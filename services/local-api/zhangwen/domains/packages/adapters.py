"""One-way adapters from existing Agent, Skill, Board, and Hardware facts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from zhangwen.domains.packages.models import PackageKind
from zhangwen.experts.packages import AgentPackageRepository
from zhangwen.hardware.board_skills import BoardSkillRepository
from zhangwen.hardware.hardware_skills import (
    HardwareSkillNotFoundError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
)
from zhangwen.hardware.models import HardwareSkillDetail
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.devices.device_packages import list_device_packages
from zhangwen.device_lab.boards import BOARDS
from zhangwen.skills.models import SkillDefinition
from zhangwen.skills.repository import SkillRepository
from zhangwen.domains.simulation.catalog import SimulationCatalog


@dataclass(frozen=True)
class LegacyPackageSnapshot:
    package_id: str
    kind: PackageKind
    slug: str
    display_name: str
    source_type: str
    source_key: str
    files: dict[str, str]


def legacy_package_snapshots(
    data_dir: Path,
    db_path: Path,
) -> tuple[LegacyPackageSnapshot, ...]:
    snapshots: list[LegacyPackageSnapshot] = []
    for package in AgentPackageRepository(data_dir).list_packages():
        detail = AgentPackageRepository(data_dir).get_package(package.expertType)
        package_id = f"agent-package:{detail.skillName}"
        files = {item.path: item.content for item in detail.files}
        manifest = {
            "schemaVersion": 1,
            "id": package_id,
            "kind": PackageKind.AGENT_PACKAGE.value,
            "displayName": detail.displayName,
            "version": detail.revision,
            "channel": "stable",
            "capabilities": list(detail.supportedArtifactTypes),
            "permissions": [],
            "riskLevel": "medium",
            "confirmationPolicy": "before_external_effect",
            "entrypoints": {"prompt": "SKILL.md"},
            "compatibility": {"legacyExpertType": detail.expertType.value},
            "evidence": {},
            "files": sorted(files),
        }
        files["manifest.json"] = _dump(manifest)
        snapshots.append(
            LegacyPackageSnapshot(
                package_id=package_id,
                kind=PackageKind.AGENT_PACKAGE,
                slug=detail.skillName,
                display_name=detail.displayName,
                source_type="AGENT_PACKAGE",
                source_key=detail.skillName,
                files=files,
            )
        )

    for skill in SkillRepository(db_path).list_skills():
        snapshots.append(_skill_snapshot(skill))
    seed_default_components(db_path)
    hardware_details = _hardware_skill_details(data_dir, db_path)
    snapshots.extend(_board_device_snapshots(hardware_details))
    snapshots.extend(_project_learning_board_snapshots())
    snapshots.extend(_hardware_device_snapshots(hardware_details))
    snapshots.append(_mqtt_service_snapshot())
    return tuple(snapshots)


def _mqtt_service_snapshot() -> LegacyPackageSnapshot:
    package_id = "service-package:mqtt-local"
    files = {
        "README.md": (
            "# 掌问设备通信服务\n\n"
            "由 FastAPI Sidecar 监管；桌面前端不得直接连接、配置或持有服务凭据。\n"
        ),
        "service.json": _dump(
            {
                "schema": "zhangwen.service.mqtt/v1",
                "modes": ["SIMULATED", "LOOPBACK", "LAN", "EXTERNAL"],
                "namespace": "zhangwen/1/{workId}",
                "supervision": {
                    "shell": False,
                    "singleLocalProcess": True,
                    "credentialStore": "windows-credential-manager",
                },
            }
        ),
    }
    manifest = {
        "schemaVersion": 1,
        "id": package_id,
        "kind": PackageKind.SERVICE_PACKAGE.value,
        "displayName": "掌问设备通信服务",
        "version": "1.0.0",
        "channel": "stable",
        "capabilities": ["mqtt_service", "topic_contract", "telemetry_bridge"],
        # The package declares capabilities, but receives no host primitive.
        # The Sidecar supervisor owns the fixed process/network/credential ports.
        "permissions": [],
        "riskLevel": "high",
        "confirmationPolicy": "before_external_effect",
        "entrypoints": {"handler": "sidecar:mqtt-supervisor-v1"},
        "compatibility": {"contractVersion": 1},
        "evidence": {"automatic": "simulator-and-controlled-process-only"},
        "files": sorted(files),
    }
    files["manifest.json"] = _dump(manifest)
    return LegacyPackageSnapshot(
        package_id=package_id,
        kind=PackageKind.SERVICE_PACKAGE,
        slug="mqtt-local",
        display_name="掌问设备通信服务",
        source_type="BUILTIN_SERVICE",
        source_key="mqtt-local-v1",
        files=files,
    )


def _skill_snapshot(skill: SkillDefinition) -> LegacyPackageSnapshot:
    package_id = f"skill-package:{skill.id}"
    input_schema_path = "schemas/input.json"
    output_schema_path = "schemas/output.json"
    entry_path = "SKILL.md"
    permissions = [permission.value for permission in skill.permissions]
    files = {
        entry_path: (
            f"---\nname: {skill.id}\ndescription: {json.dumps(skill.description, ensure_ascii=False)}\n---\n\n"
            f"# {skill.name}\n\n{skill.description}\n"
        ),
        input_schema_path: _dump(skill.inputSchema.model_dump(mode="json", exclude_none=True)),
        output_schema_path: _dump(skill.outputSchema.model_dump(mode="json", exclude_none=True)),
    }
    manifest = {
        "schemaVersion": 1,
        "id": package_id,
        "kind": PackageKind.SKILL_PACKAGE.value,
        "displayName": skill.name,
        "version": "legacy-stable",
        "channel": "stable",
        "capabilities": list(skill.artifactTypes),
        "permissions": permissions,
        "riskLevel": skill.riskLevel.value,
        "confirmationPolicy": skill.confirmationPolicy.value,
        "entrypoints": {
            "prompt": entry_path,
            "inputSchema": input_schema_path,
            "outputSchema": output_schema_path,
            "handler": "plugin-host:manifest-v1",
        },
        "compatibility": {
            "legacySkillId": skill.id,
            "ownerExpert": skill.ownerExpert.value,
        },
        "evidence": {},
        "files": sorted(files),
    }
    files["manifest.json"] = _dump(manifest)
    return LegacyPackageSnapshot(
        package_id=package_id,
        kind=PackageKind.SKILL_PACKAGE,
        slug=skill.id,
        display_name=skill.name,
        source_type="SKILL",
        source_key=skill.id,
        files=files,
    )


def _board_device_snapshots(
    hardware_details: list[HardwareSkillDetail],
) -> list[LegacyPackageSnapshot]:
    snapshots: list[LegacyPackageSnapshot] = []
    skill_repository = BoardSkillRepository()
    skill_profiles = {
        "dfrobot/dfrobot_k10": "unihiker-k10",
        "seeedstudio/xiao_esp32s3_sense": "xiao-esp32s3-sense",
    }
    hardware_components = {
        detail.componentId: detail for detail in hardware_details
    }
    board_components = {
        "dfrobot/dfrobot_k10": "hw_seed_unihiker_k10",
        "seeedstudio/xiao_esp32s3_sense": "hw_seeed_xiao_esp32s3_sense",
    }
    for declaration in list_device_packages():
        board_id = declaration.id.value
        profile_id = skill_profiles[board_id]
        package_id = f"device-package:board:{board_id.replace('/', '-')}"
        board_skill = skill_repository.package_for_profile(profile_id, required=False)
        if board_skill is None:
            instructions = f"# {declaration.display_name}\n\n只使用已验证的设备包事实。\n"
            skill_evidence: dict[str, object] = {"available": False}
        else:
            instructions = board_skill.read_text("SKILL.md", max_chars=16_000)
            skill_evidence = board_skill.summary.model_dump(mode="json")
        hardware_skill = hardware_components.get(board_components[board_id])
        hardware_evidence = (
            {
                "available": True,
                "skillName": hardware_skill.skillName,
                "revision": hardware_skill.revision,
                "verificationStatus": hardware_skill.verificationStatus,
                "sourceKind": hardware_skill.sourceKind.value,
            }
            if hardware_skill is not None
            else {"available": False}
        )
        channel_facts = [
            {
                "id": item.id.value,
                "runtime": item.runtime,
                "connectionContract": item.connection_contract,
                "requiresPairing": item.requires_pairing,
                "requiresFileReadback": item.requires_file_readback,
                "interactiveConsole": item.interactive_console,
            }
            for item in declaration.deployment_channels
        ]
        facts = {
            "schema": "zhangwen.device-technical-facts/v1",
            "deviceClass": "BOARD",
            "boardId": board_id,
            "boardProfileId": profile_id,
            "capabilities": list(declaration.capabilities),
            "deploymentChannels": channel_facts,
            "simulationModes": list(declaration.simulation_modes),
            "source": declaration.source,
            "boardCapability": BOARDS[declaration.id].model_dump(mode="json"),
            "boardSkillEvidence": skill_evidence,
            "hardwareSkill": (
                hardware_skill.specification.model_dump(mode="json")
                if hardware_skill is not None
                else None
            ),
            "hardwareSkillEvidence": hardware_evidence,
        }
        files = {
            "SKILL.md": instructions,
            "technical-facts.json": _dump(facts),
        }
        if hardware_skill is not None:
            files.update(
                {
                    f"hardware-skill/{item.path}": item.content
                    for item in hardware_skill.files
                    if item.path != "manifest.json"
                }
            )
        manifest = {
            "schemaVersion": 1,
            "id": package_id,
            "kind": PackageKind.DEVICE_PACKAGE.value,
            "displayName": declaration.display_name,
            "version": declaration.version,
            "channel": "stable",
            "capabilities": list(declaration.capabilities),
            "permissions": [],
            "riskLevel": "medium",
            "confirmationPolicy": "before_external_effect",
            "entrypoints": {"prompt": "SKILL.md"},
            "compatibility": {
                "deviceClass": "BOARD",
                "boardId": board_id,
                "boardProfileId": profile_id,
                "deploymentChannels": [item["id"] for item in channel_facts],
                "runtime": "MICROPYTHON",
            },
            "evidence": {
                "boardSkill": skill_evidence,
                "hardwareSkill": hardware_evidence,
            },
            "files": sorted(files),
        }
        files["manifest.json"] = _dump(manifest)
        snapshots.append(
            LegacyPackageSnapshot(
                package_id=package_id,
                kind=PackageKind.DEVICE_PACKAGE,
                slug=f"board-{profile_id}",
                display_name=declaration.display_name,
                source_type="DEVICE_BOARD",
                source_key=board_id,
                files=files,
            )
        )
    return snapshots


def _project_learning_board_snapshots() -> list[LegacyPackageSnapshot]:
    """Expose S3/C3 reference targets through the one versioned device platform.

    These packages assert a chip/runtime probe contract only. They deliberately
    do not claim that an arbitrary commercial board has passed physical tests.
    """

    snapshots: list[LegacyPackageSnapshot] = []
    for board in SimulationCatalog.load_builtin().boards:
        board_key = board.revision_id.rsplit("@", 1)[0]
        package_id = f"device-package:board:{board.slug}"
        facts = {
            "schema": "zhangwen.device-technical-facts/v1",
            "deviceClass": "BOARD",
            "boardId": board_key,
            "boardProfileRevisionId": board.revision_id,
            "chipFamily": board.chip_family.value,
            "capabilities": ["code", "simulation", "serial_observation"],
            "deploymentChannels": [
                {
                    "id": "USB_SERIAL",
                    "runtime": "MICROPYTHON",
                    "connectionContract": "MICROPYTHON_IDENTITY_V1",
                    "requiresPairing": False,
                    "requiresFileReadback": True,
                    "interactiveConsole": True,
                }
            ],
            "knownLimitations": board.known_limitations,
            "source": "project-learning-reference",
        }
        files = {
            "SKILL.md": (
                f"# {board.display_name}\n\n"
                "仅在本地身份探针确认 MicroPython、ESP32 平台和目标芯片族后，"
                "使用文件级上传。不得据此声称具体商品板已经通过真机验收。\n"
            ),
            "technical-facts.json": _dump(facts),
        }
        manifest = {
            "schemaVersion": 1,
            "id": package_id,
            "kind": PackageKind.DEVICE_PACKAGE.value,
            "displayName": board.display_name,
            "version": board.revision_id,
            "channel": "stable",
            "capabilities": ["code", "simulation", "serial_observation"],
            "permissions": [],
            "riskLevel": "medium",
            "confirmationPolicy": "before_external_effect",
            "entrypoints": {"prompt": "SKILL.md"},
            "compatibility": {
                "deviceClass": "BOARD",
                "boardId": board_key,
                "boardProfileRevisionId": board.revision_id,
                "chipFamily": board.chip_family.value,
                "deploymentChannels": ["USB_SERIAL"],
                "runtime": "MICROPYTHON",
            },
            "evidence": {
                "verificationStatus": "REFERENCE_PROFILE",
                "physicalBoardValidated": False,
            },
            "files": sorted(files),
        }
        files["manifest.json"] = _dump(manifest)
        snapshots.append(
            LegacyPackageSnapshot(
                package_id=package_id,
                kind=PackageKind.DEVICE_PACKAGE,
                slug=f"board-{board.slug}",
                display_name=board.display_name,
                source_type="DEVICE_BOARD",
                source_key=board_key,
                files=files,
            )
        )
    return snapshots


def _hardware_skill_details(
    data_dir: Path,
    db_path: Path,
) -> list[HardwareSkillDetail]:
    repository = HardwareSkillRepository(data_dir, db_path)
    details: list[HardwareSkillDetail] = []
    for summary in repository.list_skills():
        try:
            details.append(repository.get_skill(summary.skillName))
        except (HardwareSkillNotFoundError, HardwareSkillValidationError):
            continue
    return details


def _hardware_device_snapshots(
    hardware_details: list[HardwareSkillDetail],
) -> list[LegacyPackageSnapshot]:
    snapshots: list[LegacyPackageSnapshot] = []
    for detail in hardware_details:
        # Controller boards already have one canonical DEVICE_BOARD package that
        # combines the board profile and Board Skill.  Do not create a second
        # DEVICE_PACKAGE for the same physical board from its legacy catalog row.
        if detail.category.value == "MCU":
            continue
        package_id = f"device-package:component:{detail.componentId}"
        files = {
            item.path: item.content
            for item in detail.files
            if item.path != "manifest.json"
        }
        files["technical-facts.json"] = _dump(
            {
                "schema": "zhangwen.device-technical-facts/v1",
                "deviceClass": "COMPONENT",
                "componentId": detail.componentId,
                "category": detail.category.value,
                "electrical": detail.specification.electrical.model_dump(mode="json"),
                "ageRecommendation": detail.specification.ageRecommendation,
                "safetyTags": detail.specification.safetyTags,
                "verificationStatus": detail.specification.verificationStatus,
                "sourceIds": detail.specification.sourceIds,
                "mechanicalProfile": detail.mechanicalProfile,
            }
        )
        manifest = {
            "schemaVersion": 1,
            "id": package_id,
            "kind": PackageKind.DEVICE_PACKAGE.value,
            "displayName": detail.displayName,
            "version": detail.revision,
            "channel": "stable",
            "capabilities": ["technical_facts", detail.category.value.lower()],
            "permissions": [],
            "riskLevel": "medium" if detail.specification.safetyTags else "low",
            "confirmationPolicy": "before_external_effect",
            "entrypoints": {"prompt": "SKILL.md"},
            "compatibility": {
                "deviceClass": "COMPONENT",
                "legacyHardwareSkillName": detail.skillName,
                "componentId": detail.componentId,
                "deploymentChannels": [],
                "runtime": None,
            },
            "evidence": {
                "verificationStatus": detail.verificationStatus,
                "sourceKind": detail.sourceKind.value,
                "sourceIds": detail.specification.sourceIds,
            },
            "files": sorted(files),
        }
        files["manifest.json"] = _dump(manifest)
        snapshots.append(
            LegacyPackageSnapshot(
                package_id=package_id,
                kind=PackageKind.DEVICE_PACKAGE,
                slug=f"component-{detail.skillName}",
                display_name=detail.displayName,
                source_type="HARDWARE_SKILL",
                source_key=detail.skillName,
                files=files,
            )
        )
    return snapshots


def _dump(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
