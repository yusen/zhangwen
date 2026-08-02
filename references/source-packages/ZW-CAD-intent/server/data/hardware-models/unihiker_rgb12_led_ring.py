import cadquery as cq
import math

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 圆环中心为原点，XY 平面为圆环平面，+Z 为 12 颗 LED 所在正面。
# PCB 位于 z=0 到 z=pcb_thickness；LED 位于 +Z 面；两个接线座位于 -Z 面。
# 安装意图：默认外表面安装，用户偏好默认前侧面；具体装到哪个外侧面由后续装配参数决定，本模型不做旋转/平移。
# =========================
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
led_rotation_step = 360.0 / led_count

connector_length_x = 5.5
connector_width_y = 10.0
connector_height_z = 5.7
connector_edge_margin = 0.15

connector_half_width_y = connector_width_y / 2.0
connector_center_x = (
    math.sqrt(pcb_outer_radius ** 2 - connector_half_width_y ** 2)
    - connector_length_x / 2.0
    - connector_edge_margin
)
connector_center_z = -connector_height_z / 2.0

# PCB 圆环，外径 47mm，内径 27mm，厚度 1.6mm。
pcb_outer = cq.Workplane("XY").circle(pcb_outer_radius).extrude(pcb_thickness)
pcb_inner = cq.Workplane("XY").circle(pcb_inner_radius).extrude(pcb_thickness)
pcb = pcb_outer.cut(pcb_inner)

# LED 种子件：中心落在内外圆中间圆周上，再绕 Z 轴按 30 度间隔旋转复制。
led_seed = (
    cq.Workplane("XY")
    .box(led_size, led_size, led_height, centered=(True, True, True))
    .translate((led_center_radius, 0.0, led_center_z))
)

leds = None
for i in range(led_count):
    angle = i * led_rotation_step
    led_part = led_seed.rotate((0, 0, 0), (0, 0, 1), angle)
    leds = led_part if leds is None else leds.union(led_part)

# 两个接线座：均位于 PCB -Z 面下方，+Z 面齐平 z=0，顶面投影完整收纳进 PCB 外圆周内。
connector_pos = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, 0.0, connector_center_z))
)

connector_neg = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((-connector_center_x, 0.0, connector_center_z))
)

result = pcb.union(leds).union(connector_pos).union(connector_neg)
show_object(result, name="RGB12灯珠灯环")
