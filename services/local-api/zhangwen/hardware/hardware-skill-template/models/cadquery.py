"""器件 CadQuery 参考模型模板。

请把占位包络替换为已经验证的真实几何。该文件参与 Skill revision 和 SHA-256 校验，
但普通 Skill 保存不会直接执行它。
"""

import cadquery as cq


length_x = 30.0
width_y = 20.0
height_z = 8.0


def build_model():
    return cq.Workplane("XY").box(
        length_x,
        width_y,
        height_z,
        centered=(True, True, True),
    )


result = build_model()

if "show_object" in globals():
    show_object(result, name="<硬件显示名称>")
