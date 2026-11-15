"""Project definitions, tests and learning evidence over existing Artifact/Conversation.

No device actions. Every mutation is a bounded CAS append; observations are human reports.
"""
from __future__ import annotations
import base64
import hashlib
import json
import uuid
from typing import Literal
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException
from pydantic import Field, ValidationError
from zhangwen.artifacts.models import ArtifactPreview, ArtifactPreviewKind, ArtifactStatus
from zhangwen.llm.contracts import ChatMessage, ChatRole, ChatMessageStatus
from .models import Boundary
from .workflow_models import Baseline, CaseContent, Checkpoint, CodeChoice, CodeReference, Conditions, Definition, DefinitionVersion, Evidence, EvidenceContent, Message, Observation, Reflection, CaseSuggestion, ReflectionContent, StructureReference, TestCase, TestRun, digest, structure_digest

def now():
    return datetime.now(UTC).isoformat()

def read(conn, pid):
    row = conn.execute('SELECT v.preview_json FROM artifacts a JOIN artifact_versions v ON a.current_version_id=v.id WHERE a.id=? AND a.project_id=?', ('zhangwen_workflow_' + pid, pid)).fetchone()
    return Checkpoint.model_validate_json(json.loads(row[0])['code']) if row else Checkpoint()

def load(repo, pid):
    repo.get(pid)
    with repo.connect() as conn:
        return read(conn, pid)

def insert(repo, conn, pid, value, new_messages=()):
    value = Checkpoint.model_validate(value.model_dump())
    aid = 'zhangwen_workflow_' + pid
    vid = 'artifact_version_' + uuid.uuid4().hex
    stamp = now()
    text = value.model_dump_json()
    preview = ArtifactPreview(kind=ArtifactPreviewKind.CODE, code=text, language='json', summary='项目定义、测试观察与学习证据；实物结论由用户记录。')
    conn.execute("INSERT INTO artifacts(id,project_id,title,kind,status,source_agent_id,current_version_id,created_at,updated_at)\n        VALUES(?,?,'项目学习与验收','CODE','DRAFT','zhangwen-workflow',?,?,?)\n        ON CONFLICT(id) DO UPDATE SET current_version_id=excluded.current_version_id,updated_at=excluded.updated_at", (aid, pid, vid, stamp, stamp))
    version = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?', (aid,)).fetchone()[0]
    conn.execute("INSERT INTO artifact_versions(id,artifact_id,project_id,version,status,mime_type,preview_json,dependencies_json,source_entity_type,source_entity_id,checksum,created_at)\n        VALUES(?,?,?,?,'DRAFT','application/json',?,'[]','zhangwen_workflow',?,?,?)", (vid, aid, pid, version, preview.model_dump_json(), uuid.uuid4().hex, hashlib.sha256(text.encode()).hexdigest(), stamp))
    repo.artifacts._apply_artifact_context(conn, artifact_id=aid, version_id=vid, project_id=pid, source_agent_id='zhangwen-workflow', status=ArtifactStatus.DRAFT)
    if new_messages:
        cid = conn.execute('SELECT id FROM conversations WHERE project_id=? ORDER BY created_at LIMIT 1', (pid,)).fetchone()[0]
        for m in new_messages:
            item = ChatMessage(id='msg_' + uuid.uuid4().hex, role=ChatRole(m.role), content=m.content, status=ChatMessageStatus.COMPLETED, createdAt=m.createdAt, updatedAt=m.createdAt, metadata={'workflow': True, 'portableMessageId': m.id})
            repo.projects._insert_message(conn, cid, pid, item)

def confirmed(value):
    return next((d for d in reversed(value.definitions) if d.confirmed), None)

def structure_references(repo, pid, legacy=False):
    with repo.connect() as conn:
        rows = conn.execute('SELECT preview_json FROM artifact_versions WHERE artifact_id=? ORDER BY version DESC', (repo.artifact_id(pid, 'structure'),)).fetchall()
    result = []
    for row in rows:
        v = json.loads(json.loads(row[0])['code'])
        if v['result'].get('status') != 'artifact':
            continue
        stable = json.loads(json.dumps(v['result']).replace('/api/projects/' + pid + '/', '/api/projects/__PROJECT__/'))
        result.append(StructureReference(revision=v['revision'], checksum=(digest if legacy else structure_digest)(stable), name=(v.get('name') or v['result'].get('title') or '结构设计')[:200]))
    return result

