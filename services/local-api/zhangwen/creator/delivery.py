"""Creator delivery bundles built on the existing safe project-package boundary."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sqlite3
import stat
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from zhangwen.creator.models import (
    CompleteReproductionRequest,
    CompleteImportedReproductionRequest,
    CreateCreatorDeliveryRequest,
    CreatorCommand,
    CreatorCommandRequest,
    CreatorDeliveryFile,
    CreatorDeliveryManifestV1,
    CreatorDeliveryRecord,
    CreatorDeliveryVariant,
    CreatorImportContext,
    CreatorWorkspace,
    EvidenceCommandPayload,
    EvidenceKind,
    ImportCreatorDeliveryRequest,
    ImportCreatorDeliveryResponse,
    ReproductionReport,
)
from zhangwen.creator.metrics import append_creator_metric, metric_trigger_id
from zhangwen.creator.repository import CreatorError, CreatorRepository
from zhangwen.device_lab.boards import BOARDS, scene_profile
from zhangwen.device_lab.models import DeviceLabSceneV1
from zhangwen.device_lab.repository import DeviceLabRepository
from zhangwen.device_lab.scene import materialize_device_lab_scene
from zhangwen.project_packages.errors import ProjectPackageError
from zhangwen.project_packages.models import (
    ExportProjectPackageRequest,
    ImportProjectPackageRequest,
    ProjectPackageArtifactSelectionPatch,
)
from zhangwen.project_packages.privacy import scan_package_payload
from zhangwen.project_packages.repository import ProjectPackageRepository
from zhangwen.projects.repository import ProjectRepository


MAX_CREATOR_DELIVERY_MEMBERS = 16
MAX_CREATOR_DELIVERY_FILE_BYTES = 512 * 1024 * 1024
MAX_CREATOR_DELIVERY_BYTES = 600 * 1024 * 1024


class CreatorDeliveryService:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._creator = CreatorRepository(data_dir)
        self._projects = ProjectRepository(data_dir)
        self._packages = ProjectPackageRepository(data_dir)
        self._db_path = self._projects.db_path

    def recover_incomplete_imports(self) -> int:
        """Remove projects left by a process interruption before API startup."""

        with self._connect() as conn:
            intents = conn.execute(
                """
                SELECT id, imported_project_id
                FROM creator_delivery_import_intents
                WHERE status = 'PREPARING'
                ORDER BY created_at
                """
            ).fetchall()
        for intent in intents:
            self._packages.discard_imported_project(
                str(intent["imported_project_id"])
            )
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE creator_delivery_import_intents
                    SET status = 'RECOVERED', updated_at = ?
                    WHERE id = ? AND status = 'PREPARING'
                    """,
                    (_now(), str(intent["id"])),
                )
        return len(intents)

    def create(
        self,
        project_id: str,
        request: CreateCreatorDeliveryRequest,
        *,
        actor_subject: str,
    ) -> CreatorDeliveryRecord:
        request_hash = _hash_json(
            {
                "projectId": project_id,
                "variant": request.variant.value,
                "title": request.title,
                "actorSubject": actor_subject,
            }
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM creator_deliveries "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, request.idempotency_key),
            ).fetchone()
        if existing is not None:
            if str(existing["request_hash"]) != request_hash:
                raise CreatorError(
                    "CREATOR_IDEMPOTENCY_KEY_REUSED",
                    "该幂等键已绑定到不同的交付导出请求。",
                    status_code=409,
                )
            return self._delivery_from_row(existing)
        workspace = self._creator.workspace(project_id)
        if workspace.verification_level < 6 or not _current_evidence(
            workspace, EvidenceKind.USER_ACCEPTANCE
        ):
            raise CreatorError(
                "CREATOR_USER_ACCEPTANCE_REQUIRED",
                "用户明确验收达到等级 6 后才能生成交付包。",
                status_code=409,
            )
        if workspace.current_goal is None or workspace.current_solution is None:
            raise CreatorError(
                "CREATOR_DELIVERY_REVISIONS_REQUIRED",
                "交付包缺少当前目标或方案修订。",
                status_code=409,
            )
        materials = self._delivery_materials(project_id, workspace)
        delivery_id = f"creator_delivery_{uuid.uuid4().hex}"
        created_at = _now()
        title = (request.title or _default_title(workspace.name, request.variant)).strip()
        selection = _selection(request.variant)
        try:
            base_package = self._packages.export_project(
                project_id,
                ExportProjectPackageRequest(
                    title=title,
                    artifactSelection=selection,
                ),
            )
        except ProjectPackageError as exc:
            raise CreatorError(exc.code, exc.message, status_code=exc.status_code) from exc
        if not base_package.zipBase64:
            raise CreatorError(
                "CREATOR_BASE_PACKAGE_MISSING",
                "底层项目包没有生成可校验 ZIP。",
                status_code=500,
            )
        base_package_bytes = base64.b64decode(base_package.zipBase64, validate=True)
        sanitized_workspace = _sanitized_workspace(
            workspace,
            request.variant,
            materials,
        )
        evidence = _sanitized_evidence(workspace, request.variant)
        guide = _reproduction_guide(workspace, request.variant)
        payloads: dict[str, bytes] = {
            "creator/workspace.json": _json_bytes(sanitized_workspace),
            "creator/evidence.json": _json_bytes(evidence),
            "creator/reproduction-guide.md": guide.encode("utf-8"),
            "payload/project-package.zip": base_package_bytes,
        }
        privacy_report = scan_package_payload(
            {
                path: content.decode("utf-8")
                for path, content in payloads.items()
                if path != "payload/project-package.zip"
            }
        )
        if not privacy_report.ok:
            raise CreatorError(
                "CREATOR_DELIVERY_PRIVACY_BLOCKED",
                "作品交付包包含凭据、端点、设备标识或本机路径，已阻止生成。",
                status_code=422,
            )
        payloads["privacy_report.json"] = _json_bytes(
            privacy_report.model_dump(mode="json")
        )
        files = [
            CreatorDeliveryFile(
                path=path,
                byteSize=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
            for path, content in sorted(payloads.items())
        ]
        manifest = CreatorDeliveryManifestV1(
            deliveryId=delivery_id,
            variant=request.variant,
            sourceWorkId=project_id,
            sourceProjectVersion=workspace.project_version,
            createdAt=created_at,
            goalRevisionId=workspace.current_goal.id,
            solutionRevisionId=workspace.current_solution.id,
            devicePackages=list(materials["devicePackages"]),
            versionBindings=dict(materials["versionBindings"]),
            evidenceKinds=[EvidenceKind(str(item["kind"])) for item in evidence],
            maturity=dict(materials["maturity"]),
            files=files,
            privacyOk=True,
        )
        payloads["manifest.json"] = _json_bytes(
            manifest.model_dump(mode="json", by_alias=True)
        )
        archive = _zip_payloads(payloads)
        package_sha256 = hashlib.sha256(archive).hexdigest()
        file_name = f"{_safe_file_stem(workspace.name)}-{request.variant.value.lower()}-{delivery_id[-8:]}.zwcreator.zip"
        zip_base64 = base64.b64encode(archive).decode("ascii")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM creator_deliveries "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已绑定到不同的交付导出请求。",
                        status_code=409,
                    )
                return self._delivery_from_row(existing)
            try:
                conn.execute(
                    """
                    INSERT INTO creator_deliveries (
                  id, project_id, variant, title, package_sha256, manifest_json,
                  privacy_report_json, base_package_id, created_at,
                  idempotency_key, request_hash, actor_subject, zip_base64, file_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id,
                    project_id,
                    request.variant.value,
                    title,
                    package_sha256,
                    json.dumps(manifest.model_dump(mode="json", by_alias=True), ensure_ascii=False),
                    json.dumps(privacy_report.model_dump(mode="json"), ensure_ascii=False),
                    base_package.id,
                    created_at,
                    request.idempotency_key,
                    request_hash,
                    actor_subject,
                    zip_base64,
                    file_name,
                    ),
                )
            except sqlite3.IntegrityError:
                winner = conn.execute(
                    "SELECT * FROM creator_deliveries "
                    "WHERE project_id = ? AND idempotency_key = ?",
                    (project_id, request.idempotency_key),
                ).fetchone()
                if winner is None or str(winner["request_hash"]) != request_hash:
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已绑定到不同的交付导出请求。",
                        status_code=409,
                    )
                return self._delivery_from_row(winner)
            current_count = sum(
                1
                for item in workspace.evidence
                if item.status.value == "CURRENT" and item.passed
            )
            required_count = len(manifest.evidence_kinds)
            append_creator_metric(
                conn,
                project_id,
                {
                    "metric": "DELIVERY_EXPORTED",
                    "triggerId": metric_trigger_id(
                        metric="DELIVERY_EXPORTED",
                        project_id=project_id,
                        source_key=delivery_id,
                    ),
                    "variant": request.variant.value,
                    "requiredEvidenceCount": required_count,
                    "currentEvidenceCount": current_count,
                    "coverageRatio": (
                        min(current_count, required_count) / required_count
                        if required_count
                        else 1.0
                    ),
                },
            )
        return CreatorDeliveryRecord(
            id=delivery_id,
            workId=project_id,
            variant=request.variant,
            status="EXPORTED",
            title=title,
            fileName=file_name,
            packageSha256=package_sha256,
            manifest=manifest,
            privacyReport=privacy_report.model_dump(mode="json"),
            zipBase64=zip_base64,
            createdAt=created_at,
        )

    def import_delivery(
        self, request: ImportCreatorDeliveryRequest, *, importer_subject: str
    ) -> ImportCreatorDeliveryResponse:
        archive = _decode_base64(request.zip_base64)
        package_sha256 = hashlib.sha256(archive).hexdigest()
        request_hash = _hash_json(
            {"packageSha256": package_sha256, "importerSubject": importer_subject}
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM creator_delivery_imports "
                "WHERE importer_subject = ? AND idempotency_key = ?",
                (importer_subject, request.idempotency_key),
            ).fetchone()
        if existing is not None:
            if str(existing["request_hash"]) != request_hash:
                raise CreatorError(
                    "CREATOR_IDEMPOTENCY_KEY_REUSED",
                    "该幂等键已绑定到不同的交付导入包。",
                    status_code=409,
                )
            return ImportCreatorDeliveryResponse(
                importId=str(existing["id"]),
                sourceDeliveryId=str(existing["source_delivery_id"]),
                packageSha256=str(existing["package_sha256"]),
                workspace=self._creator.workspace(str(existing["imported_project_id"])),
            )
        files = _read_delivery_zip(archive)
        manifest = _load_manifest(files)
        _validate_manifest_files(manifest, files)
        privacy_report = scan_package_payload(
            {
                path: content.decode("utf-8")
                for path, content in files.items()
                if path != "payload/project-package.zip"
            }
        )
        if not manifest.privacy_ok or not privacy_report.ok:
            raise CreatorError(
                "CREATOR_DELIVERY_PRIVACY_BLOCKED",
                "作品包隐私复检未通过。",
                status_code=422,
            )
        workspace_data = _load_json(files, "creator/workspace.json")
        evidence_data = _load_json_list(files, "creator/evidence.json")
        _validate_delivery_snapshot(manifest, workspace_data, evidence_data)
        project_payload = files["payload/project-package.zip"]
        intent_digest = hashlib.sha256(
            (
                f"creator-delivery-import/v1\0{importer_subject}\0"
                f"{request.idempotency_key}"
            ).encode("utf-8")
        ).hexdigest()
        intent_id = f"creator_import_intent_{intent_digest[:32]}"
        import_id = f"creator_import_{intent_digest[:32]}"
        imported_id = f"prj_creator_import_{intent_digest[:24]}"
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            completed = conn.execute(
                """
                SELECT * FROM creator_delivery_imports
                WHERE importer_subject = ? AND idempotency_key = ?
                """,
                (importer_subject, request.idempotency_key),
            ).fetchone()
            if completed is not None:
                if str(completed["request_hash"]) != request_hash:
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已绑定到不同的交付导入包。",
                        status_code=409,
                    )
                completed_response = ImportCreatorDeliveryResponse(
                    importId=str(completed["id"]),
                    sourceDeliveryId=str(completed["source_delivery_id"]),
                    packageSha256=str(completed["package_sha256"]),
                    workspace=self._creator.workspace(
                        str(completed["imported_project_id"])
                    ),
                )
                conn.commit()
                return completed_response
            intent = conn.execute(
                """
                SELECT * FROM creator_delivery_import_intents
                WHERE importer_subject = ? AND idempotency_key = ?
                """,
                (importer_subject, request.idempotency_key),
            ).fetchone()
            if intent is not None:
                if str(intent["request_hash"]) != request_hash:
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已绑定到不同的交付导入包。",
                        status_code=409,
                    )
                if str(intent["status"]) != "RECOVERED":
                    raise CreatorError(
                        "CREATOR_DELIVERY_IMPORT_IN_PROGRESS",
                        "同一交付包正在导入；若服务刚刚重启，请等待启动恢复完成后重试。",
                        status_code=409,
                    )
                conn.execute(
                    """
                    UPDATE creator_delivery_import_intents
                    SET status = 'PREPARING', updated_at = ?
                    WHERE id = ? AND status = 'RECOVERED'
                    """,
                    (now, str(intent["id"])),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO creator_delivery_import_intents (
                      id, importer_subject, idempotency_key, request_hash,
                      package_sha256, imported_project_id, status,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'PREPARING', ?, ?)
                    """,
                    (
                        intent_id,
                        importer_subject,
                        request.idempotency_key,
                        request_hash,
                        package_sha256,
                        imported_id,
                        now,
                        now,
                    ),
                )
        try:
            _record, imported = self._packages.import_project(
                ImportProjectPackageRequest(
                    zipBase64=base64.b64encode(project_payload).decode("ascii")
                ),
                target_project_id=imported_id,
            )
        except ProjectPackageError as exc:
            self._abandon_import_intent(intent_id, imported_id)
            raise CreatorError(exc.code, exc.message, status_code=exc.status_code) from exc
        except Exception:
            self._abandon_import_intent(intent_id, imported_id)
            raise
        assert imported.project.id == imported_id
        try:
            self._restore_creator_snapshot(imported_id, workspace_data)
            id_map = self._restore_delivery_materials(
                imported_id, workspace_data, project_payload
            )
        except Exception:
            self._abandon_import_intent(intent_id, imported_id)
            raise
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO creator_delivery_imports (
                      id, source_delivery_id, source_project_id, imported_project_id,
                      importer, package_sha256, manifest_json, created_at,
                      idempotency_key, request_hash, importer_subject, id_map_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        import_id,
                        manifest.delivery_id,
                        manifest.source_work_id,
                        imported_id,
                        request.importer,
                        package_sha256,
                        json.dumps(manifest.model_dump(mode="json", by_alias=True), ensure_ascii=False),
                        now,
                        request.idempotency_key,
                        request_hash,
                        importer_subject,
                        json.dumps(id_map, ensure_ascii=False, sort_keys=True),
                    ),
                )
                deleted = conn.execute(
                    """
                    DELETE FROM creator_delivery_import_intents
                    WHERE id = ? AND imported_project_id = ?
                    """,
                    (intent_id, imported_id),
                )
                if deleted.rowcount != 1:
                    raise sqlite3.IntegrityError(
                        "Creator delivery import intent was lost before commit."
                    )
        except sqlite3.IntegrityError:
            self._abandon_import_intent(intent_id, imported_id)
            return self.import_delivery(request, importer_subject=importer_subject)
        except Exception:
            self._abandon_import_intent(intent_id, imported_id)
            raise
        return ImportCreatorDeliveryResponse(
            importId=import_id,
            sourceDeliveryId=manifest.delivery_id,
            packageSha256=package_sha256,
            workspace=self._creator.workspace(imported_id),
        )

    def _abandon_import_intent(
        self,
        intent_id: str,
        imported_project_id: str,
    ) -> None:
        self._packages.discard_imported_project(imported_project_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE creator_delivery_import_intents
                SET status = 'RECOVERED', updated_at = ?
                WHERE id = ? AND imported_project_id = ?
                """,
                (_now(), intent_id, imported_project_id),
            )

    def complete_reproduction(
        self,
        source_project_id: str,
        request: CompleteReproductionRequest,
        *, operator_subject: str,
    ) -> tuple[ReproductionReport, CreatorWorkspace]:
        self._projects.assert_project_access(source_project_id)
        reproduced = self._creator.workspace(request.reproduced_work_id)
        if reproduced.verification_level < 6 or not _current_evidence(
            reproduced, EvidenceKind.USER_ACCEPTANCE
        ):
            raise CreatorError(
                "CREATOR_REPRODUCED_WORK_NOT_ACCEPTED",
                "第二位用户必须在导入副本中重新完成验收后才能记录复现。",
                status_code=409,
            )
        with self._connect() as conn:
            imported = conn.execute(
                """
                SELECT * FROM creator_delivery_imports
                WHERE id = ? AND source_project_id = ? AND imported_project_id = ?
                """,
                (request.import_id, source_project_id, request.reproduced_work_id),
            ).fetchone()
            if imported is None:
                raise CreatorError(
                    "CREATOR_REPRODUCTION_IMPORT_NOT_FOUND",
                    "找不到与原作品和复现作品匹配的导入记录。",
                    status_code=409,
                )
            delivery = conn.execute(
                """
                SELECT * FROM creator_deliveries
                WHERE id = ? AND project_id = ? AND variant = 'REPRODUCIBLE'
                """,
                (str(imported["source_delivery_id"]), source_project_id),
            ).fetchone()
            if delivery is None or str(delivery["package_sha256"]) != str(
                imported["package_sha256"]
            ):
                raise CreatorError(
                    "CREATOR_REPRODUCTION_PACKAGE_MISMATCH",
                    "导入包与原作品的可复现交付记录不一致。",
                    status_code=409,
                )
            original_actor, original_subject = self._acceptance_identity(
                conn, source_project_id
            )
            operator = request.operator.strip()
            reproduced_actor, reproduced_subject = self._acceptance_identity(
                conn, request.reproduced_work_id
            )
            importer_subject = str(imported["importer_subject"] or "")
            if not reproduced_subject or reproduced_subject != operator_subject:
                raise CreatorError(
                    "CREATOR_REPRODUCTION_ACCEPTOR_MISMATCH",
                    "复现回执操作者必须是导入副本中实际完成最终验收的人。",
                    status_code=409,
                )
            if importer_subject != operator_subject:
                raise CreatorError(
                    "CREATOR_REPRODUCTION_IMPORTER_MISMATCH",
                    "导入、独立验收和复现回执必须由同一位第二测试用户完成。",
                    status_code=409,
                )
            if original_subject and original_subject == operator_subject:
                raise CreatorError(
                    "CREATOR_SECOND_OPERATOR_REQUIRED",
                    "复现验收必须由不同于原验收者的第二位测试用户完成。",
                    status_code=409,
                )
            existing = conn.execute(
                """
                SELECT * FROM creator_reproductions
                WHERE source_project_id = ? AND import_id = ?
                """,
                (source_project_id, request.import_id),
            ).fetchone()
            if existing is None:
                report_id = f"reproduction_{uuid.uuid4().hex}"
                now = _now()
                conn.execute(
                    """
                    INSERT INTO creator_reproductions (
                      id, source_project_id, delivery_id, import_id,
                      reproduced_project_id, operator, package_sha256, status, created_at
                      , operator_subject
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PASSED', ?, ?)
                    """,
                    (
                        report_id,
                        source_project_id,
                        str(delivery["id"]),
                        request.import_id,
                        request.reproduced_work_id,
                        operator,
                        str(imported["package_sha256"]),
                        now,
                        operator_subject,
                    ),
                )
            else:
                report_id = str(existing["id"])
                now = str(existing["created_at"])
            append_creator_metric(
                conn,
                source_project_id,
                {
                    "metric": "REPRODUCTION_FINISHED",
                    "triggerId": metric_trigger_id(
                        metric="REPRODUCTION_FINISHED",
                        project_id=source_project_id,
                        source_key=report_id,
                    ),
                    "passed": True,
                },
            )
            conn.commit()
        payload = EvidenceCommandPayload(
            passed=True,
            summary=request.summary,
            sourceId=report_id,
            bindings={
                "deliveryId": str(delivery["id"]),
                "packageSha256": str(imported["package_sha256"]),
                "reproducedWorkId": request.reproduced_work_id,
            },
        )
        self._creator.validate_command_source(
            source_project_id, CreatorCommand.RECORD_REPRODUCTION, payload.model_dump(mode="json", by_alias=True)
        )
        source = self._creator.workspace(source_project_id)
        result = self._creator.execute(
            source_project_id,
            CreatorCommand.RECORD_REPRODUCTION,
            CreatorCommandRequest(
                baseProjectVersion=source.project_version,
                idempotencyKey=f"creator-reproduction-{report_id}",
                payload=payload.model_dump(mode="json", by_alias=True),
            ),
        )
        report = ReproductionReport(
            id=report_id,
            sourceWorkId=source_project_id,
            deliveryId=str(delivery["id"]),
            importId=request.import_id,
            reproducedWorkId=request.reproduced_work_id,
            operator=operator,
            packageSha256=str(imported["package_sha256"]),
            passed=True,
            createdAt=now,
        )
        return report, result.workspace

    def import_context(self, project_id: str) -> CreatorImportContext | None:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM creator_delivery_imports
                WHERE imported_project_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return CreatorImportContext(
            importId=str(row["id"]),
            sourceWorkId=str(row["source_project_id"]),
            sourceDeliveryId=str(row["source_delivery_id"]),
            importer=str(row["importer"]),
            packageSha256=str(row["package_sha256"]),
        )

    def complete_from_imported(
        self,
        reproduced_project_id: str,
        request: CompleteImportedReproductionRequest,
        *, operator_subject: str,
    ) -> tuple[ReproductionReport, CreatorWorkspace]:
        context = self.import_context(reproduced_project_id)
        if context is None:
            raise CreatorError(
                "CREATOR_IMPORT_CONTEXT_NOT_FOUND",
                "当前作品不是由可复现 Creator 作品包导入。",
                status_code=404,
            )
        return self.complete_reproduction(
            context.source_work_id,
            CompleteReproductionRequest(
                importId=context.import_id,
                reproducedWorkId=reproduced_project_id,
                operator=request.operator,
                summary=request.summary,
            ),
            operator_subject=operator_subject,
        )

    def _restore_creator_snapshot(self, project_id: str, data: dict[str, Any]) -> None:
        goal = data.get("goal")
        solution = data.get("solution")
        scenarios = data.get("acceptanceScenarios")
        hardware_ids = data.get("selectedHardwareIds", [])
        if not isinstance(goal, dict) or not isinstance(solution, dict) or not isinstance(scenarios, list):
            raise CreatorError(
                "CREATOR_DELIVERY_SNAPSHOT_INVALID",
                "作品包缺少可恢复的目标、方案或验收场景。",
                status_code=422,
            )
        if isinstance(hardware_ids, list):
            self._projects.replace_preferred_hardware(
                project_id,
                [str(item) for item in hardware_ids if isinstance(item, str)],
            )
        workspace = self._creator.workspace(project_id)
        workspace = self._creator.execute(
            project_id,
            CreatorCommand.CONFIRM_GOAL,
            CreatorCommandRequest(
                baseProjectVersion=workspace.project_version,
                idempotencyKey=f"delivery-goal-{uuid.uuid4().hex}",
                payload={
                    "statement": goal.get("statement"),
                    "observableBehavior": goal.get("observableBehavior"),
                    "constraints": goal.get("constraints", []),
                    "successCriteria": goal.get("successCriteria", []),
                },
            ),
        ).workspace
        self._creator.execute(
            project_id,
            CreatorCommand.CONFIRM_SOLUTION,
            CreatorCommandRequest(
                baseProjectVersion=workspace.project_version,
                idempotencyKey=f"delivery-solution-{uuid.uuid4().hex}",
                payload={
                    "summary": solution.get("summary"),
                    "logic": solution.get("logic"),
                    "hardware": solution.get("hardware"),
                    "software": solution.get("software"),
                    "structure": solution.get("structure", "不需要结构"),
                    "simulation": solution.get("simulation"),
                    "safety": solution.get("safety"),
                    "bom": solution.get("bom", []),
                    "ioMap": solution.get("ioMap", []),
                    "acceptanceScenarios": scenarios,
                },
            ),
        )
        with self._connect() as conn:
            conn.execute(
                "UPDATE creator_work_state SET origin = 'CREATOR' WHERE project_id = ?",
                (project_id,),
            )

    def _restore_delivery_materials(
        self, project_id: str, data: dict[str, Any], project_package: bytes
    ) -> dict[str, dict[str, str]]:
        materials = data.get("deliveryMaterials")
        if not isinstance(materials, dict):
            raise CreatorError(
                "CREATOR_DELIVERY_MATERIALS_INVALID",
                "作品包缺少可恢复的交付材料。",
                status_code=422,
            )
        workspace = self._creator.workspace(project_id)
        if workspace.current_solution is None:
            raise CreatorError("CREATOR_DELIVERY_MATERIALS_INVALID", "导入方案尚未恢复。")
        artifact_map = _project_artifact_map(project_package, project_id)
        scene = materialize_device_lab_scene(self._db_path, self._data_dir, project_id)
        if scene is None:
            raise CreatorError(
                "CREATOR_DELIVERY_SCENE_RESTORE_FAILED",
                "无法从导入方案恢复数字原型。",
                status_code=422,
            )
        parameters = materials.get("parameters")
        code = materials.get("code")
        if not isinstance(parameters, dict) or not isinstance(code, dict):
            raise CreatorError(
                "CREATOR_DELIVERY_MATERIALS_INVALID",
                "作品包缺少参数或代码材料。",
                status_code=422,
            )
        restored_parameter_request = {
            "boardId": scene.boardId.value,
            "profileRevision": scene_profile(scene).revision,
            "label": str(parameters.get("label") or "导入参数"),
            "values": dict(parameters.get("values") or {}),
        }
        parameter = DeviceLabRepository(self._db_path).save_parameter_set(
            project_id=project_id,
            board_id=scene.boardId,
            profile_revision=scene_profile(scene).revision,
            label=restored_parameter_request["label"],
            values=restored_parameter_request["values"],
            idempotency_key=f"creator-m7-params-{project_id}",
            request_hash=_hash_json(restored_parameter_request),
        )
        old_artifact = str(code.get("artifactId") or "")
        old_version = str(code.get("artifactVersionId") or "")
        new_artifact = artifact_map["artifacts"].get(old_artifact)
        new_version = artifact_map["artifactVersions"].get(old_version)
        files = code.get("files")
        patch = code.get("patch")
        if (
            not new_artifact
            or not new_version
            or not isinstance(files, list)
            or not files
            or not isinstance(patch, dict)
        ):
            raise CreatorError(
                "CREATOR_DELIVERY_CODE_RESTORE_FAILED",
                "导入包中的代码产物或源码映射不完整。",
                status_code=422,
            )
        code_id = f"code_imported_{uuid.uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO code_runs (
                  id, project_id, spec_run_id, version, status, runtime, entrypoint,
                  workspace_root, max_retries, retries, test_result_json,
                  artifact_id, artifact_version_id, hardware_solution_version,
                  bom_version, io_map_version, generated_by_expert_id, stale_reason,
                  created_at, updated_at, accepted_at
                ) VALUES (?, ?, NULL, 1, 'ACCEPTED', ?, ?, ?, 0, 0, ?, ?, ?,
                          NULL, NULL, NULL, NULL, NULL, ?, ?, ?)
                """,
                (
                    code_id,
                    project_id,
                    str(code.get("runtime") or "micropython"),
                    str(code.get("entrypoint") or "main.py"),
                    f"workspace://{project_id}/code/imported",
                    json.dumps(code.get("testResult") or {"ok": True}, ensure_ascii=False),
                    new_artifact,
                    new_version,
                    now,
                    now,
                    now,
                ),
            )
            for item in files:
                if not isinstance(item, dict):
                    raise CreatorError(
                        "CREATOR_DELIVERY_CODE_RESTORE_FAILED", "导入源码记录无效。"
                    )
                conn.execute(
                    """
                    INSERT INTO code_files (
                      id, code_run_id, project_id, kind, path, language, content, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"code_file_imported_{uuid.uuid4().hex}",
                        code_id,
                        project_id,
                        str(item.get("kind") or "SOURCE"),
                        str(item.get("path") or ""),
                        str(item.get("language") or "python"),
                        str(item.get("content") or ""),
                        now,
                    ),
                )
            conn.execute(
                """
                INSERT INTO code_patches (
                  id, code_run_id, project_id, base_snapshot_id, summary, diff, created_at
                ) VALUES (?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    f"patch_imported_{uuid.uuid4().hex}",
                    code_id,
                    project_id,
                    str(patch.get("summary") or "导入代码"),
                    str(patch.get("diff") or ""),
                    now,
                ),
            )
        result = {
            **artifact_map,
            "scenes": {
                str((materials.get("digitalPrototype") or {}).get("sceneRevision") or ""):
                    scene.revision
            },
            "parameterSets": {
                str(parameters.get("parameterSetId") or ""): parameter.id
            },
            "codeRuns": {str(code.get("codeRunId") or ""): code_id},
            "solutions": {
                str(materials.get("currentSolutionRevisionId") or ""):
                    workspace.current_solution.id
            },
        }
        structure = materials.get("structure")
        if isinstance(structure, dict) and structure.get("required") is True:
            old_cad_artifact = str(structure.get("artifactId") or "")
            old_cad_version = str(structure.get("artifactVersionId") or "")
            cad_artifact = artifact_map["artifacts"].get(old_cad_artifact)
            cad_version = artifact_map["artifactVersions"].get(old_cad_version)
            if not cad_artifact or not cad_version:
                raise CreatorError(
                    "CREATOR_DELIVERY_STRUCTURE_RESTORE_FAILED",
                    "导入包缺少要求的结构产物。",
                    status_code=422,
                )
            job_id = f"tool_job_imported_{uuid.uuid4().hex}"
            cad_id = f"cad_imported_{uuid.uuid4().hex}"
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO tool_jobs (
                      id, project_id, kind, status, request_hash, request_json,
                      host_lease_id, progress, result_artifact_ids_json, error_json,
                      created_at, updated_at, result_json
                    ) VALUES (?, ?, 'CAD_INTENT', 'SUCCEEDED', ?, '{}', NULL, 100,
                              ?, NULL, ?, ?, '{}')
                    """,
                    (
                        job_id, project_id, _hash_json(structure),
                        json.dumps([cad_artifact]), now, now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO cad_intent_revisions (
                      id, project_id, parent_revision_id, tool_job_id, change_set_id,
                      project_version_id, intent_summary, route_action, status,
                      source_storage_key, base_source_sha256, source_sha256,
                      pending_patch_json, object_index_json, artifact_id,
                      artifact_version_id, created_at, confirmed_at
                    ) VALUES (?, ?, NULL, ?, NULL, NULL, ?, 'IMPORT', 'CONFIRMED',
                              NULL, NULL, NULL, NULL, '[]', ?, ?, ?, ?)
                    """,
                    (
                        cad_id, project_id, job_id, "导入结构版本",
                        cad_artifact, cad_version, now, now,
                    ),
                )
            result["cadRevisions"] = {
                str(structure.get("revisionId") or ""): cad_id
            }
        return result

    def _delivery_materials(
        self,
        project_id: str,
        workspace: CreatorWorkspace,
    ) -> dict[str, Any]:
        """Collect and revalidate the current, reproducible delivery boundary."""

        goal = workspace.current_goal
        solution = workspace.current_solution
        assert goal is not None and solution is not None
        current = {
            item.kind: item
            for item in workspace.evidence
            if item.status.value == "CURRENT" and item.passed
        }
        required = {
            EvidenceKind.STATIC_VALIDATION,
            EvidenceKind.SIMULATION,
            EvidenceKind.DEVICE_CONNECTION,
            EvidenceKind.DEPLOYMENT,
            EvidenceKind.PHYSICAL_BEHAVIOR,
            EvidenceKind.USER_ACCEPTANCE,
        }
        structure_required = _structure_required(solution.structure)
        if structure_required:
            required.add(EvidenceKind.STRUCTURE_CHECK)
        missing = [
            f"evidence:{kind.value}"
            for kind in sorted(required - set(current), key=lambda item: item.value)
        ]
        if missing:
            _raise_incomplete(missing)

        with self._connect() as conn:
            scene = conn.execute(
                """
                SELECT revision, board_id, scene_json FROM device_lab_scenes
                WHERE project_id = ? ORDER BY created_at DESC, revision DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            code = conn.execute(
                """
                SELECT c.id, c.version, c.artifact_id, c.artifact_version_id,
                       c.runtime, c.entrypoint, c.test_result_json,
                       a.current_version_id, av.status AS artifact_status
                FROM code_runs AS c
                LEFT JOIN artifacts AS a
                  ON a.id = c.artifact_id AND a.project_id = c.project_id
                LEFT JOIN artifact_versions AS av
                  ON av.id = c.artifact_version_id
                 AND av.artifact_id = c.artifact_id
                 AND av.project_id = c.project_id
                WHERE c.project_id = ? AND c.status = 'ACCEPTED'
                ORDER BY c.version DESC, c.updated_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            parameter = conn.execute(
                """
                SELECT id, board_id, profile_revision, revision, label, values_json
                FROM device_parameter_sets
                WHERE project_id = ? ORDER BY revision DESC, created_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()

            if scene is None:
                missing.append("digitalPrototype")
            if (
                code is None
                or not code["artifact_id"]
                or not code["artifact_version_id"]
                or str(code["current_version_id"]) != str(code["artifact_version_id"])
                or str(code["artifact_status"]) != "APPROVED"
            ):
                missing.append("acceptedCodeArtifact")
            if parameter is None:
                missing.append("parameterSet")
            if missing:
                _raise_incomplete(missing)
            assert scene is not None and code is not None and parameter is not None
            code_files = conn.execute(
                "SELECT kind, path, language, content FROM code_files "
                "WHERE project_id = ? AND code_run_id = ? ORDER BY path",
                (project_id, str(code["id"])),
            ).fetchall()
            code_patch = conn.execute(
                "SELECT summary, diff FROM code_patches "
                "WHERE project_id = ? AND code_run_id = ?",
                (project_id, str(code["id"])),
            ).fetchone()
            if not code_files or code_patch is None:
                _raise_incomplete(["acceptedCodeSource"])

            scene_data = _json_object(str(scene["scene_json"]), "digital prototype")
            binding = scene_data.get("binding")
            source = scene_data.get("source")
            bound_solution_id = (
                str(binding.get("solutionRevisionId", ""))
                if isinstance(binding, dict)
                else ""
            ) or (
                str(source.get("proposalId", ""))
                if isinstance(source, dict)
                else ""
            )
            if bound_solution_id != solution.id:
                _raise_incomplete(["digitalPrototype:currentSolution"])
            if str(parameter["board_id"]) != str(scene["board_id"]):
                _raise_incomplete(["parameterSet:devicePackage"])

            structure: dict[str, Any] = {"required": structure_required}
            if structure_required:
                structure_evidence = current[EvidenceKind.STRUCTURE_CHECK]
                structure_row = conn.execute(
                    """
                    SELECT id, artifact_id, artifact_version_id
                    FROM cad_intent_revisions
                    WHERE id = ? AND project_id = ? AND status = 'CONFIRMED'
                    """,
                    (structure_evidence.source_id, project_id),
                ).fetchone()
                if (
                    structure_row is None
                    or not structure_row["artifact_id"]
                    or not structure_row["artifact_version_id"]
                ):
                    _raise_incomplete(["structureArtifact"])
                structure = {
                    "required": True,
                    "revisionId": str(structure_row["id"]),
                    "artifactId": str(structure_row["artifact_id"]),
                    "artifactVersionId": str(structure_row["artifact_version_id"]),
                }

            for kind, command in (
                (EvidenceKind.STATIC_VALIDATION, CreatorCommand.RECORD_STATIC_VALIDATION),
                (EvidenceKind.SIMULATION, CreatorCommand.RECORD_SIMULATION),
                (EvidenceKind.DEVICE_CONNECTION, CreatorCommand.RECORD_DEVICE_CONNECTION),
                (EvidenceKind.DEPLOYMENT, CreatorCommand.RECORD_DEPLOYMENT),
                (EvidenceKind.PHYSICAL_BEHAVIOR, CreatorCommand.RECORD_PHYSICAL_BEHAVIOR),
                *(
                    (
                        (
                            EvidenceKind.STRUCTURE_CHECK,
                            CreatorCommand.RECORD_STRUCTURE_CHECK,
                        ),
                    )
                    if structure_required
                    else ()
                ),
            ):
                evidence = current[kind]
                try:
                    self._creator.validate_command_source(
                        project_id,
                        command,
                        {
                            "passed": True,
                            "summary": evidence.summary,
                            "sourceId": evidence.source_id,
                            "bindings": evidence.bindings,
                        },
                    )
                except CreatorError as exc:
                    raise CreatorError(
                        "CREATOR_DELIVERY_SOURCE_INVALID",
                        f"交付材料 {kind.value} 的本地来源已不可复核：{exc.message}",
                        status_code=409,
                    ) from exc

            expected_bindings = {
                "solutionRevisionId": solution.id,
                "sceneRevision": str(scene["revision"]),
                "codeRevisionId": str(code["id"]),
                "parameterRevisionId": str(parameter["id"]),
            }
            bound_kinds = (
                EvidenceKind.SIMULATION,
                EvidenceKind.DEVICE_CONNECTION,
                EvidenceKind.DEPLOYMENT,
                EvidenceKind.PHYSICAL_BEHAVIOR,
                EvidenceKind.USER_ACCEPTANCE,
            )
            mismatches = [
                f"{kind.value}:{key}"
                for kind in bound_kinds
                for key, value in expected_bindings.items()
                if current[kind].bindings.get(key) != value
            ]
            if current[EvidenceKind.STATIC_VALIDATION].bindings.get(
                "sceneRevision"
            ) != str(scene["revision"]):
                mismatches.append("STATIC_VALIDATION:sceneRevision")
            if structure_required:
                structure_id = str(structure["revisionId"])
                for kind in (
                    EvidenceKind.STRUCTURE_CHECK,
                    EvidenceKind.PHYSICAL_BEHAVIOR,
                    EvidenceKind.USER_ACCEPTANCE,
                ):
                    if current[kind].bindings.get("structureRevisionId") != structure_id:
                        mismatches.append(f"{kind.value}:structureRevisionId")
            if mismatches:
                _raise_incomplete(mismatches)

            acceptance = current[EvidenceKind.USER_ACCEPTANCE]
            actor = str(acceptance.bindings.get("actor", "")).strip()
            actor_subject = str(
                acceptance.bindings.get("actorSubject", "")
            ).strip()
            if not actor or not actor_subject or _is_system_actor(actor):
                _raise_incomplete(["userAcceptance:humanActor"])

            deployment = current[EvidenceKind.DEPLOYMENT]
            operation = conn.execute(
                """
                SELECT log FROM device_operations
                WHERE id = ? AND project_id = ?
                """,
                (deployment.source_id, project_id),
            ).fetchone()
            operation_state = (
                _json_object(str(operation["log"]), "deployment operation")
                if operation is not None
                else {}
            )
            metadata = operation_state.get("metadata")
            if (
                not isinstance(metadata, dict)
                or str(metadata.get("codeRunId", "")) != str(code["id"])
            ):
                _raise_incomplete(["deployment:acceptedCode"])

        device_packages = [
            {"id": str(scene["board_id"]), "version": "proxy-v1"}
        ]
        version_bindings = {
            "goalRevisionId": goal.id,
            "solutionRevisionId": solution.id,
            "creatorProjectVersion": str(workspace.project_version),
            "sceneRevision": str(scene["revision"]),
            "codeRunId": str(code["id"]),
            "codeVersion": str(code["version"]),
            "codeArtifactId": str(code["artifact_id"]),
            "codeArtifactVersionId": str(code["artifact_version_id"]),
            "parameterSetId": str(parameter["id"]),
            "parameterRevision": str(parameter["revision"]),
        }
        if structure_required:
            version_bindings["structureRevisionId"] = str(structure["revisionId"])

        proof = {
            _proof_key(kind): _evidence_material(current[kind])
            for kind in (
                EvidenceKind.SIMULATION,
                EvidenceKind.DEVICE_CONNECTION,
                EvidenceKind.DEPLOYMENT,
                EvidenceKind.PHYSICAL_BEHAVIOR,
                EvidenceKind.USER_ACCEPTANCE,
            )
        }
        materials: dict[str, Any] = {
            "schemaVersion": 1,
            "currentSolutionRevisionId": solution.id,
            "devicePackages": device_packages,
            "versionBindings": version_bindings,
            "digitalPrototype": {
                "sceneRevision": str(scene["revision"]),
                "boardId": str(scene["board_id"]),
            },
            "code": {
                "codeRunId": str(code["id"]),
                "version": int(code["version"]),
                "artifactId": str(code["artifact_id"]),
                "artifactVersionId": str(code["artifact_version_id"]),
                "runtime": str(code["runtime"]),
                "entrypoint": str(code["entrypoint"]),
                "testResult": json.loads(str(code["test_result_json"])),
                "patch": {
                    "summary": str(code_patch["summary"]),
                    "diff": str(code_patch["diff"]),
                },
                "files": [
                    {
                        "kind": str(item["kind"]),
                        "path": str(item["path"]),
                        "language": str(item["language"]),
                        "content": str(item["content"]),
                    }
                    for item in code_files
                ],
            },
            "parameters": {
                "parameterSetId": str(parameter["id"]),
                "boardId": str(parameter["board_id"]),
                "profileRevision": str(parameter["profile_revision"]),
                "revision": int(parameter["revision"]),
                "label": str(parameter["label"]),
                "values": _json_object(str(parameter["values_json"]), "parameter set"),
            },
            "structure": structure,
            "proof": proof,
        }
        materials["maturity"] = _derive_maturity(
            workspace,
            scene_data,
            current,
        )
        return materials

    @staticmethod
    def _acceptance_identity(
        conn: sqlite3.Connection, project_id: str
    ) -> tuple[str | None, str | None]:
        row = conn.execute(
            """
            SELECT bindings_json FROM creator_evidence
            WHERE project_id = ? AND kind = 'USER_ACCEPTANCE'
              AND status = 'CURRENT' AND passed = 1
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None, None
        bindings = json.loads(str(row["bindings_json"]))
        actor = bindings.get("actor")
        subject = bindings.get("actorSubject")
        return (
            str(actor) if actor else None,
            str(subject) if subject else None,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _delivery_from_row(row: sqlite3.Row) -> CreatorDeliveryRecord:
        manifest = CreatorDeliveryManifestV1.model_validate_json(
            str(row["manifest_json"])
        )
        return CreatorDeliveryRecord(
            id=str(row["id"]),
            workId=str(row["project_id"]),
            variant=CreatorDeliveryVariant(str(row["variant"])),
            status="EXPORTED",
            title=str(row["title"]),
            fileName=str(row["file_name"] or f"{row['id']}.zwcreator.zip"),
            packageSha256=str(row["package_sha256"]),
            manifest=manifest,
            privacyReport=json.loads(str(row["privacy_report_json"])),
            zipBase64=str(row["zip_base64"]) if row["zip_base64"] else None,
            createdAt=str(row["created_at"]),
        )


def _current_evidence(workspace: CreatorWorkspace, kind: EvidenceKind):
    return next(
        (
            item
            for item in workspace.evidence
            if item.kind is kind and item.status.value == "CURRENT" and item.passed
        ),
        None,
    )


def _hash_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _project_artifact_map(
    archive: bytes, imported_project_id: str
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {
        "artifacts": {},
        "artifactVersions": {},
    }
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            manifest = json.loads(package.read("manifest.json").decode("utf-8"))
            entries = manifest.get("artifacts", [])
            if not isinstance(entries, list):
                raise ValueError
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    raise ValueError
                payload = json.loads(
                    package.read(str(entry["path"])).decode("utf-8")
                )
                artifact = payload["artifact"]
                version = payload["version"]
                result["artifacts"][str(artifact["id"])] = (
                    f"artifact_imported_{imported_project_id}_{index}"
                )
                result["artifactVersions"][str(version["id"])] = (
                    f"artifact_version_imported_{imported_project_id}_{index}"
                )
    except (KeyError, TypeError, ValueError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise CreatorError(
            "CREATOR_DELIVERY_ARTIFACT_MAP_INVALID",
            "底层项目包缺少可验证的产物映射。",
            status_code=422,
        ) from exc
    return result


def _selection(variant: CreatorDeliveryVariant) -> ProjectPackageArtifactSelectionPatch:
    if variant is CreatorDeliveryVariant.SHARE:
        return ProjectPackageArtifactSelectionPatch(
            includeDocuments=True,
            includeCode=False,
            includeCad=True,
            includeLessons=True,
            includeDeviceLogs=False,
        )
    return ProjectPackageArtifactSelectionPatch(
        includeDocuments=True,
        includeCode=True,
        includeCad=True,
        includeLessons=True,
        includeDeviceLogs=False,
    )


def _sanitized_workspace(
    workspace: CreatorWorkspace,
    variant: CreatorDeliveryVariant,
    materials: dict[str, Any],
) -> dict[str, Any]:
    goal = workspace.current_goal
    solution = workspace.current_solution
    assert goal is not None and solution is not None
    exported_materials = json.loads(json.dumps(materials, ensure_ascii=False))
    exported_materials.pop("maturity", None)
    if variant is CreatorDeliveryVariant.TEMPLATE:
        exported_materials.pop("proof", None)
    return {
        "schemaVersion": 1,
        "variant": variant.value,
        "name": workspace.name,
        "initialIdea": workspace.initial_idea,
        "goal": goal.model_dump(
            mode="json",
            by_alias=True,
            exclude={"id", "work_id", "revision", "status", "created_at", "confirmed_at"},
        ),
        "solution": solution.model_dump(
            mode="json",
            by_alias=True,
            exclude={"id", "work_id", "revision", "status", "created_at", "confirmed_at"},
        ),
        "acceptanceScenarios": [
            {
                "title": item.title,
                "required": item.required,
                "simulationExpected": item.simulation_expected,
                "physicalExpected": item.physical_expected,
            }
            for item in workspace.acceptance_scenarios
        ],
        "selectedHardwareIds": [item.component_id for item in solution.bom],
        "deliveryMaterials": exported_materials,
        "importVerificationPolicy": "RESET_AND_REVERIFY",
    }


def _sanitized_evidence(
    workspace: CreatorWorkspace, variant: CreatorDeliveryVariant
) -> list[dict[str, Any]]:
    if variant is CreatorDeliveryVariant.TEMPLATE:
        return []
    return [
        item.model_copy(update={"source_id": None, "bindings": {}}).model_dump(
            mode="json", by_alias=True
        )
        for item in workspace.evidence
        if item.status.value == "CURRENT" and item.passed
    ]


def _reproduction_guide(
    workspace: CreatorWorkspace, variant: CreatorDeliveryVariant
) -> str:
    scenario_lines = "\n".join(
        f"- {item.title}：仿真 {item.simulation_expected}；真机 {item.physical_expected}"
        for item in workspace.acceptance_scenarios
    )
    return (
        f"# {workspace.name} · {variant.value}\n\n"
        "导入后验证等级会重置，不继承原作者的仿真、设备或真机通过状态。\n\n"
        "## 复现顺序\n\n"
        "1. 检查目标、BOM、IO、供电、代码产物、参数版本和设备包版本。\n"
        "2. 有结构要求时复核 GLB、STL、STEP 和 manifest，再重新建立数字原型。\n"
        "3. 独立完成全部必需仿真场景；不得继承原作品的通过状态。\n"
        "4. 在明确确认点后连接设备、部署并回读。\n"
        "5. 由导入包的第二测试用户逐项观察真机行为并明确验收。\n\n"
        f"## 验收场景\n\n{scenario_lines}\n"
    )


def _validate_delivery_snapshot(
    manifest: CreatorDeliveryManifestV1,
    workspace: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> None:
    if workspace.get("variant") != manifest.variant.value:
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品快照与 manifest 的交付变体不一致。",
            status_code=422,
        )
    materials = workspace.get("deliveryMaterials")
    if not isinstance(materials, dict):
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包缺少可复核的代码、参数和验证材料。",
            status_code=422,
        )
    required_sections = {
        "digitalPrototype",
        "code",
        "parameters",
        "structure",
        "versionBindings",
    }
    if not required_sections.issubset(materials):
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包交付材料不完整。",
            status_code=422,
        )
    if materials.get("currentSolutionRevisionId") != manifest.solution_revision_id:
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包交付材料没有绑定 manifest 的当前方案。",
            status_code=422,
        )
    bindings = materials.get("versionBindings")
    if not isinstance(bindings, dict) or any(
        str(bindings.get(key, "")) != value
        for key, value in manifest.version_bindings.items()
    ):
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包材料版本与 manifest 不一致。",
            status_code=422,
        )
    structure = materials.get("structure")
    if not isinstance(structure, dict) or (
        structure.get("required") is True
        and not {
            "revisionId",
            "artifactId",
            "artifactVersionId",
        }.issubset(structure)
    ):
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包结构材料不完整。",
            status_code=422,
        )

    declared = {item.value for item in manifest.evidence_kinds}
    actual = {
        str(item.get("kind"))
        for item in evidence
        if isinstance(item, dict)
    }
    if declared != actual:
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包证据摘要与 manifest 不一致。",
            status_code=422,
        )
    if manifest.variant is CreatorDeliveryVariant.TEMPLATE:
        if evidence or "proof" in materials:
            raise CreatorError(
                "CREATOR_DELIVERY_SNAPSHOT_INVALID",
                "模板包不得继承原作品的验证证据。",
                status_code=422,
            )
        return
    required_evidence = {
        EvidenceKind.STATIC_VALIDATION.value,
        EvidenceKind.SIMULATION.value,
        EvidenceKind.DEVICE_CONNECTION.value,
        EvidenceKind.DEPLOYMENT.value,
        EvidenceKind.PHYSICAL_BEHAVIOR.value,
        EvidenceKind.USER_ACCEPTANCE.value,
    }
    proof = materials.get("proof")
    if (
        not required_evidence.issubset(actual)
        or not isinstance(proof, dict)
        or not {
            "simulation",
            "deviceConnection",
            "deployment",
            "physicalBehavior",
            "userAcceptance",
        }.issubset(proof)
    ):
        raise CreatorError(
            "CREATOR_DELIVERY_SNAPSHOT_INVALID",
            "作品包缺少完整的仿真、设备、真机或用户验收材料。",
            status_code=422,
        )


