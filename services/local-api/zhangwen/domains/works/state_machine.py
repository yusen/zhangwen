"""Pure mapping from compatibility facts to one user-facing Work state."""

from __future__ import annotations

from dataclasses import dataclass

from zhangwen.creator.models import CreatorJobStatus, CreatorPhase, CreatorWorkspace
from zhangwen.domains.works.models import WorkJourneyMilestone, WorkState


@dataclass(frozen=True)
class WorkStateProjection:
    milestone: WorkJourneyMilestone
    state: WorkState
    natural_status: str
    progress_summary: str


_PHASE_PROJECTIONS: dict[CreatorPhase, WorkStateProjection] = {
    CreatorPhase.IDEA: WorkStateProjection(
        WorkJourneyMilestone.CLARIFY,
        WorkState.IDEA_CAPTURE,
        "正在理解你的想法",
        "正在想清楚作品要解决的问题",
    ),
    CreatorPhase.GOAL_REVIEW: WorkStateProjection(
        WorkJourneyMilestone.CLARIFY,
        WorkState.DISCOVERY_IN_PROGRESS,
        "正在整理作品方向",
        "作品方向正在变得清晰",
    ),
    CreatorPhase.SOLUTION_REVIEW: WorkStateProjection(
        WorkJourneyMilestone.CLARIFY,
        WorkState.PLAN_READY,
        "推荐方案已准备好",
        "可以检查并确认当前方案",
    ),
    CreatorPhase.DIGITAL_BUILDING: WorkStateProjection(
        WorkJourneyMilestone.TRY,
        WorkState.PROTOTYPE_PREPARING,
        "正在准备可运行的数字版本",
        "正在把方案做成可验证的数字作品",
    ),
    CreatorPhase.SIMULATING: WorkStateProjection(
        WorkJourneyMilestone.TRY,
        WorkState.PROTOTYPE_TESTING,
        "正在测试数字版本",
        "正在检查关键行为和异常情况",
    ),
    CreatorPhase.SIMULATION_PASSED: WorkStateProjection(
        WorkJourneyMilestone.MAKE,
        WorkState.MATERIALS_PREPARING,
        "数字版本已经通过，准备做成作品",
        "可以准备设备、材料和连接",
    ),
    CreatorPhase.DEVICE_CONNECTED: WorkStateProjection(
        WorkJourneyMilestone.MAKE,
        WorkState.DEPLOYMENT_READY,
        "设备已经连接，可以安全运行",
        "设备身份已确认，等待运行当前版本",
    ),
    CreatorPhase.DEPLOYED: WorkStateProjection(
        WorkJourneyMilestone.MAKE,
        WorkState.PHYSICAL_TESTING,
        "当前版本已经写入，等待观察实物行为",
        "写入和回读已完成，实物行为仍需验证",
    ),
    CreatorPhase.PHYSICAL_VALIDATING: WorkStateProjection(
        WorkJourneyMilestone.MAKE,
        WorkState.PHYSICAL_TESTING,
        "正在检查实物行为",
        "请根据真实观察完成验收场景",
    ),
    CreatorPhase.PHYSICAL_PASSED: WorkStateProjection(
        WorkJourneyMilestone.MAKE,
        WorkState.USER_ACCEPTANCE,
        "实物测试已通过，等待你的最终验收",
        "系统证据齐全，最终结论由你确认",
    ),
    CreatorPhase.ACCEPTED: WorkStateProjection(
        WorkJourneyMilestone.COMPLETE,
        WorkState.COMPLETED,
        "作品已经由你验收",
        "作品已完成，可以整理和分享",
    ),
    CreatorPhase.DELIVERED: WorkStateProjection(
        WorkJourneyMilestone.COMPLETE,
        WorkState.COMPLETED,
        "作品已经完成并可复现交付",
        "作品已完成，可以继续分享或复制",
    ),
}


class WorkStateMachine:
    @staticmethod
    def project(workspace: CreatorWorkspace) -> WorkStateProjection:
        base = _PHASE_PROJECTIONS[workspace.phase]
        if workspace.archived_at is not None:
            return WorkStateProjection(
                base.milestone,
                WorkState.ARCHIVED,
                "作品已归档",
                "可以恢复作品后继续创作",
            )
        failed = next(
            (
                job
                for job in workspace.jobs
                if job.status is CreatorJobStatus.FAILED
            ),
            None,
        )
        if failed is not None:
            return WorkStateProjection(
                base.milestone,
                WorkState.BLOCKED,
                failed.message or "当前步骤需要处理后才能继续",
                "处理当前问题后可以从同一作品继续",
            )
        return base
