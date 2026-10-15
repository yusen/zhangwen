"""Read adapter from current project/Creator facts to the unified Work domain."""

from __future__ import annotations

from pathlib import Path

from zhangwen.creator.models import (
    CreatorCommand,
    CreatorJobKind,
    CreatorJobStatus,
    CreatorPhase,
    CreatorWorkspace,
    EvidenceStatus,
    VerificationLevel,
)
from zhangwen.creator.repository import CreatorRepository
from zhangwen.domains.classroom.models import ProjectProcessState, WorkLearningProjection
from zhangwen.domains.classroom.repository import ClassroomRepository
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.inventory.repository import DevicePlatformRepository
from zhangwen.domains.mqtt_service.models import MqttMode, MqttServiceStatus
from zhangwen.domains.mqtt_service.repository import MqttServiceRepository
from zhangwen.domains.runs.repository import WorkRunRepository
from zhangwen.domains.works.build_journey import (
    BuildJourneyRequirements,
    ServiceJourneyFact,
    journey_next_action,
    project_build_journey,
)
from zhangwen.domains.works.canvas import WorkCanvasService
from zhangwen.domains.works.delivery import WorkDeliveryService
from zhangwen.domains.works.models import (
    WorkDeviceSummary,
    WorkAcceptanceScenario,
    WorkEvidenceSummary,
    WorkIdentity,
    WorkListResponse,
    WorkNextAction,
    WorkPlanSummary,
    WorkPreviewSummary,
    WorkSnapshot,
    WorkServiceSummary,
    WorkSummary,
    WorkTaskKind,
    WorkTaskStatus,
    WorkTaskSummary,
    WorkTrustStatus,
)
from zhangwen.domains.works.state_machine import WorkStateMachine
from zhangwen.projects.repository import ProjectRepository


_ACTION_NAMES: dict[CreatorCommand, str] = {
    CreatorCommand.SAVE_GOAL: "continue_creation",
    CreatorCommand.CONFIRM_GOAL: "confirm_direction",
    CreatorCommand.SAVE_SOLUTION: "revise_plan",
    CreatorCommand.CONFIRM_SOLUTION: "start_digital_run",
    CreatorCommand.GENERATE_PROJECT_BOOK: "view_plan",
    CreatorCommand.RECORD_STATIC_VALIDATION: "start_digital_run",
    CreatorCommand.RECORD_SIMULATION: "review_digital_result",
    CreatorCommand.RECORD_STRUCTURE_CHECK: "review_structure",
    CreatorCommand.RECORD_DEVICE_CONNECTION: "connect_device",
    CreatorCommand.RECORD_DEPLOYMENT: "run_on_device",
    CreatorCommand.RECORD_PHYSICAL_BEHAVIOR: "review_physical_result",
    CreatorCommand.ACCEPT_WORK: "accept_work",
    CreatorCommand.RECORD_REPRODUCTION: "verify_delivery",
    CreatorCommand.ARCHIVE_WORK: "archive_work",
}

_JOB_LABELS: dict[CreatorJobKind, str] = {
    CreatorJobKind.CODE_PREPARATION: "准备作品逻辑",
    CreatorJobKind.DIGITAL_PROTOTYPE: "准备数字版本",
    CreatorJobKind.STRUCTURE_DRAFT: "准备结构草案",
}

_JOB_STATUSES: dict[CreatorJobStatus, WorkTaskStatus] = {
    CreatorJobStatus.QUEUED: WorkTaskStatus.QUEUED,
    CreatorJobStatus.RUNNING: WorkTaskStatus.RUNNING,
    CreatorJobStatus.WAITING_CONFIRMATION: WorkTaskStatus.WAITING,
    CreatorJobStatus.SUCCEEDED: WorkTaskStatus.SUCCEEDED,
    CreatorJobStatus.FAILED: WorkTaskStatus.FAILED,
    CreatorJobStatus.CANCELED: WorkTaskStatus.CANCELED,
}

_LEGACY_ROLE_NAMES: tuple[str, ...] = (
    "问题引导师",
    "智能工程师",
    "结构设计师",
    "三师",
    "专家",
)


