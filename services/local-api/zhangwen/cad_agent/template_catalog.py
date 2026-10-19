"""Bounded parameter catalog for the production CAD templates."""

from __future__ import annotations

from dataclasses import dataclass

from zhangwen.cad_agent.models import CadTemplateKind


@dataclass(frozen=True)
class CadTemplateParameterSpec:
    name: str
    label: str
    unit: str
    default: float
    minimum: float
    maximum: float
    allowed_values: tuple[float, ...] = ()

    def as_legacy_tuple(self) -> tuple[str, str, str, float, float, float]:
        return (
            self.name,
            self.label,
            self.unit,
            self.default,
            self.minimum,
            self.maximum,
        )

    def accepts(self, value: float) -> bool:
        if not self.minimum <= value <= self.maximum:
            return False
        return not self.allowed_values or value in self.allowed_values


BOX_WITH_LID_PARAMETER_SPECS: tuple[CadTemplateParameterSpec, ...] = (
    CadTemplateParameterSpec("width", "盒体宽度", "mm", 100, 30, 240),
    CadTemplateParameterSpec("height", "盒体高度", "mm", 70, 15, 160),
    CadTemplateParameterSpec("depth", "盒体深度", "mm", 45, 30, 220),
    CadTemplateParameterSpec("wall_thickness", "壁厚", "mm", 2.4, 0.8, 12),
    CadTemplateParameterSpec("floor_thickness", "底板厚度", "mm", 2.4, 0.8, 12),
    CadTemplateParameterSpec("lid_thickness", "上盖厚度", "mm", 3, 0.8, 12),
    CadTemplateParameterSpec("lid_lip_height", "盖唇高度", "mm", 4, 1, 20),
    CadTemplateParameterSpec("lid_lip_thickness", "盖唇厚度", "mm", 1.6, 0.8, 8),
    CadTemplateParameterSpec("lid_clearance", "盖板配合间隙", "mm", 0.35, 0.1, 2),
    CadTemplateParameterSpec("corner_radius", "外壳圆角", "mm", 5, 0, 40),
    CadTemplateParameterSpec("hardware_gap", "器件间隙", "mm", 5, 0, 30),
    CadTemplateParameterSpec("edge_clearance", "边缘间隙", "mm", 8, 0, 40),
    CadTemplateParameterSpec(
        "screw_posts",
        "上盖螺丝柱数量",
        "count",
        4,
        0,
        4,
        allowed_values=(0, 4),
    ),
    CadTemplateParameterSpec("screw_boss_diameter", "螺丝柱外径", "mm", 8, 4, 20),
    CadTemplateParameterSpec("screw_hole_diameter", "螺丝孔直径", "mm", 2.4, 1, 8),
    CadTemplateParameterSpec("screw_post_edge_inset", "螺丝柱边距", "mm", 8, 3, 40),
)

COMPONENT_MOUNT_PARAMETER_SPECS: tuple[CadTemplateParameterSpec, ...] = (
    CadTemplateParameterSpec("base_thickness", "安装底座厚度", "mm", 3.0, 1.2, 12.0),
    CadTemplateParameterSpec("edge_margin", "器件外侧边框宽度", "mm", 7.0, 4.0, 30.0),
    CadTemplateParameterSpec("component_clearance", "器件装配间隙", "mm", 0.8, 0.2, 5.0),
    CadTemplateParameterSpec("retainer_height", "可拆压框高度", "mm", 3.0, 1.0, 20.0),
    CadTemplateParameterSpec("fastener_hole_diameter", "底座压框连接孔直径", "mm", 3.2, 1.5, 8.0),
    CadTemplateParameterSpec("corner_radius", "安装结构圆角", "mm", 3.0, 0.0, 20.0),
)


def production_template_parameter_specs(
    template_kind: CadTemplateKind,
) -> tuple[CadTemplateParameterSpec, ...]:
    if template_kind is CadTemplateKind.COMPONENT_MOUNT:
        return COMPONENT_MOUNT_PARAMETER_SPECS
    if template_kind is CadTemplateKind.FREEFORM_STRUCTURE:
        return ()
    if template_kind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM:
        return ()
    if template_kind is CadTemplateKind.BOX_WITH_LID:
        return BOX_WITH_LID_PARAMETER_SPECS
    raise KeyError(f"unsupported production CAD template: {template_kind.value}")


def production_parameter_spec(
    template_kind: CadTemplateKind,
    name: str,
) -> CadTemplateParameterSpec:
    for spec in production_template_parameter_specs(template_kind):
        if spec.name == name:
            return spec
    raise KeyError(f"unsupported CAD parameter: {template_kind.value}:{name}")


__all__ = [
    "BOX_WITH_LID_PARAMETER_SPECS",
    "COMPONENT_MOUNT_PARAMETER_SPECS",
    "CadTemplateParameterSpec",
    "production_parameter_spec",
    "production_template_parameter_specs",
]
