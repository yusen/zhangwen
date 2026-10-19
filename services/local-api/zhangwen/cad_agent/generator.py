"""Deterministic CAD template generator.

This module deliberately does not execute user Python or import CadQuery. It
produces auditable STEP/STL-like previews from bounded template parameters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from zhangwen.cad_agent.models import (
    CadFileKind,
    CadParameter,
    CadTemplateKind,
    CadValidation,
    CadValidationCheck,
)
from zhangwen.cad_agent.template_catalog import (
    BOX_WITH_LID_PARAMETER_SPECS,
    COMPONENT_MOUNT_PARAMETER_SPECS,
)
from zhangwen.specs.models import SpecRun


@dataclass(frozen=True)
class GeneratedCadFile:
    kind: CadFileKind
    path: str
    mime_type: str
    content: str


@dataclass(frozen=True)
class GeneratedCad:
    template_kind: CadTemplateKind
    command_label: str
    parameters: list[CadParameter]
    validation: CadValidation
    files: list[GeneratedCadFile]


def generate_cad_from_spec(
    spec: SpecRun,
    *,
    template_kind: CadTemplateKind,
    overrides: dict[str, float] | None = None,
    now: str,
) -> GeneratedCad:
    selected = template_kind
    parameters = _parameters(selected, overrides or {})
    validation = _validate(selected, parameters)
    slug = selected.value.lower()
    payload = {
        "template": selected.value,
        "specRunId": spec.id,
        "generatedAt": now,
        "commandLabel": "cadquery-template-dry-run",
        "parameters": [parameter.model_dump(mode="json") for parameter in parameters],
        "validation": validation.model_dump(mode="json"),
        "note": "Deterministic template preview; no user Python or CadQuery runtime executed.",
    }
    files = [
        GeneratedCadFile(
            kind=CadFileKind.PARAMETERS,
            path=f"cad/{slug}/parameters.json",
            mime_type="application/json",
            content=json.dumps(payload, ensure_ascii=False, indent=2),
        ),
        GeneratedCadFile(
            kind=CadFileKind.STEP,
            path=f"cad/{slug}/model.step",
            mime_type="model/step",
            content=_step_preview(selected, parameters, validation, spec.id),
        ),
        GeneratedCadFile(
            kind=CadFileKind.STL,
            path=f"cad/{slug}/model.stl",
            mime_type="model/stl",
            content=_stl_preview(selected, parameters, validation),
        ),
    ]
    return GeneratedCad(
        template_kind=selected,
        command_label="cadquery-template-dry-run",
        parameters=parameters,
        validation=validation,
        files=files,
    )


def _parameters(
    template_kind: CadTemplateKind,
    overrides: dict[str, float],
) -> list[CadParameter]:
    specs = template_specs()[template_kind]
    result: list[CadParameter] = []
    for name, label, unit, default, min_value, max_value in specs:
        value = float(overrides.get(name, default))
        result.append(
            CadParameter(
                name=name,
                label=label,
                unit=unit,
                value=value,
                min=float(min_value),
                max=float(max_value),
            )
        )
    return result


def template_specs() -> dict[CadTemplateKind, list[tuple[str, str, str, float, float, float]]]:
    common = [
        ("width", "宽度", "mm", 48, 10, 180),
        ("height", "高度", "mm", 36, 10, 160),
        ("thickness", "厚度", "mm", 3, 1, 12),
        ("mount_holes", "安装孔数量", "count", 4, 2, 8),
        ("hole_diameter", "安装孔直径", "mm", 3, 1, 8),
    ]
    return {
        CadTemplateKind.COMPONENT_MOUNT: [
            spec.as_legacy_tuple() for spec in COMPONENT_MOUNT_PARAMETER_SPECS
        ],
        CadTemplateKind.FREEFORM_STRUCTURE: [],
        CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM: [],
        CadTemplateKind.SENSOR_BRACKET: common,
        CadTemplateKind.MCU_MOUNT: [
            ("width", "宽度", "mm", 62, 20, 200),
            ("height", "高度", "mm", 45, 20, 180),
            ("standoff_height", "铜柱高度", "mm", 8, 3, 30),
            ("mount_holes", "安装孔数量", "count", 4, 2, 8),
            ("hole_diameter", "安装孔直径", "mm", 3, 1, 8),
        ],
        CadTemplateKind.MOTOR_MOUNT: [
            ("width", "宽度", "mm", 50, 20, 180),
            ("height", "高度", "mm", 55, 20, 180),
            ("shaft_clearance", "轴孔避让", "mm", 12, 4, 40),
            ("thickness", "厚度", "mm", 4, 2, 16),
            ("mount_holes", "安装孔数量", "count", 4, 2, 8),
        ],
        CadTemplateKind.SERVO_MOUNT: [
            ("width", "宽度", "mm", 42, 20, 120),
            ("height", "高度", "mm", 24, 12, 80),
            ("tab_length", "耳片长度", "mm", 8, 3, 30),
            ("thickness", "厚度", "mm", 3, 1, 10),
            ("mount_holes", "安装孔数量", "count", 4, 2, 8),
        ],
        CadTemplateKind.SIMPLE_ENCLOSURE: [
            ("width", "外壳宽度", "mm", 90, 30, 220),
            ("height", "外壳高度", "mm", 60, 30, 200),
            ("depth", "外壳深度", "mm", 35, 15, 140),
            ("wall_thickness", "壁厚", "mm", 2, 1, 8),
            ("lid_clearance", "盖板间隙", "mm", 0.4, 0.1, 2),
        ],
        CadTemplateKind.PANEL_CUTOUT: [
            ("width", "面板宽度", "mm", 80, 20, 220),
            ("height", "面板高度", "mm", 50, 20, 180),
            ("cutout_width", "开孔宽度", "mm", 24, 4, 100),
            ("cutout_height", "开孔高度", "mm", 14, 4, 80),
            ("thickness", "厚度", "mm", 3, 1, 10),
        ],
        CadTemplateKind.BOX_WITH_LID: [
            spec.as_legacy_tuple() for spec in BOX_WITH_LID_PARAMETER_SPECS
        ],
    }


def _validate(
    template_kind: CadTemplateKind,
    parameters: list[CadParameter],
) -> CadValidation:
    checks: list[CadValidationCheck] = []
    values = {parameter.name: parameter.value for parameter in parameters}
    for parameter in parameters:
        ok = parameter.min <= parameter.value <= parameter.max
        checks.append(
            CadValidationCheck(
                dimension=f"parameter:{parameter.name}",
                severity="PASS" if ok else "FAIL",
                message=(
                    f"{parameter.label}在允许范围内"
                    if ok
                    else f"{parameter.label}超出允许范围"
                ),
                details=f"{parameter.value:g}{parameter.unit}; range {parameter.min:g}-{parameter.max:g}{parameter.unit}",
            )
        )
    width = values.get("width", 1)
    height = values.get("height", 1)
    thickness = values.get("thickness", values.get("wall_thickness", 1))
    checks.append(
        CadValidationCheck(
            dimension="geometry:positive-volume",
            severity="PASS" if width > 0 and height > 0 and thickness > 0 else "FAIL",
            message="基础体积参数有效" if width > 0 and height > 0 and thickness > 0 else "基础体积参数无效",
            details=f"template={template_kind.value}; width={width:g}; height={height:g}; thickness={thickness:g}",
        )
    )
    if "hole_diameter" in values:
        hole_ok = values["hole_diameter"] < min(width, height) / 3
        checks.append(
            CadValidationCheck(
                dimension="geometry:hole-clearance",
                severity="PASS" if hole_ok else "FAIL",
                message="安装孔避让通过" if hole_ok else "安装孔直径过大",
                details=f"hole={values['hole_diameter']:g}; width={width:g}; height={height:g}",
            )
        )
    ok = all(check.severity != "FAIL" for check in checks)
    return CadValidation(ok=ok, checks=checks)


def _step_preview(
    template_kind: CadTemplateKind,
    parameters: list[CadParameter],
    validation: CadValidation,
    spec_run_id: str,
) -> str:
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('Zhangwen CAD template {template_kind.value}'),'2;1');",
        "ENDSEC;",
        "DATA;",
        f"#1=PRODUCT('{template_kind.value}','controlled-template','spec:{spec_run_id}',());",
    ]
    for index, parameter in enumerate(parameters, start=10):
        lines.append(
            f"#{index}=PROPERTY('{parameter.name}','{parameter.value:g}{parameter.unit}');"
        )
    lines.extend(
        [
            f"#99=PROPERTY('validation','{'ok' if validation.ok else 'failed'}');",
            "ENDSEC;",
            "END-ISO-10303-21;",
        ]
    )
    return "\n".join(lines) + "\n"


def _stl_preview(
    template_kind: CadTemplateKind,
    parameters: list[CadParameter],
    validation: CadValidation,
) -> str:
    values = {parameter.name: parameter.value for parameter in parameters}
    width = values.get("width", 10)
    height = values.get("height", 10)
    depth = values.get("depth", values.get("thickness", 3))
    return "\n".join(
        [
            f"solid zhangwen_{template_kind.value.lower()}",
            f"  facet normal 0 0 1",
            "    outer loop",
            f"      vertex 0 0 0",
            f"      vertex {width:g} 0 0",
            f"      vertex 0 {height:g} {depth:g}",
            "    endloop",
            "  endfacet",
            f"  // validation={'ok' if validation.ok else 'failed'}",
            f"endsolid zhangwen_{template_kind.value.lower()}",
            "",
        ]
    )
