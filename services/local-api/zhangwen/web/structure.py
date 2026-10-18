"""Trusted deterministic CAD adapter; reuses Project/Conversation/Artifact.

The worker has no HTTP listener, accepts no source code/commands, and only
builds from server-held drafts. Every operation writes a new immutable folder.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from zhangwen.artifacts.models import ArtifactStatus, ArtifactPreview, ArtifactPreviewKind
from zhangwen.llm.contracts import ChatMessage, ChatMessageStatus, ChatRole
from . import design_service
from .version_names import short_name

ROOT = Path(__file__).resolve().parents[4]
CAD_ROOT = ROOT / 'services/structure-cad'
FILES = {'cadquery.py', 'design-state.json', 'checks.json', 'artifact.json', 'preview.gltf',
         'design-spec.json', 'cut.svg', 'cut.dxf', 'preview.svg',
         'base.stl', 'lid.stl', 'hardware-reference.stl', 'opening-reference.stl',
         'model.step', 'base.step', 'lid.step', 'hardware.step', 'model.stl', 'hardware.stl', 'mesh-checks.json'}
FILES.update(f'workflow/{name}' for name in ['00_requirement_analysis.json', '01_intent.json', '02_bom.json',
    '03_profile_report.json', '04_feasibility_report.json', '05_layout_plan.json', '06_checks.json', '07_cadquery.py', '08_export_manifest.json'])


class StructureInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['analyze', 'confirm', 'build', 'revise', 'parameters', 'validate', 'selected']
    expectedRevision: int = Field(ge=0)
    sourceRevision: int | None = Field(default=None, ge=1)
    message: str = Field(default='', max_length=4000)
    selectedIds: list[str] | None = Field(default=None, max_length=32)
    customProfiles: list[dict[str, Any]] | None = Field(default=None, max_length=32)
    parameters: dict[str, float] = Field(default_factory=dict)
    faces: dict[str, Literal['base_floor', 'lid_inner']] = Field(default_factory=dict)
    rotations: dict[str, float] = Field(default_factory=dict)
    resolutionOptionId: str = Field(default='', max_length=150)
    designType: Literal['model', 'laser'] = 'model'
    template: Literal['box', 'cup', 'bracket', 'plate', 'round-tag', 'panel-box', 'finger-box', 'rounded-box'] | None = None

    @field_validator('parameters')
    @classmethod
    def finite_dimensions(cls, value):
        import math
        if len(value) > 100 or any(not re.fullmatch(r'[a-z0-9_]{1,100}', k) or not math.isfinite(v) or not (-500 if k.endswith(('_offset_x', '_offset_y')) else 0) <= v <= 1000 for k, v in value.items()):
            raise ValueError('尺寸必须是0到1000毫米内的有限数值。')
        if any(value.get(k, 1) < .8 for k in ('wall_thickness', 'floor_thickness', 'lid_thickness')):
            raise ValueError('壁厚、底厚、盖厚至少0.8毫米。')
        if value.get('vent_count', 0) > 40:
            raise ValueError('散热孔最多40个。')
        return value


class StructureCheckpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    versions: list[dict[str, Any]] = Field(max_length=200)
    messages: list[dict[str, str]] = Field(max_length=2000)
    assets: dict[str, dict[str, str]] = Field(default_factory=dict, max_length=5000)

    @model_validator(mode='after')
    def checked(self):
        if any(type(v.get('revision')) is not int for v in self.versions):
            raise ValueError('结构版本号无效。')
        if sorted(v.get('revision', 0) for v in self.versions) != list(range(1, len(self.versions) + 1)):
            raise ValueError('结构版本必须从1开始连续。')
        for version in self.versions:
            if not re.fullmatch('[a-f0-9]{32}', str(version.get('jobId', ''))) or not isinstance(version.get('result'), dict):
                raise ValueError('结构版本格式无效。')
            if version['result'].get('status') not in {'artifact', 'confirmation', 'requirement_analysis', 'needs_input'}:
                raise ValueError('结构阶段无效。')
            try:
                datetime.fromisoformat(version['createdAt'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('结构版本时间无效。') from exc
            if version.get('designType', 'model') not in {'model', 'laser'}:
                raise ValueError('结构设计类型无效。')
            if not isinstance(version.get('prompt'), str) or not isinstance(version.get('selectedIds'), list) or not isinstance(version.get('customProfiles'), list):
                raise ValueError('结构上下文无效。')
            if len(version['selectedIds']) > 32 or not all(isinstance(x, str) for x in version['selectedIds']) or not all(isinstance(x, dict) and isinstance(x.get('id'), str) for x in version['customProfiles']):
                raise ValueError('结构硬件格式无效。')
            result = version['result']
            if 'designKind' in result and result['designKind'] not in {'parametric', 'laser'}:
                raise ValueError('未知的结构几何类型。')
            if 'designSpec' in result or 'laserDrawing' in result:
                from .design_specs import DesignSpec, Drawing
                if result.get('designSpec') is not None:
                    DesignSpec.model_validate(result['designSpec']).check_kind(version.get('designType', 'model'))
                if result.get('laserDrawing') is not None:
                    Drawing.model_validate(result['laserDrawing'])
            if not isinstance(result.get('parameters', {}), dict) or not isinstance(result.get('questions', []), list):
                raise ValueError('结构参数或问题格式无效。')
            for key in ('checks', 'exports', 'resolution_options', 'bom', 'partial_bom'):
                if not isinstance(result.get(key, []), list) or not all(isinstance(x, dict) for x in result.get(key, [])):
                    raise ValueError('结构结果格式无效。')
            for check in result.get('checks', []):
                if not isinstance(check.get('status'), str) or not isinstance(check.get('message'), str):
                    raise ValueError('结构检查格式无效。')
            for option in result.get('resolution_options', []):
                if not isinstance(option.get('id'), str) or any(k in option and not isinstance(option[k], str) for k in ('label', 'title', 'description')):
                    raise ValueError('结构选项格式无效。')
            report = result.get('requirement_analysis_report')
            if report is not None and (not isinstance(report, dict) or not isinstance(report.get('functions', []), list) or not all(isinstance(x, dict) and isinstance(x.get('name'), str) for x in report.get('functions', []))):
                raise ValueError('结构需求分析格式无效。')
            for key in ('title', 'message', 'cadquery_code'):
                if key in result and not isinstance(result[key], str):
                    raise ValueError('结构回复格式无效。')
            if not all(isinstance(x, str) for x in result.get('questions', [])):
                raise ValueError('结构问题格式无效。')
            for group in result.get('parameters', {}).values():
                if not isinstance(group, dict) or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in group.values()):
                    raise ValueError('结构参数无效。')
            state = result.get('design_state')
            if state is not None and not isinstance(state, dict):
                raise ValueError('结构草案格式无效。')
            if state:
                try:
                    size = state['enclosure_parameters']['outer_box_size']
                    if not all(isinstance(size[k], (float, int)) and math.isfinite(size[k]) and 0 < size[k] <= 2000 for k in ('length_x', 'width_y', 'height_z')):
                        raise ValueError('外壳尺寸无效。')
                    for item in state.get('layout_plan', {}).get('hardware_transforms', []):
                        if not isinstance(item['hardware_id'], str) or not isinstance(item['name'], str):
                            raise ValueError('硬件布局无效。')
                        if not all(isinstance(item['center'][k], (int, float)) and math.isfinite(item['center'][k]) for k in ('x', 'y', 'z')):
                            raise ValueError('硬件位置无效。')
                        if not all(isinstance(item['bounding_box'][k], (int, float)) and 0 < item['bounding_box'][k] <= 1000 for k in ('length_x', 'width_y', 'height_z')):
                            raise ValueError('硬件尺寸无效。')
                except (KeyError, TypeError, AttributeError) as exc:
                    raise ValueError('结构草案格式无效。') from exc
            for item in result.get('exports', []):
                if not all(isinstance(item.get(k), str) for k in ('id', 'label', 'format')):
                    raise ValueError('导出文件格式无效。')
                if item.get('url') is not None and not isinstance(item['url'], str):
                    raise ValueError('导出文件地址无效。')
                if item.get('url'):
                    prefix = '/api/projects/__PROJECT__/structure/assets/'
                    if not item['url'].startswith(prefix) or item['url'][len(prefix):] not in self.assets:
                        raise ValueError('导出文件未随项目保存。')
        for message in self.messages:
            if message.get('designType', 'model') not in {'model', 'laser'}:
                raise ValueError('结构对话类型无效。')
            if message.get('role') not in {'user', 'assistant'} or not all(k in message for k in ['id', 'content', 'createdAt']):
                raise ValueError('结构对话无效。')
            datetime.fromisoformat(message['createdAt'])
        for key, asset in self.assets.items():
            if not re.fullmatch(r'[a-f0-9]{32}/ZW-PRODUCT-\d{8}-\d{6}(?:-\d{2})?/.+', key) or key.split('/', 2)[2] not in FILES:
                raise ValueError('结构资产路径不在允许清单。')
            try:
                data = base64.b64decode(asset['content'], validate=True)
                if hashlib.sha256(data).hexdigest() != asset['sha256']:
                    raise ValueError('结构文件摘要不符。')
            except (KeyError, ValueError) as exc:
                raise ValueError('结构文件损坏，未导入。') from exc
        return self


def export_structure(repo, project_id: str) -> dict | None:
    service = StructureService(repo, repo.projects.data_dir)
    value = service.get(project_id)
    if not value['versions']:
        return None
    assets = {}
    for version in value['versions']:
        urls = re.findall(r'"(/api/projects/[^" ]+/structure/assets/[^"]+)"', json.dumps(version['result']))
        for url in urls:
            key = url.split('/structure/assets/', 1)[1]
            job, design, filename = key.split('/', 2)
            path = service.asset(project_id, job, design, filename)
            data = path.read_bytes()
            assets[key] = {'sha256': hashlib.sha256(data).hexdigest(), 'content': base64.b64encode(data).decode()}
        version['result'] = json.loads(json.dumps(version['result']).replace(f'/api/projects/{project_id}/', '/api/projects/__PROJECT__/'))
    return StructureCheckpoint(versions=value['versions'], messages=value['messages'], assets=assets).model_dump()


def prepare_structure_import(repo, checkpoint: StructureCheckpoint | None):
    if checkpoint is None:
        return
    root = (repo.projects.data_dir / 'structure').resolve()
    for key, asset in checkpoint.assets.items():
        job, design, name = key.split('/', 2)
        path = root / job / 'exports' / design / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise HTTPException(422, '结构资产路径无效。')
        data = base64.b64decode(asset['content'], validate=True)
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise HTTPException(409, '本机已有不同内容的结构资产，未覆盖。')
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as file:
                file.write(data)


def insert_structure_import(repo, conn, project_id: str, checkpoint: StructureCheckpoint | None):
    if checkpoint is None or not checkpoint.versions:
        return
    artifact_id = 'zhangwen_structure_' + project_id
    now = datetime.now(UTC).isoformat()
    versions = sorted(checkpoint.versions, key=lambda v: v['revision'])
    ids = {v['revision']: 'artifact_version_' + uuid.uuid4().hex for v in versions}
    conn.execute('''INSERT INTO artifacts (id, project_id, title, kind, status, source_agent_id, current_version_id, created_at, updated_at)
        VALUES (?, ?, '结构设计', 'MODEL_3D', 'DRAFT', 'zhangwen-structure-import', ?, ?, ?)''', (artifact_id, project_id, ids[versions[-1]['revision']], now, now))
    for version in versions:
        value = json.loads(json.dumps(version).replace('/api/projects/__PROJECT__/', f'/api/projects/{project_id}/'))
        text = json.dumps(value, ensure_ascii=False)
        conn.execute('''INSERT INTO artifact_versions (id, artifact_id, project_id, version, status, mime_type,
            preview_json, dependencies_json, source_entity_type, source_entity_id, checksum, created_at)
            VALUES (?, ?, ?, ?, 'DRAFT', 'application/json', ?, '[]', 'zhangwen_structure', ?, ?, ?)''',
            (ids[version['revision']], artifact_id, project_id, version['revision'], json.dumps({'kind': 'CODE', 'code': text, 'language': 'json'}),
             uuid.uuid4().hex, hashlib.sha256(text.encode()).hexdigest(), version['createdAt']))
    conversation_id = conn.execute('SELECT id FROM conversations WHERE project_id=? ORDER BY created_at LIMIT 1', (project_id,)).fetchone()[0]
    for m in checkpoint.messages:
        repo.projects._insert_message(conn, conversation_id, project_id,
            ChatMessage(id='msg_' + uuid.uuid4().hex, role=ChatRole(m['role']), content=m['content'],
                status=ChatMessageStatus.COMPLETED, createdAt=m['createdAt'], updatedAt=m['createdAt'], metadata={'structure': True, 'portableMessageId': m['id'], 'designType': m.get('designType', 'model')}))


class StructureService:
    def __init__(self, repo, data_dir: Path):
        self.repo = repo
        self.root = (data_dir / 'structure').resolve()
        self.gate = asyncio.Lock()
        self.catalog = json.loads((CAD_ROOT / 'server/data/hardware-library.json').read_text(encoding='utf-8'))

    def get(self, project_id: str) -> dict:
        self.repo.get(project_id)
        with self.repo.connect() as conn:
            versions = conn.execute('''SELECT version, preview_json FROM artifact_versions
                WHERE artifact_id=? ORDER BY version DESC''', (self.repo.artifact_id(project_id, 'structure'),)).fetchall()
            messages = conn.execute('''SELECT COALESCE(json_extract(metadata_json, '$.portableMessageId'), id) AS id, role, content, created_at AS createdAt,
                COALESCE(json_extract(metadata_json, '$.designType'), 'model') AS designType FROM messages
                WHERE project_id=? AND json_extract(metadata_json, '$.structure')=1 ORDER BY rowid''', (project_id,)).fetchall()
        values = [json.loads(row['preview_json'])['code'] for row in versions]
        parsed = [json.loads(x) for x in values]
        for version in parsed:
            version.setdefault('name', short_name(version['result'].get('title') or version.get('prompt', ''), '结构设计'))
        return {'revision': versions[0]['version'] if versions else 0, 'versions': parsed,
                'messages': [dict(row) for row in messages]}

    def commit(self, project_id: str, version: dict, user: str, reply: str):
        # The immutable version and its dialogue must succeed in one transaction.
        # Reuse the original Artifact schema and context projection (as folder import does).
        with self.repo.lock:
            now = datetime.now(UTC).isoformat()
            artifact_id = self.repo.artifact_id(project_id, 'structure')
            source_id = uuid.uuid4().hex
            version_id = f'artifact_version_{artifact_id}_{source_id}'
            content = json.dumps(version, ensure_ascii=False)
            preview = ArtifactPreview(kind=ArtifactPreviewKind.CODE, code=content, language='json',
                summary='结构设计检查与模型产物；未证明实物可装配。')
            with self.repo.connect() as conn:
                conn.execute('''INSERT INTO artifacts (id, project_id, title, kind, status, source_agent_id,
                    current_version_id, created_at, updated_at) VALUES (?, ?, '结构设计', 'MODEL_3D', 'DRAFT', 'zhangwen-structure', ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET current_version_id=excluded.current_version_id, updated_at=excluded.updated_at''',
                    (artifact_id, project_id, version_id, now, now))
                conn.execute('''INSERT INTO artifact_versions (id, artifact_id, project_id, version, status,
                    mime_type, preview_json, dependencies_json, source_entity_type, source_entity_id, checksum, created_at)
                    VALUES (?, ?, ?, ?, 'DRAFT', 'application/json', ?, '[]', 'zhangwen_structure', ?, ?, ?)''',
                    (version_id, artifact_id, project_id, version['revision'], preview.model_dump_json(), source_id,
                     hashlib.sha256(content.encode()).hexdigest(), now))
                self.repo.artifacts._apply_artifact_context(conn, artifact_id=artifact_id, version_id=version_id,
                    project_id=project_id, source_agent_id='zhangwen-structure', status=ArtifactStatus.DRAFT)
                conversation_id = conn.execute('SELECT id FROM conversations WHERE project_id=? ORDER BY created_at LIMIT 1', (project_id,)).fetchone()[0]
                for role, text in [('user', user), ('assistant', reply)]:
                    self.repo.projects._insert_message(conn, conversation_id, project_id,
                        ChatMessage(id='msg_' + uuid.uuid4().hex, role=ChatRole(role), content=text,
                            status=ChatMessageStatus.COMPLETED, createdAt=now, updatedAt=now, metadata={'structure': True, 'designType': version.get('designType', 'model')}))

    async def worker(self, payload: dict) -> dict:
        node = os.environ.get('ZHANGWEN_NODE') or shutil.which('node')
        if not node:
            raise HTTPException(503, '未找到 Node.js，请通过掌问启动入口启动平台。')
        process = await asyncio.create_subprocess_exec(node, str(CAD_ROOT / 'worker.mjs'),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=ROOT, env={**os.environ, 'PYTHONUTF8': '1'}, **({'creationflags': 0x08000000} if sys.platform == 'win32' else {}))
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(json.dumps(payload, ensure_ascii=False).encode()), timeout=300)
        except (TimeoutError, asyncio.CancelledError) as exc:
            process.kill()
            await process.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise HTTPException(504, '结构设计处理超时，原版本已保留，请稍后重试。') from exc
        if process.returncode or len(stdout) > 16_000_000:
            raise HTTPException(502, '结构设计工具处理失败，原版本已保留；请检查尺寸或模型连接后重试。')
        try:
            return json.loads(stdout)
        except ValueError as exc:
            raise HTTPException(502, '结构工具未返回完整结果，原版本已保留。') from exc

    async def act(self, project_id: str, request: StructureInput, settings: dict) -> dict:
        if self.gate.locked():
            raise HTTPException(409, '已有结构设计正在处理，请完成后再操作。')
        async with self.gate:
            workspace = self.get(project_id)
            if workspace['revision'] >= 200:
                raise HTTPException(413, '当前项目已有200个结构版本，请保存归档后新建项目。')
            if workspace['revision'] != request.expectedRevision:
                raise HTTPException(409, '结构版本已在另一页面更新，请重新加载后再操作。')
            base = next((v for v in workspace['versions'] if (not request.sourceRevision or v['revision'] == request.sourceRevision)
                         and v.get('designType', 'model') == request.designType), None)
            if request.sourceRevision and not base:
                raise HTTPException(404, '结构历史版本不存在。')
            if request.action not in {'analyze', 'selected'} and not base:
                raise HTTPException(422, '请先描述需求或选择硬件生成草案。')
            previous = base['result'] if base else {}
            ids = request.selectedIds if request.selectedIds is not None else base['selectedIds'] if base else []
            profiles = request.customProfiles if request.customProfiles is not None else base['customProfiles'] if base else []
            known = {x['id'] for x in self.catalog['profiles']}
            for profile in profiles:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(profile.get('id', ''))):
                    raise HTTPException(422, '自定义结构资料须有有效id。')
                dims = profile.get('dimensions_mm', {})
                if not isinstance(dims, dict) or not all(isinstance(dims.get(k), (int, float)) and 0 < dims[k] <= 500 for k in ['length_x', 'width_y', 'height_z']):
                    raise HTTPException(422, '自定义硬件长宽高必须在0到500毫米内。')
                known.add(profile['id'])
            def bounded(value, depth=0):
                if depth > 15:
                    return False
                if isinstance(value, (int, float)):
                    return math.isfinite(value) and abs(value) <= 10000
                if isinstance(value, dict):
                    return len(value) <= 100 and all(k not in {'__proto__', 'constructor', 'prototype'} and bounded(v, depth + 1) for k, v in value.items())
                if isinstance(value, list):
                    return len(value) <= 200 and all(bounded(v, depth + 1) for v in value)
                return value is None or isinstance(value, (str, bool))
            if not bounded(profiles):
                raise HTTPException(422, '结构资料超出尺寸、数量或嵌套限制。')
            if len(set(ids)) != len(ids) or any(x not in known for x in ids):
                raise HTTPException(422, '存在未提供结构资料的硬件，请先补充尺寸资料。')
            if request.action == 'selected' and not ids and not request.template:
                raise HTTPException(422, '请先选择至少一个有结构尺寸的硬件。')
            if request.action in {'analyze', 'revise'} and not request.message.strip() and not request.resolutionOptionId and not request.template:
                raise HTTPException(422, '请填写结构需求。')
            state = previous.get('design_state')
            if request.action in {'build', 'parameters', 'validate'} and not state and not previous.get('designSpec'):
                raise HTTPException(422, '当前版本没有可建模的参数草案。')
            if request.action == 'build' and previous.get('status') != 'confirmation':
                raise HTTPException(422, '请先确认需求并生成参数草案。')
            offline = request.action == 'selected' or bool(base and base.get('offline') and request.action in {'build', 'parameters', 'validate'})
            prompt = request.message.strip() if request.action in {'analyze', 'selected'} else base['prompt']
            if request.action == 'selected':
                prompt = '为选定硬件设计带盖矩形外壳'
            body = {'prompt': prompt, 'selectedHardwareIds': ids, 'customHardwareProfiles': profiles,
                'parameterOverrides': request.parameters, 'hardwareFaceOverrides': request.faces,
                'hardwareRotationOverrides': request.rotations,
                'currentRequirementAnalysis': previous if previous.get('status') == 'requirement_analysis' else None,
                'currentDesignState': state, 'draftDesignState': state,
                'latestUserMessage': request.message, 'userAnswers': [request.message] if request.message else [],
                'activeResolutionOptions': previous.get('resolution_options', []),
                'lastNeedsInput': previous if previous.get('status') == 'needs_input' else None,
                'resolutionOptionId': request.resolutionOptionId,
                'conversationContext': {'hasRequirementAnalysis': previous.get('status') == 'requirement_analysis',
                    'hasArtifact': previous.get('status') == 'artifact', 'hasDraft': previous.get('status') == 'confirmation'},
                'routeAction': 'confirm_requirement_analysis' if request.action == 'confirm' else ''}
            # Never trust a persisted task path or source code as an execution input.
            if state:
                body['currentDesignState'] = {**state, 'id': ''}
                body['draftDesignState'] = body['currentDesignState']
            job_id = uuid.uuid4().hex
            job_root = self.root / job_id
            job_root.mkdir(parents=True)
            standalone = request.designType == 'laser' or request.template or previous.get('designKind') or (not ids and request.action in {'analyze', 'revise'})
            if standalone:
                if request.template and ((request.template in {'plate', 'round-tag', 'panel-box', 'finger-box', 'rounded-box'}) != (request.designType == 'laser')):
                    raise HTTPException(422, '设计模板与当前模式不一致。')
                history = [v for v in reversed(workspace['versions']) if v.get('designType', 'model') == request.designType
                           and base and v['revision'] <= base['revision']]
                # A new template starts a new design. Never send later versions
                # or another channel when editing a selected historical branch.
                anchor = next((i for i in range(len(history) - 1, -1, -1) if history[i]['result'].get('designTemplate')), 0)
                history = history[anchor:]
                valid = next((v['result']['designSpec'] for v in reversed(history)
                              if v['result'].get('designSpec') and not v['result']['designSpec'].get('questions')
                              and (v['result']['designSpec'].get('drawing') or v['result']['designSpec'].get('solid'))), None)
                conversation = {'history': [{'request': v['result'].get('requestText') or v['prompt'],
                    'summary': v['result'].get('message', '')[:1200], 'questions': v['result'].get('questions', [])}
                    for v in history[-8:]], 'pendingQuestions': previous.get('questions', [])}
                if valid:
                    conversation['spec'] = valid
                result = await design_service.act(request, previous, settings, job_root, conversation)
                result = self.public_result(result, project_id, job_id, job_root)
                version = {'revision': workspace['revision'] + 1, 'createdAt': datetime.now(UTC).isoformat(), 'prompt': request.message or (base['prompt'] if base else result['title']),
                    'selectedIds': [], 'customProfiles': [], 'result': result, 'offline': bool(request.template or (base and base.get('offline') and request.action in {'build', 'parameters', 'validate'})),
                    'jobId': job_id, 'designType': request.designType, 'name': short_name(result['title'])}
                self.commit(project_id, version, request.message or result['title'], result.get('message') or result['title'])
                return self.get(project_id)
            project = self.repo.get(project_id)
            selected_hardware = {project['boardId'], *project['componentIds']}
            body['engineeringHardware'] = [{'componentId': item['componentId'], 'name': item['displayName']}
                for item in self.repo.skills.web_summaries() if item['componentId'] in selected_hardware]
            available = all(importlib.util.find_spec(x) is not None for x in ['cadquery', 'OCP'])
            result = await self.worker({'action': request.action, 'body': body, 'rootDir': str(job_root),
                'python': sys.executable, 'settings': settings, 'offline': offline, 'previousResult': previous,
                'environment': {'cadqueryAvailable': available, 'missingPythonPackages': [] if available else ['cadquery', 'OCP']}})
            if request.action == 'validate':
                # Validation must retain the existing asset references and artifact stage.
                result['status'] = previous['status']
            else:
                result = self.public_result(result, project_id, job_id, job_root)
            revision = workspace['revision'] + 1
            version = {'revision': revision, 'createdAt': datetime.now(UTC).isoformat(), 'prompt': prompt,
                'selectedIds': ids, 'customProfiles': profiles, 'result': result, 'offline': offline, 'jobId': job_id, 'designType': 'model',
                'name': short_name(result.get('title') or prompt)}
            labels = {'confirm': '确认需求，生成参数草案', 'build': '确认参数并生成真实模型', 'parameters': '应用尺寸与安装参数',
                'validate': '重新检查结构', 'selected': prompt}
            self.commit(project_id, version, request.message or labels.get(request.action, request.resolutionOptionId),
                result.get('message') or result.get('title') or '结构设计已完成本轮处理。')
            return self.get(project_id)

    def public_result(self, result: Any, project_id: str, job_id: str, job_root: Path) -> Any:
        if isinstance(result, dict):
            return {k: self.public_result(v, project_id, job_id, job_root) for k, v in result.items()
                    if k not in {'path', 'exportDir', 'rootDir', 'python', 'stdout', 'stderr', 'stack'}}
        if isinstance(result, list):
            return [self.public_result(v, project_id, job_id, job_root) for v in result]
        if isinstance(result, str) and result.startswith('/exports/'):
            return f'/api/projects/{project_id}/structure/assets/{job_id}/' + result.removeprefix('/exports/')
        if isinstance(result, str):
            return result.replace(str(job_root), '[结构产物目录]')
        return result

    def asset(self, project_id: str, job_id: str, result_id: str, filename: str) -> Path:
        if not re.fullmatch('[a-f0-9]{32}', job_id) or not re.fullmatch(r'ZW-PRODUCT-\d{8}-\d{6}(?:-\d{2})?', result_id) or filename not in FILES:
            raise HTTPException(404, '结构文件不存在。')
        # Only files explicitly referenced by this project's immutable artifact are exposed.
        workspace = self.get(project_id)
        url = f'/api/projects/{project_id}/structure/assets/{job_id}/{result_id}/{filename}'
        if not any(url in json.dumps(v['result'], ensure_ascii=False) for v in workspace['versions']):
            raise HTTPException(404, '结构文件未登记到当前项目。')
        target = self.root / job_id / 'exports' / result_id / filename
        if not target.resolve().is_relative_to(self.root) or target.is_symlink() or not target.is_file():
            raise HTTPException(404, '结构文件不存在。')
        return target


def structure_router(service: StructureService, settings) -> APIRouter:
    router = APIRouter()

    @router.get('/api/structure/catalog')
    def catalog():
        hardware = service.repo.skills.web_summaries()
        profiles = []
        for profile in service.catalog['profiles']:
            existing = next((h for h in hardware if h['componentId'].endswith('_' + profile['id'])), None)
            image = existing['media'][0]['url'] if existing and existing['media'] else ''
            if not image and profile.get('thumbnail_url', '').startswith('/assets/hardware/'):
                image = '/api/structure/media/' + profile['thumbnail_url'].rsplit('/', 1)[1]
            profiles.append({**profile, 'thumbnail_url': image, 'componentId': existing['componentId'] if existing else None})
        return {'profiles': profiles, 'cadqueryAvailable': all(importlib.util.find_spec(x) is not None for x in ['cadquery', 'OCP'])}

    @router.get('/api/structure/media/{name}')
    def profile_image(name: str):
        directory = CAD_ROOT / 'public/assets/hardware'
        if name not in {p.name for p in directory.iterdir() if p.is_file()}:
            raise HTTPException(404, '结构图片不存在。')
        return FileResponse(directory / name)

    @router.get('/api/projects/{project_id}/structure')
    def workspace(project_id: str):
        return service.get(project_id)

    @router.post('/api/projects/{project_id}/structure')
    async def action(project_id: str, body: StructureInput):
        return await service.act(project_id, body, settings())

    @router.get('/api/projects/{project_id}/structure/assets/{job_id}/{result_id}/{filename:path}')
    def asset(project_id: str, job_id: str, result_id: str, filename: str):
        path = service.asset(project_id, job_id, result_id, filename)
        return FileResponse(path, filename=path.name, headers={'Cache-Control': 'private, no-store'})

    return router
