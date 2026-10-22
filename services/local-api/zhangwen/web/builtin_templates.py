"""Versioned CAD templates with bounded numeric/boolean edits; no model Python."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime

from fastapi import HTTPException
from . import template_edits

DIRECTORY = Path(__file__).resolve().parents[4] / 'services/structure-cad/templates'
MANIFEST = json.loads((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
TEMPLATES = {item['id']: item for item in MANIFEST['templates']}


def public_template(item):
    return {**{key: item[key] for key in ['id', 'revision', 'title', 'description', 'size', 'notes']},
            'image': '/api/structure/templates/media/' + item['image'], 'sourceSha256': item['sha256']}


def checked_source(item):
    source = DIRECTORY / item['file']
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError('内置模板源码摘要不符，请修复安装后重试。')
    return source


def asset_names():
    return {f'template-{part["id"]}.{fmt}' for item in TEMPLATES.values()
            for part in item['parts'] for fmt in (['stl', 'step'] if part['printable'] else ['stl'])}


async def act(request, previous, job_root, settings=None, conversation=None):
    ident = request.template or previous.get('builtinTemplate', {}).get('id')
    item = TEMPLATES.get(ident)
    if not item or request.designType != 'model':
        raise HTTPException(422, '内置模板与当前模式不一致。')
    if not request.template and previous.get('builtinTemplate', {}).get('revision') != item['revision']:
        raise HTTPException(422, '此历史模板修订暂不能重新生成，请选择当前模板创建新版本；旧文件仍可导出。')
    if request.parameters or request.faces or request.rotations:
        raise HTTPException(422, '模板改造请通过对话提交，不接受通用外壳尺寸或硬件布局参数。')
    try:
        source = checked_source(item)
    except (OSError, ValueError) as exc:
        raise HTTPException(422, '模板来源校验失败，未执行建模；原版本保留。') from exc
    original_source = source.read_text(encoding='utf-8-sig')
    local_edit = False
    try:
        edit = template_edits.checked_spec(previous.get('templateEdit') or {'title': item['title']}, item, original_source) if not request.template else template_edits.TemplateEditSpec(title=item['title'])
        if request.action in {'analyze', 'revise'} and not request.template:
            proposed = template_edits.local_text_edit(request.message, previous, item, original_source, conversation)
            local_edit = proposed is not None
            if proposed is None:
                proposed = await template_edits.propose_edit(request.message, previous, item, original_source, settings, conversation)
            if proposed.questions:
                return {**previous, 'status': 'needs_input', 'message': proposed.summary, 'questions': proposed.questions,
                        'requestText': request.message, 'blocking_reason': 'template_questions'}
            if template_edits.effective_plan(proposed, original_source) == template_edits.effective_plan(edit, original_source):
                return {**previous, 'status': 'needs_input', 'title': '本轮改造尚未实施',
                        'message': '本轮方案没有新的尺寸或几何改动，未生成新模型；当前显示上一版。',
                        'questions': ['请补充要实际修改的部件、尺寸或文字内容；不支持的要求不能标为生成成功。'],
                        'requestText': request.message, 'blocking_reason': 'unchanged_template_plan'}
            edit = proposed
    except ValueError as exc:
        raise HTTPException(422, '模板改造方案未通过校验，原模型保留。') from exc
    edited_source = template_edits.render_source(original_source, edit, item)
    checks = [{'id': 'source', 'status': 'pass', 'message': f'内置模板修订 {item["revision"]}，来源 SHA-256 一致。'},
              *[{'id': f'fit-{i}', 'status': 'warning', 'message': note} for i, note in enumerate(item['notes'])]]
    if request.action == 'validate':
        # Keep immutable geometry/export references; do not treat metadata as a fresh geometry build.
        return {**previous, 'checks': checks + [check for check in previous.get('checks', []) if check['id'] in {'solid', 'physical'}]}
    size = dict(zip(['length_x', 'width_y', 'height_z'], item['size']))
    result = {'designKind': 'builtin', 'designTemplate': ident, 'builtinTemplate': public_template(item),
              'title': edit.title, 'message': edit.summary or item['description'], 'questions': [], 'parameters': {},
              'templateEdit': edit.model_dump(mode='json'), 'requestText': request.message or previous.get('requestText', ''),
              'generationSource': 'local_text_intent' if local_edit else 'template',
              'cadquery_code': edited_source, 'checks': checks, 'exports': [],
              'design_state': {'id': '', 'parameters': {}, 'enclosure_parameters': {'outer_box_size': size}, 'bom': []}}
    if request.action not in {'build', 'parameters', 'selected', 'analyze', 'revise', 'confirm'}:
        return {**result, 'status': 'confirmation', 'message': item['description'] + ' 固定尺寸，请核对适配说明后生成。'}
    design_id = 'ZW-PRODUCT-' + datetime.now().strftime('%Y%m%d-%H%M%S')
    output = job_root / 'exports' / design_id
    output.mkdir(parents=True, exist_ok=False)
    (output / 'template-edit.json').write_text(edit.model_dump_json(), encoding='utf-8')
    # The worker receives an allowlisted ID, never persisted code, paths or object names.
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'zhangwen.web.template_worker', ident, str(output),
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
        raise HTTPException(504, '模板建模超时，原版本保留。') from exc
    if process.returncode:
        raise HTTPException(422, '改造未能形成有效单实体，或操作未改变部件；原版本保留。请核对参数、孔位和连接关系后重试。')
    report = json.loads(stdout)
    result['templateParts'] = report['parts']
    result['design_state']['enclosure_parameters']['outer_box_size'] = dict(zip(size, report['size']))
    result['checks'].append({'id': 'solid', 'status': 'pass', 'message': f'{report["printableCount"]} 个打印部件均为有效单实体，STEP/STL 已生成。'})
    result['checks'].append({'id': 'physical', 'status': 'warning', 'message': '几何检查通过；未完成实物打印、配合及强度验收。'})
    for part in report['parts']:
        for fmt in (['step', 'stl'] if part['printable'] else ['stl']):
            filename = f'template-{part["id"]}.{fmt}'
            result['exports'].append({'id': f'template_{part["id"]}_{fmt}',
                'label': f'{part["label"]} · {fmt.upper()}' + ('' if part['printable'] else '（参考，非打印）'),
                'format': fmt, 'url': f'/exports/{design_id}/{filename}', 'fidelity': 'cadquery'})
    (output / 'cadquery.py').write_text(edited_source, encoding='utf-8')
    result['exports'].append({'id': 'cadquery_py', 'label': '含注释的模板源码', 'format': 'py', 'url': f'/exports/{design_id}/cadquery.py'})
    result['exports'].append({'id': 'template_edit_json', 'label': '模板改造方案', 'format': 'json', 'url': f'/exports/{design_id}/template-edit.json'})
    result['build'] = {'status': 'artifact_exports', 'message': '真实分件 STEP/STL 已生成；打印文件已移至 Z=0，硬件参考件不参与打印。'}
    return {**result, 'status': 'artifact', 'message': (edit.summary + '\n' if edit.summary else '') + result['build']['message']}
