"""ESP-Claw is a peer code-deployment channel, never a firmware path."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient

from zhangwen.code_agent.models import (
    CodeFile,
    CodeFileKind,
    CodePatch,
    CodeRun,
    CodeRunStatus,
    CodeRuntime,
    CodeTestResult,
)
from zhangwen.devices.espclaw import (
    EspClawAdapterCanceled,
    EspClawAdapterError,
    EspClawAsyncJob,
    EspClawHandshake,
    HttpxEspClawDeploymentAdapter,
    normalize_espclaw_endpoint,
    normalize_espclaw_mcp_endpoint,
)
from zhangwen.devices.models import (
    DeviceDeploymentChannel,
    DeviceOperationKind,
    DeviceOperationPhase,
    DeviceOperationStatus,
    DeviceSessionStatus,
)
from zhangwen.devices import router as devices_router
from zhangwen.devices.repository import (
    DeviceDeploymentSessionMismatch,
    DeviceProjectLeaseBusy,
    DeviceRepository,
)
from zhangwen.devices.service import DeviceOperationService, DeviceServiceError
from zhangwen.devices.transport import MockDeviceTransport
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.projects.models import ExpertType
from zhangwen.projects.migrations import migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalSection
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from zhangwen.config import settings
from zhangwen.main import app


DESKTOP_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "test-token",
}


class FakeEspClawAdapter:
    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []
        self.corrupt_next_readback = False
        self.block_upload = False
        self.block_runtime_start = False
        self.readback_capable = True
        self.job_statuses = ["completed"]
        self.run_requests: list[dict[str, object]] = []
        self._upload_returned = False
        self.reported_board_id = SupportedDeviceBoardId.DFROBOT_K10.value
        self.stop_fails = False
        self.stop_status = "stopped"
        self.restore_failure_content: bytes | None = None
        self.silent_restore_mismatch_content: bytes | None = None
        self.restore_delay_seconds = 0.0
        self.delete_delay_seconds = 0.0

    async def handshake(self, web_endpoint, mcp_endpoint, *, cancel, timeout_seconds):
        self.calls.append(("handshake", f"{web_endpoint}|{mcp_endpoint}"))
        return EspClawHandshake(
            storage_base_path="/fatfs",
            capabilities=(
                "lua_get_async_job",
                "lua_run_script_async",
                "lua_stop_async_job",
            ),
            file_readback_capable=self.readback_capable,
            reported_board_id=self.reported_board_id,
        )

    async def make_directory(self, endpoint, path, *, cancel, timeout_seconds):
        self.calls.append(("mkdir", path))

    async def read_file(self, endpoint, path, *, cancel, timeout_seconds):
        self.calls.append(("read", path))
        if self.corrupt_next_readback and self._upload_returned:
            self.corrupt_next_readback = False
            return b"corrupt-readback"
        return self.storage.get(path)

    async def upload_file(self, endpoint, path, content, *, cancel, timeout_seconds):
        self.calls.append(("upload", path))
        if self.restore_delay_seconds and self._upload_returned:
            await asyncio.sleep(self.restore_delay_seconds)
        if self.restore_failure_content is not None and content == self.restore_failure_content:
            raise EspClawAdapterError(
                "ESP_CLAW_TEST_RESTORE_FAILED",
                "synthetic restore failure",
            )
        if (
            self.silent_restore_mismatch_content is not None
            and self._upload_returned
            and content == self.silent_restore_mismatch_content
        ):
            return
        self.storage[path] = bytes(content)
        if self.block_upload:
            while not cancel.is_set():
                await asyncio.sleep(0.001)
            raise EspClawAdapterCanceled()
        self._upload_returned = True

    async def delete_file(self, endpoint, path, *, cancel, timeout_seconds):
        self.calls.append(("delete", path))
        if self.delete_delay_seconds:
            await asyncio.sleep(self.delete_delay_seconds)
        self.storage.pop(path, None)

    async def run_lua_script(self, endpoint, path, job_name, *, cancel, timeout_seconds):
        self.calls.append(("run", path))
        self.run_requests.append(
            {
                "path": path,
                "name": job_name,
                "exclusive": job_name,
                "replace": True,
                "timeout_ms": 0,
            }
        )
        if self.block_runtime_start:
            while not cancel.is_set():
                await asyncio.sleep(0.001)
            raise EspClawAdapterCanceled()
        return "job-test-1"

    async def get_async_job(self, endpoint, job_id, *, cancel, timeout_seconds):
        self.calls.append(("job", job_id))
        status = self.job_statuses.pop(0) if len(self.job_statuses) > 1 else self.job_statuses[0]
        return EspClawAsyncJob(
            job_id=job_id,
            status=status,
            ok=True if status == "completed" else False if status == "failed" else None,
        )

    async def stop_async_job(self, endpoint, job_name, *, cancel, timeout_seconds):
        self.calls.append(("stop", job_name))
        if self.stop_fails:
            raise EspClawAdapterError(
                "ESP_CLAW_TEST_STOP_FAILED",
                "synthetic stop failure",
            )

    async def get_async_job_by_name(
        self,
        endpoint,
        job_name,
        *,
        cancel,
        timeout_seconds,
    ):
        self.calls.append(("job-name", job_name))
        return EspClawAsyncJob(
            job_id="job-test-1",
            status=self.stop_status,
            ok=None,
        )


def test_endpoint_normalization_rejects_public_https_and_embedded_credentials() -> None:
    assert normalize_espclaw_endpoint("http://192.168.20.8:80/") == "http://192.168.20.8:80"
    assert normalize_espclaw_endpoint("http://edge-agent.local/") == "http://edge-agent.local"
    with pytest.raises(Exception):
        normalize_espclaw_endpoint("https://192.168.20.8")
    with pytest.raises(Exception):
        normalize_espclaw_endpoint("http://user:secret@192.168.20.8")
    with pytest.raises(Exception):
        normalize_espclaw_endpoint("http://8.8.8.8")
    assert (
        normalize_espclaw_mcp_endpoint("http://edge-agent.local:9100/device-mcp/")
        == "http://edge-agent.local:9100/device-mcp"
    )
    with pytest.raises(Exception):
        normalize_espclaw_mcp_endpoint("http://edge-agent.local:9100/a/../mcp")
    with pytest.raises(Exception):
        normalize_espclaw_mcp_endpoint("http://8.8.8.8/mcp")


def test_v29_legacy_single_endpoint_schema_repairs_to_dual_endpoint_fail_closed(
    tmp_path: Path,
) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="legacy ESP-Claw endpoint",
        project_name="legacy endpoint repair",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    device_repository = DeviceRepository(projects.db_path)
    session = device_repository.connect_mock_port(
        workspace.project.id,
        "mock_port_esp32_s3",
        SupportedDeviceBoardId.DFROBOT_K10,
    )
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(projects.db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DROP TABLE espclaw_deployments")
        conn.execute("DROP TABLE espclaw_endpoints")
        conn.executescript(
            """
            CREATE TABLE espclaw_endpoints (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              session_id TEXT NOT NULL UNIQUE REFERENCES device_sessions(id) ON DELETE CASCADE,
              endpoint_url TEXT NOT NULL,
              board_id TEXT NOT NULL,
              status TEXT NOT NULL,
              storage_base_path TEXT NOT NULL,
              capabilities_json TEXT NOT NULL,
              paired_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(project_id, endpoint_url)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO espclaw_endpoints (
              id, project_id, session_id, endpoint_url, board_id, status,
              storage_base_path, capabilities_json, paired_at, last_seen_at,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'READY', '/fatfs', '[]', ?, ?, ?, ?)
            """,
            (
                "legacy-endpoint",
                workspace.project.id,
                session.id,
                "http://edge-agent.local:80",
                SupportedDeviceBoardId.DFROBOT_K10.value,
                now,
                now,
                now,
                now,
            ),
        )
        migrate(conn)
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(espclaw_endpoints)").fetchall()
        }
        repaired = conn.execute(
            """
            SELECT web_endpoint, mcp_endpoint, status
            FROM espclaw_endpoints WHERE id = 'legacy-endpoint'
            """
        ).fetchone()

    assert "endpoint_url" not in columns
    assert {"web_endpoint", "mcp_endpoint"}.issubset(columns)
    assert repaired == (
        "http://edge-agent.local:80",
        "http://edge-agent.local:80",
        "ERROR",
    )
    repaired_endpoint = DeviceRepository(projects.db_path).pair_espclaw_endpoint(
        project_id=workspace.project.id,
        web_endpoint="http://edge-agent.local:80",
        mcp_endpoint="http://edge-agent.local:9100/device-mcp",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        handshake=EspClawHandshake(
            storage_base_path="/fatfs",
            capabilities=(
                "lua_get_async_job",
                "lua_run_script_async",
                "lua_stop_async_job",
            ),
            file_readback_capable=True,
        ),
    )
    assert repaired_endpoint.status.value == "READY"
    assert repaired_endpoint.mcpEndpoint == "http://edge-agent.local:9100/device-mcp"


@pytest.mark.asyncio
async def test_httpx_adapter_handshake_uses_status_and_mcp_tools_list() -> None:
    requests: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/api/status":
            return httpx.Response(
                200,
                json={
                    "storage_base_path": "/fatfs",
                    "board_id": "dfrobot/dfrobot_k10",
                },
            )
        if request.url.path == "/api/files":
            assert request.url.params["path"] == "/"
            return httpx.Response(200, json=[])
        assert request.url.path == "/device-mcp"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "zhangwen",
                "result": {
                    "tools": [
                        {"name": "lua_run_script_async"},
                        {"name": "lua_get_async_job"},
                        {"name": "lua_stop_async_job"},
                    ]
                },
            },
        )

    adapter = HttpxEspClawDeploymentAdapter(httpx.MockTransport(handler))
    handshake = await adapter.handshake(
        "http://edge-agent.local:80",
        "http://edge-agent.local:9100/device-mcp",
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert handshake.storage_base_path == "/fatfs"
    assert handshake.file_readback_capable is True
    assert handshake.reported_board_id == "dfrobot/dfrobot_k10"
    assert requests == [
        ("GET", "edge-agent.local", "/api/status"),
        ("POST", "edge-agent.local", "/device-mcp"),
        ("GET", "edge-agent.local", "/api/files"),
    ]


@pytest.mark.asyncio
async def test_httpx_adapter_uses_official_web_file_methods_paths_and_raw_body() -> None:
    observed: list[tuple[str, str, str, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/files/upload":
            assert request.headers["content-type"] == "application/octet-stream"
        observed.append(
            (
                request.method,
                request.url.path,
                str(request.url.params.get("path", "")),
                request.content,
            )
        )
        if request.method == "GET":
            return httpx.Response(200, content=b"print('readback')\n")
        return httpx.Response(204)

    adapter = HttpxEspClawDeploymentAdapter(httpx.MockTransport(handler))
    cancel = asyncio.Event()
    endpoint = "http://edge-agent.local"
    directory = "/fatfs/scripts/zhangwen/project/v1"
    file_path = f"{directory}/main.lua"
    await adapter.make_directory(
        endpoint,
        directory,
        cancel=cancel,
        timeout_seconds=1,
    )
    await adapter.upload_file(
        endpoint,
        file_path,
        b"print('write')\n",
        cancel=cancel,
        timeout_seconds=1,
    )
    readback = await adapter.read_file(
        endpoint,
        file_path,
        cancel=cancel,
        timeout_seconds=1,
    )
    await adapter.delete_file(
        endpoint,
        file_path,
        cancel=cancel,
        timeout_seconds=1,
    )

    assert readback == b"print('readback')\n"
    assert observed[0][:3] == (
        "POST",
        "/api/files/mkdir",
        "",
    )
    assert observed[0][3] == b'{"path":"/scripts/zhangwen/project/v1","recursive":true}'
    assert observed[1] == (
        "POST",
        "/api/files/upload",
        "/scripts/zhangwen/project/v1/main.lua",
        b"print('write')\n",
    )
    assert observed[2] == (
        "GET",
        "/files/scripts/zhangwen/project/v1/main.lua",
        "",
        b"",
    )
    assert observed[3] == (
        "DELETE",
        "/api/files",
        "/scripts/zhangwen/project/v1/main.lua",
        b"",
    )


@pytest.mark.asyncio
async def test_httpx_adapter_calls_lua_with_managed_path_below_scripts_base() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(httpx.Response(200, content=request.content).json())
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "zhangwen",
                "result": {"structuredContent": {"job_id": "job-123"}},
            },
        )

    adapter = HttpxEspClawDeploymentAdapter(httpx.MockTransport(handler))
    job_id = await adapter.run_lua_script(
        "http://edge-agent.local:9100/device-mcp",
        "zhangwen/project/v1/main.lua",
        "zhangwen_deadbeef",
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert job_id == "job-123"
    assert captured == {
        "jsonrpc": "2.0",
        "id": "zhangwen",
        "method": "tools/call",
        "params": {
            "name": "lua_run_script_async",
            "arguments": {
                "path": "zhangwen/project/v1/main.lua",
                "name": "zhangwen_deadbeef",
                "exclusive": "zhangwen_deadbeef",
                "replace": True,
                "timeout_ms": 0,
            },
        },
    }


@pytest.mark.asyncio
async def test_httpx_adapter_stops_managed_job_by_stable_name() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(httpx.Response(200, content=request.content).json())
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "zhangwen",
                "result": {"structuredContent": {"status": "stopped"}},
            },
        )

    adapter = HttpxEspClawDeploymentAdapter(httpx.MockTransport(handler))
    await adapter.stop_async_job(
        "http://edge-agent.local:9100/device-mcp",
        "zhangwen_deadbeef",
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert captured["params"] == {
        "name": "lua_stop_async_job",
        "arguments": {"name": "zhangwen_deadbeef"},
    }


@pytest.mark.asyncio
async def test_httpx_adapter_treats_stopped_job_as_terminal_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "zhangwen",
                "result": {
                    "structuredContent": {
                        "job_id": "job-stopped",
                        "status": "stopped",
                    }
                },
            },
        )

    adapter = HttpxEspClawDeploymentAdapter(httpx.MockTransport(handler))
    job = await adapter.get_async_job(
        "http://edge-agent.local:9100/device-mcp",
        "job-stopped",
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert job.status == "stopped"
    assert job.ok is False


def test_unified_deploy_route_pairs_lists_and_deploys_espclaw(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "test-token")
    settings.data_dir = tmp_path
    adapter = FakeEspClawAdapter()
    devices_router.configure_device_transport(MockDeviceTransport())
    devices_router.configure_espclaw_adapter(adapter)
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/projects",
                json={"name": "ESP-Claw route", "initialIdea": "deploy Lua"},
            )
            assert created.status_code == 200
            project_id = str(created.json()["workspace"]["project"]["id"])
            _approve_project(
                ProjectRepository(tmp_path).db_path,
                project_id,
                SupportedDeviceBoardId.DFROBOT_K10,
            )
            code_run = _lua_code(project_id)

            class FakeCodeRepository:
                def __init__(self, _db_path: Path) -> None:
                    pass

                def get_current_code(self, value: str):
                    return code_run if value == project_id else None

                def get_code(self, value: str, code_run_id: str):
                    if value == project_id and code_run_id == code_run.id:
                        return code_run
                    raise ValueError("code run not found")

            monkeypatch.setattr("zhangwen.devices.service.CodeRepository", FakeCodeRepository)
            monkeypatch.setattr("zhangwen.devices.router.CodeRepository", FakeCodeRepository)
            paired = client.post(
                f"/api/projects/{project_id}/devices/esp-claw/endpoints/pair",
                headers=DESKTOP_HEADERS,
                json={
                    "webEndpoint": "http://edge-agent.local:80",
                    "mcpEndpoint": "http://edge-agent.local:9100/device-mcp",
                    "boardId": "dfrobot/dfrobot_k10",
                    "confirmTrustedLan": True,
                    "confirmAdminMode": True,
                    "confirmBoardIdentity": True,
                },
            )
            assert paired.status_code == 200
            paired_endpoint = paired.json()["endpoint"]
            endpoint_id = str(paired_endpoint["id"])
            assert paired_endpoint["webEndpoint"] == "http://edge-agent.local:80"
            assert paired_endpoint["mcpEndpoint"] == "http://edge-agent.local:9100/device-mcp"
            listed = client.get(
                f"/api/projects/{project_id}/devices/esp-claw/endpoints",
                headers=DESKTOP_HEADERS,
            )
            assert listed.status_code == 200
            assert listed.json()["endpoints"][0]["id"] == endpoint_id

            usb_dry_run = client.post(
                f"/api/projects/{project_id}/devices/deploy",
                headers=DESKTOP_HEADERS,
                json={
                    "channel": "USB_SERIAL",
                    "codeRunId": code_run.id,
                    "sessionId": "missing-serial-session",
                    "dryRun": True,
                },
            )
            assert usb_dry_run.status_code == 422
            assert usb_dry_run.json()["detail"]["code"] == "DEVICE_USB_RUNTIME_REQUIRED"
            legacy_usb_dry_run = client.post(
                f"/api/projects/{project_id}/devices/upload",
                headers=DESKTOP_HEADERS,
                json={
                    "codeRunId": code_run.id,
                    "sessionId": "missing-serial-session",
                    "dryRun": True,
                },
            )
            assert legacy_usb_dry_run.status_code == 422
            assert legacy_usb_dry_run.json()["detail"]["code"] == "DEVICE_USB_RUNTIME_REQUIRED"

            deployed = client.post(
                f"/api/projects/{project_id}/devices/deploy",
                headers=DESKTOP_HEADERS,
                json={
                    "channel": "ESP_CLAW",
                    "codeRunId": code_run.id,
                    "endpointId": endpoint_id,
                    "operationId": "espclaw_route_deploy_001",
                    "confirmWrite": True,
                },
            )
            assert deployed.status_code == 200
            operation_id = str(deployed.json()["operation"]["id"])
            operation: dict[str, object] = {}
            for _ in range(50):
                result = client.get(
                    f"/api/projects/{project_id}/devices/operations/{operation_id}"
                )
                assert result.status_code == 200
                operation = result.json()["operation"]
                if operation["status"] not in {"QUEUED", "RUNNING"}:
                    break
                time.sleep(0.005)
            assert operation["status"] == "COMPLETED"
            assert operation["metadata"]["channel"] == "ESP_CLAW"
    finally:
        devices_router.configure_espclaw_adapter(None)
        devices_router.configure_device_transport(None)


@pytest.mark.asyncio
async def test_pair_requires_all_trusted_lan_admin_and_board_confirmations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)

    with pytest.raises(DeviceServiceError) as captured:
        await service.pair_espclaw_endpoint(
            project_id=project_id,
            web_endpoint="http://edge-agent.local:80",
            mcp_endpoint="http://edge-agent.local:9100/device-mcp",
            board_id=SupportedDeviceBoardId.DFROBOT_K10,
            confirm_trusted_lan=True,
            confirm_admin_mode=False,
            confirm_board_identity=True,
        )

    assert captured.value.code == "ESP_CLAW_PAIR_CONFIRMATION_REQUIRED"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_pair_rejects_different_web_and_mcp_hosts_before_network_access(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)

    with pytest.raises(DeviceServiceError) as captured:
        await service.pair_espclaw_endpoint(
            project_id=project_id,
            web_endpoint="http://edge-a.local:80",
            mcp_endpoint="http://edge-b.local:9100/device-mcp",
            board_id=SupportedDeviceBoardId.DFROBOT_K10,
            confirm_trusted_lan=True,
            confirm_admin_mode=True,
            confirm_board_identity=True,
        )

    assert captured.value.code == "ESP_CLAW_ENDPOINT_HOST_MISMATCH"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_pair_rejects_board_outside_current_project_scene_without_remote_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)

    with pytest.raises(DeviceServiceError) as captured:
        await service.pair_espclaw_endpoint(
            project_id=project_id,
            web_endpoint="http://edge-agent.local:80",
            mcp_endpoint="http://edge-agent.local:9100/device-mcp",
            board_id=SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
            confirm_trusted_lan=True,
            confirm_admin_mode=True,
            confirm_board_identity=True,
        )

    assert captured.value.code == "ESP_CLAW_PROJECT_BOARD_MISMATCH"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_deploy_rejects_xiao_endpoint_for_k10_project_without_remote_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = DeviceRepository(service._db_path).pair_espclaw_endpoint(
        project_id=project_id,
        web_endpoint="http://edge-agent.local:80",
        mcp_endpoint="http://edge-agent.local:9100/device-mcp",
        board_id=SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
        handshake=EspClawHandshake(
            storage_base_path="/fatfs",
            capabilities=(
                "lua_get_async_job",
                "lua_run_script_async",
                "lua_stop_async_job",
            ),
            file_readback_capable=True,
        ),
    )

    with pytest.raises(DeviceServiceError) as captured:
        await service.start_espclaw_deployment(
            project_id=project_id,
            endpoint_id=endpoint.id,
            code_run_id="code_espclaw_lua",
            operation_id="espclaw_scene_mismatch_001",
            confirm_write=True,
        )

    assert captured.value.code == "ESP_CLAW_PROJECT_BOARD_MISMATCH"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_deploy_rejects_non_ready_endpoint_before_remote_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    with sqlite3.connect(service._db_path) as conn:
        conn.execute(
            "UPDATE espclaw_endpoints SET status = 'ERROR' WHERE id = ?",
            (endpoint.id,),
        )
    adapter.calls.clear()

    with pytest.raises(DeviceServiceError) as captured:
        await service.start_espclaw_deployment(
            project_id=project_id,
            endpoint_id=endpoint.id,
            code_run_id="code_espclaw_lua",
            operation_id="espclaw_endpoint_error_001",
            confirm_write=True,
        )

    assert captured.value.code == "ESP_CLAW_ENDPOINT_REPAIR_REQUIRED"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_espclaw_synthetic_session_never_enters_serial_paths_or_dry_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, serial_transport = _service(
        tmp_path,
        monkeypatch,
        adapter,
        _lua_code,
    )
    endpoint = await _pair(service, project_id)
    repository = DeviceRepository(service._db_path)
    session_id = repository.get_espclaw_session_id(project_id, endpoint.id)
    adapter.calls.clear()

    async_calls = (
        service.start_terminal(project_id, session_id),
        service.takeover_runtime(project_id, session_id),
        service.disconnect(project_id, session_id),
        service.start_upload(
            project_id=project_id,
            session_id=session_id,
            code_run_id="code_espclaw_lua",
            operation_id="synthetic_usb_upload_0001",
            confirm_write=True,
        ),
        service.start_parameter_sync(
            project_id=project_id,
            session_id=session_id,
            parameter_set_id="missing-parameter-set",
            operation_id="synthetic_param_sync_001",
            confirm_sync=True,
        ),
        service.start_firmware_flash(
            project_id=project_id,
            session_id=session_id,
            candidate_id=None,
            confirmation_token=None,
            operation_id="synthetic_flash_start_01",
            address=None,
            confirm_flash=False,
        ),
    )
    for call in async_calls:
        with pytest.raises(DeviceServiceError) as captured:
            await call
        assert captured.value.code == "DEVICE_USB_SERIAL_SESSION_REQUIRED"

    with pytest.raises(DeviceServiceError) as application_error:
        service.prepare_application_install(
            project_id=project_id,
            session_id=session_id,
            application_id="missing-application",
            board_id=SupportedDeviceBoardId.DFROBOT_K10,
            confirm_board_identity=True,
        )
    assert application_error.value.code == "DEVICE_USB_SERIAL_SESSION_REQUIRED"
    with pytest.raises(DeviceServiceError) as firmware_error:
        service.prepare_firmware(
            project_id=project_id,
            session_id=session_id,
            candidate_id="missing-candidate",
            address=0,
        )
    assert firmware_error.value.code == "DEVICE_USB_SERIAL_SESSION_REQUIRED"

    with pytest.raises(DeviceDeploymentSessionMismatch):
        repository.upload_code_dry_run(
            project_id=project_id,
            session_id=session_id,
            code_run=_python_code(project_id),
        )
    with pytest.raises(DeviceDeploymentSessionMismatch):
        repository.firmware_flash_dry_run(
            project_id=project_id,
            session_id=session_id,
        )

    assert serial_transport.calls == []
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_lua_deploy_uploads_reads_back_and_starts_without_flash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, serial_transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    adapter.calls.clear()

    operation, session = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_deploy_success_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    completed, returned_session = service.get_operation(project_id, operation.id)

    assert completed.kind == DeviceOperationKind.UPLOAD_CODE
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.metadata["channel"] == DeviceDeploymentChannel.ESP_CLAW.value
    assert completed.metadata["targetId"] == endpoint.id
    assert returned_session.id == session.id
    assert returned_session.portId == f"esp-claw:{endpoint.id}"
    assert [step.phase for step in completed.steps] == [
        DeviceOperationPhase.PREFLIGHT,
        DeviceOperationPhase.BACKUP,
        DeviceOperationPhase.TRANSFER,
        DeviceOperationPhase.VERIFY_FILES,
        DeviceOperationPhase.START_RUNTIME,
        DeviceOperationPhase.VERIFY_RUNTIME,
    ]
    assert any(name == "upload" for name, _ in adapter.calls)
    assert any(name == "run" for name, _ in adapter.calls)
    assert serial_transport.calls == []


@pytest.mark.asyncio
async def test_long_running_lua_job_is_successful_after_stable_running_probes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.job_statuses = ["running", "running"]
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_long_running_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    completed, _ = service.get_operation(project_id, operation.id)

    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.metadata["runtimeJobState"] == "running"
    assert completed.metadata["longRunning"] is True
    assert sum(name == "job" for name, _ in adapter.calls) == 2


@pytest.mark.asyncio
async def test_redeploy_uses_same_named_job_with_exclusive_replace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    for operation_id in ("espclaw_replace_first_001", "espclaw_replace_second_01"):
        operation, _ = await service.start_espclaw_deployment(
            project_id=project_id,
            endpoint_id=endpoint.id,
            code_run_id="code_espclaw_lua",
            operation_id=operation_id,
            confirm_write=True,
        )
        await service.wait(operation.id)
        completed, _ = service.get_operation(project_id, operation.id)
        assert completed.status == DeviceOperationStatus.COMPLETED

    assert len(adapter.run_requests) == 2
    assert adapter.run_requests[0]["name"] == adapter.run_requests[1]["name"]
    assert all(item["exclusive"] == item["name"] for item in adapter.run_requests)
    assert all(item["replace"] is True for item in adapter.run_requests)
    assert all(item["timeout_ms"] == 0 for item in adapter.run_requests)


@pytest.mark.asyncio
async def test_endpoint_aliases_share_one_project_stable_managed_job_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    first = await _pair(service, project_id)
    second = await service.pair_espclaw_endpoint(
        project_id=project_id,
        web_endpoint="http://192.168.20.8:80",
        mcp_endpoint="http://192.168.20.8:9100/device-mcp",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        confirm_trusted_lan=True,
        confirm_admin_mode=True,
        confirm_board_identity=True,
    )
    assert first.id != second.id
    adapter.calls.clear()

    for endpoint, operation_id in (
        (first, "espclaw_alias_first_0001"),
        (second, "espclaw_alias_second_001"),
    ):
        operation, _ = await service.start_espclaw_deployment(
            project_id=project_id,
            endpoint_id=endpoint.id,
            code_run_id="code_espclaw_lua",
            operation_id=operation_id,
            confirm_write=True,
        )
        await service.wait(operation.id)
        completed, _ = service.get_operation(project_id, operation.id)
        assert completed.status == DeviceOperationStatus.COMPLETED

    assert len(adapter.run_requests) == 2
    assert adapter.run_requests[0]["name"] == adapter.run_requests[1]["name"]
    assert all(item["exclusive"] == item["name"] for item in adapter.run_requests)
    assert all(item["replace"] is True for item in adapter.run_requests)


@pytest.mark.asyncio
async def test_micropython_coderun_is_rejected_before_any_espclaw_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _python_code)
    endpoint = await _pair(service, project_id)
    adapter.calls.clear()

    with pytest.raises(DeviceServiceError) as captured:
        await service.start_espclaw_deployment(
            project_id=project_id,
            endpoint_id=endpoint.id,
            code_run_id="code_micropython",
            operation_id="espclaw_python_rejected_01",
            confirm_write=True,
        )

    assert captured.value.code == "ESP_CLAW_CODE_RUNTIME_REQUIRED"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_lost_readback_capability_fails_preflight_before_remote_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    adapter.calls.clear()
    adapter.readback_capable = False

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_readback_lost_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    completed, _ = service.get_operation(project_id, operation.id)

    assert completed.status == DeviceOperationStatus.FAILED
    assert completed.errorCode == "ESP_CLAW_FILE_READBACK_UNAVAILABLE"
    assert [name for name, _ in adapter.calls] == ["handshake"]


@pytest.mark.asyncio
async def test_lost_board_identity_handshake_fails_preflight_before_remote_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    adapter.calls.clear()
    adapter.reported_board_id = None

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_board_identity_lost_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    failed, _ = service.get_operation(project_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "ESP_CLAW_BOARD_IDENTITY_REQUIRED"
    assert [name for name, _ in adapter.calls] == ["handshake"]


@pytest.mark.asyncio
async def test_hash_mismatch_restores_previous_file_content(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    adapter.corrupt_next_readback = True

    operation, _session = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_hash_rollback_001",
        confirm_write=True,
    )
    entrypoint = str(operation.metadata["remoteEntrypoint"])
    adapter.storage[entrypoint] = b"previous-version"
    await service.wait(operation.id)
    completed, _ = service.get_operation(project_id, operation.id)

    assert completed.status == DeviceOperationStatus.FAILED
    assert completed.errorCode == "ESP_CLAW_HASH_MISMATCH"
    assert completed.metadata["rollbackOk"] is True
    assert adapter.storage[entrypoint] == b"previous-version"
    assert any(name == "upload" and path == entrypoint for name, path in adapter.calls)
    assert not any(name == "run" for name, _ in adapter.calls)


@pytest.mark.asyncio
async def test_cancel_rolls_back_remote_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.block_upload = True
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_cancel_rollback_01",
        confirm_write=True,
    )
    for _ in range(100):
        if any(name == "upload" for name, _ in adapter.calls):
            break
        await asyncio.sleep(0.001)
    canceled, _ = await service.cancel_operation(project_id, operation.id)

    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.metadata["rollbackOk"] is True
    assert str(operation.metadata["remoteEntrypoint"]) not in adapter.storage


@pytest.mark.asyncio
async def test_cancel_after_runtime_start_stops_job_before_file_rollback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.job_statuses = ["running", "waiting"]
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    adapter.calls.clear()

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_cancel_running_001",
        confirm_write=True,
    )
    for _ in range(200):
        if any(name == "job" for name, _ in adapter.calls):
            break
        await asyncio.sleep(0.001)
    canceled, _ = await service.cancel_operation(project_id, operation.id)

    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.metadata["runtimeStopOk"] is True
    assert canceled.metadata["rollbackOk"] is True
    stop_index = next(index for index, call in enumerate(adapter.calls) if call[0] == "stop")
    rollback_index = next(
        index
        for index, call in enumerate(adapter.calls)
        if call[0] in {"delete", "upload"} and index > stop_index
    )
    assert stop_index < rollback_index


@pytest.mark.asyncio
async def test_runtime_failure_stops_job_then_restores_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.job_statuses = ["failed"]
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_runtime_failure_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    failed, _ = service.get_operation(project_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "ESP_CLAW_RUNTIME_FAILED"
    assert failed.metadata["runtimeStopOk"] is True
    assert failed.metadata["rollbackOk"] is True
    assert any(name == "stop" for name, _ in adapter.calls)


@pytest.mark.asyncio
async def test_runtime_timeout_stops_job_then_restores_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.job_statuses = ["waiting"]
    service, project_id, _transport = _service(
        tmp_path,
        monkeypatch,
        adapter,
        _lua_code,
        upload_timeout_seconds=0.05,
    )
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_runtime_timeout_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    timed_out, _ = service.get_operation(project_id, operation.id)

    assert timed_out.status == DeviceOperationStatus.TIMED_OUT
    assert timed_out.errorCode == "ESP_CLAW_DEPLOYMENT_TIMEOUT"
    assert timed_out.metadata["runtimeStopOk"] is True
    assert timed_out.metadata["rollbackOk"] is True
    assert any(name == "stop" for name, _ in adapter.calls)


@pytest.mark.asyncio
async def test_unconfirmed_runtime_stop_is_reported_as_emergency_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.job_statuses = ["failed"]
    adapter.stop_fails = True
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_stop_unconfirmed_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    failed, session = service.get_operation(project_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "ESP_CLAW_EMERGENCY_STOP_UNCONFIRMED"
    assert failed.metadata["runtimeStopOk"] is False
    assert session.status == DeviceSessionStatus.ERROR
    assert "do not retry" in failed.log.casefold()
    assert failed.verification is not None
    assert any("emergency stop" in warning.casefold() for warning in failed.verification.warnings)


@pytest.mark.asyncio
async def test_unknown_runtime_stop_status_never_restores_ready_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.job_statuses = ["failed"]
    adapter.stop_status = "future-unknown-state"
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_unknown_stop_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    failed, session = service.get_operation(project_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "ESP_CLAW_EMERGENCY_STOP_UNCONFIRMED"
    assert failed.metadata["runtimeStopOk"] is False
    assert session.status == DeviceSessionStatus.ERROR
    assert sum(name == "job-name" for name, _ in adapter.calls) == 3
    assert any(
        "last state=future-unknown-state" in step.summary
        for step in failed.steps
        if step.phase == DeviceOperationPhase.RESTORE
    ) or "future-unknown-state" in failed.log


@pytest.mark.asyncio
async def test_restore_failure_never_claims_files_were_restored(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.corrupt_next_readback = True
    adapter.restore_failure_content = b"previous-version"
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_restore_failure_001",
        confirm_write=True,
    )
    adapter.storage[str(operation.metadata["remoteEntrypoint"])] = b"previous-version"
    await service.wait(operation.id)
    failed, session = service.get_operation(project_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.metadata["rollbackOk"] is False
    assert session.status == DeviceSessionStatus.ERROR
    assert "rollback was not confirmed" in failed.log.casefold()
    assert "files were restored" not in failed.log.casefold()
    assert failed.verification is not None
    assert any("file rollback" in warning.casefold() for warning in failed.verification.warnings)


@pytest.mark.asyncio
async def test_restore_http_success_requires_matching_readback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.corrupt_next_readback = True
    adapter.silent_restore_mismatch_content = b"previous-version"
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)

    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_restore_readback_001",
        confirm_write=True,
    )
    adapter.storage[str(operation.metadata["remoteEntrypoint"])] = b"previous-version"
    await service.wait(operation.id)
    failed, session = service.get_operation(project_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.metadata["rollbackOk"] is False
    assert session.status == DeviceSessionStatus.ERROR
    last_restore_upload = max(
        index
        for index, (name, _path) in enumerate(adapter.calls)
        if name == "upload"
    )
    assert any(
        index > last_restore_upload and name == "read"
        for index, (name, _path) in enumerate(adapter.calls)
    )
    assert "rollback was not confirmed" in failed.log.casefold()
    assert failed.verification is not None
    assert any("file rollback" in warning.casefold() for warning in failed.verification.warnings)


@pytest.mark.asyncio
async def test_slow_cancel_cleanup_is_not_force_canceled_after_three_seconds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.block_upload = True
    adapter.delete_delay_seconds = 3.1
    service, project_id, _transport = _service(
        tmp_path,
        monkeypatch,
        adapter,
        _lua_code,
        upload_timeout_seconds=10,
    )
    endpoint = await _pair(service, project_id)
    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_slow_cancel_cleanup_001",
        confirm_write=True,
    )
    for _ in range(100):
        if any(name == "upload" for name, _ in adapter.calls):
            break
        await asyncio.sleep(0.001)

    cancel_snapshot, _ = await service.cancel_operation(project_id, operation.id)
    assert cancel_snapshot.status in {
        DeviceOperationStatus.RUNNING,
        DeviceOperationStatus.CANCELED,
    }
    await service.wait(operation.id)
    canceled, _ = service.get_operation(project_id, operation.id)

    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.metadata["rollbackOk"] is True
    assert "restored" in canceled.log.casefold() or "removed" in canceled.log.casefold()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "poll"])
async def test_orphaned_espclaw_operation_never_reports_fake_cancellation(
    tmp_path: Path,
    monkeypatch,
    action: str,
) -> None:
    adapter = FakeEspClawAdapter()
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    repository = DeviceRepository(service._db_path)
    session_id = repository.get_espclaw_session_id(project_id, endpoint.id)
    operation_id = f"espclaw_orphan_{action}_0001"
    repository.reserve_operation(
        project_id=project_id,
        session_id=session_id,
        operation_id=operation_id,
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="ESP-Claw Web Console + MCP Lua",
        log=_operation_state(DeviceDeploymentChannel.ESP_CLAW),
        fingerprint="test",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )
    adapter.calls.clear()

    if action == "cancel":
        failed, session = await service.cancel_operation(project_id, operation_id)
    else:
        failed, session = service.get_operation(project_id, operation_id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.status != DeviceOperationStatus.CANCELED
    assert failed.errorCode == "ESP_CLAW_EMERGENCY_STOP_UNCONFIRMED"
    assert failed.metadata["runtimeStopOk"] is False
    assert failed.metadata["orphanedExecution"] is True
    assert session.status == DeviceSessionStatus.ERROR
    assert failed.verification is not None
    assert any("emergency stop" in item.casefold() for item in failed.verification.warnings)
    assert "manually stop actuators" in failed.log.casefold()
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_shutdown_cancels_espclaw_through_stop_and_rollback_before_return(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FakeEspClawAdapter()
    adapter.block_runtime_start = True
    service, project_id, _transport = _service(tmp_path, monkeypatch, adapter, _lua_code)
    endpoint = await _pair(service, project_id)
    adapter.calls.clear()
    operation, _ = await service.start_espclaw_deployment(
        project_id=project_id,
        endpoint_id=endpoint.id,
        code_run_id="code_espclaw_lua",
        operation_id="espclaw_shutdown_cleanup_01",
        confirm_write=True,
    )
    for _ in range(300):
        if any(name == "run" for name, _ in adapter.calls):
            break
        await asyncio.sleep(0.001)
    assert any(name == "run" for name, _ in adapter.calls)

    await service.shutdown()
    canceled, session = service.get_operation(project_id, operation.id)

    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.metadata["runtimeStopOk"] is True
    assert canceled.metadata["rollbackOk"] is True
    assert session.status == DeviceSessionStatus.READY
    stop_index = next(index for index, call in enumerate(adapter.calls) if call[0] == "stop")
    rollback_index = next(
        index
        for index, call in enumerate(adapter.calls)
        if call[0] in {"delete", "upload"} and index > stop_index
    )
    assert stop_index < rollback_index
    assert operation.id not in service._tasks


def test_espclaw_and_serial_operations_hold_a_project_wide_mutual_exclusion_lease(
    tmp_path: Path,
) -> None:
    project_repository = ProjectRepository(tmp_path)
    workspace = project_repository.create_project_from_idea(
        idea="exclusive device operation test",
        project_name="exclusive device operation",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    project_id = workspace.project.id
    repository = DeviceRepository(project_repository.db_path)
    serial_session = repository.connect_mock_port(project_id, "mock_port_esp32_s3")
    endpoint = repository.pair_espclaw_endpoint(
        project_id=project_id,
        web_endpoint="http://edge-agent.local:80",
        mcp_endpoint="http://edge-agent.local:9100/device-mcp",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        handshake=EspClawHandshake(
            storage_base_path="/fatfs",
            capabilities=(
                "lua_get_async_job",
                "lua_run_script_async",
                "lua_stop_async_job",
            ),
            file_readback_capable=True,
        ),
    )
    assert repository.get_current_session(project_id).id == serial_session.id
    claw_session_id = repository.get_espclaw_session_id(project_id, endpoint.id)
    serial_state = _operation_state(DeviceDeploymentChannel.USB_SERIAL)
    repository.reserve_operation(
        project_id=project_id,
        session_id=serial_session.id,
        operation_id="serial_active_operation_001",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="mpremote",
        log=serial_state,
        fingerprint="serial-fingerprint",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )

    with pytest.raises(DeviceProjectLeaseBusy):
        repository.reserve_operation(
            project_id=project_id,
            session_id=claw_session_id,
            operation_id="claw_blocked_operation_001",
            kind=DeviceOperationKind.UPLOAD_CODE,
            command_label="ESP-Claw Web Console + MCP Lua",
            log=_operation_state(DeviceDeploymentChannel.ESP_CLAW),
            fingerprint="claw-blocked",
            claimed_status=DeviceSessionStatus.UPLOADING,
        )

    repository.update_operation(
        project_id,
        "serial_active_operation_001",
        status=DeviceOperationStatus.COMPLETED,
        log=serial_state,
        completed_at=datetime.now(UTC).isoformat(),
    )
    repository.set_session_status(project_id, serial_session.id, DeviceSessionStatus.READY)
    repository.reserve_operation(
        project_id=project_id,
        session_id=claw_session_id,
        operation_id="claw_active_operation_001",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="ESP-Claw Web Console + MCP Lua",
        log=_operation_state(DeviceDeploymentChannel.ESP_CLAW),
        fingerprint="claw-active",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )

    with pytest.raises(DeviceProjectLeaseBusy):
        repository.reserve_operation(
            project_id=project_id,
            session_id=serial_session.id,
            operation_id="serial_blocked_operation_001",
            kind=DeviceOperationKind.FLASH_FIRMWARE,
            command_label="esptool write-flash",
            log=serial_state,
            fingerprint="serial-blocked",
            claimed_status=DeviceSessionStatus.UPLOADING,
        )


async def _pair(service: DeviceOperationService, project_id: str):
    return await service.pair_espclaw_endpoint(
        project_id=project_id,
        web_endpoint="http://edge-agent.local:80",
        mcp_endpoint="http://edge-agent.local:9100/device-mcp",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        confirm_trusted_lan=True,
        confirm_admin_mode=True,
        confirm_board_identity=True,
    )


def _service(
    tmp_path,
    monkeypatch,
    adapter,
    code_factory,
    *,
    upload_timeout_seconds: float = 2,
):
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP-Claw deployment test",
        project_name="ESP-Claw deployment",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    _approve_project(
        repository.db_path,
        workspace.project.id,
        SupportedDeviceBoardId.DFROBOT_K10,
    )
    code_run = code_factory(workspace.project.id)

    class FakeCodeRepository:
        def __init__(self, _db_path: Path) -> None:
            pass

        def get_current_code(self, project_id: str):
            return code_run if project_id == code_run.projectId else None

    monkeypatch.setattr("zhangwen.devices.service.CodeRepository", FakeCodeRepository)
    transport = MockDeviceTransport()
    service = DeviceOperationService(
        repository.db_path,
        tmp_path,
        transport,
        command_timeout_seconds=0.5,
        upload_timeout_seconds=upload_timeout_seconds,
        flash_timeout_seconds=2,
        espclaw_adapter=adapter,
        espclaw_poll_interval_seconds=0.001,
    )
    return service, workspace.project.id, transport


def _approve_project(
    db_path: Path,
    project_id: str,
    board_id: SupportedDeviceBoardId,
) -> None:
    board_name = (
        "XIAO ESP32S3 Sense"
        if board_id == SupportedDeviceBoardId.XIAO_ESP32S3_SENSE
        else "DFRobot K10"
    )
    solutions = SolutionRepository(db_path)
    solution = solutions.create_solution(
        project_id,
        [
            SolutionSection(
                id="recommended_implementation",
                title="Recommended implementation",
                content=f"Use {board_name} as the only controller.",
            )
        ],
    )
    solution = solutions.confirm_solution(project_id, solution.id)
    proposals = ProposalRepository(db_path)
    proposal = proposals.create_proposal(
        project_id=project_id,
        solution=solution,
        sections=[
            ProposalSection(
                id=section_id,
                title=section_id.replace("_", " ").title(),
                content=f"The confirmed project uses {board_name} as its only controller.",
            )
            for section_id in (
                "project_overview",
                "requirements",
                "hardware_software_structure",
                "implementation_plan",
                "cost_difficulty_schedule",
                "risks_acceptance",
            )
        ],
        supersede_drafts=True,
    )
    proposals.confirm_proposal(project_id, proposal.id)


def _lua_code(project_id: str) -> CodeRun:
    return _code_run(
        project_id,
        code_run_id="code_espclaw_lua",
        runtime=CodeRuntime.ESP_CLAW_LUA,
        entrypoint="scripts/main.lua",
        path="scripts/main.lua",
        language="lua",
        content="return { ok = true }\n",
    )


def _python_code(project_id: str) -> CodeRun:
    return _code_run(
        project_id,
        code_run_id="code_micropython",
        runtime=CodeRuntime.MICROPYTHON,
        entrypoint="src/main.py",
        path="src/main.py",
        language="python",
        content="print('ok')\n",
    )


def _code_run(
    project_id: str,
    *,
    code_run_id: str,
    runtime: CodeRuntime,
    entrypoint: str,
    path: str,
    language: str,
    content: str,
) -> CodeRun:
    now = datetime.now(UTC).isoformat()
    return CodeRun(
        id=code_run_id,
        projectId=project_id,
        specRunId=None,
        version=1,
        status=CodeRunStatus.ACCEPTED,
        runtime=runtime,
        entrypoint=entrypoint,
        workspaceRoot=f"workspace://{project_id}/code/v1",
        maxRetries=0,
        retries=0,
        files=[
            CodeFile(
                id=f"file_{code_run_id}",
                codeRunId=code_run_id,
                projectId=project_id,
                kind=CodeFileKind.MAIN,
                path=path,
                language=language,
                content=content,
                createdAt=now,
            )
        ],
        patch=CodePatch(
            id=f"patch_{code_run_id}",
            codeRunId=code_run_id,
            projectId=project_id,
            summary="test",
            diff="",
            createdAt=now,
        ),
        testResult=CodeTestResult(
            ok=True,
            command="local-lua-validation",
            output="passed",
            createdAt=now,
            checks=[],
        ),
        createdAt=now,
        updatedAt=now,
        acceptedAt=now,
    )


def _operation_state(channel: DeviceDeploymentChannel) -> str:
    return (
        '{"schema":"device-operation/v1","log":"queued","phase":"QUEUED",'
        '"progress":0,"errorCode":null,"steps":[],"backup":null,'
        '"verification":null,"cancelable":true,"metadata":'
        f'{{"channel":"{channel.value}","fingerprint":"test"}}}}'
    )
