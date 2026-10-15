"""Controlled adapter for the reviewed ZW-CAD-intent Node worker."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zhangwen.artifacts.models import ArtifactKind, ArtifactStatus
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.cad_engine.geometry import cadquery_available
from zhangwen.experts.context_assembler import (
    ContextAssembler,
    ContextAssemblyInput,
)
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.v2.kernel import ProjectKernel, ProjectKernelError
from zhangwen.v2.models import CreateChangeSetRequest


CAD_INTENT_PROTOCOL = "zhangwen.cad.intent.worker"
CAD_INTENT_VERSION = 1
MAX_WORKER_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_BUILD_FILE_BYTES = 128 * 1024 * 1024
MAX_BUILD_TOTAL_BYTES = 256 * 1024 * 1024
MAX_BUILD_FILE_COUNT = 16
MAX_GLB_BYTES = 20 * 1024 * 1024
BUILD_EXPORTS = {
    "glb": ("GLB_PREVIEW", "model/gltf-binary"),
    "step": ("STEP_ASSEMBLY", "model/step"),
    "stl": ("STL_PRINTABLE_PARTS", "model/stl"),
}


class CadIntentError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CadIntentPromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    mode: Literal["route", "draft", "edit"] = "draft"
    baseProjectVersion: int = Field(ge=0)
    currentRevisionId: str | None = Field(default=None, min_length=1, max_length=120)


class ProjectStructureFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    displayValue: str = Field(max_length=1200)
    revision: int = Field(ge=0)


class ProjectStructureHardware(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    skillName: str | None = Field(default=None, max_length=200)
    skillRevision: str | None = Field(default=None, max_length=160)


class ProjectStructureMechanicalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hardwareId: str = Field(min_length=1, max_length=160)
    profileId: str = Field(min_length=1, max_length=160)
    revision: str = Field(min_length=1, max_length=160)
    displayName: str = Field(min_length=1, max_length=240)
    evidenceLevel: str = Field(min_length=1, max_length=80)
    representation: str = Field(min_length=1, max_length=120)
    contentSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    geometry: dict[str, Any] = Field(default_factory=dict)


class ProjectStructureArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifactId: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    kind: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=80)
    currentVersionId: str | None = Field(default=None, max_length=160)
    version: int | None = Field(default=None, ge=1)
    summary: str | None = Field(default=None, max_length=1200)


class ProjectStructureCadObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    type: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=240)
    parentId: str | None = Field(default=None, max_length=160)


class ProjectStructureCadRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    sourceSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    objectIndex: list[ProjectStructureCadObject] = Field(
        default_factory=list, max_length=256
    )


class ProjectStructureContext(BaseModel):
    """Bounded, server-derived project context sent to the isolated CAD worker."""

    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal[1] = 1
    projectId: str = Field(min_length=1, max_length=160)
    projectVersion: int = Field(ge=0)
    projectionHash: str = Field(pattern=r"^[a-f0-9]{64}$")
    contextSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    projectName: str = Field(min_length=1, max_length=120)
    initialIdea: str = Field(max_length=4000)
    currentRecommendation: str | None = Field(default=None, max_length=4000)
    stage: str = Field(min_length=1, max_length=80)
    mode: str = Field(min_length=1, max_length=80)
    confirmedFacts: list[ProjectStructureFact] = Field(
        default_factory=list, max_length=24
    )
    selectedHardware: list[ProjectStructureHardware] = Field(
        default_factory=list, max_length=32
    )
    mechanicalProfiles: list[ProjectStructureMechanicalProfile] = Field(
        default_factory=list, max_length=32
    )
    upstreamArtifacts: list[ProjectStructureArtifact] = Field(
        default_factory=list, max_length=12
    )
    currentCadRevision: ProjectStructureCadRevision | None = None


class CadIntentUndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseProjectVersion: int = Field(ge=0)


class CadIntentWorkerClient:
    def __init__(
        self,
        *,
        worker_path: Path | None = None,
        node_executable: str | None = None,
        timeout_seconds: float = 25.0,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[4]
        configured_path = os.environ.get("ZHANGWEN_CAD_INTENT_WORKER", "").strip()
        self._worker_path = worker_path or (
            Path(configured_path)
            if configured_path
            else repository_root / "services" / "cad-intent-worker" / "src" / "worker.mjs"
        )
        self._node = node_executable or os.environ.get(
            "ZHANGWEN_NODE_EXECUTABLE", "node"
        ).strip()
        self._timeout_seconds = timeout_seconds

    def call(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        staging_root: Path | None = None,
        cadquery_available: bool = False,
    ) -> dict[str, Any]:
        if not self._worker_path.is_file():
            raise CadIntentError(
                "CAD_INTENT_WORKER_MISSING",
                "CAD Intent Worker 未安装或路径无效。",
                status_code=503,
            )
        request_id = f"cadreq-{uuid.uuid4().hex}"
        request = {
            "protocol": CAD_INTENT_PROTOCOL,
            "version": CAD_INTENT_VERSION,
            "id": request_id,
            "action": action,
            "payload": payload,
        }
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            timeout_seconds = (
                max(self._timeout_seconds, 120.0)
                if action == "build"
                else self._timeout_seconds
            )
            completed = subprocess.run(
                [self._node, str(self._worker_path)],
                input=f"{_dump(request)}\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
                env=_worker_environment(
                    staging_root=staging_root,
                    cadquery_available=cadquery_available,
                ),
            )
        except subprocess.TimeoutExpired as exc:
            raise CadIntentError(
                "CAD_INTENT_WORKER_TIMEOUT", "CAD Intent Worker 响应超时。", status_code=504
            ) from exc
        except OSError as exc:
            raise CadIntentError(
                "CAD_INTENT_WORKER_UNAVAILABLE",
                "无法启动本地 CAD Intent Worker，请检查 Node 运行时。",
                status_code=503,
            ) from exc
        if completed.returncode != 0:
            raise CadIntentError(
                "CAD_INTENT_WORKER_EXITED",
                "CAD Intent Worker 异常退出。",
                status_code=502,
            )
        stdout = completed.stdout.strip()
        if not stdout or len(stdout.encode("utf-8")) > MAX_WORKER_OUTPUT_BYTES:
            raise CadIntentError(
                "CAD_INTENT_RESPONSE_INVALID", "CAD Intent Worker 返回为空或超过上限。", status_code=502
            )
        try:
            response = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError as exc:
            raise CadIntentError(
                "CAD_INTENT_RESPONSE_INVALID", "CAD Intent Worker 返回格式无效。", status_code=502
            ) from exc
        if (
            response.get("protocol") != CAD_INTENT_PROTOCOL
            or response.get("version") != CAD_INTENT_VERSION
            or response.get("id") != request_id
        ):
            raise CadIntentError(
                "CAD_INTENT_PROTOCOL_MISMATCH", "CAD Intent Worker 响应协议不匹配。", status_code=502
            )
        if response.get("ok") is not True:
            error = response.get("error") if isinstance(response.get("error"), dict) else {}
            raise CadIntentError(
                str(error.get("code") or "CAD_INTENT_WORKER_ERROR"),
                str(error.get("message") or "CAD Intent Worker 执行失败。"),
                status_code=422,
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise CadIntentError(
                "CAD_INTENT_RESPONSE_INVALID", "CAD Intent Worker 缺少结果对象。", status_code=502
            )
        return result


class CadIntentService:
    def __init__(
        self,
        data_dir: Path,
        *,
        worker: CadIntentWorkerClient | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._projects = ProjectRepository(data_dir)
        self._kernel = ProjectKernel(data_dir)
        self._db_path = self._projects.db_path
        self._worker = worker or CadIntentWorkerClient()
        self._source_root = data_dir / "v2-cad" / "sources"
        self._build_root = data_dir / "v2-cad" / "builds"
        self._artifact_file_root = data_dir / "artifact-files"
        self._source_root.mkdir(parents=True, exist_ok=True)
        self._build_root.mkdir(parents=True, exist_ok=True)
        self._artifact_file_root.mkdir(parents=True, exist_ok=True)

    def workspace(self, project_id: str) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM cad_intent_revisions
                WHERE project_id = ? ORDER BY created_at DESC, id DESC
                """,
                (project_id,),
            ).fetchall()
            revisions = [self._revision_dict(row) for row in rows]
            jobs = self._list_jobs(conn, project_id)
        current_legacy = CadRepository(self._db_path).get_current_cad(project_id)
        return {
            "currentRevision": next(
                (item for item in revisions if item["status"] == "CONFIRMED"), None
            ),
            "pendingRevision": next(
                (item for item in revisions if item["status"] == "PLANNED"), None
            ),
            "revisions": revisions,
            "legacyCadRun": (
                current_legacy.model_dump(mode="json") if current_legacy else None
            ),
            "jobs": jobs,
        }

    def submit(
        self, project_id: str, request: CadIntentPromptRequest
    ) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        state = self._kernel.project_state(project_id)
        if request.baseProjectVersion != state["projectVersion"]:
            raise CadIntentError(
                "PROJECT_VERSION_CONFLICT",
                f"基础版本 {request.baseProjectVersion} 已过期，当前版本为 {state['projectVersion']}。",
                status_code=409,
            )
        current_revision = self._revision(
            project_id, request.currentRevisionId, required=request.mode == "edit"
        )
        structure_context = self._project_structure_context(
            project_id=project_id,
            state=state,
            current_revision=current_revision,
            user_message=request.prompt,
        )
        selected_hardware_ids = [
            item.id for item in structure_context.selectedHardware
        ]
        verified_capability_ids = set(
            state["capabilityCoverage"]["verifiedCapabilityIds"]
        )
        capabilities = [
            item
            for item in self._kernel.list_capabilities(project_id)
            if item["id"] in verified_capability_ids
        ]
        action = {"route": "route", "draft": "draft", "edit": "plan_edit"}[request.mode]
        payload: dict[str, Any] = {
            "projectId": project_id,
            "baseProjectVersion": state["projectVersion"],
            "prompt": request.prompt,
            "routeContext": {
                "workflowStage": "editing" if current_revision else "",
                "projectContextSha256": structure_context.contextSha256,
            },
            "projectStructureContext": structure_context.model_dump(
                mode="json", exclude_none=True
            ),
            "capabilitySnapshot": capabilities,
            "hardwareProfileSnapshot": {
                "selectedHardwareIds": selected_hardware_ids
            },
            "currentCadRevision": (
                {
                    "id": current_revision["id"],
                    "sourceSha256": current_revision["source_sha256"],
                    "objectIndex": _load(current_revision["object_index_json"], []),
                }
                if current_revision
                else None
            ),
        }
        if request.mode == "edit":
            assert current_revision is not None
            payload.update(
                {
                    "source": self._read_source(str(current_revision["source_storage_key"])),
                    "sourceSha256": str(current_revision["source_sha256"]),
                    "objectIndex": _load(current_revision["object_index_json"], []),
                }
            )
        request_hash = _hash(
            {
                "action": action,
                "projectId": project_id,
                "projectVersion": state["projectVersion"],
                "prompt": request.prompt,
                "sourceSha256": current_revision["source_sha256"] if current_revision else None,
                "projectStructureContextSha256": structure_context.contextSha256,
                "capabilityRevisions": sorted(
                    [f"{item['id']}:{item['revision']}" for item in capabilities]
                ),
            }
        )
        job_id = f"tooljob-{uuid.uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM tool_jobs
                WHERE project_id = ? AND kind = 'CAD_INTENT' AND request_hash = ?
                """,
                (project_id, request_hash),
            ).fetchone()
            if existing is not None:
                result = _load(existing["result_json"], {})
                return {"job": self._job_dict(existing), "result": result}
            conn.execute(
                """
                INSERT INTO tool_jobs (
                  id, project_id, kind, status, request_hash, request_json,
                  host_lease_id, progress, result_artifact_ids_json, error_json,
                  created_at, updated_at, result_json
                ) VALUES (?, ?, 'CAD_INTENT', 'RUNNING', ?, ?, NULL, 15, '[]',
                          NULL, ?, ?, NULL)
                """,
                (
                    job_id,
                    project_id,
                    request_hash,
                    _dump(
                        {
                            "mode": request.mode,
                            "baseProjectVersion": request.baseProjectVersion,
                            "promptSha256": hashlib.sha256(
                                request.prompt.encode("utf-8")
                            ).hexdigest(),
                            "projectStructureContextSha256": (
                                structure_context.contextSha256
                            ),
                        }
                    ),
                    now,
                    now,
                ),
            )
            conn.commit()
        try:
            result = self._worker.call(action, payload)
            revision = self._stage_revision(
                project_id=project_id,
                job_id=job_id,
                state=state,
                prompt=request.prompt,
                result=result,
                parent=current_revision,
            )
            if revision:
                result = {**result, "revision": revision}
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE tool_jobs SET status = 'SUCCEEDED', progress = 100,
                      result_json = ?, updated_at = ? WHERE id = ?
                    """,
                    (_dump(result), _now(), job_id),
                )
                conn.commit()
                job = conn.execute("SELECT * FROM tool_jobs WHERE id = ?", (job_id,)).fetchone()
                assert job is not None
                return {"job": self._job_dict(job), "result": result}
        except (CadIntentError, ProjectKernelError) as exc:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE tool_jobs SET status = 'FAILED', error_json = ?,
                      updated_at = ? WHERE id = ?
                    """,
                    (_dump({"code": exc.code, "message": exc.message}), _now(), job_id),
                )
                conn.commit()
            raise

    def _project_structure_context(
        self,
        *,
        project_id: str,
        state: dict[str, Any],
        current_revision: sqlite3.Row | None,
        user_message: str,
    ) -> ProjectStructureContext:
        """Build the only project context shape the isolated CAD worker accepts."""

        workspace = self._projects.get_workspace(project_id)
        raw_facts = state.get("facts")
        facts = raw_facts if isinstance(raw_facts, list) else []
        selected_hardware: list[dict[str, Any]] = []
        controlled_facts: list[dict[str, Any]] = []
        for item in facts:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            if key == "preferred_hardware":
                value = item.get("value")
                components = value.get("components") if isinstance(value, dict) else []
                if isinstance(components, list):
                    for component in components[:32]:
                        if not isinstance(component, dict):
                            continue
                        component_id = _bounded_optional_text(component.get("id"), 160)
                        name = _bounded_optional_text(component.get("name"), 200)
                        if not component_id or not name:
                            continue
                        selected_hardware.append(
                            {
                                "id": component_id,
                                "name": name,
                                "skillName": _bounded_optional_text(
                                    component.get("skillName"), 200
                                ),
                                "skillRevision": _bounded_optional_text(
                                    component.get("skillRevision"), 160
                                ),
                            }
                        )
                continue
            if key == "entry_router_result":
                continue
            label = _bounded_optional_text(item.get("label"), 200)
            if not key or not label:
                continue
            controlled_facts.append(
                {
                    "key": key[:120],
                    "label": label,
                    "displayValue": _bounded_optional_text(
                        item.get("displayValue"), 1200
                    )
                    or "",
                    "revision": max(0, int(item.get("revision") or 0)),
                }
            )
            if len(controlled_facts) >= 24:
                break

        try:
            assembled = ContextAssembler(self._db_path).assemble(
                ContextAssemblyInput(
                    projectId=project_id,
                    expert=ExpertType.STRUCTURE_ENGINEER,
                    userMessage=user_message,
                )
            )
        except (ValueError, sqlite3.Error) as exc:
            raise CadIntentError(
                "PROJECT_STRUCTURE_CONTEXT_UNAVAILABLE",
                "无法读取当前项目的结构上下文，已停止 CAD 生成。",
                status_code=409,
            ) from exc

        profiles: list[dict[str, Any]] = []
        for item in assembled.mechanicalProfiles[:32]:
            if not isinstance(item, dict) or item.get("mappingConfirmed") is False:
                continue
            content_sha256 = str(item.get("contentSha256") or "").lower()
            if not re.fullmatch(r"[a-f0-9]{64}", content_sha256):
                continue
            hardware_id = _bounded_optional_text(item.get("hardwareId"), 160)
            profile_id = _bounded_optional_text(item.get("profileId"), 160)
            revision = _bounded_optional_text(item.get("revision"), 160)
            display_name = _bounded_optional_text(item.get("displayName"), 240)
            if not hardware_id or not profile_id or not revision or not display_name:
                continue
            profile = item.get("profile")
            geometry = _controlled_structure_geometry(profile)
            profiles.append(
                {
                    "hardwareId": hardware_id,
                    "profileId": profile_id,
                    "revision": revision,
                    "displayName": display_name,
                    "evidenceLevel": _bounded_optional_text(
                        item.get("evidenceLevel"), 80
                    )
                    or "UNKNOWN",
                    "representation": _bounded_optional_text(
                        item.get("representation"), 120
                    )
                    or "unknown",
                    "contentSha256": content_sha256,
                    "geometry": geometry,
                }
            )

        artifacts: list[dict[str, Any]] = []
        for item in assembled.upstreamArtifacts[:12]:
            if not isinstance(item, dict):
                continue
            artifact_id = _bounded_optional_text(item.get("artifactId"), 160)
            title = _bounded_optional_text(item.get("title"), 240)
            kind = _bounded_optional_text(item.get("kind"), 80)
            status = _bounded_optional_text(item.get("status"), 80)
            if (
                not artifact_id
                or artifact_id.startswith("artifact_v2_cad_source_")
                or not title
                or not kind
                or not status
            ):
                continue
            raw_version = item.get("version")
            version = (
                int(raw_version)
                if isinstance(raw_version, int) and raw_version >= 1
                else None
            )
            artifacts.append(
                {
                    "artifactId": artifact_id,
                    "title": title,
                    "kind": kind,
                    "status": status,
                    "currentVersionId": _bounded_optional_text(
                        item.get("currentVersionId"), 160
                    ),
                    "version": version,
                    "summary": _bounded_optional_text(item.get("summary"), 1200),
                }
            )

        current_cad: dict[str, Any] | None = None
        if current_revision is not None:
            source_sha256 = str(current_revision["source_sha256"] or "").lower()
            object_index = _controlled_object_index(
                _load(current_revision["object_index_json"], [])
            )
            if re.fullmatch(r"[a-f0-9]{64}", source_sha256):
                current_cad = {
                    "id": str(current_revision["id"]),
                    "sourceSha256": source_sha256,
                    "objectIndex": object_index,
                }

        base_context = {
            "schemaVersion": 1,
            "projectId": project_id,
            "projectVersion": int(state["projectVersion"]),
            "projectionHash": str(state["projectionHash"]),
            "projectName": workspace.project.name[:120],
            "initialIdea": workspace.project.profile.initialIdea[:4000],
            "currentRecommendation": _bounded_optional_text(
                state.get("currentRecommendation"), 4000
            ),
            "stage": str(state.get("stage") or workspace.project.stage.value)[:80],
            "mode": str(state.get("mode") or "CREATOR")[:80],
            "confirmedFacts": controlled_facts,
            "selectedHardware": selected_hardware,
            "mechanicalProfiles": profiles,
            "upstreamArtifacts": artifacts,
            "currentCadRevision": current_cad,
        }
        if len(_dump(base_context).encode("utf-8")) > 96 * 1024:
            raise CadIntentError(
                "PROJECT_STRUCTURE_CONTEXT_TOO_LARGE",
                "当前项目结构上下文超过安全上限，请精简项目事实或上游产物后重试。",
                status_code=422,
            )
        try:
            return ProjectStructureContext.model_validate(
                {**base_context, "contextSha256": _hash(base_context)}
            )
        except ValidationError as exc:
            raise CadIntentError(
                "PROJECT_STRUCTURE_CONTEXT_INVALID",
                "当前项目结构上下文未通过边界校验，已停止 CAD 生成。",
                status_code=422,
            ) from exc

    def confirm_revision(self, project_id: str, revision_id: str) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            row = self._revision_row(conn, project_id, revision_id)
            if row["status"] == "CONFIRMED":
                return self._revision_dict(row)
            if row["status"] != "PLANNED" or not row["change_set_id"]:
                raise CadIntentError(
                    "CAD_REVISION_NOT_CONFIRMABLE", "当前 CAD 修订不能确认。", status_code=409
                )
            source = self._materialize_revision_source(conn, row)
        validation = self._worker.call("preflight", {"source": source})
        preflight = validation.get("preflight")
        if not isinstance(preflight, dict) or preflight.get("status") == "fail":
            with self._connect() as conn:
                conn.execute(
                    "UPDATE cad_intent_revisions SET status = 'REJECTED' WHERE id = ?",
                    (revision_id,),
                )
                conn.commit()
            raise CadIntentError(
                "CAD_SOURCE_PREFLIGHT_FAILED",
                "CAD 源码未通过 ZW-CAD-intent 安全预检，修订未提交。",
                status_code=422,
            )
        self._kernel.confirm_change_set(project_id, str(row["change_set_id"]))
        project_version = self._kernel.commit_change_set(
            project_id, str(row["change_set_id"])
        )
        artifact_id = f"artifact_v2_cad_source_{project_id}"
        revision_number = self._revision_number(project_id, revision_id)
        artifact_version = ArtifactRepository(self._db_path).upsert_text_artifact(
            artifact_id=artifact_id,
            project_id=project_id,
            title="V2 CAD 项目源码",
            kind=ArtifactKind.MODEL_3D,
            status=ArtifactStatus.NEEDS_REVIEW,
            source_agent_id="cad-agent",
            source_entity_type="cad_intent_revision",
            source_entity_id=revision_id,
            source_version=revision_number,
            content=source,
            summary="由 ZW-CAD-intent 行为基线生成并通过安全预检的 CadQuery 项目源码。",
            mime_type="text/x-python",
            language="python",
        )
        storage_key = self._write_source(project_id, revision_id, source)
        with self._connect() as conn:
            artifact_ids = list(project_version.get("artifactVersionIds", []))
            if artifact_version.id not in artifact_ids:
                artifact_ids.append(artifact_version.id)
                conn.execute(
                    "UPDATE project_versions SET artifact_version_ids_json = ? WHERE id = ?",
                    (_dump(sorted(artifact_ids)), project_version["id"]),
                )
            conn.execute(
                """
                UPDATE cad_intent_revisions SET status = 'CONFIRMED',
                  project_version_id = ?, source_storage_key = ?, source_sha256 = ?,
                  artifact_id = ?, artifact_version_id = ?, confirmed_at = ?
                WHERE id = ?
                """,
                (
                    project_version["id"],
                    storage_key,
                    _sha256(source),
                    artifact_id,
                    artifact_version.id,
                    _now(),
                    revision_id,
                ),
            )
            from zhangwen.domains.making.service import (
                invalidate_making_for_cad_revision,
            )

            invalidate_making_for_cad_revision(
                conn,
                work_id=project_id,
                cad_revision_id=revision_id,
                now=_now(),
            )
            self._append_event(
                conn,
                project_id,
                "CAD_REVISION_CREATED",
                project_version["version"],
                {"revisionId": revision_id, "sourceSha256": _sha256(source)},
            )
            conn.commit()
            confirmed = conn.execute(
                "SELECT * FROM cad_intent_revisions WHERE id = ?", (revision_id,)
            ).fetchone()
            assert confirmed is not None
            return self._revision_dict(confirmed)

    def build_revision(self, project_id: str, revision_id: str) -> dict[str, Any]:
        """Build a confirmed V2 source revision and publish its checked files.

        The intent worker may only write below the job staging directory.  This
        method independently checks every returned path, hashes the files, and
        then exposes only the allowlisted GLB/STEP/STL outputs through the
        existing ArtifactVersion file boundary.
        """

        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            revision = self._revision_row(conn, project_id, revision_id)
        if revision["status"] != "CONFIRMED":
            raise CadIntentError(
                "CAD_REVISION_NOT_CONFIRMED",
                "请先确认 CAD 源码修订，再生成 3D 模型。",
                status_code=409,
            )
        source = self._read_source(str(revision["source_storage_key"]))
        source_sha256 = _sha256(source)
        if source_sha256 != str(revision["source_sha256"]):
            raise CadIntentError(
                "CAD_SOURCE_HASH_MISMATCH",
                "已确认 CAD 源码校验失败，已停止构建。",
                status_code=409,
            )

        request_hash = _hash(
            {
                "action": "build",
                "projectId": project_id,
                "revisionId": revision_id,
                "sourceSha256": source_sha256,
            }
        )
        job_id = f"tooljob-{uuid.uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM tool_jobs
                WHERE project_id = ? AND kind = 'CAD_BUILD' AND request_hash = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id, request_hash),
            ).fetchone()
            if existing is not None and existing["status"] == "SUCCEEDED":
                result = _load(existing["result_json"], None)
                if isinstance(result, dict):
                    return result
            if existing is not None and existing["status"] == "RUNNING":
                raise CadIntentError(
                    "CAD_BUILD_RUNNING",
                    "当前 3D 模型正在构建，请在本地任务中查看进度。",
                    status_code=409,
                )
            if existing is not None:
                job_id = str(existing["id"])
                conn.execute(
                    """
                    UPDATE tool_jobs SET status = 'RUNNING', progress = 10,
                      result_artifact_ids_json = '[]', error_json = NULL,
                      result_json = NULL, updated_at = ? WHERE id = ?
                    """,
                    (now, job_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO tool_jobs (
                      id, project_id, kind, status, request_hash, request_json,
                      host_lease_id, progress, result_artifact_ids_json, error_json,
                      created_at, updated_at, result_json
                    ) VALUES (?, ?, 'CAD_BUILD', 'RUNNING', ?, ?, NULL, 10, '[]',
                              NULL, ?, ?, NULL)
                    """,
                    (
                        job_id,
                        project_id,
                        request_hash,
                        _dump(
                            {
                                "revisionId": revision_id,
                                "sourceSha256": source_sha256,
                            }
                        ),
                        now,
                        now,
                    ),
                )
            conn.commit()

        staging_root = self._build_root / _safe_id(job_id)
        staging_root.mkdir(parents=True, exist_ok=True)
        try:
            worker_result = self._worker.call(
                "build",
                {"source": source, "sourceSha256": source_sha256},
                staging_root=staging_root,
                cadquery_available=cadquery_available(),
            )
            status = str(worker_result.get("status") or "")
            if status != "artifact_exports":
                blocking_reason = str(worker_result.get("blockingReason") or "")
                message = str(worker_result.get("message") or "3D 模型构建未完成。")
                if blocking_reason == "pending_missing_cadquery":
                    raise CadIntentError(
                        "CAD_RUNTIME_UNAVAILABLE",
                        "本地 CAD 运行时缺少 CadQuery/OCP，无法生成真实 3D；请修复桌面运行时后重试。",
                        status_code=503,
                    )
                raise CadIntentError("CAD_BUILD_FAILED", message, status_code=422)
            result = self._publish_build_result(
                project_id=project_id,
                revision=revision,
                job_id=job_id,
                source=source,
                staging_root=staging_root,
                worker_result=worker_result,
            )
            return result
        except CadIntentError as exc:
            self._mark_build_failed(job_id, exc.code, exc.message)
            raise
        except (OSError, ValueError, sqlite3.Error) as exc:
            error = CadIntentError(
                "CAD_BUILD_PUBLISH_FAILED",
                "3D 已生成，但产物校验或发布失败；未向页面暴露不完整文件。",
                status_code=500,
            )
            self._mark_build_failed(job_id, error.code, error.message)
            raise error from exc

    def _publish_build_result(
        self,
        *,
        project_id: str,
        revision: sqlite3.Row,
        job_id: str,
        source: str,
        staging_root: Path,
        worker_result: dict[str, Any],
    ) -> dict[str, Any]:
        raw_exports = worker_result.get("exports")
        if not isinstance(raw_exports, list):
            raise CadIntentError("CAD_BUILD_OUTPUT_INVALID", "CAD Worker 未返回产物清单。")
        selected = self._validated_build_exports(staging_root, raw_exports)
        preview = next((item for item in selected if item["role"] == "GLB_PREVIEW"), None)
        if preview is None:
            raise CadIntentError(
                "CAD_PREVIEW_MISSING",
                "3D 构建没有生成可校验的 GLB 预览，已停止发布。",
                status_code=422,
            )

        artifact_id = str(revision["artifact_id"] or "")
        artifact_version_id = str(revision["artifact_version_id"] or "")
        if not artifact_id or not artifact_version_id:
            raise CadIntentError(
                "CAD_ARTIFACT_MISSING",
                "已确认修订缺少产物版本，无法发布 3D 文件。",
                status_code=409,
            )
        destination_root = (
            self._artifact_file_root
            / _safe_id(project_id)
            / _safe_id(artifact_id)
            / _safe_id(artifact_version_id)
        )
        destination_root.mkdir(parents=True, exist_ok=True)
        for item in selected:
            destination = destination_root / str(item["fileName"])
            if destination.exists():
                if not destination.is_file() or _sha256_file(destination) != item["sha256"]:
                    raise CadIntentError(
                        "CAD_ARTIFACT_FILE_CONFLICT",
                        "3D 产物目录存在不一致文件，已停止覆盖。",
                        status_code=409,
                    )
                continue
            temporary = destination.with_name(f"{destination.name}.{_safe_id(job_id)}.tmp")
            shutil.copyfile(item["sourcePath"], temporary)
            if temporary.stat().st_size != item["byteSize"] or _sha256_file(temporary) != item["sha256"]:
                temporary.unlink(missing_ok=True)
                raise CadIntentError(
                    "CAD_ARTIFACT_COPY_MISMATCH",
                    "3D 产物复制校验失败，已停止发布。",
                )
            temporary.replace(destination)
            item["storageKey"] = destination.relative_to(self._artifact_file_root).as_posix()
        for item in selected:
            if not item.get("storageKey"):
                item["storageKey"] = (
                    destination_root / str(item["fileName"])
                ).relative_to(self._artifact_file_root).as_posix()

        source_version = self._revision_number(project_id, str(revision["id"]))
        project_version = int(self._kernel.project_state(project_id)["projectVersion"])
        model_file_id = str(preview["fileId"])
        artifact_repository = ArtifactRepository(self._db_path)
        now = _now()
        with self._connect() as conn:
            version = artifact_repository.upsert_model_artifact(
                artifact_id=artifact_id,
                project_id=project_id,
                title="V2 结构 CAD 模型",
                status=ArtifactStatus.NEEDS_REVIEW,
                source_agent_id="cad-agent",
                source_entity_type="cad_intent_revision",
                source_entity_id=str(revision["id"]),
                source_version=source_version,
                content=source,
                summary="已由 ZW-CAD-intent 生成并通过本地构建校验的 3D 结构模型。",
                model_url=(
                    f"/api/projects/{project_id}/artifacts/{artifact_id}/versions/"
                    f"{artifact_version_id}/files/{model_file_id}"
                ),
                model_file_id=model_file_id,
                checksum=str(preview["sha256"]),
                connection=conn,
            )
            if version.id != artifact_version_id:
                raise CadIntentError(
                    "CAD_ARTIFACT_VERSION_MISMATCH",
                    "3D 构建结果与已确认产物版本不一致。",
                    status_code=409,
                )
            for item in selected:
                artifact_repository.insert_artifact_file(
                    conn,
                    file_id=str(item["fileId"]),
                    artifact_id=artifact_id,
                    artifact_version_id=artifact_version_id,
                    project_id=project_id,
                    role=str(item["role"]),
                    file_name=str(item["fileName"]),
                    storage_key=str(item["storageKey"]),
                    mime_type=str(item["mimeType"]),
                    byte_size=int(item["byteSize"]),
                    sha256=str(item["sha256"]),
                    triangle_count=None,
                    bounds=None,
                    created_at=now,
                )
            result = {
                "kind": "CadBuildResult",
                "status": "artifact_exports",
                "message": "3D 模型已生成并通过文件校验，可在结构视口查看。",
                "artifactId": artifact_id,
                "artifactVersionId": artifact_version_id,
                "modelFileId": model_file_id,
                "sourceSha256": str(revision["source_sha256"]),
                "fileCount": len(selected),
                "meshValidationStatus": worker_result.get("meshValidationStatus"),
            }
            conn.execute(
                """
                UPDATE tool_jobs SET status = 'SUCCEEDED', progress = 100,
                  result_artifact_ids_json = ?, result_json = ?, error_json = NULL,
                  updated_at = ? WHERE id = ?
                """,
                (_dump([artifact_id]), _dump(result), now, job_id),
            )
            self._append_event(
                conn,
                project_id,
                "CAD_BUILD_SUCCEEDED",
                project_version,
                {
                    "revisionId": str(revision["id"]),
                    "artifactVersionId": artifact_version_id,
                    "modelFileId": model_file_id,
                },
            )
            conn.commit()
        return result

    def _validated_build_exports(
        self, staging_root: Path, raw_exports: list[Any]
    ) -> list[dict[str, Any]]:
        root = staging_root.resolve()
        selected: list[dict[str, Any]] = []
        used_names: set[str] = set()
        has_step_assembly = False
        total_bytes = 0
        for raw in raw_exports:
            if not isinstance(raw, dict) or raw.get("status") not in {None, "available"}:
                continue
            file_format = str(raw.get("format") or "").lower()
            file_contract = BUILD_EXPORTS.get(file_format)
            if file_contract is None:
                continue
            storage_key = str(raw.get("storageKey") or "")
            candidate = (root / storage_key).resolve()
            if (
                not storage_key
                or not candidate.is_relative_to(root)
                or not candidate.is_file()
                or candidate.is_symlink()
            ):
                raise CadIntentError(
                    "CAD_BUILD_OUTPUT_INVALID",
                    "CAD Worker 返回了越界、缺失或不受支持的产物文件。",
                )
            byte_size = candidate.stat().st_size
            if byte_size <= 0 or byte_size > MAX_BUILD_FILE_BYTES:
                raise CadIntentError(
                    "CAD_BUILD_OUTPUT_TOO_LARGE",
                    "CAD 构建单文件为空或超过大小上限。",
                )
            if file_format == "glb" and byte_size > MAX_GLB_BYTES:
                raise CadIntentError("CAD_PREVIEW_TOO_LARGE", "GLB 预览超过 20 MiB 上限。")
            total_bytes += byte_size
            if total_bytes > MAX_BUILD_TOTAL_BYTES:
                raise CadIntentError("CAD_BUILD_OUTPUT_TOO_LARGE", "CAD 构建产物总量超过上限。")
            export_id = _safe_export_id(str(raw.get("id") or candidate.stem))
            file_name = "preview.glb" if file_format == "glb" else f"{export_id}.{file_format}"
            if file_name in used_names:
                continue
            used_names.add(file_name)
            role, mime_type = file_contract
            if file_format == "step":
                if has_step_assembly:
                    role = "STEP_PRINTABLE_PARTS"
                else:
                    has_step_assembly = True
            selected.append(
                {
                    "fileId": f"artifact_file_{hashlib.sha256(f'{storage_key}:{_sha256_file(candidate)}'.encode()).hexdigest()[:24]}",
                    "role": role,
                    "fileName": file_name,
                    "mimeType": mime_type,
                    "byteSize": byte_size,
                    "sha256": _sha256_file(candidate),
                    "sourcePath": candidate,
                    "storageKey": None,
                }
            )
            if len(selected) >= MAX_BUILD_FILE_COUNT:
                break
        if not selected:
            raise CadIntentError("CAD_BUILD_OUTPUT_INVALID", "CAD Worker 没有返回可发布的 3D 文件。")
        return selected

    def _mark_build_failed(self, job_id: str, code: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tool_jobs SET status = 'FAILED', error_json = ?,
                  updated_at = ? WHERE id = ?
                """,
                (_dump({"code": code, "message": message}), _now(), job_id),
            )
            conn.commit()

    def plan_undo(
        self, project_id: str, revision_id: str, base_project_version: int
    ) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            current = self._revision_row(conn, project_id, revision_id)
            if current["status"] != "CONFIRMED" or not current["parent_revision_id"]:
                raise CadIntentError(
                    "CAD_UNDO_UNAVAILABLE", "当前修订没有可恢复的父版本。", status_code=409
                )
            parent = self._revision_row(
                conn, project_id, str(current["parent_revision_id"])
            )
        state = self._kernel.project_state(project_id)
        if base_project_version != state["projectVersion"]:
            raise CadIntentError(
                "PROJECT_VERSION_CONFLICT",
                f"基础版本 {base_project_version} 已过期，当前版本为 {state['projectVersion']}。",
                status_code=409,
            )
        source = self._read_source(str(parent["source_storage_key"]))
        job_id = f"tooljob-{uuid.uuid4().hex}"
        revision_id_new = f"cadrev-{uuid.uuid4().hex}"
        now = _now()
        request_hash = _hash(
            {"action": "undo", "current": revision_id, "target": parent["id"]}
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_jobs (
                  id, project_id, kind, status, request_hash, request_json,
                  host_lease_id, progress, result_artifact_ids_json, error_json,
                  created_at, updated_at, result_json
                ) VALUES (?, ?, 'CAD_INTENT', 'SUCCEEDED', ?, ?, NULL, 100, '[]',
                          NULL, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    request_hash,
                    _dump({"mode": "undo", "revisionId": revision_id}),
                    now,
                    now,
                    _dump({"targetRevisionId": parent["id"]}),
                ),
            )
            storage_key = self._write_source(project_id, revision_id_new, source)
            conn.execute(
                """
                INSERT INTO cad_intent_revisions (
                  id, project_id, parent_revision_id, tool_job_id, change_set_id,
                  project_version_id, intent_summary, route_action, status,
                  source_storage_key, base_source_sha256, source_sha256,
                  pending_patch_json, object_index_json, artifact_id,
                  artifact_version_id, created_at, confirmed_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, 'undo_model_edit', 'PLANNED',
                          ?, ?, ?, NULL, ?, NULL, NULL, ?, NULL)
                """,
                (
                    revision_id_new,
                    project_id,
                    revision_id,
                    job_id,
                    f"恢复到修订 {parent['id']}",
                    storage_key,
                    current["source_sha256"],
                    parent["source_sha256"],
                    parent["object_index_json"],
                    now,
                ),
            )
            conn.commit()
        change_set = self._kernel.create_change_set(
            project_id,
            CreateChangeSetRequest.model_validate(
                {
                    "baseProjectVersion": state["projectVersion"],
                    "ownerDomain": "structure",
                    "intentSummary": f"恢复 CAD 修订到 {parent['id']}",
                    "operations": [
                        {
                            "op": "UPSERT_FACT",
                            "path": "/facts/structure/cad_revision",
                            "value": revision_id_new,
                        }
                    ],
                    "idempotencyKey": f"cad-undo:{job_id}",
                }
            ),
        )
        with self._connect() as conn:
            conn.execute(
                "UPDATE cad_intent_revisions SET change_set_id = ? WHERE id = ?",
                (change_set["id"], revision_id_new),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cad_intent_revisions WHERE id = ?", (revision_id_new,)
            ).fetchone()
            assert row is not None
            return self._revision_dict(row)

    def _stage_revision(
        self,
        *,
        project_id: str,
        job_id: str,
        state: dict[str, Any],
        prompt: str,
        result: dict[str, Any],
        parent: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        if result.get("status") != "ready":
            return None
        source = result.get("source")
        patch = result.get("patch")
        if not isinstance(source, str) and not isinstance(patch, dict):
            return None
        revision_id = f"cadrev-{uuid.uuid4().hex}"
        storage_key: str | None = None
        source_sha = str(result.get("sourceSha256") or "") or None
        if isinstance(source, str):
            if _sha256(source) != source_sha:
                raise CadIntentError(
                    "CAD_SOURCE_HASH_MISMATCH", "Worker 返回源码哈希不一致。", status_code=502
                )
            storage_key = self._write_source(project_id, revision_id, source)
        elif parent is not None:
            storage_key = str(parent["source_storage_key"])
            source_sha = str(result.get("resultSourceSha256") or "") or None
        object_index = result.get("objectIndex")
        if not isinstance(object_index, list):
            object_index = _load(parent["object_index_json"], []) if parent else []
        now = _now()
        route = result.get("route") if isinstance(result.get("route"), dict) else {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cad_intent_revisions (
                  id, project_id, parent_revision_id, tool_job_id, change_set_id,
                  project_version_id, intent_summary, route_action, status,
                  source_storage_key, base_source_sha256, source_sha256,
                  pending_patch_json, object_index_json, artifact_id,
                  artifact_version_id, created_at, confirmed_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, 'PLANNED', ?, ?, ?, ?, ?,
                          NULL, NULL, ?, NULL)
                """,
                (
                    revision_id,
                    project_id,
                    str(parent["id"]) if parent else None,
                    job_id,
                    prompt,
                    str(route.get("route_action") or "new_requirement"),
                    storage_key,
                    str(parent["source_sha256"]) if parent else source_sha,
                    source_sha,
                    _dump(patch) if isinstance(patch, dict) else None,
                    _dump(object_index),
                    now,
                ),
            )
            conn.commit()
        change_set = self._kernel.create_change_set(
            project_id,
            CreateChangeSetRequest.model_validate(
                {
                    "baseProjectVersion": state["projectVersion"],
                    "ownerDomain": "structure",
                    "intentSummary": prompt,
                    "operations": [
                        {
                            "op": "UPSERT_FACT",
                            "path": "/facts/structure/cad_revision",
                            "value": revision_id,
                        }
                    ],
                    "idempotencyKey": f"cad-intent:{job_id}",
                }
            ),
        )
        with self._connect() as conn:
            conn.execute(
                "UPDATE cad_intent_revisions SET change_set_id = ? WHERE id = ?",
                (change_set["id"], revision_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cad_intent_revisions WHERE id = ?", (revision_id,)
            ).fetchone()
            assert row is not None
            return self._revision_dict(row)

    def _materialize_revision_source(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> str:
        patch = _load(row["pending_patch_json"], None)
        if not isinstance(patch, dict):
            source = self._read_source(str(row["source_storage_key"]))
            if _sha256(source) != row["source_sha256"]:
                raise CadIntentError(
                    "CAD_SOURCE_HASH_MISMATCH", "待确认 CAD 源码已变化。", status_code=409
                )
            return source
        parent = self._revision_row(
            conn, str(row["project_id"]), str(row["parent_revision_id"])
        )
        source = self._read_source(str(parent["source_storage_key"]))
        if _sha256(source) != row["base_source_sha256"]:
            raise CadIntentError(
                "CAD_SOURCE_HASH_MISMATCH", "基础 CAD 源码已变化。", status_code=409
            )
        search = patch.get("search")
        replace = patch.get("replace")
        if not isinstance(search, str) or not isinstance(replace, str):
            raise CadIntentError("CAD_PATCH_INVALID", "CAD 补丁格式无效。")
        if source.count(search) != 1:
            raise CadIntentError(
                "CAD_PATCH_TARGET_AMBIGUOUS", "CAD 补丁目标不存在或不唯一。", status_code=409
            )
        materialized = source.replace(search, replace, 1)
        if _sha256(materialized) != patch.get("resultSha256"):
            raise CadIntentError("CAD_PATCH_HASH_MISMATCH", "CAD 补丁结果哈希不一致。")
        return materialized

    def _revision(
        self, project_id: str, revision_id: str | None, *, required: bool
    ) -> sqlite3.Row | None:
        with self._connect() as conn:
            if revision_id:
                return self._revision_row(conn, project_id, revision_id)
            row = conn.execute(
                """
                SELECT * FROM cad_intent_revisions
                WHERE project_id = ? AND status = 'CONFIRMED'
                ORDER BY confirmed_at DESC, created_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if required and row is None:
                raise CadIntentError(
                    "CAD_REVISION_REQUIRED", "当前项目还没有可修改的 V2 CAD 修订。", status_code=409
                )
            return row

    def _revision_row(
        self, conn: sqlite3.Connection, project_id: str, revision_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM cad_intent_revisions WHERE id = ? AND project_id = ?
            """,
            (revision_id, project_id),
        ).fetchone()
        if row is None:
            raise CadIntentError("CAD_REVISION_NOT_FOUND", "CAD 修订不存在。", status_code=404)
        return row

    def _write_source(self, project_id: str, revision_id: str, source: str) -> str:
        target = self._source_root / _safe_id(project_id) / _safe_id(revision_id) / "model.cq.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(source, encoding="utf-8", newline="\n")
        temporary.replace(target)
        return target.relative_to(self._source_root).as_posix()

    def _read_source(self, storage_key: str) -> str:
        target = (self._source_root / storage_key).resolve()
        root = self._source_root.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise CadIntentError("CAD_SOURCE_MISSING", "CAD 项目源码不存在。", status_code=409)
        if target.stat().st_size > 384 * 1024:
            raise CadIntentError("CAD_SOURCE_TOO_LARGE", "CAD 项目源码超过大小上限。")
        return target.read_text(encoding="utf-8")

    def _revision_number(self, project_id: str, revision_id: str) -> int:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM cad_intent_revisions
                WHERE project_id = ? ORDER BY created_at, id
                """,
                (project_id,),
            ).fetchall()
        return next(index for index, row in enumerate(rows, 1) if row["id"] == revision_id)

    def _revision_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "projectId": str(row["project_id"]),
            "parentRevisionId": (
                str(row["parent_revision_id"]) if row["parent_revision_id"] else None
            ),
            "toolJobId": str(row["tool_job_id"]),
            "changeSetId": str(row["change_set_id"]) if row["change_set_id"] else None,
            "projectVersionId": (
                str(row["project_version_id"]) if row["project_version_id"] else None
            ),
            "intentSummary": str(row["intent_summary"]),
            "routeAction": str(row["route_action"]),
            "status": str(row["status"]),
            "sourceSha256": str(row["source_sha256"]) if row["source_sha256"] else None,
            "objectIndex": _load(row["object_index_json"], []),
            "artifactId": str(row["artifact_id"]) if row["artifact_id"] else None,
            "artifactVersionId": (
                str(row["artifact_version_id"]) if row["artifact_version_id"] else None
            ),
            "createdAt": str(row["created_at"]),
            "confirmedAt": str(row["confirmed_at"]) if row["confirmed_at"] else None,
        }

    def _list_jobs(self, conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM tool_jobs WHERE project_id = ? AND kind IN ('CAD_INTENT', 'CAD_BUILD')
            ORDER BY updated_at DESC LIMIT 30
            """,
            (project_id,),
        ).fetchall()
        return [self._job_dict(row) for row in rows]

    def _job_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "projectId": str(row["project_id"]),
            "kind": str(row["kind"]),
            "status": str(row["status"]),
            "requestHash": str(row["request_hash"]),
            "hostLeaseId": str(row["host_lease_id"]) if row["host_lease_id"] else None,
            "progress": int(row["progress"]),
            "resultArtifactIds": _load(row["result_artifact_ids_json"], []),
            "error": _load(row["error_json"], None),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    def _append_event(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        event_type: str,
        project_version: int,
        payload: dict[str, Any],
    ) -> None:
        sequence = int(
            conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM project_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        )
        conn.execute(
            """
            INSERT INTO project_events (
              id, project_id, sequence, event_type, change_set_id,
              project_version, payload_json, created_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                f"pevt-{uuid.uuid4().hex}",
                project_id,
                sequence,
                event_type,
                project_version,
                _dump(payload),
                _now(),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _safe_id(value: str) -> str:
    if not value or len(value) > 120 or not all(character.isalnum() or character in "-_" for character in value):
        raise CadIntentError("CAD_ID_INVALID", "CAD 标识无效。")
    return value


def _safe_export_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    if not normalized:
        normalized = "cad_export"
    return normalized[:120]


def _bounded_optional_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized[:limit] or None


def _controlled_structure_geometry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = (
        "profile_id",
        "revision",
        "category",
        "roles",
        "dimensions",
        "coordinate_system",
        "mounting",
        "model_kind",
        "keepouts",
        "openings",
        "preview_geometry",
    )
    controlled = {
        key: _controlled_json(value[key], depth=0)
        for key in allowed
        if key in value
    }
    if len(_dump(controlled).encode("utf-8")) > 24 * 1024:
        return {
            key: controlled[key]
            for key in (
                "profile_id",
                "revision",
                "dimensions",
                "coordinate_system",
                "mounting",
                "model_kind",
            )
            if key in controlled
        }
    return controlled


def _controlled_json(value: Any, *, depth: int) -> Any:
    if depth > 6:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list | tuple):
        return [
            _controlled_json(item, depth=depth + 1)
            for item in list(value)[:64]
        ]
    if isinstance(value, dict):
        return {
            str(key)[:120]: _controlled_json(child, depth=depth + 1)
            for key, child in list(value.items())[:64]
        }
    return str(value)[:500]


def _controlled_object_index(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value[:256]:
        if not isinstance(item, dict):
            continue
        object_id = _bounded_optional_text(item.get("id"), 160)
        object_type = _bounded_optional_text(item.get("type"), 80)
        label = _bounded_optional_text(item.get("label"), 240)
        if not object_id or not object_type or not label:
            continue
        result.append(
            {
                "id": object_id,
                "type": object_type,
                "label": label,
                "parentId": _bounded_optional_text(item.get("parentId"), 160),
            }
        )
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _worker_environment(
    *, staging_root: Path | None, cadquery_available: bool
) -> dict[str, str]:
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
    }
    environment = {
        key: value for key, value in os.environ.items() if key in allowed and value
    }
    environment["ZHANGWEN_CAD_PYTHON"] = sys.executable
    environment["ZHANGWEN_CADQUERY_AVAILABLE"] = "1" if cadquery_available else "0"
    environment["PYTHONUTF8"] = "1"
    if staging_root is not None:
        resolved = staging_root.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        environment["ZHANGWEN_CAD_STAGING_ROOT"] = str(resolved)
        # CadQuery imports ezdxf, whose configuration discovery requires a
        # home directory.  Point it at a job-owned directory instead of
        # exposing the user's real profile to the isolated Worker.
        runtime_home = resolved / "runtime-home"
        runtime_home.mkdir(parents=True, exist_ok=True)
        environment["HOME"] = str(runtime_home)
        environment["USERPROFILE"] = str(runtime_home)
    return environment


def _load(value: Any, default: Any) -> Any:
    if value in {None, ""}:
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return default


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_dump(value).encode("utf-8")).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
