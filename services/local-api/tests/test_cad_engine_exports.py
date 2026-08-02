from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
import struct

import pytest

from zhangwen.cad_engine.engine import build_cad_artifacts
from zhangwen.cad_engine.exports import canonical_json_bytes
from zhangwen.cad_engine.models import CadBuildSpec


FIXTURE = Path(__file__).parent / "fixtures" / "cad_engine" / "box_with_lid_k10.json"


def test_canonical_json_is_order_independent() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_real_cad_exports_and_geometry_gates(tmp_path: Path) -> None:
    cadquery = pytest.importorskip("cadquery", reason="CadQuery is an optional CAD runtime dependency")
    trimesh = pytest.importorskip("trimesh", reason="trimesh provides an independent mesh check")
    spec = CadBuildSpec.model_validate_json(FIXTURE.read_text(encoding="utf-8"))

    result = build_cad_artifacts(spec, tmp_path / "artifacts")

    expected = {
        "assembly.step",
        "base.step",
        "base.stl",
        "geometry-summary.json",
        "lid.step",
        "lid.stl",
        "manifest.json",
        "parameters.json",
        "preview.glb",
        "profiles.json",
        "validation.json",
    }
    assert {item.name for item in result.output_directory.iterdir()} == expected
    assert result.validation.ok is True
    assert result.geometry_summary.total_volume_mm3 > 0
    assert result.geometry_summary.preview_triangle_count > 0

    glb = (result.output_directory / "preview.glb").read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", glb, 0)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(glb)
    document, binary = _glb_payload(glb)
    for mesh in document["meshes"]:
        primitive = mesh["primitives"][0]
        assert "NORMAL" in primitive["attributes"]
        position_accessor = document["accessors"][primitive["attributes"]["POSITION"]]
        normal_accessor_index = primitive["attributes"]["NORMAL"]
        normal_accessor = document["accessors"][normal_accessor_index]
        assert normal_accessor["componentType"] == 5126
        assert normal_accessor["type"] == "VEC3"
        assert normal_accessor["count"] == position_accessor["count"]
        normals = _float_vec3_accessor(document, binary, normal_accessor_index)
        assert normals
        for normal in normals:
            assert all(math.isfinite(value) for value in normal)
            assert math.sqrt(sum(value * value for value in normal)) == pytest.approx(1.0, abs=1e-5)

    for file_name in ("assembly.step", "base.step", "lid.step"):
        shape = cadquery.importers.importStep(str(result.output_directory / file_name)).val()
        assert shape.isValid()
        assert shape.Volume() > 0

    for file_name in ("base.stl", "lid.stl"):
        mesh = trimesh.load_mesh(result.output_directory / file_name, force="mesh")
        assert mesh.is_watertight
        assert mesh.is_volume
    scene = trimesh.load(result.output_directory / "preview.glb", force="scene")
    assert scene.geometry

    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        content = (result.output_directory / entry["file_name"]).read_bytes()
        assert entry["byte_size"] == len(content)
        assert entry["sha256"] == sha256(content).hexdigest()


def _glb_payload(glb: bytes) -> tuple[dict[str, object], bytes]:
    json_length, json_type = struct.unpack_from("<II", glb, 12)
    assert json_type == 0x4E4F534A
    json_start = 20
    json_end = json_start + json_length
    document = json.loads(glb[json_start:json_end].decode("utf-8").rstrip(" \x00"))
    binary_length, binary_type = struct.unpack_from("<II", glb, json_end)
    assert binary_type == 0x004E4942
    binary_start = json_end + 8
    return document, glb[binary_start : binary_start + binary_length]


def _float_vec3_accessor(
    document: dict[str, object],
    binary: bytes,
    accessor_index: int,
) -> list[tuple[float, float, float]]:
    accessors = document["accessors"]
    buffer_views = document["bufferViews"]
    assert isinstance(accessors, list)
    assert isinstance(buffer_views, list)
    accessor = accessors[accessor_index]
    assert isinstance(accessor, dict)
    view = buffer_views[int(accessor["bufferView"])]
    assert isinstance(view, dict)
    offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    return [
        struct.unpack_from("<3f", binary, offset + index * 12)
        for index in range(int(accessor["count"]))
    ]
