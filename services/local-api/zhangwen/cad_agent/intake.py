"""Project-scoped intake for deterministic structure-engineer CAD drafts."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Literal

from zhangwen.cad_agent.models import (
    CadComponentDraft,
    CadDraft,
    CadOutputRole,
    CadRunStatus,
    CadTemplateKind,
)
from zhangwen.cad_agent.profile_repository import (
    MechanicalProfileRepository,
    MechanicalProfileSnapshot,
)
from zhangwen.cad_agent.template_catalog import production_parameter_spec
from zhangwen.artifacts.models import ArtifactStatus, DomainArtifactStatus
from zhangwen.coordinator import ProjectCoordinatorService


CAD_COMPONENT_MODE_QUESTION_ID = "cad_component_mode"
CAD_DIMENSIONS_QUESTION_ID = "cad_dimensions_lwh_mm"
CAD_PROFILE_QUESTION_ID = "cad_mechanical_profiles"
CAD_TARGET_QUESTION_ID = "cad_build_target"
CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID = "cad_component_mount_profile"
CAD_FREEFORM_DESCRIPTION_QUESTION_ID = "cad_freeform_description"
CAD_LOOSE_STORAGE_OPTION_ID = "cad_component_mode_loose_storage"
CAD_FIXED_INSTALL_OPTION_ID = "cad_component_mode_fixed_install"
CAD_BOX_WITH_LID_OPTION_ID = "cad_build_target_box_with_lid"
CAD_COMPONENT_MOUNT_OPTION_ID = "cad_build_target_component_mount"
CAD_FREEFORM_STRUCTURE_OPTION_ID = "cad_build_target_freeform_structure"
CAD_K10_PHOTO_ALBUM_OPTION_ID = "cad_build_target_k10_photo_album"
CAD_PROFILE_OPTION_PREFIX = "cad_profile_option_"
CAD_VIRTUAL_HARDWARE_PREFIX = "cad_profile_"
CAD_TARGET_FACT_KEY = "cad.target"
CAD_COMPONENT_MODE_FACT_KEY = "cad.component_mode"
CAD_DIMENSIONS_FACT_KEY = "cad.dimensions_lwh_mm"
CAD_PROFILE_SELECTIONS_FACT_KEY = "cad.mechanical_profile.selections"
CAD_FREEFORM_DESCRIPTION_FACT_KEY = "cad.freeform_description"

_CAD_INTAKE_FACT_KEYS = (
    CAD_TARGET_FACT_KEY,
    CAD_COMPONENT_MODE_FACT_KEY,
    CAD_DIMENSIONS_FACT_KEY,
    CAD_PROFILE_SELECTIONS_FACT_KEY,
    CAD_FREEFORM_DESCRIPTION_FACT_KEY,
)
_CAD_QUESTION_IDS = (
    CAD_TARGET_QUESTION_ID,
    CAD_COMPONENT_MODE_QUESTION_ID,
    CAD_DIMENSIONS_QUESTION_ID,
    CAD_PROFILE_QUESTION_ID,
    CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID,
    CAD_FREEFORM_DESCRIPTION_QUESTION_ID,
)
_DEFAULT_BOX_DIMENSIONS = {"width": 80.0, "depth": 50.0, "height": 28.0}

CadBuildTarget = Literal[
    "box_with_lid",
    "component_mount",
    "freeform_structure",
    "unihiker_k10_photo_album",
]

_DIMENSION_PATTERN = re.compile(
    r"^\s*(?P<length>\d+(?:\.\d+)?)\s*(?:x|×|\*)\s*"
    r"(?P<width>\d+(?:\.\d+)?)\s*(?:x|×|\*)\s*"
    r"(?P<height>\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*$",
    re.IGNORECASE,
)
_CAD_INTENT_TERMS = (
    "cad",
    "3d",
    "三维模型",
    "三维结构",
    "建模",
    "外壳",
    "保护壳",
    "壳子",
    "机壳",
    "盒体",
    "盒子",
    "储物盒",
    "收纳盒",
    "容器",
    "保护盒",
    "内腔尺寸",
    "3d打印",
    "打印外壳",
)
_CAD_REVISION_TERMS = (
    "修改",
    "改成",
    "改为",
    "调整",
    "重做",
    "重新做",
    "另做",
    "再做一个",
    "新建一个",
    "新做",
    "新的",
    "另一个",
    "重新生成",
    "换成",
)
_CAD_CONTINUATION_TERMS = (
    "继续生成",
    "开始生成",
    "可以生成",
    "直接生成",
    "进行生成",
    "确认生成",
    "按这个生成",
    "就这样生成",
    "执行生成",
    "继续建模",
    "开始建模",
)
_INLINE_DIMENSION_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:x|×|\*)\s*"
    r"\d+(?:\.\d+)?\s*(?:x|×|\*)\s*"
    r"\d+(?:\.\d+)?",
    re.IGNORECASE,
)
_CAD_FILE_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:step|stl)(?![a-z0-9])",
    re.IGNORECASE,
)
_CAD_MODEL_ACTION_PATTERN = re.compile(
    r"(?:生成|创建|制作|设计|做|画|输出).{0,8}(?:模型|外壳|保护壳|盒体|盒子|保护盒)"
    r"|(?:模型|外壳|保护壳|盒体|盒子|保护盒).{0,8}(?:生成|建模|设计|制作)",
    re.IGNORECASE,
)
_COMPONENT_MOUNT_ACTION_PATTERN = re.compile(
    r"(?:生成|创建|制作|设计|做|画|输出).{0,12}(?:安装座|固定座|安装底座|托架|支架|压框)"
    r"|(?:安装座|固定座|安装底座|托架|支架|压框).{0,12}(?:生成|建模|设计|制作|创建|做)",
    re.IGNORECASE,
)
_FREEFORM_ACTION_PATTERN = re.compile(
    r"(?:生成|创建|制作|设计|做|画|输出).{0,16}(?:零件|结构件|安装板|连接板|支撑板|板件|圆角板|打印件|自定义结构)"
    r"|(?:零件|结构件|安装板|连接板|支撑板|板件|圆角板|打印件|自定义结构).{0,16}(?:生成|建模|设计|制作|创建|做)",
    re.IGNORECASE,
)
_BOX_TARGET_TERMS = (
    "外壳",
    "保护壳",
    "壳子",
    "机壳",
    "盒体",
    "盒子",
    "储物盒",
    "收纳盒",
    "容器",
    "保护盒",
    "内腔尺寸",
    "打印外壳",
)
_COMPONENT_MOUNT_TARGET_TERMS = (
    "安装座",
    "固定座",
    "固定底座",
    "安装底座",
    "托架",
    "器件支架",
    "传感器支架",
    "主控板支架",
    "压框",
)
_FREEFORM_TARGET_TERMS = (
    "自定义结构",
    "自由结构",
    "自然语言生成",
    "圆角零件",
    "安装板",
    "连接板",
    "支撑板",
    "圆角板",
    "板件",
    "打印件",
    "结构件",
    "零件",
)
_FREEFORM_NO_HARDWARE_TERMS = (
    "不使用任何传感器",
    "不使用传感器",
    "不使用任何器件",
    "不使用电子器件",
    "不使用器件",
    "不需要器件",
    "无需器件",
)
_K10_PHOTO_ALBUM_TERMS = (
    "行空板k10电子相册",
    "行空板 k10电子相册",
    "行空板k10 电子相册",
    "行空板 k10 电子相册",
    "k10电子相册",
    "k10 电子相册",
    "k10相册支架",
    "k10 相册支架",
)


@dataclass(frozen=True)
class CadProfileOption:
    option_id: str
    hardware_id: str
    profile_id: str
    revision: str
    content_sha256: str
    label: str
    description: str


@dataclass(frozen=True)
class ConfirmedCadProfileSelection:
    hardware_id: str
    profile_id: str
    revision: str
    content_sha256: str


@dataclass(frozen=True)
class CadIntakeState:
    target: CadBuildTarget | None
    mode: Literal["loose_storage", "fixed_install"] | None
    dimensions: dict[str, float] | None
    profiles: tuple[ConfirmedCadProfileSelection, ...]
    freeform_description: str | None = None


class CadProfileIntake:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._profiles = MechanicalProfileRepository(self._db_path)

    def list_options(self) -> tuple[CadProfileOption, ...]:
        all_options = self._all_profile_options()
        current_identities = {
            (
                snapshot.profile_id,
                snapshot.revision,
                snapshot.content_sha256,
            )
            for snapshot in (
                self._profiles.get(profile_id)
                for profile_id in sorted({option.profile_id for option in all_options})
            )
        }
        return tuple(
            option
            for option in all_options
            if (option.profile_id, option.revision, option.content_sha256)
            in current_identities
        )[:32]

    def initial_question_payload(
        self,
        state: CadIntakeState | None = None,
    ) -> dict[str, object]:
        current = state or CadIntakeState(
            target="box_with_lid",
            mode=None,
            dimensions=None,
            profiles=(),
        )
        questions: list[dict[str, object]] = []
        if current.mode is None:
            questions.append({
                "id": CAD_COMPONENT_MODE_QUESTION_ID,
                "text": "盒内物品需要固定安装或按接口开孔吗？",
                "mode": "single",
                "options": [
                    {
                        "id": CAD_LOOSE_STORAGE_OPTION_ID,
                        "label": "仅松散存放，不做固定和接口开孔",
                        "value": "loose_storage",
                        "recommended": True,
                    },
                    {
                        "id": CAD_FIXED_INSTALL_OPTION_ID,
                        "label": "需要固定安装或接口开孔",
                        "value": "fixed_install",
                    },
                ],
                "allowCustomInput": False,
                "required": True,
            })
        if current.dimensions is None:
            questions.append({
                "id": CAD_DIMENSIONS_QUESTION_ID,
                "text": "请确认盒体内腔长 × 宽 × 高，单位为毫米。",
                "mode": "text",
                "options": [],
                "allowCustomInput": True,
                "required": True,
            })
        if not questions:
            raise ValueError("CAD intake is already complete")
        return _clarification_payload(
            f"还需确认 {len(questions)} 项建模输入。",
            20 if len(questions) == 2 else 45,
            questions,
        )

    def target_question_payload(self) -> dict[str, object]:
        question = {
            "id": CAD_TARGET_QUESTION_ID,
            "text": "这次希望创建哪一种结构？",
            "mode": "single",
            "options": [
                {
                    "id": CAD_COMPONENT_MOUNT_OPTION_ID,
                    "label": "按电子器件创建安装底座与压框",
                    "value": "component_mount",
                    "recommended": True,
                },
                {
                    "id": CAD_BOX_WITH_LID_OPTION_ID,
                    "label": "创建盒体与上盖",
                    "value": "box_with_lid",
                },
                {
                    "id": CAD_FREEFORM_STRUCTURE_OPTION_ID,
                    "label": "不使用电子器件，按自然语言创建零件",
                    "value": "freeform_structure",
                },
                {
                    "id": CAD_K10_PHOTO_ALBUM_OPTION_ID,
                    "label": "使用行空板 K10 电子相册固定模板",
                    "value": "unihiker_k10_photo_album",
                },
            ],
            "allowCustomInput": False,
            "required": True,
        }
        return _clarification_payload("请先确认本次建模目标。", 10, [question])

    def freeform_description_question_payload(self) -> dict[str, object]:
        return _clarification_payload(
            "请描述零件的实体、尺寸、位置、圆角以及需要切除的孔或槽。",
            30,
            [
                {
                    "id": CAD_FREEFORM_DESCRIPTION_QUESTION_ID,
                    "text": "请用毫米描述要生成的三维结构；不确定的关键尺寸请明确说明。",
                    "mode": "text",
                    "options": [],
                    "allowCustomInput": True,
                    "required": True,
                }
            ],
        )

    def profile_question_payload(self) -> dict[str, object]:
        options = [
            {
                "id": option.option_id,
                "label": option.label,
                "value": option.option_id,
                "description": option.description,
            }
            for option in self.list_options()
        ]
        question = {
            "id": CAD_PROFILE_QUESTION_ID,
            "text": "请选择需要固定安装或按接口开孔的精确机械档案（可多选）。",
            "mode": "multiple",
            "options": options,
            "allowCustomInput": False,
            "required": True,
        }
        return _clarification_payload("请选择已确认的机械档案后继续建模。", 70, [question])

    def component_mount_profile_question_payload(self) -> dict[str, object]:
        options = [
            {
                "id": option.option_id,
                "label": option.label,
                "value": option.option_id,
                "description": option.description,
            }
            for option in self.list_options()
        ]
        question = {
            "id": CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID,
            "text": "请选择要作为安装结构尺寸基准的一个电子器件机械档案。",
            "mode": "single",
            "options": options,
            "allowCustomInput": False,
            "required": True,
        }
        return _clarification_payload(
            "器件安装结构必须绑定一个已确认的机械档案。",
            55,
            [question],
        )

    def record_confirmed_answers(
        self,
        *,
        project_id: str,
        source_message_id: str | None,
        user_message_id: str,
        answers: Iterable[object],
        connection: sqlite3.Connection | None = None,
    ) -> bool:
        if not source_message_id:
            return False
        source_payload = self._source_payload(
            project_id,
            source_message_id,
            connection=connection,
        )
        if not is_cad_clarification_payload(source_payload):
            return False
        answer_items = tuple(answers)
        question_map = {
            str(question.get("id")): question
            for question in _payload_questions(source_payload)
        }
        # Direct service callers used by deterministic CAD tests may provide
        # the old combined mode+dimension answer. The chat repository still
        # validates that users only answer questions actually shown to them.
        if (
            CAD_COMPONENT_MODE_QUESTION_ID in question_map
            and any(
                str(_answer_value(answer, "question_id", "questionId", ""))
                == CAD_DIMENSIONS_QUESTION_ID
                for answer in answer_items
            )
        ):
            question_map[CAD_DIMENSIONS_QUESTION_ID] = {
                "id": CAD_DIMENSIONS_QUESTION_ID
            }
        requires_profile_options = bool(
            {CAD_PROFILE_QUESTION_ID, CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID}
            & set(question_map)
        )
        option_map = (
            {
                option.option_id: option
                for option in self._all_profile_options(connection=connection)
            }
            if requires_profile_options
            else {}
        )
        answer_priority = {
            CAD_TARGET_QUESTION_ID: 0,
            CAD_COMPONENT_MODE_QUESTION_ID: 1,
            CAD_DIMENSIONS_QUESTION_ID: 2,
            CAD_PROFILE_QUESTION_ID: 3,
            CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID: 3,
            CAD_FREEFORM_DESCRIPTION_QUESTION_ID: 1,
        }
        ordered_answers = sorted(
            answer_items,
            key=lambda item: answer_priority.get(
                str(_answer_value(item, "question_id", "questionId", "")),
                99,
            ),
        )
        handled = False
        fact_updates: dict[str, tuple[str, object]] = {}
        for answer in ordered_answers:
            question_id = str(_answer_value(answer, "question_id", "questionId", ""))
            if question_id not in question_map:
                continue
            selected_option_ids = tuple(
                str(value)
                for value in (_answer_value(
                    answer,
                    "selected_option_ids",
                    "selectedOptionIds",
                    (),
                ) or ())
            )
            text_input = _answer_value(answer, "text_input", "textInput", None)
            if question_id == CAD_TARGET_QUESTION_ID:
                handled = True
                if selected_option_ids == (CAD_BOX_WITH_LID_OPTION_ID,):
                    target: object = "box_with_lid"
                elif selected_option_ids == (CAD_COMPONENT_MOUNT_OPTION_ID,):
                    target = "component_mount"
                elif selected_option_ids == (CAD_FREEFORM_STRUCTURE_OPTION_ID,):
                    target = "freeform_structure"
                elif selected_option_ids == (CAD_K10_PHOTO_ALBUM_OPTION_ID,):
                    target = "unihiker_k10_photo_album"
                else:
                    raise ValueError("CAD_TARGET_INVALID")
                fact_updates[CAD_TARGET_FACT_KEY] = ("cad_build_target", target)
                fact_updates[CAD_COMPONENT_MODE_FACT_KEY] = (
                    "cad_component_mode",
                    {"status": "pending"},
                )
                fact_updates[CAD_DIMENSIONS_FACT_KEY] = (
                    "cad_dimensions_lwh_mm",
                    {"status": "pending"},
                )
                fact_updates[CAD_PROFILE_SELECTIONS_FACT_KEY] = (
                    "cad_mechanical_profile_selection",
                    {"schemaVersion": 1, "items": []},
                )
                fact_updates[CAD_FREEFORM_DESCRIPTION_FACT_KEY] = (
                    "cad_freeform_description",
                    (
                        {"status": "pending"}
                        if target == "freeform_structure"
                        else {"status": "not_applicable"}
                    ),
                )
                if target in {"freeform_structure", "unihiker_k10_photo_album"}:
                    fact_updates[CAD_COMPONENT_MODE_FACT_KEY] = (
                        "cad_component_mode",
                        {"status": "not_applicable"},
                    )
                    fact_updates[CAD_DIMENSIONS_FACT_KEY] = (
                        "cad_dimensions_lwh_mm",
                        {"status": "not_applicable"},
                    )
            elif question_id == CAD_COMPONENT_MODE_QUESTION_ID:
                handled = True
                if selected_option_ids == (CAD_LOOSE_STORAGE_OPTION_ID,):
                    value: object = "loose_storage"
                elif selected_option_ids == (CAD_FIXED_INSTALL_OPTION_ID,):
                    value = "fixed_install"
                else:
                    raise ValueError("CAD_COMPONENT_MODE_INVALID")
                fact_updates[CAD_COMPONENT_MODE_FACT_KEY] = (
                    "cad_component_mode",
                    value,
                )
                fact_updates[CAD_TARGET_FACT_KEY] = (
                    "cad_build_target",
                    "box_with_lid",
                )
                fact_updates[CAD_PROFILE_SELECTIONS_FACT_KEY] = (
                    "cad_mechanical_profile_selection",
                    {"schemaVersion": 1, "items": []},
                )
                fact_updates[CAD_FREEFORM_DESCRIPTION_FACT_KEY] = (
                    "cad_freeform_description",
                    {"status": "not_applicable"},
                )
                fact_updates[CAD_DIMENSIONS_FACT_KEY] = (
                    "cad_dimensions_lwh_mm",
                    dict(_DEFAULT_BOX_DIMENSIONS),
                )
            elif question_id == CAD_DIMENSIONS_QUESTION_ID:
                handled = True
                dimensions = parse_cad_dimensions(str(text_input or ""))
                fact_updates[CAD_DIMENSIONS_FACT_KEY] = (
                    "cad_dimensions_lwh_mm",
                    dimensions,
                )
            elif question_id == CAD_FREEFORM_DESCRIPTION_QUESTION_ID:
                handled = True
                description = str(text_input or "").strip()
                if not description or len(description) > 4000:
                    raise ValueError("CAD_FREEFORM_DESCRIPTION_INVALID")
                fact_updates[CAD_TARGET_FACT_KEY] = (
                    "cad_build_target",
                    "freeform_structure",
                )
                fact_updates[CAD_FREEFORM_DESCRIPTION_FACT_KEY] = (
                    "cad_freeform_description",
                    description,
                )
            elif question_id in {
                CAD_PROFILE_QUESTION_ID,
                CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID,
            }:
                handled = True
                if not selected_option_ids:
                    raise ValueError("CAD_PROFILE_SELECTION_REQUIRED")
                if (
                    question_id == CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID
                    and len(selected_option_ids) != 1
                ):
                    raise ValueError("CAD_COMPONENT_MOUNT_PROFILE_REQUIRED")
                if len(selected_option_ids) > 32:
                    raise ValueError("CAD_PROFILE_SELECTION_LIMIT_EXCEEDED")
                selections: list[dict[str, str]] = []
                selected_profile_ids: set[str] = set()
                for option_id in selected_option_ids:
                    option = option_map.get(option_id)
                    if option is None:
                        raise ValueError("CAD_PROFILE_SELECTION_INVALID")
                    if option.profile_id in selected_profile_ids:
                        raise ValueError("CAD_PROFILE_SELECTION_DUPLICATE_REVISION")
                    selected_profile_ids.add(option.profile_id)
                    selections.append(
                        {
                            "hardwareId": option.hardware_id,
                            "profileId": option.profile_id,
                            "revision": option.revision,
                            "contentSha256": option.content_sha256,
                        }
                    )
                fact_updates[CAD_PROFILE_SELECTIONS_FACT_KEY] = (
                    "cad_mechanical_profile_selection",
                    {"schemaVersion": 1, "items": selections},
                )
                if question_id == CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID:
                    fact_updates[CAD_TARGET_FACT_KEY] = (
                        "cad_build_target",
                        "component_mount",
                    )
                    fact_updates[CAD_COMPONENT_MODE_FACT_KEY] = (
                        "cad_component_mode",
                        {"status": "not_applicable"},
                    )
                    fact_updates[CAD_FREEFORM_DESCRIPTION_FACT_KEY] = (
                        "cad_freeform_description",
                        {"status": "not_applicable"},
                    )
                    fact_updates[CAD_DIMENSIONS_FACT_KEY] = (
                        "cad_dimensions_lwh_mm",
                        {"status": "not_applicable"},
                    )
        if fact_updates:
            self._confirm_facts(
                project_id=project_id,
                source_message_id=user_message_id,
                updates=fact_updates,
                connection=connection,
            )
        return handled

    def is_workflow_request(
        self,
        *,
        project_id: str,
        conversation_id: str,
        message: str,
        source_message_id: str | None = None,
        request_message_id: str | None = None,
        response_message_id: str | None = None,
    ) -> bool:
        if is_cad_intent(message):
            return True
        if source_message_id and is_cad_clarification_payload(
            self._source_payload(project_id, source_message_id)
        ):
            return True
        excluded_ids = {
            value for value in (request_message_id, response_message_id) if value
        }
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, structured_payload_json
                FROM messages
                WHERE project_id = ? AND conversation_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 10
                """,
                (project_id, conversation_id),
            ).fetchall()
        recent_cad_context = False
        for row in rows:
            if str(row["id"]) in excluded_ids:
                continue
            if row["structured_payload_json"]:
                try:
                    payload = json.loads(str(row["structured_payload_json"]))
                except json.JSONDecodeError:
                    payload = None
                if is_cad_clarification_payload(payload) or (
                    isinstance(payload, dict)
                    and payload.get("type") == "cad_artifact"
                ):
                    recent_cad_context = True
            if str(row["role"]) == "user" and is_cad_intent(str(row["content"] or "")):
                recent_cad_context = True
        normalized = message.lower()
        return recent_cad_context and (
            is_cad_revision_request(normalized)
            or any(term in normalized for term in _CAD_CONTINUATION_TERMS)
        )

    def restart_for_revision(self, project_id: str) -> None:
        staleable_statuses = (
            CadRunStatus.DRAFT.value,
            CadRunStatus.VALIDATED.value,
            CadRunStatus.READY_FOR_REVIEW.value,
            CadRunStatus.FAILED.value,
            CadRunStatus.CANCELED.value,
            CadRunStatus.REJECTED.value,
        )
        status_placeholders = ", ".join("?" for _ in staleable_statuses)
        fact_placeholders = ", ".join("?" for _ in _CAD_INTAKE_FACT_KEYS)
        with self._connect() as conn:
            now = _timestamp()
            stale_reason = "用户已开启新一轮 CAD 结构输入确认。"
            candidate_rows = conn.execute(
                f"""
                SELECT cr.id, cr.source_message_id, cr.artifact_id,
                       cr.artifact_version_id, m.structured_payload_json
                FROM cad_runs cr
                LEFT JOIN messages m
                  ON m.id = cr.source_message_id AND m.project_id = cr.project_id
                WHERE cr.project_id = ? AND cr.status IN ({status_placeholders})
                """,
                (project_id, *staleable_statuses),
            ).fetchall()
            conn.execute(
                f"""
                UPDATE cad_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN ({status_placeholders})
                """,
                (
                    CadRunStatus.STALE.value,
                    stale_reason,
                    now,
                    project_id,
                    *staleable_statuses,
                ),
            )
            self._mark_cad_artifacts_stale(
                conn,
                project_id=project_id,
                candidate_rows=candidate_rows,
                reason=stale_reason,
                now=now,
            )
            for row in candidate_rows:
                self._mark_cad_projection_stale(
                    conn,
                    project_id=project_id,
                    cad_run_id=str(row["id"]),
                    source_message_id=row["source_message_id"],
                    payload_json=row["structured_payload_json"],
                    now=now,
                )

            question_rows = conn.execute(
                f"""
                SELECT source_message_id, question_id
                FROM clarification_questions
                WHERE project_id = ? AND status = 'pending'
                  AND question_id IN ({', '.join('?' for _ in _CAD_QUESTION_IDS)})
                """,
                (project_id, *_CAD_QUESTION_IDS),
            ).fetchall()
            source_questions: dict[str, set[str]] = {}
            for row in question_rows:
                source_questions.setdefault(str(row["source_message_id"]), set()).add(
                    str(row["question_id"])
                )
            conn.execute(
                f"""
                UPDATE clarification_questions
                SET status = 'superseded', updated_at = ?
                WHERE project_id = ? AND status = 'pending'
                  AND question_id IN ({', '.join('?' for _ in _CAD_QUESTION_IDS)})
                """,
                (now, project_id, *_CAD_QUESTION_IDS),
            )
            for source_message_id, question_ids in source_questions.items():
                self._mark_cad_questions_superseded(
                    conn,
                    project_id=project_id,
                    source_message_id=source_message_id,
                    question_ids=question_ids,
                    now=now,
                )

            conn.execute(
                f"""
                UPDATE project_shared_facts
                SET status = 'superseded', superseded_by = NULL, updated_at = ?
                WHERE project_id = ? AND status = 'confirmed'
                  AND COALESCE(key, field) IN ({fact_placeholders})
                """,
                (now, project_id, *_CAD_INTAKE_FACT_KEYS),
            )

    def apply_explicit_dimensions(
        self,
        *,
        project_id: str,
        message: str,
        source_message_id: str,
        baseline: CadIntakeState | None = None,
    ) -> bool:
        """Apply dimensions stated in natural language without another intake turn."""
        dimensions = extract_cad_dimensions(message)
        if dimensions is None:
            return False

        current = baseline or self.state(project_id)
        target = current.target or "box_with_lid"
        if target != "box_with_lid":
            return False
        mode = current.mode or "loose_storage"
        profiles = current.profiles if mode == "fixed_install" else ()
        self._confirm_facts(
            project_id=project_id,
            source_message_id=source_message_id,
            updates={
                CAD_TARGET_FACT_KEY: ("cad_build_target", target),
                CAD_COMPONENT_MODE_FACT_KEY: ("cad_component_mode", mode),
                CAD_DIMENSIONS_FACT_KEY: (
                    "cad_dimensions_lwh_mm",
                    dimensions,
                ),
                CAD_PROFILE_SELECTIONS_FACT_KEY: (
                    "cad_mechanical_profile_selection",
                    {
                        "schemaVersion": 1,
                        "items": [
                            {
                                "hardwareId": item.hardware_id,
                                "profileId": item.profile_id,
                                "revision": item.revision,
                                "contentSha256": item.content_sha256,
                            }
                            for item in profiles
                        ],
                    },
                ),
                CAD_FREEFORM_DESCRIPTION_FACT_KEY: (
                    "cad_freeform_description",
                    {"status": "not_applicable"},
                ),
            },
        )
        return True

    @staticmethod
    def _mark_cad_artifacts_stale(
        conn: sqlite3.Connection,
        *,
        project_id: str,
        candidate_rows: Iterable[sqlite3.Row],
        reason: str,
        now: str,
    ) -> None:
        candidate_rows = tuple(candidate_rows)
        version_ids = sorted(
            {
                str(row["artifact_version_id"])
                for row in candidate_rows
                if row["artifact_version_id"]
            }
        )
        if not version_ids:
            return
        placeholders = ", ".join("?" for _ in version_ids)
        conn.execute(
            f"""
            UPDATE artifact_versions
            SET status = ?, domain_status = ?, stale_reason = ?
            WHERE project_id = ? AND id IN ({placeholders})
            """,
            (
                ArtifactStatus.STALE.value,
                DomainArtifactStatus.OUTDATED.value,
                reason,
                project_id,
                *version_ids,
            ),
        )
        stale_version_ids = set(version_ids)
        artifact_ids = sorted(
            {
                str(row["artifact_id"])
                for row in candidate_rows
                if row["artifact_id"]
                and row["artifact_version_id"]
                and str(row["artifact_version_id"]) in stale_version_ids
            }
        )
        for artifact_id in artifact_ids:
            artifact = conn.execute(
                """
                SELECT current_version_id FROM artifacts
                WHERE id = ? AND project_id = ?
                """,
                (artifact_id, project_id),
            ).fetchone()
            if (
                artifact is None
                or str(artifact["current_version_id"] or "") not in stale_version_ids
            ):
                continue
            approved = conn.execute(
                """
                SELECT artifact_version_id FROM cad_runs
                WHERE project_id = ? AND artifact_id = ? AND status = ?
                  AND artifact_version_id IS NOT NULL
                ORDER BY version DESC LIMIT 1
                """,
                (project_id, artifact_id, CadRunStatus.APPROVED.value),
            ).fetchone()
            if approved is not None:
                conn.execute(
                    """
                    UPDATE artifacts
                    SET status = ?, domain_status = ?, current_version_id = ?,
                        updated_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        ArtifactStatus.APPROVED.value,
                        DomainArtifactStatus.CONFIRMED.value,
                        str(approved["artifact_version_id"]),
                        now,
                        artifact_id,
                        project_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE artifacts
                    SET status = ?, domain_status = ?, updated_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        ArtifactStatus.STALE.value,
                        DomainArtifactStatus.OUTDATED.value,
                        now,
                        artifact_id,
                        project_id,
                    ),
                )

    @staticmethod
    def _mark_cad_projection_stale(
        conn: sqlite3.Connection,
        *,
        project_id: str,
        cad_run_id: str,
        source_message_id: object,
        payload_json: object,
        now: str,
    ) -> None:
        if not source_message_id or not payload_json:
            return
        try:
            payload = json.loads(str(payload_json))
        except json.JSONDecodeError:
            return
        if (
            not isinstance(payload, dict)
            or payload.get("type") != "cad_artifact"
            or payload.get("cadRunId") != cad_run_id
        ):
            return
        payload["status"] = CadRunStatus.STALE.value
        conn.execute(
            """
            UPDATE messages
            SET structured_payload_json = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                json.dumps(payload, ensure_ascii=False),
                now,
                source_message_id,
                project_id,
            ),
        )

    @staticmethod
    def _mark_cad_questions_superseded(
        conn: sqlite3.Connection,
        *,
        project_id: str,
        source_message_id: str,
        question_ids: set[str],
        now: str,
    ) -> None:
        row = conn.execute(
            """
            SELECT structured_payload_json FROM messages
            WHERE id = ? AND project_id = ?
            """,
            (source_message_id, project_id),
        ).fetchone()
        if row is None or not row["structured_payload_json"]:
            return
        try:
            payload = json.loads(str(row["structured_payload_json"]))
        except json.JSONDecodeError:
            return
        if not is_cad_clarification_payload(payload):
            return
        questions = [dict(question) for question in _payload_questions(payload)]
        changed = False
        for question in questions:
            question_id = str(question.get("id") or "")
            if question_id not in question_ids or question.get("answered"):
                continue
            question["answered"] = True
            question["answer"] = {
                "questionId": question_id,
                "selectedOptionIds": [],
                "textInput": "已由新的 CAD 输入轮次替代。",
                "usedRecommendation": False,
            }
            changed = True
        if not changed:
            return
        payload["questions"] = questions
        if isinstance(payload.get("question"), dict):
            first_id = str(payload["question"].get("id") or "")
            payload["question"] = next(
                (item for item in questions if str(item.get("id") or "") == first_id),
                payload["question"],
            )
        conn.execute(
            """
            UPDATE messages
            SET structured_payload_json = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                json.dumps(payload, ensure_ascii=False),
                now,
                source_message_id,
                project_id,
            ),
        )

    def _all_profile_options(
        self,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> tuple[CadProfileOption, ...]:
        if connection is None:
            self._profiles.seed_builtin_profiles()
        options: list[CadProfileOption] = []
        for snapshot, _hardware_ids, _locked_ids in self._profile_rows(connection):
            identity = _profile_identity(snapshot)
            options.append(
                CadProfileOption(
                    option_id=f"{CAD_PROFILE_OPTION_PREFIX}{identity}",
                    hardware_id=f"{CAD_VIRTUAL_HARDWARE_PREFIX}{identity}",
                    profile_id=snapshot.profile_id,
                    revision=snapshot.revision,
                    content_sha256=snapshot.content_sha256,
                    label=f"{snapshot.display_name} · {snapshot.revision}",
                    description=(
                        f"{snapshot.dimensions.length_x:g} × "
                        f"{snapshot.dimensions.width_y:g} × "
                        f"{snapshot.dimensions.height_z:g} mm"
                    ),
                )
            )
        return tuple(options)

    def _profile_rows(
        self,
        connection: sqlite3.Connection | None,
    ) -> list[tuple[MechanicalProfileSnapshot, tuple[str, ...], tuple[str, ...]]]:
        if connection is None:
            return self._profiles.list_with_confirmed_hardware()
        rows = connection.execute(
            """
            SELECT profile_json, content_sha256
            FROM mechanical_profile_versions
            ORDER BY display_name, profile_id, revision
            """
        ).fetchall()
        snapshots: list[
            tuple[MechanicalProfileSnapshot, tuple[str, ...], tuple[str, ...]]
        ] = []
        for row in rows:
            snapshot = MechanicalProfileSnapshot.model_validate_json(row["profile_json"])
            if snapshot.content_sha256 != str(row["content_sha256"]):
                raise ValueError("MECHANICAL_PROFILE_HASH_MISMATCH")
            snapshots.append((snapshot, (), ()))
        return snapshots

    def state(self, project_id: str) -> CadIntakeState:
        facts = self._confirmed_facts(project_id)
        target_value = facts.get(CAD_TARGET_FACT_KEY)
        target: CadBuildTarget | None = (
            target_value
            if target_value
            in {
                "box_with_lid",
                "component_mount",
                "freeform_structure",
                "unihiker_k10_photo_album",
            }
            else None
        )
        mode_value = facts.get(CAD_COMPONENT_MODE_FACT_KEY)
        mode = (
            mode_value
            if isinstance(mode_value, str)
            and mode_value in {"loose_storage", "fixed_install"}
            else None
        )
        dimensions_value = facts.get(CAD_DIMENSIONS_FACT_KEY)
        dimensions = _validated_dimensions(dimensions_value)
        try:
            profiles = self.selected_profiles(project_id)
        except ValueError:
            profiles = ()
        if target is None and (mode is not None or dimensions is not None):
            target = "box_with_lid"
        if mode == "loose_storage":
            profiles = ()
        if target == "component_mount":
            mode = None
            dimensions = None
        if target == "unihiker_k10_photo_album":
            mode = None
            dimensions = None
            profiles = ()
        description_value = facts.get(CAD_FREEFORM_DESCRIPTION_FACT_KEY)
        return CadIntakeState(
            target=target,
            mode=mode,
            dimensions=dimensions,
            profiles=profiles,
            freeform_description=(
                description_value
                if isinstance(description_value, str) and description_value.strip()
                else None
            ),
        )

    def selected_profiles(
        self,
        project_id: str,
    ) -> tuple[ConfirmedCadProfileSelection, ...]:
        value = self._confirmed_facts(project_id).get(CAD_PROFILE_SELECTIONS_FACT_KEY)
        if not isinstance(value, dict) or value.get("schemaVersion") != 1:
            return ()
        items = value.get("items")
        if not isinstance(items, list):
            return ()
        if len(items) > 32:
            raise ValueError("CAD_PROFILE_SELECTION_LIMIT_EXCEEDED")
        selections: list[ConfirmedCadProfileSelection] = []
        profile_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("CAD_PROJECT_PROFILE_SELECTION_STALE")
            try:
                selection = ConfirmedCadProfileSelection(
                    hardware_id=str(item["hardwareId"]),
                    profile_id=str(item["profileId"]),
                    revision=str(item["revision"]),
                    content_sha256=str(item["contentSha256"]),
                )
                snapshot = self._profiles.get(
                    selection.profile_id,
                    revision=selection.revision,
                )
            except (KeyError, ValueError) as exc:
                raise ValueError("CAD_PROJECT_PROFILE_SELECTION_STALE") from exc
            expected_hardware_id = virtual_hardware_id(snapshot)
            if (
                selection.hardware_id != expected_hardware_id
                or selection.content_sha256 != snapshot.content_sha256
                or selection.profile_id in profile_ids
            ):
                raise ValueError("CAD_PROJECT_PROFILE_SELECTION_STALE")
            profile_ids.add(selection.profile_id)
            selections.append(selection)
        return tuple(selections)

    def resolve_virtual_hardware(
        self,
        *,
        project_id: str,
        hardware_id: str,
        declared_profile_id: str,
    ) -> MechanicalProfileSnapshot:
        selection = next(
            (
                item
                for item in self.selected_profiles(project_id)
                if item.hardware_id == hardware_id
                and item.profile_id == declared_profile_id
            ),
            None,
        )
        if selection is None:
            raise ValueError("CAD_PROJECT_PROFILE_SELECTION_STALE")
        snapshot = self._profiles.get(
            selection.profile_id,
            revision=selection.revision,
        )
        if snapshot.content_sha256 != selection.content_sha256:
            raise ValueError("CAD_PROJECT_PROFILE_SELECTION_STALE")
        return snapshot

    def ensure_runtime_output(
        self,
        project_id: str,
        output: object,
        *,
        requested_target: CadBuildTarget | None = None,
    ) -> None:
        state = self.state(project_id)
        target = requested_target or state.target
        cad_draft = getattr(output, "cadDraft", None)
        payload = getattr(output, "uiPayload", None)
        pending_items = getattr(output, "pendingItems", ())
        if target is None:
            if cad_draft is not None or not is_target_clarification_payload(payload):
                raise ValueError("CAD target is incomplete; return the server-owned target clarification")
            return
        if target == "component_mount":
            if len(state.profiles) != 1:
                if cad_draft is not None or not is_component_mount_profile_payload(payload):
                    raise ValueError(
                        "COMPONENT_MOUNT requires the server-owned single-profile clarification"
                    )
                if pending_items:
                    raise ValueError("CAD input must not be collected through pendingItems")
                return
            if cad_draft is None or cad_draft.templateKind is not CadTemplateKind.COMPONENT_MOUNT:
                raise ValueError("Confirmed component mount input must produce COMPONENT_MOUNT")
            if len(cad_draft.components) != 1:
                raise ValueError("COMPONENT_MOUNT requires exactly one component")
            if payload is not None or pending_items:
                raise ValueError("Complete COMPONENT_MOUNT output cannot request more input")
            return
        if target == "freeform_structure":
            if (
                cad_draft is None
                or cad_draft.templateKind is not CadTemplateKind.FREEFORM_STRUCTURE
                or cad_draft.geometry is None
                or cad_draft.components
            ):
                if (
                    requested_target is None
                    and state.freeform_description is None
                    and is_cad_clarification_payload(payload)
                ):
                    return
                raise ValueError("FREEFORM_STRUCTURE requires bounded declarative geometry")
            if payload is not None or pending_items:
                raise ValueError("Complete FREEFORM_STRUCTURE output cannot request more input")
            return
        if target == "unihiker_k10_photo_album":
            if (
                cad_draft is None
                or cad_draft.templateKind
                is not CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM
                or cad_draft.parameters
                or cad_draft.components
                or cad_draft.geometry is not None
            ):
                raise ValueError("K10 photo album target requires the fixed local template")
            if payload is not None or pending_items:
                raise ValueError("Complete K10 photo album output cannot request more input")
            return
        if state.mode is None or state.dimensions is None:
            if cad_draft is not None or not is_cad_clarification_payload(payload):
                raise ValueError(
                    "CAD input is incomplete; return uiPayload.type=clarification, not plain text or pendingItems"
                )
            if pending_items:
                raise ValueError("CAD input must not be collected through pendingItems")
            return
        if state.mode == "fixed_install" and not state.profiles:
            if cad_draft is not None or not is_profile_clarification_payload(payload):
                raise ValueError("Fixed-install CAD requires the server-owned profile clarification")
            if pending_items:
                raise ValueError("CAD input must not be collected through pendingItems")
            return
        if cad_draft is None:
            raise ValueError("Confirmed CAD input must produce cadDraft")
        if payload is not None:
            raise ValueError("cadDraft and clarification uiPayload are mutually exclusive")
        if pending_items:
            raise ValueError("A complete CAD draft must not create input PendingItems")
        expected_components = 0 if state.mode == "loose_storage" else len(state.profiles)
        if len(cad_draft.components) != expected_components:
            raise ValueError("cadDraft components do not match the confirmed CAD intake")

    def canonicalize_output(
        self,
        project_id: str,
        output: object,
        *,
        requested_target: CadBuildTarget | None = None,
    ) -> None:
        state = self.state(project_id)
        target = requested_target or state.target
        if target is None:
            setattr(output, "cadDraft", None)
            setattr(output, "uiPayload", self.target_question_payload())
            setattr(output, "pendingItems", [])
            setattr(output, "content", "开始建模前，请先确认要创建盒体、器件安装结构还是自然语言零件。")
            return
        if target == "component_mount":
            if len(state.profiles) != 1:
                setattr(output, "cadDraft", None)
                setattr(output, "uiPayload", self.component_mount_profile_question_payload())
                setattr(output, "pendingItems", [])
                setattr(output, "content", "请选择一个电子器件机械档案作为安装结构基准。")
                return
            selection = state.profiles[0]
            draft = getattr(output, "cadDraft", None)
            summary = "按已确认电子器件机械档案生成的安装底座与可拆压框"
            if draft is not None and draft.summary.strip():
                summary = draft.summary.strip()
            setattr(
                output,
                "cadDraft",
                CadDraft(
                    templateKind=CadTemplateKind.COMPONENT_MOUNT,
                    parameters={},
                    components=[
                        CadComponentDraft(
                            instanceId="component_1",
                            hardwareId=selection.hardware_id,
                            profileId=selection.profile_id,
                        )
                    ],
                    constraints={"process": "FDM"},
                    summary=summary,
                    requestedOutputs=list(CadOutputRole),
                ),
            )
            setattr(output, "uiPayload", None)
            setattr(output, "pendingItems", [])
            setattr(output, "content", "器件机械档案已确认，已形成安装结构 CAD 草稿。")
            return
        if target == "freeform_structure":
            draft = getattr(output, "cadDraft", None)
            if requested_target is None and state.freeform_description is None:
                setattr(output, "cadDraft", None)
                setattr(output, "uiPayload", self.freeform_description_question_payload())
                setattr(output, "pendingItems", [])
                setattr(output, "content", "请先描述零件实体、尺寸和需要切除的孔槽。")
                return
            if (
                draft is None
                or draft.templateKind is not CadTemplateKind.FREEFORM_STRUCTURE
                or draft.geometry is None
                or draft.components
            ):
                raise ValueError(
                    "FREEFORM_STRUCTURE provider output must contain bounded declarative geometry"
                )
            setattr(
                output,
                "cadDraft",
                CadDraft(
                    templateKind=CadTemplateKind.FREEFORM_STRUCTURE,
                    geometry=draft.geometry,
                    parameters={},
                    components=[],
                    constraints={"process": "FDM"},
                    summary=draft.summary.strip(),
                    requestedOutputs=list(CadOutputRole),
                ),
            )
            setattr(output, "uiPayload", None)
            setattr(output, "pendingItems", [])
            setattr(output, "content", "自然语言结构已转换为受控几何草稿，可开始本地建模。")
            return
        if target == "unihiker_k10_photo_album":
            setattr(
                output,
                "cadDraft",
                CadDraft(
                    templateKind=CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM,
                    parameters={},
                    components=[],
                    constraints={"process": "FDM"},
                    summary="行空板 K10 电子相册固定结构（已确认 16 阶段模板）",
                    requestedOutputs=list(CadOutputRole),
                ),
            )
            setattr(output, "uiPayload", None)
            setattr(output, "pendingItems", [])
            setattr(output, "content", "已选择行空板 K10 电子相册固定模板，可开始本地建模。")
            return
        if state.mode is None or state.dimensions is None:
            setattr(output, "cadDraft", None)
            setattr(output, "uiPayload", self.initial_question_payload(state))
            setattr(output, "pendingItems", [])
            setattr(output, "content", "开始建模前，请先完成下方结构输入确认。")
            return
        if state.mode == "fixed_install" and not state.profiles:
            setattr(output, "cadDraft", None)
            setattr(output, "uiPayload", self.profile_question_payload())
            setattr(output, "pendingItems", [])
            setattr(output, "content", "固定安装需要精确机械尺寸，请选择下方受信机械档案。")
            return
        draft = getattr(output, "cadDraft", None)
        if state.mode == "loose_storage":
            components: list[CadComponentDraft] = []
            summary = "按已确认内腔尺寸生成的松散储物盒与上盖"
        else:
            components = [
                CadComponentDraft(
                    instanceId=f"component_{index}",
                    hardwareId=selection.hardware_id,
                    profileId=selection.profile_id,
                )
                for index, selection in enumerate(state.profiles, start=1)
            ]
            summary = "按已确认内腔尺寸和机械档案生成的固定安装外壳与上盖"
        if draft is not None and draft.summary.strip():
            summary = draft.summary.strip()
        setattr(
            output,
            "cadDraft",
            CadDraft(
                templateKind=CadTemplateKind.BOX_WITH_LID,
                parameters=state.dimensions,
                components=components,
                constraints={"process": "FDM"},
                summary=summary,
                requestedOutputs=list(CadOutputRole),
            ),
        )
        setattr(output, "uiPayload", None)
        setattr(output, "pendingItems", [])
        setattr(output, "content", "结构输入已确认，已形成可开始建模的 CAD 草稿。")

    def dismiss_legacy_input_pending_items(self, project_id: str) -> None:
        now = _timestamp()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, description, reason, affected_experts_json
                FROM project_pending_items
                WHERE project_id = ? AND status = 'open' AND priority = 'missing_input'
                """,
                (project_id,),
            ).fetchall()
            for row in rows:
                try:
                    affected = json.loads(str(row["affected_experts_json"] or "[]"))
                except json.JSONDecodeError:
                    affected = []
                searchable = " ".join(
                    str(row[key]) for key in ("title", "description", "reason")
                ).lower()
                cad_context = any(
                    term in searchable
                    for term in ("cad", "3d", "建模", "外壳", "盒体", "三维")
                )
                input_context = any(
                    term in searchable
                    for term in ("尺寸", "机械档案", "器件型号", "安装方式", "接口位置")
                )
                if (
                    "structure_engineer" not in affected
                    or not cad_context
                    or not input_context
                ):
                    continue
                conn.execute(
                    """
                    UPDATE project_pending_items
                    SET status = 'dismissed', is_highlighted = 0, updated_at = ?
                    WHERE id = ? AND project_id = ? AND status = 'open'
                    """,
                    (now, row["id"], project_id),
                )
        ProjectCoordinatorService(self._db_path).refresh_highlighted_pending_item(project_id)

    def _source_payload(
        self,
        project_id: str,
        source_message_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, object] | None:
        if connection is None:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT structured_payload_json FROM messages
                    WHERE id = ? AND project_id = ?
                    """,
                    (source_message_id, project_id),
                ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT structured_payload_json FROM messages
                WHERE id = ? AND project_id = ?
                """,
                (source_message_id, project_id),
            ).fetchone()
        if row is None or not row["structured_payload_json"]:
            return None
        try:
            value = json.loads(str(row["structured_payload_json"]))
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def _confirmed_facts(self, project_id: str) -> dict[str, object]:
        keys = (
            CAD_TARGET_FACT_KEY,
            CAD_COMPONENT_MODE_FACT_KEY,
            CAD_DIMENSIONS_FACT_KEY,
            CAD_PROFILE_SELECTIONS_FACT_KEY,
            CAD_FREEFORM_DESCRIPTION_FACT_KEY,
        )
        placeholders = ", ".join("?" for _ in keys)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT COALESCE(key, field) AS fact_key, value_json
                FROM project_shared_facts
                WHERE project_id = ? AND status = 'confirmed'
                  AND COALESCE(key, field) IN ({placeholders})
                ORDER BY updated_at DESC
                """,
                (project_id, *keys),
            ).fetchall()
        values: dict[str, object] = {}
        for row in rows:
            key = str(row["fact_key"])
            if key not in values:
                values[key] = json.loads(str(row["value_json"]))
        return values

    def _confirm_facts(
        self,
        *,
        project_id: str,
        source_message_id: str,
        updates: dict[str, tuple[str, object]],
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is None:
            with self._connect() as conn:
                self._write_confirmed_facts(
                    conn,
                    project_id=project_id,
                    source_message_id=source_message_id,
                    updates=updates,
                )
            return
        self._write_confirmed_facts(
            connection,
            project_id=project_id,
            source_message_id=source_message_id,
            updates=updates,
        )

    @staticmethod
    def _write_confirmed_facts(
        conn: sqlite3.Connection,
        *,
        project_id: str,
        source_message_id: str,
        updates: dict[str, tuple[str, object]],
    ) -> None:
        now = _timestamp()
        for key, (field, value) in updates.items():
            identity = hashlib.sha256(
                f"{project_id}\0{source_message_id}\0{key}".encode("utf-8")
            ).hexdigest()[:32]
            fact_id = f"fact_cad_{identity}"
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = 'superseded', superseded_by = ?, updated_at = ?
                WHERE project_id = ? AND id <> ?
                  AND COALESCE(key, field) = ? AND status = 'confirmed'
                """,
                (fact_id, now, project_id, fact_id, key),
            )
            conn.execute(
                """
                INSERT INTO project_shared_facts (
                  id, project_id, field, key, value_json, status, source_type,
                  source_id, source_expert_id, proposed_by_expert_type,
                  confirmed_by, confirmed_at, superseded_by,
                  affects_artifact_ids_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'confirmed', 'user', ?, NULL, NULL,
                          'user', ?, NULL, '[]', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  field = excluded.field,
                  key = excluded.key,
                  value_json = excluded.value_json,
                  status = 'confirmed',
                  source_type = 'user',
                  source_id = excluded.source_id,
                  confirmed_by = 'user',
                  confirmed_at = excluded.confirmed_at,
                  superseded_by = NULL,
                  updated_at = excluded.updated_at
                """,
                (
                    fact_id,
                    project_id,
                    field,
                    key,
                    json.dumps(value, ensure_ascii=False),
                    source_message_id,
                    now,
                    now,
                    now,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def is_cad_intent(message: str) -> bool:
    normalized = message.lower()
    return (
        any(term in normalized for term in _K10_PHOTO_ALBUM_TERMS)
        or
        any(term in normalized for term in _CAD_INTENT_TERMS)
        or _CAD_FILE_PATTERN.search(normalized) is not None
        or _CAD_MODEL_ACTION_PATTERN.search(normalized) is not None
        or _COMPONENT_MOUNT_ACTION_PATTERN.search(normalized) is not None
        or _FREEFORM_ACTION_PATTERN.search(normalized) is not None
    )


def classify_cad_target(message: str) -> CadBuildTarget | None:
    normalized = message.lower()
    if any(term in normalized for term in _K10_PHOTO_ALBUM_TERMS):
        return "unihiker_k10_photo_album"
    if any(term in normalized for term in _BOX_TARGET_TERMS):
        return "box_with_lid"
    if any(term in normalized for term in _FREEFORM_NO_HARDWARE_TERMS):
        return "freeform_structure"
    if any(term in normalized for term in _COMPONENT_MOUNT_TARGET_TERMS):
        return "component_mount"
    if any(term in normalized for term in _FREEFORM_TARGET_TERMS):
        return "freeform_structure"
    return None


def is_cad_revision_request(message: str) -> bool:
    normalized = message.lower()
    has_revision_term = any(term in normalized for term in _CAD_REVISION_TERMS)
    has_inline_dimensions = _INLINE_DIMENSION_PATTERN.search(normalized) is not None
    return has_inline_dimensions or (
        has_revision_term
        and (
            is_cad_intent(normalized)
            or "尺寸" in normalized
            or "固定安装" in normalized
            or "松散存放" in normalized
        )
    )


def bind_current_cad_intake_revision(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    draft: CadDraft,
) -> CadDraft:
    """Attach the server-owned confirmed-intake identity to a persisted draft."""

    revision = _current_cad_intake_revision(conn, project_id)
    return draft.model_copy(update={"intakeSnapshotSha256": revision})


def assert_current_cad_intake_revision(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    draft: CadDraft | None,
    run_created_at: str,
) -> None:
    """Fail closed when a draft/job belongs to an older CAD intake round."""

    history = conn.execute(
        f"""
        SELECT id, status, updated_at
        FROM project_shared_facts
        WHERE project_id = ?
          AND COALESCE(key, field) IN ({', '.join('?' for _ in _CAD_INTAKE_FACT_KEYS)})
        """,
        (project_id, *_CAD_INTAKE_FACT_KEYS),
    ).fetchall()
    expected = draft.intakeSnapshotSha256 if draft is not None else None
    if not history:
        if expected is not None:
            raise ValueError("CAD_INTAKE_REVISED")
        return
    if draft is None:
        raise ValueError("CAD_INTAKE_REVISED")

    current = _current_cad_intake_revision(conn, project_id)
    if isinstance(expected, str):
        if current != expected:
            raise ValueError("CAD_INTAKE_REVISED")
    else:
        created_at = _parse_timestamp(run_created_at)
        if current is None or created_at is None:
            raise ValueError("CAD_INTAKE_REVISED")
        for row in history:
            updated_at = _parse_timestamp(str(row["updated_at"]))
            if updated_at is None or updated_at > created_at:
                raise ValueError("CAD_INTAKE_REVISED")

    if not _draft_matches_current_intake(conn, project_id, draft):
        raise ValueError("CAD_INTAKE_REVISED")


def _current_cad_intake_revision(
    conn: sqlite3.Connection,
    project_id: str,
) -> str | None:
    rows = conn.execute(
        f"""
        SELECT id, COALESCE(key, field) AS fact_key, value_json
        FROM project_shared_facts
        WHERE project_id = ? AND status = 'confirmed'
          AND COALESCE(key, field) IN ({', '.join('?' for _ in _CAD_INTAKE_FACT_KEYS)})
        ORDER BY fact_key, id
        """,
        (project_id, *_CAD_INTAKE_FACT_KEYS),
    ).fetchall()
    if not rows:
        return None
    payload = [
        {
            "id": str(row["id"]),
            "key": str(row["fact_key"]),
            "value": json.loads(str(row["value_json"])),
        }
        for row in rows
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _draft_matches_current_intake(
    conn: sqlite3.Connection,
    project_id: str,
    draft: CadDraft,
) -> bool:
    rows = conn.execute(
        f"""
        SELECT COALESCE(key, field) AS fact_key, value_json
        FROM project_shared_facts
        WHERE project_id = ? AND status = 'confirmed'
          AND COALESCE(key, field) IN ({', '.join('?' for _ in _CAD_INTAKE_FACT_KEYS)})
        ORDER BY updated_at DESC
        """,
        (project_id, *_CAD_INTAKE_FACT_KEYS),
    ).fetchall()
    facts: dict[str, object] = {}
    for row in rows:
        facts.setdefault(str(row["fact_key"]), json.loads(str(row["value_json"])))
    target = facts.get(CAD_TARGET_FACT_KEY)
    if target not in {
        "box_with_lid",
        "component_mount",
        "freeform_structure",
        "unihiker_k10_photo_album",
    }:
        target = "box_with_lid"
    selection_value = facts.get(CAD_PROFILE_SELECTIONS_FACT_KEY)
    if target == "freeform_structure":
        return (
            draft.templateKind is CadTemplateKind.FREEFORM_STRUCTURE
            and draft.geometry is not None
            and not draft.components
        )
    if target == "unihiker_k10_photo_album":
        return (
            draft.templateKind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM
            and not draft.parameters
            and not draft.components
            and draft.geometry is None
        )
    if target == "component_mount":
        if draft.templateKind is not CadTemplateKind.COMPONENT_MOUNT:
            return False
        if not isinstance(selection_value, dict) or selection_value.get("schemaVersion") != 1:
            return False
        items = selection_value.get("items")
        if not isinstance(items, list) or len(items) != 1:
            return False
        item = items[0]
        if not isinstance(item, dict) or len(draft.components) != 1:
            return False
        component = draft.components[0]
        try:
            return (
                component.hardwareId == str(item["hardwareId"])
                and component.profileId == str(item["profileId"])
            )
        except KeyError:
            return False
    if draft.templateKind is not CadTemplateKind.BOX_WITH_LID:
        return False
    mode = facts.get(CAD_COMPONENT_MODE_FACT_KEY)
    dimensions = _validated_dimensions(facts.get(CAD_DIMENSIONS_FACT_KEY))
    if mode not in {"loose_storage", "fixed_install"} or dimensions is None:
        return False
    try:
        if any(float(draft.parameters[name]) != value for name, value in dimensions.items()):
            return False
    except (KeyError, TypeError, ValueError):
        return False
    if mode == "loose_storage":
        return not draft.components

    if not isinstance(selection_value, dict) or selection_value.get("schemaVersion") != 1:
        return False
    items = selection_value.get("items")
    if not isinstance(items, list) or not items:
        return False
    try:
        expected_pairs = sorted(
            (str(item["hardwareId"]), str(item["profileId"]))
            for item in items
            if isinstance(item, dict)
        )
    except KeyError:
        return False
    actual_pairs = sorted(
        (str(component.hardwareId), str(component.profileId))
        for component in draft.components
        if component.hardwareId is not None and component.profileId is not None
    )
    return (
        len(expected_pairs) == len(items) == len(actual_pairs)
        and actual_pairs == expected_pairs
    )


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_cad_clarification_payload(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("type") == "clarification" and any(
        str(question.get("id", "")).startswith("cad_")
        for question in _payload_questions(payload)
    )


def is_profile_clarification_payload(payload: object) -> bool:
    return is_cad_clarification_payload(payload) and any(
        question.get("id") == CAD_PROFILE_QUESTION_ID
        for question in _payload_questions(payload)
    )


def is_target_clarification_payload(payload: object) -> bool:
    return is_cad_clarification_payload(payload) and any(
        question.get("id") == CAD_TARGET_QUESTION_ID
        for question in _payload_questions(payload)
    )


def is_component_mount_profile_payload(payload: object) -> bool:
    return is_cad_clarification_payload(payload) and any(
        question.get("id") == CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID
        for question in _payload_questions(payload)
    )


def parse_cad_dimensions(text: str) -> dict[str, float]:
    match = _DIMENSION_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError("CAD_DIMENSIONS_INVALID")
    dimensions = {
        "width": float(match.group("length")),
        "depth": float(match.group("width")),
        "height": float(match.group("height")),
    }
    for name, value in dimensions.items():
        if not production_parameter_spec(CadTemplateKind.BOX_WITH_LID, name).accepts(value):
            raise ValueError(f"CAD_DIMENSION_OUT_OF_RANGE: {name}")
    return dimensions


def extract_cad_dimensions(text: str) -> dict[str, float] | None:
    """Extract a valid L×W×H expression embedded in a natural-language turn."""
    match = _INLINE_DIMENSION_PATTERN.search(text)
    if match is None:
        return None
    return parse_cad_dimensions(match.group(0))


def virtual_hardware_id(snapshot: MechanicalProfileSnapshot) -> str:
    return f"{CAD_VIRTUAL_HARDWARE_PREFIX}{_profile_identity(snapshot)}"


def _profile_identity(snapshot: MechanicalProfileSnapshot) -> str:
    raw = f"{snapshot.profile_id}\0{snapshot.revision}\0{snapshot.content_sha256}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _validated_dimensions(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        dimensions = {
            "width": float(value["width"]),
            "depth": float(value["depth"]),
            "height": float(value["height"]),
        }
    except (KeyError, TypeError, ValueError):
        return None
    for name, number in dimensions.items():
        if not production_parameter_spec(CadTemplateKind.BOX_WITH_LID, name).accepts(number):
            return None
    return dimensions


def _payload_questions(payload: dict[str, object]) -> list[dict[str, Any]]:
    questions = payload.get("questions")
    if isinstance(questions, list):
        return [item for item in questions if isinstance(item, dict)]
    question = payload.get("question")
    return [question] if isinstance(question, dict) else []


def _answer_value(
    answer: object,
    attribute: str,
    mapping_key: str,
    default: object,
) -> object:
    if isinstance(answer, dict):
        return answer.get(mapping_key, default)
    return getattr(answer, attribute, default)


def _clarification_payload(
    summary: str,
    completeness: int,
    questions: list[dict[str, object]],
) -> dict[str, object]:
    highest_impact = questions[:1]
    return {
        "type": "clarification",
        "summary": (
            "先确认一个会影响建模方向的问题。其他低风险参数我会先按模板默认值推进，随时可以改。"
            if len(questions) > 1
            else summary
        ),
        "question": highest_impact[0],
        "questions": highest_impact,
        "completeness": completeness,
    }


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "CAD_BOX_WITH_LID_OPTION_ID",
    "CAD_COMPONENT_MOUNT_OPTION_ID",
    "CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID",
    "CAD_FREEFORM_DESCRIPTION_QUESTION_ID",
    "CAD_FREEFORM_STRUCTURE_OPTION_ID",
    "CAD_K10_PHOTO_ALBUM_OPTION_ID",
    "CAD_COMPONENT_MODE_QUESTION_ID",
    "CAD_DIMENSIONS_QUESTION_ID",
    "CAD_FIXED_INSTALL_OPTION_ID",
    "CAD_LOOSE_STORAGE_OPTION_ID",
    "CAD_PROFILE_QUESTION_ID",
    "CAD_TARGET_QUESTION_ID",
    "CAD_VIRTUAL_HARDWARE_PREFIX",
    "CadIntakeState",
    "CadProfileIntake",
    "ConfirmedCadProfileSelection",
    "is_cad_clarification_payload",
    "is_component_mount_profile_payload",
    "is_cad_intent",
    "classify_cad_target",
    "is_target_clarification_payload",
    "is_cad_revision_request",
    "extract_cad_dimensions",
    "parse_cad_dimensions",
    "virtual_hardware_id",
]
