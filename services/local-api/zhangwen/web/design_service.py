"""Hardware-free solids and laser documents within the existing structure history."""
import asyncio
import json
import math
import os
import sys
from datetime import datetime

from fastapi import HTTPException
from .design_specs import DesignSpec, template_spec, propose, solid_code, svg, dxf
from . import laser_text, laser_rounded_box


def solid_bounds(spec, scale):
    bounds = []
    for part in spec.solid:
        if part.operation != 'add':
            continue
        # Conservative axis-aligned draft bounds; final bounds come from OCP.
        rx, ry, rz = [math.radians(n) for n in part.rotation]
        cx, cy, cz, sx, sy, sz = math.cos(rx), math.cos(ry), math.cos(rz), math.sin(rx), math.sin(ry), math.sin(rz)
        matrix = [[cz*cy, cz*sy*sx-sz*cx, cz*sy*cx+sz*sx], [sz*cy, sz*sy*sx+cz*cx, sz*sy*cx-cz*sx], [-sy, cy*sx, cy*cx]]
        half = [sum(abs(matrix[i][j]) * part.size[j] / 2 for j in range(3)) for i in range(3)]
        bounds.append([(part.center[i] - half[i], part.center[i] + half[i]) for i in range(3)])
    return [round((max(b[i][1] for b in bounds) - min(b[i][0] for b in bounds)) * scale, 3) for i in range(3)]


