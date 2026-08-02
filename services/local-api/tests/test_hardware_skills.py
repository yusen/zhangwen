"""Hardware Skill canonical package, draft lifecycle, and rule tests."""

from __future__ import annotations

import base64
import io
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from zhangwen.config import settings
from zhangwen.hardware import hardware_skills as hardware_skills_module
from zhangwen.hardware.hardware_skills import (
    HARDWARE_SKILL_PATHS,
    HardwareSkillConflictError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
    _validate_text_boundary,
)
from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareSkillSpecification,
)
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.hardware.rule_engine import validate_components
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


@pytest.fixture
def skill_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    components = HardwareRepository(projects.db_path, data_dir=tmp_path)
    skills = HardwareSkillRepository(tmp_path, projects.db_path)
    return tmp_path, projects.db_path, components, skills


def _electrical(**overrides: object) -> ElectricalProps:
    values: dict[str, object] = {
        "voltage": 3.3,
        "logicLevel": 3.3,
        "peakCurrent": 0.02,
        "communicationProtocol": "I2C",
        "i2cAddress": "0x40",
        "supportedMCUs": ["esp32-s3"],
        "driverName": "sample",
        "firmwareRequirement": None,
    }
    values.update(overrides)
    return ElectricalProps(**values)


@pytest.mark.parametrize(
    "content",
    [
        "MQTTClient(user=None, password=None)",
        "password = null",
        "api_key = <YOUR_API_KEY>",
        "access_token=${ACCESS_TOKEN}",
        'secret = ""',
    ],
)
def test_hardware_skill_secret_scan_allows_documented_placeholders(
    content: str,
) -> None:
    _validate_text_boundary(content, "references/integration.md")


@pytest.mark.parametrize(
    "content",
    [
        "password=real-home-password-123",
        "api_key=sk-secret-value",
        "access_token=actual-token-value",
        "wifi_password=maker-lab-password",
    ],
)
def test_hardware_skill_secret_scan_still_rejects_concrete_values(
    content: str,
) -> None:
    with pytest.raises(HardwareSkillValidationError, match="敏感"):
        _validate_text_boundary(content, "references/integration.md")


def test_legacy_rows_migrate_and_markdown_remains_authoritative(
    skill_environment,
) -> None:
    data_dir, db_path, components, skills = skill_environment
    component = components.create_component(
        name="测试传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
        stock=2,
        notes="初始说明",
    )

    detail = skills.get_active_by_component_id(component.id)
    skill_root = data_dir / "hardware-skills" / detail.skillName
    assert {
        file.relative_to(skill_root).as_posix()
        for file in skill_root.rglob("*")
        if file.is_file()
    } == {"manifest.json", *HARDWARE_SKILL_PATHS}
    assert detail.specification.electrical.voltage == 3.3

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE hardware_components SET electrical_json = ? WHERE id = ?",
            (json.dumps({**component.electrical.model_dump(), "voltage": 99.0}), component.id),
        )

    assert components.get_component(component.id).electrical.voltage == 3.3

    spec_file = next(
        file
        for file in detail.files
        if file.path == "references/specifications.md"
    )
    changed = spec_file.content.replace('"voltage": 3.3', '"voltage": 5.0')
    updated = skills.update_file(
        detail.skillName,
        path=spec_file.path,
        content=changed,
        expected_revision=detail.revision,
    )
    assert updated.specification.electrical.voltage == 5.0
    assert components.get_component(component.id).electrical.voltage == 5.0
    with sqlite3.connect(db_path) as conn:
        projected = json.loads(
            conn.execute(
                "SELECT electrical_json FROM hardware_components WHERE id = ?",
                (component.id,),
            ).fetchone()[0]
        )
    assert projected["voltage"] == 5.0