def _derive_maturity(
    workspace: CreatorWorkspace,
    scene_data: dict[str, Any],
    current_evidence: dict[EvidenceKind, Any],
) -> dict[str, str]:
    """Declare only capabilities exercised by this solution and its evidence."""

    solution = workspace.current_solution
    assert solution is not None
    scene = DeviceLabSceneV1.model_validate(scene_data)
    profile = scene_profile(scene)
    corpus = " ".join(
        [
            solution.summary,
            solution.logic,
            solution.hardware,
            solution.software,
            solution.simulation,
            *(item.title for item in workspace.acceptance_scenarios),
            *(item.simulation_expected for item in workspace.acceptance_scenarios),
            *(item.physical_expected for item in workspace.acceptance_scenarios),
            *(item.signal for item in solution.io_map),
            *(item.purpose for item in solution.io_map),
        ]
    ).casefold()
    maturity: dict[str, str] = {}
    has_simulation = all(
        kind in current_evidence
        for kind in (
            EvidenceKind.STATIC_VALIDATION,
            EvidenceKind.SIMULATION,
        )
    )
    sensing_relevant = _contains_any(
        corpus,
        (
            "传感",
            "采样",
            "监测",
            "检测",
            "温度",
            "湿度",
            "光照",
            "按键",
            "sensor",
            "detect",
            "monitor",
        ),
    )
    has_sensor_capability = any(
        item.kind in {"sensor-input", "telemetry"} for item in profile.channels
    )
    if sensing_relevant and has_sensor_capability and has_simulation:
        maturity["sensing"] = "MVP"

    response_relevant = _contains_any(
        corpus,
        (
            "控制",
            "点亮",
            "关闭",
            "输出",
            "提醒",
            "执行",
            "电机",
            "rgb",
            "led",
            "actuator",
            "motor",
        ),
    )
    has_actuator_capability = any(item.kind == "actuator" for item in profile.channels)
    has_physical_acceptance = all(
        kind in current_evidence
        for kind in (
            EvidenceKind.DEPLOYMENT,
            EvidenceKind.PHYSICAL_BEHAVIOR,
            EvidenceKind.USER_ACCEPTANCE,
        )
    )
    if response_relevant and has_actuator_capability and has_physical_acceptance:
        maturity["responsiveExecution"] = "CONTROLLED_BETA"

    vision_audio_relevant = _contains_any(
        corpus,
        (
            "视觉",
            "图像",
            "摄像",
            "相机",
            "音频",
            "语音",
            "麦克风",
            "扬声器",
            "camera",
            "vision",
            "image",
            "audio",
            "microphone",
            "speaker",
        ),
    )
    board_peripherals = " ".join(
        BOARDS[scene.boardId].peripherals
    ).casefold()
    has_vision_audio_capability = _contains_any(
        board_peripherals,
        (
            "camera",
            "microphone",
            "speaker",
            "摄像",
            "麦克风",
            "扬声器",
        ),
    )
    if vision_audio_relevant and has_vision_audio_capability and has_simulation:
        maturity["visionAudio"] = "TECH_PREVIEW"
    return maturity


