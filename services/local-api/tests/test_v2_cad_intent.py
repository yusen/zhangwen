from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.cad_engine import cadquery_available
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.v2.cad_intent import (
    CadIntentPromptRequest,
    CadIntentService,
    CadIntentWorkerClient,
)
from zhangwen.v2.kernel import ProjectKernel


SOURCE_V1 = """import cadquery as cq
parameters = {"wall_thickness": 2.4}
result = cq.Workplane("XY").box(40, 30, 20)
"""


class FakeCadIntentWorker:
    def call(
        self,
        action,
        payload,
        *,
        staging_root: Path | None = None,
        cadquery_available: bool = False,
    ):
        if action == "draft":
            return {
                "kind": "CadDraft",
                "status": "ready",
                "route": {"route_action": "new_requirement"},
                "source": SOURCE_V1,
                "sourceSha256": _sha(SOURCE_V1),
                "objectIndex": [
                    {"id": "assembly", "type": "assembly", "label": "当前装配"},
                    {"id": "base_part", "type": "part", "label": "底壳"},
                ],
            }
        if action == "plan_edit":
            source = payload["source"]
            search = 'wall_thickness": 2.4'
            replace = 'wall_thickness": 3.4'
            changed = source.replace(search, replace, 1)
            return {
                "kind": "CadChangeSet",
                "status": "ready",
                "route": {"route_action": "model_edit"},
                "sourceSha256": _sha(source),
                "resultSourceSha256": _sha(changed),
                "patch": {
                    "search": search,
                    "replace": replace,
                    "occurrence": 1,
                    "resultSha256": _sha(changed),
                },
                "objectIndex": payload["objectIndex"],
            }
        if action == "preflight":
            return {
                "kind": "CadValidationReport",
                "sourceSha256": _sha(payload["source"]),
                "preflight": {"status": "pass", "checks": []},
            }
        if action == "build":
            assert staging_root is not None
            assert cadquery_available is True
            export_dir = staging_root / "exports" / "fake-build"
            export_dir.mkdir(parents=True)
            files = {
                "preview.glb": b"glTF-fake-preview",
                "model.step": b"ISO-10303-21;fake-step",
                "base.stl": b"solid base\nendsolid base\n",
            }
            exports = []
            for name, content in files.items():
                target = export_dir / name
                target.write_bytes(content)
                exports.append(
                    {
                        "id": name.replace(".", "_"),
                        "label": name,
                        "format": name.rsplit(".", 1)[-1],
                        "fidelity": "cadquery",
                        "status": "available",
                        "storageKey": target.relative_to(staging_root).as_posix(),
                    }
                )
            return {
                "kind": "CadBuildResult",
                "status": "artifact_exports",
                "sourceSha256": payload["sourceSha256"],
                "exports": exports,
                "meshValidationStatus": "pass",
                "meshValidationReport": {"status": "pass", "checks": []},
            }
        raise AssertionError(action)


class CapturingCadIntentWorker:
    def __init__(self) -> None:
        self.payload = None

    def call(self, action, payload, **_kwargs):
        assert action == "draft"
        self.payload = payload
        return {
            "kind": "CadDraft",
            "status": "needs_input",
            "message": "测试只检查上下文边界。",
        }


def _project(tmp_path):
    return ProjectRepository(tmp_path).create_project(
        "V2 CAD",
        "做一个自动浇花系统并可修改外壳",
        selected_expert_types=[ExpertType.STRUCTURE_ENGINEER],
    ).project.id


def test_real_node_worker_is_callable_without_http_or_legacy_project_store() -> None:
    described = CadIntentWorkerClient().call("describe", {})

    assert described["source"] == "ZW-CAD-intent"
    assert "no_http" in described["boundaries"]
    assert any(item["id"] == "surface_engraving" for item in described["workflowTools"])