def test_skill_batch_update_is_atomic_and_syncs_projection_once(
    skill_environment,
) -> None:
    _, db_path, components, skills = skill_environment
    component = components.create_component(
        name="批量资料传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
        notes="旧说明",
    )
    detail = skills.get_active_by_component_id(component.id)
    files = {file.path: file.content for file in detail.files}
    changed_skill = files["SKILL.md"].replace("旧说明", "新的完整资料")
    changed_spec = files["references/specifications.md"].replace(
        '"voltage": 3.3',
        '"voltage": 5.0',
    )

    client = TestClient(app)
    response = client.put(
        f"/api/hardware/skills/{detail.skillName}/files/batch",
        json={
            "expectedRevision": detail.revision,
            "updates": [
                {"path": "SKILL.md", "content": changed_skill},
                {
                    "path": "references/specifications.md",
                    "content": changed_spec,
                },
            ],
        },
    )
    assert response.status_code == 200
    updated = response.json()["skill"]
    assert updated["revision"] != detail.revision
    assert updated["description"] == "新的完整资料"
    assert updated["specification"]["electrical"]["voltage"] == 5.0
    with sqlite3.connect(db_path) as conn:
        projected = json.loads(
            conn.execute(
                "SELECT electrical_json FROM hardware_components WHERE id = ?",
                (component.id,),
            ).fetchone()[0]
        )
    assert projected["voltage"] == 5.0

    updated_files = {file["path"]: file["content"] for file in updated["files"]}
    invalid_rules = updated_files["references/compatibility-rules.md"].replace(
        '"operator": "range-overlap"',
        '"operator": "python-eval"',
        1,
    )
    failed = client.put(
        f"/api/hardware/skills/{detail.skillName}/files/batch",
        json={
            "expectedRevision": updated["revision"],
            "updates": [
                {
                    "path": "references/integration.md",
                    "content": updated_files["references/integration.md"]
                    + "\n\n这段内容不应部分落盘。\n",
                },
                {
                    "path": "references/compatibility-rules.md",
                    "content": invalid_rules,
                },
            ],
        },
    )
    assert failed.status_code == 422
    unchanged = skills.get_skill(detail.skillName)
    assert unchanged.revision == updated["revision"]
    assert "这段内容不应部分落盘" not in next(
        file.content
        for file in unchanged.files
        if file.path == "references/integration.md"
    )
    client.close()


def test_malformed_legacy_package_does_not_block_selecting_valid_active_skill(
    skill_environment,
) -> None:
    data_dir, _, repository, skills = skill_environment
    component = repository.create_component(
        name="可选温度传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
    )
    active = skills.get_active_by_component_id(component.id)

    malformed = data_dir / "hardware-skills" / "000-malformed-legacy"
    malformed.mkdir()
    (malformed / "manifest.json").write_text("{}\n", encoding="utf-8")

    selected = skills.get_active_by_component_id(component.id)

    assert selected.skillName == active.skillName
    assert selected.revision == active.revision
    assert component.id in {
        item.id for item in skills.list_active_components()
    }


def test_invalid_k10_package_does_not_block_valid_skill_catalog(
    skill_environment,
) -> None:
    data_dir, db_path, repository, skills = skill_environment
    component = repository.create_component(
        name="独立有效传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
    )
    valid = skills.get_active_by_component_id(component.id)
    seed_default_components(db_path)
    skills.migrate_legacy_rows()
    k10 = skills.get_active_by_component_id("hw_seed_unihiker_k10")
    manifest_path = data_dir / "hardware-skills" / k10.skillName / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["revision"] = "0" * 24
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    listed = skills.list_skills()

    listed_ids = {item.componentId for item in listed}
    assert valid.componentId in listed_ids
    assert k10.componentId not in listed_ids
    with pytest.raises(HardwareSkillValidationError, match="revision"):
        skills.get_skill(k10.skillName)


