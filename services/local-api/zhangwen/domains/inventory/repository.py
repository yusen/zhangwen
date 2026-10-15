"""Same-database repository for device facts, inventory, and work bindings."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from zhangwen.auth.context import current_owner_subject
from zhangwen.devices.models import DeviceDeploymentChannel
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.inventory.models import (
    DeviceIdentityStatus,
    DeviceOperationRevisionPin,
    DevicePlatformConflictError,
    DevicePlatformNotFoundError,
    DevicePlatformValidationError,
    DeviceRecoveryStatus,
    DeviceTechnicalFact,
    DeviceTechnicalFactClass,
    InventoryItem,
    InventoryItemStatus,
    WorkDeviceBinding,
)
from zhangwen.domains.orchestration.models import (
    ExecutionRevisionBinding,
    ExecutionRevisionSet,
    PackageKind,
)
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.projects.repository import ProjectRepository


_LOCAL_OWNER = "__local__"
_SYSTEM_OWNER = "__system__"
_BOARD_COMPONENT_IDS = {
    "hw_seed_unihiker_k10": "dfrobot/dfrobot_k10",
    "hw_seeed_xiao_esp32s3_sense": "seeedstudio/xiao_esp32s3_sense",
}


class DevicePlatformRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        owner_subject: str | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._projects = ProjectRepository(self._data_dir)
        self._db_path = self._projects.db_path
        subject = owner_subject if owner_subject is not None else current_owner_subject()
        self._owner_subject = subject
        self._owner_key = subject or _LOCAL_OWNER
        self._events = RealtimeEventStore(self._db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def ensure_device_packages(self) -> None:
        PackagePlatformRepository(
            self._data_dir,
            owner_subject=self._owner_subject,
        ).ensure_legacy_packages()

    def list_device_facts(self) -> list[DeviceTechnicalFact]:
        self.ensure_device_packages()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.manifest_json, r.files_json
                FROM capability_packages AS p
                JOIN package_revisions AS r ON r.id = p.stable_revision_id
                WHERE p.kind = 'DEVICE_PACKAGE'
                  AND p.owner_key IN (?, ?)
                ORDER BY p.display_name, p.id
                """,
                (_SYSTEM_OWNER, self._owner_key),
            ).fetchall()
        return [_technical_fact(row) for row in rows]

    def get_device_fact(self, package_id: str) -> DeviceTechnicalFact:
        self.ensure_device_packages()
        with self._connect() as conn:
            row = self._device_package_row(conn, package_id)
        return _technical_fact(row)

    def get_board_fact(self, board_key: str) -> DeviceTechnicalFact:
        """Resolve a board source key without inferring or hard-coding a product board."""

        self.ensure_device_packages()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT p.*, r.manifest_json, r.files_json
                FROM capability_packages AS p
                JOIN package_revisions AS r ON r.id = p.stable_revision_id
                WHERE p.kind = 'DEVICE_PACKAGE'
                  AND p.source_type = 'DEVICE_BOARD' AND p.source_key = ?
                  AND p.owner_key IN (?, ?)
                LIMIT 1
                """,
                (board_key, _SYSTEM_OWNER, self._owner_key),
            ).fetchone()
        if row is None:
            raise DevicePlatformNotFoundError("设备板型没有可用的稳定技术包。")
        return _technical_fact(row)

    def list_inventory(self) -> list[InventoryItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM inventory_items
                WHERE owner_key = ?
                ORDER BY status = 'RETIRED', updated_at DESC, id
                """,
                (self._owner_key,),
            ).fetchall()
        return [_inventory_from_row(row) for row in rows]

    def get_inventory_item(self, item_id: str) -> InventoryItem:
        with self._connect() as conn:
            return _inventory_from_row(self._inventory_row(conn, item_id))

    def create_inventory_item(
        self,
        *,
        device_package_id: str,
        display_name: str | None,
        quantity: int,
        price: float,
        location: str,
        notes: str,
        idempotency_key: str,
    ) -> InventoryItem:
        fact = self.get_device_fact(device_package_id)
        resolved_name = (display_name or fact.display_name).strip()
        if not resolved_name:
            raise DevicePlatformValidationError("设备名称不能为空。")
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM inventory_items
                WHERE owner_key = ? AND idempotency_key = ?
                """,
                (self._owner_key, idempotency_key),
            ).fetchone()
            if existing is not None:
                item = _inventory_from_row(existing)
                if (
                    item.device_package_id != device_package_id
                    or item.display_name != resolved_name
                    or item.quantity != quantity
                    or item.price != price
                    or item.location != location.strip()
                    or item.notes != notes.strip()
                ):
                    raise DevicePlatformConflictError(
                        "同一幂等键不能创建不同的库存记录。"
                    )
                return item
            item_id = _id("inventory")
            conn.execute(
                """
                INSERT INTO inventory_items (
                  id, owner_subject, owner_key, device_package_id, display_name,
                  quantity, status, price, location, notes,
                  last_connection_status, last_connected_at,
                  source_type, source_key, idempotency_key,
                  revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'AVAILABLE', ?, ?, ?, NULL, NULL,
                          NULL, NULL, ?, 1, ?, ?)
                """,
                (
                    item_id,
                    self._owner_subject,
                    self._owner_key,
                    device_package_id,
                    resolved_name,
                    quantity,
                    price,
                    location.strip(),
                    notes.strip(),
                    idempotency_key,
                    now,
                    now,
                ),
            )
            self._events.append_device_event(
                conn,
                device_id=item_id,
                device_revision=1,
                event_type="inventory.created",
                source_event_id=f"inventory:{item_id}:1",
                payload={"inventoryItemId": item_id, "naturalStatus": "已加入我的设备"},
            )
        return self.get_inventory_item(item_id)

    def update_inventory_item(
        self,
        item_id: str,
        *,
        expected_revision: int,
        changes: dict[str, object],
    ) -> InventoryItem:
        allowed = {
            "display_name": "display_name",
            "quantity": "quantity",
            "status": "status",
            "price": "price",
            "location": "location",
            "notes": "notes",
        }
        normalized = {key: value for key, value in changes.items() if key in allowed}
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._inventory_row(conn, item_id)
            if int(row["revision"]) != expected_revision:
                raise DevicePlatformConflictError("库存记录已经变化，请刷新后重试。")
            if not normalized:
                return _inventory_from_row(row)
            current = dict(row)
            for key, value in normalized.items():
                if key in {"display_name", "location", "notes"} and isinstance(value, str):
                    value = value.strip()
                if key == "display_name" and not value:
                    raise DevicePlatformValidationError("设备名称不能为空。")
                if isinstance(value, StrEnum):
                    value = value.value
                current[allowed[key]] = value
            next_revision = expected_revision + 1
            conn.execute(
                """
                UPDATE inventory_items
                SET display_name = ?, quantity = ?, status = ?, price = ?,
                    location = ?, notes = ?, revision = ?, updated_at = ?
                WHERE id = ? AND owner_key = ? AND revision = ?
                """,
                (
                    current["display_name"],
                    current["quantity"],
                    current["status"],
                    current["price"],
                    current["location"],
                    current["notes"],
                    next_revision,
                    now,
                    item_id,
                    self._owner_key,
                    expected_revision,
                ),
            )
            self._events.append_device_event(
                conn,
                device_id=item_id,
                device_revision=next_revision,
                event_type="inventory.updated",
                source_event_id=f"inventory:{item_id}:{next_revision}",
                payload={"inventoryItemId": item_id, "naturalStatus": "我的设备信息已更新"},
            )
        return self.get_inventory_item(item_id)

    def ensure_legacy_work_bindings(self, work_id: str) -> None:
        self.ensure_device_packages()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            fact_row = conn.execute(
                """
                SELECT value_json FROM project_shared_facts
                WHERE project_id = ?
                  AND COALESCE(key, field) = 'preferred_hardware'
                  AND status = 'confirmed'
                ORDER BY updated_at DESC, rowid DESC
                LIMIT 1
                """,
                (work_id,),
            ).fetchone()
            if fact_row is None:
                return
            value = _object(json.loads(str(fact_row["value_json"])))
            components = value.get("components")
            if not isinstance(components, list):
                return
            for component in components:
                if not isinstance(component, dict):
                    continue
                component_id = str(component.get("id") or "").strip()
                skill_name = str(component.get("skillName") or "").strip()
                if not component_id:
                    continue
                package_row = self._package_for_legacy_component(
                    conn,
                    component_id=component_id,
                    skill_name=skill_name,
                )
                if package_row is None or package_row["stable_revision_id"] is None:
                    continue
                source_key = component_id
                existing = conn.execute(
                    """
                    SELECT 1 FROM work_device_bindings
                    WHERE work_id = ? AND owner_key = ?
                      AND source_type = 'PREFERRED_HARDWARE' AND source_key = ?
                    """,
                    (work_id, self._owner_key, source_key),
                ).fetchone()
                if existing is not None:
                    continue
                self._insert_binding(
                    conn,
                    work_id=work_id,
                    inventory_item_id=None,
                    package_row=package_row,
                    deployment_channel=None,
                    source_type="PREFERRED_HARDWARE",
                    source_key=source_key,
                    idempotency_key=None,
                )

    def list_work_bindings(self, work_id: str) -> list[WorkDeviceBinding]:
        self.ensure_legacy_work_bindings(work_id)
        return self.list_existing_work_bindings(work_id)

    def list_existing_work_bindings(self, work_id: str) -> list[WorkDeviceBinding]:
        """Read bindings without triggering the one-way legacy adapter."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM work_device_bindings
                WHERE work_id = ? AND owner_key = ?
                ORDER BY created_at, id
                """,
                (work_id, self._owner_key),
            ).fetchall()
        return [_binding_from_row(row) for row in rows]

    def list_existing_work_summaries(
        self,
        work_id: str,
    ) -> list[tuple[str, str, str, bool]]:
        """Return the user-facing device projection without mutating legacy state."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT b.id, p.display_name, b.natural_status,
                       b.identity_status, b.recovery_status
                FROM work_device_bindings AS b
                JOIN capability_packages AS p ON p.id = b.device_package_id
                WHERE b.work_id = ? AND b.owner_key = ?
                ORDER BY b.created_at, b.id
                """,
                (work_id, self._owner_key),
            ).fetchall()
        return [
            (
                str(row["id"]),
                str(row["display_name"]),
                str(row["natural_status"]),
                row["identity_status"] == DeviceIdentityStatus.NEEDS_ATTENTION.value
                or row["recovery_status"]
                == DeviceRecoveryStatus.RECOVERY_REQUIRED.value,
            )
            for row in rows
        ]

    def get_work_binding(self, work_id: str, binding_id: str) -> WorkDeviceBinding:
        with self._connect() as conn:
            return _binding_from_row(self._binding_row(conn, work_id, binding_id))

    def create_work_binding(
        self,
        *,
        work_id: str,
        inventory_item_id: str | None,
        device_package_id: str | None,
        deployment_channel: DeviceDeploymentChannel | None,
        idempotency_key: str,
    ) -> WorkDeviceBinding:
        self.ensure_device_packages()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM work_device_bindings
                WHERE work_id = ? AND owner_key = ? AND idempotency_key = ?
                """,
                (work_id, self._owner_key, idempotency_key),
            ).fetchone()
            if existing is not None:
                binding = _binding_from_row(existing)
                requested_package = device_package_id
                if inventory_item_id is not None:
                    requested_package = str(
                        self._inventory_row(conn, inventory_item_id)["device_package_id"]
                    )
                if (
                    binding.inventory_item_id != inventory_item_id
                    or binding.device_package_id != requested_package
                    or binding.deployment_channel != deployment_channel
                ):
                    raise DevicePlatformConflictError(
                        "同一幂等键不能创建不同的作品设备绑定。"
                    )
                return binding
            if inventory_item_id is not None:
                inventory_row = self._inventory_row(conn, inventory_item_id)
                device_package_id = str(inventory_row["device_package_id"])
            assert device_package_id is not None
            package_row = self._device_package_row(conn, device_package_id)
            self._assert_channel_declared(conn, package_row, deployment_channel)
            binding_id = self._insert_binding(
                conn,
                work_id=work_id,
                inventory_item_id=inventory_item_id,
                package_row=package_row,
                deployment_channel=deployment_channel,
                source_type=None,
                source_key=None,
                idempotency_key=idempotency_key,
            )
        return self.get_work_binding(work_id, binding_id)

    def update_work_binding(
        self,
        work_id: str,
        binding_id: str,
        *,
        expected_revision: int,
        changes: dict[str, object],
    ) -> WorkDeviceBinding:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._binding_row(conn, work_id, binding_id)
            if int(row["revision"]) != expected_revision:
                raise DevicePlatformConflictError("作品设备绑定已经变化，请刷新后重试。")
            target_revision_id = str(
                changes.get("device_package_revision_id")
                or row["device_package_revision_id"]
            )
            revision_row = conn.execute(
                """
                SELECT * FROM package_revisions
                WHERE id = ? AND package_id = ? AND status = 'PUBLISHED'
                """,
                (target_revision_id, row["device_package_id"]),
            ).fetchone()
            if revision_row is None:
                raise DevicePlatformValidationError("目标设备包修订不存在或尚未发布。")
            channel = changes.get("deployment_channel", row["deployment_channel"])
            channel_value = channel.value if isinstance(channel, DeviceDeploymentChannel) else channel
            self._assert_revision_channel(revision_row, channel_value)
            runtime_revision_id = changes.get(
                "runtime_package_revision_id", row["runtime_package_revision_id"]
            )
            if runtime_revision_id:
                runtime_row = conn.execute(
                    """
                    SELECT 1 FROM package_revisions AS r
                    JOIN capability_packages AS p ON p.id = r.package_id
                    WHERE r.id = ? AND r.status = 'PUBLISHED'
                      AND p.kind = 'RUNTIME_PACKAGE'
                    """,
                    (runtime_revision_id,),
                ).fetchone()
                if runtime_row is None:
                    raise DevicePlatformValidationError("运行时修订不存在或类型不匹配。")
            io_config = changes.get("io_config")
            resolved_io = (
                _dump(io_config) if isinstance(io_config, dict) else str(row["io_config_json"])
            )
            code_variant_id = changes.get("code_variant_id", row["code_variant_id"])
            next_revision = expected_revision + 1
            natural_status = _binding_natural_status(channel_value)
            conn.execute(
                """
                UPDATE work_device_bindings
                SET device_package_revision_id = ?, deployment_channel = ?,
                    runtime_package_revision_id = ?, code_variant_id = ?,
                    io_config_json = ?, natural_status = ?, revision = ?, updated_at = ?
                WHERE id = ? AND work_id = ? AND owner_key = ? AND revision = ?
                """,
                (
                    target_revision_id,
                    channel_value,
                    runtime_revision_id,
                    code_variant_id,
                    resolved_io,
                    natural_status,
                    next_revision,
                    now,
                    binding_id,
                    work_id,
                    self._owner_key,
                    expected_revision,
                ),
            )
            self._append_binding_event(
                conn,
                binding_id=binding_id,
                work_id=work_id,
                revision=next_revision,
                event_type="device.binding-updated",
                natural_status=natural_status,
            )
        return self.get_work_binding(work_id, binding_id)

    def resolve_operation_pin(
        self,
        *,
        work_id: str,
        session_id: str,
        channel: DeviceDeploymentChannel,
    ) -> DeviceOperationRevisionPin:
        self.ensure_legacy_work_bindings(work_id)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            session = conn.execute(
                """
                SELECT board FROM device_sessions WHERE id = ? AND project_id = ?
                """,
                (session_id, work_id),
            ).fetchone()
            if session is None:
                raise DevicePlatformNotFoundError("设备会话不存在。")
            package_row = conn.execute(
                """
                SELECT * FROM capability_packages
                WHERE source_type = 'DEVICE_BOARD' AND source_key = ?
                  AND kind = 'DEVICE_PACKAGE'
                """,
                (str(session["board"]),),
            ).fetchone()
            if package_row is None or package_row["stable_revision_id"] is None:
                raise DevicePlatformValidationError("设备没有可固定的稳定技术包修订。")
            self._assert_channel_declared(conn, package_row, channel)
            binding_row = conn.execute(
                """
                SELECT * FROM work_device_bindings
                WHERE work_id = ? AND owner_key = ? AND device_package_id = ?
                ORDER BY inventory_item_id IS NULL, created_at, id
                LIMIT 1
                """,
                (work_id, self._owner_key, package_row["id"]),
            ).fetchone()
            if binding_row is None:
                binding_id = self._insert_binding(
                    conn,
                    work_id=work_id,
                    inventory_item_id=None,
                    package_row=package_row,
                    deployment_channel=channel,
                    source_type="DEVICE_SESSION_BOARD",
                    source_key=str(session["board"]),
                    idempotency_key=None,
                )
                binding_row = self._binding_row(conn, work_id, binding_id)
            elif binding_row["deployment_channel"] != channel.value:
                next_revision = int(binding_row["revision"]) + 1
                natural_status = _binding_natural_status(channel.value)
                conn.execute(
                    """
                    UPDATE work_device_bindings
                    SET deployment_channel = ?, natural_status = ?,
                        revision = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        channel.value,
                        natural_status,
                        next_revision,
                        now,
                        binding_row["id"],
                    ),
                )
                self._append_binding_event(
                    conn,
                    binding_id=str(binding_row["id"]),
                    work_id=work_id,
                    revision=next_revision,
                    event_type="device.channel-selected",
                    natural_status=natural_status,
                )
                binding_row = self._binding_row(conn, work_id, str(binding_row["id"]))
            package_revision_id = str(binding_row["device_package_revision_id"])
            self._assert_revision_channel(
                self._revision_row(conn, package_revision_id),
                channel.value,
            )
            bindings = [
                ExecutionRevisionBinding(
                    packageKind=PackageKind.DEVICE_PACKAGE,
                    packageId=str(binding_row["device_package_id"]),
                    packageRevisionId=package_revision_id,
                )
            ]
            runtime_revision_id = binding_row["runtime_package_revision_id"]
            if runtime_revision_id:
                runtime_package = conn.execute(
                    """
                    SELECT p.id FROM capability_packages AS p
                    JOIN package_revisions AS r ON r.package_id = p.id
                    WHERE r.id = ? AND p.kind = 'RUNTIME_PACKAGE'
                    """,
                    (runtime_revision_id,),
                ).fetchone()
                if runtime_package is None:
                    raise DevicePlatformValidationError("绑定的运行时修订已不可用。")
                bindings.append(
                    ExecutionRevisionBinding(
                        packageKind=PackageKind.RUNTIME_PACKAGE,
                        packageId=str(runtime_package["id"]),
                        packageRevisionId=str(runtime_revision_id),
                    )
                )
        return DeviceOperationRevisionPin(
            deviceBindingId=str(binding_row["id"]),
            executionRevisionSet=ExecutionRevisionSet(
                id=_id("revision_set_device"),
                bindings=bindings,
                createdAt=now,
            ),
        )

    def can_access_device_scope(self, device_id: str) -> bool:
        with self._connect() as conn:
            inventory = conn.execute(
                "SELECT 1 FROM inventory_items WHERE id = ? AND owner_key = ?",
                (device_id, self._owner_key),
            ).fetchone()
            if inventory is not None:
                return True
            binding = conn.execute(
                """
                SELECT 1 FROM work_device_bindings
                WHERE id = ? AND owner_key = ?
                """,
                (device_id, self._owner_key),
            ).fetchone()
            return binding is not None

    def _insert_binding(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        inventory_item_id: str | None,
        package_row: sqlite3.Row,
        deployment_channel: DeviceDeploymentChannel | None,
        source_type: str | None,
        source_key: str | None,
        idempotency_key: str | None,
    ) -> str:
        stable_revision_id = package_row["stable_revision_id"]
        if stable_revision_id is None:
            raise DevicePlatformValidationError("设备技术包还没有稳定修订。")
        self._assert_channel_declared(conn, package_row, deployment_channel)
        binding_id = _id("work_device")
        now = _now()
        natural_status = _binding_natural_status(
            deployment_channel.value if deployment_channel is not None else None
        )
        conn.execute(
            """
            INSERT INTO work_device_bindings (
              id, work_id, owner_key, inventory_item_id,
              device_package_id, device_package_revision_id,
              identity_status, deployment_channel, runtime_package_revision_id,
              code_variant_id, io_config_json, recovery_status, natural_status,
              source_type, source_key, idempotency_key,
              revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'NOT_CONNECTED', ?, NULL, NULL, '{}',
                      'READY', ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                binding_id,
                work_id,
                self._owner_key,
                inventory_item_id,
                package_row["id"],
                stable_revision_id,
                deployment_channel.value if deployment_channel is not None else None,
                natural_status,
                source_type,
                source_key,
                idempotency_key,
                now,
                now,
            ),
        )
        self._append_binding_event(
            conn,
            binding_id=binding_id,
            work_id=work_id,
            revision=1,
            event_type="device.binding-created",
            natural_status=natural_status,
        )
        return binding_id

    def _append_binding_event(
        self,
        conn: sqlite3.Connection,
        *,
        binding_id: str,
        work_id: str,
        revision: int,
        event_type: str,
        natural_status: str,
    ) -> None:
        source = f"{event_type}:{binding_id}:{revision}"
        payload = {"deviceBindingId": binding_id, "naturalStatus": natural_status}
        self._events.append_device_event(
            conn,
            device_id=binding_id,
            device_revision=revision,
            event_type=event_type,
            source_event_id=f"device:{source}",
            payload=payload,
        )
        self._events.append_work_event(
            conn,
            work_id=work_id,
            event_type=event_type,
            source_event_id=f"work:{source}",
            payload=payload,
        )

    def _device_package_row(
        self, conn: sqlite3.Connection, package_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT p.*, r.manifest_json, r.files_json
            FROM capability_packages AS p
            JOIN package_revisions AS r ON r.id = p.stable_revision_id
            WHERE p.id = ? AND p.kind = 'DEVICE_PACKAGE'
              AND p.owner_key IN (?, ?)
            """,
            (package_id, _SYSTEM_OWNER, self._owner_key),
        ).fetchone()
        if row is None:
            raise DevicePlatformNotFoundError("设备技术包不存在。")
        return row

    def _package_for_legacy_component(
        self,
        conn: sqlite3.Connection,
        *,
        component_id: str,
        skill_name: str,
    ) -> sqlite3.Row | None:
        board_id = _BOARD_COMPONENT_IDS.get(component_id)
        if board_id is not None:
            return conn.execute(
                """
                SELECT * FROM capability_packages
                WHERE source_type = 'DEVICE_BOARD' AND source_key = ?
                """,
                (board_id,),
            ).fetchone()
        if skill_name:
            return conn.execute(
                """
                SELECT * FROM capability_packages
                WHERE source_type = 'HARDWARE_SKILL' AND source_key = ?
                """,
                (skill_name,),
            ).fetchone()
        return None

    def _assert_channel_declared(
        self,
        conn: sqlite3.Connection,
        package_row: sqlite3.Row,
        channel: DeviceDeploymentChannel | None,
    ) -> None:
        if channel is None:
            return
        self._assert_revision_channel(
            self._revision_row(conn, str(package_row["stable_revision_id"])),
            channel.value,
        )

    @staticmethod
    def _assert_revision_channel(
        revision_row: sqlite3.Row,
        channel: object,
    ) -> None:
        if channel is None:
            return
        manifest = _object(json.loads(str(revision_row["manifest_json"])))
        compatibility = _object(manifest.get("compatibility"))
        channels = compatibility.get("deploymentChannels")
        declared = {str(item) for item in channels} if isinstance(channels, list) else set()
        if str(channel) not in declared:
            raise DevicePlatformValidationError("设备技术包未声明所选部署通道。")

    @staticmethod
    def _revision_row(conn: sqlite3.Connection, revision_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM package_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
        if row is None:
            raise DevicePlatformNotFoundError("设备包修订不存在。")
        return row

    def _inventory_row(self, conn: sqlite3.Connection, item_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id = ? AND owner_key = ?",
            (item_id, self._owner_key),
        ).fetchone()
        if row is None:
            raise DevicePlatformNotFoundError("库存设备不存在。")
        return row

    def _binding_row(
        self, conn: sqlite3.Connection, work_id: str, binding_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM work_device_bindings
            WHERE id = ? AND work_id = ? AND owner_key = ?
            """,
            (binding_id, work_id, self._owner_key),
        ).fetchone()
        if row is None:
            raise DevicePlatformNotFoundError("作品设备绑定不存在。")
        return row

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _technical_fact(row: sqlite3.Row) -> DeviceTechnicalFact:
    manifest = _object(json.loads(str(row["manifest_json"])))
    compatibility = _object(manifest.get("compatibility"))
    evidence = _object(manifest.get("evidence"))
    raw_class = str(compatibility.get("deviceClass") or "COMPONENT")
    device_class = DeviceTechnicalFactClass(raw_class)
    raw_channels = compatibility.get("deploymentChannels")
    channels = (
        [DeviceDeploymentChannel(str(item)) for item in raw_channels]
        if isinstance(raw_channels, list)
        else []
    )
    capabilities = [str(item) for item in manifest.get("capabilities", [])]
    verification = str(
        evidence.get("verificationStatus")
        or evidence.get("hardwareValidated")
        or "UNVERIFIED"
    )
    if device_class is DeviceTechnicalFactClass.BOARD:
        summary = "可用于数字试验，并在确认后通过本地安全执行器连接。"
    else:
        summary = "提供作品连接、供电与结构所需的技术事实。"
    return DeviceTechnicalFact(
        devicePackageId=str(row["id"]),
        devicePackageRevisionId=str(row["stable_revision_id"]),
        displayName=str(row["display_name"]),
        deviceClass=device_class,
        capabilities=capabilities,
        deploymentChannels=channels,
        runtime=(str(compatibility["runtime"]) if compatibility.get("runtime") else None),
        verificationStatus=verification,
        naturalSummary=summary,
        imageUrl=None,
    )


