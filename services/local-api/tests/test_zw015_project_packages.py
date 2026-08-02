"""Tests for ZW-015 project package export/import."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.artifacts.models import (
    ArtifactKind,
    ArtifactPreviewSection,
    ArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.project_packages.privacy import scan_package_payload
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository


def test_v13_migration_creates_package_exports(tmp_path: Path) -> None:
    db_file = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()

    assert CURRENT_SCHEMA_VERSION == 31
    assert version == CURRENT_SCHEMA_VERSION
    assert "package_exports" in tables


def test_export_package_includes_manifest_privacy_report_and_artifact(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _project_with_document_artifact(tmp_path)

    response = client.post(
        f"/api/projects/{project_id}/package/export",
        json={"title": "课堂分享包"},
    )

    assert response.status_code == 200
    package = response.json()["package"]
    assert package["status"] == "EXPORTED"
    assert package["fileName"].endswith(".zip")
    assert package["zipBase64"]
    assert package["privacyReport"]["ok"] is True
    assert package["manifest"]["projectId"] == project_id
    assert len(package["manifest"]["artifacts"]) == 1
    assert package["artifactId"] == f"artifact_package_{project_id}"

    files = _zip_files(package["zipBase64"])
    assert {"manifest.json", "project/summary.json", "privacy_report.json"}.issubset(
        files
    )
    assert "artifacts/artifact_doc_export.json" in files
    manifest = json.loads(files["manifest.json"])
    assert manifest["artifacts"][0]["path"] == "artifacts/artifact_doc_export.json"

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(
        project_id
    )
    package_artifact = next(
        artifact for artifact in artifacts if artifact.kind == ArtifactKind.PACKAGE
    )
    assert package_artifact.sourceAgentId == "publish-agent"
    assert package_artifact.versions[0].preview.sections


def test_cad_binary_files_round_trip_through_project_package(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _project_with_cad_binary_artifact(tmp_path)

    exported = client.post(
        f"/api/projects/{project_id}/package/export",
        json={"title": "CAD 二进制分享包"},
    )
    assert exported.status_code == 200
    package = exported.json()["package"]
    assert package["manifest"]["schemaVersion"] == 2
    assert package["manifest"]["packageVersion"] == 2
    assert "ARTIFACT_FILE" in package["manifest"]["itemKinds"]
    manifest_files = package["manifest"]["artifacts"][0]["files"]
    assert {item["role"] for item in manifest_files} == {
        "GLB_PREVIEW",
        "STEP_ASSEMBLY",
        "STL_PRINTABLE_PARTS",
    }
    archive_files = _zip_files_binary(package["zipBase64"])
    assert all(item["path"] in archive_files for item in manifest_files)

    imported = client.post(
        "/api/projects/package/import",
        json={"zipBase64": package["zipBase64"]},
    )
    assert imported.status_code == 200
    imported_project_id = imported.json()["workspace"]["project"]["id"]
    imported_artifact = next(
        artifact
        for artifact in ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(
            imported_project_id
        )
        if artifact.title == "CAD 模型"
    )
    imported_files = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifact_files(
        imported_project_id,
        imported_artifact.id,
        imported_artifact.currentVersionId or "",
    )
    assert {file.role for file in imported_files} == {
        "GLB_PREVIEW",
        "STEP_ASSEMBLY",
        "STL_PRINTABLE_PARTS",
    }
    for file in imported_files:
        path = tmp_path / "artifact-files" / file.projectId / file.artifactId / file.artifactVersionId / file.fileName
        content = path.read_bytes()
        assert len(content) == file.byteSize
        assert hashlib.sha256(content).hexdigest() == file.sha256


def test_export_merges_partial_artifact_selection_with_defaults(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _project_with_document_artifact(tmp_path)

    response = client.post(
        f"/api/projects/{project_id}/package/export",
        json={"artifactSelection": {"includeCode": False}},
    )

    assert response.status_code == 200
    selection = response.json()["package"]["manifest"]["artifactSelection"]
    assert selection["includeDocuments"] is True
    assert selection["includeCode"] is False
    assert selection["includeCad"] is True
    assert selection["includeLessons"] is True
    assert selection["includeDeviceLogs"] is False


def test_export_blocks_sensitive_artifact_content(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _project_with_document_artifact(
        tmp_path,
        content="请不要导出 apiKey: hidden-value",
    )

    response = client.post(
        f"/api/projects/{project_id}/package/export",
        json={"title": "敏感分享包"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROJECT_PACKAGE_PRIVACY_BLOCKED"
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        row = conn.execute(
            "SELECT status, zip_base64 FROM package_exports WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert row == ("BLOCKED", None)


@pytest.mark.parametrize(
    ("content", "dimension"),
    [
        ("web=http://10.20.30.40:80/api/status", "private-lan-url"),
        ("web=https://172.16.4.8/files/main.lua", "private-lan-url"),
        ("web=http://172.31.255.254/mcp", "private-lan-url"),
        ("web=http://192.168.4.1", "private-lan-url"),
        ("web=http://esp-claw.local:80", "private-lan-url"),
        ("web=http://[fd00::1]:80/mcp", "private-lan-url"),
        ("web=http://[fe80::1]/api/status", "private-lan-url"),
        ("web=http://[::1]", "private-lan-url"),
        ("session=espclaw_session_endpoint-123", "espclaw-local-identifier"),
        ("portId=esp-claw:endpoint-123", "espclaw-local-identifier"),
    ],
)
def test_privacy_scan_blocks_espclaw_private_endpoint_data(
    content: str,
    dimension: str,
) -> None:
    report = scan_package_payload({"artifacts/device-log.json": content})

    assert report.ok is False
    assert any(
        check.dimension == dimension and check.severity == "FAIL"
        for check in report.checks
    )


@pytest.mark.parametrize(
    "content",
    [
        "docs=https://esp-claw.com/en/reference-cap/cap-mcp/",
        "public=http://172.15.0.1/status",
        "public=http://172.32.0.1/status",
        "product=ESP-Claw",
    ],
)
def test_privacy_scan_allows_public_espclaw_references(content: str) -> None:
    report = scan_package_payload({"project/summary.json": content})

    assert report.ok is True


def test_export_blocks_espclaw_private_data_in_selected_device_log(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project("ESP-Claw 调试项目", "验证设备日志导出隐私边界")
    content = json.dumps(
        {
            "webEndpoint": "http://192.168.4.1",
            "mcpEndpoint": "http://esp-claw.local/mcp",
            "sessionId": "espclaw_session_endpoint-123",
            "portId": "esp-claw:endpoint-123",
        },
        ensure_ascii=False,
    )
    ArtifactRepository(repo.db_path).upsert_text_artifact(
        artifact_id="artifact_espclaw_device_log",
        project_id=workspace.project.id,
        title="ESP-Claw 设备日志",
        kind=ArtifactKind.DEVICE_LOG,
        status=ArtifactStatus.APPROVED,
        source_agent_id="device-agent",
        source_entity_type="device-operation",
        source_entity_id="operation_espclaw_123",
        source_version=1,
        content=content,
        summary="ESP-Claw 设备日志",
        mime_type="application/json",
        sections=[
            ArtifactPreviewSection(
                id="log",
                title="设备日志",
                content=content,
            )
        ],
        confirmed_at="2026-07-30T00:00:00+00:00",
    )

    response = client.post(
        f"/api/projects/{workspace.project.id}/package/export",
        json={"artifactSelection": {"includeDeviceLogs": True}},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROJECT_PACKAGE_PRIVACY_BLOCKED"
    with sqlite3.connect(repo.db_path) as conn:
        row = conn.execute(
            "SELECT status, zip_base64 FROM package_exports WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()
    assert row == ("BLOCKED", None)


def test_import_rejects_path_traversal_zip(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    zip_base64 = _unsafe_zip_base64()

    response = client.post(
        "/api/projects/package/import",
        json={"zipBase64": zip_base64},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROJECT_PACKAGE_UNSAFE_ZIP"


def test_import_package_creates_copy_project_and_artifacts(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _project_with_document_artifact(tmp_path)
    exported = client.post(
        f"/api/projects/{project_id}/package/export",
        json={"title": "导入测试包"},
    ).json()["package"]

    imported = client.post(
        "/api/projects/package/import",
        json={"zipBase64": exported["zipBase64"]},
    )

    assert imported.status_code == 200
    body = imported.json()
    assert body["package"]["status"] == "IMPORTED"
    workspace = body["workspace"]
    assert workspace["project"]["id"] != project_id
    assert workspace["project"]["name"].endswith("（导入副本）")
    assert workspace["project"]["schemaVersion"] == CURRENT_SCHEMA_VERSION

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(
        workspace["project"]["id"]
    )
    assert any(artifact.kind == ArtifactKind.PACKAGE for artifact in artifacts)
    assert any(artifact.title == "课堂文档" for artifact in artifacts)


def _project_with_document_artifact(
    tmp_path: Path,
    *,
    content: str = "## 项目说明\n\n这是可分享的课堂项目摘要。",
) -> str:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project("分享项目", "做一个可以展示的项目")
    ArtifactRepository(repo.db_path).upsert_text_artifact(
        artifact_id="artifact_doc_export",
        project_id=workspace.project.id,
        title="课堂文档",
        kind=ArtifactKind.DOCUMENT,
        status=ArtifactStatus.APPROVED,
        source_agent_id="proposal-agent",
        source_entity_type="proposal",
        source_entity_id="proposal_export",
        source_version=1,
        content=content,
        summary="课堂文档 v1",
        mime_type="text/markdown",
        sections=[
            ArtifactPreviewSection(
                id="summary",
                title="项目说明",
                content=content,
            )
        ],
        confirmed_at="2026-07-08T00:00:00+00:00",
    )
    return workspace.project.id


def _project_with_cad_binary_artifact(tmp_path: Path) -> str:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project("CAD 分享项目", "分享结构件三维模型")
    artifact_repo = ArtifactRepository(repo.db_path)
    artifact_id = "artifact_cad_export"
    version = artifact_repo.upsert_model_artifact(
        artifact_id=artifact_id,
        project_id=workspace.project.id,
        title="CAD 模型",
        status=ArtifactStatus.APPROVED,
        source_agent_id="cad-agent",
        source_entity_type="cad",
        source_entity_id="cad_export",
        source_version=1,
        content=None,
        summary="带盖盒体三维模型",
        model_url=None,
        model_file_id="file_glb",
        checksum="a" * 64,
    )
    binary_files = {
        "preview.glb": ("GLB_PREVIEW", "model/gltf-binary", b"glTF\x02\x00\x00"),
        "assembly.step": ("STEP_ASSEMBLY", "model/step", b"ISO-10303-21;"),
        "base.stl": ("STL_PRINTABLE_PARTS", "model/stl", b"solid base\nendsolid base\n"),
    }
    root = tmp_path / "artifact-files" / workspace.project.id / artifact_id / version.id
    root.mkdir(parents=True)
    now = "2026-07-13T00:00:00+00:00"
    with repo._connect() as conn:
        for index, (file_name, (role, mime_type, content)) in enumerate(binary_files.items()):
            (root / file_name).write_bytes(content)
            artifact_repo.insert_artifact_file(
                conn,
                file_id=f"file_{index}",
                artifact_id=artifact_id,
                artifact_version_id=version.id,
                project_id=workspace.project.id,
                role=role,
                file_name=file_name,
                storage_key=f"{workspace.project.id}/{artifact_id}/{version.id}/{file_name}",
                mime_type=mime_type,
                byte_size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                triangle_count=1 if file_name.endswith((".stl", ".glb")) else None,
                bounds=None,
                created_at=now,
            )
    return workspace.project.id


def _zip_files(zip_base64: str) -> dict[str, str]:
    raw = base64.b64decode(zip_base64)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        return {
            name: archive.read(name).decode("utf-8")
            for name in archive.namelist()
        }


def _zip_files_binary(zip_base64: str) -> dict[str, bytes]:
    raw = base64.b64decode(zip_base64)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _unsafe_zip_base64() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../manifest.json", "{}")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
