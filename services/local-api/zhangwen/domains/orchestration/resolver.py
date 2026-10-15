"""Resolve existing Agent/Skill facts into immutable execution bindings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zhangwen.domains.orchestration.models import (
    ExecutionRevisionBinding,
    InternalUnit,
    PackageKind,
)
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.experts.packages import AgentPackageRepository
from zhangwen.projects.models import ExpertType
from zhangwen.skills.repository import SkillRepository


_UNIT_EXPERTS: dict[InternalUnit, ExpertType] = {
    InternalUnit.DISCOVERY_ROLE: ExpertType.PROBLEM_GUIDE,
    InternalUnit.ENGINEERING_ROLE: ExpertType.SMART_ENGINEER,
    InternalUnit.STRUCTURE_ROLE: ExpertType.STRUCTURE_ENGINEER,
}


class RevisionResolutionError(RuntimeError):
    """A configured internal unit cannot be pinned safely."""


@dataclass(frozen=True)
class ResolvedUnitRevision:
    unit: InternalUnit
    agent_binding: ExecutionRevisionBinding
    skill_bindings: tuple[ExecutionRevisionBinding, ...]

    @property
    def bindings(self) -> tuple[ExecutionRevisionBinding, ...]:
        return (self.agent_binding, *self.skill_bindings)


class CapabilityRevisionResolver:
    """Adapter over current package stores; it creates no parallel registry."""

    def __init__(self, data_dir: Path, db_path: Path) -> None:
        self._agents = AgentPackageRepository(data_dir)
        self._skills = SkillRepository(db_path)
        self._packages = PackagePlatformRepository(data_dir)

    def resolve(self, units: list[InternalUnit]) -> list[ResolvedUnitRevision]:
        self._packages.ensure_legacy_packages()
        skills = {skill.id: skill for skill in self._skills.list_skills()}
        resolved: list[ResolvedUnitRevision] = []
        for unit in units:
            expert = _UNIT_EXPERTS[unit]
            package = self._agents.get_package(expert)
            agent_binding = ExecutionRevisionBinding(
                packageKind=PackageKind.AGENT_PACKAGE,
                packageId=f"agent-package:{package.skillName}",
                packageRevisionId=self._packages.stable_revision(
                    f"agent-package:{package.skillName}"
                ).id,
            )
            skill_bindings: list[ExecutionRevisionBinding] = []
            for skill_id in package.skillIds:
                skill = skills.get(skill_id)
                if skill is None or not skill.enabled:
                    raise RevisionResolutionError(
                        f"Internal unit {unit.value} has an unavailable configured skill"
                    )
                skill_package_id = f"skill-package:{skill.id}"
                skill_bindings.append(
                    ExecutionRevisionBinding(
                        packageKind=PackageKind.SKILL_PACKAGE,
                        packageId=skill_package_id,
                        packageRevisionId=self._packages.stable_revision(
                            skill_package_id
                        ).id,
                    )
                )
            resolved.append(
                ResolvedUnitRevision(
                    unit=unit,
                    agent_binding=agent_binding,
                    skill_bindings=tuple(skill_bindings),
                )
            )
        return resolved
