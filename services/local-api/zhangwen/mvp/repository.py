"""Read-only MVP readiness aggregation."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.mvp.models import (
    MvpReadinessItem,
    MvpReadinessItemId,
    MvpReadinessReport,
    MvpReadinessStatus,
)
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION
from zhangwen.projects.repository import ProjectRepository


class MvpReadinessRepository:
    def __init__(self, data_dir: Path) -> None:
        self._project_repo = ProjectRepository(data_dir)
        self._db_path = self._project_repo.db_path

    def build_report(self, project_id: str) -> MvpReadinessReport:
        workspace = self._project_repo.get_workspace(project_id)
        with self._connect() as conn:
            items = [
                self._project_baseline_item(workspace.project.schemaVersion),
                self._solution_item(conn, project_id),
                self._proposal_item(conn, project_id),
                self._execution_plan_item(conn, project_id),
                self._spec_item(conn, project_id),
                self._code_item(conn, project_id),
                self._device_item(conn, project_id),
                self._cad_item(conn, project_id),
                self._lesson_item(conn, project_id),
                self._package_item(conn, project_id),
                self._artifacts_item(conn, project_id),
                self._security_item(conn, project_id),
            ]

        required_items = [item for item in items if item.required]
        ready_count = sum(
            1 for item in required_items if item.status == MvpReadinessStatus.READY
        )
        overall = _overall_status(required_items)
        return MvpReadinessReport(
            projectId=project_id,
            overallStatus=overall,
            readyCount=ready_count,
            totalCount=len(required_items),
            generatedAt=_now(),
            items=items,
            externalValidationRequired=[
                "真实 ESP32 串口发现、上传和重启日志需要人工在目标 Windows 机器上执行。",
                "真实固件烧录、Flash 擦除和设备文件覆盖不得由自动测试执行。",
                "真实 DeepSeek API Key 与付费调用需要用户在设置中手工配置并验证。",
            ],
            manualAcceptance=[
                "打开项目后确认中央主对话仍常驻，右侧只切换工作/产物/设备。",
                "打开立项书、代码、3D、设备日志或项目包产物浮窗，确认草稿不丢失。",
                "在设备 Tab 确认上传为 Dry Run，固件操作需要显式确认且不会真实擦除 Flash。",
                "导出项目包后检查隐私扫描通过，ZIP 不包含 API Key、系统凭据、绝对路径或真实串口标识。",
            ],
        )

    def _project_baseline_item(self, schema_version: int) -> MvpReadinessItem:
        ok = schema_version == CURRENT_SCHEMA_VERSION
        return _item(
            MvpReadinessItemId.PROJECT_BASELINE,
            "项目基线",
            ok,
            f"项目可打开，SQLite schema 已迁移到 v{CURRENT_SCHEMA_VERSION}。",
            f"项目基线未达到 schema v{CURRENT_SCHEMA_VERSION}。",
            [f"schemaVersion={schema_version}"],
        )

    def _solution_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = _latest(conn, "solutions", project_id)
        ok = row is not None and row["status"] == "CONFIRMED"
        return _item(
            MvpReadinessItemId.SOLUTION,
            "推荐实现方案",
            ok,
            "已有已确认推荐实现方案。",
            "需要先确认推荐实现方案。",
            _row_evidence(row, "solution"),
        )

    def _proposal_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = _latest(conn, "proposals", project_id)
        ok = row is not None and row["status"] == "APPROVED"
        return _item(
            MvpReadinessItemId.PROPOSAL,
            "立项书",
            ok,
            "立项书已确认，可作为下游工程基线。",
            "需要生成并确认立项书。",
            _row_evidence(row, "proposal"),
        )

    def _execution_plan_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> MvpReadinessItem:
        row = conn.execute(
            """
            SELECT * FROM execution_plans
            WHERE project_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        ok = row is not None and row["status"] == "COMPLETED"
        return _item(
            MvpReadinessItemId.EXECUTION_PLAN,
            "工作计划",
            ok,
            "执行计划已完成，Agent 状态可追踪。",
            "需要创建并完成执行计划。",
            _row_evidence(row, "plan"),
        )

    def _spec_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = _latest(conn, "spec_runs", project_id)
        validation = _json(row["validation_json"]) if row else {}
        ok = (
            row is not None
            and row["status"] == "APPROVED"
            and bool(validation.get("ok"))
        )
        file_count = _count(conn, "spec_files", project_id)
        return _item(
            MvpReadinessItemId.SPEC,
            "工程 Spec",
            ok,
            "Spec 已确认，BOM 与 IO Map 已通过规则校验。",
            "需要生成并确认 Spec。",
            [*_row_evidence(row, "spec"), f"specFiles={file_count}"],
        )

    def _code_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = _latest(conn, "code_runs", project_id)
        test_result = _json(row["test_result_json"]) if row else {}
        ok = (
            row is not None
            and row["status"] == "ACCEPTED"
            and bool(test_result.get("ok"))
        )
        file_count = _count(conn, "code_files", project_id)
        return _item(
            MvpReadinessItemId.CODE,
            "代码草稿",
            ok,
            "MicroPython 代码已接受，模拟测试通过。",
            "需要生成并接受代码草稿。",
            [*_row_evidence(row, "code"), f"codeFiles={file_count}"],
        )

    def _device_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = conn.execute(
            """
            SELECT * FROM device_operations
            WHERE project_id = ? AND kind = 'UPLOAD_CODE'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        ok = (
            row is not None
            and row["status"] in {"DRY_RUN_COMPLETE", "COMPLETED"}
            and (
                (row["status"] == "DRY_RUN_COMPLETE" and int(row["dry_run"]) == 1)
                or (row["status"] == "COMPLETED" and int(row["dry_run"]) == 0)
            )
            and row["command_label"] == "mpremote"
        )
        return _item(
            MvpReadinessItemId.DEVICE_DRY_RUN,
            "设备 Dry Run",
            ok,
            "MicroPython 上传 Dry Run 已完成，未执行真实串口命令。",
            "需要连接 Mock 设备并完成上传 Dry Run。",
            _operation_evidence(row),
        )

    def _cad_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = _latest(conn, "cad_runs", project_id)
        validation = _json(row["validation_json"]) if row else {}
        ok = (
            row is not None
            and row["status"] == "APPROVED"
            and bool(validation.get("ok"))
        )
        file_count = _count(conn, "cad_files", project_id)
        return _item(
            MvpReadinessItemId.CAD,
            "结构件 CAD",
            ok,
            "CAD 模板输出已确认，STEP/STL 预览可追踪。",
            "需要生成并确认 CAD 输出。",
            [*_row_evidence(row, "cad"), f"cadFiles={file_count}"],
            required=False,
        )

    def _lesson_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = _latest(conn, "lesson_runs", project_id)
        file_count = _count(conn, "lesson_files", project_id)
        ok = row is not None and row["status"] == "APPROVED" and file_count >= 4
        return _item(
            MvpReadinessItemId.LESSON,
            "课程教案",
            ok,
            "教师版、学生版、评价量表和安全说明已确认。",
            "需要生成并确认课程教案。",
            [*_row_evidence(row, "lesson"), f"lessonFiles={file_count}"],
            required=False,
        )

    def _package_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        row = conn.execute(
            """
            SELECT * FROM package_exports
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        report = _json(row["privacy_report_json"]) if row else {}
        ok = (
            row is not None
            and row["status"] == "EXPORTED"
            and bool(row["zip_base64"])
            and bool(report.get("ok"))
        )
        return _item(
            MvpReadinessItemId.PACKAGE,
            "项目包",
            ok,
            "项目包已导出，隐私扫描通过。",
            "需要导出通过隐私扫描的项目包。",
            _package_evidence(row, report),
        )

    def _artifacts_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        rows = conn.execute(
            "SELECT kind, COUNT(*) AS count FROM artifacts WHERE project_id = ? GROUP BY kind",
            (project_id,),
        ).fetchall()
        counts = {str(row["kind"]): int(row["count"]) for row in rows}
        required = {"DOCUMENT", "CODE", "DEVICE_LOG", "PACKAGE"}
        ok = required.issubset(counts)
        evidence = [f"{kind}={count}" for kind, count in sorted(counts.items())]
        return _item(
            MvpReadinessItemId.ARTIFACTS,
            "产物汇总",
            ok,
            "文档、代码、3D、设备日志和项目包产物均可追踪。",
            "需要补齐文档、代码、3D、设备日志和项目包产物。",
            evidence,
        )

    def _security_item(self, conn: sqlite3.Connection, project_id: str) -> MvpReadinessItem:
        blocked = conn.execute(
            """
            SELECT COUNT(*) FROM package_exports
            WHERE project_id = ? AND status IN ('BLOCKED', 'FAILED')
            """,
            (project_id,),
        ).fetchone()[0]
        unsafe_device_rows = conn.execute(
            """
            SELECT COUNT(*) FROM device_operations
            WHERE project_id = ? AND dry_run = 0 AND kind = 'FLASH_FIRMWARE'
            """,
            (project_id,),
        ).fetchone()[0]
        ok = int(blocked) == 0 and int(unsafe_device_rows) == 0
        return _item(
            MvpReadinessItemId.SECURITY,
            "安全边界",
            ok,
            "未发现被阻断项目包或真实设备操作记录。",
            "存在被阻断导出或真实设备操作记录，需要检查。",
            [f"blockedPackages={blocked}", f"realDeviceOperations={unsafe_device_rows}"],
            status=MvpReadinessStatus.BLOCKED if not ok else None,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _item(
    item_id: MvpReadinessItemId,
    label: str,
    ok: bool,
    ready_message: str,
    action_message: str,
    evidence: list[str],
    *,
    status: MvpReadinessStatus | None = None,
    required: bool = True,
) -> MvpReadinessItem:
    return MvpReadinessItem(
        id=item_id,
        label=label,
        status=status or (
            MvpReadinessStatus.READY if ok else MvpReadinessStatus.NEEDS_ACTION
        ),
        required=required,
        message=ready_message if ok else action_message,
        evidence=evidence,
    )


def _overall_status(items: list[MvpReadinessItem]) -> MvpReadinessStatus:
    if any(item.status == MvpReadinessStatus.BLOCKED for item in items):
        return MvpReadinessStatus.BLOCKED
    if all(item.status == MvpReadinessStatus.READY for item in items):
        return MvpReadinessStatus.READY
    return MvpReadinessStatus.NEEDS_ACTION


def _latest(
    conn: sqlite3.Connection,
    table: str,
    project_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        f"""
        SELECT * FROM {table}
        WHERE project_id = ?
        ORDER BY version DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()


def _count(conn: sqlite3.Connection, table: str, project_id: str) -> int:
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    )


def _row_evidence(row: sqlite3.Row | None, prefix: str) -> list[str]:
    if row is None:
        return [f"{prefix}=missing"]
    evidence = [f"{prefix}Id={row['id']}", f"status={row['status']}"]
    if "version" in row.keys():
        evidence.append(f"version={row['version']}")
    return evidence


def _operation_evidence(row: sqlite3.Row | None) -> list[str]:
    if row is None:
        return ["deviceOperation=missing"]
    return [
        f"operationId={row['id']}",
        f"status={row['status']}",
        f"dryRun={bool(row['dry_run'])}",
        f"command={row['command_label']}",
    ]


def _package_evidence(row: sqlite3.Row | None, report: dict[str, Any]) -> list[str]:
    if row is None:
        return ["package=missing"]
    return [
        f"packageId={row['id']}",
        f"status={row['status']}",
        f"privacyOk={bool(report.get('ok'))}",
        f"zipPresent={bool(row['zip_base64'])}",
    ]


def _json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _now() -> str:
    return datetime.now(UTC).isoformat()
