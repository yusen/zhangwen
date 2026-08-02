from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from zhangwen.artifacts.models import ArtifactKind, ArtifactStatus
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.devices.repository import DeviceRepository
from zhangwen.projects.errors import ProjectArchivedError, ProjectNotFoundError
from zhangwen.projects.lifecycle import ProjectLifecycleService
from zhangwen.projects.repository import ProjectRepository


def test_duplicate_copies_conversation_draft_and_versioned_artifacts_without_devices(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    source = repository.create_project("自动浇花", "制作自动浇花装置")
    repository.save_draft(source.project.id, "尚未发送的标定说明")
    artifacts = ArtifactRepository(repository.db_path)
    artifacts.upsert_text_artifact(
        artifact_id="artifact_watering_code",
        project_id=source.project.id,
        title="MicroPython 工程代码",
        kind=ArtifactKind.CODE,
        status=ArtifactStatus.APPROVED,
        source_agent_id=source.experts[0].id,
        source_entity_type="code",
        source_entity_id="code_watering_v1",
        source_version=1,
        content="print('v1')\n",
        summary="第一版",
        mime_type="text/x-python",
        language="python",
    )
    artifacts.upsert_text_artifact(
        artifact_id="artifact_watering_code",
        project_id=source.project.id,
        title="MicroPython 工程代码",
        kind=ArtifactKind.CODE,
        status=ArtifactStatus.APPROVED,
        source_agent_id=source.experts[0].id,
        source_entity_type="code",
        source_entity_id="code_watering_v2",
        source_version=2,
        content="print('v2')\n",
        summary="第二版",
        mime_type="text/x-python",
        language="python",
    )
    DeviceRepository(repository.db_path).connect_mock_port(
        source.project.id,
        "mock_port_esp32_s3",
    )

    duplicate = ProjectLifecycleService(tmp_path).duplicate(source.project.id)

    assert duplicate.project.id != source.project.id
    assert duplicate.project.name == "自动浇花（副本）"
    assert duplicate.draft.content == "尚未发送的标定说明"
    assert [message.content for message in duplicate.conversation.messages] == [
        message.content for message in source.conversation.messages
    ]
    cloned_artifacts = ArtifactRepository(repository.db_path).list_artifacts(
        duplicate.project.id
    )
    assert len(cloned_artifacts) == 1
    assert len(cloned_artifacts[0].versions) == 2
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM device_sessions WHERE project_id = ?",
            (duplicate.project.id,),
        ).fetchone()[0] == 0


def test_permanent_delete_requires_archive_and_exact_name_then_creates_backup(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    source = repository.create_project("要永久删除的项目", "测试可恢复删除")
    service = ProjectLifecycleService(tmp_path)

    with pytest.raises(ProjectArchivedError):
        service.permanently_delete(
            source.project.id,
            confirmation_name=source.project.name,
        )

    repository.archive_project(source.project.id, True)
    backup_id, _created_at = service.permanently_delete(
        source.project.id,
        confirmation_name=source.project.name,
    )

    backup_root = tmp_path / "project-deletion-backups" / backup_id
    assert (backup_root / "zhangwen.sqlite3").is_file()
    with pytest.raises(ProjectNotFoundError):
        repository.get_workspace(source.project.id)
