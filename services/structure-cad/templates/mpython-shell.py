import cadquery as cq

# ============================================================
# 掌控板外壳：底壳、固定结构与上盖
# 单位：mm
#
# 全局方向约定：
# - 掌控板显示屏面朝 +Z。
# - Type-C 接口和两个按钮所在侧面朝 +Y。
# - 金手指位于 +Z 面并紧贴 -Y 边。
# - 两个麦克风位于 +Z 面，中心在 X 轴上，分别靠近 +X/-X 边。
# - 喇叭位于 -Z 面中央。
#
# 当前脚本生成底壳、-Y 固定块、两个 M2 自攻螺丝柱，
# 以及带贯穿孔的独立上盖；不生成掌控板或其他结构。
# 底壳内腔在 X/Y 方向以原点为中心；内底面为 Z=0。
# +Y 侧壁完全省略，底板也只延伸到内腔的 +Y 边线。
# ============================================================

# =========================
# 参数区
# =========================
inner_size_x = 52.0
inner_size_y = 47.5
inner_height_z = 6.1

wall_thickness = 1.5
bottom_thickness = 1.5

# 上下壳四个外侧竖直角统一采用 R3，底壳内角保持直角。
outer_corner_radius = 3.0
shell_cavity_cut_overlap = 0.1

# 靠近 -Y 内壁的实心固定块。
fixing_block_size_x = 52.0
fixing_block_size_y = 7.0
fixing_block_height_z = 4.2

# 两个 M2 自攻螺丝柱。
screw_boss_center_spacing_x = 24.0
screw_boss_center_y = 19.8
screw_boss_outer_diameter = 6.5
screw_boss_hole_diameter = 2.4
screw_boss_height_z = 4.3

# 上盖基础尺寸。
top_cover_thickness = 3.2

# 上盖贯穿孔。
screen_opening_size_x = 41.3
screen_opening_size_y = 26.8
screen_opening_center_y = 1.5

# D5.3 麦克风孔与屏幕孔各重叠约 0.3mm，按确认意图形成连通开口。
microphone_hole_diameter = 5.3
microphone_hole_center_spacing_x = 46.0
microphone_hole_center_y = 0.0

top_cover_screw_hole_diameter = 2.4
top_cover_screw_counterbore_diameter = 4.5
top_cover_screw_counterbore_depth = 2.0

light_sensor_opening_size_x = 4.0
light_sensor_opening_size_y = 3.0
light_sensor_center_offset_from_negative_y = 9.2

led_opening_size_x = 18.0
led_opening_size_y = 4.0
led_center_offset_from_positive_y = 6.0

# 切刀在上盖上下各多伸出此距离，避免共面导致贯穿失败。
opening_cut_overlap = 0.1

# 由内尺寸和厚度推导外尺寸。
# X 方向保留两侧壁，因此增加 2 倍壁厚。
# Y 方向只保留 -Y 侧壁，因此只增加 1 倍壁厚。
outer_size_x = inner_size_x + 2.0 * wall_thickness
outer_size_y = inner_size_y + wall_thickness

# 内腔边界。
inner_x_min = -inner_size_x / 2.0
inner_x_max = inner_size_x / 2.0
inner_y_min = -inner_size_y / 2.0
inner_y_max = inner_size_y / 2.0

# 外轮廓边界：+Y 外边与内腔 +Y 边重合。
outer_x_min = inner_x_min - wall_thickness
outer_x_max = inner_x_max + wall_thickness
outer_y_min = inner_y_min - wall_thickness
outer_y_max = inner_y_max

outer_center_y = (outer_y_min + outer_y_max) / 2.0

# 底壳先生成圆角外实体，再从 Z=0 向上切除内腔和 +Y 开口。
bottom_outer_height = inner_height_z + bottom_thickness
bottom_cavity_cutter_max_y = outer_y_max + shell_cavity_cut_overlap
bottom_cavity_cutter_size_y = bottom_cavity_cutter_max_y - inner_y_min
bottom_cavity_cutter_center_y = (
    inner_y_min + bottom_cavity_cutter_max_y
) / 2.0
bottom_cavity_cutter_height = inner_height_z + shell_cavity_cut_overlap

# 固定块紧贴 -Y 内壁，两个螺丝柱关于 Y 轴对称。
fixing_block_center_y = inner_y_min + fixing_block_size_y / 2.0
negative_x_screw_boss_center = -screw_boss_center_spacing_x / 2.0
positive_x_screw_boss_center = screw_boss_center_spacing_x / 2.0

# 上盖和孔位坐标。
top_cover_bottom_z = inner_height_z
top_cover_top_z = top_cover_bottom_z + top_cover_thickness
top_cover_center_y = outer_center_y

negative_x_microphone_hole_center = -microphone_hole_center_spacing_x / 2.0
positive_x_microphone_hole_center = microphone_hole_center_spacing_x / 2.0

light_sensor_opening_center_y = (
    inner_y_min + light_sensor_center_offset_from_negative_y
)
led_opening_center_y = outer_y_max - led_center_offset_from_positive_y

