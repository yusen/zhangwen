"""Bounded edits of packaged templates; model replies are data, never Python."""
import ast
import json
import math
import re
from typing import Annotated
from pydantic import Field, model_validator
from .design_specs import Strict, SolidPart, propose
from .endpoints import configured
from .solid_text import TextOperation
from .laser_text import outlines


class PartOperations(Strict):
    partId: str = Field(min_length=1, max_length=80)
    operations: list[Annotated[SolidPart | TextOperation, Field(discriminator='kind')]] = Field(default_factory=list, max_length=16)


class TemplateEditSpec(Strict):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(default='', max_length=1200)
    questions: list[str] = Field(default_factory=list, max_length=3)
    parameterOverrides: dict[str, float] = Field(default_factory=dict, max_length=150)
    partOperations: list[PartOperations] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def bounded(self):
        if any(not math.isfinite(n) or abs(n) > 1000 for n in self.parameterOverrides.values()):
            raise ValueError('模板参数必须是-1000到1000内的有限数值。')
        if len({p.partId for p in self.partOperations}) != len(self.partOperations):
            raise ValueError('一个部件只能提供一组完整操作。')
        return self


def numeric_parameters(source):
    """Only existing top-level numeric literals can be replaced; no new names."""
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            break
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if type(value) in (int, float) and not name.startswith('_') and not any(k in name for k in ('epsilon', 'overlap')):
            values[name] = (value, node.value)
    return values


def checked_spec(value, item, source):
    spec = TemplateEditSpec.model_validate(value)
    allowed = numeric_parameters(source)
    if set(spec.parameterOverrides) - set(allowed):
        raise ValueError('修改包含不存在或不开放的模板参数。')
    parts = {part['id'] for part in item['parts'] if part['printable']}
    if any(part.partId not in parts for part in spec.partOperations):
        raise ValueError('只能修改当前模板的打印部件，不能修改硬件参考件。')
    return spec


def render_source(source, spec, item):
    # Replace only numeric literal byte spans in server-owned source. Preserve comments.
    lines = source.encode('utf-8').splitlines(keepends=True)
    for name, (default, node) in numeric_parameters(source).items():
        if name not in spec.parameterOverrides:
            continue
        if node.lineno != node.end_lineno:
            raise ValueError('模板参数必须为单行数值。')
        value = spec.parameterOverrides[name]
        value = int(value) if type(default) is int and value.is_integer() else value
        line = lines[node.lineno - 1]
        lines[node.lineno - 1] = line[:node.col_offset] + repr(value).encode('ascii') + line[node.end_col_offset:]
    text = b''.join(lines).decode('utf-8')
    objects = {part['id']: part['object'] for part in item['parts'] if part['printable']}
    out = ['\n# 掌问：基于原模板的已校验部件改造，单位毫米。']
    for part in spec.partOperations:
        target = objects[part.partId]
        # All packaged printable objects are simple names, validated here defensively.
        if not target.isidentifier():
            raise ValueError('模板部件不是可编辑对象。')
        out.append(f'_zw_target = {target} if isinstance({target}, cq.Workplane) else cq.Workplane("XY").newObject([{target}])')
        for operation in part.operations:
            if isinstance(operation, TextOperation):
                out.append('from zhangwen.web.solid_text import piece as _zw_text_piece')
                out.append(f'_zw_piece = _zw_text_piece({operation.model_dump()!r})')
                out.append('_zw_before = _zw_target.val().Volume()')
                out.append(f'_zw_target = _zw_target.{"union" if operation.operation == "add" else "cut"}(_zw_piece).clean()')
                out.append('if abs(_zw_target.val().Volume() - _zw_before) < 0.000001: raise ValueError("文字没有改变实体，请核对表面位置和深度")')
                continue
            x, y, z = operation.size
            primitive = f'box({x!r}, {y!r}, {z!r})' if operation.kind == 'box' else f'cylinder({z!r}, {x / 2!r})' if operation.kind == 'cylinder' else f'sphere({x / 2!r})'
            out.append('_zw_piece = cq.Workplane("XY").' + primitive)
            for axis, angle in zip([(1, 0, 0), (0, 1, 0), (0, 0, 1)], operation.rotation):
                if angle:
                    out.append(f'_zw_piece = _zw_piece.rotate((0, 0, 0), {axis!r}, {angle!r})')
            out.append(f'_zw_piece = _zw_piece.translate({tuple(operation.center)!r})')
            out.append('_zw_before = _zw_target.val().Volume()')
            out.append(f'_zw_target = _zw_target.{"union" if operation.operation == "add" else "cut"}(_zw_piece).clean()')
            out.append('if abs(_zw_target.val().Volume() - _zw_before) < 0.000001: raise ValueError("改造操作未改变部件，请核对位置和尺寸")')
        out.append(f'{target} = _zw_target')
    return text + '\n'.join(out) + '\n'


