from __future__ import annotations

import hashlib
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from zhangwen.mu_web.app import create_app
from zhangwen.mu_web.app import generate_reply
from zhangwen.mu_web.models import ChatInput


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ZHANGWEN_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ZHANGWEN_MU_MODEL", raising=False)
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:3080") as client:
        token = client.get("/api/session").json()["token"]
        client.headers.update({"origin": "http://127.0.0.1:3080", "x-mu-session": token})
        yield client


def new_project(client: TestClient):
    board = next(item for item in client.get("/api/hardware").json()["skills"] if item["category"] == "MCU")
    response = client.post("/api/projects", json={"name": "测试工程", "boardId": board["componentId"]})
    assert response.status_code == 201, response.text
    return response.json()


def save_payload(project: dict, **changes):
    return {"name": project["name"], "code": project["code"], "boardId": project["boardId"],
            "componentIds": project["componentIds"], "expectedRevision": project["revision"], **changes}


def test_library_comes_from_preserved_packages_with_media(client):
    skills = client.get("/api/hardware").json()["skills"]
    assert len(skills) == 74
    assert sum(item["category"] == "SENSOR" for item in skills) == 54
    assert {item["componentId"] for item in skills} >= {"hw_seed_unihiker_k10", "hw_seeed_xiao_esp32s3_sense"}
    for skill in skills:
        detail = client.get("/api/hardware/" + skill["skillName"])
        assert detail.status_code == 200
        assert detail.json()["revision"] == skill["revision"]
        assert detail.json()["files"]
        for asset in skill["media"]:
            media = client.get(asset["url"])
            assert media.status_code == 200, asset["url"]
            assert hashlib.sha256(media.content).hexdigest() == asset["sha256"]


