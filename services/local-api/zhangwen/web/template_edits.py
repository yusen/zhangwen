"""Bounded edits of packaged templates; model replies are data, never Python."""
import ast
import json
import math
import re
from typing import Annotated
from pydantic import Field, model_validator
from .design_specs import Strict, SolidPart, propose, assembly_instructions
from .endpoints import configured
from .solid_text import TextOperation
from .laser_text import outlines


class PartOperations(Strict):
    partId: str = Field(min_length=1, max_length=80)
    operations: list[Annotated[SolidPart | TextOperation, Field(discriminator='kind')]] = Field(default_factory=list, max_length=64)


class PartTransform(Strict):
    partId: str = Field(min_length=1, max_length=80)
    translation: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    rotation: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)

    @model_validator(mode='after')
    def bounded(self):
        if any(not math.isfinite(v) or abs(v) > 1000 for v in self.translation):
            raise ValueError('部件移动距离须为-1000到1000毫米内的有限数值。')
        if any(not math.isfinite(v) or abs(v) > 360 for v in self.rotation):
            raise ValueError('部件旋转角度须为-360到360度内的有限数值。')
        return self


class AddedPart(Strict):
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,39}$')
    label: str = Field(min_length=1, max_length=80)
    operations: list[SolidPart] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def printable(self):
        if not self.label.strip() or self.operations[0].operation != 'add':
            raise ValueError('独立零件需要名称，并从加料实体开始。')
        return self


def added_part_id(part):
    return 'added-' + part.id


def part_definitions(item, spec):
    return [*item['parts'], *[{'id': added_part_id(part), 'label': part.label, 'printable': True}
                             for part in spec.addedParts]]


class TemplateEditSpec(Strict):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(default='', max_length=1200)
    questions: list[str] = Field(default_factory=list, max_length=3)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    parameterOverrides: dict[str, float] = Field(default_factory=dict, max_length=150)
    partOperations: list[PartOperations] = Field(default_factory=list, max_length=6)
    partTransforms: list[PartTransform] = Field(default_factory=list, max_length=64)
    addedParts: list[AddedPart] = Field(default_factory=list, max_length=32)

    @model_validator(mode='after')
    def bounded(self):
        if any(not text.strip() or len(text) > 300 for text in self.assumptions):
            raise ValueError('预览假设须为不超过300字的非空说明。')
        if any(not math.isfinite(n) or abs(n) > 1000 for n in self.parameterOverrides.values()):
            raise ValueError('模板参数必须是-1000到1000内的有限数值。')
        if len({p.partId for p in self.partOperations}) != len(self.partOperations):
            raise ValueError('一个部件只能提供一组完整操作。')
        if len({p.partId for p in self.partTransforms}) != len(self.partTransforms):
            raise ValueError('一个部件只能提供一组完整位置。')
        if len({p.id for p in self.addedParts}) != len(self.addedParts):
            raise ValueError('独立零件ID不能重复。')
        if sum(len(p.operations) for p in [*self.partOperations, *self.addedParts]) > 512:
            raise ValueError('案例几何操作最多512项，请拆分复杂设计。')
        return self