opening_cutter_start_z = top_cover_bottom_z - opening_cut_overlap
opening_cutter_height = top_cover_thickness + 2.0 * opening_cut_overlap

# 台阶孔从上盖 +Z 面向下切除 2mm，仅在顶部增加切刀余量。
counterbore_cutter_start_z = (
    top_cover_top_z - top_cover_screw_counterbore_depth
)
counterbore_cutter_height = (
    top_cover_screw_counterbore_depth + opening_cut_overlap
)


# =========================
# 通用圆角棱柱生成函数
# 通过两个矩形核心和四个圆柱角构造 XY 外轮廓，避免复杂布尔后选边倒角。
# =========================
def make_rounded_xy_prism(size_x, size_y, radius, height, center_y, bottom_z):
    center_x_prism = (
        cq.Workplane("XY")
        .box(
            size_x - 2.0 * radius,
            size_y,
            height,
            centered=(True, True, False),
        )
        .translate((0.0, center_y, bottom_z))
    )

    center_y_prism = (
        cq.Workplane("XY")
        .box(
            size_x,
            size_y - 2.0 * radius,
            height,
            centered=(True, True, False),
        )
        .translate((0.0, center_y, bottom_z))
    )

    rounded_prism = center_x_prism.union(center_y_prism)
    corner_offset_x = size_x / 2.0 - radius
    corner_offset_y = size_y / 2.0 - radius

    for corner_x in (-corner_offset_x, corner_offset_x):
        for corner_y in (
            center_y - corner_offset_y,
            center_y + corner_offset_y,
        ):
            corner_cylinder = (
                cq.Workplane("XY")
                .center(corner_x, corner_y)
                .circle(radius)
                .extrude(height)
                .translate((0.0, 0.0, bottom_z))
            )
            rounded_prism = rounded_prism.union(corner_cylinder)

    return rounded_prism


# =========================
# 阶段 1：外角 R3、内角直角的底壳基础体
# 外实体范围为 Z=-1.5 到 6.1；直角内腔从 Z=0 向上切除，
# 并直接延伸越过 +Y 外边以保持完整开口。
# =========================
bottom_outer_solid = make_rounded_xy_prism(
    outer_size_x,
    outer_size_y,
    outer_corner_radius,
    bottom_outer_height,
    outer_center_y,
    -bottom_thickness,
)

bottom_cavity_cutter = (
    cq.Workplane("XY")
    .box(
        inner_size_x,
        bottom_cavity_cutter_size_y,
        bottom_cavity_cutter_height,
        centered=(True, True, False),
    )
    .translate((0.0, bottom_cavity_cutter_center_y, 0.0))
)

bottom_shell_base = bottom_outer_solid.cut(bottom_cavity_cutter)

# =========================
# 阶段 2：-Y 实心固定块
# 范围：X=-26 到 +26，Y=-23.75 到 -16.75，Z=0 到 4.2。
# 固定块填满 X 方向内空间，并与底板和三面侧壁连成一体。
# =========================
fixing_block = (
    cq.Workplane("XY")
    .box(
        fixing_block_size_x,
        fixing_block_size_y,
        fixing_block_height_z,
        centered=(True, True, False),
    )
    .translate((0.0, fixing_block_center_y, 0.0))
)

# =========================
# 阶段 3：两个 M2 自攻螺丝柱
# 圆心为 (-12, 19.8) 和 (12, 19.8)，外径 6.5，内孔直径 2.4。
# 柱体和内孔都从 Z=0 向 +Z 延伸 4.3，内孔不会切入下方底板。
# =========================
negative_x_screw_boss_outer = (
    cq.Workplane("XY")
    .center(negative_x_screw_boss_center, screw_boss_center_y)
    .circle(screw_boss_outer_diameter / 2.0)
    .extrude(screw_boss_height_z)
)

negative_x_screw_boss_hole = (
    cq.Workplane("XY")
    .center(negative_x_screw_boss_center, screw_boss_center_y)
    .circle(screw_boss_hole_diameter / 2.0)
    .extrude(screw_boss_height_z)
)

negative_x_screw_boss = negative_x_screw_boss_outer.cut(
    negative_x_screw_boss_hole
)

positive_x_screw_boss_outer = (
    cq.Workplane("XY")
    .center(positive_x_screw_boss_center, screw_boss_center_y)
    .circle(screw_boss_outer_diameter / 2.0)
    .extrude(screw_boss_height_z)
)

positive_x_screw_boss_hole = (
    cq.Workplane("XY")
    .center(positive_x_screw_boss_center, screw_boss_center_y)
    .circle(screw_boss_hole_diameter / 2.0)
    .extrude(screw_boss_height_z)
)

positive_x_screw_boss = positive_x_screw_boss_outer.cut(
    positive_x_screw_boss_hole
)

# 合并为一个连续底壳实体。
bottom_shell = (
    bottom_shell_base
    .union(fixing_block)
    .union(negative_x_screw_boss)
    .union(positive_x_screw_boss)
)