def _evidence_material(evidence: Any) -> dict[str, Any]:
    return {
        "kind": evidence.kind.value,
        "summary": evidence.summary,
        "recordedAt": evidence.recorded_at,
        "solutionRevisionId": evidence.bindings.get("solutionRevisionId"),
    }


def _proof_key(kind: EvidenceKind) -> str:
    return {
        EvidenceKind.SIMULATION: "simulation",
        EvidenceKind.DEVICE_CONNECTION: "deviceConnection",
        EvidenceKind.DEPLOYMENT: "deployment",
        EvidenceKind.PHYSICAL_BEHAVIOR: "physicalBehavior",
        EvidenceKind.USER_ACCEPTANCE: "userAcceptance",
    }[kind]


def _structure_required(value: str) -> bool:
    return value.strip() not in {"", "不需要结构", "不适用"}


def _is_system_actor(value: str) -> bool:
    return value.strip().casefold() in {
        "system",
        "ai",
        "model",
        "assistant",
        "掌问",
    }


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _raise_incomplete(items: list[str]) -> None:
    detail = "、".join(sorted(set(items)))
    raise CreatorError(
        "CREATOR_DELIVERY_INCOMPLETE",
        f"作品尚未形成完整可复现交付材料：{detail}",
        status_code=409,
    )


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CreatorError(
            "CREATOR_DELIVERY_MATERIAL_INVALID",
            f"{label} 不是有效 JSON。",
            status_code=409,
        ) from exc
    if not isinstance(value, dict):
        raise CreatorError(
            "CREATOR_DELIVERY_MATERIAL_INVALID",
            f"{label} 必须是 JSON 对象。",
            status_code=409,
        )
    return value