async def act(request, previous, settings, job_root, conversation=None):
    kind = 'laser' if request.designType == 'laser' else 'parametric'
    # Text revisions must reach the model, even when the source was a template.
    editing = request.action in {'analyze', 'revise', 'selected'}
    template = request.template if editing else previous.get('designTemplate')
    params = {**next(iter(previous.get('parameters', {}).values()), {}), **request.parameters}
    try:
        if editing:
            if template:
                spec = template_spec(template, params)
            else:
                context = {'spec': previous.get('designSpec'), 'priorRequest': previous.get('requestText', ''), **(conversation or {})}
                spec = await propose(request.message, request.designType, settings, context)
                params = {'scale': 1}
        elif previous.get('designSpec'):
            if template == 'finger-box':
                params['material'] = (previous['designSpec'].get('fingerBox') or {}).get('material', '待确认材料')
                params['panelTexts'] = previous['designSpec'].get('panelTexts', [])
            if template == 'rounded-box':
                params['material'] = (previous['designSpec'].get('roundedBox') or {}).get('material', '待确认材料')
            spec = DesignSpec.model_validate(previous['designSpec']) if request.action == 'validate' or not template else template_spec(template, params)
        else:
            raise HTTPException(422, '请先输入需求或选择设计模板。')
        spec.check_kind(request.designType)
        if spec.fingerBox and not spec.questions:
            template = 'finger-box'
            params = {key: getattr(spec.fingerBox, key) for key in ['width', 'depth', 'height', 'thickness']}
        if spec.roundedBox and not spec.questions:
            template = 'rounded-box'
            params = {key: float(getattr(spec.roundedBox, key)) for key in laser_rounded_box.DEFAULTS}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result = {'designKind': kind, 'designSpec': spec.model_dump(mode='json'), 'designTemplate': template,
              'title': spec.title, 'message': spec.summary, 'questions': spec.questions,
              'requestText': request.message or previous.get('requestText', ''), 'exports': [], 'checks': []}
    if spec.questions:
        return {**result, 'status': 'needs_input', 'blocking_reason': 'llm_unavailable' if spec.title == '需要配置模型' else 'design_questions'}
    if template == 'rounded-box':
        result['parameters'] = {'design': params}
        result['parameters']['design'].pop('material', None)
    elif template:
        keys = {'cup': {'width', 'height', 'thickness'}, 'plate': {'width', 'depth', 'thickness'}, 'round-tag': {'width', 'thickness'}}.get(template, {'width', 'depth', 'height', 'thickness'})
        result['parameters'] = {'design': {key: params.get(key, default) for key, default in [('width', 80), ('depth', 60), ('height', 40), ('thickness', 3)] if key in keys}}
    else:
        result['parameters'] = {'design': {'scale': params.get('scale', 1)}}
    scale = 1 if template else params.get('scale', 1)
    if not .1 <= scale <= 5:
        raise HTTPException(422, '缩放比例须在0.1到5之间。')
    if spec.drawing:
        if scale != 1:
            data = spec.drawing.model_dump()
            data['width'] *= scale; data['height'] *= scale
            for shape in data['shapes']:
                for key in ['x', 'y', 'width', 'height', 'radius', 'fontSize']:
                    shape[key] *= scale
                shape['points'] = [[n * scale for n in point] for point in shape['points']]
            from .design_specs import Drawing
            drawing = Drawing.model_validate(data)
        else:
            drawing = spec.drawing
        result['laserDrawing'] = drawing.model_dump(mode='json')
        result['laserTextPaths'] = {str(i):laser_text.svg_path(shape) for i,shape in enumerate(drawing.shapes) if shape.kind == 'text'}
        result['checks'] = [{'id': 'paths', 'status': 'pass', 'message': f'{len(drawing.shapes)}条路径；坐标范围、闭合要求与完全重复路径检查通过。'},
                            {'id': 'fabrication', 'status': 'warning', 'message': '名义尺寸，未补偿刀缝；材料、孔间距、交叉路径与装配需加工前复核。'}]
        if spec.fingerBox:
            result['checks'].insert(1, {'id': 'joinery', 'status': 'pass', 'message': '六块板按同一边长分段生成交替互补榫齿，三面角部统一分配；改变尺寸或板厚会重新生成轮廓。'})
        if spec.roundedBox:
            result['checks'].insert(1, {'id':'living-hinge',
                'status':'pass' if spec.roundedBox.pattern_version == 2 else 'warning',
                'message':'圆角盖板榫与围板凹槽同源生成；四个弯折区按中性层弧长展开，切缝交错接到上下边缘，保留中间连接桥。'
                    if spec.roundedBox.pattern_version == 2 else '旧版切缝未接通上下边缘；应用参数重新生成可保留历史并创建修正版。'})
            result['checks'].append({'id':'bend-material','status':'warning','message':'切缝为切穿线段；仅适用于经试切可弯折的材料，不能保证普通亚克力或任意木板可弯折。围板中间接缝需胶合，实际装配、桥宽与刀缝须试切确认。'})
        if result['laserTextPaths']:
            result['checks'].append({'id':'text', 'status':'pass', 'message':'文字已使用随包中文字体转为矢量轮廓，SVG填充雕刻区域、DXF为ENGRAVE层闭合轮廓；加工填充方式需在加工软件中选择。'})
    else:
        size = solid_bounds(spec, scale)
        result['design_state'] = {'id': '', 'parameters': {}, 'enclosure_parameters': {'outer_box_size': dict(zip(['length_x', 'width_y', 'height_z'], size))}, 'bom': []}
        result['cadquery_code'] = solid_code(spec, scale)
    if request.action not in {'build', 'parameters', 'validate'}:
        return {**result, 'status': 'confirmation', 'message': spec.summary + ' 请核对尺寸后生成。'}
    if request.action == 'validate':
        return {**previous, 'checks': result['checks'] or [{'id': 'spec', 'status': 'pass', 'message': '结构化实体尺寸与操作清单有效；实物强度及打印条件需另行核对。'}]}
    design_id = 'ZW-PRODUCT-' + datetime.now().strftime('%Y%m%d-%H%M%S')
    output = job_root / 'exports' / design_id
    output.mkdir(parents=True, exist_ok=False)
    def export(name, label, format):
        return {'id': name.replace('.', '_'), 'label': label, 'format': format, 'url': f'/exports/{design_id}/{name}'}
    if spec.drawing:
        (output / 'cut.svg').write_text(svg(drawing), encoding='utf-8')
        (output / 'preview.svg').write_text(svg(drawing, preview=True), encoding='utf-8')
        (output / 'cut.dxf').write_text(dxf(drawing), encoding='ascii')
        result['exports'] = [export('cut.svg', '切割图 · SVG毫米', 'svg'), export('cut.dxf', '切割图 · DXF毫米分层', 'dxf'), export('preview.svg', '材料设计预览', 'svg')]
        result['build'] = {'status': 'laser_exports', 'message': '图纸已生成，红色为切割、蓝色为雕刻；未进行机器加工。'}
    else:
        (output / 'design-spec.json').write_text(json.dumps({'spec': spec.model_dump(mode='json'), 'scale': scale}), encoding='utf-8')
        (output / 'cadquery.py').write_text(result['cadquery_code'], encoding='utf-8')
        process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'zhangwen.web.solid_worker', str(output),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env={**os.environ, 'PYTHONUTF8': '1'},
            **({'creationflags': 0x08000000} if sys.platform == 'win32' else {}))
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=120)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if process.returncode is None:
                process.kill()
            await process.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise HTTPException(504, '实体建模超时，原版本保留，请简化布尔运算。') from exc
        if process.returncode != 0:
            raise HTTPException(422, '当前尺寸或布尔组合无法形成有效实体，请调整后重试；原版本保留。')
        report = json.loads(stdout)
        result['design_state']['enclosure_parameters']['outer_box_size'] = dict(zip(['length_x', 'width_y', 'height_z'], report['size']))
        result['exports'] = [dict(export('model.step', '实体模型 · STEP', 'step'), id='cadquery_step', fidelity='cadquery'),
                             dict(export('model.stl', '打印模型 · STL', 'stl'), id='cadquery_base_stl', fidelity='cadquery'),
                             export('cadquery.py', '含注释的建模代码', 'py')]
        result['checks'] = [{'id': 'solid', 'status': 'pass', 'message': f'实体有效，{report["solids"]}个实体，体积{report["volume"]:.1f}mm³。'},
                            {'id': 'print', 'status': 'warning', 'message': '几何有效性不能代替打印、强度或实物装配验收。'}]
        result['build'] = {'status': 'artifact_exports', 'message': '真实STEP/STL已生成。'}
    (output / 'design-spec.json').write_text(json.dumps({'spec': spec.model_dump(mode='json'), 'scale': scale}, ensure_ascii=False), encoding='utf-8')
    return {**result, 'status': 'artifact', 'message': result['build']['message']}
