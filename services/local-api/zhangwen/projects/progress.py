from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from zhangwen.mvp.models import (
    MvpReadinessItem,
    MvpReadinessItemId,
    MvpReadinessReport,
    MvpReadinessStatus,
)
from zhangwen.mvp.repository import MvpReadinessRepository
from zhangwen.projects.models import (
    PendingItemActionType,
    PendingItemPriority,
    ProjectProgressConsistency,
    ProjectProgressStatus,
    ProjectStage,
)
from zhangwen.projects.repository import ProjectRepository


class ProjectCurrentAction(BaseModel):
    id: str
    title: str
    description: str
    actionType: PendingItemActionType | None = None
    blocking: bool


class ProjectArtifactSummary(BaseModel):
    draftCount: int = Field(ge=0)
    formalCount: int = Field(ge=0)
    message: str


class ProjectReadinessDimension(BaseModel):
    id: Literal["HARDWARE", "SPECIFICATION", "CODE", "TESTING", "DEPLOYMENT"]
    label: str
    status: MvpReadinessStatus
    message: str


class ProjectProgressSnapshot(BaseModel):
    projectId: str
    revision: int = Field(ge=0)
    stage: ProjectStage
    stageLabel: str
    status: ProjectProgressStatus
    currentAction: ProjectCurrentAction | None = None
    readiness: MvpReadinessReport
    readinessSummary: list[ProjectReadinessDimension]
    artifacts: ProjectArtifactSummary
    consistency: ProjectProgressConsistency
    consistencyMessages: list[str]


class ProjectProgressResponse(BaseModel):
    progress: ProjectProgressSnapshot


