import cadquery as cq

# =============================================================================
# 模型说明：侧式舵机固定座
# =============================================================================
# 作用：
#   由一块水平底板和一块位于 +Y 边缘的竖直立墙组成 L 形侧式固定座。
#   立墙中央矩形通孔提供舵机或尺寸相容部件的穿入/避让空间，上下两个
#   直径 2.2 mm 横向贯穿孔构成固定接口。
#
# BOM：
#   1. 侧式舵机固定座（本模型，3D 打印件）× 1
#
# 配合关系：
#   - 底板主体为 22.4 × 20 × 2 mm，左右各向 X 外侧延伸 5 mm 安装耳。
#   - 两个安装耳的上下外角各切除 R5 四分之一圆，安装耳中心各有一个
#     直径 2.2 mm 的 Z 向贯穿孔，孔中心为 (x=±13.7,y=0)。
#   - 立墙贴底板 +Y 边放置，范围 y=5~10，-Y 面位于 y=5 并朝向底板内部。
#   - 中央矩形通孔尺寸为 X 向 12.5、Z 向 22.8，沿 +Y 贯穿 5 mm 立墙。
#   - 上下两个直径 2.2 mm 孔同样沿 +Y 贯穿立墙，孔中心高度分别为
#     z=4.4 和 z=32.0。
#   - 未指定具体舵机和紧固件型号，因此直径 2.2 mm 仅作为几何孔径，
#     不将其认定为某种标准螺纹孔或标准螺钉间隙孔。
#
# 坐标系：
#   - 单位：mm
#   - 原点：底板 XY 平面的几何中心，位于底板底面 z=0
#   - X：底板与左右安装耳的延伸方向；立墙主体长度为 22.4 mm
#   - Y：底板的 20 mm 宽度方向；立墙孔从 -Y 面沿 +Y 贯穿
#   - +Z：从底板向立墙顶部的方向
#
# 主要结构：
#   - 底板主体：22.4 × 20.0 × 2.0
#   - 左右安装耳：各沿 ±X 延伸 5.0，带 R5 端部和直径 2.2 贯穿孔
#   - 底板含安装耳的总体包围尺寸：32.4 × 20.0 × 2.0
#   - 立墙：22.4 × 5.0 × 32.4，底面 z=2.0，顶面 z=34.4
#   - 矩形通孔：12.5 × 22.8，范围 x=-6.25~6.25、z=6.8~29.6
#   - 固定孔：两个直径 2.2 的 Y 向贯穿孔，中心为 (x=0,z=4.4/32.0)
#
# 生产调用说明：
#   本脚本只生成固定座自身，不包含舵机、螺钉或最终产品装配变换。
#   实际打印前应按材料、设备和紧固方式校核孔径补偿、矩形孔配合间隙、
#   上下横梁的剩余壁厚以及 L 形根部强度。
# =============================================================================


# =========================
# 参数区，单位：mm
# =========================

# 底板
base_size_x = 22.4
base_size_y = 20.0
base_thickness = 2.0

# 底板左右安装耳
mount_tab_extension_x = 5.0
mount_tab_corner_radius = 5.0
base_mount_hole_diameter = 2.2

# 竖直立墙
wall_size_x = 22.4
wall_size_y = 5.0
wall_height_z = 32.4

# 立墙中央矩形通孔
opening_size_x = 12.5
opening_size_z = 22.8

# 立墙上下固定孔
fixing_hole_diameter = 2.2

# 只用于提高布尔运算稳定性，不改变模型名义外形尺寸
boolean_overlap = 0.10
join_overlap = 0.05


# =========================
# 派生尺寸与参数检查
# =========================

# 原底板主体 x=-11.2~11.2；左右安装耳将外轮廓延伸到 x=±16.2。
extended_base_size_x = base_size_x + 2.0 * mount_tab_extension_x
extended_base_half_x = extended_base_size_x / 2.0
mount_tab_center_offset_x = base_size_x / 2.0 + mount_tab_extension_x / 2.0
mount_tab_centers_x = (-mount_tab_center_offset_x, mount_tab_center_offset_x)
mount_tab_outer_corner_centers = (
    (-extended_base_half_x, -base_size_y / 2.0),
    (-extended_base_half_x, base_size_y / 2.0),
    (extended_base_half_x, -base_size_y / 2.0),
    (extended_base_half_x, base_size_y / 2.0),
)

# 立墙贴底板 +Y 边：底板 y=-10~10，立墙 y=5~10。
wall_y_max = base_size_y / 2.0
wall_y_min = wall_y_max - wall_size_y
wall_center_y = (wall_y_min + wall_y_max) / 2.0
wall_bottom_z = base_thickness
wall_top_z = base_thickness + wall_height_z

# 矩形孔位于立墙 -Y 面的 X/Z 中心。
opening_center_z = base_thickness + wall_height_z / 2.0
opening_bottom_z = opening_center_z - opening_size_z / 2.0
opening_top_z = opening_center_z + opening_size_z / 2.0

