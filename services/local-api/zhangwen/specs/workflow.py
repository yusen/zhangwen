"""Shared formal-project Spec generation workflow.

The HTTP route and the problem-guide confirmation flow use the same local
hardware validation, Provider boundary, deterministic packaging, and
persistence path.  This module never executes generated code or touches a
device.
"""

from __future__ import annotations

import json

from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.models import ValidationSeverity
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.llm.contracts import (
    ChatProgressEmitter,
    LLMConfig,
    LLMModelId,
)
from zhangwen.llm.gateway import LLMProvider
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalVersion
from zhangwen.specs.generator import generate_spec_from_proposal
from zhangwen.specs.models import SpecRun
from zhangwen.specs.repository import SpecRepository
from zhangwen.specs.service import SpecGenerationService


class FormalSpecHardwareError(ValueError):
    """The project's selected hardware cannot enter a formal Spec."""


async def generate_formal_project_spec(
    *,
    repo: ProjectRepository,
    project_id: str,
    proposal: ProposalVersion,
    provider: LLMProvider,
    config: LLMConfig,
    api_key: str,
    model: LLMModelId,
    progress_emitter: ChatProgressEmitter | None = None,
) -> SpecRun:
    """Generate and persist one validated Spec for an approved proposal."""

    seed_default_components(repo.db_path)
    hardware_skills = HardwareSkillRepository(repo.data_dir, repo.db_path)
    hardware_skills.migrate_legacy_rows()
    preferred_hardware_ids = preferred_hardware_component_ids(repo, project_id)
    if preferred_hardware_ids:
        for component_id in preferred_hardware_ids:
            hardware_skills.get_active_component(component_id)
        preferred_validation = hardware_skills.validate_component_ids(
            preferred_hardware_ids
        )
        if preferred_validation.overall == ValidationSeverity.FAIL:
            raise FormalSpecHardwareError(
                "项目已选硬件的当前 Skill revision 未通过校验，请先修正硬件库。"
            )
    components = hardware_skills.list_active_components()
    draft = await SpecGenerationService(provider).generate(
        proposal=proposal,
        hardware_components=components,
        config=config,
        api_key=api_key,
        model=model,
        progress_emitter=progress_emitter,
    )
    generated = generate_spec_from_proposal(
        proposal,
        components,
        draft,
        validate_hardware=hardware_skills.validate_component_ids,
    )
    return SpecRepository(repo.db_path).create_from_generated(
        project_id=project_id,
        proposal=proposal,
        generated=generated,
    )


def preferred_hardware_component_ids(
    repo: ProjectRepository,
    project_id: str,
) -> list[str]:
    with repo._connect() as conn:
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
        return []
    try:
        payload = json.loads(str(row["value_json"]))
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("components"), list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in payload["components"]:
        if not isinstance(item, dict):
            continue
        component_id = item.get("id") or item.get("componentId")
        if (
            not isinstance(component_id, str)
            or not component_id
            or component_id in seen
        ):
            continue
        seen.add(component_id)
        result.append(component_id)
    return result[:12]
