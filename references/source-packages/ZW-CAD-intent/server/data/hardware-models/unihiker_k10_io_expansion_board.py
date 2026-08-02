import cadquery as cq

# =========================
# 参数区，单位：mm
# =========================
hardware_name = "micro:bit掌控IO扩展板子"

# 主 PCB
pcb_length = 80.0
pcb_width = 47.0
pcb_thickness = 1.6
pcb_corner_radius = 2.0

# 底板
bottom_plate_thickness = 1.6
board_gap = 3.5

# 铜柱
standoff_diameter = 4.0
standoff_height = board_gap
standoff_edge_offset = 8.0

# 顶部开关
switch_length = 6.7
switch_width = 13.0
switch_height = 6.6
switch_center_x = pcb_length / 2 - switch_length / 2
switch_center_y = pcb_width / 2 - pcb_corner_radius - switch_width / 2

# 拨杆
lever_size = 4.0
lever_height = 5.0

# K10 插槽
slot_length = 57.0
slot_width = 13.7
slot_height = 15.6
slot_cutout_length = 52.0
slot_cutout_width = 2.0


def rounded_plate(length, width, thickness, radius, z_min):
    return (
        cq.Workplane("XY")
        .box(length, width, thickness, centered=(True, True, False))
        .edges("|Z")
        .fillet(radius)
        .translate((0, 0, z_min))
    )


pcb = rounded_plate(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius, 0)

bottom_plate = rounded_plate(
    pcb_length,
    pcb_width,
    bottom_plate_thickness,
    pcb_corner_radius,
    -(board_gap + bottom_plate_thickness),
)

standoff_x = pcb_length / 2 - standoff_edge_offset
standoff_y = pcb_width / 2 - standoff_edge_offset
standoffs = None
for x in (-standoff_x, standoff_x):
    for y in (-standoff_y, standoff_y):
        post = (
            cq.Workplane("XY")
            .circle(standoff_diameter / 2)
            .extrude(standoff_height)
            .translate((x, y, -board_gap))
        )
        standoffs = post if standoffs is None else standoffs.union(post)

switch_body = (
    cq.Workplane("XY")
    .box(switch_length, switch_width, switch_height, centered=(True, True, False))
    .translate((switch_center_x, switch_center_y, pcb_thickness))
)

switch_lever = (
    cq.Workplane("XY")
    .box(lever_size, lever_size, lever_height, centered=(True, True, False))
    .translate((switch_center_x, switch_center_y, pcb_thickness + switch_height))
)

slot_body = cq.Workplane("XY").box(
    slot_length,
    slot_width,
    slot_height,
    centered=(True, True, False),
)

slot_cutout = (
    cq.Workplane("XY")
    .box(slot_cutout_length, slot_cutout_width, slot_height + 0.6, centered=(True, True, False))
    .translate((0, 0, -0.3))
)

k10_slot = slot_body.cut(slot_cutout).translate((0, 0, pcb_thickness))

result = (
    pcb
    .union(bottom_plate)
    .union(standoffs)
    .union(switch_body)
    .union(switch_lever)
    .union(k10_slot)
)

show_object(result, name=hardware_name)
