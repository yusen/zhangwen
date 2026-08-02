import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：
# PCB 中心为原点，X 为 PCB 长边方向，Y 为 PCB 短边方向，+Z 为元件面。
# PCB 位于 z=0 到 z=pcb_thickness。
# 安装意图：
# 继电器固定在盒子底面内部，默认放在盒子长边中间；
# PCB -Y 边，也就是拨杆所在侧，后续装配时应贴近盒子后侧壁。
# 本模型只画硬件本身，不决定最终装配位置。
# =========================
hardware_name = "继电器模块"

# PCB
pcb_length = 37.0
pcb_width = 26.0
pcb_thickness = 1.0
pcb_corner_radius = 2.0

# 固定孔：四角，孔径 3mm，孔心距相邻侧边 4.8mm
mount_hole_diameter = 3.0
mount_hole_edge_offset = 4.8
mount_hole_x = pcb_length / 2.0 - mount_hole_edge_offset
mount_hole_y = pcb_width / 2.0 - mount_hole_edge_offset

# 信号线接口：12 x 6 x 5.7mm，+Y 边与 PCB +Y 边重合，X 居中
signal_connector_length_x = 12.0
signal_connector_width_y = 6.0
signal_connector_height_z = 5.7
signal_connector_center_x = 0.0
signal_connector_center_y = pcb_width / 2.0 - signal_connector_width_y / 2.0
signal_connector_center_z = pcb_thickness + signal_connector_height_z / 2.0

# 两个电源输入/输出口：12 x 10 x 8mm，关于 Y 轴对称，分别贴齐 PCB +X / -X 边
power_terminal_length_x = 12.0
power_terminal_width_y = 10.0
power_terminal_height_z = 8.0
power_terminal_center_x = pcb_length / 2.0 - power_terminal_length_x / 2.0
power_terminal_center_y = 0.0
power_terminal_center_z = pcb_thickness + power_terminal_height_z / 2.0

# 开关：7 x 2 x 1.5mm，与 PCB -Y 边对齐居中，拨杆朝 -Y 面
switch_length_x = 7.0
switch_width_y = 2.0
switch_height_z = 1.5
switch_center_x = 0.0
switch_center_y = -pcb_width / 2.0 + switch_width_y / 2.0
switch_center_z = pcb_thickness + switch_height_z / 2.0


# =========================
# 建模函数
# =========================
def rounded_box(length, width, height, radius, centered=(True, True, False)):
    part = (
        cq.Workplane("XY")
        .box(length, width, height, centered=centered)
    )
    if radius > 0:
        try:
            part = part.edges("|Z").fillet(radius)
        except Exception:
            pass
    return part


def make_mount_hole_cutter(x, y, diameter, height):
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(diameter / 2.0)
        .extrude(height)
        .translate((0, 0, -0.3))
    )


# =========================
# PCB 主体和固定孔
# =========================
pcb = rounded_box(
    pcb_length,
    pcb_width,
    pcb_thickness,
    pcb_corner_radius,
)

mount_holes = [
    (-mount_hole_x, -mount_hole_y),
    (-mount_hole_x, mount_hole_y),
    (mount_hole_x, -mount_hole_y),
    (mount_hole_x, mount_hole_y),
]

for hx, hy in mount_holes:
    pcb = pcb.cut(
        make_mount_hole_cutter(
            hx,
            hy,
            mount_hole_diameter,
            pcb_thickness + 0.6,
        )
    )


# =========================
# +Z 面元件
# =========================
signal_connector = (
    cq.Workplane("XY")
    .box(
        signal_connector_length_x,
        signal_connector_width_y,
        signal_connector_height_z,
        centered=(True, True, True),
    )
    .translate((
        signal_connector_center_x,
        signal_connector_center_y,
        signal_connector_center_z,
    ))
)

power_terminal_plus_x = (
    cq.Workplane("XY")
    .box(
        power_terminal_length_x,
        power_terminal_width_y,
        power_terminal_height_z,
        centered=(True, True, True),
    )
    .translate((
        power_terminal_center_x,
        power_terminal_center_y,
        power_terminal_center_z,
    ))
)

power_terminal_minus_x = (
    cq.Workplane("XY")
    .box(
        power_terminal_length_x,
        power_terminal_width_y,
        power_terminal_height_z,
        centered=(True, True, True),
    )
    .translate((
        -power_terminal_center_x,
        power_terminal_center_y,
        power_terminal_center_z,
    ))
)

switch_body = (
    cq.Workplane("XY")
    .box(
        switch_length_x,
        switch_width_y,
        switch_height_z,
        centered=(True, True, True),
    )
    .translate((
        switch_center_x,
        switch_center_y,
        switch_center_z,
    ))
)

# 拨杆用一个更小的凸起表示，位于开关 -Y 面，方便确认朝向。
lever_length_x = 3.0
lever_width_y = 1.2
lever_height_z = 2.0
lever = (
    cq.Workplane("XY")
    .box(
        lever_length_x,
        lever_width_y,
        lever_height_z,
        centered=(True, True, True),
    )
    .translate((
        switch_center_x,
        -pcb_width / 2.0 - lever_width_y / 2.0,
        pcb_thickness + lever_height_z / 2.0,
    ))
)


# =========================
# 合并结果
# =========================
result = (
    pcb
    .union(signal_connector)
    .union(power_terminal_plus_x)
    .union(power_terminal_minus_x)
    .union(switch_body)
    .union(lever)
)

show_object(result, name=hardware_name)
