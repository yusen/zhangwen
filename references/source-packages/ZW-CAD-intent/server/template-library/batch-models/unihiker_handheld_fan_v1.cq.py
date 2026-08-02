"""
手持小风扇 CadQuery 模板

BOM：
1. 行空板 K10 × 1
2. 行空板聚合物锂电池 × 1
3. 直流电机风扇 × 1

结构说明：
- 原点在圆柱底面中心，+Z 向上，-Y 为正面。
- 实心主体由 D52×75mm 圆柱和 52×27×85mm 长方体组成。
- 长方体位于 Z=75~160mm；风扇 PCB 居中安装在其顶面。
- 使用内径 D52mm、外径 D80mm 的圆环沿 Z 方向贯穿切削长方体，削除超出圆柱投影的棱角。
- 顶部四个 D2.4×8mm 盲孔用于 M3 自攻螺丝，孔心为 X=±21.2、Y=±6.2mm。
- K10 横向放在 -Y 面，底边对齐 Z=75mm，显示面朝 -Y，摄像头允许示意穿插。
- 电池贴在 +Y 面，48mm 边沿 X、32mm 边沿 Z，底边对齐 Z=75mm。
- K10 和电池采用热熔胶，不生成专用固定结构。

后续修改对象：
- handle_cylinder：圆柱手柄。
- upper_block：上部长方体。
- main_body / result：带自攻孔的可打印主体。
- k10_model、battery_model、fan_model：独立硬件。
- assembly：非布尔装配集合。

刻字说明：
- 当前不生成刻字。
- 长方体 +Y 面的电池上方可刻产品名或版本号。
- 圆柱侧面可做竖向曲面刻字。
"""

import cadquery as cq


# ============================================================
# 参数区，单位：mm
# ============================================================
HANDLE_DIAMETER = 52.0
HANDLE_HEIGHT = 75.0
UPPER_LENGTH_X = 52.0
UPPER_DEPTH_Y = 27.0
UPPER_HEIGHT_Z = 85.0
UPPER_BOTTOM_Z = HANDLE_HEIGHT
UPPER_TOP_Z = UPPER_BOTTOM_Z + UPPER_HEIGHT_Z
BODY_UNION_OVERLAP = 0.1
TRIM_RING_INNER_DIAMETER = HANDLE_DIAMETER
TRIM_RING_OUTER_DIAMETER = 80.0
TRIM_CUT_OVERLAP = 0.2

FAN_PCB_LENGTH_X = 52.0
FAN_PCB_WIDTH_Y = 22.0
FAN_MOUNT_X = FAN_PCB_LENGTH_X / 2.0 - 4.8
FAN_MOUNT_Y = FAN_PCB_WIDTH_Y / 2.0 - 4.8
M3_PILOT_DIAMETER = 2.4
M3_PILOT_DEPTH = 8.0


# ============================================================
# 通用几何函数
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


def cylinder_along_minus_y(diameter, length, x, y_start, z, fillet_radius=0.0):
    shape = cq.Workplane("XY").circle(diameter / 2.0).extrude(length)
    if fillet_radius > 0:
        try:
            shape = shape.edges().fillet(fillet_radius)
        except Exception:
            pass
    return shape.rotate((0, 0, 0), (1, 0, 0), 90).translate((x, y_start, z))


# ============================================================
# 主体与风扇自攻孔
# ============================================================
handle_cylinder = (
    cq.Workplane("XY")
    .circle(HANDLE_DIAMETER / 2.0)
    .extrude(HANDLE_HEIGHT)
)

# 向圆柱内部重叠 0.1mm，外部顶面仍为 Z=160mm。
upper_block = (
    cq.Workplane("XY")
    .box(
        UPPER_LENGTH_X,
        UPPER_DEPTH_Y,
        UPPER_HEIGHT_Z + BODY_UNION_OVERLAP,
        centered=(True, True, False),
    )
    .translate((0.0, 0.0, UPPER_BOTTOM_Z - BODY_UNION_OVERLAP))
)

main_body = handle_cylinder.union(upper_block)

# 用 D52/D80 环形切刀沿 Z 方向贯穿上部长方体。
# 内圆柱是保留区；外圆柱减去内圆柱后，只切掉超出手柄投影的棱角。
trim_outer_cylinder = (
    cq.Workplane("XY")
    .circle(TRIM_RING_OUTER_DIAMETER / 2.0)
    .extrude(UPPER_HEIGHT_Z + 2.0 * TRIM_CUT_OVERLAP)
    .translate((0.0, 0.0, UPPER_BOTTOM_Z - TRIM_CUT_OVERLAP))
)
trim_inner_cylinder = (
    cq.Workplane("XY")
    .circle(TRIM_RING_INNER_DIAMETER / 2.0)
    .extrude(UPPER_HEIGHT_Z + 2.0 * TRIM_CUT_OVERLAP)
    .translate((0.0, 0.0, UPPER_BOTTOM_Z - TRIM_CUT_OVERLAP))
)
upper_corner_ring_cutter = trim_outer_cylinder.cut(trim_inner_cylinder)
main_body = main_body.cut(upper_corner_ring_cutter)

fan_mount_points = [
    (-FAN_MOUNT_X, -FAN_MOUNT_Y),
    (-FAN_MOUNT_X, FAN_MOUNT_Y),
    (FAN_MOUNT_X, -FAN_MOUNT_Y),
    (FAN_MOUNT_X, FAN_MOUNT_Y),
]

