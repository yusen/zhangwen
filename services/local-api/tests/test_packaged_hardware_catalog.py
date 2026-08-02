"""Packaged hardware catalog installation boundaries."""

from __future__ import annotations

from pathlib import Path

from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareSkillSpecification,
)
from zhangwen.projects.repository import ProjectRepository


def _create_source_catalog(source_dir: Path) -> HardwareSkillRepository:
    projects = ProjectRepository(source_dir)
    skills = HardwareSkillRepository(source_dir, projects.db_path)
    skills.create_skill(
        HardwareSkillSpecification(
            componentId="hw_packaged_test",
            name="Packaged test board",
            category=HardwareCategory.MCU,
            electrical=ElectricalProps(
                voltage=3.3,
                logicLevel=3.3,
                peakCurrent=0.2,
                communicationProtocol="USB",
                supportedMCUs=["esp32-s3"],
            ),
            verificationStatus="PACKAGE_TEST_VERIFIED",
            sourceIds=["test:packaged-catalog"],
        ),
        skill_name="packaged-test-board",
        description="A validated packaged catalog fixture.",
    )
    return skills


def test_bundled_catalog_installs_missing_packages_and_projects_sqlite(
    tmp_path: Path,
) -> None:
    source = _create_source_catalog(tmp_path / "source")
    target_dir = tmp_path / "target"
    target_projects = ProjectRepository(target_dir)
    target = HardwareSkillRepository(target_dir, target_projects.db_path)

    result = target.install_bundled_catalog(source.root)
    component = target.get_active_component("hw_packaged_test")

    assert result.installed == 1
    assert result.preserved == 0
    assert component.name == "Packaged test board"
    assert (target.root / "packaged-test-board" / "manifest.json").is_file()


def test_bundled_catalog_never_overwrites_same_name_user_package(
    tmp_path: Path,
) -> None:
    source = _create_source_catalog(tmp_path / "source")
    target_dir = tmp_path / "target"
    target_projects = ProjectRepository(target_dir)
    target = HardwareSkillRepository(target_dir, target_projects.db_path)
    target.install_bundled_catalog(source.root)
    current = target.get_skill("packaged-test-board")
    integration = next(
        item for item in current.files if item.path == "references/integration.md"
    )
    user_marker = "USER_OWNED_PACKAGE_MUST_BE_PRESERVED"
    changed = target.update_file(
        current.skillName,
        path=integration.path,
        content=f"{integration.content.rstrip()}\n\n{user_marker}\n",
        expected_revision=current.revision,
    )

    result = target.install_bundled_catalog(source.root)
    preserved = target.get_skill(current.skillName)

    assert result.installed == 0
    assert result.preserved == 1
    assert preserved.revision == changed.revision
    assert user_marker in next(
        item.content for item in preserved.files if item.path == integration.path
    )
