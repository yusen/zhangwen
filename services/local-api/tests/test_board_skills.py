"""Read-only K10 Board Skill package validation and selection tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from zhangwen.hardware.board_skills import (
    BUNDLED_BOARD_SKILL_DIR,
    BoardSkillRepository,
    BoardSkillValidationError,
)


def test_k10_board_skill_is_bound_validated_and_path_free() -> None:
    repository = BoardSkillRepository()

    summary = repository.summary_for_profile("unihiker-k10")

    assert summary is not None
    assert summary.id == "unihiker-k10-micropython-engineer"
    assert summary.version == "1.0.0"
    assert summary.profileId == "unihiker-k10"
    assert summary.referenceCount == 11
    assert summary.templateCount == 22
    assert summary.exampleCount == 3
    assert summary.syntaxValidated is True
    assert summary.hardwareValidated is False
    serialized = json.dumps(summary.model_dump(mode="json"), ensure_ascii=False)
    assert str(BUNDLED_BOARD_SKILL_DIR) not in serialized
    assert "board-skills" not in serialized


def test_k10_board_skill_selects_bounded_screen_guidance_without_deployment() -> None:
    context = BoardSkillRepository().build_context(
        "unihiker-k10",
        "请用行空板 K10 的屏幕显示蓝色 hello world，并生成 MicroPython 代码。",
    )

    reference_paths = [item["path"] for item in context["references"]]
    template_paths = [item["path"] for item in context["templates"]]
    assert reference_paths == [
        "references/00-sources-and-scope.md",
        "references/03-screen-api.md",
    ]
    assert template_paths == ["templates/01_screen_shapes.py"]
    assert "references/02-deployment.md" not in reference_paths
    assert "from unihiker_k10 import screen" in str(context["templates"][0]["content"])
    assert len(json.dumps(context, ensure_ascii=False)) < 30_000


def test_k10_board_skill_selects_camera_storage_references_and_generation_contract() -> None:
    context = BoardSkillRepository().build_context(
        "unihiker-k10",
        "请使用行空板 K10 摄像头拍照并保存到 TF 卡。",
    )

    reference_paths = [item["path"] for item in context["references"]]
    template_paths = [item["path"] for item in context["templates"]]
    assert reference_paths == [
        "references/00-sources-and-scope.md",
        "references/03-screen-api.md",
        "references/05-storage-audio-api.md",
    ]
    assert template_paths == [
        "templates/14_camera_preview.py",
        "templates/05_tf_card_list.py",
    ]

    generation_contract = context["generationContract"]
    camera_contract = next(
        item
        for item in generation_contract["templateContracts"]
        if item["path"] == "templates/14_camera_preview.py"
    )
    assert camera_contract["requiredImports"] == [
        "k10_base:Camera",
        "unihiker_k10:screen",
    ]
    assert camera_contract["requiredCalls"] == [
        "Camera",
        "Camera.init",
        "screen.init",
        "screen.show_camera",
    ]
    assert generation_contract["capabilityGaps"][0]["id"] == (
        "k10-camera-still-image-save"
    )
    assert "不得声称" in generation_contract["capabilityGaps"][0]["instruction"]
    assert len(json.dumps(context, ensure_ascii=False)) < 40_000


def test_k10_board_skill_keeps_camera_preview_and_onboard_sensor_references_specific() -> None:
    camera = BoardSkillRepository().build_context(
        "unihiker-k10",
        "请生成行空板 K10 摄像头实时预览代码。",
    )
    onboard_sensor = BoardSkillRepository().build_context(
        "unihiker-k10",
        "请读取行空板 K10 板载温湿度并显示在屏幕上。",
    )

    assert [item["path"] for item in camera["references"]] == [
        "references/00-sources-and-scope.md",
        "references/03-screen-api.md",
    ]
    assert [item["path"] for item in camera["templates"]] == [
        "templates/14_camera_preview.py"
    ]
    assert [item["path"] for item in onboard_sensor["references"]] == [
        "references/00-sources-and-scope.md",
        "references/03-screen-api.md",
        "references/04-onboard-api.md",
    ]
    assert [item["path"] for item in onboard_sensor["templates"]] == [
        "templates/02_onboard_dashboard.py",
    ]


def test_k10_board_skill_rejects_tampered_file(tmp_path: Path) -> None:
    target = tmp_path / "unihiker-k10"
    shutil.copytree(BUNDLED_BOARD_SKILL_DIR / "unihiker-k10", target)
    template = target / "templates" / "01_screen_shapes.py"
    template.write_text(f"{template.read_text(encoding='utf-8')}\n# tampered\n", encoding="utf-8")

    with pytest.raises(BoardSkillValidationError, match="SHA-256"):
        BoardSkillRepository(tmp_path).summary_for_profile("unihiker-k10")


def test_k10_board_skill_rejects_checksum_path_escape(tmp_path: Path) -> None:
    target = tmp_path / "unihiker-k10"
    shutil.copytree(BUNDLED_BOARD_SKILL_DIR / "unihiker-k10", target)
    checksum_file = target / "CHECKSUMS.sha256"
    checksum_file.write_text(
        f"{checksum_file.read_text(encoding='utf-8')}\n{'0' * 64}  ../escape.py\n",
        encoding="utf-8",
    )

    with pytest.raises(BoardSkillValidationError, match="安全相对路径"):
        BoardSkillRepository(tmp_path).summary_for_profile("unihiker-k10")
