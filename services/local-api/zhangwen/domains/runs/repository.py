"""Read-only Work Run projection over existing Device Lab and Creator facts."""

from __future__ import annotations

from pathlib import Path

from zhangwen.creator.models import (
    CreatorWorkspace,
    EvidenceKind,
    EvidenceStatus,
)
from zhangwen.device_lab.boards import board_profile, scene_profile
from zhangwen.device_lab.models import (
    DeviceLabChannel,
    DeviceLabEngine,
    DeviceLabRun,
    DeviceLabRunStatus,
)
from zhangwen.device_lab.repository import DeviceLabRepository
from zhangwen.domains.works.models import (
    WorkDigitalRun,
    WorkRunChannel,
    WorkRunLog,
    WorkRunRecoveryAction,
    WorkRunRevisionBindings,
    WorkRunScenario,
    WorkRunScenarioStatus,
    WorkRunStatus,
    WorkWokwiRunSummary,
)
from zhangwen.projects.repository import ProjectRepository


class WorkRunRepository:
    """Projects runs without owning another run store or executor."""

    def __init__(self, data_dir: Path) -> None:
        self._lab = DeviceLabRepository(ProjectRepository(data_dir).db_path)

    def list_runs(
        self,
        workspace: CreatorWorkspace,
        *,
        limit: int = 20,
    ) -> list[WorkDigitalRun]:
        return [
            self.project(workspace, run)
            for run in self._lab.list_runs(workspace.work_id, limit=limit)
        ]

    def latest(self, workspace: CreatorWorkspace) -> WorkDigitalRun | None:
        runs = self._lab.list_runs(workspace.work_id, limit=1)
        return self.project(workspace, runs[0]) if runs else None

    def get(self, workspace: CreatorWorkspace, run_id: str) -> WorkDigitalRun:
        return self.project(
            workspace,
            self._lab.get_run(workspace.work_id, run_id),
        )

    def project(
        self,
        workspace: CreatorWorkspace,
        run: DeviceLabRun,
    ) -> WorkDigitalRun:
        scene = run.scene
        profile = (
            run.wokwiBinding.profile
            if run.wokwiBinding is not None and run.wokwiBinding.profile is not None
            else scene_profile(scene)
            if scene is not None
            else board_profile(run.boardId)
        )
        input_ids = {
            channel_id
            for test_case in (scene.testCases if scene is not None else [])
            for channel_id in test_case.inputChannelIds
        }
        sensors = [
            channel
            for channel in profile.channels
            if channel.kind == "sensor-input"
            and (
                run.engine is DeviceLabEngine.WOKWI_CLOUD
                or channel.id in input_ids
                or (not input_ids and channel.source == "project-scene")
            )
        ]
        component_ids = {
            channel.componentId
            for channel in sensors
            if channel.componentId is not None
        }
        actuators = [
            channel
            for channel in profile.channels
            if channel.kind == "actuator"
            and (
                run.engine is DeviceLabEngine.WOKWI_CLOUD
                or channel.source == "project-scene"
                or channel.componentId in component_ids
            )
        ]
        advanced = [
            channel
            for channel in profile.channels
            if channel.kind == "parameter"
            and (
                channel.source == "project-scene"
                or channel.id == "fault-mode"
                or (channel.id == "sample-interval-ms" and bool(sensors))
                or channel.componentId in component_ids
            )
        ]
        scenario_results = {
            item.scenarioId: item.passed for item in run.scenarioResults
        }
        evidence = next(
            (
                item
                for item in workspace.evidence
                if item.kind is EvidenceKind.SIMULATION
                and item.source_id == run.id
                and item.status
                in {EvidenceStatus.CURRENT, EvidenceStatus.FAILED, EvidenceStatus.STALE}
            ),
            None,
        )
        status = _status(workspace, run, evidence)
        recovery = _recovery(status)
        revision_bindings = run.revisionBindings or _legacy_bindings(workspace, run)
        logs = self._lab.list_events(workspace.work_id, run.id, 0)[-100:]
        solution = workspace.current_solution
        behavior = solution.logic if solution is not None else workspace.initial_idea
        return WorkDigitalRun(
            id=run.id,
            workId=workspace.work_id,
            status=status,
            naturalStatus=_natural_status(status, run.resultSummary, run.engine),
            behavior=behavior,
            resultSummary=run.resultSummary,
            recoveryAction=recovery,
            scenarios=[
                WorkRunScenario(
                    id=item.id,
                    title=item.title,
                    expectedBehavior=item.simulation_expected,
                    required=item.required,
                    status=(
                        WorkRunScenarioStatus.PASSED
                        if scenario_results.get(item.id) is True
                        else WorkRunScenarioStatus.FAILED
                        if scenario_results.get(item.id) is False
                        else WorkRunScenarioStatus.PENDING
                    ),
                )
                for item in workspace.acceptance_scenarios
            ],
            inputs=[_channel(item, run, "INPUT") for item in sensors],
            outputs=[_channel(item, run, "OUTPUT", writable=False) for item in actuators],
            advancedControls=[
                _channel(
                    item,
                    run,
                    "FAULT" if item.id == "fault-mode" else "PARAMETER",
                )
                for item in advanced
            ],
            revisionBindings=revision_bindings,
            executionRevisionSet=run.executionRevisionSet,
            engine=run.engine.value,
            wokwi=(
                WorkWokwiRunSummary(
                    diagramSha256=run.wokwiBinding.diagramSha256,
                    firmwareSha256=run.wokwiBinding.firmwareSha256,
                    firmwareBaseRevision=run.wokwiBinding.firmwareBaseRevision,
                    diagramArtifactVersionId=run.wokwiBinding.diagramArtifactVersionId,
                    firmwareArtifactVersionId=run.wokwiBinding.firmwareArtifactVersionId,
                    runtimePackageRevisionId=run.wokwiBinding.runtimePackageRevisionId,
                    devicePackageRevisionId=run.wokwiBinding.devicePackageRevisionId,
                    compatibilitySummary=run.wokwiBinding.compatibilitySummary,
                )
                if run.wokwiBinding is not None
                else None
            ),
            logs=[
                WorkRunLog(
                    revision=item.revision,
                    type=item.type,
                    message=item.message,
                    channelId=item.channelId,
                    value=item.value,
                    createdAt=item.createdAt,
                )
                for item in logs
            ],
            revision=run.revision,
            startedAt=run.startedAt,
            updatedAt=run.updatedAt,
        )


