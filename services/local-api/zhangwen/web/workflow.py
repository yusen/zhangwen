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
from .workflow_models import Baseline, CaseContent, Checkpoint, CodeChoice, CodeReference, Conditions, Definition, DefinitionVersion, Evidence, EvidenceContent, Message, Observation, Reflection, ReflectionContent, StructureReference, TestCase, TestRun, digest, structure_digest

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
    return (Baseline(**raw, fingerprint=digest(raw)), codes, structures)

def stale_reasons(run, case, current, equivalent_structure=False):
    previous = run.baseline
    reasons = []
    if run.test.revision != case.revision:
        reasons.append('测试要求已修改')
    if previous.definitionRevision != current.definitionRevision:
        reasons.append('已确认需求已更新')
    if previous.boardId != current.boardId or previous.modules != current.modules:
        reasons.append('硬件选择或资料已更新')
    if (previous.code.mode, previous.code.checksum) != (current.code.mode, current.code.checksum):
        reasons.append('当前程序已改变')
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

def context(repo, pid):
    from .shared_project import text
    return text(repo, pid)

class Revision(Boundary):
    expectedRevision: int = Field(ge=0, strict=True)

class SaveDefinition(Revision):
    definition: Definition
    confirmed: bool = False
    changeId: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')

class SaveConditions(Revision):
    conditions: Conditions

class SaveCase(Revision, CaseContent):
    id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    active: bool = True

class AddCases(Revision):
    tests: list[CaseContent] = Field(min_length=1, max_length=30)

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
            if request.componentId and request.componentId not in [project['boardId'], *project['componentIds']] and (not (old and (not request.active) and (request.componentId == old.componentId))):
                raise HTTPException(422, '测试模块不在当前项目中，请先保存硬件选择。')
            new = TestCase(**request.model_dump(exclude={'expectedRevision', 'id'}), id=request.id or uuid.uuid4().hex, revision=old.revision + 1 if old else 1)
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
            if case.componentId and case.componentId not in [m.id for m in current.modules]:
                raise HTTPException(422, '这个测试项的器件已移出项目，请修改关联器件或停用测试项。')
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
            value.runs.append(TestRun(**request.model_dump(exclude={'expectedRevision', 'caseId', 'code', 'structureRevision', 'expectedBaseline'}), id=uuid.uuid4().hex, createdAt=now(), test=case.model_copy(deep=True), baseline=Baseline(**raw, fingerprint=digest(raw))))
        return mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/case-batch')
    def add_cases(pid: str, request: AddCases):

        def apply(value):
            p = repo.get(pid)
            for case in request.tests:
                if case.componentId and case.componentId not in [p['boardId'], *p['componentIds']]:
                    raise HTTPException(422, '测试模块不在当前项目中。')
                value.cases.append(TestCase(**case.model_dump(), id=uuid.uuid4().hex, revision=1))
        return mutate(repo, pid, request.expectedRevision, apply)

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
                raise HTTPException(502, '造物统筹师没有返回完整的成果检查，原记录保留。')
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
