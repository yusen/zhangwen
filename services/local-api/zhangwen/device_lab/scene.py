"""Deterministic physical-scene projection from an approved project proposal."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from zhangwen.device_lab.boards import BOARDS
from zhangwen.device_lab.models import (
    DigitalPrototypeBindingV1,
    DeviceLabProjectTestCase,
    DeviceLabSceneComponent,
    DeviceLabSceneConnection,
    DeviceLabSceneSource,
    DeviceLabSceneV1,
    SupportedDeviceBoardId,
)
from zhangwen.proposals.models import ProposalSection, ProposalStatus, ProposalVersion
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.specs.models import SpecFileKind, SpecRunStatus
from zhangwen.specs.repository import SpecRepository


_BOARD_COMPONENT_IDS: dict[str, SupportedDeviceBoardId] = {
    "hw_seed_unihiker_k10": SupportedDeviceBoardId.DFROBOT_K10,
    "unihiker-k10": SupportedDeviceBoardId.DFROBOT_K10,
    "unihiker_k10": SupportedDeviceBoardId.DFROBOT_K10,
    "dfrobot/dfrobot_k10": SupportedDeviceBoardId.DFROBOT_K10,
    "hw_seeed_xiao_esp32s3_sense": SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
    "xiao-esp32s3-sense": SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
    "seeedstudio/xiao_esp32s3_sense": SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
}

_BOARD_SCENARIO_CHANNELS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("温度", "temperature"), ("temperature",)),
    (("环境湿度", "air humidity"), ("humidity",)),
    (("环境光", "光照", "ambient light"), ("ambient-light",)),
    (("加速度", "姿态", "倾斜", "acceler"), ("accel-x", "accel-y", "accel-z")),
    (("按键 a", "button a"), ("button-a",)),
    (("按键 b", "button b"), ("button-b",)),
    (("摄像头", "camera", "图像"), ("camera-fixture",)),
    (("麦克风", "microphone", "声音"), ("microphone-level",)),
    (("sd 卡", "存储卡", "storage"), ("sd-mounted",)),
)


class DeviceLabSceneProjectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DeviceLabSceneProjector:
    """Build one immutable scene snapshot from approved project facts.

    The projection is deliberately deterministic: opening the device lab does
    not let the UI substitute a board or invent a third controller.
    """

    def __init__(self, db_path: Path, data_dir: Path) -> None:
        self._db_path = Path(db_path)
        # Kept in the constructor because all device-lab services are scoped by
        # the same data directory; scene facts themselves come from normalized
        # V29 tables, not the legacy projected workspace JSON.
        self._data_dir = Path(data_dir)
        self._proposals = ProposalRepository(self._db_path)
        self._specs = SpecRepository(self._db_path)

    def project(self, project_id: str) -> DeviceLabSceneV1:
        proposal = self._approved_proposal(project_id)
        fact = self._preferred_hardware_fact(project_id)
        fact_components = _fact_components(fact["value"] if fact else None)
        spec = self._specs.get_current_spec(project_id)
        if (
            spec is None
            or spec.status != SpecRunStatus.APPROVED
            or spec.proposalId != proposal.id
        ):
            spec = None
        bom_components, io_pins = _spec_components(spec)
        creator_components, creator_pins, creator_warnings = (
            self._creator_solution_components(project_id)
        )
        if not io_pins:
            io_pins = creator_pins
        proposal_text = "\n".join(section.content for section in proposal.sections)
        proposal_components = self._catalog_mentions(proposal_text)

        records = _merge_component_records(
            fact_components,
            bom_components,
            creator_components,
            proposal_components,
        )
        board_id, controller_record, board_source = _resolve_board(records, proposal_text)
        controller_id = str(controller_record.get("id") or f"board:{board_id.value}")
        controller_name = str(
            controller_record.get("name") or BOARDS[board_id].displayName
        )

        components: list[DeviceLabSceneComponent] = [
            DeviceLabSceneComponent(
                id=controller_id,
                name=controller_name,
                category="MCU",
                role="controller",
                source=board_source,
                simulation="FUNCTIONAL",
                builtIn=False,
                protocol=str(controller_record.get("protocol") or "GPIO/I2C/SPI"),
            )
        ]
        component_ids = {controller_id}
        for record in records:
            component_id = str(record.get("id") or "").strip()
            if not component_id or component_id in component_ids:
                continue
            if str(record.get("category") or "").upper() == "MCU":
                continue
            category = _scene_category(record.get("category"))
            component_role = (
                "service"
                if category == "SERVICE"
                else "external"
            )
            components.append(
                DeviceLabSceneComponent(
                    id=component_id,
                    name=str(record.get("name") or component_id),
                    category=category,
                    role=component_role,
                    source=_component_source(record),
                    simulation=(
                        "FUNCTIONAL"
                        if category in {"SENSOR", "ACTUATOR", "DISPLAY", "SERVICE"}
                        else "VISUAL_ONLY"
                    ),
                    builtIn=False,
                    protocol=_clean_protocol(record.get("protocol")),
                )
            )
            component_ids.add(component_id)

        connections: list[DeviceLabSceneConnection] = []
        confirmed_targets: set[str] = set()
        for index, pin in enumerate(io_pins, start=1):
            target_id = str(pin.get("component_id") or "").strip()
            if not target_id or target_id == controller_id:
                continue
            if target_id not in component_ids:
                components.append(
                    DeviceLabSceneComponent(
                        id=target_id,
                        name=str(pin.get("component") or target_id),
                        category="SENSOR",
                        role="external",
                        source="approved-spec",
                        simulation="FUNCTIONAL",
                        builtIn=False,
                        protocol=_clean_protocol(pin.get("protocol")),
                    )
                )
                component_ids.add(target_id)
            protocol = _clean_protocol(pin.get("protocol")) or "GPIO"
            signal = str(pin.get("signal") or f"signal_{index}")
            connections.append(
                DeviceLabSceneConnection(
                    id=f"io:{index}:{_slug(signal)}",
                    fromComponentId=controller_id,
                    toComponentId=target_id,
                    protocol=protocol,
                    signal=signal,
                    pin=str(pin.get("pin") or "") or None,
                    confidence="CONFIRMED",
                    note="来自已确认 Spec 的 IO Map。",
                )
            )
            confirmed_targets.add(target_id)

        warnings: list[str] = list(creator_warnings)
        topology_targets = _append_functional_topology(
            components,
            connections,
            controller_id,
        )
        for component in list(components):
            if (
                component.role not in {"external", "service"}
                or component.id in confirmed_targets
                or component.id in topology_targets
            ):
                continue
            protocol = component.protocol or "GPIO"
            connections.append(
                DeviceLabSceneConnection(
                    id=f"derived:{_slug(component.id)}",
                    fromComponentId=controller_id,
                    toComponentId=component.id,
                    protocol=protocol,
                    signal=f"auto_{_slug(component.id)}",
                    pin=None,
                    confidence="PROPOSAL_DERIVED",
                    note=(
                        "方案要求本地 MQTT；仿真使用进程内消息总线，"
                        "真实局域网 Broker 需在部署前确认。"
                        if component.category == "SERVICE"
                        else "器件来自方案内容；接线脚位需在 IO Map 确认后锁定。"
                    ),
                )
            )
        if any(item.confidence == "PROPOSAL_DERIVED" for item in connections):
            warnings.append("立项中的外接器件已生成实物场景，但未确认的 IO 脚位不会被当作真实接线。")

        board = BOARDS[board_id]
        for index, peripheral in enumerate(board.peripherals, start=1):
            onboard_id = f"{controller_id}:onboard:{index}"
            components.append(
                DeviceLabSceneComponent(
                    id=onboard_id,
                    name=peripheral,
                    category="ONBOARD",
                    role="onboard",
                    source="board-profile",
                    simulation="FUNCTIONAL",
                    builtIn=True,
                    protocol="BOARD_INTERNAL",
                )
            )
            connections.append(
                DeviceLabSceneConnection(
                    id=f"onboard:{index}",
                    fromComponentId=controller_id,
                    toComponentId=onboard_id,
                    protocol="BOARD_INTERNAL",
                    signal=f"onboard_{index}",
                    pin=None,
                    confidence="CONFIRMED",
                    note="来自精确板级档案的板载器件。",
                )
            )

        test_cases = self._project_test_cases(project_id, components)
        source = DeviceLabSceneSource(
            proposalId=proposal.id,
            proposalVersion=proposal.version,
            proposalConfirmedAt=proposal.confirmedAt or proposal.updatedAt,
            hardwareFactId=str(fact["id"]) if fact else None,
            hardwareFactUpdatedAt=str(fact["updatedAt"]) if fact else None,
            specRunId=spec.id if spec else None,
            specVersion=spec.version if spec else None,
            specConfirmedAt=spec.confirmedAt if spec else None,
        )
        status = (
            "NEEDS_IO_CONFIRMATION"
            if any(item.confidence == "PROPOSAL_DERIVED" for item in connections)
            else "READY"
        )
        prototype_binding = self._prototype_binding(project_id, proposal.id)
        revision_payload = {
            "boardId": board_id.value,
            "source": source.model_dump(mode="json"),
            "components": [item.model_dump(mode="json") for item in components],
            "connections": [item.model_dump(mode="json") for item in connections],
            "testCases": [item.model_dump(mode="json") for item in test_cases],
            "status": status,
            "binding": prototype_binding.model_dump(mode="json"),
        }
        revision = hashlib.sha256(
            json.dumps(
                revision_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return DeviceLabSceneV1(
            projectId=project_id,
            revision=revision,
            boardId=board_id,
            status=status,
            source=source,
            binding=prototype_binding,
            components=components,
            connections=connections,
            testCases=test_cases,
            warnings=warnings,
            generatedAt=proposal.confirmedAt or proposal.updatedAt,
        )

    def _creator_solution_components(
        self,
        project_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT bom_json, io_map_json, summary, logic, hardware, software
                    FROM creator_solution_revisions
                    WHERE project_id = ? AND status = 'CONFIRMED'
                    ORDER BY revision DESC LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
        except sqlite3.OperationalError:
            return [], [], []
        if row is None:
            return [], [], []
        raw_bom = json.loads(str(row["bom_json"]))
        components = [
            {
                "id": str(item.get("componentId") or ""),
                "name": str(item.get("name") or item.get("componentId") or ""),
                "category": _infer_component_category(
                    str(item.get("componentId") or ""),
                    str(item.get("name") or ""),
                ),
                "protocol": _infer_component_protocol(
                    str(item.get("componentId") or ""),
                    str(item.get("name") or ""),
                ),
                "_source": "approved-spec",
            }
            for item in raw_bom
            if isinstance(item, dict) and item.get("componentId")
        ]
        components = _ensure_structured_hardware_components(
            components,
            str(row["hardware"]),
        )
        warnings: list[str] = []
        infrastructure_text = "\n".join(
            str(row[key]) for key in ("summary", "logic", "hardware", "software")
        )
        mqtt_mode = _mqtt_requirement(infrastructure_text)
        if mqtt_mode == "LOCAL":
            components.append(
                {
                    "id": "zw.service.local-mqtt",
                    "name": "本地 MQTT 消息服务",
                    "category": "SERVICE",
                    "protocol": "MQTT",
                    "_source": "approved-spec",
                }
            )
        elif mqtt_mode == "UNSPECIFIED":
            warnings.append(
                "方案提到了 MQTT，但尚未确认 Broker 位于本地、局域网还是云端；"
                "请回到创意方案确认后再自动加入服务节点。"
            )
        raw_io = json.loads(str(row["io_map_json"]))
        pins = []
        for item in raw_io:
            if not isinstance(item, dict):
                continue
            signal = str(item.get("signal") or "")
            purpose = str(item.get("purpose") or "")
            pins.append(
                {
                    "signal": signal,
                    "pin": str(item.get("pin") or ""),
                    "component": purpose,
                    "component_id": _match_io_component(
                        signal,
                        purpose,
                        components,
                    ),
                    "protocol": _infer_io_protocol(signal, purpose),
                }
            )
        return components, pins, warnings

    def _prototype_binding(
        self,
        project_id: str,
        solution_revision_id: str,
    ) -> DigitalPrototypeBindingV1:
        code_run_id: str | None = None
        parameter_set_id: str | None = None
        capability = "FUNCTIONAL"
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                code_row = conn.execute(
                    """
                    SELECT binding.code_run_id AS id
                    FROM creator_code_variant_bindings AS binding
                    JOIN code_runs AS run ON run.id = binding.code_run_id
                    WHERE binding.project_id = ?
                      AND binding.solution_revision_id = ?
                      AND binding.validation_status IN ('ACCEPTED', 'READY_FOR_REVIEW')
                      AND run.status IN ('ACCEPTED', 'READY_FOR_REVIEW')
                    ORDER BY
                      CASE binding.deployment_channel
                        WHEN 'USB_SERIAL' THEN 0 ELSE 1
                      END,
                      CASE binding.validation_status
                        WHEN 'ACCEPTED' THEN 0 ELSE 1
                      END
                    LIMIT 1
                    """,
                    (project_id, solution_revision_id),
                ).fetchone()
                parameter_row = conn.execute(
                    """
                    SELECT id FROM device_parameter_sets
                    WHERE project_id = ?
                    ORDER BY revision DESC LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            code_run_id = str(code_row["id"]) if code_row else None
            parameter_set_id = str(parameter_row["id"]) if parameter_row else None
        except sqlite3.OperationalError:
            pass
        return DigitalPrototypeBindingV1(
            solutionRevisionId=solution_revision_id,
            codeRunId=code_run_id,
            parameterSetId=parameter_set_id,
            simulationCapability=capability,
        )

    def _project_test_cases(
        self,
        project_id: str,
        components: list[DeviceLabSceneComponent],
    ) -> list[DeviceLabProjectTestCase]:
        """Turn confirmed acceptance scenarios into the only default test inputs.

        The complete board profile remains available to the simulator, while
        the Creator prototype exposes only channels that can change the
        behavior promised by the current solution.
        """

        sensor_components = [
            item
            for item in components
            if item.role == "external" and item.category == "SENSOR"
        ]
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT id, title, simulation_expected
                    FROM creator_acceptance_scenarios
                    WHERE project_id = ?
                    ORDER BY created_at ASC, id ASC
                    """,
                    (project_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        cases: list[DeviceLabProjectTestCase] = []
        for row in rows:
            title = str(row["title"])
            expected = str(row["simulation_expected"])
            scenario_text = f"{title}\n{expected}".casefold()
            input_ids: list[str] = []
            for component in sensor_components:
                component_text = f"{component.id} {component.name}".casefold()
                tokens = _meaningful_tokens(component_text)
                is_watering_sensor = any(
                    token in component_text
                    for token in ("soil", "moisture", "土壤湿度", "湿度传感")
                )
                is_watering_case = any(
                    token in scenario_text
                    for token in ("干燥", "湿润", "浇水", "水泵", "dry", "wet", "watering")
                )
                if (is_watering_sensor and is_watering_case) or any(
                    token in scenario_text for token in tokens
                ):
                    input_ids.append(_component_channel_id(component.id, "input"))

            for tokens, channel_ids in _BOARD_SCENARIO_CHANNELS:
                if any(token in scenario_text for token in tokens):
                    input_ids.extend(channel_ids)
            if any(
                token in scenario_text
                for token in ("断线", "超时", "故障", "异常", "disconnect", "timeout", "fault")
            ):
                input_ids.append("fault-mode")

            if not input_ids and len(sensor_components) == 1:
                input_ids.append(
                    _component_channel_id(sensor_components[0].id, "input")
                )
            cases.append(
                DeviceLabProjectTestCase(
                    id=str(row["id"]),
                    title=title,
                    inputChannelIds=list(dict.fromkeys(input_ids)),
                    expectedBehavior=expected,
                    source="acceptance-scenario",
                )
            )

        if cases:
            return cases
        return [
            DeviceLabProjectTestCase(
                id=f"default:{_slug(component.id)}",
                title=f"验证{component.name}输入",
                inputChannelIds=[_component_channel_id(component.id, "input")],
                expectedBehavior=f"改变{component.name}输入后，方案定义的可观察行为应同步变化。",
                source="scene-default",
            )
            for component in sensor_components
        ]

    def _approved_proposal(self, project_id: str) -> ProposalVersion:
        creator_solution = self._confirmed_creator_solution(project_id)
        if creator_solution is not None:
            return creator_solution
        proposal = next(
            (
                item
                for item in self._proposals.list_proposals(project_id)
                if item.status == ProposalStatus.APPROVED
            ),
            None,
        )
        if proposal is not None:
            return proposal
        raise DeviceLabSceneProjectionError(
            "DEVICE_LAB_APPROVED_PROPOSAL_REQUIRED",
            "请先确认作品方案；设备实验室只根据已批准立项或 Creator 方案自动创建实物仿真。",
        )

    def _confirmed_creator_solution(self, project_id: str) -> ProposalVersion | None:
        """Adapt the current Creator solution into the established scene projector.

        This is an in-memory compatibility view only: it does not create a
        second legacy proposal or overwrite Creator revision history.
        """

        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT * FROM creator_solution_revisions
                    WHERE project_id = ? AND status = 'CONFIRMED'
                    ORDER BY revision DESC LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None:
            return None
        confirmed_at = str(row["confirmed_at"] or row["created_at"])
        sections = [
            ProposalSection(id="overview", title="方案摘要", content=str(row["summary"])),
            ProposalSection(id="logic", title="工作逻辑", content=str(row["logic"])),
            ProposalSection(id="hardware", title="硬件与供电", content=str(row["hardware"])),
            ProposalSection(id="software", title="软件与代码", content=str(row["software"])),
            ProposalSection(id="structure", title="3D 结构", content=str(row["structure"])),
            ProposalSection(id="simulation", title="仿真", content=str(row["simulation"])),
            ProposalSection(id="safety", title="安全", content=str(row["safety"])),
            ProposalSection(
                id="bom_io",
                title="BOM 与 IO",
                content=f"BOM: {row['bom_json']}\nIO: {row['io_map_json']}",
            ),
        ]
        return ProposalVersion(
            id=str(row["id"]),
            projectId=project_id,
            solutionId=str(row["id"]),
            solutionVersion=int(row["revision"]),
            version=int(row["revision"]),
            status=ProposalStatus.APPROVED,
            sections=sections,
            createdAt=str(row["created_at"]),
            updatedAt=confirmed_at,
            confirmedAt=confirmed_at,
        )

    def _preferred_hardware_fact(self, project_id: str) -> dict[str, object] | None:
        """Read the current normalized fact instead of stale workspace JSON."""

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, value_json, updated_at
                FROM project_shared_facts
                WHERE project_id = ?
                  AND COALESCE(key, field) = 'preferred_hardware'
                  AND status = 'confirmed'
                ORDER BY updated_at DESC, rowid DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "value": _json_object(row["value_json"]),
            "updatedAt": str(row["updated_at"]),
        }

    def _catalog_mentions(self, proposal_text: str) -> list[dict[str, Any]]:
        text = proposal_text.casefold()
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT id, name, category, electrical_json
                    FROM hardware_components
                    WHERE status = 'ACTIVE'
                    """
                ).fetchall()
        except sqlite3.OperationalError:
            return []
        matches: list[dict[str, Any]] = []
        for row in rows:
            name = str(row["name"])
            component_id = str(row["id"])
            if component_id.casefold() not in text and (
                len(name.strip()) < 3 or name.casefold() not in text
            ):
                continue
            electrical = _json_object(row["electrical_json"])
            matches.append(
                {
                    "id": component_id,
                    "name": name,
                    "category": str(row["category"]),
                    "protocol": electrical.get("communicationProtocol"),
                    "_source": "approved-proposal",
                }
            )
        return matches


