"""Bounded panel features resolved from original Hardware Skills, never model dimensions.

The persisted result holds the exact source snapshot. Historical preview/export
can therefore be reconstructed without consulting an updated hardware library.
"""
import copy
import math
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import laser_joinery


class HardwarePlacement(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    componentId: str = Field(pattern=r'^[A-Za-z0-9_-]{1,150}$')
    skillRevision: str = Field(min_length=1, max_length=160)
    panel: Literal['top', 'bottom', 'front', 'back', 'left', 'right']
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=1000)
    rotation: Literal[0, 90, 180, 270] = 0
    method: Literal['screw', 'adhesive', 'opening_only']
    includeOpenings: bool = True


def panel_geometry(spec, panel):
    box = spec.roundedBox or spec.fingerBox
    if box is None:
        raise ValueError('电子件安装目前支持圆角盒和榫齿盒，请先选择盒体模板。')
    w, d, h, t = box.width, box.depth, box.height, box.thickness
    if spec.fingerBox:
        faces = laser_joinery.panels(w, d, h, t)
        index = ['left', 'right', 'front', 'back', 'bottom', 'top'].index(panel)
        face = faces[index]
        ox = 5 + (face['width']+5)*(index % 2)
        oy = 5 + sum(faces[i*2]['height']+5 for i in range(index//2))
        return face['width'], face['height'], lambda x, y: (ox+x, oy+y), None
    b = spec.roundedBox
    r = b.corner_radius
    a, c, arc = w-2*r, d-2*r, math.pi*(r-t/2)/2
    perimeter = 2*(a+c)+4*arc
    wall_y = d+10 if b.top_lid or b.bottom_lid else 5
    if panel in {'top', 'bottom'}:
        if not getattr(b, panel+'_lid'):
            raise ValueError('安装面已关闭：请保留对应顶盖或底盖，或调整安装面。')
        index = int(panel == 'bottom' and b.top_lid)
        return w, d, lambda x, y: (5+index*(w+5)+x, 5+y), r
    if panel == 'front':
        # The front straight edge is split by the wall's centre glue seam.
        return a, h, lambda x, y: (5+(x-a/2 if x >= a/2 else perimeter-a/2+x), wall_y+y), 'seam'
    if panel == 'right':
        return c, h, lambda x, y: (5+a/2+arc+x, wall_y+y), None
    if panel == 'back':
        return a, h, lambda x, y: (5+a/2+2*arc+c+a-x, wall_y+y), None
    return c, h, lambda x, y: (5+a/2+3*arc+c+a+c-x, wall_y+y), None


def resolve(placements, facts):
    """Resolve one current, revision-bound mechanical snapshot per component."""
    sources = {f['componentId']: f for f in facts}
    output, seen = [], set()
    for p in placements:
        if p.componentId in seen:
            raise ValueError('同一工程器件只能安排一次；多个实物请分别建立模块身份。')
        seen.add(p.componentId)
        fact = sources.get(p.componentId)
        if not fact or not fact.get('mechanicalProfile'):
            raise ValueError('所选器件缺少机械档案，请先补充尺寸与安装资料。')
        if fact['revision'] != p.skillRevision:
            raise ValueError(f'{fact["name"]}的资料已更新，请核对并使用最新资料修订。')
        source = {key: copy.deepcopy(fact[key]) for key in
                  ['componentId', 'skillName', 'revision', 'name', 'mechanicalProfile', 'documentation'] if key in fact}
        output.append(dict(placement=p.model_dump(), name=fact['name'], source=source))
    return output


def checked_snapshots(items):
    """Validate imported/replayed sources as data; never trust arbitrary objects."""
    from zhangwen.cad_engine.models import HardwareProfile
    if not isinstance(items, list) or len(items) > 33:
        raise ValueError('安装资料快照数量无效。')
    seen = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('source'), dict):
            raise ValueError('安装资料快照格式无效。')
        p = HardwarePlacement.model_validate(item.get('placement'))
        source = item['source']
        if (p.componentId in seen or source.get('componentId') != p.componentId
                or source.get('revision') != p.skillRevision
                or not isinstance(item.get('name'), str) or not 1 <= len(item['name']) <= 120
                or not isinstance(source.get('documentation', ''), str) or len(source.get('documentation', '')) > 100000):
            raise ValueError('安装资料快照与器件身份、修订不一致。')
        seen.add(p.componentId)
        HardwareProfile.model_validate(source.get('mechanicalProfile'))
        json.dumps(source.get('mechanicalProfile'), allow_nan=False)
    return items


def apply(spec, installations):
    """Return the single final drawing used by UI, SVG and DXF exports.

    Bounds are intentionally conservative AABBs. Adjacent contours require a
    full material-thickness web. No implicit slots, fasteners or 3D retainers.
    """
    from .design_specs import Drawing
    checked_snapshots(installations)
    drawing = spec.drawing.model_dump(mode='json') if spec.drawing else None
    if not installations:
        return spec.drawing, []
    if not drawing:
        raise ValueError('当前结构没有可安装的激光面板。')
    box = spec.roundedBox or spec.fingerBox
    if not box:
        raise ValueError('电子件安装目前支持圆角盒和榫齿盒。')
    t = box.thickness
    margin = max(t, 1.)
    occupied, cuts, report = [], [], []
    # Existing engravings must not be silently cut through by new features.
    for label in spec.panelTexts:
        from .laser_text import outlines
        tw, _ = outlines(label.text, label.fontSize)
        occupied.append((label.panel, (label.x, label.y, label.x+tw, label.y+label.fontSize)))

    def separated(a, b, gap=0):
        return a[2]+gap <= b[0] or b[2]+gap <= a[0] or a[3]+gap <= b[1] or b[3]+gap <= a[1]

    for item in installations:
        p = HardwarePlacement.model_validate(item['placement'])
        profile = item['source']['mechanicalProfile']
        name = item['name']
        width, height, project, rounded = panel_geometry(spec, p.panel)
        dims, mount = profile['dimensions'], profile['mounting']
        if profile['coordinate_system']['origin'] != 'envelope_center':
            raise ValueError(f'{name}使用PCB中心，尚无包络偏移资料；请改用实测包络中心档案。')
        if mount.get('mating_hardware_face') in {'+X', '-X', '+Y', '-Y'}:
            raise ValueError(f'{name}的安装孔不是档案XY平面，当前无法投影；请提供平面安装档案。')
        if mount['strategy'] == 'edge_retainer' and p.method != 'opening_only':
            raise ValueError(f'{name}要求边缘卡持；激光盒尚未生成卡持件，请另行设计固定结构。')
        surface = {'top':'lid_inner', 'bottom':'base_floor', 'front':'front_inner',
                   'back':'back_inner', 'left':'left_inner', 'right':'right_inner'}[p.panel]
        if p.method != 'opening_only' and mount.get('allowed_enclosure_surfaces') and surface not in mount['allowed_enclosure_surfaces']:
            raise ValueError(f'{name}的档案不允许安装在所选盒面，请按原资料选择安装面。')
        if p.method == 'screw' and (mount['strategy'] != 'hole_fastened' or not mount['holes']):
            raise ValueError(f'{name}缺少已声明的孔固定策略和孔位；不能自动猜测安装孔。')
        openings = profile['openings'] if p.includeOpenings else []
        if p.includeOpenings and not openings:
            raise ValueError(f'{name}尚无开口资料；请补充开口，或明确关闭“生成开口”。')
        if p.method == 'opening_only' and not openings:
            raise ValueError(f'{name}仅生成开口时必须提供并启用开口。')
        if any(o['preferred_face'] not in {'top', 'bottom'} or o.get('corner_radius', 0) for o in openings):
            raise ValueError(f'{name}包含侧向或圆角开口，当前仅支持档案XY平面的圆孔和直角矩形；不能省略或替换。')
        available = ({'top': box.height, 'bottom': box.height, 'front': box.depth,
                      'back': box.depth, 'left': box.width, 'right': box.width}[p.panel])-2*t
        if dims['height_z'] > available:
            raise ValueError(f'{name}高度超出盒体内腔，请增大盒体或调整安装面。')
        angle = math.radians(p.rotation)
        ca, sa = round(math.cos(angle)), round(math.sin(angle))

        def transform(x, y):
            return p.x+ca*x-sa*y, p.y+sa*x+ca*y

        def bounds(cx, cy, sx, sy, clearance=0):
            corners = [transform(cx+dx*sx/2, cy+dy*sy/2) for dx in (-1, 1) for dy in (-1, 1)]
            return (min(x for x, _ in corners)-clearance, min(y for _, y in corners)-clearance,
                    max(x for x, _ in corners)+clearance, max(y for _, y in corners)+clearance)

        def fits(rect):
            x0, y0, x1, y1 = rect
            inset = t+margin
            if x0 < inset or y0 < inset or x1 > width-inset or y1 > height-inset:
                raise ValueError(f'{name}外形、避让或切口超出完整板面/距榫齿不足一倍板厚，请调整位置或盒体尺寸。')
            if rounded == 'seam' and x0-margin < width/2 < x1+margin:
                raise ValueError(f'{name}跨越前面围板中间胶合接缝，请移到接缝一侧或其他面。')
            if isinstance(rounded, (int, float)):
                radius = max(0, rounded-inset)
                for x in (x0, x1):
                    for y in (y0, y1):
                        dx = max(rounded-x, x-(width-rounded), 0)
                        dy = max(rounded-y, y-(height-rounded), 0)
                        if dx*dx+dy*dy > radius*radius+1e-6:
                            raise ValueError(f'{name}进入圆角边缘，请移动到盖板完整区域。')

        body = bounds(0, 0, dims['length_x'], dims['width_y'], mount['clearance'])
        fits(body)
        footprint = body
        for keepout in profile['keepouts']:
            c, s = keepout['center'], keepout['size']
            zone = bounds(c['x'], c['y'], s['length_x'], s['width_y'])
            fits(zone)
            if abs(c['z'])+s['height_z']/2+dims['height_z']/2 > available:
                raise ValueError(f'{name}的避让空间超出内腔深度。')
            footprint = (min(footprint[0], zone[0]), min(footprint[1], zone[1]),
                         max(footprint[2], zone[2]), max(footprint[3], zone[3]))
        features = []
        if p.method == 'screw':
            for hole in mount['holes']:
                c, diameter = hole['center'], hole['diameter']
                if abs(c['x'])+diameter/2 > dims['length_x']/2 or abs(c['y'])+diameter/2 > dims['width_y']/2:
                    raise ValueError(f'{name}孔位超出档案包络，请核对原点和尺寸。')
                features.append(('circle', bounds(c['x'], c['y'], diameter, diameter), *transform(c['x'], c['y']), diameter/2))
        for opening in openings:
            c, gap = opening['center'], opening['clearance']
            if opening['kind'] == 'circle':
                diameter = opening['diameter']+2*gap
                features.append(('circle', bounds(c['x'], c['y'], diameter, diameter), *transform(c['x'], c['y']), diameter/2))
            else:
                features.append(('rect', bounds(c['x'], c['y'], opening['size_u'], opening['size_v'], gap), 0, 0, 0))
        for _, rect, *_ in features:
            footprint = (min(footprint[0], rect[0]), min(footprint[1], rect[1]),
                         max(footprint[2], rect[2]), max(footprint[3], rect[3]))
        if any(panel == p.panel and not separated(footprint, other, margin) for panel, other in occupied):
            raise ValueError(f'{name}与同面器件、避让区域或文字重叠/间距不足，请调整位置。')
        occupied.append((p.panel, footprint))
        for kind, rect, cx, cy, radius in features:
            fits(rect)
            if any(panel == p.panel and not separated(rect, other, margin) for panel, other in cuts):
                raise ValueError(f'{name}切口相交或切口之间剩余材料不足一倍板厚，请核对孔位和开口。')
            cuts.append((p.panel, rect))
            if kind == 'circle':
                x, y = project(cx, cy)
                drawing['shapes'].append(dict(kind='circle', operation='cut', x=x, y=y, radius=radius))
            else:
                x0, y0 = project(rect[0], rect[1]); x1, y1 = project(rect[2], rect[3])
                drawing['shapes'].append(dict(kind='rect', operation='cut', x=min(x0,x1), y=min(y0,y1), width=abs(x1-x0), height=abs(y1-y0)))
        # Envelope is an engraving guide, not a fabricated fine component model.
        outline = bounds(0, 0, dims['length_x'], dims['width_y'])
        x0, y0 = project(outline[0], outline[1]); x1, y1 = project(outline[2], outline[3])
        drawing['shapes'].append(dict(kind='rect', operation='engrave', x=min(x0,x1), y=min(y0,y1), width=abs(x1-x0), height=abs(y1-y0)))
        note = {'screw': '板件已生成名义通孔；螺钉长度、垫柱及螺母需另配，未生成螺柱。',
                'adhesive': '仅雕刻安装轮廓；胶垫/粘接固定由用户选择并实测，不生成卡扣。',
                'opening_only': '仅生成开口与器件轮廓；没有生成固定结构。'}[p.method]
        report.append({**item, 'cutCount': len(features), 'note': note})
    return Drawing.model_validate(drawing), report
