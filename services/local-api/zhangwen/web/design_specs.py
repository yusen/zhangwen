"""Bounded design data, deterministic geometry and vector export; no model code."""
from __future__ import annotations

import asyncio
import json
import math
import re
from html import escape
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .endpoints import configured, is_deepseek
from .diagnostics import status_detail
from . import laser_joinery, laser_text, laser_rounded_box


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
    kind: Literal['rect', 'circle', 'polyline', 'line', 'text']
    operation: Literal['cut', 'engrave'] = 'cut'
    x: float = 0
    y: float = 0
    width: float = Field(default=1, gt=0, le=1000)
    height: float = Field(default=1, gt=0, le=1000)
    radius: float = Field(default=1, gt=0, le=500)
    points: list[list[float]] = Field(default_factory=list, max_length=256)
    closed: bool = True
    text: str = Field(default='', max_length=40)
    fontSize: float = Field(default=10, ge=1, le=150, description='文字实际轮廓高度，毫米')

    def bounds(self):
        if self.kind == 'text':
            if self.operation != 'engrave':
                raise ValueError('文字当前仅支持雕刻，不支持文字切穿。')
            width, _ = laser_text.outlines(self.text, self.fontSize)
            return self.x, self.y, self.x + width, self.y + self.fontSize
        if self.kind == 'rect':
            return self.x, self.y, self.x + self.width, self.y + self.height
        if self.kind == 'circle':
            return self.x - self.radius, self.y - self.radius, self.x + self.radius, self.y + self.radius
        if self.kind == 'line' and (self.closed or len(self.points) != 2 or self.points[0] == self.points[1]):
            raise ValueError('切缝线段需要两个不同端点，并明确closed=false。')
        if len(self.points) < (3 if self.closed else 2) or any(len(point) != 2 or not all(math.isfinite(x) for x in point) for point in self.points):
            raise ValueError('折线至少需要两个点，闭合轮廓至少三个点。')
        return min(p[0] for p in self.points), min(p[1] for p in self.points), max(p[0] for p in self.points), max(p[1] for p in self.points)


class Drawing(Strict):
    width: float = Field(gt=0, le=1000)
    height: float = Field(gt=0, le=1000)
    thickness: float = Field(default=3, gt=0, le=30)
    material: str = Field(default='待确认材料', min_length=1, max_length=80)
    kerf: float = Field(default=0, ge=0, le=1)
    shapes: list[LaserShape] = Field(min_length=1, max_length=512)

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


class FingerBox(Strict):
    width: float = Field(gt=0, le=500, description='盒子外宽，毫米')
    depth: float = Field(gt=0, le=500, description='盒子外深，毫米')
    height: float = Field(gt=0, le=500, description='盒子外高，毫米')
    thickness: float = Field(ge=.8, le=30, description='实际板厚，毫米；外尺寸至少为板厚6倍')
    material: str = Field(default='待确认材料', min_length=1, max_length=80)


class RoundedBox(FingerBox):
    # Missing in old checkpoints: retain their original canonical paths.
    pattern_version: Literal[1, 2] = 1
    corner_radius: float = Field(default=12, gt=0, le=200, description='外圆角半径，毫米')
    tab_width: float = Field(default=5, gt=0, le=100, description='目标榫宽，平台对称分段后实际宽度可能略有调整')
    slot_spacing: float = Field(default=1.2, ge=.6, le=8)
    slot_bridge: float = Field(default=2, ge=.8, le=8)
    slot_rows: int = Field(default=2, ge=1, le=6)
    top_lid: bool = True
    bottom_lid: bool = True


class PanelText(Strict):
    panel: Literal['left', 'right', 'front', 'back', 'bottom', 'top']
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=1000)
    text: str = Field(min_length=1, max_length=40)
    fontSize: float = Field(default=10, ge=1, le=150)


