"""Three-teacher runtime configuration and prompt loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from zhangwen.projects.models import ExpertType
from zhangwen.experts.packages import (
    BUNDLED_AGENT_PACKAGE_DIR,
    bundled_agent_manifests,
    parse_skill_frontmatter,
)


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


class ExpertRuntimeConfig(BaseModel):
    id: ExpertType
    displayName: str
    description: str
    promptKey: str
    visible: bool = True
    artifactTypes: list[str] = Field(default_factory=list)
    skillIds: list[str] = Field(default_factory=list)
    capabilityBoundaries: list[str] = Field(default_factory=list)


def _load_runtime_configs() -> dict[ExpertType, ExpertRuntimeConfig]:
    configs: dict[ExpertType, ExpertRuntimeConfig] = {}
    for manifest in bundled_agent_manifests():
        entry_path = BUNDLED_AGENT_PACKAGE_DIR / manifest.skillName / "SKILL.md"
        metadata = parse_skill_frontmatter(entry_path.read_text(encoding="utf-8"))
        configs[manifest.expertType] = ExpertRuntimeConfig(
            id=manifest.expertType,
            displayName=manifest.displayName,
            description=metadata["description"],
            promptKey=manifest.skillName,
            artifactTypes=manifest.supportedArtifactTypes,
            skillIds=manifest.skillIds,
            capabilityBoundaries=manifest.capabilityBoundaries,
        )
    return configs


EXPERT_RUNTIME_CONFIGS = _load_runtime_configs()
PROBLEM_GUIDE_SKILLS = EXPERT_RUNTIME_CONFIGS[ExpertType.PROBLEM_GUIDE].skillIds
SMART_ENGINEER_SKILLS = EXPERT_RUNTIME_CONFIGS[ExpertType.SMART_ENGINEER].skillIds
STRUCTURE_ENGINEER_SKILLS = EXPERT_RUNTIME_CONFIGS[ExpertType.STRUCTURE_ENGINEER].skillIds

INVISIBLE_RUNTIME_PROMPTS = {
    "entry_router": "entry-router",
    "project_coordinator": "project-coordinator",
}


def list_expert_configs() -> list[ExpertRuntimeConfig]:
    return [EXPERT_RUNTIME_CONFIGS[key] for key in _VISIBLE_EXPERT_ORDER]


def get_expert_config(expert_type: ExpertType) -> ExpertRuntimeConfig:
    canonical = canonical_expert_type(expert_type)
    return EXPERT_RUNTIME_CONFIGS[canonical]


def canonical_expert_type(expert_type: ExpertType | str) -> ExpertType:
    value = expert_type.value if isinstance(expert_type, ExpertType) else str(expert_type)
    mapping = {
        ExpertType.QUESTION_GUIDE.value: ExpertType.PROBLEM_GUIDE,
        ExpertType.INTELLIGENT_ENGINEER.value: ExpertType.SMART_ENGINEER,
        ExpertType.IDEATOR.value: ExpertType.PROBLEM_GUIDE,
        ExpertType.EDUCATOR.value: ExpertType.PROBLEM_GUIDE,
        ExpertType.OPEN_HARDWARE_DESIGNER.value: ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_DESIGNER.value: ExpertType.STRUCTURE_ENGINEER,
        ExpertType.THREE_D_STRUCTURE_DESIGNER.value: ExpertType.STRUCTURE_ENGINEER,
    }
    return mapping.get(value, ExpertType(value))


@lru_cache(maxsize=None)
def load_prompt(prompt_key: str) -> str:
    path = PROMPT_DIR / f"{prompt_key}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_expert_prompt(
    expert_type: ExpertType | str,
    *,
    user_message: str = "",
    data_dir: Path | None = None,
) -> str:
    from zhangwen.config import settings
    from zhangwen.experts.packages import AgentPackageRepository

    return AgentPackageRepository(data_dir or settings.data_dir).render_prompt(
        canonical_expert_type(expert_type),
        user_message=user_message,
    )


_VISIBLE_EXPERT_ORDER = [
    ExpertType.PROBLEM_GUIDE,
    ExpertType.SMART_ENGINEER,
    ExpertType.STRUCTURE_ENGINEER,
]
