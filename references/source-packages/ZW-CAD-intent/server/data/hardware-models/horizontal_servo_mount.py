import cadquery as cq

# =============================================================================
# 模型说明：卧式舵机固定座
# =============================================================================
# 作用：
#   用作舵机或尺寸相容部件的卧式安装连接件。两个关于 Y 轴对称的立柱
#   在 X 方向形成 23.1 mm 内部安装空间，立柱短边端面上的横向贯穿孔
#   构成被安装件的连接接口。
#
# BOM：
#   1. 卧式舵机固定座（本模型，3D 打印件）× 1
#
# 配合关系：
#   - 被安装件位于两个立柱的内侧面之间，名义空间为 23.1 mm。
#   - 每根立柱有一个直径 2.2 mm 的侧孔，孔轴沿 Y 方向贯穿 12 mm。
#   - 底板只保留左右短边凸出区域的两个直径 2.2 mm 贯穿安装孔。
#   - 本卧式版本不包含立式版本的顶部圆孔和侧面矩形槽。
#   - 未指定具体舵机和紧固件型号，因此直径 2.2 mm 仅作为几何孔径，
#     不将其认定为某种标准螺纹孔或标准螺钉间隙孔。
#
# 坐标系：
#   - 单位：mm
#   - 原点：底板 XY 平面的几何中心，位于底板底面 z=0
#   - X：底板 42.4 mm 长度方向，也是两个立柱的对称分布方向
#   - Y：底板 22.2 mm 宽度方向，也是立柱侧孔的贯穿方向
#   - +Z：从底板向立柱顶部的方向
#
# 主要结构：
#   - 底板：42.4 × 22.2 × 2.0
#   - 四角缺口：以原始角点为圆心，向板内切除 R5 四分之一圆
#   - 底板安装孔：两个直径 2.2 的 Z 向贯穿孔，中心为 (±18.7, 0)
#   - 立柱：两个 5.0 × 12.0 × 12.4 的对称实体，内侧间距 23.1
#   - 立柱侧孔：两个直径 2.2 的 Y 向贯穿孔，中心高度 z=8.2
#
# 生产调用说明：
#   本脚本只生成固定座自身，不包含舵机、螺钉或最终产品装配变换。
#   推荐以底板底面贴合打印平台。实际打印前应按材料、设备和紧固方式
#   校核孔径补偿、配合间隙及孔周围壁厚。
# =============================================================================


# =========================
# 参数区，单位：mm
# =========================

# 底板
base_length_x = 42.4
base_width_y = 22.2
base_thickness = 2.0
corner_cut_radius = 5.0

# 底板左右两个贯穿安装孔
base_mount_hole_diameter = 2.2

# 两个立柱
support_size_x = 5.0
support_size_y = 12.0
support_height_z = 12.4
support_inner_gap_x = 23.1

# 立柱短边侧面贯穿孔
support_side_hole_diameter = 2.2

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
support_side_hole_center_z = base_thickness + support_height_z / 2.0

# 两个底板孔位于左右 R5 凸出区域沿 X 方向的中间，距对应外边 2.5 mm。
base_mount_hole_edge_offset = corner_cut_radius / 2.0
base_mount_hole_offset_x = base_length_x / 2.0 - base_mount_hole_edge_offset
base_mount_hole_centers = (
    (-base_mount_hole_offset_x, 0.0),
    (base_mount_hole_offset_x, 0.0),
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
if support_side_hole_diameter <= 0.0:
    raise ValueError("support_side_hole_diameter 必须大于 0")
if support_side_hole_diameter >= min(support_size_x, support_height_z):
    raise ValueError("立柱侧孔直径过大，无法在短边侧面保留有效壁厚")

# 检查左右底板孔与相邻立柱之间仍有实体间距。
support_outer_x = support_center_offset_x + support_size_x / 2.0
base_mount_hole_inner_x = base_mount_hole_offset_x - base_mount_hole_diameter / 2.0
if base_mount_hole_inner_x <= support_outer_x:
    raise ValueError("底板安装孔与立柱在 X 方向发生相交")


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
# 第 3 步：底板左右两个直径 2.2 贯穿安装孔
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
# 第 4、5 步：两个立柱及其 Y 向侧面贯穿孔
# =========================

def make_support(center_x):
    """创建一个带短边侧面贯穿孔的立柱。"""

    # 立柱向底板内部多伸入 join_overlap，防止仅靠共面接触导致合并失败。
    # 名义底面为 z=2.0，名义顶面为 z=14.4。
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

    # 在 +Y 短边端面中心建立 XZ 圆形草图。
    # CadQuery 的 XZ 工作面法向为 -Y，因此正向拉伸会从 +Y 贯穿至 -Y。
    side_hole_cutter = (
        cq.Workplane(
            "XZ",
            origin=(
                center_x,
                support_size_y / 2.0 + boolean_overlap,
                support_side_hole_center_z,
            ),
        )
        .circle(support_side_hole_diameter / 2.0)
        .extrude(support_size_y + 2.0 * boolean_overlap)
    )
    support = support.cut(side_hole_cutter)

    return support.clean()


left_support = make_support(support_centers_x[0])
right_support = make_support(support_centers_x[1])


# =========================
# 最终合并与显示
# =========================

result = base.union(left_support).union(right_support).clean()

show_object(result, name="卧式舵机固定座")
