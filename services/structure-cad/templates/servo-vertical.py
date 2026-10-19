import cadquery as cq

# =============================================================================
# 模型说明：立式舵机固定座
# =============================================================================
# 作用：
#   用作舵机或尺寸相容部件的立式安装连接件。两个对称立柱在 X 方向形成
#   23.1 mm 的内部安装空间，立柱顶部孔和侧面贯穿槽构成固定接口。
#
# BOM：
#   1. 立式舵机固定座（本模型，3D 打印件）× 1
#
# 配合关系：
#   - 被安装件位于两个立柱的内侧面之间，名义空间为 23.1 mm。
#   - 两个直径 2.4 mm 的孔位于立柱顶面中心，孔轴沿 Z 方向。
#   - 两个 5.4 mm × 9.5 mm 的矩形槽沿 X 方向贯穿对应立柱。
#   - 底板四边凸出区域各有一个直径 2.2 mm 的贯穿安装孔；孔中心距
#     对应外边 2.5 mm，供固定座与外部安装平面配合。
#   - 未指定具体舵机和紧固件型号，因此直径 2.4 mm 和 2.2 mm 均仅
#     作为几何孔径，不将其认定为某种标准螺纹孔或标准螺钉间隙孔。
#
# 坐标系：
#   - 单位：mm
#   - 原点：底板 XY 平面的几何中心，位于底板底面 z=0
#   - X：底板 42.4 mm 长度方向
#   - Y：底板 22.2 mm 宽度方向
#   - +Z：从底板向立柱顶部的方向
#
# 主要结构：
#   - 底板：42.4 × 22.2 × 2.0
#   - 四角缺口：以原始角点为圆心，向板内切除 R5 四分之一圆
#   - 底板安装孔：四个直径 2.2 的 Z 向贯穿孔，关于 X、Y 轴对称
#   - 立柱：两个 5.0 × 12.0 × 17.5 的对称实体
#   - 顶孔：直径 2.4，名义切除深度 10.0
#   - 侧槽：Y 向宽 5.4、Z 向高 9.5，沿 X 贯穿
#
# 生产调用说明：
#   本脚本只生成连接件自身，不包含舵机、螺钉或最终产品装配变换。
#   推荐以底板底面贴合打印平台。实际打印前应按材料、设备和紧固方式
#   校核孔径补偿、配合间隙及顶部 8.0 mm 实体区域的强度。
# =============================================================================


# =========================
# 参数区，单位：mm
# =========================

# 底板
base_length_x = 42.4
base_width_y = 22.2
base_thickness = 2.0
corner_cut_radius = 5.0

# 底板四边凸出区域的贯穿安装孔
base_mount_hole_diameter = 2.2

# 两个立柱
support_size_x = 5.0
support_size_y = 12.0
support_height_z = 17.5
support_inner_gap_x = 23.1

# 顶部圆孔
top_hole_diameter = 2.4
top_hole_depth = 10.0

# 侧面矩形贯穿槽
slot_width_y = 5.4
slot_height_z = 9.5

# 只用于提高布尔运算稳定性，不改变模型名义外形尺寸
boolean_overlap = 0.10
join_overlap = 0.05


# =========================
# 派生尺寸与参数检查
# =========================

support_center_offset_x = (support_inner_gap_x + support_size_x) / 2.0
support_centers_x = (-support_center_offset_x, support_center_offset_x)
support_bottom_z = base_thickness
support_top_z = base_thickness + support_height_z
slot_bottom_z = base_thickness
slot_top_z = slot_bottom_z + slot_height_z
top_bridge_height = support_top_z - slot_top_z

# 四个孔位于 R5 凸出区域沿凸出方向的中间，距对应外边 2.5 mm。
base_mount_hole_edge_offset = corner_cut_radius / 2.0
base_mount_hole_offset_x = base_length_x / 2.0 - base_mount_hole_edge_offset
base_mount_hole_offset_y = base_width_y / 2.0 - base_mount_hole_edge_offset
base_mount_hole_centers = (
    (0.0, base_mount_hole_offset_y),
    (0.0, -base_mount_hole_offset_y),
    (base_mount_hole_offset_x, 0.0),
    (-base_mount_hole_offset_x, 0.0),
)

if corner_cut_radius <= 0.0:
    raise ValueError("corner_cut_radius 必须大于 0")
if 2.0 * corner_cut_radius > min(base_length_x, base_width_y):
    raise ValueError("角部缺口半径过大，相邻缺口会相交")
if base_mount_hole_diameter <= 0.0:
    raise ValueError("base_mount_hole_diameter 必须大于 0")