def _load_manifest(files: dict[str, bytes]) -> CreatorDeliveryManifestV1:
    try:
        return CreatorDeliveryManifestV1.model_validate(_load_json(files, "manifest.json"))
    except Exception as exc:
        raise CreatorError(
            "CREATOR_DELIVERY_MANIFEST_INVALID",
            "Creator 交付包 manifest 无效。",
            status_code=422,
        ) from exc


def _validate_manifest_files(
    manifest: CreatorDeliveryManifestV1, files: dict[str, bytes]
) -> None:
    expected = {item.path for item in manifest.files}
    actual = set(files) - {"manifest.json"}
    if expected != actual or len(expected) != len(manifest.files):
        raise CreatorError(
            "CREATOR_DELIVERY_FILE_SET_MISMATCH",
            "Creator 交付包文件集合与 manifest 不一致。",
            status_code=422,
        )
    for item in manifest.files:
        content = files[item.path]
        if len(content) != item.byte_size or hashlib.sha256(content).hexdigest() != item.sha256:
            raise CreatorError(
                "CREATOR_DELIVERY_HASH_MISMATCH",
                f"Creator 交付包文件校验失败：{item.path}",
                status_code=422,
            )


def _decode_base64(value: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise CreatorError(
            "CREATOR_DELIVERY_BASE64_INVALID", "作品包不是有效 base64。", status_code=422
        ) from exc
    if len(raw) > MAX_CREATOR_DELIVERY_BYTES:
        raise CreatorError(
            "CREATOR_DELIVERY_TOO_LARGE", "作品包超过大小上限。", status_code=422
        )
    return raw


def _read_delivery_zip(raw: bytes) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_CREATOR_DELIVERY_MEMBERS:
                raise CreatorError("CREATOR_DELIVERY_TOO_MANY_FILES", "作品包文件过多。", status_code=422)
            total = 0
            for info in members:
                _validate_member(info)
                if info.filename in files:
                    raise CreatorError(
                        "CREATOR_DELIVERY_DUPLICATE_PATH",
                        "作品包包含重复路径。",
                        status_code=422,
                    )
                total += info.file_size
                if info.file_size > MAX_CREATOR_DELIVERY_FILE_BYTES or total > MAX_CREATOR_DELIVERY_BYTES:
                    raise CreatorError("CREATOR_DELIVERY_TOO_LARGE", "作品包解压大小超限。", status_code=422)
                content = archive.read(info)
                if len(content) != info.file_size:
                    raise CreatorError("CREATOR_DELIVERY_ZIP_INVALID", "作品包条目大小异常。", status_code=422)
                files[info.filename] = content
    except CreatorError:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise CreatorError("CREATOR_DELIVERY_ZIP_INVALID", "作品包 ZIP 无法读取。", status_code=422) from exc
    return files


def _validate_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    allowed = {
        "manifest.json",
        "privacy_report.json",
        "creator/workspace.json",
        "creator/evidence.json",
        "creator/reproduction-guide.md",
        "payload/project-package.zip",
    }
    if (
        info.is_dir()
        or info.flag_bits & 0x1
        or info.filename not in allowed
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in info.filename
        or stat.S_IFMT((info.external_attr >> 16) & 0xFFFF) == stat.S_IFLNK
    ):
        raise CreatorError(
            "CREATOR_DELIVERY_UNSAFE_ZIP", "作品包包含未知或不安全路径。", status_code=422
        )


def _zip_payloads(payloads: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in sorted(payloads.items()):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def _load_json(files: dict[str, bytes], path: str) -> dict[str, Any]:
    try:
        value = json.loads(files[path].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreatorError(
            "CREATOR_DELIVERY_JSON_INVALID", f"作品包缺少或损坏：{path}", status_code=422
        ) from exc
    if not isinstance(value, dict):
        raise CreatorError(
            "CREATOR_DELIVERY_JSON_INVALID", f"作品包 JSON 结构无效：{path}", status_code=422
        )
    return value


def _load_json_list(files: dict[str, bytes], path: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(files[path].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreatorError(
            "CREATOR_DELIVERY_JSON_INVALID",
            f"作品包缺少或损坏：{path}",
            status_code=422,
        ) from exc
    if not isinstance(value, list) or not all(
        isinstance(item, dict) for item in value
    ):
        raise CreatorError(
            "CREATOR_DELIVERY_JSON_INVALID",
            f"作品包 JSON 结构无效：{path}",
            status_code=422,
        )
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _default_title(name: str, variant: CreatorDeliveryVariant) -> str:
    labels = {
        CreatorDeliveryVariant.SHARE: "查看分享包",
        CreatorDeliveryVariant.REPRODUCIBLE: "可复现项目包",
        CreatorDeliveryVariant.TEMPLATE: "创作模板包",
    }
    return f"{name} · {labels[variant]}"


def _safe_file_stem(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_" else "-" for character in value)
    return cleaned.strip("-")[:64] or "creator-work"


def _now() -> str:
    return datetime.now(UTC).isoformat()