class WorkRepository:
    """Compatibility repository; it owns no second project fact store."""

    def __init__(self, data_dir: Path) -> None:
        self._creator = CreatorRepository(data_dir)
        self._events = RealtimeEventStore(ProjectRepository(data_dir).db_path)
        self._devices = DevicePlatformRepository(data_dir)
        self._mqtt = MqttServiceRepository(data_dir)
        self._runs = WorkRunRepository(data_dir)
        self._delivery = WorkDeliveryService(data_dir)
        self._canvas = WorkCanvasService(data_dir)
        self._classroom = ClassroomRepository(data_dir)

    def list_works(
        self, *, include_archived: bool = False
    ) -> tuple[list[WorkSummary], str | None]:
        legacy, active = self._creator.list_works(include_archived=include_archived)
        return [self.get(item.id) for item in legacy], active

    def get(self, work_id: str) -> WorkSummary:
        snapshot = self.snapshot(work_id)
        return WorkSummary(
            work=snapshot.work,
            milestone=snapshot.milestone,
            state=snapshot.state,
            naturalStatus=snapshot.natural_status,
            nextAction=snapshot.next_action,
            revision=snapshot.revision,
        )

    def snapshot(self, work_id: str) -> WorkSnapshot:
        return self._project(self._creator.workspace(work_id))

    def response(self, *, include_archived: bool = False) -> WorkListResponse:
        works, active = self.list_works(include_archived=include_archived)
        return WorkListResponse(works=works, activeWorkId=active)

    def _project(self, workspace: CreatorWorkspace) -> WorkSnapshot:
        state = WorkStateMachine.project(workspace)
        learning = self._classroom.optional_work_learning_projection(workspace.work_id)
        identity = WorkIdentity(
            id=workspace.work_id,
            name=workspace.name,
            initialIdea=workspace.initial_idea,
            archivedAt=workspace.archived_at,
            updatedAt=workspace.updated_at,
        )
        plan = _plan(
            workspace,
            source_proposal_id=(
                self._canvas.solution_source_proposal(
                    workspace.work_id,
                    workspace.current_solution.id,
                )
                if workspace.current_solution is not None
                else None
            ),
        )
        devices = [
            WorkDeviceSummary(
                id=device_id,
                name=name,
                naturalStatus=natural_status,
                attentionRequired=attention_required,
            )
            for device_id, name, natural_status, attention_required in (
                self._devices.list_existing_work_summaries(workspace.work_id)
            )
        ]
        service_facts = [
            ServiceJourneyFact(
                summary=WorkServiceSummary(
                    id=instance.id,
                    name=_service_name(instance.mode),
                    naturalStatus=instance.natural_status,
                    attentionRequired=instance.status
                    is MqttServiceStatus.FAILED_NEEDS_ATTENTION,
                ),
                status=instance.status.value,
            )
            for instance in self._mqtt.list_instances()
            if instance.work_id == workspace.work_id
        ]
        canvas, canvas_layout, canvas_generation = self._canvas.current(workspace)
        requirements = _build_requirements(canvas, generated=canvas_generation is not None)
        journey = project_build_journey(
            workspace,
            devices=devices,
            services=service_facts,
            requirements=requirements,
        )
        next_action = journey_next_action(
            workspace,
            journey=journey,
            fallback=_next_action(workspace),
        )
        natural_status = state.natural_status
        progress_summary = state.progress_summary
        if learning is not None:
            natural_status, progress_summary, next_action = _learning_presentation(
                learning
            )
        return WorkSnapshot(
            schemaVersion=2 if learning is not None else 1,
            work=identity,
            milestone=state.milestone,
            state=state.state,
            naturalStatus=natural_status,
            progressSummary=progress_summary,
            nextAction=next_action,
            currentPlan=plan,
            currentPreview=_preview(workspace, plan),
            currentTasks=[
                WorkTaskSummary(
                    id=job.id,
                    kind=WorkTaskKind(job.kind.value),
                    label=_JOB_LABELS[job.kind],
                    status=_JOB_STATUSES[job.status],
                    message=_naturalize_legacy_message(job.message),
                )
                for job in workspace.jobs
            ],
            currentDevices=devices,
            currentServices=[item.summary for item in service_facts],
            currentEvidenceSummary=_evidence(workspace),
            currentDigitalRun=self._runs.latest(workspace),
            currentBuildJourney=journey,
            currentAcceptanceScenarios=[
                WorkAcceptanceScenario(
                    id=item.id,
                    title=item.title,
                    expectedBehavior=item.physical_expected,
                    required=item.required,
                )
                for item in workspace.acceptance_scenarios
            ],
            currentDelivery=self._delivery.overview(
                workspace.work_id,
                workspace=workspace,
            ),
            currentCanvas=canvas,
            currentCanvasLayout=canvas_layout,
            currentCanvasGeneration=canvas_generation,
            learningContext=(learning.learning_context if learning is not None else None),
            projectProcess=(learning.project_process if learning is not None else None),
            availableAdvancedTools=_advanced_tools(workspace),
            revision=max(
                workspace.project_version,
                self._events.latest_work_seq(workspace.work_id),
                learning.project_process.revision if learning is not None else 0,
            ),
        )


