from __future__ import annotations

import cadquery as cq

# 单位：mm
# 坐标规则：PCB 中心为原点；X 为 30 mm 长度方向；Y 为 22 mm 宽度方向；
# +Z 为传感器和接口正面。模型仅作为 REFERENCE_ONLY 参考源码。

pcb_length = 30.0
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 4.0

mounting_hole_diameter = 3.0
mounting_hole_edge_offset = 3.5
mounting_hole_x = -pcb_length / 2 + mounting_hole_edge_offset
mounting_hole_y = pcb_width / 2 - mounting_hole_edge_offset

connector_length_x = 6.0
connector_width_y = 10.0
connector_height_z = 5.7
connector_center_x = pcb_length / 2 - connector_length_x / 2
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2

sensor_diameter = 5.0
sensor_height_z = 2.7
sensor_center_x = -4.0
sensor_center_y = 0.0
sensor_center_z = pcb_thickness + sensor_height_z / 2

# PCB 主体位于 z=0 到 z=pcb_thickness。
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

# 两个靠近 -X 边的直径 3 mm 固定孔；孔中心距相邻板边均为 3.5 mm。
for hole_y in (-mounting_hole_y, mounting_hole_y):
    pcb = (
        pcb.faces(">Z")
        .workplane()
        .pushPoints([(mounting_hole_x, hole_y)])
        .hole(mounting_hole_diameter)
    )

# +X 边接线口：6 x 10 x 5.7；+X 外边与 PCB +X 外边齐平，整体位于 PCB 上。
connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

# 光线传感器主体：直径 5 mm、厚 2.7 mm 的圆柱体，中心 x=-4 mm。
sensor_body = (
    cq.Workplane("XY")
    .circle(sensor_diameter / 2)
    .extrude(sensor_height_z)
    .translate((sensor_center_x, sensor_center_y, pcb_thickness))
)

result = pcb.union(connector).union(sensor_body)

# CQ-editor 可显示；普通 CadQuery 环境导入本文件时不会因 show_object 缺失而失败。
if "show_object" in globals():
    show_object(result, name="DFR0026 模拟环境光线传感器")