def same_structure(repo, pid, previous, current, legacy=None):
    if previous == current:
        return True
    if not previous or not current or previous.revision != current.revision:
        return False
    legacy = legacy if legacy is not None else {s.revision: s for s in structure_references(repo, pid, legacy=True)}
    return previous == legacy.get(current.revision)

def code_references(repo, pid, project):
    from . import lua_coding
    values = []
    mode = 'micropython'
    current = project['revision']
    if project.get('programmingMode') == 'chat-coding':
        lua = lua_coding.load(repo, pid)
        mode = 'lua' if lua.accepted else 'claw'
        values.extend((CodeReference(mode='lua', revision=v.revision, checksum=v.checksum, name='Lua程序') for v in reversed(lua.versions) if v.source == 'saved'))
        current = lua.accepted if mode == 'lua' else project['revision']
    values.extend((CodeReference(mode='claw' if v.get('programmingMode') == 'chat-coding' else 'micropython', revision=v['revision'], checksum=v['checksum'], name=v.get('name', '程序')) for v in repo.versions(pid) if v.get('source') != 'ai' and v.get('boardId', '') == project['boardId'] and v['code'].strip()))
    selected = next((v for v in values if v.mode == mode and v.revision == current), CodeReference(mode='none', revision=None, checksum='', name='未关联程序'))
    return (selected, values)

def baseline(repo, pid, value):
    project = repo.get(pid)
    modules = []
    for cid in [project['boardId'], *project['componentIds']]:
        if not cid:
            continue
        d = repo.skills.get_active_by_component_id(cid)
        modules.append({'id': cid, 'name': d.displayName, 'revision': d.revision})
    code, codes = code_references(repo, pid, project)
    structures = structure_references(repo, pid)
    definition = confirmed(value)
    raw = {'boardId': project['boardId'], 'boardName': next((m['name'] for m in modules if m['id'] == project['boardId']), '未选择主控'), 'modules': sorted(modules, key=lambda m: m['id']), 'definitionRevision': definition.revision if definition else None, 'code': code.model_dump(), 'structure': structures[0].model_dump() if structures else None, 'conditions': value.conditions.model_dump()}
    raw['controllers'] = controller_baselines(repo, pid, raw)
    return (Baseline(**raw, fingerprint=digest(raw)), codes, structures)

def controller_baselines(repo, pid, root):
    from . import channels
    from .programming_modes import board_mode
    checkpoint = channels.load(repo, pid)
    result = [dict(id='project', name=checkpoint.mainName or root['boardName'], boardId=root['boardId'], modules=root['modules'], code=root['code'])]
    for channel in checkpoint.channels:
        modules = []
        for cid in [channel.boardId, *channel.componentIds]:
            detail = repo.skills.get_active_by_component_id(cid)
            modules.append(dict(id=cid, name=detail.displayName, revision=detail.revision))
        version = channel.versions[-1]
        mode = 'micropython'
        if board_mode(repo, channel.boardId) == 'chat-coding':
            mode = 'claw'
            if channel.mosaico and channel.mosaico.source == 'local':
                mode = 'lua'
                version = next((v for v in channel.mosaico.lua.versions if v.revision == channel.mosaico.lua.accepted), None)
        code = dict(mode=mode if version else 'none', revision=version.revision if version else None, checksum=version.checksum if version else '', name='Lua程序' if mode == 'lua' else '主控程序')
        result.append(dict(id=channel.id, name=channel.name, boardId=channel.boardId, modules=sorted(modules, key=lambda m: m['id']), code=code))
    return result