class ProjectProgressRepository:
    def __init__(self, data_dir) -> None:
        self._projects = ProjectRepository(data_dir)
        self._db_path = self._projects.db_path
        self._readiness = MvpReadinessRepository(data_dir)

    def build_snapshot(self, project_id: str) -> ProjectProgressSnapshot:
        workspace = self._projects.get_workspace(project_id)
        readiness = self._readiness.build_report(project_id)
        item_by_id = {item.id: item for item in readiness.items}
        with self._connect() as conn:
            derived_stage = self._derive_stage(conn, project_id, item_by_id)
            stored_stage = workspace.project.stage
            consistency = ProjectProgressConsistency.CONSISTENT
            consistency_messages: list[str] = []
            if stored_stage != derived_stage:
                conn.execute(
                    "UPDATE projects SET stage = ? WHERE id = ?",
                    (derived_stage.value, project_id),
                )
                consistency = ProjectProgressConsistency.REPAIRED
                consistency_messages.append(
                    f"已按已确认方案、产物和设备记录将阶段从 {stored_stage.value} 校正为 {derived_stage.value}。"
                )
            artifact_summary = self._artifact_summary(conn, project_id)
            current_action = self._current_action(
                workspace,
                readiness,
            )
            real_device_complete = _has_verified_runtime(conn, project_id)
        status = _progress_status(readiness, real_device_complete)
        readiness_summary = _readiness_summary(item_by_id)
        revision = _revision(
            {
                "stage": derived_stage.value,
                "status": status.value,
                "action": current_action.model_dump(mode="json") if current_action else None,
                "readiness": readiness.model_dump(mode="json"),
                "artifacts": artifact_summary.model_dump(mode="json"),
            }
        )
        return ProjectProgressSnapshot(
            projectId=project_id,
            revision=revision,
            stage=derived_stage,
            stageLabel=_STAGE_LABELS[derived_stage],
            status=status,
            currentAction=current_action,
            readiness=readiness,
            readinessSummary=readiness_summary,
            artifacts=artifact_summary,
            consistency=consistency,
            consistencyMessages=consistency_messages,
        )

    @staticmethod
    def _derive_stage(
        conn: sqlite3.Connection,
        project_id: str,
        items: dict[MvpReadinessItemId, MvpReadinessItem],
    ) -> ProjectStage:
        if _has_verified_runtime(conn, project_id):
            return ProjectStage.DEVICE_VERIFIED
        if _ready(items, MvpReadinessItemId.CODE):
            return ProjectStage.READY_TO_UPLOAD
        if _ready(items, MvpReadinessItemId.SPEC):
            return ProjectStage.IMPLEMENTING
        if _ready(items, MvpReadinessItemId.EXECUTION_PLAN):
            return ProjectStage.EXECUTION_PLANNED
        if _ready(items, MvpReadinessItemId.PROPOSAL):
            return ProjectStage.PROPOSAL_CONFIRMED
        if _has_row(conn, "proposals", project_id):
            return ProjectStage.PROPOSAL_DRAFT
        if _ready(items, MvpReadinessItemId.SOLUTION):
            return ProjectStage.SOLUTION_CONFIRMED
        if _has_row(conn, "solutions", project_id):
            return ProjectStage.SOLUTION_DRAFT
        message_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM messages WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        )
        return ProjectStage.CLARIFYING if message_count > 2 else ProjectStage.IDEA

    @staticmethod
    def _artifact_summary(conn: sqlite3.Connection, project_id: str) -> ProjectArtifactSummary:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM artifacts
            WHERE project_id = ? AND status <> 'ARCHIVED'
            GROUP BY status
            """,
            (project_id,),
        ).fetchall()
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        formal = counts.get("APPROVED", 0)
        draft = sum(
            counts.get(status, 0)
            for status in ("DRAFT", "GENERATING", "NEEDS_REVIEW", "STALE")
        )
        if draft and not formal:
            message = "已有草稿，确认后才会出现在正式产物中。"
        elif draft:
            message = f"已有 {formal} 项正式产物，另有 {draft} 项草稿待确认。"
        elif formal:
            message = f"已有 {formal} 项正式产物。"
        else:
            message = "尚无正式产物；对话中的草稿需确认后才会出现在产物栏。"
        return ProjectArtifactSummary(draftCount=draft, formalCount=formal, message=message)

    @staticmethod
    def _current_action(workspace, readiness: MvpReadinessReport) -> ProjectCurrentAction | None:
        pending = (
            workspace.coordinator.currentPendingItem
            if workspace.coordinator is not None
            else None
        ) or (
            workspace.sharedContext.currentPendingItem
            if workspace.sharedContext is not None
            else None
        )
        if pending is not None:
            return ProjectCurrentAction(
                id=pending.id,
                title=pending.title,
                description=pending.description,
                actionType=pending.actionType,
                blocking=pending.priority
                in {PendingItemPriority.SAFETY, PendingItemPriority.BLOCKING},
            )
        order = (
            MvpReadinessItemId.SOLUTION,
            MvpReadinessItemId.PROPOSAL,
            MvpReadinessItemId.EXECUTION_PLAN,
            MvpReadinessItemId.SPEC,
            MvpReadinessItemId.CODE,
            MvpReadinessItemId.DEVICE_DRY_RUN,
            MvpReadinessItemId.PACKAGE,
        )
        items = {item.id: item for item in readiness.items}
        for item_id in order:
            item = items.get(item_id)
            if item is not None and item.required and item.status != MvpReadinessStatus.READY:
                return ProjectCurrentAction(
                    id=f"readiness:{item_id.value}",
                    title=f"下一步：{item.label}",
                    description=item.message,
                    blocking=item.status == MvpReadinessStatus.BLOCKED,
                )
        return None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _readiness_summary(
    items: dict[MvpReadinessItemId, MvpReadinessItem],
) -> list[ProjectReadinessDimension]:
    solution = items[MvpReadinessItemId.SOLUTION]
    spec = items[MvpReadinessItemId.SPEC]
    code = items[MvpReadinessItemId.CODE]
    device = items[MvpReadinessItemId.DEVICE_DRY_RUN]
    return [
        ProjectReadinessDimension(
            id="HARDWARE",
            label="硬件核验",
            status=spec.status if spec.status == MvpReadinessStatus.READY else solution.status,
            message="硬件、电气约束与 IO 映射随方案和工程规格统一核验。",
        ),
        ProjectReadinessDimension(id="SPECIFICATION", label="工程规格", status=spec.status, message=spec.message),
        ProjectReadinessDimension(id="CODE", label="代码", status=code.status, message=code.message),
        ProjectReadinessDimension(id="TESTING", label="测试", status=code.status, message=code.message),
        ProjectReadinessDimension(id="DEPLOYMENT", label="设备部署", status=device.status, message=device.message),
    ]


def _progress_status(
    readiness: MvpReadinessReport,
    real_device_complete: bool,
) -> ProjectProgressStatus:
    if readiness.overallStatus == MvpReadinessStatus.BLOCKED:
        return ProjectProgressStatus.BLOCKED
    if real_device_complete and readiness.overallStatus == MvpReadinessStatus.READY:
        return ProjectProgressStatus.COMPLETE
    if readiness.overallStatus == MvpReadinessStatus.READY:
        return ProjectProgressStatus.READY
    return ProjectProgressStatus.ACTION_REQUIRED


def _ready(
    items: dict[MvpReadinessItemId, MvpReadinessItem],
    item_id: MvpReadinessItemId,
) -> bool:
    item = items.get(item_id)
    return item is not None and item.status == MvpReadinessStatus.READY


def _has_verified_runtime(conn: sqlite3.Connection, project_id: str) -> bool:
    rows = conn.execute(
        """
        SELECT log FROM device_operations
        WHERE project_id = ? AND kind = 'UPLOAD_CODE'
          AND status = 'COMPLETED' AND dry_run = 0
        ORDER BY created_at DESC
        """,
        (project_id,),
    ).fetchall()
    for row in rows:
        try:
            state = json.loads(str(row["log"]))
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(state, dict):
            continue
        metadata = state.get("metadata")
        runtime = metadata.get("runtimeEvidence") if isinstance(metadata, dict) else None
        if isinstance(runtime, dict) and runtime.get("ok") is True:
            return True
    return False


def _has_row(conn: sqlite3.Connection, table: str, project_id: str) -> bool:
    return conn.execute(
        f"SELECT 1 FROM {table} WHERE project_id = ? LIMIT 1",
        (project_id,),
    ).fetchone() is not None


def _revision(payload: dict[str, object]) -> int:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return int(digest[:12], 16)


_STAGE_LABELS = {
    ProjectStage.IDEA: "描述创意",
    ProjectStage.CLARIFYING: "澄清需求",
    ProjectStage.SOLUTION_DRAFT: "推荐方案",
    ProjectStage.SOLUTION_CONFIRMED: "方案已确认",
    ProjectStage.PROPOSAL_DRAFT: "立项书草稿",
    ProjectStage.PROPOSAL_CONFIRMED: "立项书已确认",
    ProjectStage.EXECUTION_PLANNED: "执行计划已确认",
    ProjectStage.IMPLEMENTING: "实现中",
    ProjectStage.VALIDATING: "测试验证",
    ProjectStage.READY_TO_UPLOAD: "可上传设备",
    ProjectStage.DEVICE_VERIFIED: "设备运行已验证",
    ProjectStage.READY_TO_PUBLISH: "可交付",
    ProjectStage.PUBLISHED: "已发布",
}
