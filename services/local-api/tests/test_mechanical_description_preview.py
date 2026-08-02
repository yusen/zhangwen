from __future__ import annotations

import json

import pytest

from tests.fakes import SequenceProvider
from zhangwen.hardware.mechanical_preview import (
    MechanicalDescriptionPreviewService,
    MechanicalPreviewSourceError,
    extract_mechanical_natural_description,
    mechanical_description_sha256,
    write_preview_geometry,
)
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.llm.structured import StructuredLLMError


MECHANICAL_MARKDOWN = """# 示例机械档案

## 自然语言描述

PCB 长 30 mm、宽 22 mm、厚 1 mm，中心为 (0, 0, 0.5) mm，四角 R4。
接线口为 6 × 10 × 5.7 mm 长方体，中心为 (12, 0, 3.85) mm。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "example_sensor",
    "preview_geometry": {
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "primitives": [{"primitive_id": "old", "operation": "add", "kind": "box"}]
    }
  },
  "model": {"path": "models/cadquery.py"}
}
```
"""


def generated_geometry_payload() -> dict[str, object]:
    return {
        "primitives": [
            {
                "primitive_id": "pcb",
                "operation": "add",
                "kind": "rounded_box",
                "center": {"x": 0.0, "y": 0.0, "z": 0.5},
                "size": {"length_x": 30.0, "width_y": 22.0, "height_z": 1.0},
                "corner_radius": 4.0,
                "rotation_z_deg": 0,
                "role": "pcb",
            },
            {
                "primitive_id": "connector",
                "operation": "add",
                "kind": "box",
                "center": {"x": 12.0, "y": 0.0, "z": 3.85},
                "size": {"length_x": 6.0, "width_y": 10.0, "height_z": 5.7},
                "corner_radius": 0.0,
                "rotation_z_deg": 0,
                "role": "connector",
            },
        ]
    }


def test_extracts_only_natural_description_and_hashes_normalized_text() -> None:
    description = extract_mechanical_natural_description(
        MECHANICAL_MARKDOWN.replace("\n", "\r\n")
    )

    assert description.startswith("PCB 长 30 mm")
    assert "机器可读机械档案" not in description
    assert mechanical_description_sha256(description) == mechanical_description_sha256(
        description.replace("\n", "\r\n")
    )


def test_requires_one_non_empty_natural_description_section() -> None:
    with pytest.raises(MechanicalPreviewSourceError):
        extract_mechanical_natural_description("# 没有自然描述\n")


@pytest.mark.asyncio
async def test_provider_compiles_description_into_bounded_geometry() -> None:
    provider = SequenceProvider([json.dumps(generated_geometry_payload())])
    description = extract_mechanical_natural_description(MECHANICAL_MARKDOWN)

    geometry = await MechanicalDescriptionPreviewService(provider).generate(
        description=description,
        config=LLMConfig(keySaved=True),
        api_key="fake-test-key",
        model=LLMModelId.DEEPSEEK_V4_FLASH,
    )

    assert geometry.source_sha256 == mechanical_description_sha256(description)
    assert [item.primitive_id for item in geometry.primitives] == ["pcb", "connector"]
    request_text = "\n".join(message.content for message in provider.requests[0].messages)
    assert description in request_text
    assert "models/cadquery.py" not in request_text


@pytest.mark.asyncio
async def test_provider_output_outside_geometry_schema_fails_closed() -> None:
    provider = SequenceProvider([json.dumps({"python": "import cadquery"})])

    with pytest.raises(StructuredLLMError):
        await MechanicalDescriptionPreviewService(provider).generate(
            description=extract_mechanical_natural_description(MECHANICAL_MARKDOWN),
            config=LLMConfig(keySaved=True),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )

    assert provider.calls == 2


@pytest.mark.asyncio
async def test_writes_generated_cache_without_changing_natural_description() -> None:
    provider = SequenceProvider([json.dumps(generated_geometry_payload())])
    description = extract_mechanical_natural_description(MECHANICAL_MARKDOWN)
    geometry = await MechanicalDescriptionPreviewService(provider).generate(
        description=description,
        config=LLMConfig(keySaved=True),
        api_key="fake-test-key",
        model=LLMModelId.DEEPSEEK_V4_FLASH,
    )

    updated = write_preview_geometry(MECHANICAL_MARKDOWN, geometry)
    payload_text = updated.split("```zhangwen:hardware-mechanical:v1\n", 1)[1].split(
        "\n```", 1
    )[0]
    payload = json.loads(payload_text)

    assert extract_mechanical_natural_description(updated) == description
    assert payload["profile"]["preview_geometry"]["source_sha256"] == (
        mechanical_description_sha256(description)
    )
    assert [
        item["primitive_id"]
        for item in payload["profile"]["preview_geometry"]["primitives"]
    ] == ["pcb", "connector"]