for hole_x, hole_y in fan_mount_points:
    # 切刀高出顶面 0.2mm 防薄皮；主体内有效孔深为 8mm。
    pilot_hole_cutter = (
        cq.Workplane("XY")
        .center(hole_x, hole_y)
        .circle(M3_PILOT_DIAMETER / 2.0)
        .extrude(M3_PILOT_DEPTH + 0.2)
        .translate((0.0, 0.0, UPPER_TOP_Z - M3_PILOT_DEPTH))
    )
    main_body = main_body.cut(pilot_hole_cutter)

result = main_body


# ============================================================
# 行空板 K10
# 原始坐标：PCB 中心在 XY 原点，PCB 从 Z=0 向 +Z。
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
        pcb_length, pcb_width, pcb_thickness, pcb_corner_radius, 0.0
    )
    top_gold = rounded_plate(
        gold_length, pcb_width, gold_thickness, pcb_corner_radius, pcb_thickness
    ).translate((gold_center_x, 0.0, 0.0))
    bottom_gold = rounded_plate(
        gold_length, pcb_width, gold_thickness, pcb_corner_radius, -gold_thickness
    ).translate((gold_center_x, 0.0, 0.0))

    frame = box_from_z(
        frame_length, frame_width, frame_height, frame_center_x, 0.0, pcb_thickness
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
        display_length, display_width, 0.12, display_center_x, 0.0, display_surface_z
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
        camera_diameter, camera_height, camera_x, 0.0, camera_z_min
    )
    camera = camera.cut(
        cylinder_from_z(
            lens_diameter, lens_recess + 0.2, camera_x, 0.0, camera_z_min
        )
    )
    lens_surface = cylinder_from_z(
        lens_diameter, 0.08, camera_x, 0.0, camera_z_min + lens_recess
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


# +90° 绕 X：硬件 X→全局 X，硬件 Y→全局 Z，硬件 +Z→全局 -Y。
k10_model = (
    make_k10_model()
    .rotate((0, 0, 0), (1, 0, 0), 90)
    .translate(
        (
            0.0,
            -UPPER_DEPTH_Y / 2.0,
            UPPER_BOTTOM_Z + 51.3 / 2.0,
        )
    )
)


# ============================================================
# 行空板聚合物锂电池
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


# -90° 绕 X：电池厚度 +Z→全局 +Y；旋转后 Z 范围为 75~107mm。
battery_model = (
    make_battery_model()
    .rotate((0, 0, 0), (1, 0, 0), -90)
    .translate(
        (
            0.0,
            UPPER_DEPTH_Y / 2.0,
            UPPER_BOTTOM_Z + 32.0 / 2.0,
        )
    )
)


# ============================================================
# 直流电机风扇
# 原始坐标：PCB 中心在 XY 原点，底面 Z=0，输出轴朝 -Y。
# ============================================================
def make_fan_model():
    pcb_length = 52.0
    pcb_width = 22.0
    pcb_thickness = 1.0
    pcb = rounded_plate(pcb_length, pcb_width, pcb_thickness, 2.5, 0.0)

    mount_x = pcb_length / 2.0 - 4.8
    mount_y = pcb_width / 2.0 - 4.8
    for hole_x, hole_y in [
        (-mount_x, -mount_y),
        (-mount_x, mount_y),
        (mount_x, -mount_y),
        (mount_x, mount_y),
    ]:
        cutter = (
            cq.Workplane("XY")
            .center(hole_x, hole_y)
            .circle(1.5)
            .extrude(pcb_thickness + 0.6)
            .translate((0.0, 0.0, -0.3))
        )
        pcb = pcb.cut(cutter)

    connector = (
        cq.Workplane("XY")
        .box(4.7, 8.0, 6.0, centered=(True, True, False))
        .translate((52.0 / 2.0 - 4.7 / 2.0, 0.0, pcb_thickness))
    )

    motor_height = 17.0
    motor_center_z = pcb_thickness + motor_height / 2.0
    motor_minus_y = -22.0 / 2.0
    motor = (
        cq.Workplane("XY")
        .box(27.0, 22.0, motor_height, centered=(True, True, True))
        .translate((0.0, 0.0, motor_center_z))
    )

    front_cylinder = cylinder_along_minus_y(
        6.0, 1.5, 0.0, motor_minus_y, motor_center_z
    )
    shaft = cylinder_along_minus_y(
        2.0, 4.0, 0.0, motor_minus_y - 1.5, motor_center_z
    )
    fan_hub = cylinder_along_minus_y(
        24.0, 11.5, 0.0, motor_minus_y - 1.5 - 4.0, motor_center_z, 2.0
    )

    return (
        pcb
        .union(connector)
        .union(motor)
        .union(front_cylinder)
        .union(shaft)
        .union(fan_hub)
    )


# PCB 底面中心与 52×27mm 顶面中心重合，扇叶自然朝 -Y。
fan_model = make_fan_model().translate((0.0, 0.0, UPPER_TOP_Z))


# ============================================================
# 装配与 CQ-editor 显示
# ============================================================
assembly = cq.Compound.makeCompound(
    [
        main_body.val(),
        k10_model.val(),
        battery_model.val(),
        fan_model.val(),
    ]
)

try:
    show_object
except NameError:
    def show_object(*args, **kwargs):
        pass


show_object(
    main_body,
    name="主体_main_body",
    options={"color": (185, 185, 190), "alpha": 1.0},
)
show_object(
    k10_model,
    name="行空板K10_k10_model",
    options={"color": (37, 99, 235), "alpha": 1.0},
)
show_object(
    battery_model,
    name="行空电池_battery_model",
    options={"color": (245, 158, 11), "alpha": 1.0},
)
show_object(
    fan_model,
    name="直流电机风扇_fan_model",
    options={"color": (75, 85, 99), "alpha": 1.0},
)
