"""
光效水杯 CadQuery 模板

BOM：
1. 行空板 K10 × 1
2. 行空板聚合物锂电池 × 1
3. RGB12 灯珠灯环 × 1

主体结构：
- 全局原点位于杯子底面中心，+Z 向上，-Y 为正面。
- 杯体外径 100mm、高 100mm、壁厚 3mm、底厚 3mm，顶部敞开。
- 把手中心线直径 80mm、圆管直径 12mm，位于 +Y 背面。
- 把手圆心为 (0, 65, 50)，圆环轴线沿 X；把手先与外杯体合并，再切除杯腔。
- RGB 灯环位于 -Y 正面，电池位于 -X 左侧，K10 位于 +X 右侧。
- 三个电子硬件仅作胶粘位置示意，不生成卡槽、避让孔、走线孔或螺丝结构。
- 灯环接线座和 K10 摄像头允许与杯壁示意穿插。

便于后续修改的对象：
- cup_outer：实心外杯体。
- handle_model：圆环把手。
- cup_inner_cutter：D94 杯腔切刀。
- main_body / result：完成杯腔切除后的可打印主体。
- rgb_ring_model、battery_model、k10_model：三个独立硬件模型。
- assembly：主体与全部硬件组成的非布尔装配体。

刻字说明：
- 当前代码不生成刻字。
- 杯体正面灯环周围、左右硬件上下方可作为后续图案或文字区域。
- 杯壁为曲面，后续刻字应单独建立圆柱局部坐标。
"""

import cadquery as cq
import math


# ============================================================
# 全局参数，单位：mm
# ============================================================
CUP_OUTER_DIAMETER = 100.0
CUP_HEIGHT = 100.0
CUP_WALL_THICKNESS = 3.0
CUP_BOTTOM_THICKNESS = 3.0
CUP_INNER_DIAMETER = CUP_OUTER_DIAMETER - 2.0 * CUP_WALL_THICKNESS
CUT_OVERLAP = 0.2

HANDLE_CENTERLINE_DIAMETER = 80.0
HANDLE_MAJOR_RADIUS = HANDLE_CENTERLINE_DIAMETER / 2.0
HANDLE_TUBE_DIAMETER = 12.0
HANDLE_TUBE_RADIUS = HANDLE_TUBE_DIAMETER / 2.0
HANDLE_CENTER_Y = 65.0
HANDLE_CENTER_Z = 50.0

HARDWARE_CENTER_Z = 50.0
CUP_OUTER_RADIUS = CUP_OUTER_DIAMETER / 2.0


# ============================================================
# 通用辅助函数
# ============================================================
def rounded_plate(length, width, thickness, radius, z_min=0.0):
    plate = (
        cq.Workplane("XY")
        .box(length, width, thickness, centered=(True, True, False))
        .translate((0.0, 0.0, z_min))
    )
    if radius > 0:
        try:
            plate = plate.edges("|Z").fillet(radius)
        except Exception:
            pass
    return plate


def box_from_z(length, width, height, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .box(length, width, height, centered=(True, True, False))
        .translate((center_x, center_y, z_min))
    )


def cylinder_from_z(diameter, height, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(height)
        .translate((center_x, center_y, z_min))
    )


# ============================================================
# 第一阶段：外杯体与圆环把手
# ============================================================
cup_outer = (
    cq.Workplane("XY")
    .circle(CUP_OUTER_DIAMETER / 2.0)
    .extrude(CUP_HEIGHT)
)

# 在经过 (0, 65, 50)、方向为 X 的轴线周围旋转圆形截面，生成完整圆环。
# 工作平面原点位于把手圆心；截面圆心距旋转轴 40mm，截面直径 12mm。
handle_model = (
    cq.Workplane("XY", origin=(0.0, HANDLE_CENTER_Y, HANDLE_CENTER_Z))
    .moveTo(0.0, HANDLE_MAJOR_RADIUS)
    .circle(HANDLE_TUBE_RADIUS)
    .revolve(360.0, (0.0, 0.0), (1.0, 0.0))
)

cup_with_handle = cup_outer.union(handle_model)


