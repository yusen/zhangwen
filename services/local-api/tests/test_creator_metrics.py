from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError

from zhangwen.creator.metrics import (
    CREATOR_METRIC_ADAPTER,
    CreatorMetricError,
    WorkCreatedMetric,
    append_creator_metric,
    metric_trigger_id,
)
from zhangwen.creator.models import CreatorCommand, CreatorCommandRequest
from zhangwen.creator import repository as creator_repository_module
from zhangwen.creator.repository import CreatorRepository
from zhangwen.devices.models import (
    DeviceOperationKind,
    DeviceOperationStatus,
)
from zhangwen.devices.repository import DeviceRepository
from zhangwen.devices.simulator import MOCK_DEVICE_PORT_ID


def test_creator_metric_is_strict_private_and_exactly_once(tmp_path) -> None:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="指标契约",
        initial_idea="验证匿名指标",
        idempotency_key="creator-metric-work",
        selected_hardware_ids=[],
    )
    trigger_id = metric_trigger_id(
        metric="WORK_CREATED",
        project_id=workspace.work_id,
        source_key="creator-metric-work",
    )
    payload = WorkCreatedMetric(triggerId=trigger_id, origin="CREATOR")

    with sqlite3.connect(repository._db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        assert append_creator_metric(conn, workspace.work_id, payload) is False
        assert append_creator_metric(conn, workspace.work_id, payload) is False
        conn.commit()

    metric_events = [
        event
        for event in repository.events(workspace.work_id)
        if event["type"] == "METRIC"
    ]
    assert len(metric_events) == 1
    assert metric_events[0]["payload"] == {
        "metric": "WORK_CREATED",
        "origin": "CREATOR",
        "schemaVersion": 1,
        "triggerId": trigger_id,
    }
    assert "workId" not in metric_events[0]
    assert workspace.work_id not in trigger_id


def test_creator_metric_rejects_changed_payload_and_sensitive_extra_fields(
    tmp_path,
) -> None:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="指标冲突",
        initial_idea="验证指标不可覆盖",
        idempotency_key="creator-metric-conflict-work",
        selected_hardware_ids=[],
    )
    trigger_id = metric_trigger_id(
        metric="WORK_CREATED",
        project_id=workspace.work_id,
        source_key="creator-metric-conflict-work",
    )
    with sqlite3.connect(repository._db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(CreatorMetricError):
            append_creator_metric(
                conn,
                workspace.work_id,
                WorkCreatedMetric(triggerId=trigger_id, origin="LEGACY"),
            )
        conn.rollback()

    with pytest.raises(ValidationError):
        CREATOR_METRIC_ADAPTER.validate_python(
            {
                "schemaVersion": 1,
                "metric": "WORK_CREATED",
                "triggerId": trigger_id,
                "origin": "CREATOR",
                "email": "not-allowed@example.test",
            }
        )


def test_creator_command_metric_is_written_in_idempotent_transaction(
    tmp_path,
) -> None:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="指标命令",
        initial_idea="制作环境提醒灯",
        idempotency_key="creator-metric-command-work",
        selected_hardware_ids=[],
    )
    request = CreatorCommandRequest.model_validate(
        {
            "baseProjectVersion": workspace.project_version,
            "idempotencyKey": "creator-metric-confirm-goal",
            "payload": {
                "statement": "制作环境提醒灯",
                "observableBehavior": "温度过高时点亮提示灯",
                "constraints": ["离线运行"],
                "successCriteria": ["高温点亮", "恢复后关闭"],
            },
        }
    )
    first = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        request,
    )
    repeated = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        request,
    )

    assert first.repeated is False
    assert repeated.repeated is True
    metric_names = [
        event["payload"]["metric"]
        for event in repository.events(workspace.work_id)
        if event["type"] == "METRIC"
    ]
    assert metric_names.count("WORK_CREATED") == 1
    assert metric_names.count("GOAL_CONFIRMED") == 1


