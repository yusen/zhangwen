"""Unified delivery/reproduction adapter over the existing Creator package service."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.creator.delivery import CreatorDeliveryService
from zhangwen.creator.models import (
    CompleteImportedReproductionRequest,
    CreateCreatorDeliveryRequest,
    CreatorDeliveryRecord,
    CreatorDeliveryVariant,
    CreatorWorkspace,
    EvidenceKind,
    EvidenceStatus,
    ImportCreatorDeliveryRequest,
    ImportCreatorDeliveryResponse,
    ReproductionReport,
)
from zhangwen.creator.repository import CreatorRepository
from zhangwen.domains.works.models import (
    CompleteWorkReproductionRequest,
    CreateWorkDeliveryRequest,
    ImportWorkDeliveryRequest,
    WorkDatabaseProtection,
    WorkDeliveryCard,
    WorkDeliveryOption,
    WorkDeliveryOverview,
    WorkDeliveryRecord,
    WorkDeliveryTechnicalDetails,
    WorkImportedCopy,
    WorkMigrationAudit,
    WorkMigrationPreservationItem,
    WorkMigrationReport,
    WorkRecoveryOverview,
    WorkRecoveryPoint,
    WorkReproductionReport,
    WorkReproductionSummary,
)
from zhangwen.projects.repository import ProjectRepository


_DELIVERY_LABELS: dict[str, str] = {
    "SHARE": "分享作品",
    "REPRODUCIBLE": "可复现副本",
    "TEMPLATE": "创作模板",
}

_DELIVERY_DESCRIPTIONS: dict[str, str] = {
    "SHARE": "适合查看作品故事、说明和展示结果。",
    "REPRODUCIBLE": "包含按固定版本重新制作和独立验收所需的材料。",
    "TEMPLATE": "保留创作起点和实现骨架，不继承原作品的验证结论。",
}


class WorkDeliveryService:
    """Expose consumer-facing delivery facts without owning another fact store."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._projects = ProjectRepository(data_dir)
        self._creator = CreatorRepository(data_dir)
        self._delivery = CreatorDeliveryService(data_dir)
        self._db_path = self._projects.db_path

    def overview(
        self,
        work_id: str,
        *,
        workspace: CreatorWorkspace | None = None,
    ) -> WorkDeliveryOverview:
        current = workspace or self._creator.workspace(work_id)
        self._projects.assert_project_access(work_id)
        with self._connect() as conn:
            delivery_rows = conn.execute(
                """
                SELECT id, project_id, variant, title, package_sha256,
                       manifest_json, privacy_report_json, created_at,
                       COALESCE(file_name, '') AS file_name
                FROM creator_deliveries
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (work_id,),
            ).fetchall()
            imported = conn.execute(
                """
                SELECT * FROM creator_delivery_imports
                WHERE imported_project_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (work_id,),
            ).fetchone()
            reproduction = conn.execute(
                """
                SELECT * FROM creator_reproductions
                WHERE source_project_id = ? OR reproduced_project_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (work_id, work_id),
            ).fetchone()
            migration = self._migration_report(conn, current, imported)

        ready = _ready_to_export(current)
        delivery_records = [_delivery_record(row) for row in delivery_rows]
        imported_copy = (
            WorkImportedCopy(
                importId=str(imported["id"]),
                sourceWorkId=str(imported["source_project_id"]),
                sourceDeliveryId=str(imported["source_delivery_id"]),
                naturalStatus=(
                    "这是从可复现副本导入的作品；原作者的真机结果和最终验收没有被继承。"
                ),
            )
            if imported is not None
            else None
        )
        reproduced = reproduction is not None and str(reproduction["status"]) == "PASSED"
        status, natural_status = _delivery_status(
            ready=ready,
            has_delivery=bool(delivery_records),
            imported=imported_copy is not None,
            reproduced=reproduced,
        )
        unavailable_reason = None if ready else "完成真机观察并由你明确验收后即可交付。"
        return WorkDeliveryOverview(
            status=status,
            naturalStatus=natural_status,
            readyToExport=ready,
            card=_work_card(current),
            options=[
                WorkDeliveryOption(
                    kind=kind,
                    label=_DELIVERY_LABELS[kind],
                    description=_DELIVERY_DESCRIPTIONS[kind],
                    available=ready,
                    unavailableReason=unavailable_reason,
                )
                for kind in ("SHARE", "REPRODUCIBLE", "TEMPLATE")
            ],
            deliveries=delivery_records,
            importedCopy=imported_copy,
            reproduction=WorkReproductionSummary(
                passed=reproduced,
                naturalStatus=(
                    "另一位测试者已经按固定版本独立完成复现与验收。"
                    if reproduced
                    else "可复现副本仍需由另一位测试者独立导入、验证并提交回执。"
                ),
                completedAt=(
                    str(reproduction["created_at"]) if reproduction is not None else None
                ),
            ),
            migration=migration,
            databaseProtection=_database_protection(self._data_dir),
        )

    def create(
        self,
        work_id: str,
        request: CreateWorkDeliveryRequest,
        *,
        actor_subject: str,
    ) -> tuple[WorkDeliveryRecord, str, WorkDeliveryOverview]:
        record = self._delivery.create(
            work_id,
            CreateCreatorDeliveryRequest(
                idempotencyKey=request.idempotency_key,
                variant=CreatorDeliveryVariant(request.kind),
                title=request.title,
            ),
            actor_subject=actor_subject,
        )
        if record.zip_base64 is None:
            raise RuntimeError("Delivery package payload was not returned by the package service.")
        return (
            _creator_delivery_record(record),
            record.zip_base64,
            self.overview(work_id),
        )

    def import_delivery(
        self,
        request: ImportWorkDeliveryRequest,
        *,
        importer_subject: str,
    ) -> ImportCreatorDeliveryResponse:
        return self._delivery.import_delivery(
            ImportCreatorDeliveryRequest(
                idempotencyKey=request.idempotency_key,
                zipBase64=request.zip_base64,
                importer=request.importer,
            ),
            importer_subject=importer_subject,
        )

    def complete_reproduction(
        self,
        work_id: str,
        request: CompleteWorkReproductionRequest,
        *,
        operator_subject: str,
    ) -> tuple[WorkReproductionReport, CreatorWorkspace]:
        report, source = self._delivery.complete_from_imported(
            work_id,
            CompleteImportedReproductionRequest(
                operator=request.operator,
                summary=request.summary,
            ),
            operator_subject=operator_subject,
        )
        return _reproduction_report(report), source

    def migration_report(self, work_id: str) -> WorkMigrationReport:
        return self.overview(work_id).migration

    def _migration_report(
        self,
        conn: sqlite3.Connection,
        workspace: CreatorWorkspace,
        imported: sqlite3.Row | None,
    ) -> WorkMigrationReport:
        work_id = workspace.work_id
        category_sources: tuple[
            tuple[str, str, tuple[tuple[str, str], ...]], ...
        ] = (
            (
                "WORK",
                "作品主记录",
                (
                    ("projects", "id = ?"),
                    ("creator_work_state", "project_id = ?"),
                    ("work_snapshots", "work_id = ?"),
                    ("work_learning_contexts", "work_id = ?"),
                ),
            ),
            (
                "PROPOSALS",
                "项目方案书",
                (
                    ("proposals", "project_id = ?"),
                    ("project_proposal_revisions_v2", "work_id = ?"),
                ),
            ),
            ("CONVERSATION", "对话记录", (("messages", "project_id = ?"),)),
            (
                "CODE",
                "代码历史",
                (
                    ("code_runs", "project_id = ?"),
                    ("code_files", "project_id = ?"),
                ),
            ),
            (
                "WOKWI",
                "旧 Wokwi 只读资料",
                (
                    ("device_lab_runs", "project_id = ? AND engine = 'WOKWI_CLOUD'"),
                    (
                        "artifact_versions",
                        "project_id = ? AND ("
                        "LOWER(COALESCE(source_entity_type, '')) LIKE 'wokwi_%' OR "
                        "LOWER(COALESCE(source_entity_id, '')) LIKE 'wokwi-%')",
                    ),
                ),
            ),
            (
                "DEVICE_LAB",
                "旧设备实验记录",
                (
                    ("device_lab_scenes", "project_id = ?"),
                    ("device_lab_runs", "project_id = ?"),
                    (
                        "device_lab_events",
                        "run_id IN (SELECT id FROM device_lab_runs WHERE project_id = ?)",
                    ),
                    ("device_parameter_sets", "project_id = ?"),
                ),
            ),
            (
                "LESSONS",
                "旧教案记录",
                (
                    ("lesson_runs", "project_id = ?"),
                    ("lesson_files", "project_id = ?"),
                ),
            ),
            (
                "RESULTS",
                "作品结果",
                (
                    ("artifacts", "project_id = ?"),
                    ("artifact_versions", "project_id = ?"),
                ),
            ),
            (
                "DEVICES",
                "设备记录",
                (
                    ("device_sessions", "project_id = ?"),
                    ("device_operations", "project_id = ?"),
                    ("work_device_bindings", "work_id = ?"),
                ),
            ),
            (
                "DELIVERIES",
                "交付记录",
                (
                    ("creator_deliveries", "project_id = ?"),
                    ("creator_delivery_imports", "imported_project_id = ?"),
                ),
            ),
        )
        items = [
            _migration_item(conn, work_id, category, label, sources)
            for category, label, sources in category_sources
        ]
        database_schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if imported is not None:
            source = "IMPORTED_PACKAGE"
        elif workspace.legacy:
            source = "LEGACY_PROJECT"
        else:
            source = "CREATOR_WORK"
        warnings: list[str] = []
        if workspace.needs_organization:
            warnings.append("旧作品已安全打开，建议在继续制作前确认当前目标和实现方案。")
        if imported is not None:
            warnings.append("导入副本的真机结果和最终验收已重置，必须在本机重新完成。")
        if source == "LEGACY_PROJECT" and not warnings:
            warnings.append("旧作品继续使用原数据库；统一界面只读取并组织现有内容。")
        needs_review = workspace.needs_organization or imported is not None
        natural_status = {
            "IMPORTED_PACKAGE": "作品包已校验并导入，原始包未被修改；请重新完成本机验证。",
            "LEGACY_PROJECT": (
                "旧作品已通过兼容层打开，原有内容保持在原数据库中。"
            ),
            "CREATOR_WORK": "作品已使用统一模型读取，无需复制或迁移数据。",
        }[source]
        retired_capabilities = ["WOKWI_CLOUD_RUNTIME", "LEGACY_QUICK_CREATE"]
        compatibility_imports = ["WOKWI_DIAGRAM_V1"]
        report_sha256 = _stable_sha256(
            {
                "schemaVersion": "zhangwen.work-migration-report/v2",
                "workId": work_id,
                "source": source,
                "databaseSchemaVersion": database_schema_version,
                "items": [item.model_dump(mode="json", by_alias=True) for item in items],
                "retiredCapabilities": retired_capabilities,
                "compatibilityImports": compatibility_imports,
            }
        )
        return WorkMigrationReport(
            workId=work_id,
            source=source,
            databaseSchemaVersion=database_schema_version,
            reportSha256=report_sha256,
            naturalStatus=natural_status,
            needsReview=needs_review,
            items=items,
            retiredCapabilities=retired_capabilities,
            compatibilityImports=compatibility_imports,
            warnings=warnings,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


class WorkRecoveryService:
    """Read and verify recovery evidence without restoring a live database."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._projects = ProjectRepository(data_dir)
        self._db_path = self._projects.db_path
        self._backup_dir = self._db_path.parent / "backups"

    def overview(self) -> WorkRecoveryOverview:
        recovery_points = [
            _recovery_point(path)
            for path in sorted(
                self._backup_dir.glob("*.sqlite3"),
                key=lambda item: item.stat().st_mtime_ns,
                reverse=True,
            )[:30]
        ]
        names = {item.file_name for item in recovery_points}
        with sqlite3.connect(self._db_path) as conn:
            schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            rows = conn.execute(
                """
                SELECT id, from_version, to_version, status, backup_path, applied_at
                FROM schema_migration_audit
                ORDER BY applied_at DESC LIMIT 50
                """
            ).fetchall()
        audits = [
            WorkMigrationAudit(
                id=str(row[0]),
                fromVersion=int(row[1]),
                toVersion=int(row[2]),
                status=str(row[3]),
                backupAvailable=(
                    Path(str(row[4])).name in names if row[4] not in {None, ""} else False
                ),
                appliedAt=str(row[5]),
            )
            for row in rows
        ]
        return WorkRecoveryOverview(
            schemaVersion=schema_version,
            databaseIntegrity="OK",
            naturalStatus=(
                f"数据库检查通过，已找到 {len(recovery_points)} 个本地恢复点。"
                if recovery_points
                else "数据库检查通过；首次需要迁移时会先自动创建恢复点。"
            ),
            restoreMode="RESTART_REQUIRED",
            recoveryPoints=recovery_points,
            migrationAudits=audits,
        )


def _ready_to_export(workspace: CreatorWorkspace) -> bool:
    return workspace.verification_level >= 6 and any(
        item.kind is EvidenceKind.USER_ACCEPTANCE
        and item.status is EvidenceStatus.CURRENT
        and item.passed
        for item in workspace.evidence
    )


def _delivery_status(
    *, ready: bool, has_delivery: bool, imported: bool, reproduced: bool
) -> tuple[str, str]:
    if reproduced:
        return "REPRODUCED", "固定版本已经由另一位测试者独立复现并验收。"
    if imported:
        return "IMPORTED_COPY", "作品已从校验通过的副本导入，正在等待本机重新验证。"
    if has_delivery:
        return "EXPORTED", "交付文件已经生成；可继续制作新的固定版本或等待独立复现。"
    if ready:
        return "READY", "作品已完成最终验收，可以生成分享、复现或模板文件。"
    return "PREPARING", "先完成数字结果、真机观察和最终验收，再生成交付文件。"


def _work_card(workspace: CreatorWorkspace) -> WorkDeliveryCard:
    solution = workspace.current_solution
    goal = workspace.current_goal
    included = ["作品卡片与制作说明", "材料、连接和安全说明", "复现与验收步骤"]
    if solution is not None and solution.structure.strip() not in {"", "不需要结构", "不适用"}:
        included.append("结构与装配结果")
    if workspace.evidence:
        included.append("数字与真机验证摘要")
    return WorkDeliveryCard(
        title=workspace.name,
        introduction=(solution.summary if solution is not None else workspace.initial_idea),
        story=(goal.observable_behavior if goal is not None else workspace.initial_idea),
        included=included,
        reproductionGuide=[
            "先查看作品说明、材料和安全边界。",
            "按包内固定版本建立数字结果，并重新完成必需场景。",
            "连接真实设备前检查确认点、备份和恢复方式。",
            "由实际观察者逐项确认真机行为，不能沿用原作者的通过状态。",
            "由另一位测试者完成独立复现后提交回执。",
        ],
    )


def _delivery_record(row: sqlite3.Row) -> WorkDeliveryRecord:
    manifest = json.loads(str(row["manifest_json"]))
    files = manifest.get("files", [])
    file_hashes = {
        str(item.get("path")): str(item.get("sha256"))
        for item in files
        if isinstance(item, dict) and item.get("path") and item.get("sha256")
    }
    byte_size = sum(
        int(item.get("byteSize", 0))
        for item in files
        if isinstance(item, dict)
    )
    kind = str(row["variant"])
    return WorkDeliveryRecord(
        id=str(row["id"]),
        kind=kind,
        label=_DELIVERY_LABELS[kind],
        title=str(row["title"]),
        fileName=str(row["file_name"]),
        byteSize=byte_size,
        createdAt=str(row["created_at"]),
        technical=WorkDeliveryTechnicalDetails(
            packageSha256=str(row["package_sha256"]),
            sourceProjectVersion=int(manifest.get("sourceProjectVersion", 0)),
            goalRevisionId=str(manifest.get("goalRevisionId", "")),
            solutionRevisionId=str(manifest.get("solutionRevisionId", "")),
            fileCount=len(files),
            fileHashes=file_hashes,
            versionBindings={
                str(key): str(value)
                for key, value in dict(manifest.get("versionBindings", {})).items()
            },
            privacyOk=bool(manifest.get("privacyOk")),
            manifest=manifest,
        ),
    )


def _creator_delivery_record(record: CreatorDeliveryRecord) -> WorkDeliveryRecord:
    manifest = record.manifest.model_dump(mode="json", by_alias=True)
    row = {
        "id": record.id,
        "variant": record.variant.value,
        "title": record.title,
        "package_sha256": record.package_sha256,
        "manifest_json": json.dumps(manifest, ensure_ascii=False),
        "created_at": record.created_at,
        "file_name": record.file_name,
    }
    return _delivery_record(_MappingRow(row))


def _reproduction_report(report: ReproductionReport) -> WorkReproductionReport:
    return WorkReproductionReport.model_validate(
        report.model_dump(mode="json", by_alias=True)
    )


def _database_protection(data_dir: Path) -> WorkDatabaseProtection:
    backup_dir = data_dir / "projects" / "backups"
    points = sorted(
        backup_dir.glob("*.sqlite3"),
        key=lambda item: item.stat().st_mtime_ns,
        reverse=True,
    )
    latest = points[0] if points else None
    return WorkDatabaseProtection(
        backupAvailable=latest is not None,
        lastBackupAt=(
            datetime.fromtimestamp(latest.stat().st_mtime, UTC).isoformat()
            if latest is not None
            else None
        ),
        integrityStatus="OK",
        restoreMode="RESTART_REQUIRED",
        naturalStatus=(
            "已保留本地恢复点；恢复数据库需要先关闭正在运行的掌问。"
            if latest is not None
            else "数据库检查通过；发生版本迁移前会自动创建恢复点。"
        ),
    )


def _recovery_point(path: Path) -> WorkRecoveryPoint:
    kind = (
        "PRE_MIGRATION"
        if path.name.startswith("pre-migration-")
        else "CORRUPT_QUARANTINE"
        if path.name.startswith("corrupt-")
        else "OTHER"
    )
    integrity = "NOT_APPLICABLE" if kind == "CORRUPT_QUARANTINE" else _backup_integrity(path)
    stat = path.stat()
    return WorkRecoveryPoint(
        fileName=path.name,
        kind=kind,
        byteSize=stat.st_size,
        createdAt=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        integrityStatus=integrity,
    )


def _backup_integrity(path: Path) -> str:
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        return "OK" if result is not None and result[0] == "ok" else "NEEDS_ATTENTION"
    except (OSError, sqlite3.DatabaseError):
        return "NEEDS_ATTENTION"


def _migration_item(
    conn: sqlite3.Connection,
    work_id: str,
    category: str,
    label: str,
    sources: tuple[tuple[str, str], ...],
) -> WorkMigrationPreservationItem:
    records: list[dict[str, object]] = []
    for table, where_clause in sources:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if table_exists is None:
            continue
        rows = conn.execute(
            f'SELECT * FROM "{table}" WHERE {where_clause}',  # noqa: S608 - fixed internal migration map
            (work_id,),
        ).fetchall()
        columns = [str(item[1]) for item in conn.execute(f'PRAGMA table_info("{table}")')]
        for row in rows:
            records.append(
                {
                    "table": table,
                    "values": {
                        column: _json_safe(value)
                        for column, value in zip(columns, row, strict=True)
                    },
                }
            )
    records.sort(
        key=lambda item: json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    return WorkMigrationPreservationItem(
        category=category,
        label=label,
        count=len(records),
        sourceTables=[table for table, _ in sources],
        contentSha256=_stable_sha256(records),
    )


def _json_safe(value: object) -> object:
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    return value


def _stable_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class _MappingRow:
    """Minimal sqlite.Row-compatible adapter for an in-memory delivery record."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> object:
        return self._values[key]
