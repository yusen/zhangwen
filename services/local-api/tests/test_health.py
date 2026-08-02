"""健康检查端点测试"""

from fastapi.testclient import TestClient
import pytest

from zhangwen.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """GET /api/health 返回 200"""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_response_structure() -> None:
    """健康检查响应包含 status、version、uptimeSeconds"""
    response = client.get("/api/health")
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "uptimeSeconds" in data
    assert data["status"] == "ok"
    assert isinstance(data["version"], str)
    assert isinstance(data["uptimeSeconds"], (int, float))
    assert data["llmTestMode"] == "standard"
    assert data["usesPaidLlm"] is True


def test_desktop_capability_health_requires_matching_token(monkeypatch) -> None:
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "health-test-token")
    accepted = client.get(
        "/api/health/desktop-capability",
        headers={
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": "health-test-token",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "ok", "desktopCapability": True}

    rejected = client.get(
        "/api/health/desktop-capability",
        headers={
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": "wrong-token",
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "DESKTOP_CAPABILITY_MISMATCH"
    assert "重新启动应用" in rejected.json()["detail"]["message"]


def test_health_reports_explicit_paid_and_fake_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZHANGWEN_LLM_TEST_MODE", "paid")
    paid = client.get("/api/health").json()
    assert paid["llmTestMode"] == "paid"
    assert paid["usesPaidLlm"] is True

    monkeypatch.setenv("ZHANGWEN_LLM_TEST_MODE", "fake")
    fake = client.get("/api/health").json()
    assert fake["llmTestMode"] == "fake"
    assert fake["usesPaidLlm"] is False