def test_work_creation_rolls_back_when_metric_projection_fails(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = CreatorRepository(tmp_path)

    def reject_metric(*_args, **_kwargs) -> bool:
        raise RuntimeError("injected metric failure")

    monkeypatch.setattr(
        creator_repository_module,
        "append_creator_metric",
        reject_metric,
    )
    with pytest.raises(RuntimeError, match="injected metric failure"):
        repository.create_work(
            name="事务回滚",
            initial_idea="指标失败时不能留下孤立作品",
            idempotency_key="creator-metric-rollback-work",
            selected_hardware_ids=[],
        )

    with sqlite3.connect(repository._db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM creator_work_state"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM creator_events").fetchone()[0] == 0


def test_terminal_device_operation_projects_first_failure_and_recovery(
    tmp_path,
) -> None:
    creator = CreatorRepository(tmp_path)
    workspace = creator.create_work(
        name="设备指标",
        initial_idea="验证首轮部署失败与恢复投影",
        idempotency_key="creator-device-metric-work",
        selected_hardware_ids=[],
    )
    devices = DeviceRepository(creator._db_path)
    session = devices.connect_mock_port(
        workspace.work_id,
        MOCK_DEVICE_PORT_ID,
    )
    failed_state = {
        "schema": "device-operation/v1",
        "log": "readback failed and previous files were restored",
        "phase": "COMPLETE",
        "progress": 100,
        "errorCode": "DEVICE_READBACK_MISMATCH",
        "steps": [
            {
                "phase": "RESTORE",
                "status": "COMPLETED",
                "exitCode": 0,
                "summary": "restored",
                "startedAt": "2026-07-31T00:00:00Z",
                "completedAt": "2026-07-31T00:00:00Z",
            }
        ],
        "backup": None,
        "verification": None,
        "cancelable": False,
        "metadata": {
            "channel": "USB_SERIAL",
            "failureEvidence": {"restoreSucceeded": True},
        },
    }
    devices.create_operation(
        project_id=workspace.work_id,
        session_id=session.id,
        operation_id="metric-upload-failed-1",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="mpremote",
        log=json.dumps(failed_state),
    )
    devices.update_operation(
        workspace.work_id,
        "metric-upload-failed-1",
        status=DeviceOperationStatus.FAILED,
        log=json.dumps(failed_state),
        completed_at="2026-07-31T00:00:01Z",
    )

    succeeded_state = {
        **failed_state,
        "log": "upload completed",
        "errorCode": None,
        "steps": [],
        "metadata": {"channel": "USB_SERIAL"},
    }
    devices.create_operation(
        project_id=workspace.work_id,
        session_id=session.id,
        operation_id="metric-upload-success-2",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="mpremote",
        log=json.dumps(succeeded_state),
    )
    devices.update_operation(
        workspace.work_id,
        "metric-upload-success-2",
        status=DeviceOperationStatus.COMPLETED,
        log=json.dumps(succeeded_state),
        completed_at="2026-07-31T00:00:02Z",
    )

    payloads = [
        event["payload"]
        for event in creator.events(workspace.work_id)
        if event["type"] == "METRIC"
    ]
    deployments = [
        payload
        for payload in payloads
        if payload["metric"] == "FIRST_DEPLOYMENT_FINISHED"
    ]
    recoveries = [
        payload for payload in payloads if payload["metric"] == "RECOVERY_FINISHED"
    ]
    assert len(deployments) == 1
    assert deployments == [
        {
            "channel": "USB_SERIAL",
            "metric": "FIRST_DEPLOYMENT_FINISHED",
            "passed": False,
            "recoveryRequired": True,
            "schemaVersion": 1,
            "triggerId": deployments[0]["triggerId"],
        }
    ]
    assert workspace.work_id not in deployments[0]["triggerId"]
    assert len(recoveries) == 1
    assert recoveries[0]["action"] == "USB_UPLOAD"
    assert recoveries[0]["passed"] is True
