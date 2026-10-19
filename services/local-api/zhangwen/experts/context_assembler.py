"""Minimal shared context assembly for expert runtime calls."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, Field, field_validator

from zhangwen.cad_agent.intake import CadProfileIntake
from zhangwen.cad_agent.template_catalog import production_template_parameter_specs
from zhangwen.cad_agent.models import (
    SUPPORTED_TEMPLATE_REVISIONS,
    CadOutputRole,
    CadTemplateKind,
)
from zhangwen.cad_agent.profile_repository import MechanicalProfileSnapshot
from zhangwen.cad_engine.profiles import unihiker_k10_profile
from zhangwen.devices.models import DeviceSessionStatus
from zhangwen.experts.config import canonical_expert_type
from zhangwen.hardware.board_profiles import BoardProfile, BoardProfileRepository
from zhangwen.hardware.board_skills import BoardSkillError, BoardSkillRepository
from zhangwen.hardware.hardware_skills import (
    HardwareContextCandidate,
    HardwareContextEntry,
    HardwareSkillNotFoundError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
)
from zhangwen.hardware.models import (
    HardwareCategory,
    HardwareComponent,
    ValidationResult,
    ValidationSeverity,
)
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.hardware.rule_engine import validate_components
from zhangwen.projects.models import ExpertType, SharedFactStatus


_PUBLIC_KNOWLEDGE_LIMIT = 4
_HARDWARE_MARKDOWN_TOTAL_LIMIT = 16_000
_DISCOVERED_HARDWARE_MARKDOWN_LIMIT = 1_000
_HARDWARE_QUERY_KEYWORDS = (
    "esp32",
    "dht22",
    "bme280",
    "oled",
    "ssd1306",
    "sg90",
    "gpio",
    "i2c",
    "pwm",
    "mcu",
    "主控",
    "开发板",
    "led",
    "传感器",
    "温湿度",
    "气压",
    "显示屏",
    "舵机",
    "继电器",
    "蜂鸣器",
    "按钮",
    "电源",
    "供电",
    "面包板",
    "杜邦线",
    "驱动",
    "k10",
    "行空板",
)
_HARDWARE_QUERY_EXPANSIONS = {
    "相册": ("屏", "tf", "存储", "摄像头"),
    "照片": ("屏", "tf", "存储", "摄像头"),
    "图片": ("屏", "tf", "存储"),
    "photo": ("display", "tf", "storage", "camera"),
    "image": ("display", "tf", "storage"),
    "主控": ("esp32", "mcu", "开发板"),
}
_CODE_CONTENT_KEYWORDS = (
    "代码",
    "micropython",
    "esp-claw",
    "esp_claw",
    "lua",
    "main.py",
    "main.lua",
    "config.py",
    "driver",
    "函数",
    "报错",
    "修改",
    "审查",
    "调试",
    "验证",
    "程序",
    "脚本",
    "阈值",
)
_CURRENT_CODE_CONTENT_LIMIT = 12_000
_CURRENT_CODE_FILE_LIMITS = {
    "src/main.py": 3_500,
    "scripts/main.lua": 3_500,
    "src/drivers.py": 3_000,
    "src/config.py": 2_500,
    "tests/test_logic.py": 2_000,
    "README.md": 1_000,
}
_K10_MARKERS = ("unihiker k10", "unihiker-k10", "行空板 k10", "行空板k10", "k10")
_OTHER_BOARD_MARKERS = (
    "esp32-c3",
    "esp32c3",
    "unihiker m10",
    "行空板 m10",
    "行空板m10",
    "arduino",
    "micro:bit",
    "microbit",
    "raspberry pi",
    "树莓派",
    "pico",
    "stm32",
    "掌控板",
)


class ContextAssemblyInput(BaseModel):
    projectId: str
    expert: ExpertType
    taskId: str | None = None
    userMessage: str = ""

    @field_validator("expert", mode="before")
    @classmethod
    def _canonical_expert(cls, value: Any) -> ExpertType:
        return canonical_expert_type(value)


class AssembledContext(BaseModel):
    projectSummary: str
    currentTask: dict[str, Any] | None = None
    relevantFacts: list[dict[str, Any]] = Field(default_factory=list)
    relevantDecisions: list[dict[str, Any]] = Field(default_factory=list)
    upstreamArtifacts: list[dict[str, Any]] = Field(default_factory=list)
    activeProposal: dict[str, Any] | None = None
    publicKnowledge: list[dict[str, Any]] = Field(default_factory=list)
    hardwareKnowledgePolicy: dict[str, Any] = Field(default_factory=dict)
    relevantDevices: list[dict[str, Any]] = Field(default_factory=list)
    relevantConflicts: list[dict[str, Any]] = Field(default_factory=list)
    currentCode: dict[str, Any] | None = None
    boardSkill: dict[str, Any] | None = None
    cadCapability: dict[str, Any] | None = None
    mechanicalProfiles: list[dict[str, Any]] = Field(default_factory=list)


class ContextAssembler:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def assemble(self, request: ContextAssemblyInput) -> AssembledContext:
        with self._connect() as conn:
            project = conn.execute(
                "SELECT id, name, stage, initial_idea FROM projects WHERE id = ?",
                (request.projectId,),
            ).fetchone()
            if project is None:
                raise ValueError("Project not found")
            facts = self._relevant_facts(conn, request)
            decisions = self._relevant_decisions(conn, request)
            artifacts = self._upstream_artifacts(conn, request)
            active_proposal = self._active_proposal(conn, request.projectId)
            project_summary = _project_summary(project)
            current_task = self._current_task(conn, request.projectId, request.expert)
            devices = self._relevant_devices(conn, request)
            conflicts = self._relevant_conflicts(conn, request.projectId)
            current_code = self._current_code(conn, request)
            mechanical_profiles = self._mechanical_profiles(conn, request)
            preferred_hardware_ids, _ = (
                _preferred_hardware_selection(
                    conn,
                    request.projectId,
                )
            )
        initial_idea = str(project["initial_idea"])
        hardware_catalog = self._hardware_catalog(
            required=bool(preferred_hardware_ids),
        )
        (
            preferred_hardware,
            preferred_hardware_validation,
            preferred_hardware_entries,
        ) = self._preferred_hardware(
            preferred_hardware_ids,
            hardware_catalog or [],
        )
        preferred_hardware_query = "\n".join(
            [initial_idea, *(component.name for component in preferred_hardware)]
        )
        public_knowledge = self._public_knowledge(
            request,
            preferred_hardware_query,
            preferred_hardware,
            preferred_hardware_validation,
            hardware_catalog,
            preferred_hardware_entries,
        )
        return AssembledContext(
            projectSummary=project_summary,
            currentTask=current_task,
            relevantFacts=facts,
            relevantDecisions=decisions,
            upstreamArtifacts=artifacts,
            activeProposal=active_proposal,
            publicKnowledge=public_knowledge,
            hardwareKnowledgePolicy=_hardware_knowledge_policy(public_knowledge),
            relevantDevices=devices,
            relevantConflicts=conflicts,
            currentCode=current_code,
            boardSkill=self._board_skill(request, preferred_hardware_query),
            cadCapability=_cad_capability(request.expert),
            mechanicalProfiles=mechanical_profiles,
        )

    def _active_proposal(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT id, solution_id, solution_version, version, status, sections_json
            FROM proposals
            WHERE project_id = ? AND status = 'APPROVED'
            ORDER BY version DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        raw_sections = _load_json_array(row["sections_json"])
        remaining = 12_000
        sections: list[dict[str, str]] = []
        for item in raw_sections:
            if remaining <= 0:
                break
            content = str(item.get("content", ""))[: min(3_000, remaining)]
            remaining -= len(content)
            sections.append(
                {
                    "id": str(item.get("id", "")),
                    "title": str(item.get("title", "")),
                    "content": content,
                }
            )
        return {
            "id": row["id"],
            "version": row["version"],
            "status": row["status"],
            "solutionId": row["solution_id"],
            "solutionVersion": row["solution_version"],
            "sections": sections,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _mechanical_profiles(
        self,
        conn: sqlite3.Connection,
        request: ContextAssemblyInput,
    ) -> list[dict[str, Any]]:
        if request.expert != ExpertType.STRUCTURE_ENGINEER:
            return []
        try:
            component_ids = _dedupe_component_ids(
                [
                    *_preferred_hardware_component_ids(conn, request.projectId),
                    *_confirmed_bom_component_ids(conn, request.projectId),
                ]
            )
        except sqlite3.OperationalError:
            component_ids = []
        rows: list[sqlite3.Row] = []
        if component_ids:
            placeholders = ", ".join("?" for _ in component_ids)
            try:
                rows = conn.execute(
                    f"""
                SELECT
                  hc.id AS hardware_id,
                  hc.name AS hardware_name,
                  hc.category AS hardware_category,
                  hml.mechanical_profile_id AS profile_id,
                  hml.mechanical_profile_revision AS revision,
                  hml.evidence_level AS link_evidence_level,
                  hml.confirmed_at AS link_confirmed_at,
                  mpv.display_name,
                  mpv.schema_version,
                  mpv.source,
                  mpv.evidence_level AS profile_evidence_level,
                  mpv.representation,
                  mpv.profile_json,
                  mpv.content_sha256
                FROM hardware_components hc
                JOIN hardware_mechanical_links hml
                  ON hml.hardware_component_id = hc.id
                JOIN mechanical_profile_versions mpv
                  ON mpv.profile_id = hml.mechanical_profile_id
                 AND mpv.revision = hml.mechanical_profile_revision
                WHERE hc.id IN ({placeholders})
                  AND hc.status = 'ACTIVE'
                  AND hml.confirmed_at IS NOT NULL
                    """,
                    component_ids,
                ).fetchall()
            except sqlite3.OperationalError:
                # Pre-v24 databases have no mechanical profile tables. Absence is safer
                # than falling back to a name or keyword based dimension guess.
                rows = []

        order = {component_id: index for index, component_id in enumerate(component_ids)}
        profiles: list[dict[str, Any]] = []
        for row in sorted(rows, key=lambda item: order.get(str(item["hardware_id"]), 999)):
            try:
                profile = json.loads(row["profile_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(profile, dict):
                continue
            profiles.append(
                {
                    "source": "confirmed_bom_mechanical_mapping",
                    "hardwareId": str(row["hardware_id"]),
                    "hardwareName": str(row["hardware_name"]),
                    "hardwareCategory": str(row["hardware_category"]),
                    "profileId": str(row["profile_id"]),
                    "revision": str(row["revision"]),
                    "displayName": str(row["display_name"]),
                    "schemaVersion": str(row["schema_version"]),
                    "profileSource": str(row["source"]),
                    "evidenceLevel": str(row["profile_evidence_level"]),
                    "mappingEvidenceLevel": str(row["link_evidence_level"]),
                    "mappingConfirmed": row["link_confirmed_at"] is not None,
                    "representation": str(row["representation"]),
                    "contentSha256": str(row["content_sha256"]),
                    "profile": profile,
                }
            )
        mapped_hardware_ids = {str(item["hardwareId"]) for item in profiles}
        if (
            "hw_seed_unihiker_k10" in component_ids
            and "hw_seed_unihiker_k10" not in mapped_hardware_ids
        ):
            hardware = conn.execute(
                """
                SELECT id, name, category FROM hardware_components
                WHERE id = 'hw_seed_unihiker_k10' AND status = 'ACTIVE'
                """
            ).fetchone()
            if hardware is not None:
                snapshot = MechanicalProfileSnapshot.from_profile(unihiker_k10_profile())
                profiles.append(
                    {
                        "source": "trusted_k10_alias",
                        "hardwareId": str(hardware["id"]),
                        "hardwareName": str(hardware["name"]),
                        "hardwareCategory": str(hardware["category"]),
                        "profileId": snapshot.profile_id,
                        "revision": snapshot.revision,
                        "displayName": snapshot.display_name,
                        "schemaVersion": snapshot.schema_version,
                        "profileSource": snapshot.source.value,
                        "evidenceLevel": snapshot.evidence_level,
                        "mappingEvidenceLevel": "TRUSTED_ALIAS",
                        "mappingConfirmed": True,
                        "representation": snapshot.representation,
                        "contentSha256": snapshot.content_sha256,
                        "profile": snapshot.model_dump(mode="json"),
                    }
                )
        intake = CadProfileIntake(self._db_path)
        try:
            selections = intake.selected_profiles(request.projectId)
        except (sqlite3.OperationalError, ValueError):
            selections = ()
        selected_profiles: list[dict[str, Any]] = []
        for selection in selections:
            try:
                snapshot = intake.resolve_virtual_hardware(
                    project_id=request.projectId,
                    hardware_id=selection.hardware_id,
                    declared_profile_id=selection.profile_id,
                )
            except ValueError:
                continue
            selected_profiles.append(
                {
                    "source": "confirmed_project_cad_selection",
                    "hardwareId": selection.hardware_id,
                    "hardwareName": snapshot.display_name,
                    "hardwareCategory": "project_cad_selection",
                    "profileId": snapshot.profile_id,
                    "revision": snapshot.revision,
                    "displayName": snapshot.display_name,
                    "schemaVersion": snapshot.schema_version,
                    "profileSource": snapshot.source.value,
                    "evidenceLevel": snapshot.evidence_level,
                    "mappingEvidenceLevel": "USER_CONFIRMED_PROJECT_SELECTION",
                    "mappingConfirmed": True,
                    "representation": snapshot.representation,
                    "contentSha256": snapshot.content_sha256,
                    "profile": snapshot.model_dump(mode="json"),
                }
            )
        profiles.sort(key=lambda item: order.get(str(item["hardwareId"]), 999))
        selected_identities = {
            (str(item["hardwareId"]), str(item["profileId"]))
            for item in selected_profiles
        }
        remaining_profiles = [
            item
            for item in profiles
            if (str(item["hardwareId"]), str(item["profileId"]))
            not in selected_identities
        ]
        return [*selected_profiles, *remaining_profiles][:32]

    def _relevant_facts(
        self,
        conn: sqlite3.Connection,
        request: ContextAssemblyInput,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM project_shared_facts
            WHERE project_id = ?
              AND status IN ('confirmed', 'proposed')
            ORDER BY updated_at DESC
            """,
            (request.projectId,),
        ).fetchall()
        facts = [_fact_from_row(row) for row in rows]
        facts.extend(_legacy_context_facts(conn, request.projectId))
        facts = _dedupe_by_id(facts)
        facts.sort(key=_fact_priority)
        return facts[:12]

    def _relevant_decisions(
        self,
        conn: sqlite3.Connection,
        request: ContextAssemblyInput,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM project_decisions
            WHERE project_id = ?
              AND status IN ('confirmed', 'proposed')
            ORDER BY updated_at DESC
            """,
            (request.projectId,),
        ).fetchall()
        decisions = [_decision_from_row(row) for row in rows]
        decisions.sort(key=_fact_priority)
        return decisions[:8]

    def _upstream_artifacts(
        self,
        conn: sqlite3.Connection,
        request: ContextAssemblyInput,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
              a.id,
              a.title,
              a.kind,
              a.status,
              a.domain_status,
              a.source_agent_id,
              a.owner_expert_id,
              a.owner_expert_type,
              a.current_version_id,
              a.updated_at,
              av.version,
              av.preview_json,
              av.dependencies_json,
              av.status AS version_status,
              av.domain_status AS version_domain_status
            FROM artifacts a
            LEFT JOIN artifact_versions av ON av.id = a.current_version_id
            WHERE a.project_id = ?
              AND a.status != 'ARCHIVED'
            ORDER BY a.updated_at DESC
            LIMIT 30
            """,
            (request.projectId,),
        ).fetchall()
        artifacts = [_artifact_from_row(row) for row in rows]
        artifact_ids = [artifact["artifactId"] for artifact in artifacts]
        dependency_map = _artifact_dependency_map(conn, request.projectId, artifact_ids)
        for artifact in artifacts:
            dependencies = dependency_map.get(artifact["artifactId"], [])
            artifact["dependencies"] = [*artifact["dependencies"], *dependencies]
        return artifacts[:10]

    def _relevant_devices(
        self,
        conn: sqlite3.Connection,
        request: ContextAssemblyInput,
    ) -> list[dict[str, Any]]:
        if request.expert != ExpertType.SMART_ENGINEER:
            return []
        rows = conn.execute(
            """
            SELECT board, status, connected_at, last_seen_at
            FROM device_sessions
            WHERE project_id = ?
            ORDER BY last_seen_at DESC
            LIMIT 3
            """,
            (request.projectId,),
        ).fetchall()
        return [_cloud_device_summary(row) for row in rows]

    def _relevant_conflicts(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> list[dict[str, Any]]:
        row = conn.execute(
            """
            SELECT current_item_json, conflicts_json, dependencies_json
            FROM project_coordinator_states
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return []
        current_item = _load_json(row["current_item_json"])
        conflicts = _load_json_array(row["conflicts_json"])
        dependencies = _load_json_array(row["dependencies_json"])
        items: list[dict[str, Any]] = []
        if isinstance(current_item, dict):
            items.append({"kind": "current_item", **current_item})
        items.extend({"kind": "conflict", **item} for item in conflicts)
        items.extend({"kind": "dependency", **item} for item in dependencies)
        return items[:8]

    def _public_knowledge(
        self,
        request: ContextAssemblyInput,
        fallback_query: str,
        preferred_hardware: list[HardwareComponent],
        preferred_hardware_validation: dict[str, Any] | None,
        hardware_catalog: list[HardwareContextCandidate] | None,
        preferred_hardware_entries: list[HardwareContextEntry],
    ) -> list[dict[str, Any]]:
        profiles = self._board_profiles(request.userMessage, fallback_query)
        if hardware_catalog is None:
            return [
                *self._hardware_knowledge(
                    preferred_hardware,
                    selected_ids={component.id for component in preferred_hardware},
                    preferred_hardware_validation=preferred_hardware_validation,
                ),
                *profiles,
            ]
        selected_ids = {component.id for component in preferred_hardware}
        hardware_query = f"{request.userMessage}\n{fallback_query}".strip()
        ranked = sorted(
            (
                (
                    _hardware_knowledge_score(
                        candidate.component,
                        hardware_query,
                        skill_text=candidate.searchText[:6_000],
                    ),
                    candidate,
                )
                for candidate in hardware_catalog
                if candidate.component.id not in selected_ids
            ),
            key=lambda item: (-item[0], item[1].component.name),
        )
        matched_candidates = [
            candidate
            for score, candidate in ranked
            if score > 0
        ][:_PUBLIC_KNOWLEDGE_LIMIT]
        fallback_candidates = [
            candidate
            for candidate in sorted(
                hardware_catalog,
                key=lambda item: item.component.name,
            )
            if candidate.component.id not in selected_ids
        ][:_PUBLIC_KNOWLEDGE_LIMIT]
        extra_candidates = sorted(
            matched_candidates or fallback_candidates,
            key=lambda candidate: (
                candidate.component.category != HardwareCategory.MCU,
                candidate.component.name.casefold(),
            ),
        )
        extra_entries = HardwareSkillRepository(
            self._db_path.parents[1],
            self._db_path,
        ).list_active_context_entries(
            candidates=extra_candidates,
            max_chars=_HARDWARE_MARKDOWN_TOTAL_LIMIT,
        )
        extra_components = [entry.component for entry in extra_entries]
        skill_markdown_by_component = {
            entry.component.id: entry.markdown
            for entry in [*preferred_hardware_entries, *extra_entries]
        }
        hardware_items = self._hardware_knowledge(
            [*preferred_hardware, *extra_components],
            selected_ids=selected_ids,
            preferred_hardware_validation=preferred_hardware_validation,
            skill_markdown_by_component=skill_markdown_by_component,
        )
        selected = [
            item for item in hardware_items if item.get("selectedByUser") is True
        ]
        discovered = [
            item for item in hardware_items if item.get("selectedByUser") is not True
        ]
        return [*selected, *profiles, *discovered]

    def _hardware_knowledge(
        self,
        components: list[HardwareComponent],
        *,
        selected_ids: set[str],
        preferred_hardware_validation: dict[str, Any] | None,
        skill_markdown_by_component: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        if not components:
            return []
        hardware_skills = HardwareSkillRepository(
            self._db_path.parents[1],
            self._db_path,
        )
        selected_count = sum(component.id in selected_ids for component in components)
        selected_max_chars = (
            max(800, _HARDWARE_MARKDOWN_TOTAL_LIMIT // selected_count)
            if selected_count
            else 0
        )
        discovered_max_chars = (
            _DISCOVERED_HARDWARE_MARKDOWN_LIMIT
            if selected_count
            else max(800, _HARDWARE_MARKDOWN_TOTAL_LIMIT // len(components))
        )
        items: list[dict[str, Any]] = []
        for component in components:
            selected_by_user = component.id in selected_ids
            max_chars = (
                selected_max_chars if selected_by_user else discovered_max_chars
            )
            item = _hardware_public_knowledge(
                component,
                source=(
                    "preferred_project_hardware"
                    if selected_by_user
                    else "local_hardware_library"
                ),
                selected_by_user=selected_by_user,
            )
            if selected_by_user:
                item["selectionPolicy"] = "prefer_selected_and_fill_gaps"
                item["recommendationRule"] = (
                    "这是用户已有器件；必须优先复用，不得重复推荐，只补充功能缺口。"
                )
                if preferred_hardware_validation is not None:
                    item["selectionValidation"] = preferred_hardware_validation
            try:
                skill_markdown = (
                    skill_markdown_by_component.get(component.id)
                    if skill_markdown_by_component is not None
                    else None
                )
                if skill_markdown is None:
                    skill_markdown = hardware_skills.render_context(
                        component.id,
                        max_chars=max_chars,
                    )
            except (HardwareSkillNotFoundError, HardwareSkillValidationError):
                if selected_by_user:
                    raise
                continue
            bounded_markdown = skill_markdown[:max_chars]
            item["hardwareSkillMarkdown"] = bounded_markdown
            item["componentPackageMarkdown"] = bounded_markdown
            items.append(item)
        return items

    def _hardware_catalog(
        self,
        *,
        required: bool,
    ) -> list[HardwareContextCandidate] | None:
        try:
            seed_default_components(self._db_path)
            return HardwareSkillRepository(
                self._db_path.parents[1],
                self._db_path,
            ).list_active_context_candidates()
        except (
            sqlite3.Error,
            HardwareSkillNotFoundError,
            HardwareSkillValidationError,
            OSError,
            UnicodeError,
            ValueError,
        ):
            if required:
                raise
            return None

    def _preferred_hardware(
        self,
        component_ids: list[str],
        hardware_catalog: list[HardwareContextCandidate],
    ) -> tuple[
        list[HardwareComponent],
        dict[str, Any] | None,
        list[HardwareContextEntry],
    ]:
        if not component_ids:
            return [], None, []
        entries_by_id = {
            entry.component.id: entry for entry in hardware_catalog
        }
        missing_ids = [
            component_id
            for component_id in component_ids
            if component_id not in entries_by_id
        ]
        if missing_ids:
            raise HardwareSkillNotFoundError(
                "项目已选硬件 Skill 不存在、未激活或未通过完整校验："
                + "、".join(missing_ids)
            )
        selected_candidates = [
            entries_by_id[component_id] for component_id in component_ids
        ]
        selected_entries = HardwareSkillRepository(
            self._db_path.parents[1],
            self._db_path,
        ).list_active_context_entries(
            candidates=selected_candidates,
            max_chars=_HARDWARE_MARKDOWN_TOTAL_LIMIT,
            required_component_ids=set(component_ids),
        )
        selected_entries_by_id = {
            entry.component.id: entry for entry in selected_entries
        }
        selected_entries = [
            selected_entries_by_id[component_id] for component_id in component_ids
        ]
        components = [entry.component for entry in selected_entries]
        validation = validate_components(
            components,
            rules=[rule for entry in selected_entries for rule in entry.rules],
        )
        if validation.overall == ValidationSeverity.FAIL:
            failed_messages = [
                check.message
                for check in validation.checks
                if check.severity == ValidationSeverity.FAIL
            ]
            detail = "；".join(failed_messages[:4])
            raise HardwareSkillValidationError(
                "项目已选硬件的当前 Skill revision 未通过校验："
                f"{detail or validation.message}"
            )
        return components, _current_hardware_validation(validation), selected_entries

    def _board_profiles(
        self,
        query: str,
        fallback_query: str = "",
    ) -> list[dict[str, Any]]:
        try:
            profiles = BoardProfileRepository(self._db_path.parents[1]).search(
                _effective_board_query(query, fallback_query)
            )
        except (OSError, ValueError):
            return []
        return [_board_profile_public_knowledge(profile) for profile in profiles]

    def _board_skill(
        self,
        request: ContextAssemblyInput,
        initial_idea: str,
    ) -> dict[str, Any] | None:
        if request.expert != ExpertType.SMART_ENGINEER:
            return None
        query = _effective_board_query(request.userMessage, initial_idea)
        try:
            profiles = BoardProfileRepository(self._db_path.parents[1]).search(
                query,
                limit=1,
            )
            if not profiles:
                return None
            profile = profiles[0]
            context = BoardSkillRepository().build_context(profile.id, query)
        except (OSError, ValueError, BoardSkillError):
            return None
        context["boardProfile"] = {
            "profileId": profile.id,
            "revision": profile.revision,
            "overridden": profile.overridden,
        }
        return context

    def _current_code(
        self,
        conn: sqlite3.Connection,
        request: ContextAssemblyInput,
    ) -> dict[str, Any] | None:
        if request.expert != ExpertType.SMART_ENGINEER:
            return None
        row = conn.execute(
            """
            SELECT
              cr.id,
              cr.version,
              cr.status,
              cr.runtime,
              cr.entrypoint,
              cr.updated_at,
              cr.stale_reason,
              cr.test_result_json,
              cp.base_snapshot_id,
              cp.summary,
              cp.diff
            FROM code_runs cr
            JOIN code_patches cp ON cp.code_run_id = cr.id
            WHERE cr.project_id = ?
            ORDER BY cr.version DESC
            LIMIT 1
            """,
            (request.projectId,),
        ).fetchone()
        if row is None:
            return None
        include_content = any(
            keyword in request.userMessage.lower()
            for keyword in _CODE_CONTENT_KEYWORDS
        )
        file_rows = conn.execute(
            """
            SELECT path, language, content
            FROM code_files
            WHERE code_run_id = ?
            ORDER BY CASE path
              WHEN 'src/main.py' THEN 1
              WHEN 'scripts/main.lua' THEN 1
              WHEN 'src/drivers.py' THEN 2
              WHEN 'scripts/drivers.lua' THEN 2
              WHEN 'src/config.py' THEN 3
              WHEN 'scripts/config.lua' THEN 3
              WHEN 'tests/test_logic.py' THEN 4
              WHEN 'README.md' THEN 5
              ELSE 99
            END, path
            """,
            (row["id"],),
        ).fetchall()
        remaining = _CURRENT_CODE_CONTENT_LIMIT
        files: list[dict[str, Any]] = []
        for file_row in file_rows:
            file_item: dict[str, Any] = {
                "path": file_row["path"],
                "language": file_row["language"],
            }
            if include_content and remaining > 0:
                content = str(file_row["content"])
                file_limit = _CURRENT_CODE_FILE_LIMITS.get(
                    str(file_row["path"]),
                    1_000,
                )
                excerpt = content[: min(remaining, file_limit)]
                file_item["content"] = excerpt
                file_item["truncated"] = len(excerpt) < len(content)
                remaining -= len(excerpt)
            files.append(file_item)
        return {
            "codeRunId": row["id"],
            "version": row["version"],
            "status": row["status"],
            "runtime": row["runtime"],
            "entrypoint": row["entrypoint"],
            "modifiedByUser": bool(row["base_snapshot_id"]),
            "baseCodeRunId": row["base_snapshot_id"],
            "changeSummary": row["summary"],
            "changeDiff": str(row["diff"])[:4000],
            "requiresValidation": bool(row["base_snapshot_id"])
            and row["status"] == "DRAFT",
            "staleReason": row["stale_reason"],
            "testResult": _load_json(row["test_result_json"]),
            "files": files,
            "updatedAt": row["updated_at"],
        }

    def _current_task(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        expert: ExpertType,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT id, expert_type, status, workspace_status, current_task
            FROM project_experts
            WHERE project_id = ?
              AND expert_type = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            ORDER BY added_at ASC
            LIMIT 1
            """,
            (project_id, expert.value),
        ).fetchone()
        if row is None:
            return None
        return {
            "projectExpertId": row["id"],
            "expertType": row["expert_type"],
            "status": row["status"],
            "workspaceStatus": row["workspace_status"],
            "currentTask": row["current_task"],
        }


def _project_summary(row: sqlite3.Row) -> str:
    idea = (row["initial_idea"] or "").strip()
    if len(idea) > 160:
        idea = f"{idea[:157]}..."
    return f"{row['name']} ({row['stage']}): {idea}"


def _cloud_device_summary(row: sqlite3.Row) -> dict[str, Any]:
    status, ready = _cloud_device_status(str(row["status"]))
    return {
        "board": str(row["board"]).strip()[:80] or "Unknown",
        "status": status,
        "ready": ready,
        "connectedAt": row["connected_at"],
        "lastSeenAt": row["last_seen_at"],
    }


def _cloud_device_status(status: str) -> tuple[str, bool]:
    if status == DeviceSessionStatus.READY.value:
        return "ready", True
    if status in {
        DeviceSessionStatus.DISCOVERED.value,
        DeviceSessionStatus.CONNECTING.value,
        DeviceSessionStatus.CONNECTED.value,
    }:
        return "available", False
    if status in {
        DeviceSessionStatus.UPLOADING.value,
        DeviceSessionStatus.RESTARTING.value,
        DeviceSessionStatus.VERIFYING.value,
    }:
        return "busy", False
    if status in {
        DeviceSessionStatus.DISCONNECTED.value,
        DeviceSessionStatus.ERROR.value,
    }:
        return "unavailable", False
    return "unknown", False


def _fact_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "field": row["field"],
        "key": row["key"],
        "value": _load_json(row["value_json"]),
        "status": row["status"],
        "sourceType": row["source_type"],
        "sourceId": row["source_id"],
        "sourceExpertId": row["source_expert_id"],
        "proposedBy": row["proposed_by_expert_type"],
        "confirmedBy": row["confirmed_by"],
        "confirmedAt": row["confirmed_at"],
        "supersededBy": row["superseded_by"],
        "affectsArtifactIds": _load_json_array(row["affects_artifact_ids_json"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _legacy_context_facts(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT goals_json, constraints_json, requirements_json
        FROM project_shared_contexts
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return []
    facts: list[dict[str, Any]] = []
    for field_name in ("goals_json", "constraints_json", "requirements_json"):
        for item in _load_json_array(row[field_name]):
            if isinstance(item, dict):
                facts.append(item)
    return facts


def _decision_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "value": _load_json(row["value_json"]),
        "status": row["status"],
        "reason": row["reason"],
        "proposedBy": row["proposed_by_expert_type"],
        "confirmedBy": row["confirmed_by"],
        "confirmedAt": row["confirmed_at"],
        "affectedArtifactIds": _load_json_array(row["affected_artifact_ids_json"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _artifact_from_row(row: sqlite3.Row) -> dict[str, Any]:
    preview = _load_json(row["preview_json"]) if row["preview_json"] else {}
    dependencies = _load_json_array(row["dependencies_json"])
    return {
        "artifactId": row["id"],
        "title": row["title"],
        "kind": row["kind"],
        "status": row["status"],
        "domainStatus": row["domain_status"] or row["version_domain_status"],
        "sourceAgentId": row["source_agent_id"],
        "ownerExpertId": row["owner_expert_id"],
        "ownerExpertType": row["owner_expert_type"],
        "currentVersionId": row["current_version_id"],
        "version": row["version"],
        "versionStatus": row["version_status"],
        "summary": preview.get("summary") if isinstance(preview, dict) else None,
        "dependencies": dependencies,
        "updatedAt": row["updated_at"],
    }


def _artifact_dependency_map(
    conn: sqlite3.Connection,
    project_id: str,
    artifact_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not artifact_ids:
        return {}
    placeholders = ",".join("?" for _ in artifact_ids)
    rows = conn.execute(
        f"""
        SELECT *
        FROM artifact_dependencies
        WHERE project_id = ?
          AND artifact_id IN ({placeholders})
        ORDER BY created_at DESC
        """,
        (project_id, *artifact_ids),
    ).fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row["artifact_id"], []).append(
            {
                "artifactId": row["upstream_artifact_id"],
                "versionId": row["upstream_version_id"],
                "version": row["upstream_version"],
                "kind": row["kind"],
                "label": row["label"],
                "status": row["status"],
                "relation": row["relation"],
                "required": bool(row["required"]),
            }
        )
    return result


def _is_relevant_fact(fact: dict[str, Any], expert: ExpertType, user_message: str) -> bool:
    if fact.get("status") == SharedFactStatus.CONFIRMED.value:
        return True
    if expert == ExpertType.PROBLEM_GUIDE:
        return True
    return _contains_expert_keyword(_searchable_text(fact, user_message), expert)


def _is_relevant_decision(row: sqlite3.Row, expert: ExpertType, user_message: str) -> bool:
    if row["status"] == SharedFactStatus.CONFIRMED.value:
        return True
    if expert == ExpertType.PROBLEM_GUIDE:
        return True
    return _contains_expert_keyword(
        f"{row['title']} {row['reason']} {row['value_json']} {user_message}",
        expert,
    )


def _is_relevant_artifact(row: sqlite3.Row, expert: ExpertType, user_message: str) -> bool:
    owner = row["owner_expert_type"]
    source_agent = row["source_agent_id"]
    text = f"{row['title']} {row['kind']} {source_agent} {user_message}".lower()
    if expert == ExpertType.PROBLEM_GUIDE:
        return owner in {None, "", "problem_guide"} or row["kind"] == "DOCUMENT"
    if expert == ExpertType.SMART_ENGINEER:
        return owner in {"problem_guide", "smart_engineer"} or source_agent in {
            "spec-agent",
            "code-agent",
            "deploy-agent",
        } or _contains_expert_keyword(text, expert)
    if expert == ExpertType.STRUCTURE_ENGINEER:
        return (
            owner in {"smart_engineer", "structure_engineer"}
            or source_agent == "cad-agent"
            or _contains_expert_keyword(text, expert)
        )
    return False


def _contains_expert_keyword(text: str, expert: ExpertType) -> bool:
    lowered = text.lower()
    keywords = {
        ExpertType.SMART_ENGINEER: (
            "hardware",
            "firmware",
            "code",
            "bom",
            "io",
            "wiring",
            "device",
            "sensor",
            "硬件",
            "代码",
            "接线",
            "传感器",
            "设备",
        ),
        ExpertType.STRUCTURE_ENGINEER: (
            "structure",
            "cad",
            "stl",
            "step",
            "print",
            "mount",
            "结构",
            "外壳",
            "支架",
            "打印",
            "装配",
        ),
    }.get(expert, ())
    return any(keyword in lowered for keyword in keywords)


def _cad_capability(expert: ExpertType) -> dict[str, Any] | None:
    if expert != ExpertType.STRUCTURE_ENGINEER:
        return None
    allowed_templates = []
    for template_kind in (
        CadTemplateKind.BOX_WITH_LID,
        CadTemplateKind.COMPONENT_MOUNT,
        CadTemplateKind.FREEFORM_STRUCTURE,
        CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM,
    ):
        parameters = []
        for spec in production_template_parameter_specs(template_kind):
            definition: dict[str, Any] = {
                "name": spec.name,
                "label": spec.label,
                "unit": spec.unit,
                "default": spec.default,
                "minimum": spec.minimum,
                "maximum": spec.maximum,
            }
            if spec.allowed_values:
                definition["allowedValues"] = list(spec.allowed_values)
            parameters.append(definition)
        allowed_constraints: dict[str, object] = {"process": ["FDM"]}
        if template_kind is CadTemplateKind.BOX_WITH_LID:
            allowed_constraints.update(
                {
                    "minWallThicknessMm": {"minimum": 0.8, "maximum": 6.0},
                    "hardwareGapMm": {"minimum": 0.0, "maximum": 30.0},
                    "edgeClearanceMm": {"minimum": 0.0, "maximum": 40.0},
                }
            )
        allowed_templates.append(
            {
                "templateKind": template_kind.value,
                "parameters": parameters,
                "allowedConstraints": allowed_constraints,
                "componentCount": (
                    1
                    if template_kind is CadTemplateKind.COMPONENT_MOUNT
                    else 0
                    if template_kind in {
                        CadTemplateKind.FREEFORM_STRUCTURE,
                        CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM,
                    }
                    else "0..32"
                ),
                **(
                    {
                        "templateRevision": SUPPORTED_TEMPLATE_REVISIONS[template_kind],
                        "fixedGeometry": True,
                        "interaction": "stage_spec_then_final_build",
                    }
                    if template_kind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM
                    else {}
                ),
                **(
                    {
                        "declarativeGeometry": {
                            "maxPrimitives": 32,
                            "kinds": ["box", "rounded_box", "cylinder"],
                            "operations": ["add", "cut"],
                            "rotationZDeg": [0, 90, 180, 270],
                            "units": "mm",
                            "singleConnectedSolid": True,
                        }
                    }
                    if template_kind is CadTemplateKind.FREEFORM_STRUCTURE
                    else {}
                ),
            }
        )
    return {
        "engine": "cadquery-deterministic",
        "templateRevisionOwnedBy": "local_runtime",
        "allowedTemplates": allowed_templates,
        "requestedOutputs": [item.value for item in CadOutputRole],
        "rules": [
            "Only declarative numeric parameters are accepted.",
            "Components must reference an entry from mechanicalProfiles exactly.",
            "FREEFORM_STRUCTURE uses bounded declarative geometry and must not include components.",
            "UNIHIKER_K10_PHOTO_ALBUM uses fixed local geometry and accepts no parameters, components, or provider geometry.",
            "Do not provide code, commands, paths, URLs, environment variables, or IDs owned by the local runtime.",
        ],
    }


def _confirmed_bom_component_ids(
    conn: sqlite3.Connection,
    project_id: str,
) -> list[str]:
    row = conn.execute(
        """
        SELECT sf.content
        FROM spec_runs sr
        JOIN spec_files sf ON sf.spec_run_id = sr.id
        WHERE sr.project_id = ?
          AND sr.status = 'APPROVED'
          AND sr.confirmed_at IS NOT NULL
          AND sf.kind = 'BOM'
        ORDER BY sr.version DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return []
    try:
        payload = yaml.safe_load(str(row["content"]))
    except yaml.YAMLError:
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("components"), list):
        return []
    component_ids: list[str] = []
    for item in payload["components"]:
        if not isinstance(item, dict):
            continue
        component_id = item.get("id")
        if (
            isinstance(component_id, str)
            and component_id
            and component_id not in component_ids
        ):
            component_ids.append(component_id)
    return component_ids[:32]


def _preferred_hardware_component_ids(
    conn: sqlite3.Connection,
    project_id: str,
) -> list[str]:
    component_ids, _validation = _preferred_hardware_selection(conn, project_id)
    return component_ids


def _preferred_hardware_selection(
    conn: sqlite3.Connection,
    project_id: str,
) -> tuple[list[str], dict[str, Any] | None]:
    row = conn.execute(
        """
        SELECT value_json
        FROM project_shared_facts
        WHERE project_id = ?
          AND field = 'preferred_hardware'
          AND status = 'confirmed'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return [], None
    payload = _load_json(row["value_json"])
    if not isinstance(payload, dict) or not isinstance(payload.get("components"), list):
        return [], None
    component_ids: list[str] = []
    for item in payload["components"]:
        if not isinstance(item, dict):
            continue
        component_id = item.get("id") or item.get("componentId")
        if isinstance(component_id, str) and component_id:
            component_ids.append(component_id)
    return (
        _dedupe_component_ids(component_ids)[:12],
        _controlled_hardware_validation(payload.get("validation")),
    )


def _controlled_hardware_validation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    overall = value.get("overall")
    message = value.get("message")
    if overall not in {"PASS", "WARNING"} or not isinstance(message, str):
        return None
    warnings: list[dict[str, str]] = []
    raw_warnings = value.get("warnings")
    if isinstance(raw_warnings, list):
        for item in raw_warnings[:12]:
            if not isinstance(item, dict):
                continue
            dimension = item.get("dimension")
            warning_message = item.get("message")
            details = item.get("details")
            if not all(
                isinstance(field, str)
                for field in (dimension, warning_message, details)
            ):
                continue
            warnings.append(
                {
                    "dimension": dimension[:80],
                    "message": warning_message[:240],
                    "details": details[:500],
                }
            )
    return {
        "overall": overall,
        "message": message[:240],
        "warnings": warnings,
    }


def _current_hardware_validation(validation: ValidationResult) -> dict[str, Any]:
    return {
        "overall": validation.overall.value,
        "message": validation.message[:240],
        "warnings": [
            {
                "dimension": check.dimension[:80],
                "message": check.message[:240],
                "details": check.details[:500],
            }
            for check in validation.checks
            if check.severity == ValidationSeverity.WARNING
        ][:12],
    }


def _dedupe_component_ids(component_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for component_id in component_ids:
        if component_id in seen:
            continue
        seen.add(component_id)
        result.append(component_id)
    return result


def _hardware_knowledge_score(
    component: HardwareComponent,
    query: str,
    *,
    skill_text: str = "",
) -> int:
    terms = _hardware_query_terms(query)
    if not terms:
        return 0
    name = component.name.lower()
    notes = component.notes.lower()
    safety = " ".join(component.safetyTags).lower()
    electrical = json.dumps(
        component.electrical.model_dump(mode="json"),
        ensure_ascii=False,
    ).lower()
    skill_knowledge = skill_text.lower()
    score = 0
    for term in terms:
        if term in name:
            score += 8
        elif term in notes:
            score += 4
        elif term in safety:
            score += 3
        elif term in electrical:
            score += 2
        elif term in skill_knowledge:
            score += 4
    return score


def _hardware_query_terms(query: str) -> set[str]:
    normalized = query.lower()[:1000]
    terms = {
        match.group(0)
        for match in re.finditer(r"[a-z0-9][a-z0-9.+_-]{1,31}", normalized)
    }
    terms.update(keyword for keyword in _HARDWARE_QUERY_KEYWORDS if keyword in normalized)
    for trigger, expanded_terms in _HARDWARE_QUERY_EXPANSIONS.items():
        if trigger in normalized:
            terms.update(expanded_terms)
    return terms


def _hardware_public_knowledge(
    component: HardwareComponent,
    *,
    source: str = "local_hardware_library",
    selected_by_user: bool = False,
) -> dict[str, Any]:
    electrical = component.electrical
    payload: dict[str, Any] = {
        "source": source,
        "componentId": component.id,
        "skillName": component.skillName,
        "skillRevision": component.skillRevision,
        "name": component.name,
        "category": component.category.value,
        "electrical": {
            "voltage": electrical.voltage,
            "logicLevel": electrical.logicLevel,
            "peakCurrent": electrical.peakCurrent,
            "communicationProtocol": electrical.communicationProtocol,
            "i2cAddress": electrical.i2cAddress,
            "supportedMCUs": electrical.supportedMCUs[:6],
            "driverName": electrical.driverName,
            "firmwareRequirement": electrical.firmwareRequirement,
        },
        "safetyTags": component.safetyTags[:6],
        "notes": " ".join(component.notes.split())[:240],
    }
    if selected_by_user:
        payload["selectedByUser"] = True
    return payload


def _hardware_knowledge_policy(
    public_knowledge: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = [
        _hardware_policy_component(item)
        for item in public_knowledge
        if item.get("source") == "preferred_project_hardware"
    ]
    active_library = [
        _hardware_policy_component(item)
        for item in public_knowledge
        if item.get("source") == "local_hardware_library"
    ]
    return {
        "priorityOrder": [
            "preferred_project_hardware",
            "local_hardware_library",
            "missing_capability",
        ],
        "selectedComponents": selected,
        "activeLibraryComponents": active_library,
        "rule": (
            "硬件推理必须先复用项目已选器件；未选择时先评估本地 ACTIVE 硬件库。"
            "只有二者无法覆盖的能力才能声明为缺口，不得静默替换已选主控或绕开本地库。"
        ),
    }


def _hardware_policy_component(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item[key]
        for key in (
            "componentId",
            "name",
            "category",
            "skillName",
            "skillRevision",
            "source",
        )
        if item.get(key) is not None
    }


def _board_profile_public_knowledge(profile: BoardProfile) -> dict[str, Any]:
    return {
        "source": "markdown_board_profile",
        "profileId": profile.id,
        "name": profile.displayName,
        "aliases": profile.aliases,
        "platform": profile.platform,
        "language": profile.language,
        "revision": profile.revision,
        "markdown": profile.content[:12_000],
        "truncated": len(profile.content) > 12_000,
    }


def _effective_board_query(current_query: str, fallback_query: str) -> str:
    """Keep an established K10 project unless this turn names another board."""
    normalized = current_query.lower()
    if any(marker in normalized for marker in _K10_MARKERS):
        return current_query
    if any(marker in normalized for marker in _OTHER_BOARD_MARKERS):
        return current_query
    if fallback_query.strip():
        return f"{current_query}\n{fallback_query}".strip()
    return current_query


def _searchable_text(data: dict[str, Any], user_message: str) -> str:
    return f"{json.dumps(data, ensure_ascii=False)} {user_message}"


def _fact_priority(item: dict[str, Any]) -> tuple[int, int, str]:
    confirmed_rank = 0 if item.get("status") == SharedFactStatus.CONFIRMED.value else 1
    model_summary_rank = 1 if item.get("sourceType") == "model_summary" else 0
    return (confirmed_rank, model_summary_rank, str(item.get("updatedAt") or ""))


def _dedupe_by_id(items: Any) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("id") or "")
        if item_id and item_id in seen:
            continue
        if item_id:
            seen.add(item_id)
        result.append(item)
    return result


def _load_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _load_json_array(value: str | None) -> list[Any]:
    loaded = _load_json(value)
    return loaded if isinstance(loaded, list) else []