def test_obsolete_package_merges_valid_imported_content_into_active_successor(
    skill_environment,
) -> None:
    data_dir, _, repository, skills = skill_environment
    component = repository.create_component(
        name="资料迁移传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
    )
    active = skills.get_active_by_component_id(component.id)
    active_root = data_dir / "hardware-skills" / active.skillName
    imported_root = data_dir / "hardware-skills" / "legacy-rich-sensor"
    imported_root.mkdir()

    imported_files = {file.path: file.content for file in active.files}
    imported_files["SKILL.md"] = imported_files["SKILL.md"].replace(
        f"name: {active.skillName}",
        "name: legacy-rich-sensor",
    ).replace(
        f"description: {active.description}",
        "description: 已导入的完整器件资料",
    )
    imported_files["references/specifications.md"] = imported_files[
        "references/specifications.md"
    ].replace(
        '"verificationStatus": "USER_CONFIRMED"',
        '"verificationStatus": "OFFICIAL_DOC_VERIFIED"',
    )
    imported_files["references/compatibility-rules.md"] = imported_files[
        "references/compatibility-rules.md"
    ].replace(
        '"rules": [',
        '"rules": [\n'
        '    {"id": "manual-import-check", "operator": "required-if", '
        '"severity": "WARNING", "message": "导入资料中的扩展检查", '
        '"params": {"requiredField": "integration.extra", '
        '"ifField": "peripheral.voltage", "ifGreaterThan": 3.3}},',
        1,
    )
    for relative, content in imported_files.items():
        path = imported_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (imported_root / "README.md").write_text(
        "# 旧格式额外资料\n\n必须保留。\n",
        encoding="utf-8",
    )
    manifest = json.loads((active_root / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        {
            "skillName": "legacy-rich-sensor",
            "description": "已导入的完整器件资料",
            "files": [*HARDWARE_SKILL_PATHS, "README.md"],
        }
    )
    (imported_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    skills.migrate_legacy_rows()

    synchronized = skills.get_active_by_component_id(component.id)
    assert synchronized.skillName == active.skillName
    assert synchronized.description == "已导入的完整器件资料"
    assert synchronized.specification.verificationStatus == "OFFICIAL_DOC_VERIFIED"
    assert "manual-import-check" not in {rule.id for rule in synchronized.rules}
    synchronized_rules = next(
        file.content
        for file in synchronized.files
        if file.path == "references/compatibility-rules.md"
    )
    assert "manual-import-check" in synchronized_rules
    assert "已降级为人工检查项" in synchronized_rules
    assert (imported_root / "README.md").read_text(encoding="utf-8").endswith(
        "必须保留。\n"
    )


def test_legacy_markdown_overlay_is_folded_into_the_canonical_skill_once(
    skill_environment,
) -> None:
    data_dir, db_path, _, skills = skill_environment
    component_id = "hw_legacy_overlay"
    electrical = _electrical().model_dump(mode="json")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO hardware_components (
                id, name, category, status, electrical_json, stock, price,
                age_recommendation, safety_tags_json, notes, created_at, updated_at
            ) VALUES (?, ?, ?, 'ACTIVE', ?, 1, 2.5, NULL, '[]', ?, ?, ?)
            """,
            (
                component_id,
                "旧版光照传感器",
                HardwareCategory.SENSOR.value,
                json.dumps(electrical, ensure_ascii=False),
                "旧数据库说明",
                "2026-07-01T00:00:00+00:00",
                "2026-07-01T00:00:00+00:00",
            ),
        )

    legacy_root = data_dir / "hardware-component-packages" / component_id
    (legacy_root / "docs").mkdir(parents=True)
    (legacy_root / "README.md").write_text(
        "# 用户保存的旧概览\n\n保留遮光罩。\n",
        encoding="utf-8",
    )
    (legacy_root / "docs" / "integration.md").write_text(
        "# 用户保存的旧集成说明\n\n信号线需要上拉。\n",
        encoding="utf-8",
    )

    migrated = skills.ensure_component_migrated(component_id)
    files = {file.path: file.content for file in migrated.files}
    assert "迁移的旧器件概览" in files["SKILL.md"]
    assert "保留遮光罩" in files["SKILL.md"]
    assert "迁移的旧集成说明" in files["references/integration.md"]
    assert "信号线需要上拉" in files["references/integration.md"]
    assert f"legacy-overlay:{component_id}:README.md" in migrated.specification.sourceIds
    assert legacy_root.is_dir()

    old_revision = migrated.revision
    (legacy_root / "README.md").write_text("# 后续旧目录修改\n", encoding="utf-8")
    unchanged = skills.get_active_by_component_id(component_id)
    assert unchanged.revision == old_revision
    assert "后续旧目录修改" not in next(
        file.content for file in unchanged.files if file.path == "SKILL.md"
    )


def test_failed_projection_rolls_back_new_active_package(
    skill_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir, db_path, _, skills = skill_environment
    specification = HardwareSkillSpecification(
        componentId="hw_atomic_failure",
        name="原子失败测试器件",
        category=HardwareCategory.SENSOR,
        electrical=_electrical(),
    )

    def fail_projection(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.OperationalError("simulated projection failure")

    monkeypatch.setattr(skills, "_sync_projection", fail_projection)
    with pytest.raises(sqlite3.OperationalError, match="simulated"):
        skills.create_skill(
            specification,
            skill_name="atomic-failure",
            description="验证包和 SQLite 投影的失败回滚。",
        )

    assert not (data_dir / "hardware-skills" / "atomic-failure").exists()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT 1 FROM hardware_components WHERE id = ?",
            (specification.componentId,),
        ).fetchone() is None


def test_package_swap_retries_a_transient_windows_file_lock(
    skill_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir, _, _, skills = skill_environment
    specification = HardwareSkillSpecification(
        componentId="hw_transient_file_lock",
        name="短暂文件锁测试器件",
        category=HardwareCategory.SENSOR,
        electrical=_electrical(),
    )
    original_replace = hardware_skills_module.os.replace
    replace_attempts = 0

    def replace_with_one_transient_lock(source: Path, target: Path) -> None:
        nonlocal replace_attempts
        if ".tmp-" in source.name:
            replace_attempts += 1
            if replace_attempts == 1:
                raise PermissionError(5, "simulated scanner lock", str(source))
        original_replace(source, target)

    monkeypatch.setattr(
        hardware_skills_module.os,
        "replace",
        replace_with_one_transient_lock,
    )
    monkeypatch.setattr(hardware_skills_module.time, "sleep", lambda _delay: None)

    created = skills.create_skill(
        specification,
        skill_name="transient-file-lock",
        description="验证 Windows 安全扫描短暂占用时仍保持原子写入。",
    )

    assert replace_attempts == 2
    assert created.skillName == "transient-file-lock"
    assert (data_dir / "hardware-skills" / created.skillName).is_dir()


def test_skill_update_enforces_revision_paths_rules_and_sensitive_content(
    skill_environment,
) -> None:
    _, _, components, skills = skill_environment
    component = components.create_component(
        name="规则器件",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
    )
    detail = skills.get_active_by_component_id(component.id)
    rules_file = next(
        file
        for file in detail.files
        if file.path == "references/compatibility-rules.md"
    )

    with pytest.raises(HardwareSkillConflictError):
        skills.update_file(
            detail.skillName,
            path="SKILL.md",
            content="# stale\n",
            expected_revision="stale",
        )
    with pytest.raises(HardwareSkillValidationError, match="文件路径"):
        skills.update_file(
            detail.skillName,
            path="../SKILL.md",
            content="# escape\n",
            expected_revision=detail.revision,
        )

    unknown_operator = rules_file.content.replace(
        '"operator": "range-overlap"',
        '"operator": "python-eval"',
        1,
    )
    with pytest.raises(HardwareSkillValidationError, match="算子"):
        skills.update_file(
            detail.skillName,
            path=rules_file.path,
            content=unknown_operator,
            expected_revision=detail.revision,
        )

    malicious_field = rules_file.content.replace(
        '"field": "electrical.voltage"',
        '"field": "__class__.__mro__"',
        1,
    )
    with pytest.raises(HardwareSkillValidationError, match="字段"):
        skills.update_file(
            detail.skillName,
            path=rules_file.path,
            content=malicious_field,
            expected_revision=detail.revision,
        )

    with pytest.raises(HardwareSkillValidationError, match="敏感"):
        skills.update_file(
            detail.skillName,
            path="references/integration.md",
            content="# 接线\n\napi_key = sk-secret-value\n",
            expected_revision=detail.revision,
        )

    skill_file = next(file for file in detail.files if file.path == "SKILL.md")
    with pytest.raises(HardwareSkillValidationError, match="绝对路径"):
        skills.update_file(
            detail.skillName,
            path="SKILL.md",
            content=skill_file.content + "\n[越界](C:\\Users\\private\\secret.md)\n",
            expected_revision=detail.revision,
        )
    with pytest.raises(HardwareSkillValidationError, match="相对链接越出"):
        skills.update_file(
            detail.skillName,
            path="SKILL.md",
            content=skill_file.content + "\n[越界](../outside.md)\n",
            expected_revision=detail.revision,
        )

    validation_file = next(
        file for file in detail.files if file.path == "tests/validation-cases.md"
    )
    unexpected_pass = validation_file.content.replace(
        '[\n        "PASS",\n        "WARNING",\n        "FAIL"\n      ]',
        '["PASS"]',
    )
    with pytest.raises(HardwareSkillValidationError, match="validation case"):
        skills.update_file(
            detail.skillName,
            path=validation_file.path,
            content=unexpected_pass,
            expected_revision=detail.revision,
        )


def test_skill_reader_rejects_extra_files_and_non_utf8_content(
    skill_environment,
) -> None:
    data_dir, _, components, skills = skill_environment
    component = components.create_component(
        name="文件边界器件",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(),
    )
    detail = skills.get_active_by_component_id(component.id)
    root = data_dir / "hardware-skills" / detail.skillName
    extra = root / "references" / "unexpected.md"
    extra.write_text("# 不允许的文件\n", encoding="utf-8")
    with pytest.raises(HardwareSkillValidationError, match="文件树"):
        skills.get_skill(detail.skillName)
    extra.unlink()

    specifications = root / "references" / "specifications.md"
    original = specifications.read_bytes()
    specifications.write_bytes(b"\xff\xfe")
    with pytest.raises(HardwareSkillValidationError, match="UTF-8"):
        skills.get_skill(detail.skillName)
    specifications.write_bytes(original)
    assert skills.get_skill(detail.skillName).revision == detail.revision


def test_rule_engine_executes_rules_compiled_from_active_skills(
    skill_environment,
) -> None:
    _, _, components, skills = skill_environment
    mcu = components.create_component(
        name="ESP32-S3",
        category=HardwareCategory.MCU.value,
        electrical=_electrical(
            communicationProtocol="GPIO",
            i2cAddress=None,
            driverName=None,
        ),
    )
    first = components.create_component(
        name="I2C A",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(i2cAddress="0x40"),
    )
    second = components.create_component(
        name="I2C B",
        category=HardwareCategory.SENSOR.value,
        electrical=_electrical(i2cAddress="0x40"),
    )
    details = [
        skills.get_active_by_component_id(item.id)
        for item in (mcu, first, second)
    ]
    rules = [rule for detail in details for rule in detail.rules]

    result = validate_components(
        [skills.component_from_detail(detail) for detail in details],
        rules=rules,
    )

    assert result.overall.value == "FAIL"
    assert any(
        check.dimension == "i2c_address" and check.severity.value == "FAIL"
        for check in result.checks
    )


def test_draft_is_invisible_until_confirmed_and_dialogue_revises_it(
    skill_environment,
) -> None:
    _, _, _, skills = skill_environment
    client = TestClient(app)
    before = {skill["componentId"] for skill in client.get("/api/hardware/skills").json()["skills"]}
    source = {
        "name": "对话新增传感器",
        "category": "SENSOR",
        "electrical": _electrical(i2cAddress="0x41").model_dump(mode="json"),
        "stock": 3,
        "price": 8.5,
        "ageRecommendation": 9,
        "safetyTags": ["3.3V 逻辑"],
        "notes": "通过资料和对话创建。",
        "verificationStatus": "USER_CONFIRMED",
    }
    created = client.post(
        "/api/hardware/skills/drafts",
        json={
            "description": "本地受控提取",
            "sources": [
                {
                    "name": "sensor.json",
                    "mediaType": "application/json",
                    "content": json.dumps(source, ensure_ascii=False),
                }
            ],
        },
    )
    assert created.status_code == 201
    draft = created.json()["draft"]
    assert draft["status"] == "DRAFT"
    assert draft["canConfirm"] is True
    assert draft["specification"]["name"] == "对话新增传感器"
    assert {skill["componentId"] for skill in client.get("/api/hardware/skills").json()["skills"]} == before

    continued = client.post(
        f"/api/hardware/skills/drafts/{draft['id']}/messages",
        json={
            "message": json.dumps({"stock": 7, "notes": "对话补充后的说明"}, ensure_ascii=False),
            "expectedRevision": draft["revision"],
        },
    )
    assert continued.status_code == 200
    revised = continued.json()["draft"]
    assert revised["revision"] != draft["revision"]
    assert revised["specification"]["stock"] == 7

    stale = client.post(
        f"/api/hardware/skills/drafts/{draft['id']}/confirm",
        json={"expectedRevision": draft["revision"]},
    )
    assert stale.status_code == 409

    confirmed = client.post(
        f"/api/hardware/skills/drafts/{draft['id']}/confirm",
        json={"expectedRevision": revised["revision"]},
    )
    assert confirmed.status_code == 201
    skill = confirmed.json()["skill"]
    assert skill["status"] == "ACTIVE"
    assert skill["specification"]["stock"] == 7
    assert (settings.data_dir / "hardware-skills" / skill["skillName"] / "SKILL.md").is_file()
    assert skills.get_active_by_component_id(skill["componentId"]).revision == skill["revision"]
    client.close()


def test_draft_rejects_uncontrolled_sources_and_pdf_has_controlled_diagnostic(
    skill_environment,
) -> None:
    client = TestClient(app)
    bad_name = client.post(
        "/api/hardware/skills/drafts",
        json={
            "sources": [
                {"name": "../secret.txt", "mediaType": "text/plain", "content": "safe"}
            ]
        },
    )
    assert bad_name.status_code == 422

    bad_media = client.post(
        "/api/hardware/skills/drafts",
        json={
            "sources": [
                {"name": "board.exe", "mediaType": "application/octet-stream", "content": "x"}
            ]
        },
    )
    assert bad_media.status_code == 422

    pdf = client.post(
        "/api/hardware/skills/drafts",
        json={
            "name": "PDF 器件",
            "sources": [
                {"name": "board.pdf", "mediaType": "application/pdf", "content": "bm90IGEgcGRm"}
            ],
        },
    )
    assert pdf.status_code == 201
    draft = pdf.json()["draft"]
    assert draft["canConfirm"] is False
    assert any(item["code"].startswith("PDF_") for item in draft["diagnostics"])

    deleted = client.delete(f"/api/hardware/skills/drafts/{draft['id']}")
    assert deleted.status_code == 204
    client.close()


def test_pdf_datasheet_is_extracted_by_the_local_sidecar(skill_environment) -> None:
    payload = json.dumps(
        {
            "name": "PDF Sensor",
            "category": "SENSOR",
            "electrical": {
                "voltage": 3.3,
                "logicLevel": 3.3,
                "peakCurrent": 0.02,
                "communicationProtocol": "I2C",
                "i2cAddress": "0x44",
                "supportedMCUs": ["esp32-s3"],
                "driverName": "pdf_sensor",
                "firmwareRequirement": None,
            },
        },
        separators=(",", ":"),
    )
    client = TestClient(app)
    response = client.post(
        "/api/hardware/skills/drafts",
        json={
            "sources": [
                {
                    "name": "datasheet.pdf",
                    "mediaType": "application/pdf",
                    "content": base64.b64encode(_text_pdf(payload)).decode("ascii"),
                }
            ]
        },
    )

    assert response.status_code == 201
    draft = response.json()["draft"]
    assert draft["canConfirm"] is True
    assert draft["specification"]["name"] == "PDF Sensor"
    assert draft["specification"]["electrical"]["i2cAddress"] == "0x44"
    assert not [item for item in draft["diagnostics"] if item["severity"] == "error"]
    client.close()


def test_natural_datasheet_and_dialogue_fill_required_electrical_fields(
    skill_environment,
) -> None:
    client = TestClient(app)
    created = client.post(
        "/api/hardware/skills/drafts",
        json={
            "name": "BME280 环境传感器",
            "description": "I2C 环境传感器",
            "sources": [
                {
                    "name": "datasheet.txt",
                    "mediaType": "text/plain",
                    "content": "通信协议 I2C，I2C 地址 0x76，支持 ESP32-S3。",
                }
            ],
        },
    )
    assert created.status_code == 201
    draft = created.json()["draft"]
    assert draft["canConfirm"] is False

    continued = client.post(
        f"/api/hardware/skills/drafts/{draft['id']}/messages",
        json={
            "message": "工作电压 3.3V，逻辑电平 3.3V，峰值电流 1mA。",
            "expectedRevision": draft["revision"],
        },
    )
    assert continued.status_code == 200
    revised = continued.json()["draft"]
    assert revised["canConfirm"] is True
    assert revised["specification"]["category"] == "SENSOR"
    assert revised["specification"]["electrical"]["peakCurrent"] == 0.001
    assert revised["specification"]["electrical"]["i2cAddress"] == "0x76"
    client.delete(f"/api/hardware/skills/drafts/{draft['id']}")
    client.close()


def _text_pdf(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 7 Tf 24 720 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
