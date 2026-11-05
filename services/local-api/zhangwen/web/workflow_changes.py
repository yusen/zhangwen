"""Explicit requirement handoffs in the existing workflow Artifact, with no device tools."""
import uuid
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from .models import Boundary
from .workflow_models import ChangeTask, CodeChoice, Definition, DefinitionVersion, RequirementChange


class Revision(Boundary):
    expectedRevision: int = Field(ge=0, strict=True)


class ProposeChange(Revision):
    sourceMode: Literal['engineer', 'structure', 'learning']
    summary: str = Field(min_length=1, max_length=2000)


class TaskUpdate(Revision):
    status: Literal['working', 'delivered', 'not_needed']
    note: str = Field(default='', max_length=1500)
    code: CodeChoice | None = None
    structureRevision: int | None = Field(default=None, ge=1, strict=True)


class Collaborate(Revision):
    roles: list[Literal['engineer', 'structure']] = Field(max_length=2)


def find_change(value, cid):
    change = next((c for c in value.changes if c.id == cid), None)
    if change is None: raise HTTPException(404, '需求变更不存在。')
    return change


def pending_change(value, cid):
    change = find_change(value, cid)
    if change.status != 'proposed': raise HTTPException(409, '这项变更已经处理，请读取最新记录。')
    return change


def save_definition(repo, pid, value, request):
    from . import workflow as w
    old = w.confirmed(value)
    change = pending_change(value, request.changeId) if request.changeId else None
    if change and change.baseDefinitionRevision != (old.revision if old else None):
        raise HTTPException(409, '此变更基于旧需求，请先按最新需求重新整理，原草稿保留。')
    before = {k: getattr(old, k) for k in Definition.model_fields} if old else None
    changed = before != request.definition.model_dump()
    if request.confirmed and old and not changed: raise HTTPException(422, '项目定义与当前已确认需求一致，请修改后再确认；原需求与任务保持。')
    baseline = w.baseline(repo, pid, value)[0] if request.confirmed else None
    stamp = w.now()
    version = DefinitionVersion(**request.definition.model_dump(), confirmed=request.confirmed,
                                revision=len(value.definitions) + 1, createdAt=stamp)
    value.definitions.append(version)
    if not request.confirmed or baseline is None: return
    if change is None:
        labels = {'problem':'问题', 'audience':'使用场景', 'goal':'目标', 'behavior':'动作规则', 'parameters':'参数',
                  'exceptionPolicy':'异常策略', 'constraints':'约束', 'criteria':'验收条件'}
        summary = '项目目标已确定' if before is None else '项目目标更新：' + '、'.join(labels[k] for k in labels if before[k] != getattr(request.definition, k))
        change = RequirementChange(id=uuid.uuid4().hex, createdAt=stamp, sourceMode='learning', summary=summary,
                                   baseDefinitionRevision=old.revision if old else None, baseline=baseline)
        value.changes.append(change)
    change.definitionRevision = version.revision
    change.status = 'confirmed'
    change.tasks = []
    change.collaborationDecided = False


