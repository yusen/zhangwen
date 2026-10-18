"""Bounded design data, deterministic geometry and vector export; no model code."""
from __future__ import annotations

import json
import math
from html import escape
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .endpoints import configured, is_deepseek


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SolidPart(Strict):
    kind: Literal['box', 'cylinder', 'sphere']
    operation: Literal['add', 'cut'] = 'add'
    label: str = Field(default='', max_length=80)
    size: list[float] = Field(min_length=3, max_length=3)
    center: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    rotation: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)

    @model_validator(mode='after')
    def bounds(self):
        if not all(.1 <= n <= 1000 for n in self.size) or not all(abs(n) <= 1000 for n in self.center) or not all(abs(n) <= 360 for n in self.rotation):
            raise ValueError('实体尺寸、位置或角度超出范围。')
        if self.kind in {'sphere', 'cylinder'} and self.size[0] != self.size[1]:
            raise ValueError('圆柱/球的X与Y直径必须一致。')
        if self.kind == 'sphere' and len(set(self.size)) != 1:
            raise ValueError('球体三轴直径必须一致。')
        return self


class LaserShape(Strict):
    kind: Literal['rect', 'circle', 'polyline']
    operation: Literal['cut', 'engrave'] = 'cut'
    x: float = 0
    y: float = 0
    width: float = Field(default=1, gt=0, le=1000)
    height: float = Field(default=1, gt=0, le=1000)
    radius: float = Field(default=1, gt=0, le=500)
    points: list[list[float]] = Field(default_factory=list, max_length=120)
    closed: bool = True

    def bounds(self):
        if self.kind == 'rect':
            return self.x, self.y, self.x + self.width, self.y + self.height
        if self.kind == 'circle':
            return self.x - self.radius, self.y - self.radius, self.x + self.radius, self.y + self.radius
        if len(self.points) < (3 if self.closed else 2) or any(len(point) != 2 or not all(math.isfinite(x) for x in point) for point in self.points):
            raise ValueError('折线至少需要两个点，闭合轮廓至少三个点。')
        return min(p[0] for p in self.points), min(p[1] for p in self.points), max(p[0] for p in self.points), max(p[1] for p in self.points)


class Drawing(Strict):
    width: float = Field(gt=0, le=1000)
    height: float = Field(gt=0, le=1000)
    thickness: float = Field(default=3, gt=0, le=30)
    material: str = Field(default='待确认材料', min_length=1, max_length=80)
    kerf: float = Field(default=0, ge=0, le=1)
    shapes: list[LaserShape] = Field(min_length=1, max_length=160)

    @model_validator(mode='after')
    def bounds(self):
        seen = set()
        for shape in self.shapes:
            x1, y1, x2, y2 = shape.bounds()
            if x1 < 0 or y1 < 0 or x2 > self.width + .001 or y2 > self.height + .001:
                raise ValueError('图形超出材料画布，请调整尺寸或排版。')
            if shape.operation == 'cut' and shape.kind == 'polyline' and not shape.closed:
                raise ValueError('切割折线必须闭合，开放线请标注雕刻。')
            key = json.dumps(shape.model_dump(), sort_keys=True)
            if key in seen:
                raise ValueError('存在完全重复的路径，可能导致重复切割。')
            seen.add(key)
        if self.kerf != 0:
            raise ValueError('当前导出为名义尺寸，刀缝请在加工软件中补偿；平台暂不自动偏移轮廓。')
        return self


class DesignSpec(Strict):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(default='', max_length=1200)
    questions: list[str] = Field(default_factory=list, max_length=3)
    solid: list[SolidPart] = Field(default_factory=list, max_length=32)
    drawing: Drawing | None = None

    def check_kind(self, design_type):
        if self.questions:
            if any(len(question) > 300 for question in self.questions):
                raise ValueError('问题过长。')
            return self
        if design_type == 'laser':
            if not self.drawing or self.solid:
                raise ValueError('激光图纸需要平面路径，不接受实体代码。')
        elif not self.solid or self.solid[0].operation != 'add' or self.drawing:
            raise ValueError('3D模型需要从一个实体开始，不接受图纸或可执行代码。')
        return self