# 矩形孔上下各留下相同高度的横梁，圆孔位于各横梁的 X/Z 中心。
remaining_band_height = (wall_height_z - opening_size_z) / 2.0
lower_hole_center_z = base_thickness + remaining_band_height / 2.0
upper_hole_center_z = wall_top_z - remaining_band_height / 2.0
fixing_hole_centers_z = (lower_hole_center_z, upper_hole_center_z)

if base_size_x <= 0.0 or base_size_y <= 0.0 or base_thickness <= 0.0:
    raise ValueError("底板尺寸必须全部大于 0")
if mount_tab_extension_x <= 0.0 or mount_tab_corner_radius <= 0.0:
    raise ValueError("安装耳延伸量和端部圆角半径必须大于 0")
if mount_tab_corner_radius > mount_tab_extension_x:
    raise ValueError("安装耳端部圆角半径不能大于 X 向延伸量")
if 2.0 * mount_tab_corner_radius > base_size_y:
    raise ValueError("安装耳上下圆角在 Y 方向发生相交")
if base_mount_hole_diameter <= 0.0:
    raise ValueError("base_mount_hole_diameter 必须大于 0")
if base_mount_hole_diameter >= mount_tab_extension_x:
    raise ValueError("底板安装孔直径必须小于安装耳的 X 向长度")
if wall_size_x <= 0.0 or wall_size_y <= 0.0 or wall_height_z <= 0.0:
    raise ValueError("立墙尺寸必须全部大于 0")
if wall_size_x > base_size_x or wall_size_y > base_size_y:
    raise ValueError("立墙在 XY 平面内不能超出底板")
if opening_size_x <= 0.0 or opening_size_z <= 0.0:
    raise ValueError("矩形通孔尺寸必须大于 0")
if opening_size_x >= wall_size_x or opening_size_z >= wall_height_z:
    raise ValueError("矩形通孔必须小于立墙的 X/Z 尺寸")
if fixing_hole_diameter <= 0.0:
    raise ValueError("fixing_hole_diameter 必须大于 0")
if fixing_hole_diameter >= min(wall_size_x, remaining_band_height):
    raise ValueError("固定孔过大，无法在上下剩余横梁中保留有效壁厚")


# =========================
# 第 1 步：底板主体与左右 5 mm 安装耳
# =========================

# 先建立包含左右安装耳的整体矩形，可避免三个共面实体合并产生薄片。
base = (
    cq.Workplane("XY")
    .box(
        extended_base_size_x,
        base_size_y,
        base_thickness,
        centered=(True, True, False),
    )
)

# 四个圆柱均以新外角为圆心；与底板相交的部分是 R5 四分之一圆。
for corner_x, corner_y in mount_tab_outer_corner_centers:
    corner_cutter = (
        cq.Workplane(
            "XY",
            origin=(corner_x, corner_y, -boolean_overlap),
        )
        .circle(mount_tab_corner_radius)
        .extrude(base_thickness + 2.0 * boolean_overlap)
    )
    base = base.cut(corner_cutter)

# 两个孔位于各 5 mm 安装耳的 X/Y 中心，沿 Z 贯穿底板。
for hole_x in mount_tab_centers_x:
    base_mount_hole_cutter = (
        cq.Workplane(
            "XY",
            origin=(hole_x, 0.0, -boolean_overlap),
        )
        .circle(base_mount_hole_diameter / 2.0)
        .extrude(base_thickness + 2.0 * boolean_overlap)
    )
    base = base.cut(base_mount_hole_cutter)


# =========================
# 第 2 步：贴 +Y 边的竖直立墙
# =========================

# 立墙向底板内部多伸入 join_overlap，避免仅靠共面接触造成合并失败。
# 名义底面仍为 z=2.0，名义顶面仍为 z=34.4。
wall = (
    cq.Workplane("XY")
    .box(
        wall_size_x,
        wall_size_y,
        wall_height_z + join_overlap,
        centered=(True, True, False),
    )
    .translate((0.0, wall_center_y, wall_bottom_z - join_overlap))
)


# =========================
# 第 3 步：立墙 -Y 面中央矩形贯穿孔
# =========================

def make_positive_y_cut_plane(center_z):
    """建立 X 向水平、法向沿 +Y 的立墙切除工作面。"""

    return cq.Plane(
        origin=(0.0, wall_y_min - boolean_overlap, center_z),
        xDir=(1.0, 0.0, 0.0),
        normal=(0.0, 1.0, 0.0),
    )


opening_cutter = (
    cq.Workplane(make_positive_y_cut_plane(opening_center_z))
    .rect(opening_size_x, opening_size_z)
    .extrude(wall_size_y + 2.0 * boolean_overlap)
)
wall = wall.cut(opening_cutter)


# =========================
# 第 4 步：上下剩余横梁中心的两个直径 2.2 贯穿孔
# =========================

for hole_center_z in fixing_hole_centers_z:
    fixing_hole_cutter = (
        cq.Workplane(make_positive_y_cut_plane(hole_center_z))
        .circle(fixing_hole_diameter / 2.0)
        .extrude(wall_size_y + 2.0 * boolean_overlap)
    )
    wall = wall.cut(fixing_hole_cutter)


# =========================
# 最终合并与显示
# =========================

result = base.union(wall).clean()

show_object(result, name="侧式舵机固定座")