# =========================
# 阶段 4：带 R3 外角的上盖基础板
# 与底壳外轮廓完全重合，范围为：
# X=-27.5 到 +27.5，Y=-25.25 到 +23.75，Z=6.1 到 9.3。
# =========================
top_cover_blank = make_rounded_xy_prism(
    outer_size_x,
    outer_size_y,
    outer_corner_radius,
    top_cover_thickness,
    top_cover_center_y,
    top_cover_bottom_z,
)

# =========================
# 阶段 5：矩形贯穿孔切刀
# 屏幕孔中心 (0, 1.5)。
# 光线传感器孔中心 (0, -14.55)。
# LED 孔中心 (0, 17.75)。
# =========================
screen_opening_cutter = (
    cq.Workplane("XY")
    .box(
        screen_opening_size_x,
        screen_opening_size_y,
        opening_cutter_height,
        centered=(True, True, False),
    )
    .translate((0.0, screen_opening_center_y, opening_cutter_start_z))
)

light_sensor_opening_cutter = (
    cq.Workplane("XY")
    .box(
        light_sensor_opening_size_x,
        light_sensor_opening_size_y,
        opening_cutter_height,
        centered=(True, True, False),
    )
    .translate((0.0, light_sensor_opening_center_y, opening_cutter_start_z))
)

led_opening_cutter = (
    cq.Workplane("XY")
    .box(
        led_opening_size_x,
        led_opening_size_y,
        opening_cutter_height,
        centered=(True, True, False),
    )
    .translate((0.0, led_opening_center_y, opening_cutter_start_z))
)

# =========================
# 阶段 6：圆形贯穿孔切刀
# 两个麦克风孔中心为 (-23, 0) 和 (23, 0)。
# 两个螺丝孔中心与底壳柱孔一致，为 (-12, 19.8) 和 (12, 19.8)。
# =========================
negative_x_microphone_hole_cutter = (
    cq.Workplane("XY")
    .center(negative_x_microphone_hole_center, microphone_hole_center_y)
    .circle(microphone_hole_diameter / 2.0)
    .extrude(opening_cutter_height)
    .translate((0.0, 0.0, opening_cutter_start_z))
)

positive_x_microphone_hole_cutter = (
    cq.Workplane("XY")
    .center(positive_x_microphone_hole_center, microphone_hole_center_y)
    .circle(microphone_hole_diameter / 2.0)
    .extrude(opening_cutter_height)
    .translate((0.0, 0.0, opening_cutter_start_z))
)

negative_x_top_cover_screw_hole_cutter = (
    cq.Workplane("XY")
    .center(negative_x_screw_boss_center, screw_boss_center_y)
    .circle(top_cover_screw_hole_diameter / 2.0)
    .extrude(opening_cutter_height)
    .translate((0.0, 0.0, opening_cutter_start_z))
)

positive_x_top_cover_screw_hole_cutter = (
    cq.Workplane("XY")
    .center(positive_x_screw_boss_center, screw_boss_center_y)
    .circle(top_cover_screw_hole_diameter / 2.0)
    .extrude(opening_cutter_height)
    .translate((0.0, 0.0, opening_cutter_start_z))
)

# =========================
# 阶段 7：上盖螺丝孔平底台阶
# 从上盖 +Z 面向下切直径 4.5、深度 2.0 的同轴圆柱凹槽。
# 台阶底面为 Z=7.3，下方保留 1.2 厚度并连接 D2.4 贯穿孔。
# =========================
negative_x_top_cover_counterbore_cutter = (
    cq.Workplane("XY")
    .center(negative_x_screw_boss_center, screw_boss_center_y)
    .circle(top_cover_screw_counterbore_diameter / 2.0)
    .extrude(counterbore_cutter_height)
    .translate((0.0, 0.0, counterbore_cutter_start_z))
)

positive_x_top_cover_counterbore_cutter = (
    cq.Workplane("XY")
    .center(positive_x_screw_boss_center, screw_boss_center_y)
    .circle(top_cover_screw_counterbore_diameter / 2.0)
    .extrude(counterbore_cutter_height)
    .translate((0.0, 0.0, counterbore_cutter_start_z))
)

# 只对上盖依次切孔和台阶，底壳保持不变。
top_cover = (
    top_cover_blank
    .cut(screen_opening_cutter)
    .cut(light_sensor_opening_cutter)
    .cut(led_opening_cutter)
    .cut(negative_x_microphone_hole_cutter)
    .cut(positive_x_microphone_hole_cutter)
    .cut(negative_x_top_cover_screw_hole_cutter)
    .cut(positive_x_top_cover_screw_hole_cutter)
    .cut(negative_x_top_cover_counterbore_cutter)
    .cut(positive_x_top_cover_counterbore_cutter)
)

# result 指向上盖，便于单独导出上盖 STL。
result = top_cover

# CQ-editor 中将底壳与上盖作为两个独立对象显示。
show_object(bottom_shell, name="掌控板外壳_底壳")
show_object(top_cover, name="掌控板外壳_上盖")
