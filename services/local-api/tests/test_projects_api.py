from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app


def test_project_api_lifecycle(tmp_path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    create = client.post(
        "/api/projects",
        json={
            "name": "自动浇花",
            "initialIdea": "想做自动浇花",
            "selectedModel": "deepseek-v4-pro",
        },
    )
    assert create.status_code == 200
    workspace = create.json()["workspace"]
    project_id = workspace["project"]["id"]
    assert workspace["project"]["name"] == "自动浇花"
    assert workspace["project"]["selectedModel"] == "deepseek-v4-pro"

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert listed.json()["activeProjectId"] == project_id
    assert listed.json()["projects"][0]["id"] == project_id

    draft = client.put(
        f"/api/projects/{project_id}/draft",
        json={"content": "未发送草稿"},
    )
    assert draft.status_code == 200
    assert draft.json()["workspace"]["draft"]["content"] == "未发送草稿"

    patched = client.patch(
        f"/api/projects/{project_id}",
        json={"name": "自动浇花 v2", "selectedModel": "deepseek-v4-flash"},
    )
    assert patched.status_code == 200
    assert patched.json()["workspace"]["project"]["name"] == "自动浇花 v2"
    assert patched.json()["workspace"]["project"]["selectedModel"] == "deepseek-v4-flash"

    opened = client.post(f"/api/projects/{project_id}/open")
    assert opened.status_code == 200
    assert opened.json()["workspace"]["project"]["lastOpenedAt"] is not None

    archived = client.post(
        f"/api/projects/{project_id}/archive",
        json={"archived": True},
    )
    assert archived.status_code == 200
    assert archived.json()["projects"] == []

    archived_list = client.get("/api/projects?includeArchived=true")
    assert archived_list.status_code == 200
    assert archived_list.json()["projects"][0]["id"] == project_id
    assert archived_list.json()["projects"][0]["archivedAt"] is not None

    restored = client.post(f"/api/projects/{project_id}/restore", json={})
    assert restored.status_code == 200
    assert restored.json()["activeProjectId"] == project_id
    assert restored.json()["projects"][0]["id"] == project_id

    restored_workspace = client.get(f"/api/projects/{project_id}")
    assert restored_workspace.status_code == 200
    assert restored_workspace.json()["workspace"]["draft"]["content"] == "未发送草稿"
    assert restored_workspace.json()["workspace"]["conversation"]["messages"][0]["content"] == (
        "想做自动浇花"
    )


def test_project_api_returns_structured_error(tmp_path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    response = client.get("/api/projects/prj_missing")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


def test_project_api_round_trips_custom_provider_model(tmp_path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    created = client.post(
        "/api/projects",
        json={
            "name": "自定义模型项目",
            "initialIdea": "验证自定义模型进入项目运行时",
            "selectedModel": "kimi-preview-custom",
        },
    )

    assert created.status_code == 200
    project_id = created.json()["workspace"]["project"]["id"]
    reloaded = client.get(f"/api/projects/{project_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["workspace"]["project"]["selectedModel"] == "kimi-preview-custom"
