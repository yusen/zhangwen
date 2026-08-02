import math

import cadquery as cq


SURFACE_ENGRAVING_REPORT = []
SURFACE_SELECTOR_VERSION = 'planar_surface_selector_v3'


class SurfaceEngravingError(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _as_tuple(value, fallback):
    values = value if isinstance(value, (list, tuple)) else fallback
    if len(values) != 3:
        return tuple(float(item) for item in fallback)
    return tuple(float(item) for item in values)


def _add(a, b):
    return tuple(a[index] + b[index] for index in range(3))


def _sub(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def _mul(value, scalar):
    return tuple(item * scalar for item in value)


def _dot(a, b):
    return sum(a[index] * b[index] for index in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(value):
    return math.sqrt(max(0.0, _dot(value, value)))


def _normalize(value, fallback=(0.0, 0.0, 1.0)):
    vector = _as_tuple(value, fallback)
    length = _length(vector)
    if length <= 1e-9:
        return _as_tuple(fallback, (0.0, 0.0, 1.0))
    return _mul(vector, 1.0 / length)


def _number(value, fallback=0.0):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return result if math.isfinite(result) else float(fallback)


def _shape_from_part(part):
    values = part.vals()
    if not values:
        raise SurfaceEngravingError(
            'empty_part',
            '当前项目模型已存在，但所选刻字目标零件没有实体；请改选模型上实际存在的外部平面。',
        )
    if len(values) == 1:
        return values[0]
    return cq.Compound.makeCompound(values)


def _face_center(face):
    center = face.Center()
    return (float(center.x), float(center.y), float(center.z))


def _face_normal(face):
    try:
        normal = face.normalAt()
    except Exception:
        normal = face.normalAt(0.5, 0.5)
    return _normalize((normal.x, normal.y, normal.z))


def _face_vertices(face):
    result = []
    try:
        tessellated_vertices, _ = face.tessellate(0.05)
    except Exception:
        tessellated_vertices = []
    for vertex in tessellated_vertices:
        point = vertex.toTuple()
        result.append((float(point[0]), float(point[1]), float(point[2])))
    for vertex in face.Vertices():
        point = vertex.toTuple()
        result.append((float(point[0]), float(point[1]), float(point[2])))
    if result:
        return result
    box = face.BoundingBox()
    result.extend([
        (float(x), float(y), float(z))
        for x in (box.xmin, box.xmax)
        for y in (box.ymin, box.ymax)
        for z in (box.zmin, box.zmax)
    ])
    return result


def _face_area(face):
    try:
        return max(0.0, float(face.Area()))
    except Exception:
        return 0.0


def _point_to_plane_distance(point, plane_point, normal):
    return abs(_dot(_sub(point, plane_point), normal))


def _project_to_plane(point, plane_point, normal):
    signed_distance = _dot(_sub(point, plane_point), normal)
    return _sub(point, _mul(normal, signed_distance))


def _point_to_face_distance(face, point):
    try:
        return float(face.distance(cq.Vertex.makeVertex(*point)))
    except Exception:
        return float('inf')


def _projection_is_on_trimmed_face(face, projected_point, tolerance):
    return _point_to_face_distance(face, projected_point) <= tolerance


def _point_inside_shape(shape, point, tolerance):
    try:
        solids = shape.Solids()
    except Exception:
        solids = []
    for solid in solids:
        try:
            if solid.isInside(cq.Vector(*point), tolerance):
                return True
        except Exception:
            continue
    return False


def _locally_outward_visible(shape, point, normal, tolerance):
    ray_origin = _add(point, _mul(normal, max(0.05, tolerance * 2.0)))
    try:
        intersections = shape.facesIntersectedByLine(
            cq.Vector(*ray_origin),
            cq.Vector(*normal),
            tol=max(1e-4, tolerance * 0.25),
            direction='AlongAxis',
        )
    except Exception:
        # 外部平面判定是安全边界；无法完成无限射线检查时按不可见处理。
        return False
    return len(intersections) == 0


def _pair_hint(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    first = _number(value[0], -1.0)
    second = _number(value[1], -1.0)
    if first <= 0.0 or second <= 0.0:
        return None
    return (first, second)


def _relative_error(actual, expected):
    if expected <= 1e-9:
        return 0.0
    return abs(actual - expected) / expected


def _candidate_signature_error(area, span, spec):
    errors = []
    area_hint = _number(spec.get('surface_area_hint_mm2'), 0.0)
    if area_hint > 0.0:
        errors.append(_relative_error(area, area_hint))
    span_hint = _pair_hint(spec.get('surface_span_hint_mm'))
    if span_hint:
        direct = (
            _relative_error(span[0], span_hint[0])
            + _relative_error(span[1], span_hint[1])
        ) / 2.0
        swapped = (
            _relative_error(span[0], span_hint[1])
            + _relative_error(span[1], span_hint[0])
        ) / 2.0
        errors.append(min(direct, swapped))
    return sum(errors) / len(errors) if errors else 0.0


def _selection_reason(candidates):
    if len(candidates) == 1:
        return 'unique_normal_match', '只有一个平面同时满足法向与表面约束。'
    first, second = candidates[0], candidates[1]
    if first['plane_distance'] + 0.05 < second['plane_distance']:
        return 'nearest_reference_plane', '参考点到该候选平面的距离最近。'
    if first['projection_inside'] and not second['projection_inside']:
        return 'reference_projection_inside', '参考点的投影落在该候选面的真实裁剪边界内。'
    if first['locally_visible'] and not second['locally_visible']:
        return 'locally_outward_visible', '该候选面沿外法向在局部可见。'
    if first['signature_error'] + 0.02 < second['signature_error']:
        return 'geometry_signature_match', '该候选面的面积和局部跨度与稳定表面签名最接近。'
    if first['area'] > second['area'] * 1.05:
        return 'largest_matching_face', '法向、参考平面和可见性相同，选择面积更大的完整平面。'
    return 'nearest_face_center_tiebreak', '其他约束相同，以面中心距离作最终平局条件。'


def _candidate_report(candidate):
    return {
        'face_index': candidate['face_index'],
        'normal_alignment': round(candidate['normal_alignment'], 6),
        'point_to_plane_distance_mm': round(candidate['plane_distance'], 4),
        'reference_projection_inside': bool(candidate['projection_inside']),
        'locally_outward_visible': bool(candidate['locally_visible']),
        'area_mm2': round(candidate['area'], 3),
        'local_span_mm': [round(value, 3) for value in candidate['span']],
        'signature_error': round(candidate['signature_error'], 4),
        'center_distance_mm': round(candidate['center_distance'], 3),
        'face_center': [round(value, 3) for value in candidate['center']],
        'face_normal': [round(value, 5) for value in candidate['normal']],
    }


def _select_face(part, spec):
    normal_hint = _normalize(spec.get('normal_hint'), (0.0, 0.0, 1.0))
    point_hint = _as_tuple(spec.get('point_hint'), (0.0, 0.0, 0.0))
    candidates = []
    shape = _shape_from_part(part)
    shape_box = shape.BoundingBox()
    geometric_tolerance = max(
        0.05,
        math.sqrt(shape_box.xlen ** 2 + shape_box.ylen ** 2 + shape_box.zlen ** 2) * 1e-4,
    )
    for face_index, face in enumerate(shape.Faces()):
        if str(face.geomType()).upper() != 'PLANE':
            continue
        normal = _face_normal(face)
        normal_alignment = _dot(normal, normal_hint)
        if normal_alignment < 0.92:
            continue
        center = _face_center(face)
        plane_distance = _point_to_plane_distance(point_hint, center, normal)
        projected_point = _project_to_plane(point_hint, center, normal)
        projection_inside = _projection_is_on_trimmed_face(face, projected_point, geometric_tolerance)
        visibility_point = projected_point if projection_inside else center
        locally_visible = _locally_outward_visible(shape, visibility_point, normal, geometric_tolerance)
        plane, _, _ = _plane_for_face(face, spec)
        bounds = _local_bounds(face, plane)
        span = (max(0.0, bounds[1] - bounds[0]), max(0.0, bounds[3] - bounds[2]))
        area = _face_area(face)
        signature_error = _candidate_signature_error(area, span, spec)
        candidates.append({
            'face_index': face_index,
            'face': face,
            'normal': normal,
            'center': center,
            'normal_alignment': normal_alignment,
            'plane_distance': plane_distance,
            'projection_inside': projection_inside,
            'locally_visible': locally_visible,
            'area': area,
            'span': span,
            'signature_error': signature_error,
            'center_distance': _length(_sub(center, point_hint)),
        })
    if not candidates:
        requested_surface_id = str(spec.get('surface_id') or '')
        code = 'surface_identity_mismatch' if requested_surface_id else 'planar_face_not_found'
        raise SurfaceEngravingError(
            code,
            '没有找到与刻字描述和稳定表面身份匹配的外部平面。请重新确认目标平面。',
            {
                'failure_kind': 'surface_identity_mismatch',
                'surface_id': requested_surface_id,
                'normal_hint': normal_hint,
                'point_hint': point_hint,
                'candidate_count': 0,
                'selector_version': SURFACE_SELECTOR_VERSION,
            },
        )
    candidates.sort(key=lambda item: (
        -round(item['normal_alignment'], 6),
        round(item['plane_distance'], 4),
        0 if item['projection_inside'] else 1,
        0 if item['locally_visible'] else 1,
        round(item['signature_error'], 5),
        -round(item['area'], 4),
        -round(item['span'][0] * item['span'][1], 4),
        round(item['center_distance'], 4),
    ))
    selected = candidates[0]
    if not selected['locally_visible']:
        raise SurfaceEngravingError(
            'planar_face_not_external',
            '参考点匹配到的平面沿外法向无法通向模型外部，当前不支持在封闭内腔面刻字。',
            {
                'failure_kind': 'non_external_planar_face',
                'surface_id': str(spec.get('surface_id') or ''),
                'candidate_count': len(candidates),
                'selector_version': SURFACE_SELECTOR_VERSION,
                'selection_candidates': [_candidate_report(item) for item in candidates[:20]],
            },
        )
    has_signature = (
        _number(spec.get('surface_area_hint_mm2'), 0.0) > 0.0
        or _pair_hint(spec.get('surface_span_hint_mm')) is not None
    )
    if has_signature and selected['signature_error'] > 0.35:
        raise SurfaceEngravingError(
            'surface_identity_mismatch',
            '找到了法向相似的平面，但面积或局部跨度与已记录的表面身份不符。为避免把旧刻字移到别的面，请重新确认目标平面。',
            {
                'failure_kind': 'surface_identity_mismatch',
                'surface_id': str(spec.get('surface_id') or ''),
                'candidate_count': len(candidates),
                'selector_version': SURFACE_SELECTOR_VERSION,
                'selection_candidates': [_candidate_report(item) for item in candidates[:20]],
            },
        )
    reason_code, reason = _selection_reason(candidates)
    selection = {
        'selector_version': SURFACE_SELECTOR_VERSION,
        'candidate_count': len(candidates),
        'selection_reason_code': reason_code,
        'selection_reason': reason,
        'selected_face_area_mm2': round(selected['area'], 3),
        'selected_face_local_span_mm': [round(value, 3) for value in selected['span']],
        'point_to_plane_distance_mm': round(selected['plane_distance'], 4),
        'reference_projection_inside': bool(selected['projection_inside']),
        'locally_outward_visible': bool(selected['locally_visible']),
        'selection_candidates': [_candidate_report(item) for item in candidates[:20]],
    }
    return selected['face'], selection


def _plane_for_face(face, spec):
    origin = _face_center(face)
    normal = _face_normal(face)
    requested_x = _as_tuple(spec.get('x_direction'), (1.0, 0.0, 0.0))
    projected_x = _sub(requested_x, _mul(normal, _dot(requested_x, normal)))
    if _length(projected_x) <= 1e-8:
        for candidate in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
            projected_x = _sub(candidate, _mul(normal, _dot(candidate, normal)))
            if _length(projected_x) > 1e-8:
                break
    x_direction = _normalize(projected_x, (1.0, 0.0, 0.0))
    return cq.Plane(origin=origin, xDir=x_direction, normal=normal), origin, normal


def _local_bounds(face, plane):
    points = _face_vertices(face)
    if not points:
        raise SurfaceEngravingError('face_has_no_vertices', '目标平面没有可用于定位的边界顶点。')
    origin = (float(plane.origin.x), float(plane.origin.y), float(plane.origin.z))
    x_direction = (float(plane.xDir.x), float(plane.xDir.y), float(plane.xDir.z))
    normal = (float(plane.zDir.x), float(plane.zDir.y), float(plane.zDir.z))
    y_direction = _normalize(_cross(normal, x_direction), (0.0, 1.0, 0.0))
    local = []
    for point in points:
        delta = _sub(point, origin)
        local.append((_dot(delta, x_direction), _dot(delta, y_direction)))
    return (
        min(item[0] for item in local),
        max(item[0] for item in local),
        min(item[1] for item in local),
        max(item[1] for item in local),
    )


def _anchor_ratio(anchor):
    values = {
        'left': -0.5,
        'center': 0.0,
        'right': 0.5,
        'top': 0.5,
        'bottom': -0.5,
    }
    text = str(anchor or 'center').lower()
    horizontal = 'right' if 'right' in text else 'left' if 'left' in text else 'center'
    vertical = 'top' if 'top' in text else 'bottom' if 'bottom' in text else 'center'
    return values[horizontal], values[vertical]


def _anchor_center(bounds, spec, text_width, text_height, margin):
    min_u, max_u, min_v, max_v = bounds
    horizontal, vertical = _anchor_ratio(spec.get('anchor'))
    offset_u = _number(spec.get('offset_u_mm'))
    offset_v = _number(spec.get('offset_v_mm'))
    if horizontal < 0:
        center_u = min_u + margin + text_width / 2.0
    elif horizontal > 0:
        center_u = max_u - margin - text_width / 2.0
    else:
        center_u = (min_u + max_u) / 2.0
    if vertical < 0:
        center_v = min_v + margin + text_height / 2.0
    elif vertical > 0:
        center_v = max_v - margin - text_height / 2.0
    else:
        center_v = (min_v + max_v) / 2.0
    center_u += offset_u
    center_v += offset_v
    return center_u, center_v


def _anchored_available_extent(minimum, maximum, margin, anchor_ratio, offset):
    usable_minimum = minimum + margin
    usable_maximum = maximum - margin
    if usable_maximum <= usable_minimum:
        return 0.0
    if anchor_ratio < 0.0:
        anchored_edge = usable_minimum + offset
        if anchored_edge < usable_minimum:
            return 0.0
        return max(0.0, usable_maximum - anchored_edge)
    if anchor_ratio > 0.0:
        anchored_edge = usable_maximum + offset
        if anchored_edge > usable_maximum:
            return 0.0
        return max(0.0, anchored_edge - usable_minimum)
    center = (usable_minimum + usable_maximum) / 2.0 + offset
    return max(0.0, 2.0 * min(center - usable_minimum, usable_maximum - center))


def _font_choices(text):
    is_cjk = any(
        (0x3400 <= ord(char) <= 0x9FFF)
        or (0xF900 <= ord(char) <= 0xFAFF)
        for char in str(text)
    )
    candidates = (
        ("SimHei", r"C:\\Windows\\Fonts\\simhei.ttf"),
        ("Microsoft YaHei", r"C:\\Windows\\Fonts\\msyh.ttc"),
        ("Noto Sans CJK SC", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ("Noto Sans CJK SC", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
        ("Arial", r"C:\\Windows\\Fonts\\arial.ttf"),
        ("Arial", "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"),
    )
    return [(name, path) for name, path in candidates if not (is_cjk and name == 'Arial')], is_cjk


def _shape_vertices(shape):
    result = []
    try:
        tessellated_vertices, _ = shape.tessellate(0.02)
    except Exception:
        tessellated_vertices = []
    for vertex in tessellated_vertices:
        point = vertex.toTuple()
        result.append(cq.Vector(float(point[0]), float(point[1]), float(point[2])))
    try:
        result.extend(shape.Vertices())
    except Exception:
        pass
    return result


def _local_shape_bounds(shape, plane):
    origin = (float(plane.origin.x), float(plane.origin.y), float(plane.origin.z))
    x_direction = (float(plane.xDir.x), float(plane.xDir.y), float(plane.xDir.z))
    normal = (float(plane.zDir.x), float(plane.zDir.y), float(plane.zDir.z))
    y_direction = _normalize(_cross(normal, x_direction), (0.0, 1.0, 0.0))
    points = []
    for vertex in _shape_vertices(shape):
        point = vertex.toTuple()
        delta = _sub((float(point[0]), float(point[1]), float(point[2])), origin)
        points.append((_dot(delta, x_direction), _dot(delta, y_direction)))
    if not points:
        box = shape.BoundingBox()
        points = [
            (float(box.xmin), float(box.ymin)),
            (float(box.xmax), float(box.ymax)),
        ]
    return (
        min(item[0] for item in points),
        max(item[0] for item in points),
        min(item[1] for item in points),
        max(item[1] for item in points),
    )


def _text_lines(spec):
    raw_lines = spec.get('lines')
    if isinstance(raw_lines, (list, tuple)):
        lines = [str(item).strip() for item in raw_lines if str(item).strip()]
    else:
        text = str(spec.get('text') or '').replace('\r\n', '\n').replace('\r', '\n')
        lines = [item.strip() for item in text.split('\n') if item.strip()]
    if not lines:
        raise SurfaceEngravingError('empty_text', '刻字内容不能为空。')
    if len(lines) > 32:
        raise SurfaceEngravingError('text_too_long', '多行刻字最多支持 32 行。')
    if sum(len(line) for line in lines) > 256 or any(len(line) > 32 for line in lines):
        raise SurfaceEngravingError('text_too_long', '多行刻字总计最多 256 个字符，且每行不超过 32 个字符。')
    for line in lines:
        if any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or char in ('\u2028', '\u2029') for char in line):
            raise SurfaceEngravingError('invalid_text', '刻字不能包含空行、制表符或其他控制字符。')
    return lines


def _text_workplane(plane, center_u, center_v, spec, depth, allow_probe=False, text_override=None, font_height_override=None):
    text = str(text_override if text_override is not None else spec.get('text') or '')
    font_height = _number(font_height_override if font_height_override is not None else spec.get('font_height_mm'))
    if not text:
        raise SurfaceEngravingError('empty_text', '刻字内容不能为空。')
    if any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or char in ('\u2028', '\u2029') for char in text):
        raise SurfaceEngravingError('invalid_text', '单行刻字不能包含换行、制表符或其他控制字符。')
    if len(text) > 32:
        raise SurfaceEngravingError('text_too_long', '单行刻字最多支持 32 个字符。')
    if font_height < 3.0 and not allow_probe:
        raise SurfaceEngravingError('font_height_too_small', '字体高度不能小于 3mm。')
    workplane = cq.Workplane(plane).center(center_u, center_v)
    font_choices, is_cjk = _font_choices(text)
    cutter = None
    for font_name, font_path in font_choices:
        try:
            cutter = workplane.text(
                text,
                font_height,
                -float(depth),
                combine=False,
                font=font_name,
                fontPath=font_path,
                kind='bold' if str(spec.get('font_kind') or '').lower() == 'bold' else 'regular',
                halign='center',
                valign='center',
            )
            break
        except Exception:
            cutter = None
    if cutter is None:
        if is_cjk:
            raise SurfaceEngravingError('cjk_font_missing', '当前环境没有可用的中文刻字字体。')
        raise SurfaceEngravingError('font_missing', '当前环境没有可用的刻字字体。')
    return cutter


def _rotated_size(width, height, rotation_deg):
    angle = math.radians(_number(rotation_deg))
    cosine = abs(math.cos(angle))
    sine = abs(math.sin(angle))
    return (
        width * cosine + height * sine,
        width * sine + height * cosine,
    )


def _rotate_uv(offset_u, offset_v, rotation_deg):
    angle = math.radians(_number(rotation_deg))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return (
        offset_u * cosine - offset_v * sine,
        offset_u * sine + offset_v * cosine,
    )


def _plane_local_point(plane, u, v):
    origin = (float(plane.origin.x), float(plane.origin.y), float(plane.origin.z))
    x_direction = (float(plane.xDir.x), float(plane.xDir.y), float(plane.xDir.z))
    normal = (float(plane.zDir.x), float(plane.zDir.y), float(plane.zDir.z))
    y_direction = _normalize(_cross(normal, x_direction), (0.0, 1.0, 0.0))
    return _add(origin, _add(_mul(x_direction, u), _mul(y_direction, v)))


def _preflight_text(part, face, plane, spec):
    bounds = _local_bounds(face, plane)
    margin = max(0.8, _number(spec.get('depth_mm'), 0.6) + 0.2)
    lines = _text_lines(spec)
    line_spacing_ratio = min(3.0, max(0.8, _number(spec.get('line_spacing_ratio'), 1.2)))
    probe_spec = dict(spec)
    probe_spec['font_height_mm'] = 1.0
    line_sizes_per_unit = []
    for line in lines:
        probe = _text_workplane(
            plane,
            0.0,
            0.0,
            probe_spec,
            0.1,
            allow_probe=True,
            text_override=line,
            font_height_override=1.0,
        )
        probe_shape = probe.val() if len(probe.vals()) == 1 else cq.Compound.makeCompound(probe.vals())
        probe_bounds = _local_shape_bounds(probe_shape, plane)
        line_sizes_per_unit.append((
            max(0.001, probe_bounds[1] - probe_bounds[0]),
            max(0.001, probe_bounds[3] - probe_bounds[2]),
        ))
    unrotated_width_per_unit = max(item[0] for item in line_sizes_per_unit)
    glyph_height_per_unit = max(item[1] for item in line_sizes_per_unit)
    unrotated_height_per_unit = glyph_height_per_unit + line_spacing_ratio * max(0, len(lines) - 1)
    rotation = _number(spec.get('rotation_deg'))
    width_per_unit, block_height_per_unit = _rotated_size(
        unrotated_width_per_unit,
        unrotated_height_per_unit,
        rotation,
    )
    horizontal_anchor, vertical_anchor = _anchor_ratio(spec.get('anchor'))
    available_width = _anchored_available_extent(
        bounds[0],
        bounds[1],
        margin,
        horizontal_anchor,
        _number(spec.get('offset_u_mm')),
    )
    available_height = _anchored_available_extent(
        bounds[2],
        bounds[3],
        margin,
        vertical_anchor,
        _number(spec.get('offset_v_mm')),
    )
    max_font_height = max(0.0, min(available_width / width_per_unit, available_height / block_height_per_unit))
    requested = _number(spec.get('font_height_mm'))
    if requested > max_font_height + 0.05:
        raise SurfaceEngravingError(
            'font_height_too_large',
            f'当前字体高度超过目标面的可用边界（边界估算上限约 {max_font_height:.2f}mm）。',
            {
                'failure_kind': 'original_face_too_small',
                'max_font_height_mm': round(max_font_height, 2),
                'face_bounds': [round(value, 3) for value in bounds],
                'available_size_uv': [round(available_width, 3), round(available_height, 3)],
            },
        )
    text_width = width_per_unit * requested
    text_height = block_height_per_unit * requested
    center_u, center_v = _anchor_center(bounds, spec, text_width, text_height, margin)
    if (
        center_u - text_width / 2.0 < bounds[0] + margin - 0.05
        or center_u + text_width / 2.0 > bounds[1] - margin + 0.05
        or center_v - text_height / 2.0 < bounds[2] + margin - 0.05
        or center_v + text_height / 2.0 > bounds[3] - margin + 0.05
    ):
        raise SurfaceEngravingError(
            'engraving_out_of_bounds',
            '刻字偏移后超出原始目标面边界，请调整位置或偏移量。',
            {
                'failure_kind': 'original_face_out_of_bounds',
                'max_font_height_mm': round(max_font_height, 2),
                'face_bounds': [round(value, 3) for value in bounds],
            },
        )
    line_pitch = line_spacing_ratio * requested
    top_line_offset_v = line_pitch * (len(lines) - 1) / 2.0
    unrotated_line_centers = [
        [center_u, center_v + top_line_offset_v - index * line_pitch]
        for index in range(len(lines))
    ]
    line_centers = []
    for line_center_u, line_center_v in unrotated_line_centers:
        rotated_u, rotated_v = _rotate_uv(
            line_center_u - center_u,
            line_center_v - center_v,
            rotation,
        )
        line_centers.append([center_u + rotated_u, center_v + rotated_v])
    return {
        'face_bounds': [round(value, 3) for value in bounds],
        'max_font_height_mm': round(max_font_height, 2),
        'requested_font_height_mm': requested,
        'center_uv': [round(center_u, 3), round(center_v, 3)],
        'text_size_uv': [round(text_width, 3), round(text_height, 3)],
        'unrotated_text_size_uv': [
            round(unrotated_width_per_unit * requested, 3),
            round(unrotated_height_per_unit * requested, 3),
        ],
        'rotation_deg': rotation,
        'lines': lines,
        'line_count': len(lines),
        'line_spacing_ratio': line_spacing_ratio,
        'line_centers_uv': [[round(value, 3) for value in center] for center in line_centers],
        'unrotated_line_centers_uv': [
            [round(value, 3) for value in center]
            for center in unrotated_line_centers
        ],
    }


def _engrave_one(part, reference_part, spec):
    face, selection = _select_face(reference_part, spec)
    plane, origin, normal = _plane_for_face(face, spec)
    try:
        preflight = _preflight_text(reference_part, face, plane, spec)
    except SurfaceEngravingError as error:
        details = dict(error.details or {})
        details.update({
            'engraving_id': str(spec.get('id') or ''),
            'surface_id': str(spec.get('surface_id') or ''),
            'face_center': [round(value, 3) for value in origin],
            'face_normal': [round(value, 4) for value in normal],
            'selection': selection,
            'selector_version': selection.get('selector_version'),
            'candidate_count': selection.get('candidate_count'),
            'selection_reason': selection.get('selection_reason'),
            'selected_face_area_mm2': selection.get('selected_face_area_mm2'),
            'selected_face_local_span_mm': selection.get('selected_face_local_span_mm'),
            'point_to_plane_distance_mm': selection.get('point_to_plane_distance_mm'),
        })
        error.details = details
        raise
    cutter_values = []
    for line, center in zip(preflight['lines'], preflight['unrotated_line_centers_uv']):
        cutter = _text_workplane(
            plane,
            center[0],
            center[1],
            spec,
            _number(spec.get('depth_mm'), 0.6),
            text_override=line,
        )
        cutter_values.extend(cutter.vals())
    cutter_shape = cutter_values[0] if len(cutter_values) == 1 else cq.Compound.makeCompound(cutter_values)
    rotation = _number(spec.get('rotation_deg'))
    if abs(rotation) > 0.001:
        rotation_origin = _plane_local_point(
            plane,
            preflight['center_uv'][0],
            preflight['center_uv'][1],
        )
        cutter_shape = cutter_shape.rotate(rotation_origin, _add(rotation_origin, normal), rotation)
    cutter_bounds = _local_shape_bounds(cutter_shape, plane)
    cutter_center_uv = [
        round((cutter_bounds[0] + cutter_bounds[1]) / 2.0, 3),
        round((cutter_bounds[2] + cutter_bounds[3]) / 2.0, 3),
    ]
    reference_shape = _shape_from_part(reference_part)
    part_shape = _shape_from_part(part)
    cutter_volume = float(cutter_shape.Volume())
    allow_original_feature_intersection = spec.get('allow_original_feature_intersection') is True
    if cutter_volume <= 1e-6:
        raise SurfaceEngravingError(
            'engraving_invalid_cutter',
            '刻字切除体为空或体积过小，无法对模型执行有效凹刻。',
            {
                'failure_kind': 'invalid_engraving_cutter',
                'engraving_id': str(spec.get('id') or ''),
                'surface_id': str(spec.get('surface_id') or ''),
                'cutter_volume': round(cutter_volume, 5),
                'reference_intersection_volume': 0.0,
                'current_intersection_volume': 0.0,
                'reference_intersection_ratio': 0.0,
                'current_intersection_ratio': 0.0,
                'override_eligible': False,
                'allow_original_feature_intersection_requested': allow_original_feature_intersection,
                'selection': selection,
            },
        )
    reference_intersection = reference_shape.intersect(cutter_shape)
    reference_intersection_volume = float(reference_intersection.Volume())
    current_intersection = part_shape.intersect(cutter_shape)
    current_intersection_volume = float(current_intersection.Volume())
    reference_ratio = reference_intersection_volume / max(cutter_volume, 1e-6)
    current_ratio = current_intersection_volume / max(cutter_volume, 1e-6)
    reference_missing_volume = max(0.0, cutter_volume - reference_intersection_volume)
    reference_tolerance = max(1e-5, cutter_volume * 0.001)
    minimum_intersection_volume = max(1e-6, cutter_volume * 1e-6)
    if reference_intersection_volume <= minimum_intersection_volume:
        raise SurfaceEngravingError(
            'engraving_no_intersection',
            '刻字切除体与原模型没有有效交集，请重新确认目标面、位置或偏移量。',
            {
                'failure_kind': 'no_original_model_intersection',
                'engraving_id': str(spec.get('id') or ''),
                'surface_id': str(spec.get('surface_id') or ''),
                'cutter_volume': round(cutter_volume, 5),
                'reference_intersection_volume': round(reference_intersection_volume, 5),
                'current_intersection_volume': round(current_intersection_volume, 5),
                'minimum_intersection_volume': round(minimum_intersection_volume, 6),
                'reference_intersection_ratio': round(reference_ratio, 4),
                'current_intersection_ratio': round(current_ratio, 4),
                'override_eligible': False,
                'selection': selection,
            },
        )
    original_feature_conflict = reference_missing_volume > reference_tolerance
    if original_feature_conflict and not allow_original_feature_intersection:
        raise SurfaceEngravingError(
            'engraving_original_feature_conflict',
            '刻字与原模型的平面边界、开孔或螺丝孔相交，请调整位置或字号。',
            {
                'failure_kind': 'original_opening_or_boundary_conflict',
                'engraving_id': str(spec.get('id') or ''),
                'surface_id': str(spec.get('surface_id') or ''),
                'max_font_height_mm': preflight.get('max_font_height_mm'),
                'reference_intersection_ratio': round(reference_ratio, 4),
                'current_intersection_ratio': round(current_ratio, 4),
                'face_center': [round(value, 3) for value in origin],
                'face_normal': [round(value, 4) for value in normal],
                'center_uv': preflight.get('center_uv'),
                'face_bounds': preflight.get('face_bounds'),
                'text_size_uv': preflight.get('text_size_uv'),
                'cutter_center_uv': cutter_center_uv,
                'cutter_volume': round(cutter_volume, 5),
                'reference_intersection_volume': round(reference_intersection_volume, 5),
                'current_intersection_volume': round(current_intersection_volume, 5),
                'reference_missing_volume': round(reference_missing_volume, 6),
                'intersection_tolerance_volume': round(reference_tolerance, 6),
                'minimum_intersection_volume': round(minimum_intersection_volume, 6),
                'override_eligible': True,
                'allow_original_feature_intersection_requested': False,
                'selection': selection,
            },
        )
    overlap_volume = max(0.0, reference_intersection_volume - current_intersection_volume)
    overlap_tolerance = max(1e-5, reference_intersection_volume * 0.001)
    if overlap_volume > overlap_tolerance:
        raise SurfaceEngravingError(
            'engraving_overlap',
            '本次文字与已有刻字重叠，请调整位置、偏移量或修改原刻字。',
            {
                'failure_kind': 'existing_engraving_overlap',
                'engraving_id': str(spec.get('id') or ''),
                'surface_id': str(spec.get('surface_id') or ''),
                'reference_intersection_ratio': round(reference_ratio, 4),
                'current_intersection_ratio': round(current_ratio, 4),
                'face_center': [round(value, 3) for value in origin],
                'face_normal': [round(value, 4) for value in normal],
                'center_uv': preflight.get('center_uv'),
                'face_bounds': preflight.get('face_bounds'),
                'text_size_uv': preflight.get('text_size_uv'),
                'cutter_center_uv': cutter_center_uv,
                'overlap_volume': round(overlap_volume, 6),
                'intersection_tolerance_volume': round(overlap_tolerance, 6),
                'selection': selection,
            },
        )
    override_warning = None
    if original_feature_conflict:
        override_warning = {
            'code': 'engraving_original_feature_intersection_overridden',
            'id': 'engraving_original_feature_intersection_overridden',
            'status': 'warn',
            'severity': 'warning',
            'applied': True,
            'message': '已按用户确认强制刻字；文字可能被边界裁断或影响孔位。',
            'engraving_id': str(spec.get('id') or ''),
            'surface_id': str(spec.get('surface_id') or ''),
            'reference_intersection_ratio': round(reference_ratio, 4),
            'current_intersection_ratio': round(current_ratio, 4),
            'cutter_volume': round(cutter_volume, 5),
            'reference_intersection_volume': round(reference_intersection_volume, 5),
            'current_intersection_volume': round(current_intersection_volume, 5),
            'reference_missing_volume': round(reference_missing_volume, 6),
            'intersection_tolerance_volume': round(reference_tolerance, 6),
        }
    report = {
        'id': str(spec.get('id') or ''),
        'text': str(spec.get('text') or ''),
        'lines': preflight.get('lines', []),
        'line_count': preflight.get('line_count', 1),
        'target_part': str(spec.get('target_part') or ''),
        'surface_id': str(spec.get('surface_id') or ''),
        'font_height_mm': _number(spec.get('font_height_mm')),
        'depth_mm': _number(spec.get('depth_mm'), 0.6),
        'face_center': [round(value, 3) for value in origin],
        'face_normal': [round(value, 4) for value in normal],
        'center_uv': preflight.get('center_uv'),
        'cutter_center_uv': cutter_center_uv,
        'preflight': preflight,
        'intersection_ratio': round(current_ratio, 4),
        'current_intersection_ratio': round(current_ratio, 4),
        'reference_intersection_ratio': round(reference_ratio, 4),
        'cutter_volume': round(cutter_volume, 5),
        'reference_intersection_volume': round(reference_intersection_volume, 5),
        'current_intersection_volume': round(current_intersection_volume, 5),
        'reference_missing_volume': round(reference_missing_volume, 6),
        'original_feature_intersection_override': override_warning,
        'warnings': [override_warning] if override_warning else [],
        'selection': selection,
        'selector_version': selection.get('selector_version'),
        'candidate_count': selection.get('candidate_count'),
        'selection_reason': selection.get('selection_reason'),
        'selected_face_area_mm2': selection.get('selected_face_area_mm2'),
        'selected_face_local_span_mm': selection.get('selected_face_local_span_mm'),
        'point_to_plane_distance_mm': selection.get('point_to_plane_distance_mm'),
    }
    SURFACE_ENGRAVING_REPORT.append(report)
    return part.cut(cutter_shape)


def apply_surface_engraving_patch(base_part, lid_part, surface_engraving_specs):
    reference_base_part = base_part
    reference_lid_part = lid_part
    for spec in surface_engraving_specs or []:
        target_part = str(spec.get('target_part') or '')
        if target_part == 'lid_part':
            lid_part = _engrave_one(lid_part, reference_lid_part, spec)
        elif target_part == 'base_part':
            base_part = _engrave_one(base_part, reference_base_part, spec)
        else:
            raise SurfaceEngravingError('invalid_target_part', '刻字目标零件只能是 base_part 或 lid_part。')
    return base_part, lid_part
