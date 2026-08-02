from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.llm.contracts import LLMModelId, LLMProviderId
from zhangwen.llm.runtime import require_llm_config
from zhangwen.main import app
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.security.credentials import MemoryCredentialStore
from zhangwen.settings import router as settings_router


def test_local_cors_allows_only_required_local_ui_origins() -> None:
    client = TestClient(app)
    for origin in (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://tauri.localhost",
        "tauri://localhost",
    ):
        response = client.options(
            "/api/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": (
                    "X-Zhangwen-Host, X-Zhangwen-Capability-Token"
                ),
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin

    blocked = client.options(
        "/api/health",
        headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
    )
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


def test_web_host_cannot_call_local_device_or_cad_execution(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="Web capability gate",
        project_name="Web 项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    project_id = workspace.project.id
    client = TestClient(app)
    headers = {"X-Zhangwen-Host": "web"}

    requests = [
        client.get(f"/api/projects/{project_id}/devices/ports", headers=headers),
        client.post(
            f"/api/projects/{project_id}/devices/connect",
            headers=headers,
            json={"portId": "mock-com3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
        ),
        client.post(
            f"/api/projects/{project_id}/devices/upload",
            headers=headers,
            json={"codeRunId": "code_none", "sessionId": "session_none", "dryRun": True},
        ),
        client.post(
            f"/api/projects/{project_id}/devices/flash",
            headers=headers,
            json={"sessionId": "session_none", "dryRun": True, "confirmFlash": True},
        ),
        client.post(
            f"/api/projects/{project_id}/cad/generate",
            headers=headers,
            json={"specRunId": "spec_none"},
        ),
    ]

    assert [response.status_code for response in requests] == [409, 409, 409, 409, 409]
    assert all(
        response.json()["detail"]["code"] == "HOST_CAPABILITY_UNAVAILABLE"
        for response in requests
    )
    origin_only = client.get(
        f"/api/projects/{project_id}/devices/ports",
        headers={"Origin": "http://localhost:5173"},
    )
    assert origin_only.status_code == 409
    assert origin_only.json()["detail"]["code"] == "HOST_CAPABILITY_UNAVAILABLE"
    with repository._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM device_sessions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM device_operations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cad_runs").fetchone()[0] == 0


def test_tauri_header_without_runtime_token_cannot_call_device_scan(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "expected-token")
    workspace = ProjectRepository(tmp_path).create_project_from_idea(
        idea="Desktop capability token",
        project_name="Token 项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    client = TestClient(app)

    missing = client.get(
        f"/api/projects/{workspace.project.id}/devices/ports",
        headers={"X-Zhangwen-Host": "tauri"},
    )
    forged = client.get(
        f"/api/projects/{workspace.project.id}/devices/ports",
        headers={
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": "wrong-token",
        },
    )
    secret_forged = client.put(
        "/api/settings/llm",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": "wrong-token",
        },
        json={"apiKey": "fake-forged-key"},
    )

    assert missing.status_code == 409
    assert forged.status_code == 409
    assert secret_forged.status_code == 409
    assert missing.json()["detail"]["code"] == "DESKTOP_CAPABILITY_MISMATCH"
    assert forged.json()["detail"]["code"] == "DESKTOP_CAPABILITY_MISMATCH"
    assert secret_forged.json()["detail"]["code"] == "DESKTOP_CAPABILITY_MISMATCH"
    assert "重新启动应用" in missing.json()["detail"]["message"]


def test_web_host_cannot_submit_provider_key() -> None:
    response = TestClient(app).put(
        "/api/settings/llm",
        headers={"X-Zhangwen-Host": "web"},
        json={"apiKey": "fake-browser-key"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "WEB_PROVIDER_KEY_BLOCKED"


def test_tauri_vite_origin_can_save_qwen_for_chat_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "expected-token")
    credentials = MemoryCredentialStore()
    monkeypatch.setattr(
        settings_router,
        "BackendCredentialStore",
        lambda: credentials,
    )

    response = TestClient(app).put(
        "/api/settings/llm",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": "expected-token",
        },
        json={
            "provider": "qwen",
            "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "defaultModel": "qwen3.7-max",
            "apiKey": "fake-qwen-key",
        },
    )

    assert response.status_code == 200
    assert response.json()["config"]["provider"] == LLMProviderId.QWEN
    assert response.json()["config"]["keySaved"] is True
    config, api_key = require_llm_config(
        data_dir=tmp_path,
        credential_store=credentials,
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
    )
    assert config.provider == LLMProviderId.QWEN
    assert config.defaultModel == LLMModelId.QWEN_3_7_MAX
    assert api_key == "fake-qwen-key"
