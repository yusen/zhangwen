"""Deterministic Mock Spec Agent for ZW-010."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from zhangwen.hardware.models import (
    HardwareCategory,
    HardwareComponent,
    ValidationResult,
)
from zhangwen.proposals.models import ProposalVersion
from zhangwen.specs.models import (
    SpecContentDraft,
    SpecFileKind,
    SpecValidation,
    SpecValidationCheck,
)


@dataclass(frozen=True)
class GeneratedSpecFile:
    kind: SpecFileKind
    path: str
    content: str


@dataclass(frozen=True)
class GeneratedSpec:
    files: list[GeneratedSpecFile]
    validation: SpecValidation


def generate_spec_from_proposal(
    proposal: ProposalVersion,
    hardware_components: list[HardwareComponent],
    draft: SpecContentDraft,
    *,
    validate_hardware: Callable[[list[str]], ValidationResult],
) -> GeneratedSpec:
    selected = _select_mvp_components(hardware_components, draft.componentIds)
    validation_result = validate_hardware(
        [component.id for component in selected]
    )
    io_checks = _validate_io_suggestions(draft, selected)
    validation = SpecValidation(
        ok=(
            validation_result.overall.value != "FAIL"
            and all(check.severity != "FAIL" for check in io_checks)
        ),
        checks=[
            SpecValidationCheck(
                dimension=check.dimension,
                severity=check.severity.value,
                message=check.message,
                details=check.details,
            )
            for check in validation_result.checks
        ]
        + io_checks,
    )
    project_spec = {
        "project": {
            "name": draft.projectName,
            "proposal_id": proposal.id,
            "proposal_version": proposal.version,
            "goal": draft.goal,
        },
        "modules": [module.model_dump(mode="json") for module in draft.modules],
        "acceptance": draft.acceptance,
        "risks": draft.risks,
    }
    bom = {
        "components": [
            {
                "id": component.id,
                "name": component.name,
                "category": component.category.value,
                "quantity": 1,
                "driver": component.electrical.driverName,
                "notes": component.notes,
            }
            for component in selected
        ]
    }
    io_map = {
        "mcu": next((component.name for component in selected if component.category == HardwareCategory.MCU), "ESP32-S3 DevKitC"),
        "pins": [
            {
                "signal": item.signal,
                "pin": item.pin,
                "protocol": item.protocol,
                "component": _component_name_by_id(selected, item.componentId),
                "component_id": item.componentId,
            }
            for item in draft.ioSuggestions
        ],
        "validation": {
            "ok": validation.ok,
            "checks": [check.model_dump(mode="json") for check in validation.checks],
        },
    }
    return GeneratedSpec(
        files=[
            GeneratedSpecFile(
                kind=SpecFileKind.PROJECT_SPEC,
                path="spec/project_spec.yaml",
                content=_to_yaml(project_spec),
            ),
            GeneratedSpecFile(
                kind=SpecFileKind.BOM,
                path="spec/bom.yaml",
                content=_to_yaml(bom),
            ),
            GeneratedSpecFile(
                kind=SpecFileKind.IO_MAP,
                path="spec/io_map.yaml",
                content=_to_yaml(io_map),
            ),
        ],
        validation=validation,
    )


def _select_mvp_components(
    components: list[HardwareComponent],
    requested_ids: list[str],
) -> list[HardwareComponent]:
    preferred_ids = [
        "hw_seed_esp32_s3_devkit",
        "hw_seed_dht22",
        "hw_seed_mosfet_driver",
        "hw_seed_oled_096",
        "hw_seed_usb_5v_power",
        "hw_seed_breadboard",
    ]
    by_id = {component.id: component for component in components}
    selected = [by_id[item] for item in requested_ids if item in by_id]
    if not any(component.category == HardwareCategory.MCU for component in selected):
        selected = [
            *[by_id[item] for item in preferred_ids if item in by_id],
            *selected,
        ]
    selected_by_id = {component.id: component for component in selected}
    selected = list(selected_by_id.values())
    if selected:
        return selected
    return components[:6]


def _component_name(
    components: list[HardwareComponent],
    category: HardwareCategory,
) -> str:
    return next(
        (component.name for component in components if component.category == category),
        "待选择",
    )


def _component_name_by_id(
    components: list[HardwareComponent],
    component_id: str,
) -> str:
    return next(
        (component.name for component in components if component.id == component_id),
        "待选择",
    )


def _validate_io_suggestions(
    draft: SpecContentDraft,
    selected: list[HardwareComponent],
) -> list[SpecValidationCheck]:
    selected_ids = {component.id for component in selected}
    checks: list[SpecValidationCheck] = []
    for item in draft.ioSuggestions:
        known_component = item.componentId in selected_ids
        checks.append(
            SpecValidationCheck(
                dimension=f"io:{item.signal}",
                severity="PASS" if known_component else "FAIL",
                message=(
                    "IO 建议引用本地已选组件"
                    if known_component
                    else "IO 建议引用了未选择或不存在的组件"
                ),
                details=f"{item.signal} -> {item.pin} -> {item.componentId}",
            )
        )
    return checks


def _to_yaml(value, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}{key}: {_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}-")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{spaces}{_scalar(value)}"


def _scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if any(char in text for char in [":", "#", "\n", "{", "}", "[", "]"]):
        return '"' + text.replace('"', '\\"') + '"'
    return text
