"""Isolated paid-provider smoke for ZW-LLM-001.

This script never prints the API Key or generated content and never calls any
device, serial, shell, upload, Flash, or firmware endpoint.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCAL_API = ROOT / "services" / "local-api"
sys.path.insert(0, str(LOCAL_API))

from fastapi.testclient import TestClient  # noqa: E402

from zhangwen.config import settings  # noqa: E402
from zhangwen.llm.contracts import SaveLLMConfigRequest  # noqa: E402
from zhangwen.main import app  # noqa: E402
from zhangwen.security.credentials import WindowsCredentialStore  # noqa: E402
from zhangwen.settings.repository import LLMSettingsRepository  # noqa: E402


IDEA = (
    "制作一个桌面温湿度显示器：ESP32-S3 读取 DHT22，"
    "GPIO4 连接数据线，GPIO8/GPIO9 连接 0.96 英寸 OLED，"
    "使用 5V USB 供电，不使用电机或水泵。"
)


class SmokeFailure(RuntimeError):
    pass


def main() -> int:
    original_data_dir = settings.data_dir
    credential_store = WindowsCredentialStore()
    api_key = credential_store.get_password(
        settings.credential_service,
        settings.credential_account,
    )
    if not api_key:
        print("REAL_LLM_SMOKE_FAILED step=credential code=CONFIG_MISSING")
        return 2

    source_config = LLMSettingsRepository(original_data_dir).load(
        key_saved=True,
        masked_api_key=None,
    )
    try:
        with tempfile.TemporaryDirectory(
            prefix="zhangwen-real-llm-smoke-",
            ignore_cleanup_errors=True,
        ) as raw_dir:
            data_dir = Path(raw_dir)
            LLMSettingsRepository(data_dir).save(
                SaveLLMConfigRequest(
                    provider=source_config.provider,
                    baseUrl=source_config.baseUrl,
                    defaultModel=source_config.defaultModel,
                    thinkingMode=source_config.thinkingMode,
                    reasoningEffort=source_config.reasoningEffort,
                    timeoutSeconds=source_config.timeoutSeconds,
                ),
                key_saved=True,
                masked_api_key=None,
            )
            settings.data_dir = data_dir
            with TestClient(app) as client:
                result = _run_smoke(client, data_dir)
    except SmokeFailure as exc:
        print(f"REAL_LLM_SMOKE_FAILED {exc}")
        return 1
    finally:
        settings.data_dir = original_data_dir
        api_key = ""

    print(
        "REAL_LLM_SMOKE_OK "
        f"artifacts={result['artifacts']} model_routes={result['model_routes']} "
        f"expert_runs={result['expert_runs']}"
    )
    return 0


def _run_smoke(client: TestClient, data_dir: Path) -> dict[str, int]:
    suggestion = _post(
        client,
        "/api/projects/suggest",
        {"text": IDEA},
        "project_route",
    )["suggestion"]
    _ok("project_route")

    workspace = _post(
        client,
        "/api/projects",
        {
            "name": suggestion["name"],
            "initialIdea": IDEA,
            "selectedExpertTypes": [
                "problem_guide",
                "smart_engineer",
                "structure_engineer",
            ],
            "initialExpert": suggestion["initialExpert"],
            "routerResult": suggestion["routerResult"],
            "expertSelectionMode": "manual",
            "idempotencyKey": "real-llm-smoke-project",
        },
        "project_create",
    )["workspace"]
    project_id = str(workspace["project"]["id"])
    experts = {item["expertType"]: item for item in workspace["experts"]}
    _ok("project_create")

    for expert_type, prompt in (
        (
            "smart_engineer",
            "请审查这个项目的供电、IO 和 MicroPython 实现边界，只给出可验证建议。",
        ),
        (
            "structure_engineer",
            "请根据桌面显示器需求提出一个保守的结构与装配建议，不执行建模。",
        ),
    ):
        expert = experts[expert_type]
        _post(
            client,
            f"/api/projects/{project_id}/experts/{expert['id']}/activate",
            {},
            f"activate_{expert_type}",
        )
        _chat(client, project_id, prompt, f"expert_{expert_type}")
        _ok(f"expert_{expert_type}")

    guide = experts["problem_guide"]
    _post(
        client,
        f"/api/projects/{project_id}/experts/{guide['id']}/activate",
        {},
        "activate_problem_guide",
    )
    _chat(
        client,
        project_id,
        "请检查需求完整度，并一次性给出仍需确认的全部关键问题。",
        "clarification",
    )
    _ok("clarification")

    _chat(
        client,
        project_id,
        "根据当前明确需求生成唯一推荐实现方案。",
        "solution",
        conversation_action="generate_solution",
    )
    solution = _get(client, f"/api/projects/{project_id}/solution/current", "solution_get")[
        "solution"
    ]
    _post(
        client,
        f"/api/projects/{project_id}/solution/confirm",
        {"solutionId": solution["id"]},
        "solution_confirm",
    )
    _ok("solution")

    proposal = _post(
        client,
        f"/api/projects/{project_id}/proposal/generate",
        {"solutionId": solution["id"]},
        "proposal",
    )["proposal"]
    proposal = _post(
        client,
        f"/api/projects/{project_id}/proposal/confirm",
        {"proposalId": proposal["id"]},
        "proposal_confirm",
    )["proposal"]
    _ok("proposal")

    spec = _post(
        client,
        f"/api/projects/{project_id}/spec/generate",
        {"proposalId": proposal["id"]},
        "spec",
    )["spec"]
    if spec["status"] != "VALIDATED" or not spec["validation"]["ok"]:
        raise SmokeFailure(f"step=spec code=LOCAL_VALIDATION_FAILED status={spec['status']}")
    spec = _post(
        client,
        f"/api/projects/{project_id}/spec/confirm",
        {"specRunId": spec["id"]},
        "spec_confirm",
    )["spec"]
    _ok("spec")

    code_run = _post(
        client,
        f"/api/projects/{project_id}/code/generate",
        {"specRunId": spec["id"]},
        "code",
    )["codeRun"]
    if code_run["status"] != "READY_FOR_REVIEW" or not code_run["testResult"]["ok"]:
        raise SmokeFailure(f"step=code code=LOCAL_VALIDATION_FAILED status={code_run['status']}")
    _ok("code")

    lesson = _post(
        client,
        f"/api/projects/{project_id}/lesson/generate",
        {"specRunId": spec["id"], "gradeBand": "初中", "lessonHours": 2},
        "lesson",
    )["lessonRun"]
    if lesson["status"] != "READY_FOR_REVIEW" or len(lesson["files"]) != 4:
        raise SmokeFailure(f"step=lesson code=LOCAL_VALIDATION_FAILED status={lesson['status']}")
    _ok("lesson")

    artifacts = _get(client, f"/api/projects/{project_id}/artifacts", "artifacts")
    db_path = data_dir / "projects" / "zhangwen.sqlite3"
    with sqlite3.connect(db_path) as conn:
        model_routes = int(conn.execute("SELECT COUNT(*) FROM model_route_audit").fetchone()[0])
        expert_runs = int(conn.execute("SELECT COUNT(*) FROM expert_runs").fetchone()[0])
    return {
        "artifacts": len(artifacts["artifacts"]),
        "model_routes": model_routes,
        "expert_runs": expert_runs,
    }


def _chat(
    client: TestClient,
    project_id: str,
    content: str,
    step: str,
    *,
    conversation_action: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"content": content, "model": "deepseek-v4-flash"}
    if conversation_action:
        body["conversationAction"] = conversation_action
    response = client.post(f"/api/projects/{project_id}/chat/stream", json=body)
    if response.status_code != 200:
        raise SmokeFailure(f"step={step} code=HTTP_{response.status_code}")
    chunks = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    if not chunks:
        raise SmokeFailure(f"step={step} code=EMPTY_STREAM")
    final = chunks[-1]
    if final.get("type") != "COMPLETED":
        error = final.get("error") or {}
        raise SmokeFailure(f"step={step} code={error.get('code', final.get('type'))}")
    return final


def _post(
    client: TestClient,
    path: str,
    body: dict[str, Any],
    step: str,
) -> dict[str, Any]:
    response = client.post(path, json=body)
    return _json_response(response, step)


def _get(client: TestClient, path: str, step: str) -> dict[str, Any]:
    response = client.get(path)
    return _json_response(response, step)


def _json_response(response: Any, step: str) -> dict[str, Any]:
    if response.status_code < 400:
        return response.json()
    try:
        payload = response.json()
        detail = payload.get("detail", payload)
        code = detail.get("code", f"HTTP_{response.status_code}")
    except Exception:
        code = f"HTTP_{response.status_code}"
    raise SmokeFailure(f"step={step} code={code}")


def _ok(step: str) -> None:
    print(f"REAL_LLM_SMOKE_STEP_OK step={step}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