def materialize_device_lab_scene(
    db_path: Path,
    data_dir: Path,
    project_id: str,
) -> DeviceLabSceneV1 | None:
    """Best-effort projection invoked by every proposal-confirmation entry.

    Approval remains valid when a non-device proposal has no supported board;
    the device lab then reports the precise projection blocker instead of
    silently choosing K10.
    """

    try:
        scene = DeviceLabSceneProjector(db_path, data_dir).project(project_id)
    except DeviceLabSceneProjectionError:
        return None
    from zhangwen.device_lab.repository import DeviceLabRepository

    return DeviceLabRepository(db_path).save_scene(scene)


def _fact_components(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("components"), list):
        return []
    return [
        {**item, "_source": "project-hardware"}
        for item in value["components"]
        if isinstance(item, dict)
    ]


def _spec_components(spec: object | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if spec is None:
        return [], []
    bom: list[dict[str, Any]] = []
    pins: list[dict[str, Any]] = []
    for file in spec.files:  # type: ignore[attr-defined]
        if file.kind not in {SpecFileKind.BOM, SpecFileKind.IO_MAP}:
            continue
        try:
            value = yaml.safe_load(file.content)
        except yaml.YAMLError:
            continue
        if not isinstance(value, dict):
            continue
        if file.kind == SpecFileKind.BOM and isinstance(value.get("components"), list):
            bom = [
                {**item, "_source": "approved-spec"}
                for item in value["components"]
                if isinstance(item, dict)
            ]
        if file.kind == SpecFileKind.IO_MAP and isinstance(value.get("pins"), list):
            pins = [item for item in value["pins"] if isinstance(item, dict)]
    return bom, pins


def _merge_component_records(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for group in groups:
        for item in group:
            component_id = str(item.get("id") or "").strip()
            if not component_id:
                continue
            if component_id not in merged:
                order.append(component_id)
                merged[component_id] = dict(item)
            else:
                merged[component_id] = {**item, **merged[component_id]}
    return [merged[item] for item in order]


def _resolve_board(
    records: list[dict[str, Any]],
    proposal_text: str,
) -> tuple[SupportedDeviceBoardId, dict[str, Any], str]:
    mcu_records = [
        item for item in records if str(item.get("category") or "").upper() == "MCU"
    ]
    resolved: list[tuple[SupportedDeviceBoardId, dict[str, Any]]] = []
    unsupported: list[str] = []
    for item in mcu_records:
        component_id = str(item.get("id") or "").casefold()
        board = _BOARD_COMPONENT_IDS.get(component_id)
        if board is None:
            unsupported.append(str(item.get("name") or component_id))
        else:
            resolved.append((board, item))
    unique = {board for board, _item in resolved}
    if unsupported:
        raise DeviceLabSceneProjectionError(
            "DEVICE_LAB_UNSUPPORTED_CONTROLLER",
            "立项内容包含不受支持的主控板：" + "、".join(unsupported[:4]) + "。请显式迁移为 K10 或 XIAO Sense。",
        )
    if len(unique) > 1:
        raise DeviceLabSceneProjectionError(
            "DEVICE_LAB_MULTIPLE_CONTROLLERS",
            "立项内容同时包含两块主控板；一个实物仿真场景只能确定一块主控。",
        )
    if unique:
        board_id = next(iter(unique))
        record = next(item for board, item in resolved if board == board_id)
        return board_id, record, _component_source(record)

    normalized = re.sub(r"[\s_-]+", "", proposal_text.casefold())
    k10 = any(token in normalized for token in ("dfrobotk10", "unihikerk10", "行空板k10"))
    xiao = any(
        token in normalized
        for token in ("xiaoesp32s3sense", "seeedstudioxiao", "xiao sense".replace(" ", ""))
    )
    if k10 and xiao:
        raise DeviceLabSceneProjectionError(
            "DEVICE_LAB_MULTIPLE_CONTROLLERS",
            "立项书同时提到 K10 与 XIAO Sense，无法自动确定实物仿真的唯一主控。",
        )
    if k10:
        return (
            SupportedDeviceBoardId.DFROBOT_K10,
            {"id": "hw_seed_unihiker_k10", "name": BOARDS[SupportedDeviceBoardId.DFROBOT_K10].displayName},
            "approved-proposal",
        )
    if xiao:
        return (
            SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
            {"id": "hw_seeed_xiao_esp32s3_sense", "name": BOARDS[SupportedDeviceBoardId.XIAO_ESP32S3_SENSE].displayName},
            "approved-proposal",
        )
    raise DeviceLabSceneProjectionError(
        "DEVICE_LAB_SUPPORTED_CONTROLLER_REQUIRED",
        "已批准立项内容中没有唯一的 K10 或 XIAO ESP32S3 Sense，不能自动创建实物仿真。",
    )


def _component_source(record: dict[str, Any]) -> str:
    source = str(record.get("_source") or "approved-proposal")
    if source not in {"project-hardware", "approved-spec", "approved-proposal"}:
        return "approved-proposal"
    return source


def _scene_category(value: object) -> str:
    category = str(value or "STRUCTURE").upper()
    return (
        category
        if category
        in {"SENSOR", "ACTUATOR", "DISPLAY", "POWER", "STRUCTURE", "SERVICE"}
        else "STRUCTURE"
    )


def _append_functional_topology(
    components: list[DeviceLabSceneComponent],
    connections: list[DeviceLabSceneConnection],
    controller_id: str,
) -> set[str]:
    """Add power/load/service relationships that an IO map cannot express."""

    external = [item for item in components if item.role in {"external", "service"}]

    def find(*tokens: str) -> DeviceLabSceneComponent | None:
        for item in external:
            text = f"{item.id} {item.name}".casefold()
            if any(token in text for token in tokens):
                return item
        return None

    driver = find("pump-driver", "mosfet", "relay", "水泵驱动", "继电器", "驱动")
    pump = find("water-pump", "直流水泵", "微型水泵")
    power = next((item for item in external if item.category == "POWER"), None)
    mqtt = next((item for item in external if item.category == "SERVICE"), None)
    claimed: set[str] = set()

    if driver is not None and pump is not None:
        connections.append(
            DeviceLabSceneConnection(
                id="topology:driver-to-load",
                fromComponentId=driver.id,
                toComponentId=pump.id,
                protocol="POWER_LOAD",
                signal="受控泵电源",
                pin=None,
                confidence="PROPOSAL_DERIVED",
                note="方案要求驱动模块隔离主控与水泵负载；额定电流需在实物阶段确认。",
            )
        )
        claimed.add(pump.id)
    if power is not None and driver is not None:
        connections.append(
            DeviceLabSceneConnection(
                id="topology:power-to-driver",
                fromComponentId=power.id,
                toComponentId=driver.id,
                protocol="POWER",
                signal="独立负载供电",
                pin=None,
                confidence="PROPOSAL_DERIVED",
                note="外部电源为驱动和负载供电，不从主控 GPIO 直接驱动水泵。",
            )
        )
        connections.append(
            DeviceLabSceneConnection(
                id="topology:common-ground",
                fromComponentId=power.id,
                toComponentId=controller_id,
                protocol="COMMON_GROUND",
                signal="共地",
                pin="GND",
                confidence="PROPOSAL_DERIVED",
                note="功能拓扑要求主控与外部驱动电源共地；实物接线前仍需复核。",
            )
        )
        claimed.add(power.id)
    if mqtt is not None:
        connections.append(
            DeviceLabSceneConnection(
                id="topology:local-mqtt",
                fromComponentId=controller_id,
                toComponentId=mqtt.id,
                protocol="MQTT",
                signal="本地消息通道",
                pin=None,
                confidence="CONFIRMED",
                note="仿真使用本机进程内消息总线；不会自动监听局域网端口。",
            )
        )
        claimed.add(mqtt.id)
    return claimed


def _mqtt_requirement(text: str) -> str:
    normalized = text.casefold()
    if "mqtt" not in normalized:
        return "NONE"
    if any(
        token in normalized
        for token in (
            "本地 mqtt",
            "本机 mqtt",
            "局域网 mqtt",
            "内网 mqtt",
            "离线 mqtt",
            "local mqtt",
            "lan mqtt",
            "offline mqtt",
            "本地 broker",
            "本机 broker",
            "局域网 broker",
            "内网 broker",
        )
    ):
        return "LOCAL"
    if any(
        token in normalized
        for token in (
            "云 mqtt",
            "云端 mqtt",
            "cloud mqtt",
            "公网 broker",
            "aliyun",
            "aws iot",
            "emqx cloud",
        )
    ):
        return "REMOTE"
    return "UNSPECIFIED"


def _component_channel_id(component_id: str, suffix: str) -> str:
    digest = hashlib.sha256(component_id.encode("utf-8")).hexdigest()[:12]
    return f"project.{digest}.{suffix}"


def _meaningful_tokens(text: str) -> tuple[str, ...]:
    known = (
        "soil",
        "moisture",
        "temperature",
        "humidity",
        "light",
        "camera",
        "microphone",
        "土壤湿度",
        "温度",
        "湿度",
        "环境光",
        "摄像头",
        "麦克风",
    )
    return tuple(token for token in known if token in text)


def _infer_component_category(component_id: str, name: str) -> str:
    text = f"{component_id} {name}".casefold()
    if any(token in text for token in ("power", "电源", "供电", "battery", "电池")):
        return "POWER"
    if any(token in text for token in ("display", "oled", "lcd", "显示", "屏")):
        return "DISPLAY"
    if any(
        token in text
        for token in (
            "sensor",
            "moisture",
            "temperature",
            "humidity",
            "light",
            "camera",
            "microphone",
            "传感",
            "湿度",
            "温度",
            "光照",
            "摄像",
            "麦克风",
        )
    ):
        return "SENSOR"
    if any(
        token in text
        for token in (
            "pump",
            "mosfet",
            "relay",
            "servo",
            "buzzer",
            "speaker",
            "rgb",
            "led",
            "水泵",
            "驱动",
            "继电器",
            "舵机",
            "蜂鸣",
            "扬声器",
            "灯",
        )
    ):
        return "ACTUATOR"
    return "STRUCTURE"


def _infer_component_protocol(component_id: str, name: str) -> str | None:
    text = f"{component_id} {name}".casefold()
    if any(token in text for token in ("moisture", "湿度", "light", "光照")):
        return "ADC"
    if any(token in text for token in ("camera", "摄像")):
        return "CAMERA"
    if any(token in text for token in ("microphone", "麦克风")):
        return "PDM/I2S"
    if any(token in text for token in ("display", "oled", "显示")):
        return "I2C/SPI"
    if _infer_component_category(component_id, name) == "ACTUATOR":
        return "GPIO/PWM"
    return None


def _ensure_structured_hardware_components(
    components: list[dict[str, Any]],
    hardware: str,
) -> list[dict[str, Any]]:
    text = hardware.casefold()
    watering = (
        any(token in text for token in ("水泵", "pump"))
        and any(token in text for token in ("湿度", "moisture", "浇花", "watering"))
    )
    if not watering:
        return components
    result = list(components)

    def ensure(
        component_id: str,
        name: str,
        category: str,
        protocol: str | None,
        tokens: tuple[str, ...],
    ) -> None:
        haystacks = [
            f"{item.get('id', '')} {item.get('name', '')}".casefold()
            for item in result
        ]
        if any(any(token in item for token in tokens) for item in haystacks):
            return
        result.append(
            {
                "id": component_id,
                "name": name,
                "category": category,
                "protocol": protocol,
                "_source": "approved-spec",
            }
        )

    ensure(
        "zw.sensor.soil-moisture",
        "土壤湿度传感器",
        "SENSOR",
        "ADC",
        ("soil", "moisture", "土壤湿度", "湿度传感"),
    )
    ensure(
        "zw.actuator.pump-driver",
        "MOSFET/继电器水泵驱动",
        "ACTUATOR",
        "GPIO/PWM",
        ("mosfet", "relay", "pump-driver", "泵驱动", "继电器", "驱动"),
    )
    ensure(
        "zw.actuator.water-pump",
        "直流水泵",
        "ACTUATOR",
        "POWER_LOAD",
        ("water-pump", "直流水泵", "微型水泵"),
    )
    ensure(
        "zw.power.external-5v",
        "独立 5V 水泵电源",
        "POWER",
        "POWER",
        ("power", "电源", "供电", "battery", "电池"),
    )
    return result


def _match_io_component(
    signal: str,
    purpose: str,
    components: list[dict[str, Any]],
) -> str:
    text = f"{signal} {purpose}".casefold()
    if any(token in text for token in ("pump", "水泵", "泵")):
        for item in components:
            item_text = f"{item.get('id', '')} {item.get('name', '')}".casefold()
            if any(token in item_text for token in ("driver", "mosfet", "relay", "驱动", "继电器")):
                return str(item.get("id") or "")
    if any(token in text for token in ("moisture", "湿度")):
        for item in components:
            if str(item.get("category") or "") == "SENSOR":
                return str(item.get("id") or "")
    return ""


def _infer_io_protocol(signal: str, purpose: str) -> str:
    text = f"{signal} {purpose}".casefold()
    if any(token in text for token in ("moisture", "湿度", "adc")):
        return "ADC"
    if any(token in text for token in ("pump", "水泵", "servo", "舵机", "pwm")):
        return "PWM"
    return "GPIO"


def _clean_protocol(value: object) -> str | None:
    text = str(value or "").strip()
    return text[:100] or None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:72] or hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _json_object(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