def _inventory_from_row(row: sqlite3.Row) -> InventoryItem:
    return InventoryItem(
        id=str(row["id"]),
        devicePackageId=str(row["device_package_id"]),
        displayName=str(row["display_name"]),
        quantity=int(row["quantity"]),
        status=InventoryItemStatus(str(row["status"])),
        price=float(row["price"]),
        location=str(row["location"]),
        notes=str(row["notes"]),
        lastConnectionStatus=(
            str(row["last_connection_status"])
            if row["last_connection_status"] is not None
            else None
        ),
        lastConnectedAt=(
            str(row["last_connected_at"])
            if row["last_connected_at"] is not None
            else None
        ),
        revision=int(row["revision"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _binding_from_row(row: sqlite3.Row) -> WorkDeviceBinding:
    return WorkDeviceBinding(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        inventoryItemId=(
            str(row["inventory_item_id"])
            if row["inventory_item_id"] is not None
            else None
        ),
        devicePackageId=str(row["device_package_id"]),
        devicePackageRevisionId=str(row["device_package_revision_id"]),
        identityStatus=DeviceIdentityStatus(str(row["identity_status"])),
        deploymentChannel=(
            DeviceDeploymentChannel(str(row["deployment_channel"]))
            if row["deployment_channel"] is not None
            else None
        ),
        runtimePackageRevisionId=(
            str(row["runtime_package_revision_id"])
            if row["runtime_package_revision_id"] is not None
            else None
        ),
        codeVariantId=(
            str(row["code_variant_id"]) if row["code_variant_id"] is not None else None
        ),
        ioConfig=_object(json.loads(str(row["io_config_json"]))),
        recoveryStatus=DeviceRecoveryStatus(str(row["recovery_status"])),
        naturalStatus=str(row["natural_status"]),
        revision=int(row["revision"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _binding_natural_status(channel: object) -> str:
    if channel == DeviceDeploymentChannel.USB_SERIAL.value:
        return "已选择 USB 连接，真实写入前仍会再次确认。"
    if channel == DeviceDeploymentChannel.ESP_CLAW.value:
        return "已选择 ESP-Claw，配对与写入仍需本地明确确认。"
    return "已加入作品，先完成数字试验再连接。"


def _object(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