if base_mount_hole_diameter >= corner_cut_radius:
    raise ValueError("底板安装孔直径必须小于 5 mm 凸出区域的深度")
if support_inner_gap_x + 2.0 * support_size_x > base_length_x:
    raise ValueError("两个立柱超出底板的 X 向范围")
if slot_width_y <= 0.0 or slot_width_y >= support_size_y:
    raise ValueError("slot_width_y 必须大于 0 且小于立柱 Y 向尺寸")
if slot_height_z <= 0.0 or slot_height_z >= support_height_z:
    raise ValueError("slot_height_z 必须大于 0 且小于立柱高度")
if top_hole_diameter <= 0.0 or top_hole_diameter >= support_size_x:
    raise ValueError("顶部孔直径必须大于 0 且小于立柱 X 向尺寸")
if top_hole_depth <= 0.0 or top_hole_depth > support_height_z:
    raise ValueError("顶部孔深度必须大于 0 且不超过立柱高度")


# =========================
# 第 1、2 步：底板与四角 R5 内凹缺口
# =========================

base = (
    cq.Workplane("XY")
    .box(
        base_length_x,
        base_width_y,
        base_thickness,
        centered=(True, True, False),
    )
)

corner_centers = (
    (-base_length_x / 2.0, -base_width_y / 2.0),
    (-base_length_x / 2.0, base_width_y / 2.0),
    (base_length_x / 2.0, -base_width_y / 2.0),
    (base_length_x / 2.0, base_width_y / 2.0),
)

for corner_x, corner_y in corner_centers:
    # 圆柱中心位于原始角点；与底板相交的部分正好是四分之一圆。
    corner_cutter = (
        cq.Workplane(
            "XY",
            origin=(corner_x, corner_y, -boolean_overlap),
        )
        .circle(corner_cut_radius)
        .extrude(base_thickness + 2.0 * boolean_overlap)
    )
    base = base.cut(corner_cutter)


# =========================
# 新增步骤：底板四边凸出区域的四个直径 2.2 贯穿孔
# =========================

for hole_x, hole_y in base_mount_hole_centers:
    # 切刀从底板下方开始并穿过顶面，避免共面布尔运算残留薄皮。
    base_mount_hole_cutter = (
        cq.Workplane(
            "XY",
            origin=(hole_x, hole_y, -boolean_overlap),
        )
        .circle(base_mount_hole_diameter / 2.0)
        .extrude(base_thickness + 2.0 * boolean_overlap)
    )
    base = base.cut(base_mount_hole_cutter)


# =========================
# 第 3、4、5 步：立柱、顶部孔和侧面贯穿槽
# =========================

def make_support(center_x):
    """创建一个完成孔槽切除的立柱，再交给主模型与底板合并。"""

    # 立柱向底板内部多伸入 join_overlap，防止仅靠共面接触导致合并失败。
    # 立柱名义底面仍为 z=2.0，名义顶面为 z=19.5。
    support = (
        cq.Workplane("XY")
        .box(
            support_size_x,
            support_size_y,
            support_height_z + join_overlap,
            centered=(True, True, False),
        )
        .translate((center_x, 0.0, support_bottom_z - join_overlap))
    )

    # 从立柱顶面中心沿 -Z 切除直径 2.4、名义深度 10.0 的圆柱。
    top_hole_cutter = (
        cq.Workplane(
            "XY",
            origin=(center_x, 0.0, support_top_z + boolean_overlap),
        )
        .circle(top_hole_diameter / 2.0)
        .extrude(-(top_hole_depth + boolean_overlap))
    )
    support = support.cut(top_hole_cutter)

    # 在 YZ 侧面绘制 5.4 × 9.5 的矩形，沿 +X 贯穿整个 5 mm 立柱。
    # 槽范围：y=-2.7~2.7，z=2.0~11.5；顶部保留 8.0 mm。
    slot_cutter = (
        cq.Workplane(
            "YZ",
            origin=(
                center_x - support_size_x / 2.0 - boolean_overlap,
                0.0,
                slot_bottom_z + slot_height_z / 2.0,
            ),
        )
        .rect(slot_width_y, slot_height_z)
        .extrude(support_size_x + 2.0 * boolean_overlap)
    )
    support = support.cut(slot_cutter)

    return support.clean()


left_support = make_support(support_centers_x[0])
right_support = make_support(support_centers_x[1])


# =========================
# 最终合并与显示
# =========================

result = base.union(left_support).union(right_support).clean()

show_object(result, name="立式舵机固定座")