def validate_case_scope(repo, pid, case, controllers=None):
    if controllers is None:
        controllers = baseline(repo, pid, load(repo, pid))[0].controllers or []
    if len(set(case.controllerIds)) != len(case.controllerIds) or set(case.controllerIds) - {c.id for c in controllers}:
        raise HTTPException(422, f'测试“{case.title}”：关联主控不存在或重复，请重新选择。')
    selected = [c for c in controllers if not case.controllerIds or c.id in case.controllerIds]
    if case.componentId and (not any((case.componentId in [m.id for m in c.modules] for c in selected))):
        raise HTTPException(422, f'测试“{case.title}”：关联器件 {case.componentId} 已移出项目或不在所选主控中，请重新选择或明确设为整机。')

def stale_reasons(run, case, current, equivalent_structure=False):
    previous = run.baseline
    reasons = []
    if run.test.revision != case.revision:
        reasons.append('测试要求已修改')
    if previous.definitionRevision != current.definitionRevision:
        reasons.append('已确认需求已更新')
    if not case.controllerIds or 'project' in case.controllerIds:
        if previous.boardId != current.boardId or previous.modules != current.modules:
            reasons.append('硬件选择或资料已更新')
        if (previous.code.mode, previous.code.checksum) != (current.code.mode, current.code.checksum):
            reasons.append('当前程序已改变')
    if current.controllers:
        scope = set(case.controllerIds) or {c.id for c in current.controllers} | {c.id for c in previous.controllers or []}
        old = {c.id: c for c in previous.controllers or []}
        new = {c.id: c for c in current.controllers}
        if previous.controllers is None and (len(current.controllers) > 1 or case.controllerIds):
            reasons.append('历史观察未记录多主控程序，请按当前主控重新核对')
        elif previous.controllers is not None:
            for cid in sorted(scope):
                a, b = (old.get(cid), new.get(cid))
                name = b.name if b else a.name if a else cid
                if a is None or b is None or a.boardId != b.boardId or (a.modules != b.modules):
                    reasons.append(name + '：主控或器件资料已更新')
                elif (a.code.mode, a.code.checksum) != (b.code.mode, b.code.checksum):
                    reasons.append(name + '：程序已改变')
    fields = ['firmware', 'wiring', 'power'] + (['assembly'] if case.stage != 'module' else [])
    if any((getattr(previous.conditions, k) != getattr(current.conditions, k) for k in fields)):
        reasons.append('测试条件已改变')
    if case.stage != 'module' and previous.structure != current.structure and (not equivalent_structure):
        reasons.append('结构版本已改变')
    return reasons

def view(repo, pid, value=None):
    from .workflow_review import records
    with repo.lock:
        value = value or load(repo, pid)
        current, codes, structures = baseline(repo, pid, value)
        states = []
        legacy_structures = {s.revision: s for s in structure_references(repo, pid, legacy=True)} if any((r.baseline.structure for r in value.runs)) else {}
        for case in value.cases:
            run = next((r for r in reversed(value.runs) if r.test.id == case.id), None)
            equivalent = bool(run and same_structure(repo, pid, run.baseline.structure, current.structure, legacy_structures))
            reasons = stale_reasons(run, case, current, equivalent) if run else []
            states.append({'id': case.id, 'status': 'stale' if reasons else run.result if run else 'unrecorded', 'reasons': reasons, 'runId': run.id if run else None})
        return {'checkpoint': value.model_dump(), 'current': current.model_dump(), 'codeVersions': [v.model_dump() for v in codes], 'structureVersions': [v.model_dump() for v in structures], 'caseStates': states, 'reviewRecords': records(value.model_dump())}

def mutate(repo, pid, expected, apply):
    repo.get(pid)
    try:
        with repo.lock, repo.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            value = read(conn, pid)
            if value.revision != expected:
                raise HTTPException(409, '项目记录已更新。草稿保留，请读取最新记录后核对再保存。')
            count = len(value.messages)
            apply(value)
            value.revision += 1
            insert(repo, conn, pid, value, value.messages[count:])
    except ValidationError as exc:
        raise HTTPException(422, '记录未通过校验：' + str(exc.errors()[0]['msg'])[:250]) from exc
    return view(repo, pid, value)

