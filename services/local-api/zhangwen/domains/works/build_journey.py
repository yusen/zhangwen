"""Pure projection of existing Creator/device/service facts into one build journey."""

from __future__ import annotations

from dataclasses import dataclass

from zhangwen.creator.models import (
    CreatorJobStatus,
    CreatorWorkspace,
    EvidenceKind,
    EvidenceStatus,
)
from zhangwen.domains.works.models import (
    WorkBuildJourney,
    WorkBuildRecoveryAction,
    WorkBuildStep,
    WorkDeviceSummary,
    WorkNextAction,
    WorkServiceSummary,
)


@dataclass(frozen=True)
class ServiceJourneyFact:
    summary: WorkServiceSummary
    status: str


@dataclass(frozen=True)
class BuildJourneyRequirements:
    """Canvas-derived needs for the current immutable work proposal.

    ``None`` for ``structure_required`` preserves the legacy solution-text
    projection.  This keeps old works readable while new Canvas-backed works
    decide their path from the unified WorkIntent.
    """

    hardware_required: bool = True
    structure_required: bool | None = None
    communication_required: bool = False
    digital_only: bool = False


def project_build_journey(
    workspace: CreatorWorkspace,
    *,
    devices: list[WorkDeviceSummary],
    services: list[ServiceJourneyFact],
    requirements: BuildJourneyRequirements | None = None,
) -> WorkBuildJourney:
    needs = requirements or BuildJourneyRequirements()
    current = _current_evidence(workspace)
    solution = workspace.current_solution
    solution_confirmed = solution is not None and solution.status == "CONFIRMED"
    simulation_ready = EvidenceKind.SIMULATION in current
    legacy_structure_required = bool(
        solution is not None
        and solution.structure.strip() not in {"", "不需要结构", "不适用", "无"}
    )
    structure_required = (
        legacy_structure_required
        if needs.structure_required is None
        else needs.structure_required
    )
    structure_ready = not structure_required or EvidenceKind.STRUCTURE_CHECK in current
    device_ready = EvidenceKind.DEVICE_CONNECTION in current
    deployed = EvidenceKind.DEPLOYMENT in current
    observed = EvidenceKind.PHYSICAL_BEHAVIOR in current
    accepted = EvidenceKind.USER_ACCEPTANCE in current
    hardware_required = needs.hardware_required and not needs.digital_only

    service_statuses = {item.status for item in services}
    service_attention = any(item.summary.attention_required for item in services)
    communication_running = bool(service_statuses) and service_statuses <= {"RUNNING"}
    communication_ready = not needs.communication_required or communication_running

    steps: list[WorkBuildStep] = [
        _step(
            "materials",
            "MATERIALS",
            "准备清单",
            "确认当前方案需要的设备、材料和安全注意。",
            "SKIPPED"
            if needs.digital_only
            else "COMPLETED"
            if solution_confirmed
            else "BLOCKED",
            (
                "这是一件纯数字作品，无需准备设备、材料或供电。"
                if needs.digital_only
                else
                "当前方案已经列出需要准备的设备和材料。"
                if solution_confirmed
                else "方案明确后，掌问会整理需要准备的内容。"
            ),
            required=not needs.digital_only,
        )
    ]
    if structure_required:
        structure_status = (
            "COMPLETED"
            if EvidenceKind.STRUCTURE_CHECK in current
            else "READY"
            if simulation_ready
            else "BLOCKED"
        )
        steps.append(
            _step(
                "structure",
                "STRUCTURE",
                "检查作品结构",
                "按当前方案检查装配、开孔和可制造性。",
                structure_status,
                (
                    "当前结构已经与采用的方案一起检查。"
                    if structure_status == "COMPLETED"
                    else "数字结果通过后即可检查当前结构。"
                    if structure_status == "READY"
                    else "先完成数字试运行，再准备结构。"
                ),
            )
        )
    else:
        steps.append(
            _step(
                "structure",
                "STRUCTURE",
                "作品结构",
                "当前作品不需要独立结构件。",
                "SKIPPED",
                "当前方案不需要额外结构，已自动跳过。",
                required=False,
            )
        )

    steps.append(
        _step(
            "device",
            "DEVICE",
            "连接设备",
            "确认设备身份、连接方式、供电和当前作品匹配。",
            "SKIPPED"
            if not hardware_required
            else "COMPLETED"
            if device_ready
            else "READY"
            if simulation_ready and structure_ready
            else "BLOCKED",
            (
                "这件作品不需要连接真实设备。"
                if not hardware_required
                else "设备身份、供电方式和当前作品已经匹配。"
                if device_ready
                else "可以选择设备，并在本机安全步骤中确认身份与供电。"
                if simulation_ready and structure_ready
                else "先完成数字结果和需要的结构检查。"
            ),
            required=hardware_required,
            attention=hardware_required
            and any(item.attention_required for item in devices),
        )
    )

    if services or needs.communication_required:
        communication_status = (
            "BLOCKED"
            if service_attention
            else "COMPLETED"
            if communication_running
            else "READY"
            if not needs.communication_required or device_ready and structure_ready
            else "BLOCKED"
        )
        steps.append(
            _step(
                "communication",
                "COMMUNICATION",
                "设备通信",
                "按作品需要在本机或受控网络中交换消息。",
                communication_status,
                _service_status_text(
                    services,
                    communication_status,
                    required=needs.communication_required,
                ),
                required=needs.communication_required,
                attention=service_attention,
            )
        )

    steps.extend(
        [
            _step(
                "deployment",
                "DEPLOYMENT",
                "运行到设备",
                "通过 USB 或 ESP-Claw 写入当前版本并完成回读。",
                "SKIPPED"
                if not hardware_required
                else "COMPLETED"
                if deployed
                else "READY"
                if device_ready and structure_ready and communication_ready
                else "BLOCKED",
                (
                    "纯数字作品无需写入真实设备。"
                    if not hardware_required
                    else
                    "当前版本已经写入并完成回读。"
                    if deployed
                    else "设备确认后，可以选择 USB 或 ESP-Claw 运行当前版本。"
                    if device_ready and structure_ready and communication_ready
                    else "先确认设备、结构和作品需要的通信。"
                ),
                required=hardware_required,
            ),
            _step(
                "observation",
                "OBSERVATION",
                "观察实物行为",
                "逐项观察真实作品；写入成功不会自动算作行为成功。",
                "SKIPPED"
                if not hardware_required
                else "COMPLETED"
                if observed
                else "WAITING_USER"
                if deployed
                else "BLOCKED",
                (
                    "纯数字作品无需声明实物行为。"
                    if not hardware_required
                    else
                    "真实行为已经逐项观察并记录。"
                    if observed
                    else "请运行作品并逐项确认你实际看到的结果。"
                    if deployed
                    else "写入和回读完成后才能观察实物行为。"
                ),
                required=hardware_required,
            ),
            _step(
                "acceptance",
                "ACCEPTANCE",
                "完成最终验收",
                "最终结论只能由实际观察作品的人确认。",
                "COMPLETED"
                if accepted
                else "WAITING_USER"
                if observed or needs.digital_only and simulation_ready
                else "BLOCKED",
                (
                    "作品已经由真实用户完成最终验收。"
                    if accepted
                    else "数字试做已经通过，请亲自检查画面与行为后确认。"
                    if needs.digital_only and simulation_ready
                    else "实物场景通过后，请由实际观察者给出最终结论。"
                    if observed
                    else "先完成实物行为观察，掌问不会代替你验收。"
                ),
            ),
        ]
    )

    recovery = _recovery_action(workspace, devices=devices, services=services)
    current_step_id = _activate_first_open_required_step(steps)
    if recovery is not None and current_step_id is not None:
        for index, item in enumerate(steps):
            if item.id != current_step_id:
                continue
            steps[index] = item.model_copy(
                update={"status": "BLOCKED", "attention_required": True}
            )
            break

    if accepted:
        status = "COMPLETED"
        natural_status = "作品已经由你验收，可以准备交付。"
        current_step_id = None
        recovery = None
    elif recovery is not None:
        status = "BLOCKED"
        natural_status = recovery.label
    elif observed:
        status = "WAITING_USER"
        natural_status = "实物行为已经记录，等待你完成最终验收。"
    elif deployed:
        status = "WAITING_USER"
        natural_status = "当前版本已写入并回读，等待观察真实行为。"
    elif needs.digital_only and simulation_ready:
        status = "WAITING_USER"
        natural_status = "数字作品已经试做通过，等待你亲自检查并确认。"
    elif not simulation_ready:
        status = "NOT_READY"
        natural_status = "先完成数字试运行，再连接真实设备。"
    else:
        status = "IN_PROGRESS"
        current_step = next(
            (item for item in steps if item.id == current_step_id), None
        )
        natural_status = (
            current_step.natural_status
            if current_step is not None
            else "正在按当前方案把作品做出来。"
        )

    return WorkBuildJourney(
        status=status,
        naturalStatus=natural_status,
        currentStepId=current_step_id,
        steps=steps,
        recoveryAction=recovery,
        requiresHumanAcceptance=True,
    )