# ============================================================
# 第二阶段：切除杯腔
# ============================================================
# 切刀从 Z=3mm 开始并高出杯口 0.2mm，确保顶部完全敞开且无薄皮。
cup_inner_cutter = (
    cq.Workplane("XY")
    .circle(CUP_INNER_DIAMETER / 2.0)
    .extrude(CUP_HEIGHT - CUP_BOTTOM_THICKNESS + CUT_OVERLAP)
    .translate((0.0, 0.0, CUP_BOTTOM_THICKNESS))
)

# 把手已经与外杯体合并，因此同一次切除也会清理进入杯腔的把手材料。
main_body = cup_with_handle.cut(cup_inner_cutter)
result = main_body


# ============================================================
# 第三阶段：RGB12 灯珠灯环
# 原始坐标：灯环位于 XY 平面，+Z 为 LED 正面，接线座位于 -Z。
# ============================================================
def make_rgb_ring_model():
    pcb_inner_diameter = 27.0
    pcb_outer_diameter = 47.0
    pcb_thickness = 1.6
    pcb_inner_radius = pcb_inner_diameter / 2.0
    pcb_outer_radius = pcb_outer_diameter / 2.0

    led_count = 12
    led_size = 5.0
    led_height = 1.8
    led_center_radius = (pcb_inner_radius + pcb_outer_radius) / 2.0
    led_center_z = pcb_thickness + led_height / 2.0

    connector_length_x = 5.5
    connector_width_y = 10.0
    connector_height_z = 5.7
    connector_half_width_y = connector_width_y / 2.0
    connector_center_x = (
        math.sqrt(pcb_outer_radius ** 2 - connector_half_width_y ** 2)
        - connector_length_x / 2.0
        - 0.15
    )

    pcb_outer = (
        cq.Workplane("XY")
        .circle(pcb_outer_radius)
        .extrude(pcb_thickness)
    )
    pcb_inner = (
        cq.Workplane("XY")
        .circle(pcb_inner_radius)
        .extrude(pcb_thickness)
    )
    pcb = pcb_outer.cut(pcb_inner)

    led_seed = (
        cq.Workplane("XY")
        .box(led_size, led_size, led_height, centered=(True, True, True))
        .translate((led_center_radius, 0.0, led_center_z))
    )
    leds = None
    for index in range(led_count):
        led_part = led_seed.rotate(
            (0, 0, 0),
            (0, 0, 1),
            index * 360.0 / led_count,
        )
        leds = led_part if leds is None else leds.union(led_part)

    connector_pos = (
        cq.Workplane("XY")
        .box(
            connector_length_x,
            connector_width_y,
            connector_height_z,
            centered=(True, True, True),
        )
        .translate((connector_center_x, 0.0, -connector_height_z / 2.0))
    )
    connector_neg = (
        cq.Workplane("XY")
        .box(
            connector_length_x,
            connector_width_y,
            connector_height_z,
            centered=(True, True, True),
        )
        .translate((-connector_center_x, 0.0, -connector_height_z / 2.0))
    )

    return pcb.union(leds).union(connector_pos).union(connector_neg)


# 绕 X 轴 +90°：硬件 +Z→全局 -Y；PCB 基准面贴在杯体 -Y 切平面。
rgb_ring_model = (
    make_rgb_ring_model()
    .rotate((0, 0, 0), (1, 0, 0), 90)
    .translate((0.0, -CUP_OUTER_RADIUS, HARDWARE_CENTER_Z))
)


# ============================================================
# 第四阶段：行空板聚合物锂电池
# 原始坐标：48×32mm 大面位于 XY，厚度从 Z=0 向 +Z。
# ============================================================
def make_battery_model():
    length_x = 48.0
    width_y = 32.0
    thickness_z = 6.0
    body = rounded_plate(length_x, width_y, thickness_z, 2.0, 0.0)

    def wire_stub(center_y):
        return (
            cq.Workplane("YZ")
            .center(center_y, thickness_z / 2.0)
            .circle(0.4)
            .extrude(1.0)
            .translate((length_x / 2.0, 0.0, 0.0))
        )

    return body.union(wire_stub(1.5)).union(wire_stub(-1.5))


# 绕 Y 轴 -90°：电池 +Z 厚度方向→全局 -X，48mm 长边→全局 +Z。
battery_model = (
    make_battery_model()
    .rotate((0, 0, 0), (0, 1, 0), -90)
    .translate((-CUP_OUTER_RADIUS, 0.0, HARDWARE_CENTER_Z))
)


