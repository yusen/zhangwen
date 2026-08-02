"""Deterministic Orchestrator state machine with Mock Agent execution."""

from __future__ import annotations

from datetime import UTC, datetime

from zhangwen.orchestrator.models import ExecutionPlan, TaskNode, TaskStatus
from zhangwen.orchestrator.repository import (
    OrchestratorRepository,
    add_log,
    touch_plan,
)
from zhangwen.proposals.models import ProposalStatus, ProposalVersion


class OrchestratorService:
    def __init__(self, repository: OrchestratorRepository) -> None:
        self._repository = repository

    def create_plan(
        self,
        project_id: str,
        proposal: ProposalVersion,
    ) -> ExecutionPlan:
        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError("只有已确认立项书可以创建执行计划。")
        return self._repository.create_plan(
            project_id=project_id,
            proposal_id=proposal.id,
            node_specs=_default_node_specs(),
        )

    def start_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        if plan.status == TaskStatus.PAUSED:
            raise ValueError("执行计划已暂停，请先恢复。")
        if plan.startedAt is None:
            plan.startedAt = _now()
        plan.status = TaskStatus.RUNNING
        touch_plan(plan)
        self._advance(plan)
        return self._repository.save_plan(plan)

    def pause_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        if plan.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED}:
            raise ValueError("当前执行计划不能暂停。")
        plan.status = TaskStatus.PAUSED
        for node in plan.nodes:
            if node.status in {TaskStatus.QUEUED, TaskStatus.AWAITING_APPROVAL}:
                add_log(node, "INFO", "执行计划已暂停。")
        touch_plan(plan)
        return self._repository.save_plan(plan)

    def resume_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        if plan.status != TaskStatus.PAUSED:
            raise ValueError("只有暂停中的执行计划可以恢复。")
        plan.status = TaskStatus.RUNNING
        touch_plan(plan)
        self._advance(plan)
        return self._repository.save_plan(plan)

    def approve_node(
        self,
        plan: ExecutionPlan,
        node_id: str,
        approved: bool,
        comment: str | None,
    ) -> ExecutionPlan:
        node = _find_node(plan, node_id)
        if not node.requiresApproval:
            raise ValueError("该任务不需要用户确认。")
        if node.status != TaskStatus.AWAITING_APPROVAL:
            raise ValueError("该任务当前不在等待确认状态。")
        if not approved:
            node.status = TaskStatus.FAILED
            node.error = comment or "用户未确认。"
            node.completedAt = _now()
            add_log(node, "WARNING", f"用户退回确认：{node.error}")
            plan.status = TaskStatus.FAILED
            touch_plan(plan)
            return self._repository.save_plan(plan)

        node.status = TaskStatus.COMPLETED
        node.error = None
        node.completedAt = _now()
        add_log(node, "INFO", f"用户确认通过。{comment or ''}".strip())
        touch_plan(plan)
        self._advance(plan)
        return self._repository.save_plan(plan)

    def retry_node(self, plan: ExecutionPlan, node_id: str | None) -> ExecutionPlan:
        node = _find_node(plan, node_id) if node_id else _first_failed_node(plan)
        if node.attempts >= node.maxAttempts:
            raise ValueError("任务已达到最大重试次数。")
        if node.requiresApproval:
            node.status = TaskStatus.AWAITING_APPROVAL
        else:
            node.status = TaskStatus.QUEUED
        node.error = None
        node.completedAt = None
        node.attempts += 1
        add_log(node, "INFO", "任务已进入重试。")
        plan.status = TaskStatus.RUNNING
        touch_plan(plan)
        self._advance(plan)
        return self._repository.save_plan(plan)

    def _advance(self, plan: ExecutionPlan) -> None:
        if plan.status == TaskStatus.PAUSED:
            return

        changed = True
        while changed:
            changed = False
            completed = {node.id for node in plan.nodes if node.status == TaskStatus.COMPLETED}
            for node in plan.nodes:
                if node.status != TaskStatus.QUEUED:
                    continue
                if not set(node.dependencies).issubset(completed):
                    continue
                if node.requiresApproval:
                    node.status = TaskStatus.AWAITING_APPROVAL
                    add_log(node, "INFO", "等待用户确认后继续。")
                else:
                    _run_mock_agent(node)
                changed = True

        if any(node.status == TaskStatus.FAILED for node in plan.nodes):
            plan.status = TaskStatus.FAILED
            plan.completedAt = _now()
        elif any(node.status == TaskStatus.AWAITING_APPROVAL for node in plan.nodes):
            plan.status = TaskStatus.AWAITING_APPROVAL
        elif all(node.status == TaskStatus.COMPLETED for node in plan.nodes):
            plan.status = TaskStatus.COMPLETED
            plan.completedAt = _now()
        else:
            plan.status = TaskStatus.RUNNING
        touch_plan(plan)


def _run_mock_agent(node: TaskNode) -> None:
    now = _now()
    node.status = TaskStatus.RUNNING
    node.startedAt = node.startedAt or now
    node.attempts += 1
    add_log(node, "INFO", "Mock Agent 开始执行。")
    node.status = TaskStatus.COMPLETED
    node.completedAt = _now()
    add_log(node, "INFO", "Mock Agent 执行完成。")


def _find_node(plan: ExecutionPlan, node_id: str | None) -> TaskNode:
    if not node_id:
        raise ValueError("缺少任务节点。")
    for node in plan.nodes:
        if node.id == node_id:
            return node
    raise ValueError("任务节点不存在。")


def _first_failed_node(plan: ExecutionPlan) -> TaskNode:
    for node in plan.nodes:
        if node.status == TaskStatus.FAILED:
            return node
    raise ValueError("没有可重试的失败任务。")


def _default_node_specs() -> list[dict[str, object]]:
    return [
        {
            "id": "spec",
            "agentId": "spec-agent",
            "title": "生成工程规格",
            "description": "基于已确认立项书准备项目规格、BOM 和 IO Map。",
            "dependencies": [],
        },
        {
            "id": "spec_review",
            "agentId": "orchestrator",
            "title": "确认工程规格",
            "description": "等待用户确认规格基线后再进入下游生成。",
            "dependencies": ["spec"],
            "requiresApproval": True,
        },
        {
            "id": "code",
            "agentId": "code-agent",
            "title": "准备代码任务",
            "description": "为后续 Code Agent 创建 MicroPython 工程任务。",
            "dependencies": ["spec_review"],
        },
        {
            "id": "cad",
            "agentId": "cad-agent",
            "title": "准备结构任务",
            "description": "为后续 CAD Agent 创建结构件生成任务。",
            "dependencies": ["spec_review"],
        },
        {
            "id": "lesson",
            "agentId": "lesson-agent",
            "title": "准备教案任务",
            "description": "为后续 Lesson Agent 创建教师版和学生版材料任务。",
            "dependencies": ["spec_review"],
        },
        {
            "id": "deploy",
            "agentId": "deploy-agent",
            "title": "准备部署验证",
            "description": "为后续设备部署和 Mock 验证创建任务。",
            "dependencies": ["code"],
        },
        {
            "id": "publish_review",
            "agentId": "publish-agent",
            "title": "确认发布准备",
            "description": "等待用户确认产物齐备后再进入分享阶段。",
            "dependencies": ["cad", "lesson", "deploy"],
            "requiresApproval": True,
        },
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat()