def test_release_catalog_is_complete_and_preserves_user_packages(client):
    from zhangwen.mu_web.hardware import RELEASE_CATALOG
    repo = client.app.state.repo.skills
    assert len(list(RELEASE_CATALOG.iterdir())) == 74
    source_manifest = json.loads((RELEASE_CATALOG.parents[1] / "docs/hardware-import-snapshot.json").read_text(encoding="utf-8"))
    assert len(source_manifest["files"]) == 817
    for item in source_manifest["files"]:
        assert hashlib.sha256((RELEASE_CATALOG / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert len(repo.list_skills(include_archived=True)) == 76
    # Local supplementary notes survive subsequent launches.
    package = repo.root / "labplus-mpython-v2"
    note = package / "README.md"
    original = note.read_text(encoding="utf-8") if note.exists() else ""
    note.write_text(original + "\n本机备注\n", encoding="utf-8")
    before = {p.relative_to(repo.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in repo.root.rglob("*") if p.is_file()}
    repo.install_release_catalog()
    repo.install_web_boards()
    after = {p.relative_to(repo.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in repo.root.rglob("*") if p.is_file()}
    assert before == after


def test_five_web_boards_use_original_store_and_validated_manifests(client):
    from zhangwen.mu_web.hardware import WEB_CONTROLLERS
    skills = client.get("/api/hardware").json()["skills"]
    assert {item["componentId"] for item in skills if item["category"] == "MCU"} == WEB_CONTROLLERS
    for board in WEB_CONTROLLERS:
        created = client.post('/api/projects', json={"name": board, "boardId": board, "code": "print('board')\n"})
        assert created.status_code == 201, created.text
        project = created.json()
        manifest = client.post('/api/projects/' + project['id'] + '/upload-manifest', json={"expectedRevision": 1})
        assert manifest.status_code == 200, manifest.text
        assert manifest.json()['boardId'] == board
        assert len(manifest.json()['hardwareRevisions'][board]) == 24


def test_save_versions_conflict_and_restart_preserve_existing_tables(client):
    project = new_project(client)
    original = project["code"]
    path = "/api/projects/" + project["id"]
    saved = client.put(path, json=save_payload(project, code='print("保存验证")\n')).json()
    assert saved["revision"] == 2
    assert saved["code"] == 'print("保存验证")\n'
    conflict = client.put(path, json=save_payload(project, code="print('stale')"))
    assert conflict.status_code == 409
    versions = client.get(path + "/versions").json()["versions"]
    assert [version["revision"] for version in versions] == [2, 1]
    assert versions[1]["code"] == original
    app2 = create_app(client.app.state.repo.projects.data_dir)
    with TestClient(app2, base_url="http://127.0.0.1:3080") as restarted:
        assert restarted.get(path).json()["code"] == saved["code"]
    with client.app.state.repo.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM artifact_versions WHERE source_entity_type='mu_code'").fetchone()[0] == 2


def test_create_preserves_editor_scratch_and_checks_code_boundary(client):
    board = new_project(client)["boardId"]
    scratch = 'print("页面草稿")\n'
    response = client.post("/api/projects", json={"name": "草稿保存", "boardId": board, "code": scratch})
    assert response.status_code == 201
    project = response.json()
    assert project["code"] == scratch
    versions = client.get(f'/api/projects/{project["id"]}/versions').json()["versions"]
    assert len(versions) == 1 and versions[0]["code"] == scratch
    for invalid in ["\x00", "中" * 30000]:
        response = client.post("/api/projects", json={"name": "非法草稿", "boardId": board, "code": invalid})
        assert response.status_code == 422


def test_create_preserves_preselected_sensors_and_rejects_invalid_selection(client):
    catalog = client.get('/api/hardware').json()['skills']
    board = next(item['componentId'] for item in catalog if item['componentId'] == 'hw_seed_unihiker_k10')
    sensors = [item['componentId'] for item in catalog if item['category'] == 'SENSOR'][:2]
    body = {'name': '先选器件', 'boardId': board, 'componentIds': sensors, 'code': 'print("scratch")'}
    response = client.post('/api/projects', json=body)
    assert response.status_code == 201, response.text
    project = response.json()
    assert project['componentIds'] == sensors
    assert project['revision'] == 1
    assert client.get('/api/projects/' + project['id']).json()['componentIds'] == sensors
    for invalid in [[sensors[0], sensors[0]], ['missing'], [board], sensors * 20]:
        assert client.post('/api/projects', json={**body, 'componentIds': invalid}).status_code == 422


def test_check_never_executes_and_manifest_is_fixed_to_saved_revision(client, tmp_path):
    project = new_project(client)
    code = "import pathlib\npathlib.Path('" + (tmp_path / "must-not-exist").as_posix() + "').write_text('bad')\n"
    body = {"code": code, "boardId": project["boardId"], "componentIds": []}
    result = client.post("/api/check", json=body)
    assert result.json()["valid"]
    assert not (tmp_path / "must-not-exist").exists()
    assert not client.post("/api/check", json={**body, "code": "def :"}).json()["valid"]
    path = "/api/projects/" + project["id"]
    manifest = client.post(path + "/upload-manifest", json={"expectedRevision": 1}).json()
    assert manifest["files"][0]["path"] == "main.py"
    assert manifest["files"][0]["sha256"] == project["checksum"]
    client.put(path, json=save_payload(project, code="def :"))
    assert client.post(path + "/upload-manifest", json={"expectedRevision": 1}).status_code == 409
    assert client.post(path + "/upload-manifest", json={"expectedRevision": 2}).status_code == 422


@pytest.mark.parametrize("changes", [{"boardId": "missing"}, {"componentIds": ["missing"]}, {"code": "\x00"}, {"code": "中" * 30000}, {"componentIds": ["hw_seed_unihiker_k10", "hw_seed_unihiker_k10"]}])
def test_invalid_save_cannot_change_project(client, changes):
    project = new_project(client)
    response = client.put("/api/projects/" + project["id"], json=save_payload(project, **changes))
    assert response.status_code == 422, response.text
    assert client.get("/api/projects/" + project["id"]).json()["revision"] == 1


def test_local_security_and_api_misses(client):
    assert client.get("/api/session", headers={"host": "attacker.test:3080"}).status_code == 403
    assert client.get("/api/session", headers={"origin": "https://attacker.test"}).status_code == 403
    assert client.get("/api/session", headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert client.post("/api/check", json={}, headers={"x-mu-session": "bad"}).status_code == 403
    assert client.get("/api/no-such-route").status_code == 404
    assert "application/json" in client.get("/api/no-such-route").headers["content-type"]
    assert client.get("/api/health").headers["content-security-policy"]
    assert client.post("/api/projects", content=b" " * 300001).status_code == 413
    assert client.get("/api/devices").status_code == 404


def test_no_ai_config_is_truthful_and_does_not_modify_code(client):
    project = new_project(client)
    path = "/api/projects/" + project["id"]
    response = client.post(path + "/chat", json={"message": "帮我修改", "code": project["code"], "boardId": project["boardId"]})
    assert response.status_code == 503
    assert client.get(path).json()["code"] == project["code"]


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro"])
def test_provider_sends_current_model_with_final_answer_budget(client, monkeypatch, model):
    project = new_project(client)
    sent = []
    def respond(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        sent.append(json.loads(request.content))
        chunks = [{"delta": {"reasoning_content": "internal only"}}, {"delta": {"content": "测试最终回答"}}, {"delta": {}, "finish_reason": "stop"}]
        body = ": keep-alive\n\n" + "".join("data: " + json.dumps({"choices": [chunk]}) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    real_client = httpx.AsyncClient
    monkeypatch.setattr("zhangwen.mu_web.app.httpx.AsyncClient", lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)))
    request = ChatInput(message="帮助调试", code=project["code"], boardId=project["boardId"])
    result = asyncio.run(generate_reply(request, client.app.state.repo, [], api_key="test-only-key", model=model))
    assert result == "测试最终回答"
    assert sent[0]["model"] == model
    assert sent[0]["thinking"] == {"type": "disabled"}
    assert sent[0]["max_tokens"] == 4096
    assert sent[0]["stream"] is True
    assert "tools" not in sent[0]


@pytest.mark.parametrize("status, text", [(401, "API Key 无效"), (429, "余额不足或请求受限")])
def test_provider_errors_are_actionable_without_echoing_credentials(client, monkeypatch, status, text):
    project = new_project(client)
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _: httpx.Response(status, json={"error": "secret-test-key"}))
    monkeypatch.setattr("zhangwen.mu_web.app.httpx.AsyncClient", lambda **kwargs: real_client(**kwargs, transport=transport))
    request = ChatInput(message="测试", code=project["code"], boardId=project["boardId"])
    with pytest.raises(HTTPException) as caught:
        asyncio.run(generate_reply(request, client.app.state.repo, [], api_key="secret-test-key", model="deepseek-flash"))
    assert caught.value.status_code == 502
    assert text in caught.value.detail
    assert "secret-test-key" not in caught.value.detail


def test_ai_settings_are_local_persisted_and_never_echo_key(client, tmp_path):
    assert client.get("/api/session").json()["aiConfigured"] is False
    assert client.get("/api/settings/ai").json()["aiModel"] == "deepseek-flash"
    response = client.post("/api/settings/ai", json={"apiKey": "  local-secret  ", "model": "deepseek-flash"})
    assert response.status_code == 200
    assert response.json() == {"aiConfigured": True, "aiModel": "deepseek-flash"}
    assert "local-secret" not in response.text
    settings = json.loads((tmp_path / "mu-settings.json").read_text(encoding="utf-8"))
    assert settings == {"apiKey": "local-secret", "model": "deepseek-flash"}
    kept = client.post("/api/settings/ai", json={"apiKey": None, "model": "deepseek-v4-pro"})
    assert kept.json() == {"aiConfigured": True, "aiModel": "deepseek-v4-pro"}
    assert json.loads((tmp_path / "mu-settings.json").read_text(encoding="utf-8"))["apiKey"] == "local-secret"
    restarted = create_app(tmp_path)
    with TestClient(restarted, base_url="http://127.0.0.1:3080") as other:
        session = other.get("/api/session")
        assert session.json()["aiConfigured"] is True
        assert session.json()["aiModel"] == "deepseek-v4-pro"
        assert "local-secret" not in session.text
        token = session.json()["token"]
        cleared = other.post("/api/settings/ai", json={"apiKey": "", "model": "deepseek-flash"}, headers={"origin": "http://127.0.0.1:3080", "x-mu-session": token})
        assert cleared.status_code == 200
        assert other.get("/api/settings/ai").json()["aiConfigured"] is False
    assert not create_app(tmp_path).state.ai_settings["apiKey"]


def test_legacy_model_settings_upgrade_without_rewriting_key_or_file(client, tmp_path, monkeypatch):
    path = tmp_path / "mu-settings.json"
    legacy = {"apiKey": "unchanged-local-key", "model": "deepseek-reasoner"}
    content = json.dumps(legacy)
    path.write_text(content, encoding="utf-8")
    restarted = create_app(tmp_path)
    assert restarted.state.ai_settings == {"apiKey": legacy["apiKey"], "model": "deepseek-flash"}
    assert path.read_text(encoding="utf-8") == content
    for model in ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp"]:
        result = client.post("/api/settings/ai", json={"apiKey": legacy["apiKey"], "model": model})
        assert result.json() == {"aiConfigured": True, "aiModel": "deepseek-flash"}
        assert json.loads(path.read_text(encoding="utf-8"))["apiKey"] == legacy["apiKey"]
    monkeypatch.setenv("ZHANGWEN_MU_MODEL", "deepseek-chat")
    from_env = create_app(tmp_path / "env-only")
    assert from_env.state.ai_settings["model"] == "deepseek-flash"
    monkeypatch.setenv("ZHANGWEN_MU_MODEL", "deepseek-v4-pro")
    from_pro_env = create_app(tmp_path / "pro-env")
    assert from_pro_env.state.ai_settings["model"] == "deepseek-v4-pro"


def test_ai_settings_reject_cross_site_invalid_input_and_failed_save(client, tmp_path, monkeypatch):
    body = {"apiKey": "secret-marker", "model": "deepseek-flash"}
    assert client.post("/api/settings/ai", json=body, headers={"x-mu-session": "bad"}).status_code == 403
    assert client.post("/api/settings/ai", json=body, headers={"origin": "https://attacker.test"}).status_code == 403
    for invalid in [{**body, "model": " "}, {**body, "apiKey": "secret-marker\ninvalid"}, {**body, "apiKey": "x" * 501}, {**body, "unknown": True}]:
        response = client.post("/api/settings/ai", json=invalid)
        assert response.status_code == 422
        assert "secret-marker" not in response.text
    assert not (tmp_path / "mu-settings.json").exists()
    assert client.post("/api/settings/ai", json=body).status_code == 200
    monkeypatch.setattr(Path, "replace", lambda *_: (_ for _ in ()).throw(OSError("test failure")))
    failed = client.post("/api/settings/ai", json={"apiKey": "different-secret", "model": "deepseek-v4-pro"})
    assert failed.status_code == 500
    assert client.get("/api/settings/ai").json() == {"aiConfigured": True, "aiModel": "deepseek-flash"}
    assert json.loads((tmp_path / "mu-settings.json").read_text(encoding="utf-8"))["apiKey"] == "secret-marker"


def test_real_provider_adapter_contract_with_fake_response_only(client, monkeypatch):
    client.post("/api/settings/ai", json={"apiKey": "test-only-placeholder", "model": "deepseek-v4-pro"})
    reply = AsyncMock(return_value="```python\nprint('建议')\n```")
    monkeypatch.setattr("zhangwen.mu_web.app.generate_reply", reply)
    project = new_project(client)
    path = "/api/projects/" + project["id"]
    response = client.post(path + "/chat", json={"message": "生成示例", "code": project["code"], "boardId": project["boardId"]})
    assert response.status_code == 200, response.text
    assert reply.call_args.kwargs == {"api_key": "test-only-placeholder", "model": "deepseek-v4-pro"}
    messages = response.json()["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[-1]["status"] == "COMPLETED"
    assert client.get(path).json()["code"] == project["code"]
    monkeypatch.setattr("zhangwen.mu_web.app.generate_reply", AsyncMock(side_effect=HTTPException(502, "fake failure")))
    failed = client.post(path + "/chat", json={"message": "失败测试", "code": project["code"], "boardId": project["boardId"]})
    assert failed.status_code == 502
    assert client.get(path).json()["messages"][-1]["status"] == "FAILED"


def test_streamed_chat_saves_only_complete_answers_and_preserves_error_detail(client, monkeypatch):
    client.post("/api/settings/ai", json={"apiKey": "placeholder", "model": "deepseek-flash"})
    project = new_project(client)
    path = "/api/projects/" + project["id"]
    body = {"message": "生成示例", "code": project["code"], "boardId": project["boardId"]}

    async def reply(*_args, on_delta, **_kw):
        await on_delta("```python\n")
        await on_delta("print(1)\n```")
        return "```python\nprint(1)\n```"

    monkeypatch.setattr("zhangwen.mu_web.app.generate_reply", reply)
    response = client.post(path + "/chat", json=body, headers={"accept": "application/x-ndjson"})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [e["type"] for e in events] == ["status", "delta", "delta", "done"]
    assert events[-1]["messages"][-1]["status"] == "COMPLETED"
    assert client.get(path).json()["code"] == project["code"]
    detail = "DeepSeek 已受理请求，但长时间未返回回答。"
    monkeypatch.setattr("zhangwen.mu_web.app.generate_reply", AsyncMock(side_effect=HTTPException(504, detail)))
    failed = client.post(path + "/chat", json=body, headers={"accept": "application/x-ndjson"})
    assert json.loads(failed.text.splitlines()[-1]) == {"type": "error", "detail": detail}
    assert client.get(path).json()["messages"][-1]["content"] == detail
    assert client.get(path).json()["messages"][-1]["status"] == "FAILED"
    monkeypatch.setattr("zhangwen.mu_web.app.generate_reply", AsyncMock(side_effect=RuntimeError("private detail")))
    unexpected = client.post(path + "/chat", json=body, headers={"accept": "application/x-ndjson"})
    assert json.loads(unexpected.text.splitlines()[-1])["type"] == "error"
    assert "private detail" not in unexpected.text
    assert client.get(path).json()["messages"][-1]["status"] == "FAILED"


def test_stream_disconnect_cancels_provider_marks_failure_and_releases_project_lock(client, monkeypatch):
    from starlette.requests import Request
    client.post("/api/settings/ai", json={"apiKey": "placeholder", "model": "deepseek-flash"})
    project = new_project(client)
    endpoint = next(route.endpoint for route in client.app.routes if getattr(route, "path", None) == "/api/projects/{project_id}/chat")

    async def run():
        ready = asyncio.Event()
        cancelled = asyncio.Event()

        async def reply(*_args, on_delta, **_kw):
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        monkeypatch.setattr("zhangwen.mu_web.app.generate_reply", reply)
        request = Request({"type": "http", "headers": [(b"accept", b"application/x-ndjson")]})
        response = await endpoint(project["id"], ChatInput(message="取消测试", code="", boardId=project["boardId"]), request)
        await anext(response.body_iterator)
        await asyncio.wait_for(ready.wait(), 1)
        assert client.app.state.chat_locks[project["id"]].locked()
        with pytest.raises(HTTPException) as conflict:
            await endpoint(project["id"], ChatInput(message="并发", code="", boardId=project["boardId"]), request)
        assert conflict.value.status_code == 409
        await response.body_iterator.aclose()
        assert cancelled.is_set()
        assert not client.app.state.chat_locks[project["id"]].locked()

    asyncio.run(run())
    message = client.get("/api/projects/" + project["id"]).json()["messages"][-1]
    assert message["status"] == "FAILED"
    assert "已取消" in message["content"]


def test_legacy_course_or_other_project_not_silently_converted(client):
    old = client.app.state.repo.projects.create_project("历史课程", "保留审核策略").project
    assert client.get("/api/projects/" + old.id).status_code == 404
    assert client.get("/api/projects").json()["projects"] == []


def test_preserved_source_manifest():
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "docs/legacy-source-manifest.json").read_text(encoding="utf-8"))
    for file in manifest["files"]:
        path = root / "services/local-api/zhangwen" / file["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == file["sha256"], file["path"]