def effective_plan(spec, source):
    defaults = numeric_parameters(source)
    return {'parameters': {k: v for k, v in spec.parameterOverrides.items() if v != defaults[k][0]},
            'parts': {p.partId: [op.model_dump(mode='json') for op in p.operations] for p in spec.partOperations if p.operations}}


def local_text_edit(message, previous, item, source, conversation):
    """Recover the confirmed shell-back inscription without another paid call.

    Deliberately limited to the packaged shell's documented flat bottom face,
    centred text and explicit dimensions or a matching previously confirmed request.
    Other locations, shapes and layouts go through the normal bounded proposal.
    """
    if item['id'] != 'mpython-shell':
        return None
    confirming = message.strip(' 。！!') in {'是', '确认', '可以', '好的'} and previous.get('questions')
    intent = (previous.get('requestText', '') + ' ' + previous.get('message', '') + ' '.join(previous.get('questions', []))) if confirming else message
    quoted = re.findall(r'[“"「『]([^”"」』\n]{1,20})[”"」』]', intent)
    if len(set(quoted)) != 1 or not re.search('背面|底面|背部', intent) or not re.search('凹|雕刻|刻字', intent):
        return None
    if re.search('左|右|偏|竖|浮雕|凸|旋转|移|取消|删除|不要|不刻|不做|不能|如果|是否|能否', intent):
        return None
    text = quoted[0]
    confirmed = [h.get('summary', '') for h in (conversation or {}).get('history', [])
                 if text in h.get('summary', '') and '已确认' in h.get('summary', '')]
    records = [intent, *reversed(confirmed)]
    def number(label):
        pattern = label + r'\s*(?:约|为|是)?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)'
        # An explicit but unsupported dimension must not silently reuse an old one.
        values = [intent] if re.search(label, intent) else records
        return next((float(m[1]) for value in values if (m := re.search(pattern, value))), None)
    height = number(r'字高')
    depth = number(r'(?:凹深|深度)')
    if height is None or depth is None:
        return None
    spec = checked_spec(previous.get('templateEdit') or {'title': item['title']}, item, source).model_copy(deep=True)
    defaults = {k: v[0] for k, v in numeric_parameters(source).items()}
    dims = {**defaults, **spec.parameterOverrides}
    operation = TextOperation(text=text, fontSize=height, depth=depth, center=[0, -dims['wall_thickness']/2, -dims['bottom_thickness']], face='bottom')
    if depth >= dims['bottom_thickness']:
        return TemplateEditSpec(title=item['title'], questions=['凹字深度必须小于底板厚度，请确认深度。'], summary='该深度会刻穿底板，尚未实施。')
    width, _ = outlines(text, height)
    if width >= dims['inner_size_x'] or height >= dims['inner_size_y']:
        return TemplateEditSpec(title=item['title'], questions=['文字超出底壳背面，请减小字高或缩短文字。'], summary='文字超出可用区域，尚未实施。')
    target = next((p for p in spec.partOperations if p.partId == 'bottom'), None)
    if target and any(isinstance(op, TextOperation) and op.face == 'bottom' and op.text != text for op in target.operations):
        # Another inscription may need replacement or separate placement; let
        # the normal proposal resolve that instead of overlapping both strings.
        return None
    if target is None:
        target = PartOperations(partId='bottom'); spec.partOperations.append(target)
    target.operations = [op for op in target.operations if not (isinstance(op, TextOperation) and op.text == text and op.face == 'bottom')]
    target.operations.append(operation)
    spec.questions = []; spec.title = item['title'] + ' · 背面凹字'
    spec.summary = f'底壳外侧背面居中凹刻“{text}”，实际字高{height:g}毫米、深度{depth:g}毫米；保留其余模板结构。'
    return spec


