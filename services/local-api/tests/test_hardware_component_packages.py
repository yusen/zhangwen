"""Safe hardware component Markdown package repository and API tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from zhangwen.config import settings
from zhangwen.hardware.component_packages import (
    ALLOWED_PACKAGE_PATHS,
    MAX_CONTEXT_CHARS,
    HardwareComponentPackageConflictError,
    HardwareComponentPackageRepository,
    HardwareComponentPackageValidationError,
)
from zhangwen.hardware.models import ElectricalProps, HardwareCategory
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


@pytest.fixture
def package_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    components = HardwareRepository(projects.db_path)
    component = components.create_component(
        name="BME280 环境传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=ElectricalProps(
            voltage=3.3,
            logicLevel=3.3,
            peakCurrent=0.001,
            communicationProtocol="I2C",
            i2cAddress="0x76",
            supportedMCUs=["esp32-s3", "rp2040"],
            driverName="bme280",
            firmwareRequirement="MicroPython 1.22+",
        ),
        stock=4,
        price=19.9,
        age_recommendation=10,
        safety_tags=["仅限 3.3V 逻辑", "注意防反接"],
        notes="安装时为传感器保留通风空间。",
    )
    return tmp_path, components, component


def test_component_package_defaults_follow_authoritative_component_fields(
    package_environment,
) -> None:
    data_dir, components, component = package_environment
    repository = HardwareComponentPackageRepository(data_dir, components)

    package = repository.get_package(component.id)

    assert [file.path for file in package.files] == [
        "README.md",
        "docs/specifications.md",
        "docs/integration.md",
        "docs/safety.md",
    ]
    assert {file.path for file in package.files} == set(ALLOWED_PACKAGE_PATHS)
    assert [file.kind for file in package.files] == [
        "entry",
        "reference",
        "reference",
        "reference",
    ]
    assert all(file.overridden is False for file in package.files)
    readme = next(file.content for file in package.files if file.path == "README.md")
    specifications = next(
        file.content
        for file in package.files
        if file.path == "docs/specifications.md"
    )
    safety = next(
        file.content for file in package.files if file.path == "docs/safety.md"
    )
    assert component.name in readme
    assert "库存：4" in readme
    assert "I2C 地址：0x76" in specifications
    assert "esp32-s3" in specifications
    assert "注意防反接" in safety
    assert len(package.revision) == 24
    assert not (data_dir / "hardware-component-packages").exists()

    components.update_component(component.id, stock=9, notes="更新后的结构化备注。")
    refreshed = repository.get_package(component.id)
    assert refreshed.revision != package.revision
    assert "库存：9" in next(
        file.content for file in refreshed.files if file.path == "README.md"
    )
    assert "更新后的结构化备注" in next(
        file.content for file in refreshed.files if file.path == "README.md"
    )


def test_component_package_update_is_atomic_persistent_and_package_scoped(
    package_environment,
) -> None:
    data_dir, components, component = package_environment
    repository = HardwareComponentPackageRepository(data_dir, components)
    original = repository.get_package(component.id)
    custom_readme = "# 自定义器件说明\n\n只保存已确认的工程知识。\r\n"

    updated = repository.update_file(
        component.id,
        path="README.md",
        content=custom_readme,
        expected_revision=original.revision,
    )

    assert updated.revision != original.revision
    updated_readme = next(
        file for file in updated.files if file.path == "README.md"
    )
    assert updated_readme.content == custom_readme.replace("\r\n", "\n")
    assert updated_readme.overridden is True
    assert all(
        file.overridden is False
        for file in updated.files
        if file.path != "README.md"
    )
    persisted = HardwareComponentPackageRepository(
        data_dir,
        components,
    ).get_package(component.id)
    assert persisted == updated

    overlay_root = data_dir / "hardware-component-packages" / component.id
    assert sorted(
        file.relative_to(overlay_root).as_posix()
        for file in overlay_root.rglob("*")
        if file.is_file()
    ) == ["README.md"]
    assert not list(overlay_root.rglob("*.tmp"))

    with pytest.raises(HardwareComponentPackageConflictError):
        repository.update_file(
            component.id,
            path="docs/integration.md",
            content="# 不应覆盖\n",
            expected_revision=original.revision,
        )

    second = repository.update_file(
        component.id,
        path="docs/integration.md",
        content="# 已确认集成说明\n",
        expected_revision=updated.revision,
    )
    assert second.revision != updated.revision
    assert next(
        file for file in second.files if file.path == "docs/integration.md"
    ).overridden is True


def test_component_package_context_is_validated_and_bounded(
    package_environment,
) -> None:
    data_dir, components, component = package_environment
    repository = HardwareComponentPackageRepository(data_dir, components)

    context = repository.render_context(component.id, max_chars=600)

    assert len(context) <= 600
    assert "器件知识包：BME280 环境传感器" in context
    assert "README.md" in context
    assert str(data_dir) not in context
    with pytest.raises(HardwareComponentPackageValidationError):
        repository.render_context(component.id, max_chars=MAX_CONTEXT_CHARS + 1)


def test_component_package_rejects_corrupt_non_utf8_overlay(
    package_environment,
) -> None:
    data_dir, components, component = package_environment
    repository = HardwareComponentPackageRepository(data_dir, components)
    original = repository.get_package(component.id)
    repository.update_file(
        component.id,
        path="README.md",
        content="# 有效 UTF-8 Markdown\n",
        expected_revision=original.revision,
    )
    overlay = (
        data_dir
        / "hardware-component-packages"
        / component.id
        / "README.md"
    )
    overlay.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(
        HardwareComponentPackageValidationError,
        match="不是有效 UTF-8 Markdown",
    ):
        repository.get_package(component.id)
    with pytest.raises(HardwareComponentPackageValidationError):
        repository.render_context(component.id)


def test_component_package_api_is_a_read_only_view_of_the_canonical_skill(
    package_environment,
) -> None:
    _, _, component = package_environment
    client = TestClient(app)

    detail = client.get(f"/api/hardware/components/{component.id}/package")
    assert detail.status_code == 200
    package = detail.json()["package"]
    assert package["componentId"] == component.id
    assert len(package["files"]) == 4
    assert package["revision"] == component.skillRevision
    files = {file["path"]: file["content"] for file in package["files"]}
    assert files["README.md"].startswith("---\nname:")
    assert "zhangwen:hardware-spec:v1" in files["docs/specifications.md"]

    write = client.put(
        f"/api/hardware/components/{component.id}/package/files",
        json={
            "path": "docs/safety.md",
            "content": "# 项目安全说明\n\n不得使用 5V 逻辑。\n",
            "expectedRevision": package["revision"],
        },
    )
    assert write.status_code == 410
    assert write.json()["detail"] == {
        "code": "HARDWARE_COMPONENT_PACKAGE_READ_ONLY",
        "message": "旧器件 Markdown 接口已改为只读，请使用 Hardware Skill 项目编辑器。",
        "retryable": False,
    }
    client.close()


def test_component_package_api_rejects_missing_and_archived_components(
    package_environment,
) -> None:
    _, components, component = package_environment
    client = TestClient(app)

    missing = client.get("/api/hardware/components/hw_missing/package")
    assert missing.status_code == 404
    assert (
        missing.json()["detail"]["code"]
        == "HARDWARE_COMPONENT_PACKAGE_NOT_FOUND"
    )

    before_archive = client.get(
        f"/api/hardware/components/{component.id}/package"
    ).json()["package"]
    components.archive_component(component.id)
    archived_read = client.get(
        f"/api/hardware/components/{component.id}/package"
    )
    archived_write = client.put(
        f"/api/hardware/components/{component.id}/package/files",
        json={
            "path": "README.md",
            "content": "# 不允许保存\n",
            "expectedRevision": before_archive["revision"],
        },
    )
    assert archived_read.status_code == 404
    assert archived_write.status_code == 410
    assert archived_write.json()["detail"]["code"] == "HARDWARE_COMPONENT_PACKAGE_READ_ONLY"
    client.close()