def template_spec(template, params):
    width, depth, height = (params.get(k, default) for k, default in [('width', 80), ('depth', 60), ('height', 40)])
    thickness = params.get('thickness', 3)
    if min(width, depth, height) <= thickness * 2 or not .8 <= thickness <= 30:
        raise HTTPException(422, '尺寸应大于两倍厚度，厚度为0.8至30毫米。')
    def part(kind, size, center, operation='add', label=''):
        return dict(kind=kind, size=size, center=center, operation=operation, label=label)
    if template == 'box':
        solid = [part('box', [width, depth, height], [0, 0, height / 2], label='盒体'),
                 part('box', [width - 2 * thickness, depth - 2 * thickness, height], [0, 0, height / 2 + thickness], 'cut', '内腔')]
        return DesignSpec(title='开口收纳盒', summary='无硬件收纳盒，内腔与底板保留指定厚度。', solid=solid)
    if template == 'cup':
        return DesignSpec(title='圆柱笔筒', summary='圆柱形开口容器，直径由宽度决定。', solid=[
            part('cylinder', [width, width, height], [0, 0, height / 2], label='外筒'),
            part('cylinder', [width - thickness * 2, width - thickness * 2, height], [0, 0, height / 2 + thickness], 'cut', '内腔')])
    if template == 'bracket':
        return DesignSpec(title='L形支架', summary='底板与立板一体，具体承载能力需另行测试。', solid=[
            part('box', [width, depth, thickness], [0, 0, thickness / 2], label='底板'),
            part('box', [width, thickness, height], [0, depth / 2 - thickness / 2, height / 2], label='立板')])
    margin = 5
    if template in {'plate', 'round-tag'} and min(width, depth) < 16:
        raise HTTPException(422, '挂牌至少16毫米，确保4毫米挂孔与外轮廓之间留有材料。')
    if template == 'plate':
        drawing = dict(width=width + 10, height=depth + 10, thickness=thickness, shapes=[
            dict(kind='rect', x=margin, y=margin, width=width, height=depth),
            dict(kind='circle', x=margin + 6, y=margin + 6, radius=2)])
        return DesignSpec(title='矩形挂牌', summary='矩形外轮廓与直径4毫米的挂孔；按名义尺寸导出。', drawing=drawing)
    if template == 'round-tag':
        return DesignSpec(title='圆形挂牌', summary='圆形外轮廓与直径4毫米挂孔。', drawing=dict(
            width=width + 10, height=width + 10, thickness=thickness, shapes=[
                dict(kind='circle', x=width / 2 + 5, y=width / 2 + 5, radius=width / 2),
                dict(kind='circle', x=width / 2 + 5, y=11, radius=2)]))
    if template == 'panel-box':
        # Butt joints: outer W/D, side panels sit on the floor, end panels
        # between long sides. Glue required; never claim finger joints.
        shapes = [dict(kind='rect', x=5, y=5, width=width, height=depth),
                  dict(kind='rect', x=width + 10, y=5, width=width, height=height - thickness),
                  dict(kind='rect', x=width + 10, y=height + 10, width=width, height=height - thickness),
                  dict(kind='rect', x=5, y=depth + 10, width=depth - 2 * thickness, height=height - thickness),
                  dict(kind='rect', x=5, y=depth + height + 15, width=depth - 2 * thickness, height=height - thickness)]
        return DesignSpec(title='胶合收纳盒板件', summary='五块板平铺：底板、两长边、两短边，按厚度扣除搭接；需胶合，不含榫齿。', drawing=dict(
            width=max(s['x'] + s['width'] for s in shapes) + 5, height=max(s['y'] + s['height'] for s in shapes) + 5,
            thickness=thickness, shapes=shapes))
    raise HTTPException(422, '未知设计模板。')


async def propose(message, design_type, settings, previous=None):
    if not settings or not configured(settings):
        return DesignSpec(title='需要配置模型', summary='可配置结构设计师 API 后描述任意需求，或使用左侧模板直接生成。', questions=['选择左侧模板，或先配置结构设计师模型 API。'])
    instruction = ('你是掌问结构设计师，只返回JSON设计数据，不返回Python、脚本、HTML、SVG源码或系统命令。'
        '单位毫米。根据需求生成完整设计；缺少关键尺寸时只问一个问题，questions非空时不生成几何。'
        '允许schema：{title,summary,questions:[],solid:[],drawing:null}。'
        '3D实体solid每项为{kind:box|cylinder|sphere,operation:add|cut,label,size:[X,Y,Z],center:[X,Y,Z],rotation:[X,Y,Z]}。'
        'size为完整尺寸（圆柱/球为直径），box中心在center，圆柱中心在center且轴沿Z；rotation依次绕世界XYZ轴旋转角度，再平移。'
        '按序布尔加/减，第一项add，最多32项，尺寸0.1至1000，坐标±1000；圆柱X=Y、球三轴相同。'
        '激光drawing={width,height,thickness,material,kerf:0,shapes:[{kind:rect|circle|polyline,operation:cut|engrave,x,y,width,height,radius,points:[[x,y]],closed:true}]}。'
        'rect的x/y为左上角，circle的x/y为圆心，坐标从左上向右下；全部路径必须在画布0..width/height内，最多160项，画布最大1000mm。'
        '只返回本次设计类型的几何，另一类留空；不猜硬件孔位；没有硬件也可以设计。不能实现的曲面或艺术造型明确说明并问如何简化。'
        '激光切割路径须闭合、不能重复；不自动补偿刀缝（kerf必须0），不指定激光功率或执行加工。')
    user = json.dumps({'designType': design_type, 'request': message, 'previousDesign': previous}, ensure_ascii=False)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(150, connect=15), trust_env=False, follow_redirects=False) as client:
            response = await client.post(settings['baseUrl'] + '/chat/completions',
                headers={'Authorization': 'Bearer ' + settings['apiKey']} if settings.get('apiKey') else {},
                json={'model': settings['model'], 'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': user}],
                      'max_tokens': 6000, **({'thinking': {'type': 'disabled'}, 'response_format': {'type': 'json_object'}} if is_deepseek(settings['baseUrl']) else {})})
            response.raise_for_status()
            if len(response.content) > 300000:
                raise ValueError('oversized response')
            choice = response.json()['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('incomplete response')
            content = choice['message']['content'].strip()
            if content.startswith('```json') and content.endswith('```'):
                content = content[7:-3].strip()
            return DesignSpec.model_validate_json(content).check_kind(design_type)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, '结构模型响应超时，输入与原版本保留，可稍后重试。') from exc
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(502, '模型未返回可校验的设计数据，请核对 API 或简化需求；原版本保留。') from exc


