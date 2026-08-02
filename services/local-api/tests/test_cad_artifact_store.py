from __future__ import annotations

import hashlib

import pytest

from zhangwen.cad_agent.artifact_store import ArtifactFileStore, EXPECTED_FILES


def _worker_manifest(staging) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for file_name, (role, mime_type) in EXPECTED_FILES.items():
        payload = f"cad-output:{file_name}".encode("utf-8")
        (staging / file_name).write_bytes(payload)
        files.append(
            {
                "role": role,
                "fileName": file_name,
                "relativePath": file_name,
                "mimeType": mime_type,
                "byteSize": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "triangleCount": 12 if file_name.endswith((".stl", ".glb")) else None,
                "bounds": (
                    {
                        "min_x": 0,
                        "min_y": 0,
                        "min_z": 0,
                        "max_x": 1,
                        "max_y": 1,
                        "max_z": 1,
                    }
                    if file_name.endswith((".step", ".stl", ".glb"))
                    else None
                ),
            }
        )
    return {
        "schemaVersion": "1.0",
        "engineId": "zhangwen-cad-engine",
        "engineVersion": "2.8.0",
        "designId": "cadjob_1234",
        "specSha256": "a" * 64,
        "files": files,
    }


def test_store_validates_and_atomically_publishes_worker_files(tmp_path) -> None:
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging("cadjob_1234")
    manifest = _worker_manifest(staging)

    files = store.validate_manifest("cadjob_1234", manifest)
    assert len(files) == 11
    assert EXPECTED_FILES["base.step"] == ("STEP_PRINTABLE_PARTS", "model/step")
    assert EXPECTED_FILES["lid.step"] == ("STEP_PRINTABLE_PARTS", "model/step")
    published = store.publish(
        job_id="cadjob_1234",
        project_id="project_1",
        artifact_id="artifact_cad_1",
        version_id="artifact_version_1",
        files=files,
    )

    preview = next(item for item in published if item.file_name == "preview.glb")
    assert preview.storage_key == (
        "project_1/artifact_cad_1/artifact_version_1/preview.glb"
    )
    assert (tmp_path / "artifact-files" / preview.storage_key).read_bytes() == (
        b"cad-output:preview.glb"
    )


def test_store_rejects_hash_mismatch_and_path_escape(tmp_path) -> None:
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging("cadjob_5678")
    manifest = _worker_manifest(staging)
    files = manifest["files"]
    assert isinstance(files, list)

    files[0]["relativePath"] = "../assembly.step"
    with pytest.raises(ValueError, match="相对路径"):
        store.validate_manifest("cadjob_5678", manifest)

    files[0]["relativePath"] = "assembly.step"
    files[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="哈希或大小"):
        store.validate_manifest("cadjob_5678", manifest)


def test_store_rejects_duplicate_file_name_across_roles(tmp_path) -> None:
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging("cadjob_duplicate")
    manifest = _worker_manifest(staging)
    files = manifest["files"]
    assert isinstance(files, list)
    files[1]["fileName"] = files[0]["fileName"]
    files[1]["relativePath"] = files[0]["fileName"]

    with pytest.raises(ValueError, match="角色、名称或 MIME"):
        store.validate_manifest("cadjob_duplicate", manifest)


def test_store_rejects_manifest_replayed_for_another_job_or_spec(tmp_path) -> None:
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging("cadjob_bound")
    manifest = _worker_manifest(staging)

    with pytest.raises(ValueError, match="Job 标识"):
        store.validate_manifest(
            "cadjob_bound",
            manifest,
            expected_design_id="cadjob_other",
            expected_spec_sha256="a" * 64,
        )

    with pytest.raises(ValueError, match="构建规范哈希"):
        store.validate_manifest(
            "cadjob_bound",
            manifest,
            expected_design_id="cadjob_1234",
            expected_spec_sha256="b" * 64,
        )
