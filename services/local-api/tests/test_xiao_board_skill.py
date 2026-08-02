"""XIAO ESP32S3 Sense Board Skill binding tests."""

from __future__ import annotations

import json
from pathlib import Path

from zhangwen.hardware.board_profiles import BoardProfileRepository
from zhangwen.hardware.board_skills import BoardSkillRepository


def test_xiao_sense_board_skill_is_bound_and_does_not_inherit_k10_apis(
    tmp_path: Path,
) -> None:
    repository = BoardSkillRepository()

    summary = repository.summary_for_profile("xiao-esp32s3-sense")
    context = repository.build_context(
        "xiao-esp32s3-sense",
        "为 XIAO ESP32S3 Sense 生成摄像头预览，并保存到 SD 卡",
    )
    profile = BoardProfileRepository(tmp_path).get_profile("xiao-esp32s3-sense")

    assert summary is not None
    assert summary.id == "xiao-esp32s3-sense-micropython-engineer"
    assert summary.profileId == "xiao-esp32s3-sense"
    assert profile.skillPackage == summary
    package = repository.package_for_profile("xiao-esp32s3-sense")
    assert package is not None
    paths = {
        item["path"]
        for group in (context["references"], context["templates"])
        for item in group
    }
    assert paths <= package.declared_paths
    serialized = json.dumps(context, ensure_ascii=False)
    assert "unihiker_k10" not in serialized
    assert "k10_base" not in serialized
    assert context["generationContract"]["capabilityGaps"] == []