def prepare_source(source, item):
    """Adapt the digest-checked legacy case without changing its archived source.

    These fixed substitutions link both probe openings, four mounting holes and
    the hardware reference to the same X/Z position. Zero X preserves old cases.
    """
    if item['id'] not in {'auto-open-lid-box', 'auto-open-lid-box-c3'} or source.startswith('# ZW linked ultrasonic placement\n'):
        return source
    replacements = {
        '(x, -box_width_y / 2.0, 20.0)': '(x + ultrasonic_offset_x, -box_width_y / 2.0, ultrasonic_shell_mount_center_z)',
        '(x, -box_width_y / 2.0, z)': '(x + ultrasonic_offset_x, -box_width_y / 2.0, z)',
        '.translate((0.0, ultrasonic_pcb_origin_y, 20.0))': '.translate((ultrasonic_offset_x, ultrasonic_pcb_origin_y, ultrasonic_shell_mount_center_z))',
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise ValueError('案例安装位置定义不一致，未改动模型。')
        source = source.replace(before, after, 1)
    source = source.replace('只用于盒子 -Y 侧壁的四个超声波固定孔，不改硬件参考模型本体。', '超声波整体安装位置：探头孔、四个固定孔和参考件同步移动；孔距仍独立调整。')
    return '# ZW linked ultrasonic placement\nultrasonic_offset_x = 0.0\n' + source


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
    source = prepare_source(source, item)
    allowed = numeric_parameters(source)
    if set(spec.parameterOverrides) - set(allowed):
        raise ValueError('修改包含不存在或不开放的模板参数。')
    parts = {part['id'] for part in item['parts'] if part['printable']}
    if any(part.partId not in parts for part in spec.partOperations):
        raise ValueError('加料、挖空只作用于打印件；移动参考件请使用部件位置。')
    original_ids = {p['id'] for p in item['parts']}
    if any(added_part_id(p) in original_ids for p in spec.addedParts):
        raise ValueError('独立零件ID与案例部件冲突。')
    if any(part.partId not in {p['id'] for p in part_definitions(item, spec)} for part in spec.partTransforms):
        raise ValueError('只能移动当前案例中已登记的部件。')
    if item['id'] in {'auto-open-lid-box', 'auto-open-lid-box-c3'}:
        dims = {**{k: v[0] for k, v in allowed.items()}, **spec.parameterOverrides}
        extent_x = max(10.75 + 17.4 / 2, dims['ultrasonic_shell_mount_pitch_x'] / 2 + dims['ultrasonic_shell_mount_hole_diameter'] / 2)
        extent_z = max(17.4 / 2, dims['ultrasonic_shell_mount_pitch_z'] / 2 + dims['ultrasonic_shell_mount_hole_diameter'] / 2)
        if abs(dims['ultrasonic_offset_x']) + extent_x >= dims['box_length_x'] / 2 - dims['wall_thickness']:
            raise ValueError('超声波安装孔移出了盒壁，请减小左右移动距离或增大盒体。')
        if not dims['floor_thickness'] < dims['ultrasonic_shell_mount_center_z'] - extent_z or dims['ultrasonic_shell_mount_center_z'] + extent_z >= dims['base_height_z']:
            raise ValueError('超声波安装孔移出了盒壁，请调整整体中心高度或底盒高度。')
    return spec


def render_source(source, spec, item):
    source = prepare_source(source, item)
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
            from .solid_geometry import piece_lines
            out.extend(piece_lines(operation, name='_zw_piece'))
            out.append('_zw_before = _zw_target.val().Volume()')
            out.append(f'_zw_target = _zw_target.{"union" if operation.operation == "add" else "cut"}(_zw_piece).clean()')
            out.append('if abs(_zw_target.val().Volume() - _zw_before) < 0.000001: raise ValueError("改造操作未改变部件，请核对位置和尺寸")')
        out.append(f'{target} = _zw_target')
    # Separate solids are built from the same fixed numeric compiler. They are
    # never unioned into a case part or allowed to cut another part's geometry.
    out.append('_zw_added_parts = {}')
    from .solid_geometry import piece_lines
    for part in spec.addedParts:
        for index, operation in enumerate(part.operations):
            out.extend(piece_lines(operation, name='_zw_piece'))
            if index == 0:
                out.append('_zw_target = _zw_piece')
            else:
                out.append('_zw_before = _zw_target.val().Volume()')
                out.append(f'_zw_target = _zw_target.{"union" if operation.operation == "add" else "cut"}(_zw_piece).clean()')
                out.append('if abs(_zw_target.val().Volume() - _zw_before) < 0.000001: raise ValueError("独立零件操作未改变实体，请核对位置和尺寸")')
        out.append(f'_zw_added_parts[{part.id!r}] = _zw_target')
    objects = {part['id']: part['object'] for part in item['parts']}
    added_objects = {added_part_id(part): f'_zw_added_parts[{part.id!r}]' for part in spec.addedParts}
    for transform in spec.partTransforms:
        if transform.partId in added_objects:
            target = added_objects[transform.partId]
        else:
            name, _, index = objects[transform.partId].partition(':')
            if not name.isidentifier() or (index and not index.isdecimal()):
                raise ValueError('案例部件位置定义无效。')
            target = f'{name}[{int(index)}]' if index else name
        out.append(f'_zw_moved = {target}')
        for axis, angle in zip([(1, 0, 0), (0, 1, 0), (0, 0, 1)], transform.rotation):
            if angle:
                out.append(f'_zw_moved = _zw_moved.rotate((0, 0, 0), {axis!r}, {angle!r})')
        out.append(f'{target} = _zw_moved.translate({tuple(transform.translation)!r})')
    return text + '\n'.join(out) + '\n'


def effective_plan(spec, source):
    defaults = numeric_parameters(source)
    return {'parameters': {k: v for k, v in spec.parameterOverrides.items() if v != defaults[k][0]},
            'parts': {p.partId: [op.model_dump(mode='json') for op in p.operations] for p in spec.partOperations if p.operations},
            'positions': {p.partId: p.model_dump(mode='json') for p in spec.partTransforms if any(p.translation) or any(p.rotation)},
            'addedParts': {p.id: p.model_dump(mode='json') for p in spec.addedParts}}


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
    source = prepare_source(source, item)
    if not settings or not configured(settings):
        return TemplateEditSpec(title=item['title'], summary='原模板模型已保留。配置结构工程师的 AI 服务 后，可以对话修改此模板。',
            questions=['请先配置结构工程师的 AI 服务，再描述要修改的部件、尺寸或孔位。'])
    def parse(choice):
        message = choice.get('message')
        content = message.get('content') if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ValueError('缺少模板改造JSON正文。')
        content = content.strip()
        if content.startswith('```') and content.endswith('```'):
            content = content.partition('\n')[2][:-3].strip()
        return checked_spec(json.loads(content), item, source)
    instructions = ('你是掌问的结构工程师。用户是教师、学生或DIY爱好者，使用容易理解的中文，不称老板或总办。'
        '用户可以直接找你，是否协作由用户决定；记录本次变化，不声称已向学习设计师或智能工程师发送任务。'
        '只能基于给定的原始CAD模板返回一个完整JSON改造方案，不能返回Python、文件、命令或重建为普通方盒。'
        'parameterOverrides仅能使用allowedParameters中的现有参数名，数值单位毫米，角度参数为度；保留未请求修改的配合和硬件尺寸。'
        'partOperations仅能作用于printable=true部件。每个操作支持box/cylinder/sphere/cone/torus/extrude/revolve/loft的add或cut，按Schema提供轮廓或截面，可指定fillet圆角或chamfer倒角；尺寸为XYZ全长，圆柱XY是直径、Z是高度，圆柱初始沿Z轴，'
        '先绕全局X/Y/Z旋转，再平移到center。坐标是原模板装配坐标，并非归零后的打印坐标。加料必须连接原实体，切孔必须与原实体相交。'
        '现在支持addedParts新增独立打印零件，例如两孔连杆、连接销轴和铰链轴，不再受只能修改已有部件的旧限制。'
        '每件填写id（小写字母开头、其余仅小写字母/数字/连字符，最多40字符）、label中文名称、operations完整几何操作列表。'
        'operations使用相同的SolidPart几何类型，第一项必须add；后续add须连接本零件，cut只挖本零件，每件最终必须形成一个有效单实体。'
        '独立件可与案例保持间隙，不要为了新增零件把它焊进上盖或盒体。每件会真实进入整体/分件预览，单独导出归零STEP/STL并随项目保存。'
        '新增件使用原模板当前装配坐标；开盖或旋转后的连接孔需要计算实际坐标，定长连杆的两孔孔心须落在实际铰点，舵机臂不能默认与盖板同步旋转相同角度。'
        'partTransforms允许移动或旋转任意已登记部件，包括printable=false的硬件参考件和addedParts；原件partId取parts.id，新增件partId为added-加id。'
        'translation=[X,Y,Z]毫米，rotation=[X,Y,Z]度，先绕全局原点旋转再平移。'
        '位置每次相对原案例及当前参数计算，必须保留此前的位置变化，不把本轮增量当最终位置，不重复累计。移动参考件不会自动移动壳体开孔。'
        '自动感应开盖盒的超声波已有联动参数：ultrasonic_offset_x为横向偏移，负为左；ultrasonic_shell_mount_center_z为整体中心高度。'
        '这两个参数同步移动两个探头孔、四个固定孔及超声波参考件。用户要求超声波整体左移5毫米时，在当前偏移上减5，不能只移动孔位，也不需要另加ultrasonic的partTransforms。'
        '历史对话中“只能修改盒体、参考件不能移动”的限制已经解除，应按当前Schema处理，不再要求用户接受孔位和参考件分离。'
        '还支持kind=text的真实中文字形雕刻或浮雕：text文字（最多20字）、fontSize实际字高、depth深度、center三维表面中心、face外法线方向（top=+Z,bottom=-Z,front=-Y,back=+Y,left=-X,right=+X）、angle面内角度，operation=cut或add。'
        '文字使用随包中文字体真实闭合轮廓，保留字腔，不要用方块或假图案代替文字；center是字形包围框中心，cut朝实体内部，add朝外部。'
        '例如掌控板外壳背面（底壳外底面）居中凹刻掌问：partId=bottom，operations:[{kind:text,operation:cut,text:掌问,fontSize:8,depth:0.5,center:[0,-0.75,-1.5],face:bottom}]；深度必须小于底厚。'
        '完整方案每次从原始模板重新应用，必须保留currentEdit中此前要求的参数、操作、addedParts独立零件和位置，除非本轮明确撤销或重置。不要重复累计已有操作。'
        '不得假称已生成、已装配或实物兼容。无法明确表达的改动用questions询问，不得用无关近似模型假装完成。'
        '默认先更新模型预览再让用户确认。外观尺寸、厚度或角度未给出时保留原案例数值，或按需求采用可逆初稿值，'
        '用assumptions说明数值与依据，不因缺这些尺寸要求用户先提供尺寸表。保留currentEdit中尚未核实的assumptions，明确解决后才移除。'
        'conversation.projectHardware提供全部主控与模块机械档案及修订，conversation.projectControllers标识独立实物。'
        + assembly_instructions() +
        '未知孔位不能猜测，可先保留原案例参考件或预留空间并在assumptions说明待适配。'
        '只有明确要求精确安装但缺必要资料，或无法表达核心改动时，questions最多问一个真正阻塞的问题。'
        'JSON Schema: ' + json.dumps(TemplateEditSpec.model_json_schema(), ensure_ascii=False))
    context = {'template': {key: item[key] for key in ['id', 'title', 'description', 'notes', 'parts']},
        'allowedParameters': {name: value for name, (value, _) in numeric_parameters(source).items()},
        'originalSourceReference': source, 'currentEdit': previous.get('templateEdit'),
        'currentParts': previous.get('templateParts'), 'conversation': conversation}
    return await propose(message, 'model', settings, context, instructions=instructions, parser=parse)