def _status(workspace: CreatorWorkspace, run: DeviceLabRun, evidence: object) -> WorkRunStatus:
    current_solution_id = (
        workspace.current_solution.id if workspace.current_solution is not None else None
    )
    pinned_solution_id = (
        run.revisionBindings.solution_revision_id
        if run.revisionBindings is not None
        else run.scene.binding.solutionRevisionId
        if run.scene is not None and run.scene.binding is not None
        else None
    )
    if current_solution_id is None or pinned_solution_id != current_solution_id:
        return WorkRunStatus.STALE
    if evidence is not None and getattr(evidence, "status", None) is EvidenceStatus.STALE:
        return WorkRunStatus.STALE
    if run.status is DeviceLabRunStatus.RUNNING:
        return WorkRunStatus.RUNNING
    if run.status is DeviceLabRunStatus.ERROR:
        return WorkRunStatus.FAILED
    if (
        run.resultPassed is True
        and evidence is not None
        and getattr(evidence, "status", None) is EvidenceStatus.CURRENT
        and getattr(evidence, "passed", False) is True
    ):
        return WorkRunStatus.PASSED
    if (
        run.resultPassed is False
        and evidence is not None
        and getattr(evidence, "status", None) is EvidenceStatus.FAILED
    ):
        return WorkRunStatus.FAILED
    return WorkRunStatus.READY


def _natural_status(
    status: WorkRunStatus,
    summary: str | None,
    engine: DeviceLabEngine,
) -> str:
    if engine is DeviceLabEngine.WOKWI_CLOUD:
        return "这是一条只读历史联网仿真记录；旧 Wokwi Cloud 已退役，请使用掌问自研仿真重新验证。"
    if summary:
        return summary
    return {
        WorkRunStatus.READY: "数字试运行已经安全停止，可以检查场景结果。",
        WorkRunStatus.RUNNING: "数字试运行正在本机运行，可以改变作品输入并观察结果。",
        WorkRunStatus.PASSED: "当前方案的数字行为已经通过。",
        WorkRunStatus.FAILED: "这次数字试运行没有达到预期。",
        WorkRunStatus.STALE: "方案已经变化，需要按新方案重新试运行。",
    }[status]


def _recovery(status: WorkRunStatus) -> WorkRunRecoveryAction | None:
    if status not in {WorkRunStatus.FAILED, WorkRunStatus.STALE}:
        return None
    return WorkRunRecoveryAction(
        id="retry-digital-run",
        label="按当前方案重新试运行" if status is WorkRunStatus.STALE else "调整后重新试运行",
        actionName="retry_digital_run",
    )


def _channel(
    channel: DeviceLabChannel,
    run: DeviceLabRun,
    kind: str,
    *,
    writable: bool | None = None,
) -> WorkRunChannel:
    return WorkRunChannel(
        id=channel.id,
        label=channel.label,
        kind=kind,
        valueType=channel.valueType,
        value=run.channelValues.get(channel.id, channel.defaultValue),
        unit=channel.unit,
        minimum=channel.minimum,
        maximum=channel.maximum,
        step=channel.step,
        writable=channel.writable if writable is None else writable,
    )


def _legacy_bindings(
    workspace: CreatorWorkspace,
    run: DeviceLabRun,
) -> WorkRunRevisionBindings:
    scene = run.scene
    solution_id = (
        scene.binding.solutionRevisionId
        if scene is not None and scene.binding is not None
        else workspace.current_solution.id
        if workspace.current_solution is not None
        else "legacy-unknown"
    )
    return WorkRunRevisionBindings(
        solutionRevisionId=solution_id,
        codeRunId=(scene.binding.codeRunId if scene is not None and scene.binding else None),
        parameterSetId=run.parameterSetId,
        sceneRevision=scene.revision if scene is not None else "legacy-unknown",
        structureRevisionId=None,
    )