def journey_next_action(
    workspace: CreatorWorkspace,
    *,
    journey: WorkBuildJourney,
    fallback: WorkNextAction,
) -> WorkNextAction:
    if journey.recovery_action is not None:
        return WorkNextAction(
            id=journey.recovery_action.id,
            label=journey.recovery_action.label,
            actionName=journey.recovery_action.action_name,
            enabled=True,
            blockedReason=None,
            riskLevel="LOW",
        )
    current_step = next(
        (item for item in journey.steps if item.id == journey.current_step_id),
        None,
    )
    if current_step is not None and current_step.status in {
        "ACTIVE",
        "READY",
        "WAITING_USER",
    }:
        action = {
            "STRUCTURE": ("review-structure", "检查并确认作品结构", "review_structure", "LOW"),
            "DEVICE": ("connect-device", "选择并连接真实设备", "connect_device", "HIGH"),
            "COMMUNICATION": ("prepare-communication", "准备作品需要的通信", "prepare_communication", "MEDIUM"),
            "DEPLOYMENT": ("run-on-device", "运行到设备", "run_on_device", "HIGH"),
            "OBSERVATION": ("review-physical-result", "记录我看到的真实结果", "review_physical_result", "HIGH"),
            "ACCEPTANCE": ("accept-work", "由我确认作品结果", "accept_work", "MEDIUM"),
        }.get(current_step.kind)
        if action is not None:
            return WorkNextAction(
                id=action[0],
                label=action[1],
                actionName=action[2],
                enabled=True,
                blockedReason=None,
                riskLevel=action[3],
            )
    return fallback