# ============================================================
# 第五阶段：行空板 K10
# 原始坐标：PCB 中心位于 XY 原点，PCB 从 Z=0 向 +Z。
# ============================================================
def make_k10_model():
    pcb_length = 83.2
    pcb_width = 51.3
    pcb_thickness = 1.6
    pcb_corner_radius = 1.0

    frame_length = 71.0
    frame_width = 51.0
    frame_height = 4.0
    frame_center_x = -pcb_length / 2.0 + 5.5 + frame_length / 2.0

    display_length = 57.5
    display_width = 43.0
    display_recess = 1.0
    frame_min_x = frame_center_x - frame_length / 2.0
    display_center_x = frame_min_x + 10.0 + display_length / 2.0
    display_surface_z = pcb_thickness + frame_height - display_recess

    camera_x = -12.0
    camera_block_size = 8.0
    camera_block_height = 2.5
    camera_diameter = 8.0
    camera_height = 2.5
    lens_diameter = 2.5
    lens_recess = 1.0

    gold_length = 7.0
    gold_thickness = 0.06
    gold_center_x = pcb_length / 2.0 - gold_length / 2.0

    pcb = rounded_plate(
        pcb_length,
        pcb_width,
        pcb_thickness,
        pcb_corner_radius,
        0.0,
    )
    top_gold = rounded_plate(
        gold_length,
        pcb_width,
        gold_thickness,
        pcb_corner_radius,
        pcb_thickness,
    ).translate((gold_center_x, 0.0, 0.0))
    bottom_gold = rounded_plate(
        gold_length,
        pcb_width,
        gold_thickness,
        pcb_corner_radius,
        -gold_thickness,
    ).translate((gold_center_x, 0.0, 0.0))

    frame = box_from_z(
        frame_length,
        frame_width,
        frame_height,
        frame_center_x,
        0.0,
        pcb_thickness,
    )
    frame = frame.cut(
        box_from_z(
            display_length,
            display_width,
            display_recess + 0.2,
            display_center_x,
            0.0,
            display_surface_z,
        )
    )
    display_surface = box_from_z(
        display_length,
        display_width,
        0.12,
        display_center_x,
        0.0,
        display_surface_z,
    )

    camera_block = box_from_z(
        camera_block_size,
        camera_block_size,
        camera_block_height,
        camera_x,
        0.0,
        -camera_block_height,
    )
    camera_z_min = -camera_block_height - camera_height
    camera = cylinder_from_z(
        camera_diameter,
        camera_height,
        camera_x,
        0.0,
        camera_z_min,
    )
    camera = camera.cut(
        cylinder_from_z(
            lens_diameter,
            lens_recess + 0.2,
            camera_x,
            0.0,
            camera_z_min,
        )
    )
    lens_surface = cylinder_from_z(
        lens_diameter,
        0.08,
        camera_x,
        0.0,
        camera_z_min + lens_recess,
    )

    return (
        pcb
        .union(top_gold)
        .union(bottom_gold)
        .union(frame)
        .union(display_surface)
        .union(camera_block)
        .union(camera)
        .union(lens_surface)
    )


# 绕 Y 轴 +90°：K10 +Z 显示方向→全局 +X，83.2mm 长边→全局 -Z。
k10_model = (
    make_k10_model()
    .rotate((0, 0, 0), (0, 1, 0), 90)
    .translate((CUP_OUTER_RADIUS, 0.0, HARDWARE_CENTER_Z))
)


# ============================================================
# 装配集合与 CQ-editor 显示
# ============================================================
assembly = cq.Compound.makeCompound(
    [
        main_body.val(),
        rgb_ring_model.val(),
        battery_model.val(),
        k10_model.val(),
    ]
)

try:
    show_object
except NameError:
    def show_object(*args, **kwargs):
        pass


show_object(
    main_body,
    name="光效水杯主体_main_body",
    options={"color": (190, 205, 220), "alpha": 1.0},
)
show_object(
    rgb_ring_model,
    name="RGB12灯环_rgb_ring_model",
    options={"color": (80, 190, 255), "alpha": 1.0},
)
show_object(
    battery_model,
    name="行空电池_battery_model",
    options={"color": (245, 158, 11), "alpha": 1.0},
)
show_object(
    k10_model,
    name="行空板K10_k10_model",
    options={"color": (37, 99, 235), "alpha": 1.0},
)
