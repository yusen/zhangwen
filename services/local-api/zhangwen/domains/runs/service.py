"""Unified Work Run application service over the existing local simulator."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from zhangwen.creator.models import (
    CreatorCommand,
    CreatorCommandRequest,
    EvidenceKind,
    EvidenceStatus,
)
from zhangwen.creator.repository import CreatorRepository
from zhangwen.device_lab.models import (
    CreateDeviceLabRunRequest,
    DeviceLabRunStatus,
    DeviceLabScenarioResult,
    DeviceLabSceneV1,
    DeviceLabTarget,
    UpdateDeviceLabChannelRequest,
)
from zhangwen.device_lab.service import DeviceLabService
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.runs.repository import WorkRunRepository
from zhangwen.domains.works.models import (
    CompleteWorkRunRequest,
    StartWorkRunRequest,
    UpdateWorkRunControlRequest,
    WorkRunListResponse,
    WorkRunResponse,
)
from zhangwen.domains.works.repository import WorkRepository
from zhangwen.projects.repository import ProjectRepository


class WorkRunError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class WorkRunService:
    def __init__(self, data_dir: Path, lab: DeviceLabService) -> None:
        self._data_dir = Path(data_dir)
        self._creator = CreatorRepository(self._data_dir)
        self._works = WorkRepository(self._data_dir)
        self._runs = WorkRunRepository(self._data_dir)
        self._lab = lab
        self._db_path = ProjectRepository(self._data_dir).db_path
        self._events = RealtimeEventStore(self._db_path)

    def list_runs(self, work_id: str) -> WorkRunListResponse:
        workspace = self._creator.workspace(work_id)
        return WorkRunListResponse(runs=self._runs.list_runs(workspace))

    async def start(
        self,
        work_id: str,
        request: StartWorkRunRequest,
    ) -> WorkRunResponse:
        workspace = self._creator.workspace(work_id)
        solution = workspace.current_solution
        if solution is None:
            raise WorkRunError(
                "WORK_RUN_SOLUTION_REQUIRED",
                "请先和掌问确认当前方案，再开始数字试运行。",
                409,
            )
        scene = self._lab.get_work_functional_scene(work_id)
        if scene.status != "READY":
            raise WorkRunError(
                "WORK_RUN_SCENE_NOT_READY",
                "当前场景还有连接需要确认，完成后才能开始数字试运行。",
                409,
            )
        if scene.binding is None or scene.binding.codeRunId is None:
            raise WorkRunError(
                "WORK_RUN_CODE_NOT_READY",
                "作品逻辑仍在本机准备和检查，完成后再开始数字试运行。",
                409,
            )
        self._ensure_static_evidence(work_id, scene)
        response = await self._lab.create_work_run(
            work_id,
            CreateDeviceLabRunRequest(
                idempotencyKey=request.idempotency_key,
                target=DeviceLabTarget.SIMULATOR,
                engine=request.engine,
                parameterSetId=request.parameter_set_id,
                expectedSceneRevision=scene.revision,
                expectedSolutionRevisionId=solution.id,
                codeRunId=(scene.binding.codeRunId if scene.binding else None),
            ),
        )
        self._append_event(
            work_id,
            event_type="work.run.started",
            source_event_id=f"work-run:{response.run.id}:started",
            payload={
                "runId": response.run.id,
                "naturalStatus": "数字试运行已开始",
            },
        )
        return self._response(work_id, response.run.id)

    async def update_control(
        self,
        work_id: str,
        run_id: str,
        control_id: str,
        request: UpdateWorkRunControlRequest,
        *,
        advanced: bool,
    ) -> WorkRunResponse:
        workspace = self._creator.workspace(work_id)
        projected = self._runs.get(workspace, run_id)
        allowed = projected.advanced_controls if advanced else projected.inputs
        if control_id not in {item.id for item in allowed if item.writable}:
            raise WorkRunError(
                "WORK_RUN_CONTROL_NOT_AVAILABLE",
                "这个控制项不属于当前作品场景。",
                404,
            )
        response = await self._lab.update_channel(
            work_id,
            run_id,
            control_id,
            UpdateDeviceLabChannelRequest(
                value=request.value,
                expectedRevision=request.expected_revision,
                actuatorArmed=False,
                commandId=request.command_id,
            ),
        )
        return self._response(work_id, response.run.id)

    async def complete(
        self,
        work_id: str,
        run_id: str,
        request: CompleteWorkRunRequest,
    ) -> WorkRunResponse:
        workspace = self._creator.workspace(work_id)
        projected = self._runs.get(workspace, run_id)
        scenario_by_id = {item.id: item for item in projected.scenarios}
        result_ids = [item.scenario_id for item in request.scenario_results]
        if len(set(result_ids)) != len(result_ids) or any(
            item_id not in scenario_by_id for item_id in result_ids
        ):
            raise WorkRunError(
                "WORK_RUN_SCENARIO_INVALID",
                "试运行结果包含重复或不属于当前作品的场景。",
            )
        required = {item.id for item in projected.scenarios if item.required}
        if not required.issubset(result_ids):
            raise WorkRunError(
                "WORK_RUN_SCENARIOS_INCOMPLETE",
                "请先检查所有必需场景，再形成这次试运行结果。",
                409,
            )
        current = self._lab.get_run(work_id, run_id)
        if current.run.status is DeviceLabRunStatus.RUNNING:
            current = await self._lab.stop_run(work_id, run_id)
        if current.run.status is not DeviceLabRunStatus.STOPPED:
            raise WorkRunError(
                "WORK_RUN_NOT_STOPPED",
                "数字试运行未能安全停止，请重试安全停止。",
                409,
            )
        passed = all(item.passed for item in request.scenario_results)
        if passed:
            summary = "所有必需场景都达到预期，当前方案的数字试运行已通过。"
        else:
            failed = next(item for item in request.scenario_results if not item.passed)
            title = scenario_by_id[failed.scenario_id].title
            summary = f"“{title}”没有达到预期。建议先调整作品输入或当前方案，然后重新试运行。"
        recorded = await self._lab.record_result(
            work_id,
            run_id,
            scenario_results=[
                DeviceLabScenarioResult(
                    scenarioId=item.scenario_id,
                    passed=item.passed,
                )
                for item in request.scenario_results
            ],
            summary=summary,
            idempotency_key=request.idempotency_key,
        )
        run = recorded.run
        bindings = run.revisionBindings
        if bindings is None:
            raise WorkRunError(
                "WORK_RUN_REVISION_SET_MISSING",
                "这次试运行没有完整固定当前版本，请按当前方案重新开始。",
                409,
            )
        self._record_simulation_evidence(
            work_id,
            run_id,
            idempotency_key=request.idempotency_key,
            passed=passed,
            summary=summary,
            scenario_ids=[
                item.scenario_id for item in request.scenario_results if item.passed
            ],
            scene_revision=bindings.scene_revision,
            solution_revision_id=bindings.solution_revision_id,
            code_run_id=bindings.code_run_id,
            parameter_set_id=bindings.parameter_set_id,
            runtime_bindings_json=(
                json.dumps(
                    [
                        {
                            "packageKind": item.package_kind.value,
                            "packageId": item.package_id,
                            "packageRevisionId": item.package_revision_id,
                        }
                        for item in run.executionRevisionSet.bindings
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if run.executionRevisionSet is not None
                else "[]"
            ),
            wokwi_bindings=(
                {
                    "diagramSha256": run.wokwiBinding.diagramSha256,
                    "firmwareSha256": run.wokwiBinding.firmwareSha256,
                    "firmwareBaseRevision": run.wokwiBinding.firmwareBaseRevision,
                }
                if run.wokwiBinding is not None
                else {}
            ),
        )
        self._append_event(
            work_id,
            event_type="work.run.completed",
            source_event_id=f"work-run:{run_id}:result",
            payload={
                "runId": run_id,
                "passed": passed,
                "naturalStatus": summary,
            },
        )
        return self._response(work_id, run_id)

    async def stop(self, work_id: str, run_id: str) -> WorkRunResponse:
        workspace = self._creator.workspace(work_id)
        self._runs.get(workspace, run_id)
        await self._lab.stop_run(work_id, run_id)
        self._append_event(
            work_id,
            event_type="work.run.stopped",
            source_event_id=f"work-run:{run_id}:stopped",
            payload={
                "runId": run_id,
                "naturalStatus": "数字试运行已安全停止",
            },
        )
        return self._response(work_id, run_id)

    def _ensure_static_evidence(
        self,
        work_id: str,
        scene: DeviceLabSceneV1,
    ) -> None:
        scene_revision = scene.revision
        workspace = self._creator.workspace(work_id)
        if any(
            item.kind is EvidenceKind.STATIC_VALIDATION
            and item.status is EvidenceStatus.CURRENT
            and item.passed
            and item.source_id == scene_revision
            for item in workspace.evidence
        ):
            return
        request = CreatorCommandRequest(
            baseProjectVersion=workspace.project_version,
            idempotencyKey=(
                f"unified-static-v2-{scene_revision}-{workspace.project_version}"
            ),
            payload={
                "passed": True,
                "summary": (
                    "当前方案的功能场景、输入和结果映射已通过本地检查；这不代表真实接线已经确认。"
                    if scene.source.projectionPurpose == "WORK_FUNCTIONAL"
                    else "当前方案的场景、器件和连接静态检查已通过。"
                ),
                "sourceId": scene_revision,
                "bindings": {
                    "sceneRevision": scene_revision,
                    "projectionPurpose": scene.source.projectionPurpose,
                },
            },
        )
        repeated = self._creator.replay_command(
            work_id,
            CreatorCommand.RECORD_STATIC_VALIDATION,
            request,
        )
        if repeated is None:
            self._creator.validate_command_source(
                work_id,
                CreatorCommand.RECORD_STATIC_VALIDATION,
                request.payload,
            )
            self._creator.execute(
                work_id,
                CreatorCommand.RECORD_STATIC_VALIDATION,
                request,
            )

    def _record_simulation_evidence(
        self,
        work_id: str,
        run_id: str,
        *,
        idempotency_key: str,
        passed: bool,
        summary: str,
        scenario_ids: list[str],
        scene_revision: str,
        solution_revision_id: str,
        code_run_id: str | None,
        parameter_set_id: str | None,
        runtime_bindings_json: str,
        wokwi_bindings: dict[str, str],
    ) -> None:
        workspace = self._creator.workspace(work_id)
        existing = next(
            (
                item
                for item in workspace.evidence
                if item.kind is EvidenceKind.SIMULATION
                and item.source_id == run_id
                and item.status in {EvidenceStatus.CURRENT, EvidenceStatus.FAILED}
            ),
            None,
        )
        if existing is not None:
            if existing.passed != passed:
                raise WorkRunError(
                    "WORK_RUN_RESULT_IMMUTABLE",
                    "这次数字试运行已经形成结果，不能在原会话上改写。",
                    409,
                )
            return
        evidence_key = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        request = CreatorCommandRequest(
            baseProjectVersion=workspace.project_version,
            idempotencyKey=f"unified-simulation-{evidence_key}",
            payload={
                "passed": passed,
                "summary": summary,
                "sourceId": run_id,
                "bindings": {
                    "scenarioIds": ",".join(sorted(scenario_ids)),
                    "sceneRevision": scene_revision,
                    "solutionRevisionId": solution_revision_id,
                    "codeRunId": code_run_id or "",
                    "parameterSetId": parameter_set_id or "default",
                    "executionRevisionSet": runtime_bindings_json,
                    **wokwi_bindings,
                },
            },
        )
        repeated = self._creator.replay_command(
            work_id,
            CreatorCommand.RECORD_SIMULATION,
            request,
        )
        if repeated is None:
            self._creator.validate_command_source(
                work_id,
                CreatorCommand.RECORD_SIMULATION,
                request.payload,
            )
            self._creator.execute(
                work_id,
                CreatorCommand.RECORD_SIMULATION,
                request,
            )

    def _append_event(
        self,
        work_id: str,
        *,
        event_type: str,
        source_event_id: str,
        payload: dict[str, object],
    ) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type=event_type,
                source_event_id=source_event_id,
                payload=payload,
            )

    def _response(self, work_id: str, run_id: str) -> WorkRunResponse:
        workspace = self._creator.workspace(work_id)
        return WorkRunResponse(
            run=self._runs.get(workspace, run_id),
            snapshot=self._works.snapshot(work_id),
        )