def _step(
    step_id: str,
    kind: str,
    title: str,
    description: str,
    status: str,
    natural_status: str,
    *,
    required: bool = True,
    attention: bool = False,
) -> WorkBuildStep:
    return WorkBuildStep(
        id=step_id,
        kind=kind,
        title=title,
        description=description,
        status=status,
        naturalStatus=natural_status,
        required=required,
        attentionRequired=attention,
    )


def _current_evidence(workspace: CreatorWorkspace) -> set[EvidenceKind]:
    return {
        item.kind
        for item in workspace.evidence
        if item.status is EvidenceStatus.CURRENT and item.passed
    }


def _activate_first_open_required_step(steps: list[WorkBuildStep]) -> str | None:
    for index, item in enumerate(steps):
        if not item.required or item.status in {"COMPLETED", "SKIPPED"}:
            continue
        if item.status == "READY":
            steps[index] = item.model_copy(update={"status": "ACTIVE"})
        return item.id
    return None


def _recovery_action(
    workspace: CreatorWorkspace,
    *,
    devices: list[WorkDeviceSummary],
    services: list[ServiceJourneyFact],
) -> WorkBuildRecoveryAction | None:
    if any(item.status is CreatorJobStatus.FAILED for item in workspace.jobs):
        return WorkBuildRecoveryAction(
            id="retry-current-step",
            label="重新准备当前步骤",
            actionName="retry_current_step",
        )
    if any(item.attention_required for item in devices):
        return WorkBuildRecoveryAction(
            id="check-device-connection",
            label="检查设备连接后继续",
            actionName="check_device_connection",
        )
    if any(item.summary.attention_required for item in services):
        return WorkBuildRecoveryAction(
            id="recover-device-communication",
            label="恢复设备通信后继续",
            actionName="recover_device_communication",
        )
    current_kinds = _current_evidence(workspace)
    if any(
        item.status is EvidenceStatus.FAILED and item.kind not in current_kinds
        for item in workspace.evidence
    ):
        return WorkBuildRecoveryAction(
            id="review-current-result",
            label="重新检查当前结果",
            actionName="review_current_result",
        )
    return None


def _service_status_text(
    services: list[ServiceJourneyFact], status: str, *, required: bool
) -> str:
    if status == "BLOCKED":
        return next(
            (
                item.summary.natural_status
                for item in services
                if item.summary.attention_required
            ),
            "设备通信需要处理后才能继续。",
        )
    if status == "COMPLETED":
        return "作品需要的设备通信正在运行。"
    if not services and required:
        return "当前作品需要通信；请先选择仅本机、家庭网络或已有服务。"
    if status == "BLOCKED" and required:
        return "先确认设备和结构，再准备作品通信。"
    return "设备通信已准备，可按作品需要启动。"