async def propose_edit(message, previous, item, source, settings, conversation):
    if not settings or not configured(settings):
        return TemplateEditSpec(title=item['title'], summary='原模板模型已保留。配置结构设计师 API 后，可以对话修改此模板。',
            questions=['请先配置结构设计师 API，再描述要修改的部件、尺寸或孔位。'])
    def parse(choice):
        message = choice.get('message')
        content = message.get('content') if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ValueError('缺少模板改造JSON正文。')
        content = content.strip()
        if content.startswith('```') and content.endswith('```'):
            content = content.partition('\n')[2][:-3].strip()
        return checked_spec(json.loads(content), item, source)
    instructions = ('你是掌问模板改造助手。只能基于给定的原始CAD模板返回一个完整JSON改造方案，不能返回Python、文件、命令或重建为普通方盒。'
        'parameterOverrides仅能使用allowedParameters中的现有参数名，数值单位毫米，角度参数为度；保留未请求修改的配合和硬件尺寸。'
        'partOperations仅能作用于printable=true部件。每个操作为box/cylinder/sphere的add或cut；尺寸为XYZ全长，圆柱XY是直径、Z是高度，圆柱初始沿Z轴，'
        '先绕全局X/Y/Z旋转，再平移到center。坐标是原模板装配坐标，并非归零后的打印坐标。加料必须连接原实体，切孔必须与原实体相交。'
        '还支持kind=text的真实中文字形雕刻或浮雕：text文字（最多20字）、fontSize实际字高、depth深度、center三维表面中心、face外法线方向（top=+Z,bottom=-Z,front=-Y,back=+Y,left=-X,right=+X）、angle面内角度，operation=cut或add。'
        '文字使用随包中文字体真实闭合轮廓，保留字腔，不要用方块或假图案代替文字；center是字形包围框中心，cut朝实体内部，add朝外部。'
        '例如掌控板外壳背面（底壳外底面）居中凹刻掌问：partId=bottom，operations:[{kind:text,operation:cut,text:掌问,fontSize:8,depth:0.5,center:[0,-0.75,-1.5],face:bottom}]；深度必须小于底厚。'
        '完整方案每次从原始模板重新应用，必须保留currentEdit中此前要求的参数和操作，除非本轮明确撤销或重置。不要重复累计已有操作。'
        '不得假称已生成、已装配或实物兼容。无法明确表达的改动用questions询问，不得用无关近似模型假装完成。'
        'conversation.projectHardware提供原模块机械档案与修订；安装和开孔必须参考实际尺寸、孔位和避让，缺失时questions追问，不猜测。'
        'JSON Schema: ' + json.dumps(TemplateEditSpec.model_json_schema(), ensure_ascii=False))
    context = {'template': {key: item[key] for key in ['id', 'title', 'description', 'notes', 'parts']},
        'allowedParameters': {name: value for name, (value, _) in numeric_parameters(source).items()},
        'originalSourceReference': source, 'currentEdit': previous.get('templateEdit'),
        'currentParts': previous.get('templateParts'), 'conversation': conversation}
    return await propose(message, 'model', settings, context, instructions=instructions, parser=parse)