def _build_requirements(
    canvas: object, *, generated: bool
) -> BuildJourneyRequirements:
    """Derive one physical/digital path from the current Canvas only."""

    from zhangwen.domains.works.models import CanvasSpec

    if not generated or not isinstance(canvas, CanvasSpec):
        return BuildJourneyRequirements()
    intent = canvas.work_intent
    digital_only = bool(
        canvas.scene is not None
        and canvas.scene.subject.kind == "SOFTWARE"
        and not intent.physical_actions
        and not intent.structure_needs
        and not intent.service_needs
    )
    return BuildJourneyRequirements(
        hardware_required=not digital_only,
        structure_required=bool(intent.structure_needs),
        communication_required=bool(intent.service_needs),
        digital_only=digital_only,
    )


def _learning_presentation(
    projection: WorkLearningProjection,
) -> tuple[str, str, WorkNextAction]:
    state = projection.project_process.state
    presentations: dict[ProjectProcessState, tuple[str, str, str, str, bool]] = {
        ProjectProcessState.PROPOSAL_DRAFT: (
            "正在和问题引导师完善项目方案书",
            "先把要解决的问题、成功标准、硬件计划和验证方法说清楚。",
            "continue_project_proposal",
            "继续完善项目方案书",
            True,
        ),
        ProjectProcessState.PROPOSAL_READY_FOR_REVIEW: (
            "项目方案书已可提交检查",
            "方案字段已经齐全，提交后将固定本次修订。",
            "submit_project_proposal",
            "提交方案书供检查",
            True,
        ),
        ProjectProcessState.PROPOSAL_IN_REVIEW: (
            "项目方案书正在等待教师检查",
            "当前方案修订已提交，教师反馈不会覆盖你的原始内容。",
            "wait_for_proposal_review",
            "等待方案书检查",
            False,
        ),
        ProjectProcessState.PROPOSAL_CHANGES_REQUESTED: (
            "项目方案书需要修改",
            "根据教师指出的检查点创建一个新修订。",
            "revise_project_proposal",
            "按反馈修改方案书",
            True,
        ),
        ProjectProcessState.PROPOSAL_APPROVED: (
            "项目方案书已通过，可以设计仿真",
            "下一步把同一方案版本落实为电路、代码和必测场景。",
            "start_simulation_design",
            "开始设计仿真",
            True,
        ),
        ProjectProcessState.SIMULATION_DRAFT: (
            "正在搭建仿真项目",
            "补齐电路、MicroPython 代码和验证场景。",
            "continue_simulation_design",
            "继续搭建仿真",
            True,
        ),
        ProjectProcessState.SIMULATION_READY: (
            "仿真项目已可运行",
            "运行固定版本的电路、代码和场景集合。",
            "run_simulation_scenarios",
            "运行验证场景",
            True,
        ),
        ProjectProcessState.SIMULATION_RUNNING: (
            "正在运行验证场景",
            "保留当前运行版本，等待场景完成或主动停止。",
            "view_simulation_run",
            "查看运行过程",
            True,
        ),
        ProjectProcessState.SIMULATION_CHANGES_REQUIRED: (
            "仿真发现需要修改的问题",
            "查看失败场景并创建新的电路或代码修订。",
            "fix_simulation_failures",
            "修改并重新验证",
            True,
        ),
        ProjectProcessState.SIMULATION_VALIDATED: (
            "行为仿真已经通过",
            "仿真证据只证明数字行为；现在选择是否制作结构件。",
            "review_simulation_evidence",
            "查看验证结果",
            True,
        ),
        ProjectProcessState.BUILD_ROUTE_REQUIRED: (
            "需要选择制作路径",
            "选择制作结构件或不做结构件，两条路径都会进入实物验证。",
            "choose_build_route",
            "选择制作路径",
            True,
        ),
        ProjectProcessState.STRUCTURE_DESIGN: (
            "正在设计结构件",
            "结构设计必须绑定当前硬件和方案修订。",
            "continue_structure_design",
            "继续结构设计",
            True,
        ),
        ProjectProcessState.ASSEMBLY_IN_PROGRESS: (
            "正在完成装配检查",
            "记录接线、固定、绝缘和供电检查。",
            "continue_assembly",
            "继续装配检查",
            True,
        ),
        ProjectProcessState.DEVICE_DEPLOYMENT_READY: (
            "已准备好上传到实体硬件",
            "选择匹配设备后执行带备份和回读的文件级上传。",
            "select_deployment_device",
            "选择实体设备",
            True,
        ),
        ProjectProcessState.DEVICE_DEPLOYING: (
            "正在向实体硬件上传代码",
            "保持设备连接，上传完成后还需要人工观察。",
            "view_device_deployment",
            "查看上传过程",
            True,
        ),
        ProjectProcessState.PHYSICAL_OBSERVATION_REQUIRED: (
            "需要记录实体作品的实际表现",
            "真机观察与仿真通过是两类独立证据。",
            "record_physical_observation",
            "记录实物观察",
            True,
        ),
        ProjectProcessState.SUBMISSION_DRAFT: (
            "正在整理项目提交",
            "汇总方案、验证、制作决定、实物观察和反思。",
            "continue_project_submission",
            "继续整理提交",
            True,
        ),
        ProjectProcessState.SUBMISSION_IN_REVIEW: (
            "项目提交正在等待教师评审",
            "评审固定到本次提交修订，后续修改不会覆盖它。",
            "wait_for_submission_review",
            "等待教师评审",
            False,
        ),
        ProjectProcessState.SUBMISSION_CHANGES_REQUESTED: (
            "项目提交需要补充",
            "根据反馈补充过程证据或反思，并创建新提交修订。",
            "revise_project_submission",
            "按反馈补充提交",
            True,
        ),
        ProjectProcessState.COMPLETED: (
            "项目过程已经完成",
            "方案、验证、制作和教师评审均保留为可追溯版本。",
            "view_project_record",
            "查看完整项目记录",
            True,
        ),
    }
    natural_status, progress, action_name, label, enabled = presentations[state]
    return (
        natural_status,
        progress,
        WorkNextAction(
            id=action_name.replace("_", "-"),
            label=label,
            actionName=action_name,
            enabled=enabled,
            blockedReason=None if enabled else natural_status,
            riskLevel="LOW",
        ),
    )