def solid_code(spec: DesignSpec, scale=1):
    lines = ['# 掌问参数化3D模型 · 单位毫米', '# 由经过校验的尺寸生成；不执行模型返回的程序。', 'import cadquery as cq', 'result = None']
    for i, part in enumerate(spec.solid):
        size = [round(n * scale, 6) for n in part.size]
        center = [round(n * scale, 6) for n in part.center]
        lines.append(f'# 第{i + 1}步：{part.operation} {part.kind}；尺寸 {size}，中心 {center}')
        if part.kind == 'box':
            lines.append(f'piece = cq.Workplane("XY").box({size[0]}, {size[1]}, {size[2]})')
        elif part.kind == 'cylinder':
            lines.append(f'piece = cq.Workplane("XY").cylinder({size[2]}, {size[0] / 2})')
        else:
            lines.append(f'piece = cq.Workplane("XY").sphere({size[0] / 2})')
        for axis, angle in zip([(1, 0, 0), (0, 1, 0), (0, 0, 1)], part.rotation):
            if angle:
                lines.append(f'piece = piece.rotate((0, 0, 0), {axis}, {angle})')
        lines.append(f'piece = piece.translate({tuple(center)})')
        lines.append('result = piece' if i == 0 else f'result = result.{"union" if part.operation == "add" else "cut"}(piece)')
    lines.extend(['# 修复布尔运算后边线，并供STEP/STL导出。', 'result = result.clean()', 'base = result'])
    return '\n'.join(lines) + '\n'


def svg(drawing: Drawing, preview=False):
    elements = []
    if preview:
        elements.append(f'<rect width="{drawing.width}" height="{drawing.height}" fill="#f5ebd5"/>')
    for shape in drawing.shapes:
        color = '#1672c4' if shape.operation == 'engrave' else '#cc332d'
        attrs = f'fill="none" stroke="{color}" stroke-width="0.1" data-operation="{shape.operation}"'
        if shape.kind == 'rect':
            elements.append(f'<rect x="{shape.x}" y="{shape.y}" width="{shape.width}" height="{shape.height}" {attrs}/>')
        elif shape.kind == 'circle':
            elements.append(f'<circle cx="{shape.x}" cy="{shape.y}" r="{shape.radius}" {attrs}/>')
        else:
            points = ' '.join(f'{x},{y}' for x, y in shape.points)
            tag = 'polygon' if shape.closed else 'polyline'
            elements.append(f'<{tag} points="{points}" {attrs}/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{drawing.width}mm" height="{drawing.height}mm" viewBox="0 0 {drawing.width} {drawing.height}"><title>{escape(drawing.material)}</title>' + ''.join(elements) + '</svg>\n'


def dxf(drawing: Drawing):
    # AutoCAD 2000 ASCII DXF, explicit millimetres and separate named layers.
    out = ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1015', '9', '$INSUNITS', '70', '4', '0', 'ENDSEC',
           '0', 'SECTION', '2', 'TABLES', '0', 'TABLE', '2', 'LAYER', '5', '1', '330', '0', '100', 'AcDbSymbolTable', '70', '2']
    for name, color in [('CUT', 1), ('ENGRAVE', 5)]:
        out += ['0', 'LAYER', '2', name, '70', '0', '62', str(color), '6', 'CONTINUOUS']
    out += ['0', 'ENDTAB', '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES']
    for shape in drawing.shapes:
        layer = 'CUT' if shape.operation == 'cut' else 'ENGRAVE'
        if shape.kind == 'circle':
            out += ['0', 'CIRCLE', '100', 'AcDbEntity', '8', layer, '100', 'AcDbCircle', '10', str(shape.x), '20', str(drawing.height - shape.y), '30', '0', '40', str(shape.radius)]
        else:
            points = shape.points if shape.kind == 'polyline' else [[shape.x, shape.y], [shape.x + shape.width, shape.y], [shape.x + shape.width, shape.y + shape.height], [shape.x, shape.y + shape.height]]
            out += ['0', 'LWPOLYLINE', '100', 'AcDbEntity', '8', layer, '100', 'AcDbPolyline', '90', str(len(points)), '70', '1' if shape.closed else '0']
            for x, y in points:
                out += ['10', str(x), '20', str(drawing.height - y)]
    return '\n'.join(out + ['0', 'ENDSEC', '0', 'EOF']) + '\n'
