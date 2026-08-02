"""Clarification HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from zhangwen.clarification.service import ClarificationService
from zhangwen.config import settings
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.repository import ProjectRepository
from zhangwen.security.credentials import BackendCredentialStore

router = APIRouter(prefix="/api/projects", tags=["clarification"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


class ClarifyRequest(BaseModel):
    userMessage: str = Field(min_length=1, max_length=20000)


class ClarificationOptionOut(BaseModel):
    id: str
    label: str
    description: str | None = None
    recommended: bool | None = None


class ClarificationQuestionOut(BaseModel):
    id: str
    type: str
    question: str
    options: list[ClarificationOptionOut] = []


class ClarificationRoundOut(BaseModel):
    round: int
    questions: list[ClarificationQuestionOut]
    completeness: int
    message: str


class ClarifyResponse(BaseModel):
    round: ClarificationRoundOut


class AnswerItem(BaseModel):
    questionId: str
    selectedOptionIds: list[str] = []
    textInput: str | None = None
    usedRecommendation: bool | None = None


class AnswerQuestionsRequest(BaseModel):
    answers: list[AnswerItem]


class AnswerQuestionsResponse(BaseModel):
    round: ClarificationRoundOut


@router.post("/{project_id}/clarify", response_model=ClarifyResponse)
async def clarify(project_id: str, request: ClarifyRequest) -> ClarifyResponse:
    repo = _repo()
    workspace = repo.get_workspace(project_id)
    try:
        config, api_key = _get_llm_config()
        result = await ClarificationService(provider_factory()).clarify(
            user_message=request.userMessage,
            context_messages=workspace.conversation.messages,
            config=config,
            api_key=api_key,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc

    # Count existing rounds
    from zhangwen.solutions.repository import SolutionRepository
    sol_repo = SolutionRepository(repo.db_path)
    conn = sol_repo._connect()
    round_count = conn.execute(
        "SELECT COUNT(*) FROM clarification_rounds WHERE project_id = ?",
        (project_id,),
    ).fetchone()[0]
    conn.close()

    round_number = round_count + 1

    # Store round
    import json
    import uuid
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    round_id = f"clr_{uuid.uuid4().hex}"
    questions_data = [q.model_dump(mode="json") for q in result.questions]
    with sol_repo._connect() as conn2:
        conn2.execute(
            """
            INSERT INTO clarification_rounds
              (id, project_id, round_number, completeness, questions_json, answers_json, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (round_id, project_id, round_number, result.completeness,
             json.dumps(questions_data, ensure_ascii=False), now),
        )

    # Update project stage to CLARIFYING
    from zhangwen.projects.models import ProjectStage
    with repo._connect() as conn3:
        conn3.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (ProjectStage.CLARIFYING.value, now, project_id),
        )

    out_questions = [
        ClarificationQuestionOut(
            id=q.id,
            type=q.type,
            question=q.question,
            options=[
                ClarificationOptionOut(
                    id=o.id, label=o.label,
                    description=o.description, recommended=o.recommended,
                )
                for o in q.options
            ],
        )
        for q in result.questions
    ]

    return ClarifyResponse(
        round=ClarificationRoundOut(
            round=round_number,
            questions=out_questions,
            completeness=result.completeness,
            message=result.message,
        )
    )


@router.post("/{project_id}/clarify/answer", response_model=AnswerQuestionsResponse)
async def answer_questions(
    project_id: str, request: AnswerQuestionsRequest
) -> AnswerQuestionsResponse:
    repo = _repo()
    try:
        config, api_key = _get_llm_config()
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc

    # Store answers in the latest round
    import json
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    from zhangwen.solutions.repository import SolutionRepository
    sol_repo = SolutionRepository(repo.db_path)
    with sol_repo._connect() as conn:
        latest = conn.execute(
            """
            SELECT * FROM clarification_rounds
            WHERE project_id = ? ORDER BY round_number DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if latest:
            answers_data = [a.model_dump(mode="json") for a in request.answers]
            conn.execute(
                "UPDATE clarification_rounds SET answers_json = ? WHERE id = ?",
                (json.dumps(answers_data, ensure_ascii=False), latest["id"]),
            )

    # Run next clarification round
    workspace = repo.get_workspace(project_id)
    try:
        result = await ClarificationService(provider_factory()).clarify(
            user_message="用户已回答上一轮问题，请继续评估需求完整度并提出新的澄清问题。",
            context_messages=workspace.conversation.messages,
            config=config,
            api_key=api_key,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc

    round_count = 0
    with sol_repo._connect() as conn2:
        round_count = conn2.execute(
            "SELECT COUNT(*) FROM clarification_rounds WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        # Store new round
        import uuid
        round_id = f"clr_{uuid.uuid4().hex}"
        questions_data = [q.model_dump(mode="json") for q in result.questions]
        conn2.execute(
            """
            INSERT INTO clarification_rounds
              (id, project_id, round_number, completeness, questions_json, answers_json, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (round_id, project_id, round_count + 1, result.completeness,
             json.dumps(questions_data, ensure_ascii=False), now),
        )

    out_questions = [
        ClarificationQuestionOut(
            id=q.id, type=q.type, question=q.question,
            options=[
                ClarificationOptionOut(
                    id=o.id, label=o.label,
                    description=o.description, recommended=o.recommended,
                )
                for o in q.options
            ],
        )
        for q in result.questions
    ]

    return AnswerQuestionsResponse(
        round=ClarificationRoundOut(
            round=round_count + 1,
            questions=out_questions,
            completeness=result.completeness,
            message=result.message,
        )
    )


def _repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _get_llm_config():
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
    )
