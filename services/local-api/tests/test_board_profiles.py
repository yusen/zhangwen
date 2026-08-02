"""Markdown BoardProfile catalog and overlay tests."""

from __future__ import annotations

from pathlib import Path
import json

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.hardware.board_profiles import BoardProfileRepository
from zhangwen.main import app


def test_k10_board_profile_is_markdown_and_searchable(tmp_path: Path) -> None:
    repository = BoardProfileRepository(tmp_path)

    profile = repository.get_profile("unihiker-k10")
    matches = repository.search("请为行空板 K10 生成 MicroPython 屏幕代码")

    assert profile.displayName == "行空板 K10"
    assert profile.language == "micropython"
    assert profile.content.startswith("---\n")
    assert "ESP32-S3 N16R8" in profile.content
    assert "16 MB Flash" in profile.content
    assert "8 MB PSRAM" in profile.content
    assert matches[0].id == "unihiker-k10"
    assert repository.search("ESP32-C3 温度计") == []


def test_board_profile_api_lists_k10_without_exposing_host_paths(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    listing = client.get("/api/hardware/board-profiles")
    detail = client.get("/api/hardware/board-profiles/unihiker-k10")

    assert listing.status_code == 200
    assert listing.json()["profiles"][0]["id"] == "unihiker-k10"
    skill = listing.json()["profiles"][0]["skillPackage"]
    assert skill["id"] == "unihiker-k10-micropython-engineer"
    assert skill["version"] == "1.0.0"
    assert skill["referenceCount"] == 11
    assert skill["templateCount"] == 22
    assert skill["exampleCount"] == 3
    assert skill["syntaxValidated"] is True
    assert skill["hardwareValidated"] is False
    assert "content" not in listing.json()["profiles"][0]
    assert detail.status_code == 200
    serialized = json.dumps(
        {"listing": listing.json(), "detail": detail.json()},
        ensure_ascii=False,
    )
    assert str(tmp_path) not in serialized
    assert str(tmp_path).replace("\\", "\\\\") not in serialized
    assert str(tmp_path).replace("\\", "/") not in serialized
    assert "board-profiles\\unihiker-k10.md" not in serialized
    assert "board-skills" not in serialized


def test_board_profile_catalog_contains_only_k10_and_xiao_sense(tmp_path: Path) -> None:
    repository = BoardProfileRepository(tmp_path)
    profiles = repository.list_profiles()
    assert [profile.id for profile in profiles] == ["unihiker-k10", "xiao-esp32s3-sense"]
    xiao = repository.get_profile("xiao-esp32s3-sense")
    assert "seeedstudio/xiao_esp32s3_sense" in xiao.aliases
    assert "8 MB Flash" in xiao.content
    assert "8 MB OPI PSRAM" in xiao.content
    assert "GPIO21" in xiao.content


def test_board_profile_overlay_conflict_and_reset(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    detail = client.get("/api/hardware/board-profiles/unihiker-k10")
    assert detail.status_code == 200
    profile = detail.json()["profile"]
    changed = profile["content"] + "\n## 用户补充\n\n项目默认使用屏幕横向布局。\n"

    saved = client.put(
        "/api/hardware/board-profiles/unihiker-k10",
        json={"content": changed, "expectedRevision": profile["revision"]},
    )
    assert saved.status_code == 200
    assert saved.json()["profile"]["overridden"] is True
    assert "用户补充" in saved.json()["profile"]["content"]

    stale = client.put(
        "/api/hardware/board-profiles/unihiker-k10",
        json={"content": changed, "expectedRevision": profile["revision"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "BOARD_PROFILE_CONFLICT"

    stale_reset = client.post(
        "/api/hardware/board-profiles/unihiker-k10/reset",
        json={"expectedRevision": profile["revision"]},
    )
    assert stale_reset.status_code == 409
    assert stale_reset.json()["detail"]["code"] == "BOARD_PROFILE_CONFLICT"

    reset = client.post(
        "/api/hardware/board-profiles/unihiker-k10/reset",
        json={"expectedRevision": saved.json()["profile"]["revision"]},
    )
    assert reset.status_code == 200
    assert reset.json()["profile"]["overridden"] is False
    assert "用户补充" not in reset.json()["profile"]["content"]


def test_board_profile_rejects_identity_change(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    profile = client.get("/api/hardware/board-profiles/unihiker-k10").json()["profile"]

    response = client.put(
        "/api/hardware/board-profiles/unihiker-k10",
        json={
            "content": profile["content"].replace(
                "id: unihiker-k10",
                "id: other-board",
                1,
            ),
            "expectedRevision": profile["revision"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "BOARD_PROFILE_INVALID"