def _service_name(mode: MqttMode) -> str:
    return {
        MqttMode.SIMULATED: "设备通信（本机模拟）",
        MqttMode.LOOPBACK: "设备通信（仅本机）",
        MqttMode.LAN: "设备通信（家庭网络）",
        MqttMode.EXTERNAL: "设备通信（已有服务）",
    }[mode]


def _next_action(workspace: CreatorWorkspace) -> WorkNextAction:
    command = workspace.next_action.command
    if command is None:
        action_name = (
            "view_delivery"
            if workspace.phase in {CreatorPhase.ACCEPTED, CreatorPhase.DELIVERED}
            else "continue_creation"
        )
    else:
        action_name = _ACTION_NAMES[command]
    return WorkNextAction(
        id=action_name.replace("_", "-"),
        label=_naturalize_legacy_message(workspace.next_action.label),
        actionName=action_name,
        enabled=workspace.next_action.enabled,
        blockedReason=_naturalize_legacy_message(workspace.next_action.blocked_reason),
        riskLevel=workspace.next_action.risk_level,
    )


def _naturalize_legacy_message(message: str | None) -> str | None:
    """Keep internal legacy role names out of the unified user-facing contract."""
    if message is None:
        return None
    natural = message
    for role_name in _LEGACY_ROLE_NAMES:
        natural = natural.replace(role_name, "掌问")
    return natural


