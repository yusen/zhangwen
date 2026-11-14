"""ESP32C3-CORE visual reference, mm; heights/components are provisional.

Not a manufacturing model. No mounting screw holes are declared. This file is
inert in Hardware Skill; the web worker only consumes checked primitive data.
"""
import cadquery as cq


def box(identifier, size, center, role="feature", operation="add"):
    return dict(primitive_id=identifier, kind="box", operation=operation,
                size=dict(zip(("length_x", "width_y", "height_z"), size)),
                center=dict(zip(("x", "y", "z"), center)), role=role)


PRIMITIVES = [
    box("pcb", (51, 21, 1.6), (.5, 0, -1.7), "pcb"),
    box("usb_shell", (7.5, 9, 3.2), (-22.255, 0, .7), "connector"),
    box("usb_mouth", (3, 7, 2.2), (-25.5, 0, .7), "feature", "cut"),
    box("mcu", (5, 5, 1), (6.5, 0, -.4), "body"),
    box("flash", (6, 5, 1.5), (-3, 0, -.15), "body"),
    box("uart_bridge", (4, 4, 1), (-14, 0, -.4), "body"),
    box("regulator", (3, 3, 1), (-17, 5, -.4), "body"),
    box("rst_body", (4, 4, 2), (-9, -5.5, .1)),
    box("boot_body", (4, 4, 2), (-9, 5.5, .1)),
    dict(primitive_id="rst_cap", kind="cylinder", operation="add", diameter=2.6,
         height=.7, center=dict(x=-9, y=-5.5, z=1.45), role="feature"),
    dict(primitive_id="boot_cap", kind="cylinder", operation="add", diameter=2.6,
         height=.7, center=dict(x=-9, y=5.5, z=1.45), role="feature"),
    box("pad_row_left", (40, 2, .08), (.5, -8.89, -.86), "connector"),
    box("pad_row_right", (40, 2, .08), (.5, 8.89, -.86), "connector"),
    box("antenna_region", (6, 18, .08), (22.5, 0, -.86)),
    box("d4", (2, 1, .6), (-22, -7, -.6)),
    box("d5", (2, 1, .6), (-22, 7, -.6)),
]


def primitive_shape(p):
    if p["kind"] == "cylinder":
        shape = cq.Workplane("XY").cylinder(p["height"], p["diameter"] / 2)
    else:
        size = p["size"]
        shape = cq.Workplane("XY").box(size["length_x"], size["width_y"], size["height_z"])
    center = p["center"]
    return shape.translate((center["x"], center["y"], center["z"]))


def build():
    result = None
    for primitive in PRIMITIVES:
        part = primitive_shape(primitive)
        result = part if result is None else (
            result.cut(part) if primitive["operation"] == "cut" else result.union(part))
    return result