def context(repo, pid, query=''):
    from .shared_project import text
    return text(repo, pid, query=query)

class Revision(Boundary):
    expectedRevision: int = Field(ge=0, strict=True)

class SaveDefinition(Revision):
    definition: Definition
    confirmed: bool = False
    changeId: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')

class SaveConditions(Revision):
    conditions: Conditions

class SaveCase(Revision, CaseContent):
    definitionRevision: int | None = Field(default=None, ge=1, strict=True)
    id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    active: bool = True

class AddCases(Revision):
    tests: list[CaseSuggestion] = Field(min_length=1, max_length=30)
    mode: Literal['merge', 'replace'] = 'merge'

class SaveRun(Revision, Observation):
    caseId: str = Field(pattern='^[a-f0-9]{32}$')
    code: CodeChoice
    structureRevision: int | None = Field(default=None, ge=1, strict=True)
    expectedBaseline: str = Field(pattern='^[a-f0-9]{64}$')

class SaveEvidence(Revision, EvidenceContent):
    pass

class SaveReflection(Revision, ReflectionContent):
    pass

class Guide(Revision):
    message: str = Field(min_length=1, max_length=4000)
    role: str = Field(pattern='^(student|teacher)$')
    changeId: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    purpose: Literal['guide', 'review'] = 'guide'