def add_routes(router, repo):
    from . import workflow as w

    @router.post('/changes')
    def propose(pid: str, request: ProposeChange):
        def apply(value):
            if not request.summary.strip(): raise HTTPException(422, '请填写需求变更。')
            baseline = w.baseline(repo, pid, value)[0]
            value.changes.append(RequirementChange(id=uuid.uuid4().hex, createdAt=w.now(), sourceMode=request.sourceMode,
                summary=request.summary.strip(), baseDefinitionRevision=baseline.definitionRevision, baseline=baseline))
        return w.mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/changes/{cid}/rebase')
    def rebase(pid: str, cid: str, request: Revision):
        def apply(value):
            change = pending_change(value, cid)
            change.baseline = w.baseline(repo, pid, value)[0]
            change.baseDefinitionRevision = change.baseline.definitionRevision
        return w.mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/changes/{cid}/cancel')
    def cancel(pid: str, cid: str, request: Revision):
        def apply(value): pending_change(value, cid).status = 'cancelled'
        return w.mutate(repo, pid, request.expectedRevision, apply)

    @router.put('/changes/{cid}/tasks/{role}')
    def update_task(pid: str, cid: str, role: Literal['engineer', 'structure'], request: TaskUpdate):
        def apply(value):
            change = find_change(value, cid)
            current, codes, structures = w.baseline(repo, pid, value)
            if change.status != 'confirmed' or change.definitionRevision != current.definitionRevision:
                raise HTTPException(409, '这项变更已结束或需求已更新，请处理最新需求的任务。')
            if role not in {t.role for t in change.tasks}: raise HTTPException(422, '你还没有选择请这位伙伴处理。')
            code = None; structure = None
            if request.status == 'delivered':
                if role == 'engineer':
                    if request.code is None or request.structureRevision is not None: raise HTTPException(422, '请选择本项目已保存的程序版本。')
                    code = next((c for c in codes if c.mode == request.code.mode and c.revision == request.code.revision), None)
                    if code is None or code != current.code or code.checksum == change.baseline.code.checksum: raise HTTPException(422, '请选择当前已保存且不同于变更前的程序；无需修改时请说明依据。')
                else:
                    if request.code is not None: raise HTTPException(422, '结构任务只能关联结构版本。')
                    structure = next((s for s in structures if s.revision == request.structureRevision), None)
                    if structure is None or structure != current.structure or change.baseline.structure and w.same_structure(repo,pid,change.baseline.structure,structure):
                        raise HTTPException(422, '请选择变更后已生成的结构版本；无需修改时请说明依据。')
            elif request.code is not None or request.structureRevision is not None: raise HTTPException(422, '仅交付时关联产物。')
            if request.status == 'not_needed' and not request.note.strip(): raise HTTPException(422, '请说明此角色无需调整的依据。')
            item = ChangeTask(role=role, status=request.status, note=request.note.strip(), code=code, structure=structure, updatedAt=w.now())
            value.changes[value.changes.index(change)].tasks = [item if t.role == role else t for t in change.tasks]
        return w.mutate(repo, pid, request.expectedRevision, apply)

    @router.put('/changes/{cid}/collaboration')
    def collaborate(pid: str, cid: str, request: Collaborate):
        def apply(value):
            change = find_change(value, cid)
            if len(set(request.roles)) != len(request.roles): raise HTTPException(422, '协作伙伴不能重复。')
            if change.status != 'confirmed' or change.definitionRevision != w.baseline(repo, pid, value)[0].definitionRevision:
                raise HTTPException(409, '请为当前目标选择协作伙伴。')
            if any(t.role not in request.roles and t.status != 'pending' for t in change.tasks):
                raise HTTPException(409, '这位伙伴已有处理记录，请保留该记录，或确认新的目标后重新安排。')
            previous = {t.role: t for t in change.tasks}
            change.tasks = [previous.get(r) or ChangeTask(role=r, updatedAt=w.now()) for r in request.roles]
            change.collaborationDecided = True
        return w.mutate(repo, pid, request.expectedRevision, apply)

    @router.post('/changes/{cid}/complete')
    def complete(pid: str, cid: str, request: Revision):
        def apply(value):
            change = find_change(value, cid)
            current = w.baseline(repo, pid, value)[0]
            if change.status != 'confirmed' or change.definitionRevision != current.definitionRevision:
                raise HTTPException(409, '请对当前已确认需求完成验收。')
            if not change.collaborationDecided: raise HTTPException(422, '请先选择要不要请伙伴协作。')
            if any(t.status not in {'delivered', 'not_needed'} for t in change.tasks): raise HTTPException(422, '请先完成已选择的协作，或说明无需调整。')
            for task in change.tasks:
                if task.code and task.code != current.code or task.structure and not w.same_structure(repo,pid,task.structure,current.structure):
                    raise HTTPException(409, '当前产物与交付版本不同，请重新核对角色交付。')
            cases = [c for c in value.cases if c.active]
            runs = [next((r for r in reversed(value.runs) if r.test.id == case.id), None) for case in cases]
            if not cases or any(r is None or r.result != 'passed' or w.stale_reasons(r, c, current,w.same_structure(repo,pid,r.baseline.structure,current.structure)) for c, r in zip(cases, runs)):
                raise HTTPException(422, '当前需求的启用测试仍有未测、未通过或需复测项，请先保存实际观察。')
            change.status = 'completed'; change.completedAt = w.now()
            change.verificationRunIds = [r.id for r in runs]
        return w.mutate(repo, pid, request.expectedRevision, apply)
