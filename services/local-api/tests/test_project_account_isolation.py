from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


def _register(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "displayName": username,
            "password": "ProjectPass123",
        },
    )
    assert response.status_code == 201
    return response.json()["sessionToken"]


def _create_project(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "initialIdea": "做一个自动浇花装置"},
    )
    assert response.status_code == 200
    return response.json()["workspace"]["project"]["id"]


def test_two_accounts_cannot_list_open_or_archive_each_others_projects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_AUTH_DISABLED", raising=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with TestClient(app) as client:
        first = _register(client, "owner_one")
        second = _register(client, "owner_two")
        first_project = _create_project(client, first, "账号一的项目")
        second_project = _create_project(client, second, "账号二的项目")

        first_headers = {"Authorization": f"Bearer {first}"}
        second_headers = {"Authorization": f"Bearer {second}"}
        assert [
            item["id"] for item in client.get("/api/projects", headers=first_headers).json()["projects"]
        ] == [first_project]
        assert [
            item["id"] for item in client.get("/api/projects", headers=second_headers).json()["projects"]
        ] == [second_project]

        assert client.get(
            f"/api/projects/{first_project}", headers=second_headers
        ).status_code == 404
        assert client.post(
            f"/api/projects/{first_project}/archive",
            headers=second_headers,
            json={"archived": True},
        ).status_code == 404
        assert client.get(
            f"/api/projects/{first_project}/artifacts",
            headers=second_headers,
        ).status_code == 404
        assert client.get(
            f"/api/projects/{first_project}/devices/ports",
            headers=second_headers,
        ).status_code == 404
        assert client.get(
            f"/api/projects/{first_project}", headers=first_headers
        ).status_code == 200


def test_legacy_projects_are_hidden_until_one_account_claims_them(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    legacy_project = ProjectRepository(tmp_path).create_project(
        "旧设备项目",
        "旧版本创建的项目",
    )
    monkeypatch.delenv("ZHANGWEN_AUTH_DISABLED", raising=False)

    with TestClient(app) as client:
        first = _register(client, "claim_one")
        second = _register(client, "claim_two")
        first_headers = {"Authorization": f"Bearer {first}"}
        second_headers = {"Authorization": f"Bearer {second}"}

        assert client.get("/api/projects", headers=first_headers).json()["projects"] == []
        status = client.get(
            "/api/projects/legacy-claim/status", headers=first_headers
        )
        assert status.json() == {
            "unclaimedProjectCount": 1,
            "decisionRecorded": False,
        }
        deferred = client.post(
            "/api/projects/legacy-claim",
            headers=first_headers,
            json={"claimAll": False},
        )
        assert deferred.json()["claimedProjectCount"] == 0

        claimed = client.post(
            "/api/projects/legacy-claim",
            headers=second_headers,
            json={"claimAll": True},
        )
        assert claimed.json()["claimedProjectCount"] == 1
        assert client.get(
            f"/api/projects/{legacy_project.project.id}", headers=first_headers
        ).status_code == 404
        assert client.get(
            f"/api/projects/{legacy_project.project.id}", headers=second_headers
        ).status_code == 200