def router(repo, settings):
    router = APIRouter(prefix='/api/projects/{pid}/workflow')

    @router.get('')
    def get(pid: str):
        return view(repo, pid)

    @router.get('/shared')
    def shared(pid: str):
        from .shared_project import snapshot
        return snapshot(repo, pid)

    @router.post('/definition')
    def definition(pid: str, request: SaveDefinition):
        from .workflow_changes import save_definition

        def apply(value):
            save_definition(repo, pid, value, request)
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.put('/conditions')
    def conditions(pid: str, request: SaveConditions):

        def apply(value):
            value.conditions = request.conditions
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/cases')
    def cases(pid: str, request: SaveCase):

        def apply(value):
            project = repo.get(pid)
            old = next((c for c in value.cases if c.id == request.id), None)
            if request.id and (not old):
                raise HTTPException(404, '测试项不存在。')
            if request.active:
                validate_case_scope(repo, pid, request)
            new = TestCase(**request.model_dump(exclude={'expectedRevision', 'id', 'definitionRevision'}), id=request.id or uuid.uuid4().hex, revision=old.revision + 1 if old else 1)
            new.definitionRevision = confirmed(value).revision if confirmed(value) else None
            if old:
                value.cases[value.cases.index(old)] = new
            else:
                value.cases.append(new)
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/runs')
    def runs(pid: str, request: SaveRun):

        def apply(value):
            case = next((c for c in value.cases if c.id == request.caseId and c.active), None)
            if not case:
                raise HTTPException(422, '请选择当前启用的测试项。')
            current, codes, structures = baseline(repo, pid, value)
            validate_case_scope(repo, pid, case, current.controllers)
            if current.fingerprint != request.expectedBaseline:
                raise HTTPException(409, '程序、结构或硬件条件已更新。请读取最新条件并核对本次实际使用的版本。')
            code = next((c for c in codes if c.mode == request.code.mode and c.revision == request.code.revision), None)
            if request.code.mode == 'none' and request.code.revision is None:
                code = CodeReference(mode='none', revision=None, checksum='', name='未关联程序')
            if code is None:
                raise HTTPException(422, '程序版本不属于当前项目的已保存版本。')
            structure = next((s for s in structures if s.revision == request.structureRevision), None)
            if request.structureRevision is not None and structure is None:
                raise HTTPException(422, '结构版本不存在或尚未生成产物。')
            raw = {**current.model_dump(exclude={'fingerprint'}), 'code': code.model_dump(), 'structure': structure.model_dump() if structure else None}
            raw['controllers'] = [{**c, 'code': code.model_dump()} if c['id'] == 'project' else c for c in raw.get('controllers') or []]
            value.runs.append(TestRun(**request.model_dump(exclude={'expectedRevision', 'caseId', 'code', 'structureRevision', 'expectedBaseline'}), id=uuid.uuid4().hex, createdAt=now(), test=case.model_copy(deep=True), baseline=Baseline(**raw, fingerprint=digest(raw))))
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/case-batch')
    def add_cases(pid: str, request: AddCases):
        counts = dict(added=0, updated=0, retired=0, unchanged=0)

        def apply(value):
            seen = set()
            controllers = baseline(repo, pid, value)[0].controllers or []

            def identity(c):
                return (c.stage, tuple(sorted(c.controllerIds)), c.componentId, c.title.strip())
            for case in request.tests:
                validate_case_scope(repo, pid, case, controllers)
                matches = [c for c in value.cases if c.active and identity(c) == identity(case)]
                old = next((c for c in value.cases if c.id == case.id), None) if case.id else matches[0] if len(matches) == 1 else None
                if case.id and (not old):
                    raise HTTPException(422, '测试项已不存在，请重新核对清单。')
                key = old.id if old else identity(case)
                if key in seen:
                    raise HTTPException(422, f'测试“{case.title}”在本次清单中重复，请合并后保存。')
                seen.add(key)
                data = case.model_dump(exclude={'id'})
                if old and old.active and (old.definitionRevision == (confirmed(value).revision if confirmed(value) else None)) and all((getattr(old, k) == v for k, v in data.items())):
                    counts['unchanged'] += 1
                    continue
                new = TestCase(**data, id=old.id if old else uuid.uuid4().hex, revision=old.revision + 1 if old else 1, definitionRevision=confirmed(value).revision if confirmed(value) else None)
                if old:
                    value.cases[value.cases.index(old)] = new
                    counts['updated'] += 1
                else:
                    value.cases.append(new)
                    seen.add(new.id)
                    counts['added'] += 1
            if request.mode == 'replace':
                for c in value.cases:
                    if c.active and c.id not in seen:
                        c.active = False
                        c.revision += 1
                        counts['retired'] += 1
        result = mutate(repo, pid, request.expectedRevision, apply)
        result['caseBatch'] = counts
        return result

    @router.post('/evidence')
    def evidence(pid: str, request: SaveEvidence):

        def apply(value):
            value.evidence.append(Evidence(**request.model_dump(exclude={'expectedRevision'}), id=uuid.uuid4().hex, createdAt=now(), checksum=digest(base64.b64decode(request.content))))
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/reflection')
    def reflection(pid: str, request: SaveReflection):

        def apply(value):
            value.reflections.append(Reflection(**request.model_dump(exclude={'expectedRevision'}), revision=len(value.reflections) + 1, createdAt=now()))
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/guide')
    async def guide(pid: str, request: Guide):
        from .workflow_ai import propose
        from . import workflow_review
        from .endpoints import configured
        from .shared_project import snapshot
        with repo.lock:
            state = view(repo, pid)
            state['sharedProject'] = snapshot(repo, pid, state)
            from .references import list_references
            state['projectReferences'] = list_references(repo, pid)
        if state['checkpoint']['revision'] != request.expectedRevision:
            raise HTTPException(409, '项目记录已更新，请读取最新记录再提问。')
        if request.changeId and request.purpose == 'review':
            raise HTTPException(422, '检查成果与整理目标请分别进行。')
        if request.changeId:
            from .workflow_changes import pending_change
            change = pending_change(load(repo, pid), request.changeId)
            if change.baseDefinitionRevision != state['current']['definitionRevision']:
                raise HTTPException(409, '需求已更新，请先按最新需求重新整理此变更。')
            state['activeChange'] = change.model_dump()
        if len(state['checkpoint']['messages']) >= 100:
            raise HTTPException(422, '本项目已有50轮学习对话，请先导出归档，再新建项目继续。手工记录仍可保存。')
        config = settings()
        if request.purpose == 'review':
            with repo.lock:
                if view(repo, pid)['current'] != state['current']:
                    raise HTTPException(409, '作品已更新，请刷新后再检查。')
                state['reviewSources'] = workflow_review.sources(repo, pid, state)
            proposal = await propose(request.message, request.role, state, config) if configured(config) else workflow_review.record_review(state)
            if proposal.review is None:
                raise HTTPException(502, '学习设计师没有返回完整的成果检查，原记录保留。')
            proposal.question = None
            proposal.definition = None
            proposal.tests = []
            proposal.review.source = workflow_review.source(state, now(), 'ai' if configured(config) else 'records')
        else:
            proposal = await propose(request.message, request.role, state, config)
            proposal.review = None
        stamp = now()

        def apply(value):
            if baseline(repo, pid, value)[0].model_dump() != state['current']:
                raise HTTPException(409, '处理期间作品已有更改，请刷新记录后重新核对。原结果未覆盖。')
            value.messages.extend([Message(id=uuid.uuid4().hex, role='user', content=request.message, createdAt=stamp), Message(id=uuid.uuid4().hex, role='assistant', content=proposal.model_dump_json(), createdAt=stamp)])
        return mutate(repo, pid, request.expectedRevision, apply)
    from .workflow_changes import add_routes
    add_routes(router, repo)
    from .learning_documents import add_routes as document_routes
    document_routes(router, repo, settings)
    return router