def test_cad_intent_derives_bounded_context_from_current_project_only(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    project_id = repository.create_project(
        "电子相册",
        "做一个行空板电子相册，使用板载摄像头浏览照片。",
        selected_expert_types=[ExpertType.STRUCTURE_ENGINEER],
    ).project.id
    repository.replace_preferred_hardware(project_id, ["hw_seed_unihiker_k10"])
    version = ProjectKernel(tmp_path).project_state(project_id)["projectVersion"]
    worker = CapturingCadIntentWorker()
    service = CadIntentService(tmp_path, worker=worker)

    service.submit(
        project_id,
        CadIntentPromptRequest(
            prompt="给这个项目生成一个外壳",
            mode="draft",
            baseProjectVersion=version,
        ),
    )

    assert worker.payload is not None
    context = worker.payload["projectStructureContext"]
    assert context["schemaVersion"] == 1
    assert context["projectId"] == project_id
    assert context["projectVersion"] == version
    assert context["initialIdea"].startswith("做一个行空板电子相册")
    assert context["contextSha256"]
    assert len(context["selectedHardware"]) == 1
    selected_hardware = context["selectedHardware"][0]
    assert selected_hardware["id"] == "hw_seed_unihiker_k10"
    assert selected_hardware["name"] == "行空板 K10"
    assert selected_hardware["skillName"]
    assert selected_hardware["skillRevision"]
    assert worker.payload["hardwareProfileSnapshot"]["selectedHardwareIds"] == [
        "hw_seed_unihiker_k10"
    ]
    project_hardware_capabilities = [
        item["sourceId"]
        for item in worker.payload["capabilitySnapshot"]
        if item["sourceType"] == "hardware_component"
    ]
    assert project_hardware_capabilities == ["hw_seed_unihiker_k10"]
    assert "conversationMessages" not in context
    assert "provider" not in context
    assert "paths" not in context


def test_real_v2_worker_builds_downloadable_glb_step_and_stl(tmp_path) -> None:
    project_id = _project(tmp_path)
    service = CadIntentService(tmp_path)

    drafted = service.submit(
        project_id,
        CadIntentPromptRequest(
            prompt="automatic plant watering enclosure",
            mode="draft",
            baseProjectVersion=0,
        ),
    )
    revision = service.confirm_revision(
        project_id,
        drafted["result"]["revision"]["id"],
    )
    built = service.build_revision(project_id, revision["id"])

    assert built["status"] == "artifact_exports"
    assert built["fileCount"] >= 3
    repository = ArtifactRepository(ProjectRepository(tmp_path).db_path)
    files = repository.list_artifact_files(
        project_id,
        built["artifactId"],
        built["artifactVersionId"],
    )
    assert {item.role for item in files} >= {
        "GLB_PREVIEW",
        "STEP_ASSEMBLY",
        "STL_PRINTABLE_PARTS",
    }
    preview = next(item for item in files if item.id == built["modelFileId"])
    metadata, storage_key = repository.get_artifact_file(
        project_id,
        built["artifactId"],
        built["artifactVersionId"],
        preview.id,
    )
    payload = (tmp_path / "artifact-files" / storage_key).read_bytes()
    assert metadata.byteSize == len(payload)
    assert payload[:4] == b"glTF"
    assert metadata.sha256 == hashlib.sha256(payload).hexdigest()

    workspace = service.workspace(project_id)
    assert workspace["currentRevision"]["id"] == revision["id"]
    assert workspace["jobs"][0]["kind"] == "CAD_BUILD"
    assert workspace["jobs"][0]["status"] == "SUCCEEDED"


@pytest.mark.skipif(not cadquery_available(), reason="CadQuery runtime unavailable")
def test_real_v2_worker_publishes_contextual_k10_build_with_only_existing_exports(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    project_id = repository.create_project(
        "行空板 K10 桌面电子相册",
        "用行空板 K10 做电子相册，需要可 3D 打印的桌面倾斜支架。",
        selected_expert_types=[ExpertType.STRUCTURE_ENGINEER],
    ).project.id
    repository.replace_preferred_hardware(project_id, ["hw_seed_unihiker_k10"])
    service = CadIntentService(tmp_path)
    project_version = ProjectKernel(tmp_path).project_state(project_id)["projectVersion"]

    drafted = service.submit(
        project_id,
        CadIntentPromptRequest(
            prompt="根据当前项目上下文生成可 3D 打印的桌面结构，沿用已确认机械约束。",
            mode="draft",
            baseProjectVersion=project_version,
        ),
    )
    revision = service.confirm_revision(
        project_id,
        drafted["result"]["revision"]["id"],
    )
    built = service.build_revision(project_id, revision["id"])

    assert built["status"] == "artifact_exports"
    assert built["fileCount"] >= 3
    files = ArtifactRepository(repository.db_path).list_artifact_files(
        project_id,
        built["artifactId"],
        built["artifactVersionId"],
    )
    assert {item.role for item in files} >= {
        "GLB_PREVIEW",
        "STEP_ASSEMBLY",
        "STL_PRINTABLE_PARTS",
    }


def test_cad_revision_confirm_edit_and_undo_are_hash_bound(tmp_path) -> None:
    project_id = _project(tmp_path)
    service = CadIntentService(tmp_path, worker=FakeCadIntentWorker())

    drafted = service.submit(
        project_id,
        CadIntentPromptRequest(
            prompt="做一个自动浇花外壳",
            mode="draft",
            baseProjectVersion=0,
        ),
    )
    revision_v1 = drafted["result"]["revision"]
    assert revision_v1["status"] == "PLANNED"
    assert revision_v1["changeSetId"]

    confirmed_v1 = service.confirm_revision(project_id, revision_v1["id"])
    assert confirmed_v1["status"] == "CONFIRMED"
    assert confirmed_v1["artifactVersionId"]
    assert confirmed_v1["sourceSha256"] == _sha(SOURCE_V1)

    built_v1 = service.build_revision(project_id, confirmed_v1["id"])
    assert built_v1["status"] == "artifact_exports"
    assert built_v1["modelFileId"]
    assert built_v1["artifactId"] == confirmed_v1["artifactId"]
    artifact_repository = ArtifactRepository(ProjectRepository(tmp_path).db_path)
    artifact = artifact_repository.get_artifact(project_id, confirmed_v1["artifactId"])
    artifact_version = next(
        item for item in artifact.versions if item.id == confirmed_v1["artifactVersionId"]
    )
    assert artifact_version.preview.kind.value == "MODEL_3D"
    assert artifact_version.preview.modelFileId == built_v1["modelFileId"]
    files = artifact_repository.list_artifact_files(
        project_id,
        confirmed_v1["artifactId"],
        confirmed_v1["artifactVersionId"],
    )
    assert {item.role for item in files} == {
        "GLB_PREVIEW",
        "STEP_ASSEMBLY",
        "STL_PRINTABLE_PARTS",
    }

    repeated_build = service.build_revision(project_id, confirmed_v1["id"])
    assert repeated_build == built_v1

    edited = service.submit(
        project_id,
        CadIntentPromptRequest(
            prompt="底壳壁厚增加 1mm",
            mode="edit",
            baseProjectVersion=1,
            currentRevisionId=confirmed_v1["id"],
        ),
    )
    revision_v2 = edited["result"]["revision"]
    confirmed_v2 = service.confirm_revision(project_id, revision_v2["id"])
    assert confirmed_v2["parentRevisionId"] == confirmed_v1["id"]
    assert confirmed_v2["sourceSha256"] == _sha(
        SOURCE_V1.replace('wall_thickness": 2.4', 'wall_thickness": 3.4')
    )

    undo = service.plan_undo(project_id, confirmed_v2["id"], 2)
    confirmed_undo = service.confirm_revision(project_id, undo["id"])
    assert confirmed_undo["sourceSha256"] == confirmed_v1["sourceSha256"]

    workspace = service.workspace(project_id)
    assert workspace["currentRevision"]["id"] == confirmed_undo["id"]
    assert [item["status"] for item in workspace["revisions"]].count("CONFIRMED") == 3
    assert len(workspace["jobs"]) == 4


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