def _plan(
    workspace: CreatorWorkspace,
    *,
    source_proposal_id: str | None,
) -> WorkPlanSummary | None:
    solution = workspace.current_solution
    if solution is None:
        return None
    structure = solution.structure.strip()
    return WorkPlanSummary(
        solutionRevisionId=solution.id,
        sourceProposalId=source_proposal_id,
        title="当前推荐方案",
        summary=solution.summary,
        logic=solution.logic,
        hardware=solution.hardware,
        software=solution.software,
        structure=(
            None if structure in {"", "不需要结构", "不适用"} else structure
        ),
        simulation=solution.simulation,
        safety=solution.safety,
    )


def _preview(
    workspace: CreatorWorkspace,
    plan: WorkPlanSummary | None,
) -> WorkPreviewSummary | None:
    if plan is None:
        return None
    if workspace.phase in {
        CreatorPhase.IDEA,
        CreatorPhase.GOAL_REVIEW,
        CreatorPhase.SOLUTION_REVIEW,
    }:
        kind = "PLAN"
        title = "当前方案预览"
    elif workspace.phase in {
        CreatorPhase.DIGITAL_BUILDING,
        CreatorPhase.SIMULATING,
        CreatorPhase.SIMULATION_PASSED,
    }:
        kind = "DIGITAL"
        title = "数字版本预览"
    elif workspace.phase in {CreatorPhase.ACCEPTED, CreatorPhase.DELIVERED}:
        kind = "DELIVERY"
        title = "完成作品预览"
    else:
        kind = "PHYSICAL"
        title = "实物作品预览"
    return WorkPreviewSummary(kind=kind, title=title, summary=plan.summary)


def _evidence(workspace: CreatorWorkspace) -> WorkEvidenceSummary:
    attention = any(
        item.status in {EvidenceStatus.STALE, EvidenceStatus.FAILED}
        for item in workspace.evidence
    )
    if attention:
        return WorkEvidenceSummary(
            status=WorkTrustStatus.NEEDS_ATTENTION,
            label="部分检查需要重新完成",
            attentionRequired=True,
        )
    if workspace.verification_level is VerificationLevel.USER_ACCEPTED:
        return WorkEvidenceSummary(
            status=WorkTrustStatus.ACCEPTED,
            label="作品已经由你验收",
            attentionRequired=False,
        )
    if any(job.status is CreatorJobStatus.RUNNING for job in workspace.jobs):
        return WorkEvidenceSummary(
            status=WorkTrustStatus.CHECKING,
            label="正在进行本地检查",
            attentionRequired=False,
        )
    if workspace.verification_level >= VerificationLevel.SIMULATION_PASSED:
        label = (
            "实物行为已经验证"
            if workspace.verification_level >= VerificationLevel.PHYSICAL_PASSED
            else "数字行为已经验证"
        )
        return WorkEvidenceSummary(
            status=WorkTrustStatus.VERIFIED,
            label=label,
            attentionRequired=False,
        )
    return WorkEvidenceSummary(
        status=WorkTrustStatus.NOT_VERIFIED,
        label="还没有完成关键行为验证",
        attentionRequired=False,
    )


def _advanced_tools(workspace: CreatorWorkspace) -> list[str]:
    tools = ["conversation"]
    solution = workspace.current_solution
    if solution is not None:
        tools.extend(["plan", "code", "simulation"])
        if solution.structure.strip() not in {"", "不需要结构", "不适用"}:
            tools.append("structure")
    if workspace.phase not in {
        CreatorPhase.IDEA,
        CreatorPhase.GOAL_REVIEW,
        CreatorPhase.SOLUTION_REVIEW,
        CreatorPhase.DIGITAL_BUILDING,
        CreatorPhase.SIMULATING,
    }:
        tools.append("devices")
    if workspace.phase in {CreatorPhase.ACCEPTED, CreatorPhase.DELIVERED}:
        tools.append("delivery")
    return tools