class DesignSpec(Strict):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(default='', max_length=1200)
    questions: list[str] = Field(default_factory=list, max_length=3)
    solid: list[SolidPart] = Field(default_factory=list, max_length=32)
    drawing: Drawing | None = None
    fingerBox: FingerBox | None = None
    roundedBox: RoundedBox | None = None
    panelTexts: list[PanelText] = Field(default_factory=list, max_length=16)

    @model_validator(mode='after')
    def joinery(self):
        if self.roundedBox:
            if self.fingerBox or self.panelTexts:
                raise ValueError('圆角盒与六面榫齿盒不能混用；圆角盒文字雕刻另行设计。')
            canonical = Drawing.model_validate(laser_rounded_box.drawing(**self.roundedBox.model_dump()))
            if self.drawing and self.drawing != canonical:
                raise ValueError('roundedBox由平台生成盖板、围板与弯折切缝，drawing应省略，不能附加不同路径。')
            self.drawing = canonical
        if self.fingerBox:
            data = laser_joinery.drawing(**self.fingerBox.model_dump())
            faces = laser_joinery.panels(self.fingerBox.width, self.fingerBox.depth, self.fingerBox.height, self.fingerBox.thickness)
            for label in self.panelTexts:
                index = ['left', 'right', 'front', 'back', 'bottom', 'top'].index(label.panel)
                face = faces[index]
                width, _ = laser_text.outlines(label.text, label.fontSize)
                t = self.fingerBox.thickness
                if label.x < t or label.y < t or label.x + width > face['width']-t or label.y + label.fontSize > face['height']-t:
                    raise ValueError('面板文字须位于榫齿以内的完整板面，请缩小字高或调整文字位置。')
                ox = 5 + (face['width']+5)*(index % 2)
                oy = 5 + sum(faces[i*2]['height']+5 for i in range(index//2))
                data['shapes'].append(dict(kind='text', operation='engrave', text=label.text, fontSize=label.fontSize, x=ox+label.x, y=oy+label.y))
            canonical = Drawing.model_validate(data)
            if self.drawing and self.drawing != canonical:
                raise ValueError('fingerBox由平台生成六块互补榫齿轮廓，drawing应省略，不能附加不同的路径。')
            self.drawing = canonical
        elif self.panelTexts:
            raise ValueError('panelTexts仅用于fingerBox；平面图纸请在drawing.shapes中放文字。')
        return self

    def check_kind(self, design_type):
        if self.questions:
            if any(len(question) > 300 for question in self.questions):
                raise ValueError('问题过长。')
            return self
        if design_type == 'laser':
            if not self.drawing or self.solid:
                raise ValueError('激光图纸需要平面路径，不接受实体代码。')
        elif not self.solid or self.solid[0].operation != 'add' or self.drawing or self.fingerBox or self.roundedBox:
            raise ValueError('3D模型需要从一个实体开始，不接受图纸或可执行代码。')
        return self


def template_spec(template, params):
    if template == 'rounded-box':
        options = {key:params.get(key, default) for key,default in laser_rounded_box.DEFAULTS.items()}
        if any(options[key] not in (0,1) for key in ['top_lid','bottom_lid']):
            raise ValueError('顶盖、底盖选项须为0或1。')
        options['material'] = params.get('material', '待确认材料')
        options['pattern_version'] = 2
        return DesignSpec(title=f'{options["width"]:g}×{options["depth"]:g}×{options["height"]:g}mm 圆角盒',
            summary='圆角盖板与连续围板，四角切缝交错接到上下边缘，中间保留连接桥，盖板榫与围板凹槽配对；尺寸为外尺寸，围板按中性层展开。接缝需胶合，材料弯折与榫接须先试切；未补偿刀缝。',
            roundedBox=RoundedBox.model_validate(options))
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
    if template == 'finger-box':
        return DesignSpec(title=f'{width:g}×{depth:g}×{height:g}mm 榫齿盒',
            summary='六块互补榫齿板，外尺寸与实际板厚联动；按名义尺寸生成，未补偿刀缝，需先试切核对配合。',
            fingerBox=dict(width=width, depth=depth, height=height, thickness=thickness, material=params.get('material', '待确认材料')),
            panelTexts=params.get('panelTexts', []))
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


def design_instructions(design_type):
    laser = design_type == 'laser'
    example = template_spec('plate' if laser else 'box', {}).model_dump(mode='json', exclude_defaults=True)
    return ('你是掌问结构设计师，只返回一个完整JSON对象，不要代码块、说明文字、Python、HTML、SVG源码或系统命令。'
        '下面提供真实JSON Schema和有效示例，必须遵守字段名、类型、数量和范围，不得添加schema以外的字段。'
        '单位毫米。缺少关键尺寸时questions只问一个问题，solid=[]、drawing=null，不要猜测答案。'
        'previousDesign.spec是所选版本的有效设计，history是截至该版本的同类需求记录；优先本次request，'
        '保留未要求修改的内容，不要重新引入历史中已替换的方案。pendingQuestions可用于理解本次回答。'
        'previousDesign.projectHardware是当前项目原模块的机械资料、来源及修订，selectedStructureProfiles是选定结构硬件。'
        '按本次请求决定哪些硬件参与结构；参考其中尺寸、坐标原点、孔位、开口和避让，不能猜缺失的数据或把外包络冒充精细模型。'
        '需要安装或开孔而相应资料缺失时必须用questions追问；未要求安装硬件的独立作品不受缺项阻止。'
        + ('本次只做激光平面图纸：solid=[]，drawing包含完整图纸。rect的x/y为左上角，circle为圆心，'
           'polyline用points二维坐标，不要给不适用字段填null；不需要的字段可省略。'
           '全部路径必须在画布0..width/height内，最多512项，每条折线最多256点，画布最大1000mm。'
           '切割折线必须闭合，不得重复；有意的单段弯折切缝可用kind=line、points两个不同端点、closed=false、operation=cut。'
           'kerf只能为0，不自动补偿刀缝或设置加工功率。'
           '文字雕刻支持常用中英文：shapes中kind=text、operation=engrave、text文字、fontSize实际字高mm、x/y为文字轮廓左上角。'
           '平台用随包字体转真实矢量轮廓，最多40字/项，不支持换行或切穿文字；不要用矩形代替文字。'
           '按名义尺寸输出；若请求含目前不支持的曲线等，先用questions确认可接受的替代方案。'
           '矩形六面榫卯盒/榫齿盒必须使用fingerBox，只返回width/depth/height外尺寸、thickness实际板厚和material，'
           'drawing省略或null，平台生成六块互补的闭合榫齿轮廓。每个外尺寸至少为板厚6倍。'
           '例如50毫米立方盒用fingerBox:{"width":50,"depth":50,"height":50,"thickness":3}。'
           '圆角弯折盒改用roundedBox:{width:50,depth:50,height:50,thickness:3,corner_radius:12,tab_width:5,slot_spacing:1.2,slot_bridge:2,slot_rows:2,top_lid:true,bottom_lid:true}；'
           'drawing省略，由平台确定性生成两圆角盖板与四个弯折区的连续围板，不用普通六面盒代替。宽深是外尺寸，板厚0.8至12、圆角至少2倍板厚，直边至少5倍板厚。'
           '榫齿盒文字用顶层panelTexts:[{panel:front,x:6,y:10,text:掌问,fontSize:10}]；panel选left/right/front/back/bottom/top。'
           '坐标相对该面板左上角，文字须完全处于四边各扣除一倍板厚后的矩形内，drawing仍省略。'
           '不得用六个矩形或圆孔假称榫卯；不支持的开盖方式、额外孔、非矩形榫卯先用questions确认。'
           if laser else
           '本次只做3D：drawing=null，solid从add开始，最多32项，只允许box/cylinder/sphere及add/cut。'
           'size是完整三轴尺寸，圆柱X=Y，球三轴相同；center是中心，圆柱轴沿Z，rotation依次绕世界XYZ旋转后平移。'
           '尺寸0.1至1000，坐标±1000。复杂自由曲面等不支持内容请用questions询问如何简化。')
        + '没有硬件也能设计，不猜硬件孔位。直接返回紧凑JSON，避免重复填写默认字段，确保回答完整结束。'
        + '\nJSON Schema:\n' + json.dumps(DesignSpec.model_json_schema(), ensure_ascii=False, separators=(',', ':'))
        + '\n有效示例:\n' + json.dumps(example, ensure_ascii=False, separators=(',', ':')))


def design_validation_detail(exc):
    if isinstance(exc, ValidationError):
        fields = set(DesignSpec.model_fields) | set(SolidPart.model_fields) | set(Drawing.model_fields) | set(LaserShape.model_fields) | set(FingerBox.model_fields) | set(RoundedBox.model_fields) | set(PanelText.model_fields)
        errors = []
        for item in exc.errors(include_url=False, include_input=False)[:3]:
            path = '.'.join(str(n) if isinstance(n, int) else n if n in fields else '未知字段' for n in item['loc'])
            errors.append((path or '设计数据') + '：' + item['msg'][:160])
        return '；'.join(errors)
    return str(exc)


def parse_design_reply(choice, design_type):
    if not isinstance(choice, dict) or not isinstance(choice.get('message'), dict):
        raise ValueError('缺少完整的设计回复对象。')
    content = choice['message'].get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('模型没有返回JSON正文。')
    content = content.strip()
    if content.startswith('```') and content.endswith('```'):
        header, separator, body = content.partition('\n')
        if separator and header.strip().lower() in {'```', '```json'}:
            content = body[:-3].strip()
    data = json.loads(content)
    if isinstance(data, dict) and isinstance(data.get('roundedBox'), dict):
        # Only new model replies are upgraded; saved checkpoints validate as-is.
        data['roundedBox']['pattern_version'] = 2
    spec = DesignSpec.model_validate(data).check_kind(design_type)
    # New responses must not repeat the old false label. Historical specs remain
    # readable: this semantic guard applies only at the model reply boundary.
    if (design_type == 'laser' and not spec.questions and not spec.fingerBox and not spec.roundedBox
        and re.search(r'榫|指接|finger|tenon', spec.title, re.I) and re.search(r'盒|箱|box', spec.title, re.I)):
        raise ValueError('榫卯盒请返回fingerBox尺寸与板厚，由平台生成互补榫齿，不能只把普通板件命名为榫卯。')
    return spec


async def propose(message, design_type, settings, previous=None, *, instructions=None, parser=None):
    if not settings or not configured(settings):
        return DesignSpec(title='需要配置模型', summary='可配置结构设计师 API 后描述任意需求，或使用左侧模板直接生成。', questions=['选择左侧模板，或先配置结构设计师模型 API。'])
    user = json.dumps({'designType': design_type, 'request': message, 'previousDesign': previous}, ensure_ascii=False)
    messages = [{'role': 'system', 'content': instructions or design_instructions(design_type)}, {'role': 'user', 'content': user}]
    try:
        # Both attempts share the original total deadline. Never retry network,
        # authentication or truncated replies, and never accept partial geometry.
        async with asyncio.timeout(150), httpx.AsyncClient(timeout=httpx.Timeout(150, connect=15), trust_env=False, follow_redirects=False) as client:
            for attempt in range(2):
                response = await client.post(settings['baseUrl'] + '/chat/completions',
                    headers={'Authorization': 'Bearer ' + settings['apiKey']} if settings.get('apiKey') else {},
                    json={'model': settings['model'], 'messages': messages, 'max_tokens': 12000 if design_type == 'laser' and is_deepseek(settings['baseUrl']) else 6000,
                          **({'thinking': {'type': 'disabled'}, 'response_format': {'type': 'json_object'}} if is_deepseek(settings['baseUrl']) else {})})
                response.raise_for_status()
                if len(response.content) > 300000:
                    raise HTTPException(502, '模型返回的设计数据过大，请把图纸拆分成较小的设计；输入和原版本保留。')
                try:
                    envelope = response.json()
                    choices = envelope.get('choices') if isinstance(envelope, dict) else None
                    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                        raise ValueError('接口未返回choices设计回复，请检查所选API是否兼容。')
                    choice = choices[0]
                except (ValueError, TypeError) as exc:
                    raise HTTPException(502, '结构设计API未返回有效的回复对象，请检查API地址与模型；输入和原版本保留。') from exc
                reason = choice.get('finish_reason')
                if reason == 'length':
                    raise HTTPException(502, '图纸回答达到长度上限，未接收不完整的路径。请减少本次图形数量或分步修改；输入和原版本保留。')
                if reason not in ('stop', None):
                    raise HTTPException(502, '模型没有完整完成本次设计，请调整需求后重试；输入和原版本保留。')
                try:
                    return parser(choice) if parser else parse_design_reply(choice, design_type)
                except ValueError as exc:
                    detail = design_validation_detail(exc)
                    if attempt or len(json.dumps(choice, ensure_ascii=False)) > 40000:
                        raise HTTPException(502, '模型返回的设计格式未通过校验：' + detail + '。请调整本次需求后重试；输入和原版本保留。') from exc
                    content = choice.get('message', {}).get('content') if isinstance(choice.get('message'), dict) else None
                    if isinstance(content, str) and content.strip():
                        messages.append({'role': 'assistant', 'content': content})
                    messages.append({'role': 'user', 'content': '刚才的数据没有通过平台校验：' + detail +
                        '。仅修正格式或违规参数，保留原需求，重新返回一个完整JSON对象。不能满足时用questions询问，不返回代码或不完整图形。'})
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise HTTPException(504, '结构模型响应超时，输入与原版本保留，可稍后重试。') from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, '结构设计API请求失败：' + status_detail(exc.response.status_code) + ' 输入和原版本保留。') from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, '无法连接结构设计模型，请检查API地址或网络后重试；输入和原版本保留。') from exc


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
        elif shape.kind == 'text':
            elements.append(f'<path d="{laser_text.svg_path(shape)}" fill="{color}" fill-rule="evenodd" stroke="none" data-operation="engrave"/>')
        elif shape.kind == 'circle':
            elements.append(f'<circle cx="{shape.x}" cy="{shape.y}" r="{shape.radius}" {attrs}/>')
        elif shape.kind == 'line':
            (x1,y1),(x2,y2) = shape.points
            elements.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {attrs}/>')
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
        if shape.kind == 'text':
            for contour in laser_text.placed(shape):
                out += ['0', 'LWPOLYLINE', '100', 'AcDbEntity', '8', 'ENGRAVE', '100', 'AcDbPolyline', '90', str(len(contour)), '70', '1']
                for x,y in contour:
                    out += ['10', str(x), '20', str(round(drawing.height-y,6))]
            continue
        if shape.kind == 'line':
            (x1,y1),(x2,y2) = shape.points
            out += ['0','LINE','100','AcDbEntity','8',layer,'100','AcDbLine','10',str(x1),'20',str(drawing.height-y1),'30','0','11',str(x2),'21',str(drawing.height-y2),'31','0']
        elif shape.kind == 'circle':
            out += ['0', 'CIRCLE', '100', 'AcDbEntity', '8', layer, '100', 'AcDbCircle', '10', str(shape.x), '20', str(drawing.height - shape.y), '30', '0', '40', str(shape.radius)]
        else:
            points = shape.points if shape.kind == 'polyline' else [[shape.x, shape.y], [shape.x + shape.width, shape.y], [shape.x + shape.width, shape.y + shape.height], [shape.x, shape.y + shape.height]]
            out += ['0', 'LWPOLYLINE', '100', 'AcDbEntity', '8', layer, '100', 'AcDbPolyline', '90', str(len(points)), '70', '1' if shape.closed else '0']
            for x, y in points:
                out += ['10', str(x), '20', str(drawing.height - y)]
    return '\n'.join(out + ['0', 'ENDSEC', '0', 'EOF']) + '\n'