def validate_snapshot(checkpoint, snapshot):
    """Validate project-owned references before any imported files are materialized."""
    if not checkpoint:
        return
    codes = {('claw' if v.programmingMode == 'chat-coding' else 'micropython', v.revision): v.checksum for v in snapshot.versions if v.source == 'saved'}
    if snapshot.luaCoding:
        codes.update({('lua', v.revision): v.checksum for v in snapshot.luaCoding.versions if v.source == 'saved'})
    structures = {v['revision']: {digest(v['result']), structure_digest(v['result'])} for v in snapshot.structure.versions} if snapshot.structure else {}
    references = [(run.baseline.code, run.baseline.structure) for run in checkpoint.runs]
    for change in checkpoint.changes:
        references.append((change.baseline.code, change.baseline.structure))
        references.extend(((task.code, task.structure) for task in change.tasks))
    from .workflow_models import Proposal
    for message in checkpoint.messages:
        if message.role == 'assistant':
            p = Proposal.model_validate_json(message.content)
            if p.review and p.review.source:
                references.append((p.review.source.baseline.code, p.review.source.baseline.structure))
    for c, s in references:
        if c is None:
            pass
        elif c.mode == 'none':
            if c.revision is not None or c.checksum:
                raise ValueError('未关联程序的记录含非法版本。')
        elif codes.get((c.mode, c.revision)) != c.checksum:
            raise ValueError('测试程序来源与项目历史不一致。')
        if s and s.checksum not in structures.get(s.revision, set()):
            raise ValueError('测试结构来源与项目历史不一致。')
    channel_checkpoint = getattr(snapshot, 'developmentChannels', None)
    channel_map = {c.id: c for c in channel_checkpoint.channels} if channel_checkpoint else {}
    baselines = [r.baseline for r in checkpoint.runs] + [c.baseline for c in checkpoint.changes]
    for message in checkpoint.messages:
        if message.role == 'assistant':
            proposal = Proposal.model_validate_json(message.content)
            if proposal.review and proposal.review.source:
                baselines.append(proposal.review.source.baseline)
    for b in baselines:
        for controller in b.controllers or []:
            code = controller.code
            if controller.id == 'project':
                valid = codes
            else:
                ch = channel_map.get(controller.id)
                if ch is None:
                    raise ValueError('测试主控不属于当前项目。')
                valid = {('claw' if v.programmingMode == 'chat-coding' else 'micropython', v.revision): v.checksum for v in ch.versions}
                if ch.mosaico:
                    valid.update({('lua', v.revision): v.checksum for v in ch.mosaico.lua.versions if v.source == 'saved'})
            if code.mode == 'none':
                if code.revision is not None or code.checksum:
                    raise ValueError('主控未关联程序却含版本。')
            elif valid.get((code.mode, code.revision)) != code.checksum:
                raise ValueError('测试主控程序来源与项目历史不一致。')
