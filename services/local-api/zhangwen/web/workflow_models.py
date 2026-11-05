"""Bounded project learning records. Observations are user assertions, not device proof."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator
from .models import Boundary


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def structure_digest(value):
    """JSON numbers retain their value when a browser serializes 90.0 as 90."""
    def canonical(item):
        if isinstance(item, dict): return {k: canonical(v) for k, v in item.items()}
        if isinstance(item, list): return [canonical(v) for v in item]
        if isinstance(item, float) and item.is_integer(): return int(item)
        return item
    return digest(canonical(value))


class Definition(Boundary):
    problem: str = Field(default='', max_length=1500)
    audience: str = Field(default='', max_length=500)
    goal: str = Field(default='', max_length=1500)
    behavior: str = Field(default='', max_length=2000)
    parameters: str = Field(default='', max_length=1000)
    exceptionPolicy: str = Field(default='', max_length=1000)
    constraints: str = Field(default='', max_length=1500)
    criteria: list[str] = Field(default_factory=list, max_length=30)

    @field_validator('criteria')
    @classmethod
    def items(cls, values):
        if any(not v.strip() or len(v) > 500 for v in values): raise ValueError('验收条件不能为空，每条最多500字。')
        return values


class DefinitionVersion(Definition):
    revision: int = Field(ge=1, strict=True)
    createdAt: str
    confirmed: bool

    @model_validator(mode='after')
    def complete(self):
        datetime.fromisoformat(self.createdAt)
        if self.confirmed and (not self.goal.strip() or not self.behavior.strip() or not self.criteria):
            raise ValueError('确认前请填写项目目标、动作规则和至少一条验收条件。')
        return self


class Conditions(Boundary):
    firmware: str = Field(default='', max_length=1000)
    wiring: str = Field(default='', max_length=2000)
    power: str = Field(default='', max_length=1000)
    assembly: str = Field(default='', max_length=1500)


class CaseContent(Boundary):
    title: str = Field(min_length=1, max_length=100)
    stage: Literal['module', 'system', 'assembly']
    componentId: str = Field(default='', max_length=150)
    procedure: str = Field(min_length=1, max_length=1500)
    expected: str = Field(min_length=1, max_length=1500)

    @field_validator('title', 'procedure', 'expected')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('测试名称、步骤和预期结果均须填写。')
        return value.strip()


class TestCase(CaseContent):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    revision: int = Field(ge=1, strict=True)
    active: bool = True


class CodeChoice(Boundary):
    mode: Literal['micropython', 'lua', 'idea', 'claw', 'none']
    revision: int | None = Field(default=None, ge=1, strict=True)


class CodeReference(CodeChoice):
    checksum: str = Field(max_length=64)
    name: str = Field(max_length=200)


class StructureReference(Boundary):
    revision: int = Field(ge=1, strict=True)
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    name: str = Field(max_length=200)


class Module(Boundary):
    id: str = Field(max_length=150)
    name: str = Field(max_length=300)
    revision: str = Field(max_length=64)


class Baseline(Boundary):
    boardId: str = Field(max_length=150)
    boardName: str = Field(max_length=300)
    modules: list[Module] = Field(max_length=33)
    definitionRevision: int | None = Field(default=None, ge=1, strict=True)
    code: CodeReference
    structure: StructureReference | None = None
    conditions: Conditions
    fingerprint: str = Field(pattern='^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def integrity(self):
        if digest(self.model_dump(exclude={'fingerprint'})) != self.fingerprint: raise ValueError('测试条件摘要不一致。')
        if len({m.id for m in self.modules}) != len(self.modules): raise ValueError('测试硬件标识重复。')
        return self


class EvidenceContent(Boundary):
    name: str = Field(min_length=1, max_length=100)
    mime: Literal['image/png', 'image/jpeg', 'image/webp', 'text/plain']
    content: str = Field(min_length=1, max_length=710000)
    caption: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def data(self):
        if re.search(r'[<>:"/\\\x00-\x1f]', self.name) or self.name in {'.', '..'}: raise ValueError('附件名称无效。')
        try: raw = base64.b64decode(self.content, validate=True)
        except ValueError as exc: raise ValueError('附件编码无效。') from exc
        if not raw or len(raw) > 512000: raise ValueError('单个附件最多500KiB，请压缩图片或日志。')
        if self.mime == 'text/plain':
            text = raw.decode('utf-8')
            if '\0' in text: raise ValueError('日志须为无NUL的UTF-8文本。')
        elif not ((self.mime == 'image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or
                  (self.mime == 'image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or
                  (self.mime == 'image/webp' and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP')):
            raise ValueError('图片内容与格式不一致。')
        return self


class Evidence(EvidenceContent):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    createdAt: str

    @model_validator(mode='after')
    def integrity(self):
        if digest(base64.b64decode(self.content)) != self.checksum: raise ValueError('附件摘要不一致。')
        datetime.fromisoformat(self.createdAt)
        return self


class Observation(Boundary):
    result: Literal['passed', 'failed', 'blocked']
    observer: str = Field(min_length=1, max_length=100)
    prediction: str = Field(default='', max_length=1500)
    observed: str = Field(min_length=1, max_length=3000)
    explanation: str = Field(default='', max_length=2000)
    changes: str = Field(default='', max_length=1500)
    evidenceIds: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('observer', 'observed')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('请填写观察人和实际现象；平台不会代替实物确认。')
        return value.strip()


class TestRun(Observation):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    createdAt: str
    test: TestCase
    baseline: Baseline


class ReflectionContent(Boundary):
    role: Literal['teacher', 'student']
    author: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=3000)
    learned: str = Field(default='', max_length=3000)
    nextStep: str = Field(default='', max_length=1500)

    @field_validator('author', 'summary')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('请填写记录人和内容。')
        return value.strip()


class Reflection(ReflectionContent):
    revision: int = Field(ge=1, strict=True)
    createdAt: str


class Question(Boundary):
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(max_length=4)

    @field_validator('options')
    @classmethod
    def items(cls, values):
        if any(len(v) > 100 for v in values): raise ValueError('回复选项过长。')
        return values


class ReviewSource(Boundary):
    baseline: Baseline
    records: str = Field(pattern='^[a-f0-9]{64}$')
    checkedAt: str
    facts: list[str] = Field(max_length=12)
    method: Literal['records', 'ai'] = 'ai'

    @model_validator(mode='after')
    def valid_date(self):
        datetime.fromisoformat(self.checkedAt)
        if any(not s.strip() or len(s) > 500 for s in self.facts): raise ValueError('检查依据无效。')
        return self


class ProjectReview(Boundary):
    conclusion: str = Field(min_length=1, max_length=1500)
    gaps: list[str] = Field(max_length=10)
    nextSteps: list[str] = Field(max_length=8)
    decisions: list[str] = Field(max_length=6)
    comparison: str = Field(max_length=2500)
    source: ReviewSource | None = None

    @field_validator('gaps', 'nextSteps', 'decisions')
    @classmethod
    def bounded_items(cls, values):
        if any(not s.strip() or len(s) > 500 for s in values): raise ValueError('每项说明须为1到500字。')
        return values


class Proposal(Boundary):
    summary: str = Field(min_length=1, max_length=2000)
    question: Question | None
    definition: Definition | None
    tests: list[CaseContent] = Field(max_length=15)
    review: ProjectReview | None = None


class Message(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=30000)
    createdAt: str


class ChangeTask(Boundary):
    role: Literal['engineer', 'structure']
    status: Literal['pending', 'working', 'delivered', 'not_needed'] = 'pending'
    note: str = Field(default='', max_length=1500)
    code: CodeReference | None = None
    structure: StructureReference | None = None
    updatedAt: str

    @model_validator(mode='after')
    def integrity(self):
        datetime.fromisoformat(self.updatedAt)
        if self.status == 'not_needed' and not self.note.strip(): raise ValueError('无需调整须说明依据。')
        if self.status == 'delivered' and not (self.code if self.role == 'engineer' else self.structure): raise ValueError('交付须关联已保存的对应产物。')
        if self.status == 'delivered' and self.code and (self.code.mode == 'none' or self.code.revision is None or not re.fullmatch('[a-f0-9]{64}', self.code.checksum)): raise ValueError('程序交付须引用有效版本与摘要。')
        if self.role == 'engineer' and self.structure or self.role == 'structure' and self.code: raise ValueError('任务产物与角色不符。')
        if self.status != 'delivered' and (self.code or self.structure): raise ValueError('未交付任务不能关联交付版本。')
        return self


class RequirementChange(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    createdAt: str
    sourceMode: Literal['engineer', 'structure', 'learning']
    summary: str = Field(min_length=1, max_length=2000)
    baseDefinitionRevision: int | None = Field(default=None, ge=1, strict=True)
    definitionRevision: int | None = Field(default=None, ge=1, strict=True)
    status: Literal['proposed', 'confirmed', 'completed', 'cancelled'] = 'proposed'
    baseline: Baseline
    tasks: list[ChangeTask] = Field(default_factory=list, max_length=2)
    verificationRunIds: list[str] = Field(default_factory=list, max_length=60)
    completedAt: str | None = None
    collaborationDecided: bool = False

    @model_validator(mode='after')
    def integrity(self):
        datetime.fromisoformat(self.createdAt)
        if not self.summary.strip(): raise ValueError('请填写需求变更。')
        if self.baseDefinitionRevision != self.baseline.definitionRevision: raise ValueError('变更来源需求与基线不一致。')
        if len(set(self.verificationRunIds)) != len(self.verificationRunIds): raise ValueError('变更验收记录重复。')
        roles = {t.role for t in self.tasks}
        if self.tasks: self.collaborationDecided = True  # Existing handoffs remain readable.
        if len(roles) != len(self.tasks): raise ValueError('变更角色任务重复。')
        for task in self.tasks:
            if task.code and task.code.checksum == self.baseline.code.checksum or task.structure and self.baseline.structure and task.structure.checksum == self.baseline.structure.checksum:
                raise ValueError('交付版本须不同于变更前；无需修改须说明依据。')
        if self.status in {'confirmed', 'completed'}:
            if self.definitionRevision is None: raise ValueError('确认调整须关联已确认的目标。')
        elif self.definitionRevision is not None or self.tasks or self.collaborationDecided: raise ValueError('未确认变更不能带确认版本或处理任务。')
        if self.status == 'completed':
            if not self.collaborationDecided or not self.verificationRunIds or not self.completedAt or any(t.status not in {'delivered', 'not_needed'} for t in self.tasks): raise ValueError('完成调整须核对协作选择并有实际测试记录。')
            datetime.fromisoformat(self.completedAt)
        elif self.completedAt or self.verificationRunIds: raise ValueError('未完成变更不能携带完成记录。')
        return self


class Checkpoint(Boundary):
    schemaVersion: Literal[1] = 1
    revision: int = Field(default=0, ge=0, strict=True)
    definitions: list[DefinitionVersion] = Field(default_factory=list, max_length=100)
    conditions: Conditions = Field(default_factory=Conditions)
    cases: list[TestCase] = Field(default_factory=list, max_length=60)
    runs: list[TestRun] = Field(default_factory=list, max_length=200)
    evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    reflections: list[Reflection] = Field(default_factory=list, max_length=100)
    messages: list[Message] = Field(default_factory=list, max_length=100)
    changes: list[RequirementChange] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def integrity(self):
        for entries in [self.definitions, self.reflections]:
            if [v.revision for v in entries] != list(range(1, len(entries)+1)): raise ValueError('项目学习版本须连续。')
        for entries in [self.cases, self.runs, self.evidence, self.messages, self.changes]:
            if len({v.id for v in entries}) != len(entries): raise ValueError('项目学习记录标识重复。')
        cases = {c.id: c for c in self.cases}
        defs = {d.revision for d in self.definitions if d.confirmed}
        evidence = {e.id for e in self.evidence}
        runs = {r.id: r for r in self.runs}
        for change in self.changes:
            if change.baseDefinitionRevision is not None and change.baseDefinitionRevision not in defs: raise ValueError('变更来源需求不存在。')
            if change.definitionRevision is not None and change.definitionRevision not in defs: raise ValueError('变更确认需求不存在。')
            if change.definitionRevision is not None and change.baseDefinitionRevision is not None and change.definitionRevision <= change.baseDefinitionRevision: raise ValueError('变更必须确认到新的需求版本。')
            for rid in change.verificationRunIds:
                if rid not in runs or runs[rid].result != 'passed' or runs[rid].baseline.definitionRevision != change.definitionRevision: raise ValueError('变更验收引用不属于该需求的通过记录。')
            if len({runs[rid].test.id for rid in change.verificationRunIds}) != len(change.verificationRunIds): raise ValueError('同一测试不能重复计入变更验收。')
        for run in self.runs:
            datetime.fromisoformat(run.createdAt)
            if run.test.id not in cases or run.test.revision > cases[run.test.id].revision: raise ValueError('测试项引用无效。')
            if run.baseline.definitionRevision is not None and run.baseline.definitionRevision not in defs: raise ValueError('测试引用未确认的需求。')
            if len(set(run.evidenceIds)) != len(run.evidenceIds) or not set(run.evidenceIds) <= evidence: raise ValueError('测试附件引用无效。')
        for item in [*self.reflections, *self.messages]: datetime.fromisoformat(item.createdAt)
        for m in self.messages:
            if m.role == 'assistant':
                p = Proposal.model_validate_json(m.content)
                if p.review and p.review.source and p.review.source.baseline.definitionRevision is not None and p.review.source.baseline.definitionRevision not in defs:
                    raise ValueError('成果检查引用的作品目标不存在。')
        if len(self.model_dump_json().encode()) > 8*1024*1024: raise ValueError('项目学习记录超过8MiB，请先导出并另建项目。')
        return self
