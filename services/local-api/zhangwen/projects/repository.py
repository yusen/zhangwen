"""SQLite project repository."""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from zhangwen.auth.context import current_owner_subject
from zhangwen.experts.entry_router import (
    RouterOutput as EntryRouterOutput,
    local_recovery_route,
)
from zhangwen.hardware.hardware_skills import (
    HardwareSkillNotFoundError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
    SUPPORTED_CONTROLLER_COMPONENT_IDS,
)
from zhangwen.hardware.models import HardwareCategory, ValidationSeverity
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.llm.contracts import (
    ChatMessage,
    ChatMessageStatus,
    ChatRole,
    LLMError,
    LLMErrorCode,
    LLMModelId,
    LLMModelSelection,
    TokenUsage,
)
from zhangwen.llm.errors import make_llm_error
from zhangwen.projects.errors import (
    ConversationContextError,
    ProjectArchivedError,
    ProjectDatabaseCorruptError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.models import (
    ActiveArtifactVersion,
    CoordinatorIssue,
    CoordinatorItem,
    CoordinatorSeverity,
    Conversation,
    DomainTaskStatus,
    Draft,
    ExpertConversation,
    ExpertDefinition,
    ExpertType,
    ExpertWorkspaceStatus,
    PendingItem,
    PendingItemPriority,
    PendingItemStatus,
    Project,
    ProjectCoordinatorState,
    ProjectDecision,
    ProjectExpert,
    ProjectExpertStatus,
    ProjectKickoff,
    ProjectPersistenceVersion,
    ProjectProfile,
    ProjectSharedContext,
    ProjectStage,
    ProjectSummary,
    ProjectWorkspace,
    RouterOutput,
    SharedFactStatus,
    SharedFact,
    SuggestedProject,
    normalize_selected_hardware_ids,
)

THREE_EXPERT_TYPES: set[ExpertType] = {
    ExpertType.PROBLEM_GUIDE,
    ExpertType.SMART_ENGINEER,
    ExpertType.STRUCTURE_ENGINEER,
}
AUTOMATIC_RECOVERY_LABEL = "已按原需求自动重试"
MAX_AUTOMATIC_RECOVERY_ATTEMPTS = 3


@dataclass(frozen=True)
class ClarificationAnswerValue:
    question_id: str
    selected_option_ids: tuple[str, ...] = ()
    text_input: str | None = None


class ProjectRepository:
    def __init__(self, data_dir: Path) -> None:
        self._owner_subject = current_owner_subject()
        self._db_dir = data_dir / "projects"
        self._db_path = self._db_dir / "zhangwen.sqlite3"
        self._backup_dir = self._db_dir / "backups"
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_database()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def data_dir(self) -> Path:
        return self._db_dir.parent

    def assert_project_access(self, project_id: str) -> None:
        with self._connect() as conn:
            self._project_row(conn, project_id)

    def list_projects(
        self,
        *,
        include_archived: bool = False,
    ) -> tuple[list[ProjectSummary], str | None]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.*, d.updated_at AS draft_updated_at,
                       (
                         SELECT COUNT(*)
                         FROM messages m
                         WHERE m.project_id = p.id
                       ) AS message_count,
                       (
                         SELECT GROUP_CONCAT(pe.id)
                         FROM project_experts pe
                         WHERE pe.project_id = p.id
                           AND pe.removed_at IS NULL
                           AND pe.archived_legacy_thread = 0
                       ) AS active_expert_ids
                FROM projects p
                LEFT JOIN drafts d ON d.project_id = p.id
                WHERE (? = 1 OR p.archived_at IS NULL)
                  AND (? IS NULL OR p.owner_subject = ?)
                ORDER BY COALESCE(p.last_opened_at, p.updated_at) DESC
                """,
                (
                    1 if include_archived else 0,
                    self._owner_subject,
                    self._owner_subject,
                ),
            ).fetchall()
            active = self._get_meta(conn, "activeProjectId") or None
            return [self._summary(row) for row in rows], active

    def create_project(
        self,
        name: str | None,
        initial_idea: str,
        selected_model: LLMModelSelection | None = None,
        selected_expert_types: list[ExpertType] | None = None,
        *,
        project_id_override: str | None = None,
    ) -> ProjectWorkspace:
        suggestion = self.suggest_project(initial_idea)
        return self.create_project_from_idea(
            idea=initial_idea,
            project_name=name or suggestion.name,
            initial_expert=None,
            participating_experts=selected_expert_types or suggestion.recommendedExpertTypes,
            selected_model=selected_model,
            router_result=suggestion.routerResult,
            expert_selection_mode="auto" if selected_expert_types is None else "manual",
            project_id_override=project_id_override,
        )

    def create_project_from_idea(
        self,
        *,
        idea: str,
        project_name: str,
        initial_expert: ExpertType | None,
        participating_experts: list[ExpertType],
        selected_model: LLMModelSelection | None = None,
        router_result: RouterOutput | EntryRouterOutput | None = None,
        expert_selection_mode: str = "auto",
        idempotency_key: str | None = None,
        selected_hardware_ids: list[str] | None = None,
        project_id_override: str | None = None,
        after_create: Callable[[sqlite3.Connection, str, str], None] | None = None,
    ) -> ProjectWorkspace:
        clean_idea = _clean_idea(idea)
        clean_name = _clean_name(project_name)
        try:
            preferred_hardware_ids = normalize_selected_hardware_ids(
                selected_hardware_ids
            )
        except ValueError as exc:
            raise ProjectValidationError(str(exc)) from exc
        if preferred_hardware_ids:
            seed_default_components(self._db_path)
            try:
                HardwareSkillRepository(
                    self.data_dir,
                    self._db_path,
                ).migrate_legacy_rows()
            except (HardwareSkillNotFoundError, HardwareSkillValidationError) as exc:
                raise ProjectValidationError(
                    "所选硬件 Skill 不存在、未激活或未通过校验，请刷新硬件库后重新选择。"
                ) from exc
        model = selected_model or LLMModelId.DEEPSEEK_V4_FLASH
        route = _router_output_from_any(router_result) or _router_output_from_entry(
            local_recovery_route(clean_idea)
        )
        expert_types = _normalize_creation_experts(participating_experts)
        if not expert_types:
            expert_types = _normalize_creation_experts(route.recommendedExperts)
        if (
            _requires_smart_engineer(clean_idea, preferred_hardware_ids)
            and ExpertType.SMART_ENGINEER not in expert_types
        ):
            expert_types.append(ExpertType.SMART_ENGINEER)
        if not expert_types:
            raise ProjectValidationError("至少需要选择一位专家。")
        if initial_expert is None:
            initial = route.initialExpert if route.initialExpert in expert_types else expert_types[0]
        else:
            initial = _canonical_expert_type(initial_expert)
            if initial not in expert_types:
                raise ProjectValidationError("初始专家必须属于已选择专家。")
        expert_types = _order_experts_with_initial(expert_types, initial)
        safe_selection_mode = (
            "manual" if expert_selection_mode == "manual" else "auto"
        )
        now = _now()
        project_id = project_id_override or _id("prj")
        with self._connect() as conn:
            if idempotency_key:
                existing = conn.execute(
                    """
                    SELECT project_id FROM project_shared_facts
                    WHERE field = 'creation_idempotency_key'
                      AND value_json = ?
                      AND EXISTS (
                        SELECT 1 FROM projects p
                        WHERE p.id = project_shared_facts.project_id
                          AND (? IS NULL OR p.owner_subject = ?)
                      )
                    LIMIT 1
                    """,
                    (
                        json.dumps(idempotency_key, ensure_ascii=False),
                        self._owner_subject,
                        self._owner_subject,
                    ),
                ).fetchone()
                if existing is not None:
                    return self.get_workspace(str(existing["project_id"]))
            preferred_hardware, preferred_hardware_validation = (
                self._validated_hardware_snapshots(
                    preferred_hardware_ids,
                )
            )
            conn.execute(
                """
                INSERT INTO projects (
                  id, name, stage, initial_idea, selected_model,
                  created_at, updated_at, last_opened_at, owner_subject
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    clean_name,
                    ProjectStage.IDEA.value,
                    clean_idea,
                    str(model),
                    now,
                    now,
                    now,
                    self._owner_subject,
                ),
            )
            shared_context_id = self._create_shared_context(
                conn,
                project_id,
                clean_idea,
                now,
            )
            coordinator_id = self._create_coordinator(conn, project_id, now)
            created_experts: list[ProjectExpert] = []
            for expert_type in expert_types:
                created_experts.append(
                    self._create_project_expert(
                        conn,
                        project_id=project_id,
                        expert_type=expert_type,
                        now=now,
                        is_initial_active=expert_type == initial,
                    )
                )
            active_expert = next(
                expert for expert in created_experts if expert.expertType == initial
            )
            active_expert_id = active_expert.id
            conn.execute(
                "UPDATE projects SET active_expert_id = ? WHERE id = ?",
                (active_expert_id, project_id),
            )
            conn.execute(
                """
                INSERT INTO drafts (project_id, content, updated_at)
                VALUES (?, '', NULL)
                """,
                (project_id,),
            )
            self._insert_creation_records(
                conn,
                project_id=project_id,
                active_expert=active_expert,
                idea=clean_idea,
                model=model,
                route=route,
                expert_selection_mode=safe_selection_mode,
                idempotency_key=idempotency_key,
                preferred_hardware=preferred_hardware,
                preferred_hardware_validation=preferred_hardware_validation,
                now=now,
            )
            self._sync_coordinator(
                conn,
                project_id=project_id,
                coordinator_id=coordinator_id,
                active_expert_id=active_expert_id,
                now=now,
            )
            if after_create is not None:
                after_create(conn, project_id, now)
            _ = shared_context_id
            self._set_meta(conn, "activeProjectId", project_id)
        return self.get_workspace(project_id)

    def suggest_project(
        self,
        initial_idea: str,
        user_selected_expert: ExpertType | None = None,
        router_result: EntryRouterOutput | RouterOutput | None = None,
    ) -> SuggestedProject:
        idea = _clean_idea(initial_idea)
        route = (
            router_result
            if isinstance(router_result, EntryRouterOutput)
            else local_recovery_route(
                idea,
                initial_expert=(
                    _canonical_expert_type(user_selected_expert)
                    if user_selected_expert is not None
                    else None
                ),
            )
        )
        if isinstance(route, RouterOutput):
            route = EntryRouterOutput.model_validate(route.model_dump(mode="json"))
        router_result = _router_output_from_entry(route)
        return SuggestedProject(
            name=route.projectName,
            initialIdea=idea,
            recommendedExpertTypes=route.recommendedExperts,
            availableExperts=self._expert_definitions(),
            initialExpert=route.initialExpert,
            routerResult=router_result,
            reason=route.reason,
            confidence=route.confidence,
            requiresClarification=route.requiresClarification,
        )

    def get_workspace(self, project_id: str) -> ProjectWorkspace:
        with self._connect() as conn:
            row = self._project_row(conn, project_id)
            experts = self._project_experts(conn, project_id)
            definitions = self._expert_definitions(conn)
            active_expert = self._active_expert(row, experts)
            conversation_row = (
                conn.execute(
                    "SELECT * FROM conversations WHERE id = ?",
                    (active_expert.conversationId,),
                ).fetchone()
                if active_expert
                else None
            )
            if conversation_row is None:
                conversation_row = conn.execute(
                    """
                    SELECT * FROM conversations
                    WHERE project_id = ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            if conversation_row is None:
                raise ProjectNotFoundError("项目会话不存在。")
            draft = self._project_draft(conn, project_id)
            messages = self._messages_for_conversation(
                conn,
                project_id,
                conversation_row["id"],
            )
            expert_conversations = self._expert_conversations(
                conn,
                project_id,
                experts + self._archived_legacy_project_experts(conn, project_id),
                definitions,
            )
            shared_context = self._shared_context(conn, project_id)
            coordinator = self._coordinator(conn, project_id, experts)
            kickoff = self._project_kickoff(conn, project_id)
            return ProjectWorkspace(
                project=self._project(
                    row,
                    conversation_row["id"],
                    experts=experts,
                    shared_context=shared_context,
                    coordinator=coordinator,
                ),
                conversation=Conversation(
                    id=conversation_row["id"],
                    projectId=project_id,
                    messages=messages,
                    updatedAt=conversation_row["updated_at"],
                ),
                draft=draft,
                experts=experts,
                expertDefinitions=definitions,
                expertConversations=expert_conversations,
                sharedContext=shared_context,
                coordinator=coordinator,
                kickoff=kickoff,
            )

    def open_project(self, project_id: str) -> ProjectWorkspace:
        now = _now()
        with self._connect() as conn:
            self._ensure_not_archived(conn, project_id)
            conn.execute(
                "UPDATE projects SET last_opened_at = ?, updated_at = ? WHERE id = ?",
                (now, now, project_id),
            )
            self._set_meta(conn, "activeProjectId", project_id)
        return self.get_workspace(project_id)

    def set_active_expert(self, project_id: str, project_expert_id: str) -> ProjectWorkspace:
        now = _now()
        with self._connect() as conn:
            self._ensure_not_archived(conn, project_id)
            self._ensure_project_expert_row(conn, project_id, project_expert_id)
            conn.execute(
                "UPDATE projects SET active_expert_id = ?, updated_at = ? WHERE id = ?",
                (project_expert_id, now, project_id),
            )
        return self.get_workspace(project_id)

    def add_project_expert(
        self,
        project_id: str,
        expert_type: ExpertType,
        *,
        activate: bool = False,
    ) -> ProjectWorkspace:
        now = _now()
        expert_type = _canonical_expert_type(expert_type)
        if expert_type not in THREE_EXPERT_TYPES:
            raise ProjectValidationError("只能添加三师系统中的专家。")
        with self._connect() as conn:
            project = self._ensure_not_archived(conn, project_id)
            active_existing = conn.execute(
                """
                SELECT id FROM project_experts
                WHERE project_id = ?
                  AND expert_type = ?
                  AND removed_at IS NULL
                  AND archived_legacy_thread = 0
                LIMIT 1
                """,
                (project_id, expert_type.value),
            ).fetchone()
            if active_existing is not None:
                expert_id = str(active_existing["id"])
                if activate:
                    conn.execute(
                        "UPDATE projects SET active_expert_id = ?, updated_at = ? WHERE id = ?",
                        (expert_id, now, project_id),
                    )
            else:
                removed_existing = conn.execute(
                    """
                    SELECT * FROM project_experts
                    WHERE project_id = ?
                      AND expert_type = ?
                      AND removed_at IS NOT NULL
                      AND archived_legacy_thread = 0
                    ORDER BY removed_at DESC
                    LIMIT 1
                    """,
                    (project_id, expert_type.value),
                ).fetchone()
                if removed_existing is not None:
                    expert_id = str(removed_existing["id"])
                    status = ProjectExpertStatus.WORKING if activate else ProjectExpertStatus.IDLE
                    conn.execute(
                        """
                        UPDATE project_experts
                        SET removed_at = NULL,
                            status = ?,
                            workspace_status = ?,
                            current_task = COALESCE(current_task, ?)
                        WHERE id = ?
                        """,
                        (
                            status.value,
                            _workspace_status_for_project_status(status),
                            _default_expert_task(expert_type),
                            expert_id,
                        ),
                    )
                else:
                    expert = self._create_project_expert(
                        conn,
                        project_id=project_id,
                        expert_type=expert_type,
                        now=now,
                        is_initial_active=activate,
                    )
                    expert_id = expert.id

            current_active = self._active_project_expert_row(conn, project)
            if activate or current_active is None:
                conn.execute(
                    "UPDATE projects SET active_expert_id = ?, updated_at = ? WHERE id = ?",
                    (expert_id, now, project_id),
                )
            else:
                conn.execute(
                    "UPDATE projects SET updated_at = ? WHERE id = ?",
                    (now, project_id),
                )
        return self.get_workspace(project_id)

    def remove_project_expert(
        self,
        project_id: str,
        project_expert_id: str,
        *,
        confirm_impact: bool = False,
    ) -> ProjectWorkspace:
        _ = confirm_impact
        now = _now()
        with self._connect() as conn:
            project = self._ensure_not_archived(conn, project_id)
            expert_row = self._ensure_project_expert_row(conn, project_id, project_expert_id)
            active_rows = conn.execute(
                """
                SELECT id FROM project_experts
                WHERE project_id = ?
                  AND removed_at IS NULL
                  AND archived_legacy_thread = 0
                ORDER BY CASE expert_type
                  WHEN 'problem_guide' THEN 1
                  WHEN 'smart_engineer' THEN 2
                  WHEN 'structure_engineer' THEN 3
                  ELSE 99
                END
                """,
                (project_id,),
            ).fetchall()
            if len(active_rows) <= 1:
                raise ProjectValidationError("项目至少需要保留一位专家。")

            conn.execute(
                """
                UPDATE project_experts
                SET removed_at = ?,
                    status = ?,
                    workspace_status = ?
                WHERE id = ?
                """,
                (
                    now,
                    ProjectExpertStatus.IDLE.value,
                    ExpertWorkspaceStatus.NOT_STARTED.value,
                    project_expert_id,
                ),
            )
            if project["active_expert_id"] == project_expert_id:
                next_active = next(
                    (row["id"] for row in active_rows if row["id"] != project_expert_id),
                    None,
                )
                conn.execute(
                    "UPDATE projects SET active_expert_id = ?, updated_at = ? WHERE id = ?",
                    (next_active, now, project_id),
                )
            else:
                conn.execute(
                    "UPDATE projects SET updated_at = ? WHERE id = ?",
                    (now, project_id),
                )
            _ = expert_row
        return self.get_workspace(project_id)

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        selected_model: LLMModelSelection | None = None,
    ) -> ProjectWorkspace:
        if name is None and selected_model is None:
            return self.get_workspace(project_id)
        now = _now()
        with self._connect() as conn:
            self._ensure_not_archived(conn, project_id)
            if name is not None:
                conn.execute(
                    "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
                    (_clean_name(name), now, project_id),
                )
            if selected_model is not None:
                conn.execute(
                    "UPDATE projects SET selected_model = ?, updated_at = ? WHERE id = ?",
                    (str(selected_model), now, project_id),
                )
        return self.get_workspace(project_id)

    def replace_preferred_hardware(
        self,
        project_id: str,
        selected_hardware_ids: list[str],
    ) -> tuple[ProjectWorkspace, list[str]]:
        """Replace the user-confirmed project hardware as one audited snapshot."""

        try:
            component_ids = normalize_selected_hardware_ids(selected_hardware_ids)
        except ValueError as exc:
            raise ProjectValidationError(str(exc)) from exc
        if component_ids:
            seed_default_components(self._db_path)
            try:
                HardwareSkillRepository(
                    self.data_dir,
                    self._db_path,
                ).migrate_legacy_rows()
            except (HardwareSkillNotFoundError, HardwareSkillValidationError) as exc:
                raise ProjectValidationError(
                    "所选硬件 Skill 不存在、未激活或未通过校验，请刷新硬件库后重新选择。"
                ) from exc
        now = _now()
        new_fact_id = _id("fact")
        with self._connect() as conn:
            self._ensure_not_archived(conn, project_id)
            snapshots, validation = self._validated_hardware_snapshots(component_ids)
            value: dict[str, object] = {
                "policy": "prefer_selected_and_fill_gaps",
                "components": snapshots,
            }
            if validation is not None:
                value["validation"] = validation
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = ?, superseded_by = ?, updated_at = ?
                WHERE project_id = ?
                  AND COALESCE(key, field) = 'preferred_hardware'
                  AND status = ?
                """,
                (
                    SharedFactStatus.SUPERSEDED.value,
                    new_fact_id,
                    now,
                    project_id,
                    SharedFactStatus.CONFIRMED.value,
                ),
            )
            self._insert_shared_fact_row(
                conn,
                project_id=project_id,
                field="preferred_hardware",
                key="preferred_hardware",
                value=value,
                source_type="user",
                source_expert_id=None,
                proposed_by=None,
                status=SharedFactStatus.CONFIRMED,
                confirmed_by="user",
                confirmed_at=now,
                now=now,
                fact_id=new_fact_id,
            )
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )
        warnings = [
            str(item.get("message", ""))
            for item in (validation or {}).get("warnings", [])
            if isinstance(item, dict) and item.get("message")
        ][:12]
        return self.get_workspace(project_id), warnings

    def set_delivery_track(self, project_id: str, track: str) -> ProjectWorkspace:
        """Persist the user-selected post-solution delivery route."""

        if track not in {"project", "lesson"}:
            raise ProjectValidationError("未知产物路线，只能选择工程立项或教案版本。")
        now = _now()
        new_fact_id = _id("fact")
        with self._connect() as conn:
            self._ensure_not_archived(conn, project_id)
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = ?, superseded_by = ?, updated_at = ?
                WHERE project_id = ?
                  AND COALESCE(key, field) = 'delivery_track'
                  AND status = ?
                """,
                (
                    SharedFactStatus.SUPERSEDED.value,
                    new_fact_id,
                    now,
                    project_id,
                    SharedFactStatus.CONFIRMED.value,
                ),
            )
            self._insert_shared_fact_row(
                conn,
                project_id=project_id,
                field="delivery_track",
                key="delivery_track",
                value={"track": track},
                source_type="user",
                source_expert_id=None,
                proposed_by=None,
                status=SharedFactStatus.CONFIRMED,
                confirmed_by="user",
                confirmed_at=now,
                now=now,
                fact_id=new_fact_id,
            )
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )
        return self.get_workspace(project_id)

    def get_delivery_track(self, project_id: str) -> str:
        with self._connect() as conn:
            self._ensure_not_archived(conn, project_id)
            return self._delivery_track(conn, project_id)

    def _delivery_track(self, conn: sqlite3.Connection, project_id: str) -> str:
        row = conn.execute(
            """
            SELECT value_json FROM project_shared_facts
            WHERE project_id = ?
              AND COALESCE(key, field) = 'delivery_track'
              AND status = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id, SharedFactStatus.CONFIRMED.value),
        ).fetchone()
        if row is None:
            return "project"
        try:
            value = json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError):
            return "project"
        track = value.get("track") if isinstance(value, dict) else None
        return track if track in {"project", "lesson"} else "project"

    def archive_project(self, project_id: str, archived: bool) -> tuple[list[ProjectSummary], str | None]:
        now = _now()
        with self._connect() as conn:
            self._project_row(conn, project_id)
            conn.execute(
                "UPDATE projects SET archived_at = ?, updated_at = ? WHERE id = ?",
                (now if archived else None, now, project_id),
            )
            active = self._get_meta(conn, "activeProjectId") or None
            if archived and active == project_id:
                next_project = conn.execute(
                    """
                    SELECT id
                    FROM projects
                    WHERE archived_at IS NULL AND id <> ?
                      AND (? IS NULL OR owner_subject = ?)
                    ORDER BY COALESCE(last_opened_at, updated_at) DESC
                    LIMIT 1
                    """,
                    (project_id, self._owner_subject, self._owner_subject),
                ).fetchone()
                self._set_meta(
                    conn,
                    "activeProjectId",
                    str(next_project["id"]) if next_project is not None else "",
                )
            elif not archived and not active:
                self._set_meta(conn, "activeProjectId", project_id)
        return self.list_projects()

    def restore_project(self, project_id: str) -> tuple[list[ProjectSummary], str | None]:
        return self.archive_project(project_id, False)

    def legacy_claim_status(self) -> tuple[int, bool]:
        if self._owner_subject is None:
            return 0, True
        with self._connect() as conn:
            count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM projects WHERE owner_subject IS NULL"
                ).fetchone()[0]
            )
            row = conn.execute(
                """
                SELECT legacy_claim_decision_at
                FROM account_workspace_state
                WHERE owner_subject = ?
                """,
                (self._owner_subject,),
            ).fetchone()
        return count, bool(row is not None and row["legacy_claim_decision_at"])

    def decide_legacy_claim(self, *, claim_all: bool) -> int:
        if self._owner_subject is None:
            raise ProjectValidationError("旧项目认领需要已登录账号。")
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            claimed = 0
            if claim_all:
                cursor = conn.execute(
                    """
                    UPDATE projects
                    SET owner_subject = ?, updated_at = ?
                    WHERE owner_subject IS NULL
                    """,
                    (self._owner_subject, now),
                )
                claimed = cursor.rowcount
            conn.execute(
                """
                INSERT INTO account_workspace_state (
                  owner_subject, current_project_id, legacy_claim_decision_at, updated_at
                ) VALUES (?, NULL, ?, ?)
                ON CONFLICT(owner_subject) DO UPDATE SET
                  legacy_claim_decision_at = excluded.legacy_claim_decision_at,
                  updated_at = excluded.updated_at
                """,
                (self._owner_subject, now, now),
            )
        return claimed

    def save_draft(
        self,
        project_id: str,
        content: str,
        project_expert_id: str | None = None,
    ) -> ProjectWorkspace:
        now = _now()
        with self._connect() as conn:
            project = self._ensure_not_archived(conn, project_id)
            expert_row = (
                self._ensure_project_expert_row(conn, project_id, project_expert_id)
                if project_expert_id
                else None
            )
            if project_expert_id and expert_row is not None:
                conn.execute(
                    """
                    INSERT INTO expert_drafts (project_expert_id, project_id, content, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(project_expert_id) DO UPDATE SET
                      content = excluded.content,
                      updated_at = excluded.updated_at
                    """,
                    (expert_row["id"], project_id, content, now),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO drafts (project_id, content, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                      content = excluded.content,
                      updated_at = excluded.updated_at
                    """,
                    (project_id, content, now),
                )
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )
        return self.get_workspace(project_id)

    def append_user_and_assistant(
        self,
        project_id: str,
        content: str,
        model: LLMModelSelection,
        *,
        project_expert_id: str | None = None,
        turn_id: str | None = None,
        response_turn_id: str | None = None,
        client_turn_id: str | None = None,
        parent_turn_id: str | None = None,
        request_json: dict[str, Any] | None = None,
        user_metadata: dict[str, Any] | None = None,
        clarification_source_message_id: str | None = None,
        clarification_answers: list[ClarificationAnswerValue] | None = None,
        require_complete_clarification: bool = False,
        automatic_recovery_source_message_id: str | None = None,
        clarification_transaction: (
            Callable[[sqlite3.Connection, str], None] | None
        ) = None,
    ) -> tuple[ProjectWorkspace, ChatMessage, ChatMessage]:
        if not content.strip():
            raise ProjectValidationError("消息不能为空。")
        now = _now()
        turn_id = turn_id or _id("turn")
        response_turn_id = response_turn_id or _id("turn")
        user_id = _id("msg")
        assistant_id = _id("msg")
        with self._connect() as conn:
            project = self._ensure_not_archived(conn, project_id)
            expert_row = (
                self._ensure_project_expert_row(conn, project_id, project_expert_id)
                if project_expert_id
                else self._active_project_expert_row(conn, project)
            )
            conversation_id = (
                expert_row["conversation_id"]
                if expert_row is not None
                else conn.execute(
                    """
                    SELECT id FROM conversations
                    WHERE project_id = ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()["id"]
            )
            if automatic_recovery_source_message_id:
                # One local Sidecar owns this SQLite database. BEGIN IMMEDIATE
                # serializes automatic recovery claims so two browser/desktop
                # clients cannot both pass the read-before-write check.
                conn.execute("BEGIN IMMEDIATE")
                self._claim_automatic_recovery_with_conn(
                    conn,
                    project_id=project_id,
                    conversation_id=str(conversation_id),
                    source_message_id=automatic_recovery_source_message_id,
                    request_content=content,
                )
            validated_answers = self._validate_structured_answers_with_conn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                source_message_id=clarification_source_message_id,
                answers=clarification_answers or [],
                require_complete=require_complete_clarification,
            )
            expert_metadata = {
                "projectExpertId": str(expert_row["id"]) if expert_row is not None else None,
                "expertType": str(expert_row["expert_type"]) if expert_row is not None else None,
                "conversationId": str(conversation_id),
            }
            user = ChatMessage(
                id=user_id,
                role=ChatRole.USER,
                content=content.strip(),
                metadata={
                    **expert_metadata,
                    **(user_metadata or {}),
                    "turnId": turn_id,
                    "clientTurnId": client_turn_id,
                    "requestTurnId": turn_id,
                },
                status=ChatMessageStatus.COMPLETED,
                createdAt=now,
                updatedAt=now,
                model=model,
            )
            assistant = ChatMessage(
                id=assistant_id,
                role=ChatRole.ASSISTANT,
                content="",
                metadata={
                    **expert_metadata,
                    "turnId": response_turn_id,
                    "parentTurnId": turn_id,
                    "clientTurnId": client_turn_id,
                    "requestTurnId": turn_id,
                    "responseTurnId": response_turn_id,
                },
                status=ChatMessageStatus.STREAMING,
                createdAt=now,
                updatedAt=now,
                model=model,
            )
            self._insert_message(conn, conversation_id, project_id, user)
            self._insert_message(conn, conversation_id, project_id, assistant)
            try:
                conn.execute(
                    """
                    INSERT INTO conversation_turns (
                      id, project_id, conversation_id, client_turn_id, parent_turn_id,
                      user_message_id, assistant_message_id, request_json, status,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn_id,
                        project_id,
                        conversation_id,
                        client_turn_id,
                        parent_turn_id,
                        user.id,
                        assistant.id,
                        _dump(request_json or {}) or "{}",
                        "PENDING",
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConversationContextError(
                    "DUPLICATE_TURN",
                    "Duplicate conversation turn.",
                ) from exc
            self._record_structured_answers_with_conn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_message_id=user.id,
                client_turn_id=client_turn_id or turn_id,
                source_message_id=clarification_source_message_id,
                validated_answers=validated_answers,
            )
            if clarification_transaction is not None:
                clarification_transaction(conn, user.id)
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            conn.execute(
                "UPDATE projects SET updated_at = ?, selected_model = ? WHERE id = ?",
                (now, str(model), project["id"]),
            )
            if expert_row is not None:
                conn.execute(
                    """
                    INSERT INTO expert_drafts (project_expert_id, project_id, content, updated_at)
                    VALUES (?, ?, '', ?)
                    ON CONFLICT(project_expert_id) DO UPDATE SET
                      content = '',
                      updated_at = excluded.updated_at
                    """,
                    (expert_row["id"], project_id, now),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO drafts (project_id, content, updated_at)
                    VALUES (?, '', ?)
                    ON CONFLICT(project_id) DO UPDATE SET content = '', updated_at = excluded.updated_at
                    """,
                    (project_id, now),
                )
        return self.get_workspace(project_id), user, assistant

    def _claim_automatic_recovery_with_conn(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str,
        request_content: str,
    ) -> None:
        recovery_rows = conn.execute(
            """
            SELECT metadata_json FROM messages
            WHERE project_id = ? AND conversation_id = ? AND role = ?
              AND metadata_json IS NOT NULL
            """,
            (project_id, conversation_id, ChatRole.USER.value),
        ).fetchall()
        for recovery_row in recovery_rows:
            try:
                recovery_metadata = json.loads(str(recovery_row["metadata_json"] or "{}"))
            except (TypeError, ValueError):
                continue
            if (
                recovery_metadata.get("recoveryOfMessageId") == source_message_id
                and recovery_metadata.get("recoveryLabel") == AUTOMATIC_RECOVERY_LABEL
            ):
                raise ConversationContextError(
                    "DUPLICATE_TURN",
                    "这条失败消息已由另一窗口发起自动恢复。",
                )

        attempts = 0
        current_failure_id: str | None = source_message_id
        visited: set[str] = set()
        is_current_failure = True

        while current_failure_id and current_failure_id not in visited:
            visited.add(current_failure_id)
            row = conn.execute(
                """
                SELECT failed.role, failed.status, failed.error_json,
                       failed.metadata_json, source.content AS source_content,
                       source.metadata_json AS source_metadata_json
                FROM messages failed
                JOIN conversation_turns turn
                  ON turn.assistant_message_id = failed.id
                JOIN messages source ON source.id = turn.user_message_id
                WHERE failed.id = ?
                  AND failed.project_id = ?
                  AND failed.conversation_id = ?
                """,
                (current_failure_id, project_id, conversation_id),
            ).fetchone()
            if row is None:
                raise ConversationContextError(
                    "INVALID_REQUEST",
                    "自动恢复来源不存在或不属于当前专家会话。",
                    status_code=422,
                )

            try:
                error_payload = json.loads(str(row["error_json"] or "{}"))
                failed_metadata = json.loads(str(row["metadata_json"] or "{}"))
                source_metadata = json.loads(str(row["source_metadata_json"] or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ConversationContextError(
                    "INVALID_REQUEST",
                    "自动恢复来源元数据无效。",
                    status_code=422,
                ) from exc

            if (
                row["role"] != ChatRole.ASSISTANT.value
                or row["status"] != ChatMessageStatus.FAILED.value
                or error_payload.get("code") != LLMErrorCode.LOCAL_OUTPUT_REJECTED.value
            ):
                raise ConversationContextError(
                    "INVALID_REQUEST",
                    "只有智能工程师本地校验失败消息可以自动恢复。",
                    status_code=422,
                )
            if is_current_failure:
                if failed_metadata.get("expertType") != ExpertType.SMART_ENGINEER.value:
                    raise ConversationContextError(
                        "INVALID_REQUEST",
                        "当前失败消息不属于智能工程师。",
                        status_code=422,
                    )
                if str(row["source_content"]).strip() != request_content.strip():
                    raise ConversationContextError(
                        "INVALID_REQUEST",
                        "自动恢复必须复用原需求。",
                        status_code=422,
                    )
                is_current_failure = False

            previous_failure_id = source_metadata.get("recoveryOfMessageId")
            if (
                source_metadata.get("recoveryLabel") != AUTOMATIC_RECOVERY_LABEL
                or not isinstance(previous_failure_id, str)
                or not previous_failure_id
            ):
                break
            attempts += 1
            current_failure_id = previous_failure_id

        if attempts >= MAX_AUTOMATIC_RECOVERY_ATTEMPTS:
            raise ConversationContextError(
                "RATE_LIMITED",
                "已达到三次自动恢复上限，请补充要求后重新发送。",
                status_code=429,
            )


    def resolve_conversation_id(
        self,
        project_id: str,
        project_expert_id: str | None = None,
    ) -> str:
        with self._connect() as conn:
            project = self._ensure_not_archived(conn, project_id)
            expert_row = (
                self._ensure_project_expert_row(conn, project_id, project_expert_id)
                if project_expert_id
                else self._active_project_expert_row(conn, project)
            )
            if expert_row is not None:
                return str(expert_row["conversation_id"])
            row = conn.execute(
                """
                SELECT id FROM conversations
                WHERE project_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if row is None:
                raise ProjectNotFoundError("项目会话不存在。")
            return str(row["id"])

    def find_turn_messages(
        self,
        project_id: str,
        conversation_id: str,
        client_turn_id: str | None,
    ) -> tuple[ChatMessage, ChatMessage] | None:
        if not client_turn_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_message_id, assistant_message_id
                FROM conversation_turns
                WHERE project_id = ? AND conversation_id = ? AND client_turn_id = ?
                """,
                (project_id, conversation_id, client_turn_id),
            ).fetchone()
            if row is None or not row["user_message_id"] or not row["assistant_message_id"]:
                return None
            user_row = conn.execute(
                "SELECT * FROM messages WHERE project_id = ? AND id = ?",
                (project_id, row["user_message_id"]),
            ).fetchone()
            assistant_row = conn.execute(
                "SELECT * FROM messages WHERE project_id = ? AND id = ?",
                (project_id, row["assistant_message_id"]),
            ).fetchone()
            if user_row is None or assistant_row is None:
                return None
            return self._message(user_row), self._message(assistant_row)

    def claim_kickoff_turn(
        self,
        *,
        project_id: str,
        turn_id: str,
        content: str,
        conversation_id: str,
        project_expert_id: str | None,
        client_turn_id: str | None,
        retry: bool,
    ) -> tuple[str, ChatMessage, ChatMessage]:
        """Atomically claim the creation turn without inserting another user message."""
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT ct.*, pe.id AS project_expert_id
                FROM conversation_turns ct
                LEFT JOIN project_experts pe
                  ON pe.project_id = ct.project_id
                 AND pe.conversation_id = ct.conversation_id
                 AND pe.removed_at IS NULL
                WHERE ct.id = ? AND ct.project_id = ?
                """,
                (turn_id, project_id),
            ).fetchone()
            if row is None:
                raise ConversationContextError(
                    "STALE_CONVERSATION_TURN",
                    "Project kickoff turn no longer exists.",
                )
            request_json = _load(row["request_json"]) or {}
            if request_json.get("kind") != "project_kickoff":
                raise ConversationContextError(
                    "STALE_CONVERSATION_TURN",
                    "Conversation turn is not a project kickoff.",
                )
            if str(row["conversation_id"]) != conversation_id:
                raise ConversationContextError(
                    "PROJECT_CONTEXT_MISMATCH",
                    "Kickoff conversation does not match the current project.",
                )
            expected_expert_id = str(
                row["project_expert_id"] or request_json.get("projectExpertId") or ""
            )
            if project_expert_id != expected_expert_id:
                raise ConversationContextError(
                    "PROJECT_CONTEXT_MISMATCH",
                    "Kickoff expert does not match the current project.",
                )
            stored_client_turn_id = str(row["client_turn_id"] or "")
            if client_turn_id != stored_client_turn_id:
                raise ConversationContextError(
                    "STALE_CONVERSATION_TURN",
                    "Kickoff client turn does not match the stored turn.",
                )
            user_row = conn.execute(
                "SELECT * FROM messages WHERE project_id = ? AND id = ?",
                (project_id, row["user_message_id"]),
            ).fetchone()
            assistant_row = conn.execute(
                "SELECT * FROM messages WHERE project_id = ? AND id = ?",
                (project_id, row["assistant_message_id"]),
            ).fetchone()
            if user_row is None or assistant_row is None:
                raise ConversationContextError(
                    "STALE_CONVERSATION_TURN",
                    "Kickoff messages are incomplete.",
                )
            user_message = self._message(user_row)
            assistant_message = self._message(assistant_row)
            if user_message.content != content.strip():
                raise ConversationContextError(
                    "PROJECT_CONTEXT_MISMATCH",
                    "Kickoff content does not match the original project idea.",
                )

            status = str(row["status"])
            if status == "COMPLETED":
                return "COMPLETED", user_message, assistant_message
            if status in {"PENDING", "STREAMING"}:
                return "RUNNING", user_message, assistant_message
            if status in {"FAILED", "CANCELED"} and not retry:
                return "RETRY_REQUIRED", user_message, assistant_message
            if status not in {"READY", "FAILED", "CANCELED"}:
                raise ConversationContextError(
                    "STALE_CONVERSATION_TURN",
                    "Kickoff turn has an unsupported state.",
                )

            conn.execute(
                "UPDATE conversation_turns SET status = 'PENDING', updated_at = ? WHERE id = ?",
                (now, turn_id),
            )
            conn.execute(
                """
                UPDATE messages
                SET content = '', reasoning_content = NULL, status = ?, error_json = NULL,
                    usage_json = NULL, structured_payload_json = NULL, updated_at = ?
                WHERE id = ?
                """,
                (ChatMessageStatus.STREAMING.value, now, assistant_message.id),
            )
            claimed_row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (assistant_message.id,),
            ).fetchone()
            return "CLAIMED", user_message, self._message(claimed_row)

    def update_turn_status(self, turn_id: str | None, status: str) -> None:
        if not turn_id:
            return
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversation_turns SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, turn_id),
            )

    def register_clarification_question(
        self,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str,
        stage: ProjectStage | str,
        payload: dict[str, Any] | None,
    ) -> None:
        if not payload or payload.get("type") != "clarification":
            return
        questions = _payload_questions(payload)
        if not questions:
            return
        now = _now()
        with self._connect() as conn:
            source = conn.execute(
                """
                SELECT id FROM messages
                WHERE project_id = ? AND conversation_id = ? AND id = ?
                """,
                (project_id, conversation_id, source_message_id),
            ).fetchone()
            if source is None:
                raise ConversationContextError(
                    "PROJECT_CONTEXT_MISMATCH",
                    "Question source message does not belong to this project.",
                )
            for question in questions:
                conn.execute(
                    """
                    INSERT INTO clarification_questions (
                      id, question_id, project_id, conversation_id, source_message_id,
                      stage, text, mode, options_json, required, status,
                      answered_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                    ON CONFLICT(project_id, conversation_id, source_message_id, question_id)
                    DO UPDATE SET
                      text = excluded.text,
                      mode = excluded.mode,
                      options_json = excluded.options_json,
                      required = excluded.required,
                      updated_at = excluded.updated_at
                    """,
                    (
                        _id("qrec"),
                        str(question["id"]),
                        project_id,
                        conversation_id,
                        source_message_id,
                        stage.value if isinstance(stage, ProjectStage) else str(stage),
                        str(question.get("text") or ""),
                        str(question.get("mode") or "single"),
                        _dump(question.get("options") or []) or "[]",
                        1 if question.get("required", True) else 0,
                        "answered" if question.get("answered") else "pending",
                        now,
                        now,
                    ),
                )

    def validate_structured_answer(
        self,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str | None,
        question_id: str | None,
        selected_option_ids: list[str] | None,
        text_input: str | None,
    ) -> None:
        if not question_id:
            return
        with self._connect() as conn:
            self._validate_structured_answers_with_conn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                source_message_id=source_message_id,
                answers=[
                    ClarificationAnswerValue(
                        question_id=question_id,
                        selected_option_ids=tuple(selected_option_ids or []),
                        text_input=text_input,
                    )
                ],
                require_complete=False,
            )

    def record_structured_answer(
        self,
        *,
        project_id: str,
        conversation_id: str,
        user_message_id: str,
        client_turn_id: str,
        source_message_id: str | None,
        question_id: str | None,
        selected_option_ids: list[str] | None,
        text_input: str | None,
    ) -> None:
        if not question_id:
            return
        with self._connect() as conn:
            validated_answers = self._validate_structured_answers_with_conn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                source_message_id=source_message_id,
                answers=[
                    ClarificationAnswerValue(
                        question_id=question_id,
                        selected_option_ids=tuple(selected_option_ids or []),
                        text_input=text_input,
                    )
                ],
                require_complete=False,
            )
            self._record_structured_answers_with_conn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                client_turn_id=client_turn_id,
                source_message_id=source_message_id,
                validated_answers=validated_answers,
            )

    def _validate_structured_answers_with_conn(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str | None,
        answers: list[ClarificationAnswerValue],
        require_complete: bool,
    ) -> list[tuple[ClarificationAnswerValue, sqlite3.Row]]:
        if not answers:
            return []
        if not source_message_id:
            raise ConversationContextError(
                "QUESTION_NOT_FOUND",
                "Question source message is required.",
                status_code=404,
            )
        question_ids = [answer.question_id for answer in answers]
        if len(set(question_ids)) != len(question_ids):
            raise ConversationContextError(
                "DUPLICATE_QUESTION_ANSWER",
                "A question cannot be answered twice in one submission.",
                status_code=422,
            )
        self._register_questions_from_source_message(
            conn,
            project_id=project_id,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
        )
        rows = conn.execute(
            """
            SELECT * FROM clarification_questions
            WHERE project_id = ? AND conversation_id = ? AND source_message_id = ?
            """,
            (project_id, conversation_id, source_message_id),
        ).fetchall()
        records = {str(row["question_id"]): row for row in rows}
        validated: list[tuple[ClarificationAnswerValue, sqlite3.Row]] = []
        for answer in answers:
            record = records.get(answer.question_id)
            if record is None:
                raise ConversationContextError(
                    "QUESTION_NOT_FOUND",
                    "Question does not belong to the current conversation.",
                    status_code=404,
                )
            if record["status"] != "pending":
                if record["status"] != "answered":
                    raise ConversationContextError(
                        "STALE_CONVERSATION_TURN",
                        "Question has been superseded by a newer clarification round.",
                    )
                raise ConversationContextError(
                    "QUESTION_ALREADY_ANSWERED",
                    "Question has already been answered.",
                )
            self._validate_answer_options(
                record,
                list(answer.selected_option_ids),
                answer.text_input,
            )
            validated.append((answer, record))
        if require_complete:
            submitted = set(question_ids)
            missing_required = {
                str(row["question_id"])
                for row in rows
                if bool(row["required"])
                and row["status"] == "pending"
                and str(row["question_id"]) not in submitted
            }
            if missing_required:
                raise ConversationContextError(
                    "CLARIFICATION_INCOMPLETE",
                    "All required clarification questions must be answered together.",
                    status_code=422,
                )
        return validated

    def _record_structured_answers_with_conn(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        user_message_id: str,
        client_turn_id: str,
        source_message_id: str | None,
        validated_answers: list[tuple[ClarificationAnswerValue, sqlite3.Row]],
    ) -> None:
        for answer, record in validated_answers:
            self._record_structured_answer_with_conn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                client_turn_id=client_turn_id,
                source_message_id=source_message_id,
                answer=answer,
                record=record,
            )

    def _record_structured_answer_with_conn(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        user_message_id: str,
        client_turn_id: str,
        source_message_id: str | None,
        answer: ClarificationAnswerValue,
        record: sqlite3.Row,
    ) -> None:
        selected_option_ids = list(answer.selected_option_ids)
        options = _load(record["options_json"]) or []
        option_map = {
            str(option.get("id")): option
            for option in options
            if isinstance(option, dict) and option.get("id") is not None
        }
        labels = [
            str(option_map[option_id].get("label") or option_id)
            for option_id in selected_option_ids
            if option_id in option_map
        ]
        values = [
            str(option_map[option_id].get("value") or option_id)
            for option_id in selected_option_ids
            if option_id in option_map
        ]
        answer_type = "text" if not selected_option_ids else (
            "multiple" if len(selected_option_ids) > 1 else "single"
        )
        if answer_type == "text":
            labels = [answer.text_input or ""]
            values = [answer.text_input or ""]
        now = _now()
        try:
            conn.execute(
                """
                INSERT INTO clarification_answers (
                  id, question_record_id, question_id, project_id, conversation_id,
                  answer_type, values_json, labels_json, user_message_id,
                  client_turn_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id("ans"),
                    record["id"],
                    answer.question_id,
                    project_id,
                    conversation_id,
                    answer_type,
                    _dump(values) or "[]",
                    _dump(labels) or "[]",
                    user_message_id,
                    client_turn_id,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConversationContextError(
                "QUESTION_ALREADY_ANSWERED",
                "Question has already been answered.",
            ) from exc
        conn.execute(
            """
            UPDATE clarification_questions
            SET status = 'answered', answered_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, record["id"]),
        )
        if source_message_id:
            self._mark_source_message_answered(
                conn,
                project_id=project_id,
                source_message_id=source_message_id,
                question_id=answer.question_id,
                selected_option_ids=selected_option_ids,
                text_input=answer.text_input,
            )

    def answered_clarification_count(self, project_id: str, conversation_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM clarification_questions
                WHERE project_id = ? AND conversation_id = ? AND status = 'answered'
                """,
                (project_id, conversation_id),
            ).fetchone()
            return int(row["count"])

    def _question_record(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str | None,
        question_id: str,
    ) -> sqlite3.Row | None:
        if source_message_id:
            return conn.execute(
                """
                SELECT * FROM clarification_questions
                WHERE project_id = ?
                  AND conversation_id = ?
                  AND source_message_id = ?
                  AND question_id = ?
                """,
                (project_id, conversation_id, source_message_id, question_id),
            ).fetchone()
        return conn.execute(
            """
            SELECT * FROM clarification_questions
            WHERE project_id = ?
              AND conversation_id = ?
              AND question_id = ?
              AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id, conversation_id, question_id),
        ).fetchone()

    def _register_question_from_source_message(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str | None,
        question_id: str,
    ) -> None:
        self._register_questions_from_source_message(
            conn,
            project_id=project_id,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
        )

    def _register_questions_from_source_message(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        conversation_id: str,
        source_message_id: str | None,
    ) -> None:
        if not source_message_id:
            return
        row = conn.execute(
            """
            SELECT structured_payload_json
            FROM messages
            WHERE project_id = ? AND conversation_id = ? AND id = ?
            """,
            (project_id, conversation_id, source_message_id),
        ).fetchone()
        if row is None:
            return
        payload = _load(row["structured_payload_json"])
        if not payload or payload.get("type") != "clarification":
            return
        now = _now()
        for question in _payload_questions(payload):
            conn.execute(
                """
                INSERT INTO clarification_questions (
                  id, question_id, project_id, conversation_id, source_message_id,
                  stage, text, mode, options_json, required, status,
                  answered_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(project_id, conversation_id, source_message_id, question_id)
                DO NOTHING
                """,
                (
                    _id("qrec"),
                    str(question["id"]),
                    project_id,
                    conversation_id,
                    source_message_id,
                    "UNKNOWN",
                    str(question.get("text") or ""),
                    str(question.get("mode") or "single"),
                    _dump(question.get("options") or []) or "[]",
                    1 if question.get("required", True) else 0,
                    "answered" if question.get("answered") else "pending",
                    now,
                    now,
                ),
            )

    def _validate_answer_options(
        self,
        record: sqlite3.Row,
        selected_option_ids: list[str] | None,
        text_input: str | None,
    ) -> None:
        option_ids = [str(option_id) for option_id in (selected_option_ids or [])]
        mode = str(record["mode"])
        if mode == "text":
            if not (text_input or "").strip():
                raise ConversationContextError(
                    "OPTION_NOT_ALLOWED",
                    "Text answer is required for this question.",
                    status_code=422,
                )
            return
        options = _load(record["options_json"]) or []
        allowed = {
            str(option.get("id"))
            for option in options
            if isinstance(option, dict) and option.get("id") is not None
        }
        # M7 lets the main composer answer every visible question in natural
        # language. Keep exact option ids when the text maps cleanly, but accept
        # a non-empty textual answer for historical selection questions too.
        if not option_ids and (text_input or "").strip():
            return
        if not option_ids:
            raise ConversationContextError(
                "OPTION_NOT_ALLOWED",
                "At least one option is required.",
                status_code=422,
            )
        if mode == "single" and len(option_ids) != 1:
            raise ConversationContextError(
                "OPTION_NOT_ALLOWED",
                "This question only accepts one option.",
                status_code=422,
            )
        if any(option_id not in allowed for option_id in option_ids):
            raise ConversationContextError(
                "OPTION_NOT_ALLOWED",
                "Answer option does not belong to this question.",
                status_code=422,
            )

    def _mark_source_message_answered(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        source_message_id: str,
        question_id: str,
        selected_option_ids: list[str],
        text_input: str | None,
    ) -> None:
        row = conn.execute(
            "SELECT structured_payload_json FROM messages WHERE project_id = ? AND id = ?",
            (project_id, source_message_id),
        ).fetchone()
        if row is None:
            return
        payload = _load(row["structured_payload_json"])
        if not payload:
            return
        questions = [dict(question) for question in _payload_questions(payload)]
        matched = False
        for question in questions:
            if str(question.get("id")) != question_id:
                continue
            question["answered"] = True
            question["answer"] = {
                "questionId": question_id,
                "selectedOptionIds": selected_option_ids,
                "textInput": text_input,
                "usedRecommendation": "recommended" in set(selected_option_ids),
            }
            matched = True
        if not matched:
            return
        payload["questions"] = questions
        if isinstance(payload.get("question"), dict) and str(payload["question"].get("id")) == question_id:
            payload["question"] = next(
                question for question in questions if str(question.get("id")) == question_id
            )
        conn.execute(
            """
            UPDATE messages
            SET structured_payload_json = ?, updated_at = ?
            WHERE project_id = ? AND id = ?
            """,
            (_dump(payload), _now(), project_id, source_message_id),
        )

    def update_message(
        self,
        project_id: str,
        message_id: str,
        *,
        content: str | None = None,
        reasoning_content: str | None = None,
        status: ChatMessageStatus | None = None,
        error: LLMError | None = None,
        usage: TokenUsage | None = None,
        structured_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE project_id = ? AND id = ?",
                (project_id, message_id),
            ).fetchone()
            if row is None:
                raise ProjectNotFoundError("消息不存在。")
            conn.execute(
                """
                UPDATE messages SET
                  content = COALESCE(?, content),
                  reasoning_content = COALESCE(?, reasoning_content),
                  status = COALESCE(?, status),
                  error_json = ?,
                  usage_json = ?,
                  structured_payload_json = COALESCE(?, structured_payload_json),
                  metadata_json = COALESCE(?, metadata_json),
                  updated_at = ?
                WHERE id = ?
                """,
                (
                    content,
                    reasoning_content,
                    status.value if status else None,
                    _dump(error),
                    _dump(usage),
                    _dump(structured_payload),
                    _dump(metadata),
                    now,
                    message_id,
                ),
            )
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )
            updated = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            return self._message(updated)

    def normalize_stale_streaming(self) -> int:
        now = _now()
        error = make_llm_error(LLMErrorCode.GENERATION_INTERRUPTED)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.id, ct.id AS turn_id, ct.request_json, ct.updated_at AS turn_updated_at
                FROM messages m
                LEFT JOIN conversation_turns ct ON ct.assistant_message_id = m.id
                WHERE m.status = ?
                """,
                (ChatMessageStatus.STREAMING.value,),
            ).fetchall()
            normalized = 0
            for row in rows:
                request_json = _load(row["request_json"]) or {}
                if request_json.get("kind") == "project_kickoff":
                    try:
                        updated_at = datetime.fromisoformat(str(row["turn_updated_at"]))
                    except (TypeError, ValueError):
                        updated_at = datetime.min.replace(tzinfo=UTC)
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=UTC)
                    if (datetime.now(UTC) - updated_at).total_seconds() < 300:
                        continue
                conn.execute(
                    """
                    UPDATE messages
                    SET status = ?, error_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (ChatMessageStatus.FAILED.value, _dump(error), now, row["id"]),
                )
                if row["turn_id"]:
                    conn.execute(
                        "UPDATE conversation_turns SET status = 'FAILED', updated_at = ? WHERE id = ?",
                        (now, row["turn_id"]),
                    )
                normalized += 1
            return normalized

    def _project_kickoff(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> ProjectKickoff | None:
        rows = conn.execute(
            """
            SELECT ct.*, um.content AS user_content, am.metadata_json AS assistant_metadata,
                   am.error_json AS assistant_error, pe.id AS project_expert_id,
                   pe.expert_type
            FROM conversation_turns ct
            JOIN messages um ON um.id = ct.user_message_id
            JOIN messages am ON am.id = ct.assistant_message_id
            LEFT JOIN project_experts pe
              ON pe.project_id = ct.project_id
             AND pe.conversation_id = ct.conversation_id
             AND pe.removed_at IS NULL
            WHERE ct.project_id = ?
            ORDER BY ct.created_at ASC
            """,
            (project_id,),
        ).fetchall()
        for row in rows:
            request_json = _load(row["request_json"]) or {}
            if request_json.get("kind") != "project_kickoff":
                continue
            metadata = _load(row["assistant_metadata"]) or {}
            error = _load(row["assistant_error"]) or {}
            return ProjectKickoff(
                turnId=str(row["id"]),
                responseTurnId=str(metadata.get("responseTurnId") or metadata.get("turnId")),
                clientTurnId=str(row["client_turn_id"]),
                userMessageId=str(row["user_message_id"]),
                assistantMessageId=str(row["assistant_message_id"]),
                projectExpertId=str(
                    row["project_expert_id"] or request_json.get("projectExpertId") or ""
                ),
                conversationId=str(row["conversation_id"]),
                expertType=ExpertType(
                    row["expert_type"] or request_json.get("expertType")
                ),
                content=str(row["user_content"]),
                status=str(row["status"]),
                retryable=(
                    str(row["status"]) in {"FAILED", "CANCELED"}
                    and bool(error.get("retryable", True))
                ),
            )
        return None

    def _expert_definitions(
        self,
        conn: sqlite3.Connection | None = None,
    ) -> list[ExpertDefinition]:
        from zhangwen.experts.config import list_expert_configs
        from zhangwen.experts.packages import AgentPackageRepository

        package_repository = AgentPackageRepository(self.data_dir)
        definition_ids = {
            ExpertType.PROBLEM_GUIDE: "expert_def_problem_guide",
            ExpertType.SMART_ENGINEER: "expert_def_smart_engineer",
            ExpertType.STRUCTURE_ENGINEER: "expert_def_structure_engineer",
        }
        definitions: list[ExpertDefinition] = []
        for config in list_expert_configs():
            package = package_repository.get_package(config.id)
            definitions.append(
                ExpertDefinition(
                    id=definition_ids[config.id],
                    type=config.id,
                    name=package.displayName,
                    description=package.description,
                    icon=package.icon,
                    builtIn=True,
                    skillIds=config.skillIds,
                    supportedArtifactTypes=config.artifactTypes,
                )
            )
        return definitions

    def _project_experts(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> list[ProjectExpert]:
        rows = conn.execute(
            """
            SELECT * FROM project_experts
            WHERE project_id = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            ORDER BY CASE expert_type
              WHEN 'problem_guide' THEN 1
              WHEN 'smart_engineer' THEN 2
              WHEN 'structure_engineer' THEN 3
              ELSE 99
            END
            """,
            (project_id,),
        ).fetchall()
        return [self._project_expert(row) for row in rows]

    def _archived_legacy_project_experts(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> list[ProjectExpert]:
        rows = conn.execute(
            """
            SELECT * FROM project_experts
            WHERE project_id = ?
              AND archived_legacy_thread = 1
              AND legacy_expert_type IS NOT NULL
            ORDER BY CASE legacy_expert_type
              WHEN 'ideator' THEN 1
              WHEN 'educator' THEN 2
              WHEN 'open_hardware_designer' THEN 3
              WHEN 'structure_designer' THEN 4
              WHEN 'three_d_structure_designer' THEN 5
              ELSE 99
            END, added_at ASC
            """,
            (project_id,),
        ).fetchall()
        return [self._project_expert(row) for row in rows]

    def _project_expert(self, row: sqlite3.Row) -> ProjectExpert:
        return ProjectExpert(
            id=row["id"],
            projectId=row["project_id"],
            expertDefinitionId=row["expert_definition_id"],
            expertType=ExpertType(row["expert_type"]),
            legacyExpertType=row["legacy_expert_type"],
            archivedLegacyThread=bool(row["archived_legacy_thread"]),
            conversationId=row["conversation_id"],
            privateMemoryId=row["private_memory_id"],
            status=ProjectExpertStatus(row["status"]),
            workspaceStatus=row["workspace_status"],
            currentTask=row["current_task"],
            addedAt=row["added_at"],
            removedAt=row["removed_at"],
        )

    def _active_expert(
        self,
        project_row: sqlite3.Row,
        experts: list[ProjectExpert],
    ) -> ProjectExpert | None:
        active_expert_id = project_row["active_expert_id"]
        if active_expert_id:
            active = next((item for item in experts if item.id == active_expert_id), None)
            if active:
                return active
        return experts[0] if experts else None

    def _active_project_expert_row(
        self,
        conn: sqlite3.Connection,
        project_row: sqlite3.Row,
    ) -> sqlite3.Row | None:
        active_expert_id = project_row["active_expert_id"]
        if active_expert_id:
            row = conn.execute(
                """
                SELECT * FROM project_experts
                WHERE id = ?
                  AND project_id = ?
                  AND removed_at IS NULL
                  AND archived_legacy_thread = 0
                """,
                (active_expert_id, project_row["id"]),
            ).fetchone()
            if row is not None:
                return row
        return conn.execute(
            """
            SELECT * FROM project_experts
            WHERE project_id = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            ORDER BY CASE expert_type
              WHEN 'problem_guide' THEN 1
              WHEN 'smart_engineer' THEN 2
              WHEN 'structure_engineer' THEN 3
              ELSE 99
            END
            LIMIT 1
            """,
            (project_row["id"],),
        ).fetchone()

    def _ensure_project_expert_row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        project_expert_id: str | None,
    ) -> sqlite3.Row:
        if not project_expert_id:
            raise ProjectNotFoundError("项目专家不存在。")
        row = conn.execute(
            """
            SELECT * FROM project_experts
            WHERE id = ?
              AND project_id = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            """,
            (project_expert_id, project_id),
        ).fetchone()
        if row is None:
            raise ProjectNotFoundError("项目专家不存在。")
        return row

    def _messages_for_conversation(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        conversation_id: str,
    ) -> list[ChatMessage]:
        return [
            self._message(message_row)
            for message_row in conn.execute(
                """
                SELECT * FROM messages
                WHERE project_id = ? AND conversation_id = ?
                ORDER BY created_at ASC
                """,
                (project_id, conversation_id),
            ).fetchall()
        ]

    def _draft_for_expert(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        expert: ProjectExpert | None,
    ) -> Draft:
        if expert is not None:
            row = conn.execute(
                """
                SELECT * FROM expert_drafts
                WHERE project_expert_id = ?
                """,
                (expert.id,),
            ).fetchone()
            if row is not None:
                return Draft(
                    projectId=project_id,
                    projectExpertId=expert.id,
                    content=row["content"],
                    updatedAt=row["updated_at"],
                )
        row = conn.execute(
            "SELECT * FROM drafts WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return Draft(
            projectId=project_id,
            projectExpertId=expert.id if expert else None,
            content=row["content"] if row else "",
            updatedAt=row["updated_at"] if row else None,
        )

    def _project_draft(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> Draft:
        row = conn.execute(
            "SELECT * FROM drafts WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return Draft(
            projectId=project_id,
            projectExpertId=None,
            content=row["content"] if row else "",
            updatedAt=row["updated_at"] if row else None,
        )

    def _expert_conversations(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        experts: list[ProjectExpert],
        definitions: list[ExpertDefinition],
    ) -> list[ExpertConversation]:
        definition_map = {definition.type: definition for definition in definitions}
        conversations: list[ExpertConversation] = []
        for expert in experts:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (expert.conversationId,),
            ).fetchone()
            if row is None:
                continue
            definition = definition_map.get(expert.expertType)
            conversations.append(
                ExpertConversation(
                    id=expert.conversationId,
                    projectId=project_id,
                    projectExpertId=expert.id,
                    expertType=expert.expertType,
                    legacyExpertType=expert.legacyExpertType,
                    archivedLegacyThread=expert.archivedLegacyThread,
                    expertName=definition.name if definition else expert.expertType.value,
                    messages=self._messages_for_conversation(
                        conn,
                        project_id,
                        expert.conversationId,
                    ),
                    draft=self._draft_for_expert(conn, project_id, expert),
                    updatedAt=row["updated_at"],
                )
            )
        return conversations

    def _shared_context(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> ProjectSharedContext | None:
        row = conn.execute(
            "SELECT * FROM project_shared_contexts WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        goals = [
            SharedFact(**item)
            for item in _load_json_array(row["goals_json"])
        ]
        constraints = [
            SharedFact(**item)
            for item in _load_json_array(row["constraints_json"])
        ]
        requirements = [
            SharedFact(**item)
            for item in _load_json_array(row["requirements_json"])
        ]
        decisions = [
            ProjectDecision(**item)
            for item in _load_json_array(row["decisions_json"])
        ]
        all_facts = [*goals, *constraints, *requirements]
        return ProjectSharedContext(
            id=row["id"],
            projectId=row["project_id"],
            revision=row["revision"],
            goals=goals,
            constraints=constraints,
            requirements=requirements,
            decisions=decisions,
            confirmedFacts=[fact for fact in all_facts if fact.status == "confirmed"],
            openQuestions=[fact for fact in all_facts if fact.status == "proposed"],
            currentPendingItem=self._current_pending_item(conn, project_id),
            activeArtifactVersions=[
                ActiveArtifactVersion(**item)
                for item in _load_json_array(row["active_artifact_versions_json"])
            ],
            deliveryTrack=self._delivery_track(conn, project_id),
            updatedAt=row["updated_at"],
        )

    def _coordinator(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        experts: list[ProjectExpert],
    ) -> ProjectCoordinatorState | None:
        row = conn.execute(
            "SELECT * FROM project_coordinator_states WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        current_item_json = _load(row["current_item_json"])
        current_item = (
            CoordinatorItem(**current_item_json)
            if isinstance(current_item_json, dict)
            else None
        )
        conflicts = [
            CoordinatorIssue(**item)
            for item in _load_json_array(row["conflicts_json"])
        ]
        dependencies = [
            CoordinatorIssue(**item)
            for item in _load_json_array(row["dependencies_json"])
        ]
        pending_items = self._pending_items(conn, project_id)
        current_pending_item = next(
            (item for item in pending_items if item.isHighlighted and item.status == "open"),
            None,
        )
        return ProjectCoordinatorState(
            id=row["id"],
            projectId=row["project_id"],
            currentItem=current_item,
            currentPendingItem=current_pending_item,
            pendingItems=pending_items,
            expertStatuses=experts,
            conflicts=conflicts,
            dependencies=dependencies,
            updatedAt=row["updated_at"],
        )

    def _pending_items(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> list[PendingItem]:
        rows = conn.execute(
            """
            SELECT p.*, a.pending_item_id AS authorization_id
            FROM project_pending_items p
            LEFT JOIN skill_run_authorizations a
              ON a.pending_item_id = p.id AND a.project_id = p.project_id
            WHERE p.project_id = ?
            ORDER BY p.is_highlighted DESC, p.updated_at DESC
            """,
            (project_id,),
        ).fetchall()
        return [
            self._pending_item_from_row(row)
            for row in rows
        ]

    def _current_pending_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> PendingItem | None:
        row = conn.execute(
            """
            SELECT p.*, a.pending_item_id AS authorization_id
            FROM project_pending_items p
            LEFT JOIN skill_run_authorizations a
              ON a.pending_item_id = p.id AND a.project_id = p.project_id
            WHERE p.project_id = ?
              AND p.status = 'open'
              AND p.is_highlighted = 1
            ORDER BY p.updated_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return self._pending_item_from_row(row)

    def _pending_item_from_row(self, row: sqlite3.Row) -> PendingItem:
        authorization_id = row["authorization_id"]
        return PendingItem(
            id=row["id"],
            projectId=row["project_id"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"],
            reason=row["reason"],
            affectedExperts=[
                ExpertType(item) for item in _load_list(row["affected_experts_json"])
            ],
            options=_load_list(row["options_json"]),
            status=row["status"],
            kind=(
                "local_execution_authorization"
                if authorization_id
                else "general"
            ),
            actionType="resume_skill_run" if authorization_id else None,
            authorizationId=authorization_id,
            isHighlighted=bool(row["is_highlighted"]),
            criticalPath=bool(row["critical_path"]),
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    def _create_shared_context(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        initial_idea: str,
        now: str,
    ) -> str:
        context_id = _id("shared")
        goals = []
        if initial_idea.strip():
            goals.append(
                {
                    "id": _id("fact"),
                    "projectId": project_id,
                    "field": "initialIdea",
                    "key": "initialIdea",
                    "value": initial_idea.strip(),
                    "status": "proposed",
                    "sourceType": "user",
                    "sourceId": None,
                    "sourceExpertId": None,
                    "proposedBy": None,
                    "confirmed": False,
                    "confirmedBy": None,
                    "confirmedAt": None,
                    "supersededBy": None,
                    "affectsArtifactIds": [],
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
        conn.execute(
            """
            INSERT INTO project_shared_contexts (
              id, project_id, revision, goals_json, constraints_json,
              requirements_json, decisions_json, active_artifact_versions_json,
              updated_at
            ) VALUES (?, ?, 1, ?, '[]', '[]', '[]', '[]', ?)
            """,
            (context_id, project_id, _dump(goals) or "[]", now),
        )
        return context_id

    def _create_coordinator(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        now: str,
    ) -> str:
        coordinator_id = _id("coord")
        current_item = {
            "id": _id("item"),
            "title": "从当前专家开始推进",
            "description": "先确认当前任务所需的关键信息，再由项目协调器维护后续交接。",
            "targetExpertId": None,
            "targetArtifactId": None,
            "actionLabel": "进入当前专家",
            "severity": CoordinatorSeverity.INFO.value,
        }
        conn.execute(
            """
            INSERT INTO project_coordinator_states (
              id, project_id, current_item_json, conflicts_json, dependencies_json,
              updated_at
            ) VALUES (?, ?, ?, '[]', '[]', ?)
            """,
            (coordinator_id, project_id, _dump(current_item), now),
        )
        return coordinator_id

    def _create_project_expert(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        expert_type: ExpertType,
        now: str,
        conversation_id: str | None = None,
        is_initial_active: bool = False,
    ) -> ProjectExpert:
        expert_type = _canonical_expert_type(expert_type)
        definition_row = conn.execute(
            "SELECT id FROM expert_definitions WHERE expert_type = ?",
            (expert_type.value,),
        ).fetchone()
        if definition_row is None:
            raise ProjectValidationError("项目专家定义不存在。")
        if conversation_id is None:
            conversation_id = _id("conv")
            conn.execute(
                """
                INSERT INTO conversations (id, project_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, project_id, now, now),
            )
        expert_id = _id("pexp")
        private_memory_id = _id("pmem")
        status = ProjectExpertStatus.WORKING if is_initial_active else ProjectExpertStatus.IDLE
        current_task = _default_expert_task(expert_type)
        conn.execute(
            """
            INSERT INTO project_experts (
              id, project_id, expert_definition_id, expert_type, conversation_id,
              private_memory_id, status, workspace_status, current_task, added_at,
              removed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                expert_id,
                project_id,
                definition_row["id"],
                expert_type.value,
                conversation_id,
                private_memory_id,
                status.value,
                _workspace_status_for_project_status(status),
                current_task,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO expert_private_memories (
              id, project_id, project_expert_id, notes_json, updated_at
            ) VALUES (?, ?, ?, '[]', ?)
            """,
            (private_memory_id, project_id, expert_id, now),
        )
        conn.execute(
            """
            INSERT INTO expert_drafts (
              project_expert_id, project_id, content, updated_at
            ) VALUES (?, ?, '', NULL)
            """,
            (expert_id, project_id),
        )
        return ProjectExpert(
            id=expert_id,
            projectId=project_id,
            expertDefinitionId=definition_row["id"],
            expertType=expert_type,
            conversationId=conversation_id,
            privateMemoryId=private_memory_id,
            status=status,
            workspaceStatus=_workspace_status_for_project_status(status),
            currentTask=current_task,
            addedAt=now,
        )

    def _validated_hardware_snapshots(
        self,
        component_ids: list[str],
    ) -> tuple[list[dict[str, str]], dict[str, object] | None]:
        hardware_skills = HardwareSkillRepository(self.data_dir, self._db_path)
        try:
            components = [
                hardware_skills.get_active_component(component_id)
                for component_id in component_ids
            ]
            unsupported_controllers = [
                component
                for component in components
                if component.category == HardwareCategory.MCU
                and component.id not in SUPPORTED_CONTROLLER_COMPONENT_IDS
            ]
            if unsupported_controllers:
                names = "、".join(component.name for component in unsupported_controllers)
                raise ProjectValidationError(
                    f"旧项目板型不受支持：{names}。请显式迁移为 K10 或 XIAO ESP32S3 Sense。"
                )
            validation = hardware_skills.validate_component_ids(component_ids)
        except ProjectValidationError:
            raise
        except (HardwareSkillNotFoundError, HardwareSkillValidationError) as exc:
            raise ProjectValidationError(
                "所选硬件 Skill 不存在、未激活或未通过校验，请刷新硬件库后重新选择。"
            ) from exc
        snapshots = [
            {
                "id": component.id,
                "name": component.name,
                "category": component.category.value,
                "skillName": component.skillName,
                "skillRevision": component.skillRevision,
                "updatedAt": component.updatedAt,
            }
            for component in components
        ]
        if not components:
            return snapshots, None
        if validation.overall == ValidationSeverity.FAIL:
            failed_messages = [
                check.message
                for check in validation.checks
                if check.severity == ValidationSeverity.FAIL
            ]
            detail = "；".join(failed_messages[:4])
            raise ProjectValidationError(
                f"所选硬件组合未通过安全校验：{detail or validation.message}"
            )
        return snapshots, {
            "overall": validation.overall.value,
            "message": validation.message,
            "warnings": [
                {
                    "dimension": check.dimension,
                    "message": check.message,
                    "details": check.details,
                }
                for check in validation.checks
                if check.severity == ValidationSeverity.WARNING
            ][:12],
        }

    def _insert_creation_records(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        active_expert: ProjectExpert,
        idea: str,
        model: LLMModelSelection,
        route: RouterOutput,
        expert_selection_mode: str,
        idempotency_key: str | None,
        preferred_hardware: list[dict[str, str]],
        preferred_hardware_validation: dict[str, object] | None,
        now: str,
    ) -> None:
        turn_id = _id("turn")
        response_turn_id = _id("turn")
        client_turn_id = f"kickoff:{project_id}"
        expert_metadata = {
            "projectExpertId": active_expert.id,
            "expertType": active_expert.expertType.value,
            "conversationId": active_expert.conversationId,
        }
        user_message = ChatMessage(
            id=_id("msg"),
            role=ChatRole.USER,
            content=idea,
            metadata={
                **expert_metadata,
                "source": "project_creation",
                "initialExpert": active_expert.expertType.value,
                "turnId": turn_id,
                "clientTurnId": client_turn_id,
                "requestTurnId": turn_id,
            },
            status=ChatMessageStatus.COMPLETED,
            createdAt=now,
            updatedAt=now,
        )
        self._insert_message(
            conn,
            active_expert.conversationId,
            project_id,
            user_message,
        )
        assistant_message = ChatMessage(
            id=_id("msg"),
            role=ChatRole.ASSISTANT,
            content="",
            metadata={
                **expert_metadata,
                "source": "project_creation_runtime",
                "initialExpert": active_expert.expertType.value,
                "routerConfidence": route.confidence,
                "requiresClarification": route.requiresClarification,
                "turnId": response_turn_id,
                "parentTurnId": turn_id,
                "clientTurnId": client_turn_id,
                "requestTurnId": turn_id,
                "responseTurnId": response_turn_id,
            },
            status=ChatMessageStatus.READY,
            createdAt=now,
            updatedAt=now,
            model=model,
        )
        self._insert_message(
            conn,
            active_expert.conversationId,
            project_id,
            assistant_message,
        )
        conn.execute(
            """
            INSERT INTO conversation_turns (
              id, project_id, conversation_id, client_turn_id, parent_turn_id,
              user_message_id, assistant_message_id, request_json, status,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, 'READY', ?, ?)
            """,
            (
                turn_id,
                project_id,
                active_expert.conversationId,
                client_turn_id,
                user_message.id,
                assistant_message.id,
                _dump(
                    {
                        "kind": "project_kickoff",
                        "projectExpertId": active_expert.id,
                        "expertType": active_expert.expertType.value,
                    }
                ),
                now,
                now,
            ),
        )
        route_payload = route.model_dump(mode="json")
        creation_metadata = {
            "routerResult": route_payload,
            "expertSelectionMode": expert_selection_mode,
            "initialExpert": active_expert.expertType.value,
        }
        preferred_hardware_value: dict[str, object] = {
            "policy": "prefer_selected_and_fill_gaps",
            "components": preferred_hardware,
        }
        if preferred_hardware_validation is not None:
            preferred_hardware_value["validation"] = preferred_hardware_validation
        self._insert_shared_fact_row(
            conn,
            project_id=project_id,
            field="initial_idea",
            key="initial_idea",
            value=idea,
            source_type="user",
            source_expert_id=active_expert.id,
            proposed_by=active_expert.expertType,
            now=now,
        )
        self._insert_shared_fact_row(
            conn,
            project_id=project_id,
            field="preferred_hardware",
            key="preferred_hardware",
            value=preferred_hardware_value,
            source_type="user",
            source_expert_id=None,
            proposed_by=None,
            status=SharedFactStatus.CONFIRMED,
            confirmed_by="user",
            confirmed_at=now,
            now=now,
        )
        self._insert_shared_fact_row(
            conn,
            project_id=project_id,
            field="entry_router_result",
            key="entry_router_result",
            value=creation_metadata,
            source_type="system",
            source_expert_id=None,
            proposed_by=None,
            now=now,
        )
        if idempotency_key:
            self._insert_shared_fact_row(
                conn,
                project_id=project_id,
                field="creation_idempotency_key",
                key=f"creation_idempotency_key:{idempotency_key}",
                value=idempotency_key,
                source_type="system",
                source_expert_id=None,
                proposed_by=None,
                now=now,
            )
        pending_id = _id("pending")
        conn.execute(
            """
            INSERT INTO project_pending_items (
              id, project_id, title, description, priority, reason,
              affected_experts_json, options_json, status, is_highlighted,
              critical_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, 1, 1, ?, ?)
            """,
            (
                pending_id,
                project_id,
                "继续澄清并确认方案",
                "请在中央对话中补充关键需求，掌问会据此给出一套推荐实现方案和硬件方案。",
                PendingItemPriority.CONFIRMATION.value,
                route.reason,
                json.dumps([active_expert.expertType.value], ensure_ascii=False),
                PendingItemStatus.OPEN.value,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO project_tasks (
              id, project_id, title, description, owner_expert_type, status,
              dependency_task_ids_json, artifact_ids_json,
              current_pending_item_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?, ?)
            """,
            (
                _id("task"),
                project_id,
                "处理项目初始创意",
                "读取用户创意，结合最小上下文生成第一轮专家响应。",
                active_expert.expertType.value,
                DomainTaskStatus.RUNNING.value,
                pending_id,
                now,
                now,
            ),
        )

    def _insert_shared_fact_row(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        field: str,
        key: str,
        value: object,
        source_type: str,
        source_expert_id: str | None,
        proposed_by: ExpertType | None,
        now: str,
        status: SharedFactStatus = SharedFactStatus.PROPOSED,
        confirmed_by: str | None = None,
        confirmed_at: str | None = None,
        fact_id: str | None = None,
    ) -> str:
        inserted_fact_id = fact_id or _id("fact")
        conn.execute(
            """
            INSERT INTO project_shared_facts (
              id, project_id, field, key, value_json, status, source_type,
              source_id, source_expert_id, proposed_by_expert_type,
              confirmed_by, confirmed_at, superseded_by,
              affects_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, '[]', ?, ?)
            """,
            (
                inserted_fact_id,
                project_id,
                field,
                key,
                json.dumps(value, ensure_ascii=False),
                status.value,
                source_type,
                source_expert_id,
                proposed_by.value if proposed_by else None,
                confirmed_by,
                confirmed_at,
                now,
                now,
            ),
        )
        return inserted_fact_id

    def _sync_coordinator(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        coordinator_id: str,
        active_expert_id: str | None,
        now: str,
    ) -> None:
        current_item = {
            "id": _id("item"),
            "title": "继续推进当前专家任务",
            "description": "围绕当前专家的任务补齐必要输入，后续交接由项目协调器维护。",
            "targetExpertId": active_expert_id,
            "targetArtifactId": None,
            "actionLabel": "进入当前专家",
            "severity": CoordinatorSeverity.INFO.value,
        }
        conn.execute(
            """
            UPDATE project_coordinator_states
            SET current_item_json = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (_dump(current_item), now, coordinator_id, project_id),
        )

    def _ensure_database(self) -> None:
        with self._connect(raw=True) as conn:
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
            except sqlite3.DatabaseError as exc:
                self._quarantine_corrupt()
                raise ProjectDatabaseCorruptError("项目数据库损坏，已隔离。") from exc
            if result and result[0] != "ok":
                self._quarantine_corrupt()
                raise ProjectDatabaseCorruptError("项目数据库损坏，已隔离。")
            current_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            backup_path: Path | None = None
            if 0 < current_version < CURRENT_SCHEMA_VERSION:
                backup_path = self._create_pre_migration_backup(conn, current_version)
            migrate(conn)
            if backup_path is not None:
                conn.execute(
                    """
                    INSERT INTO schema_migration_audit (
                      id, from_version, to_version, status, backup_path, applied_at
                    ) VALUES (?, ?, ?, 'applied', ?, ?)
                    """,
                    (
                        f"migration_session_{uuid.uuid4().hex}",
                        current_version,
                        CURRENT_SCHEMA_VERSION,
                        str(backup_path),
                        _now(),
                    ),
                )
                conn.commit()
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

    def _create_pre_migration_backup(
        self,
        conn: sqlite3.Connection,
        current_version: int,
    ) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self._backup_dir / (
            f"pre-migration-v{current_version}-to-v{CURRENT_SCHEMA_VERSION}-{stamp}.sqlite3"
        )
        with sqlite3.connect(backup_path) as backup_conn:
            conn.backup(backup_conn)
        return backup_path

    def _connect(self, *, raw: bool = False) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        if not raw:
            conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _quarantine_corrupt(self) -> None:
        if not self._db_path.exists():
            return
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        shutil.move(str(self._db_path), self._backup_dir / f"corrupt-{stamp}.sqlite3")

    def _get_meta(self, conn: sqlite3.Connection, key: str) -> str | None:
        if key == "activeProjectId" and self._owner_subject is not None:
            row = conn.execute(
                """
                SELECT current_project_id AS value
                FROM account_workspace_state
                WHERE owner_subject = ?
                """,
                (self._owner_subject,),
            ).fetchone()
            if row is None or row["value"] in {None, ""}:
                return None
            project = conn.execute(
                "SELECT 1 FROM projects WHERE id = ? AND owner_subject = ?",
                (str(row["value"]), self._owner_subject),
            ).fetchone()
            return str(row["value"]) if project is not None else None
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None or row["value"] == "":
            return None
        return str(row["value"])

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        if key == "activeProjectId" and self._owner_subject is not None:
            conn.execute(
                """
                INSERT INTO account_workspace_state (
                  owner_subject, current_project_id, legacy_claim_decision_at, updated_at
                ) VALUES (?, ?, NULL, ?)
                ON CONFLICT(owner_subject) DO UPDATE SET
                  current_project_id = excluded.current_project_id,
                  updated_at = excluded.updated_at
                """,
                (self._owner_subject, value or None, _now()),
            )
            return
        conn.execute(
            """
            INSERT INTO meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def _project_row(self, conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM projects
            WHERE id = ? AND (? IS NULL OR owner_subject = ?)
            """,
            (project_id, self._owner_subject, self._owner_subject),
        ).fetchone()
        if row is None:
            raise ProjectNotFoundError("项目不存在。")
        return row

    def _ensure_not_archived(self, conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = self._project_row(conn, project_id)
        if row["archived_at"] is not None:
            raise ProjectArchivedError("项目已归档，不能继续编辑。")
        return row

    def _project(
        self,
        row: sqlite3.Row,
        conversation_id: str,
        *,
        experts: list[ProjectExpert] | None = None,
        shared_context: ProjectSharedContext | None = None,
        coordinator: ProjectCoordinatorState | None = None,
    ) -> Project:
        active_expert_ids = [expert.id for expert in (experts or [])]
        return Project(
            id=row["id"],
            name=row["name"],
            stage=ProjectStage(row["stage"]),
            profile=ProjectProfile(initialIdea=row["initial_idea"]),
            conversationId=conversation_id,
            activeExpertIds=active_expert_ids,
            activeExpertId=row["active_expert_id"],
            sharedContextId=shared_context.id if shared_context else None,
            coordinatorStateId=coordinator.id if coordinator else None,
            selectedModel=str(row["selected_model"]),
            archivedAt=row["archived_at"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            lastOpenedAt=row["last_opened_at"],
            schemaVersion=ProjectPersistenceVersion.V31,
        )

    def _summary(self, row: sqlite3.Row) -> ProjectSummary:
        active_expert_ids = [
            item
            for item in (row["active_expert_ids"] or "").split(",")
            if item
        ]
        return ProjectSummary(
            id=row["id"],
            name=row["name"],
            stage=ProjectStage(row["stage"]),
            activeExpertIds=active_expert_ids,
            selectedModel=str(row["selected_model"]),
            messageCount=int(row["message_count"]),
            draftUpdatedAt=row["draft_updated_at"],
            archivedAt=row["archived_at"],
            updatedAt=row["updated_at"],
            lastOpenedAt=row["last_opened_at"],
        )

    def _message(self, row: sqlite3.Row) -> ChatMessage:
        error_data = _load(row["error_json"])
        usage_data = _load(row["usage_json"])
        return ChatMessage(
            id=row["id"],
            role=ChatRole(row["role"]),
            content=row["content"],
            structuredPayload=_load(row["structured_payload_json"]),
            metadata=_load(row["metadata_json"]),
            reasoningContent=row["reasoning_content"],
            status=ChatMessageStatus(row["status"]),
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            model=str(row["model"]) if row["model"] else None,
            error=LLMError(**error_data) if error_data else None,
            usage=TokenUsage(**usage_data) if usage_data else None,
        )

    def _insert_message(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        project_id: str,
        message: ChatMessage,
    ) -> None:
        conn.execute(
            """
            INSERT INTO messages (
              id, conversation_id, project_id, role, content, reasoning_content,
              status, model, error_json, usage_json, structured_payload_json, metadata_json,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                conversation_id,
                project_id,
                message.role.value,
                message.content,
                message.reasoningContent,
                message.status.value,
                str(message.model) if message.model else None,
                _dump(message.error),
                _dump(message.usage),
                _dump(message.structuredPayload),
                _dump(message.metadata),
                message.createdAt,
                message.updatedAt,
            ),
        )


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ProjectValidationError("项目名称不能为空。")
    if len(cleaned) > 80:
        raise ProjectValidationError("项目名称不能超过 80 个字符。")
    return cleaned


def _clean_idea(idea: str) -> str:
    cleaned = " ".join(idea.strip().split())
    if not cleaned:
        raise ProjectValidationError("项目创意不能为空。")
    if len(cleaned) > 4000:
        raise ProjectValidationError("项目创意不能超过 4000 个字符。")
    return cleaned


def _initial_assistant_message_content(expert_type: ExpertType, route: RouterOutput) -> str:
    intros = {
        ExpertType.PROBLEM_GUIDE: (
            "我会像产品经理一样把这个想法整理成可执行方案。只在会改变方向时问一个具体问题，"
            "信息足够后就直接整理推荐方案，并在需要时自动交给后续工程师。"
        ),
        ExpertType.SMART_ENGINEER: (
            "我会从实现方案开始推进。接下来会确认核心功能、硬件模块、"
            "供电与通信方式，以及第一版可验证的软件和硬件路径。"
        ),
        ExpertType.STRUCTURE_ENGINEER: (
            "我会先处理结构侧问题。接下来会确认尺寸、安装方式、外壳或机构约束，"
            "以及需要承载或避让的电子模块。"
        ),
    }
    intro = intros.get(expert_type, intros[ExpertType.PROBLEM_GUIDE])
    if route.requiresClarification:
        return (
            f"{intro}\n\n当前想法还比较宽泛，建议先由问题引导师帮助你进一步梳理。"
        )
    reason = route.reason.strip()
    if reason:
        return f"{intro}\n\n当前判断：{reason}"
    return intro


def _router_output_from_entry(route: EntryRouterOutput) -> RouterOutput:
    return RouterOutput(
        intent=route.intent,
        projectName=route.projectName,
        initialExpert=route.initialExpert,
        recommendedExperts=route.recommendedExperts,
        confidence=route.confidence,
        reason=route.reason,
        requiresClarification=route.requiresClarification,
    )


def _router_output_from_any(
    route: RouterOutput | EntryRouterOutput | None,
) -> RouterOutput | None:
    if route is None:
        return None
    if isinstance(route, RouterOutput):
        recommended = _normalize_creation_experts(route.recommendedExperts)
        initial = _canonical_expert_type(route.initialExpert)
        if initial not in recommended:
            recommended.insert(0, initial)
        return route.model_copy(
            update={
                "initialExpert": initial,
                "recommendedExperts": _dedupe_experts(recommended),
            }
        )
    return _router_output_from_entry(route)


def _normalize_creation_experts(expert_types: list[ExpertType]) -> list[ExpertType]:
    canonical: list[ExpertType] = []
    for expert_type in expert_types:
        mapped = _canonical_expert_type(expert_type)
        if mapped not in {
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        }:
            continue
        if mapped not in canonical:
            canonical.append(mapped)
    return canonical


def _requires_smart_engineer(idea: str, selected_hardware_ids: list[str]) -> bool:
    if selected_hardware_ids:
        return True
    normalized = idea.casefold()
    return any(
        keyword in normalized
        for keyword in (
            "硬件",
            "代码",
            "设备",
            "传感器",
            "水泵",
            "浇花",
            "micropython",
            "esp32",
            "k10",
            "gpio",
            "串口",
        )
    )


def _order_experts_with_initial(
    expert_types: list[ExpertType],
    initial_expert: ExpertType,
) -> list[ExpertType]:
    return [initial_expert, *[expert for expert in expert_types if expert != initial_expert]]


def _dedupe_experts(expert_types: list[ExpertType]) -> list[ExpertType]:
    deduped: list[ExpertType] = []
    for expert_type in expert_types:
        if expert_type not in deduped:
            deduped.append(expert_type)
    return deduped


def _default_expert_task(expert_type: ExpertType) -> str:
    expert_type = _canonical_expert_type(expert_type)
    return {
        ExpertType.PROBLEM_GUIDE: "梳理问题、需求、项目方案和教学目标",
        ExpertType.SMART_ENGINEER: "等待确认技术方案、硬件方案和 IO Map",
        ExpertType.STRUCTURE_ENGINEER: "等待硬件尺寸、安装约束和结构目标",
    }[expert_type]


def _workspace_status_for_project_status(status: ProjectExpertStatus) -> str:
    return {
        ProjectExpertStatus.WAITING_USER: "awaiting_user",
        ProjectExpertStatus.WORKING: "in_progress",
        ProjectExpertStatus.BLOCKED: "waiting_dependency",
        ProjectExpertStatus.COMPLETED: "completed",
    }.get(status, "not_started")


def _canonical_expert_type(expert_type: ExpertType) -> ExpertType:
    mapping = {
        ExpertType.QUESTION_GUIDE: ExpertType.PROBLEM_GUIDE,
        ExpertType.INTELLIGENT_ENGINEER: ExpertType.SMART_ENGINEER,
        ExpertType.IDEATOR: ExpertType.PROBLEM_GUIDE,
        ExpertType.EDUCATOR: ExpertType.PROBLEM_GUIDE,
        ExpertType.OPEN_HARDWARE_DESIGNER: ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_DESIGNER: ExpertType.STRUCTURE_ENGINEER,
        ExpertType.THREE_D_STRUCTURE_DESIGNER: ExpertType.STRUCTURE_ENGINEER,
    }
    return mapping.get(expert_type, expert_type)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def _load(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return json.loads(value)


def _payload_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    questions = payload.get("questions")
    if isinstance(questions, list):
        return [
            question
            for question in questions
            if isinstance(question, dict) and question.get("id")
        ]
    question = payload.get("question")
    if isinstance(question, dict) and question.get("id"):
        return [question]
    return []


def _load_list(value: str | None) -> list[str]:
    if not value:
        return []
    loaded = json.loads(value)
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _load_json_array(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    loaded = json.loads(value)
    return [item for item in loaded if isinstance(item, dict)] if isinstance(loaded, list) else []
