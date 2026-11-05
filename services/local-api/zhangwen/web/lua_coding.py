"""Reviewed Lua candidates and explicit upload, using existing Project/Artifact storage.

No model tools, firmware, console endpoint, arbitrary upload path or auto-retry.
The device's fixed console command is used separately by browser Web Serial.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator, field_validator, ValidationError

from zhangwen.artifacts.models import ArtifactPreview, ArtifactPreviewKind, ArtifactStatus
from .models import Boundary, CodeInput
from .programming_modes import board_mode
from .mosaico_device import Operation, FileWrite
from .replies import reply_code


def sha(code): return hashlib.sha256(code.encode('utf-8')).hexdigest()
def now(): return datetime.now(UTC).isoformat()


class Version(Boundary):
    revision: int = Field(ge=1, strict=True)
    code: str = Field(min_length=1, max_length=65536)
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    source: Literal['ai', 'saved']
    createdAt: str

    @model_validator(mode='after')
    def integrity(self):
        CodeInput.code_size(self.code)
        if not self.code.strip() or sha(self.code) != self.checksum: raise ValueError('Lua内容摘要不一致。')
        datetime.fromisoformat(self.createdAt)
        return self


class UploadRecord(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    revision: int = Field(ge=1, strict=True)
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    path: str = Field(pattern=r'^/scripts/temp/zw_[a-f0-9]{16}\.lua$')
    createdAt: str
    state: Literal['pending', 'verified', 'outcome-unknown']
    backupId: str | None = Field(default=None, max_length=200)


class Checkpoint(Boundary):
    schemaVersion: Literal[1] = 1
    revision: int = Field(default=0, ge=0, strict=True)
    accepted: int | None = Field(default=None, ge=1, strict=True)
    versions: list[Version] = Field(default_factory=list, max_length=200)
    uploads: list[UploadRecord] = Field(default_factory=list, max_length=200)
    runs: list['RunRecord'] = Field(default_factory=list, max_length=200)
    runRecoveries: list['RunRecovery'] = Field(default_factory=list, max_length=200)
    wifiSetups: list['WifiSetupRecord'] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def integrity(self):
        if [v.revision for v in self.versions] != list(range(1, len(self.versions)+1)):
            raise ValueError('Lua版本必须连续且不重复。')
        by_id = {v.revision:v for v in self.versions}
        if self.accepted is not None and (self.accepted not in by_id or by_id[self.accepted].source != 'saved'):
            raise ValueError('当前Lua必须指向用户已接受并保存的版本。')
        if len({u.id for u in self.uploads}) != len(self.uploads): raise ValueError('上传标识重复。')
        for u in self.uploads:
            v = by_id.get(u.revision)
            if not v or v.source != 'saved' or v.checksum != u.checksum: raise ValueError('上传记录与已保存Lua不一致。')
            datetime.fromisoformat(u.createdAt)
        if len({r.id for r in self.runs}) != len(self.runs): raise ValueError('运行标识重复。')
        if len({s.id for s in self.wifiSetups}) != len(self.wifiSetups): raise ValueError('WiFi安装标识重复。')
        for r in self.runs:
            if r.revision not in by_id or by_id[r.revision].source != 'saved': raise ValueError('运行版本无效。')
        if len({r.runId for r in self.runRecoveries}) != len(self.runRecoveries) or len({r.id for r in self.runRecoveries}) != len(self.runRecoveries):
            raise ValueError('运行归档记录重复。')
        for recovery in self.runRecoveries:
            record = next((r for r in self.runs if r.id == recovery.runId), None)
            if (not record or record.transport != 'wifi' or record.state not in {'submitted','outcome-unknown'}
                    or record.bootId != recovery.previousBootId or record.deviceEndpoint != recovery.deviceEndpoint
                    or recovery.bootId == recovery.previousBootId):
                raise ValueError('运行归档与原始证据不一致。')
            datetime.fromisoformat(recovery.createdAt)
        if len(self.model_dump_json().encode()) > 4*1024*1024: raise ValueError('Lua历史超过4MiB，请另建项目。')
        return self


class RunRecord(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    revision: int = Field(ge=1,strict=True)
    createdAt: str
    state: Literal['submitted','returned','outcome-unknown']
    timeoutMs: int = Field(ge=1000,le=60000,strict=True)
    output: str = Field(default='',max_length=16000)
    transport: Literal['usb','wifi'] = 'usb'
    bootId: str | None = Field(default=None,pattern='^[a-f0-9]{16}$')
    deviceEndpoint: str | None = Field(default=None,max_length=200)
    jobId: str | None = Field(default=None,pattern='^[a-zA-Z0-9_-]{1,80}$')
    deviceState: str | None = Field(default=None,max_length=24)


class RunRecovery(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    runId: str = Field(pattern='^[a-f0-9]{32}$')
    previousBootId: str = Field(pattern='^[a-f0-9]{16}$')
    bootId: str = Field(pattern='^[a-f0-9]{16}$')
    deviceEndpoint: str = Field(max_length=200)
    createdAt: str


def unresolved_runs(value):
    archived = {r.runId for r in value.runRecoveries}
    return [r for r in value.runs if r.transport == 'wifi' and r.state in {'submitted','outcome-unknown'} and r.id not in archived]


class WifiSetupFile(Boundary):
    path: Literal['/scripts/zhangwen_wifi_bridge.lua','/router_rules/router_rules.json']
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    backupId: str | None = Field(default=None,max_length=200)


class WifiSetupRecord(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    createdAt: str
    state: Literal['pending','verified','outcome-unknown']
    planChecksum: str = Field(pattern='^[a-f0-9]{64}$')
    files: list[WifiSetupFile] = Field(max_length=2)


Checkpoint.model_rebuild()


def require_project(repo, pid):
    p = repo.get(pid)
    if board_mode(repo, p['boardId']) != 'chat-coding': raise HTTPException(422, '请选择Mosaico项目。')
    return p


def reference(repo, board_id):
    """Read reviewed references from the same Skill without replacing user files.

    Installed packages survive catalog upgrades. Fill missing reference sections
    from the matching release package so older Lua v2 packages receive onboard
    hardware and example knowledge as well. Never write to the installed package.
    """
    detail=repo.skills.get_active_by_component_id(board_id)
    from .hardware import RELEASE_CATALOG
    package=RELEASE_CATALOG/detail.skillName
    manifest=package/'manifest.json'
    # Match package identity, including renamed user-maintained Skills.
    if not manifest.is_file() or json.loads(manifest.read_text(encoding='utf-8')).get('componentId') != board_id:
        package=next((p.parent for p in sorted(RELEASE_CATALOG.glob('*/manifest.json'))
                      if json.loads(p.read_text(encoding='utf-8')).get('componentId') == board_id), None)
    installed={f.path:f.content for f in detail.files}
    def bundled(path):
        source=package/path if package else None
        return source.read_text(encoding='utf-8') if source and source.is_file() else ''
    marker='<!-- zhangwen:lua-reference:v2 -->'
    text=installed.get('references/integration.md','')
    if marker not in text:
        text=bundled('references/integration.md') or text
    parts=[text.split(marker,1)[-1] if marker in text else '当前Hardware Skill未提供Lua API资料。只可给标准Lua诊断或询问实际模块API，不猜测。']
    for path, section in (
        ('SKILL.md','<!-- zhangwen:mosaico-onboard:v1 -->'),
        ('references/integration.md','<!-- zhangwen:mosaico-lua-peripherals:v1 -->'),
        ('examples/usage.md','<!-- zhangwen:mosaico-examples:v1 -->'),
        ('references/integration.md','<!-- zhangwen:lua-confirmed-api:v1 -->'),
    ):
        if any(section in part for part in parts):
            continue
        content=installed.get(path,'')
        if section not in content:
            content=bundled(path)
        if section in content:
            if section == '<!-- zhangwen:lua-confirmed-api:v1 -->':
                # Older marked peripheral sections also need the compact contract.
                parts.append(section + content.split(section,1)[-1].split('<!-- /zhangwen:lua-confirmed-api:v1 -->',1)[0]
                             + '<!-- /zhangwen:lua-confirmed-api:v1 -->')
            else:
                parts.append(content.split(section,1)[-1])
    return '\n\n'.join(parts)


def confirmed_api_context(text):
    """Repeat the Skill's compact contract near the request, after old dialogue.

    The full reference and user history remain intact. API facts have one source
    in the existing Skill, not a second hard-coded hardware map.
    """
    start='<!-- zhangwen:lua-confirmed-api:v1 -->'
    end='<!-- /zhangwen:lua-confirmed-api:v1 -->'
    if start not in text or end not in text.split(start,1)[1]:
        return ''
    return text.split(start,1)[1].split(end,1)[0].strip()


def load(repo, pid):
    repo.get(pid)
    with repo.connect() as conn:
        row = conn.execute('SELECT v.preview_json FROM artifacts a JOIN artifact_versions v ON v.id=a.current_version_id WHERE a.id=? AND a.project_id=?', ('zhangwen_lua_'+pid,pid)).fetchone()
    return Checkpoint.model_validate_json(json.loads(row[0])['code']) if row else Checkpoint()


def insert(repo, conn, pid, value):
    """Also called inside portable Project import's original transaction."""
    value = Checkpoint.model_validate(value.model_dump())
    aid='zhangwen_lua_'+pid; vid='artifact_version_'+uuid.uuid4().hex; stamp=now(); text=value.model_dump_json(exclude_none=True)
    preview=ArtifactPreview(kind=ArtifactPreviewKind.CODE, code=text, language='json', summary='掌问Lua候选、已接受代码与上传证据；不代表实物成功。')
    conn.execute("""INSERT INTO artifacts(id,project_id,title,kind,status,source_agent_id,current_version_id,created_at,updated_at)
        VALUES(?,?,'掌问Lua程序','CODE','DRAFT','zhangwen-lua',?,?,?)
        ON CONFLICT(id) DO UPDATE SET current_version_id=excluded.current_version_id,updated_at=excluded.updated_at""",(aid,pid,vid,stamp,stamp))
    version=conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?',(aid,)).fetchone()[0]
    conn.execute("""INSERT INTO artifact_versions(id,artifact_id,project_id,version,status,mime_type,preview_json,dependencies_json,source_entity_type,source_entity_id,checksum,created_at)
        VALUES(?,?,?,?,'DRAFT','application/json',?,'[]','zhangwen_lua',?,?,?)""",(vid,aid,pid,version,preview.model_dump_json(),uuid.uuid4().hex,sha(text),stamp))
    repo.artifacts._apply_artifact_context(conn,artifact_id=aid,version_id=vid,project_id=pid,source_agent_id='zhangwen-lua',status=ArtifactStatus.DRAFT)


def store(repo,pid,value):
    value.revision += 1
    try:
        with repo.connect() as conn: insert(repo,conn,pid,value)
    except ValidationError as exc: raise HTTPException(422,'Lua内容或历史超过约束，请检查内容或另建项目；原记录保持。') from exc
    return value


def candidate(repo,pid,content):
    code=reply_code(content)
    if code is None: return
    with repo.lock:
        value=load(repo,pid)
        value.versions.append(Version(revision=len(value.versions)+1,code=code,checksum=sha(code),source='ai',createdAt=now()))
        store(repo,pid,value)


class Save(Boundary):
    expectedRevision: int = Field(ge=0, strict=True)
    code: str = Field(min_length=1,max_length=65536)

    @field_validator('code')
    @classmethod
    def valid_code(cls,value):
        CodeInput.code_size(value)
        if not value.strip():raise ValueError('Lua内容不能为空。')
        return value


class Upload(Operation):
    projectId: str
    revision: int = Field(ge=1,strict=True)
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    expectedChecksum: str | None = Field(default=None,pattern='^[a-f0-9]{64}$')


class RunStart(Operation):
    revision: int = Field(ge=1,strict=True)
    timeoutMs: int = Field(ge=1000,le=60000,strict=True)


class RunFinish(Boundary):
    state: Literal['returned','outcome-unknown']
    output: str = Field(max_length=16000)


def accepted(repo,pid,revision):
    require_project(repo,pid);value=load(repo,pid)
    if value.accepted != revision: raise HTTPException(409,'Lua已保存版本已改变，请重新查看上传清单。')
    version=next(v for v in value.versions if v.revision==revision)
    return value,version


def device_path(pid): return '/scripts/temp/zw_'+sha(pid)[:16]+'.lua'


async def manifest(service,pid,revision):
    _,v=accepted(service.repo,pid,revision)
    connection=service.connection_id
    service.target(connection)
    path=device_path(pid);raw=await service.read_file(path)
    return {'projectId':pid,'revision':v.revision,'checksum':v.checksum,'content':v.code,'size':len(v.code.encode()),'path':path,
            'expectedChecksum':hashlib.sha256(raw).hexdigest() if raw is not None else None,'connectionId':connection}


async def upload(service,request):
    repo=service.repo; path=device_path(request.projectId)
    # Durable intent in original Artifact history survives a lost response/restart.
    with repo.lock:
        value,version=accepted(repo,request.projectId,request.revision)
        old=next((u for u in value.uploads if u.id==request.requestId),None)
        if old:
            if old.revision!=request.revision or old.checksum!=request.checksum: raise HTTPException(409,'上传标识对应的版本不同。')
            if old.state=='verified': return {'state':'verified','message':'此上传已有回读凭证，未再次写入。'}
            raise HTTPException(409,'此上传结果未知，必须先核对设备文件，不会重发。')
        if version.checksum!=request.checksum: raise HTTPException(409,'上传内容摘要已改变。')
        service.target(request.connectionId)
    # Preflight before committing the intent; actual write repeats this check under device lock.
    raw=await service.read_file(path)
    if (hashlib.sha256(raw).hexdigest() if raw is not None else None)!=request.expectedChecksum:
        raise HTTPException(409,'设备目标文件已改变，请重新查看清单；未覆盖。')
    with repo.lock:
        value,version=accepted(repo,request.projectId,request.revision)
        if any(u.id==request.requestId for u in value.uploads): raise HTTPException(409,'上传已提交，请先读取记录。')
        record=UploadRecord(id=request.requestId,revision=version.revision,checksum=version.checksum,path=path,createdAt=now(),state='pending')
        value.uploads.append(record);store(repo,request.projectId,value)
    try:
        # Native mkdir is explicit and fixed; no shared startup/rules/config files.
        if raw is None:
            from .mosaico_device import PathWrite
            mkdir=PathWrite(connectionId=request.connectionId,requestId=uuid.uuid4().hex,path='/scripts/temp')
            await service.simple_write(mkdir,'/api/files/mkdir',{'path':'/scripts/temp','recursive':True})
        result=await service.write_file(FileWrite(**request.model_dump(exclude={'revision','checksum'}),path=path,content=base64.b64encode(version.code.encode()).decode()))
    except BaseException:
        with repo.lock:
            value=load(repo,request.projectId);next(u for u in value.uploads if u.id==request.requestId).state='outcome-unknown';store(repo,request.projectId,value)
        raise
    with repo.lock:
        value=load(repo,request.projectId);record=next(u for u in value.uploads if u.id==request.requestId)
        record.state='verified';record.backupId=result['backupId'];store(repo,request.projectId,value)
    return {**result,'path':path}


def router(repo,service):
    route=APIRouter()
    @route.get('/api/projects/{pid}/lua-coding')
    def state(pid:str): require_project(repo,pid);return load(repo,pid)
    @route.post('/api/projects/{pid}/lua-coding/save')
    def save(pid:str,request:Save):
        require_project(repo,pid)
        with repo.lock:
            value=load(repo,pid)
            if value.revision!=request.expectedRevision: raise HTTPException(409,'Lua历史已更新，请先重新读取。')
            v=Version(revision=len(value.versions)+1,code=request.code,checksum=sha(request.code),source='saved',createdAt=now())
            value.versions.append(v);value.accepted=v.revision
            return store(repo,pid,value)
    @route.get('/api/mosaico/lua-manifest')
    async def preview(projectId:str,revision:int): return await manifest(service,projectId,revision)
    @route.post('/api/mosaico/lua-upload')
    async def send(request:Upload): return await upload(service,request)
    @route.post('/api/projects/{pid}/lua-coding/runs')
    async def run(pid:str,request:RunStart):
        service.target(request.connectionId)
        preview=await manifest(service,pid,request.revision)
        if preview['expectedChecksum']!=preview['checksum']: raise HTTPException(409,'设备文件与当前已保存Lua不一致，请先上传并回读。')
        with repo.lock:
            value,_=accepted(repo,pid,request.revision)
            if any(r.id==request.requestId for r in value.runs): raise HTTPException(409,'运行已提交，不能自动重复运行。')
            value.runs.append(RunRecord(id=request.requestId,revision=request.revision,createdAt=now(),state='submitted',timeoutMs=request.timeoutMs))
            store(repo,pid,value)
        return {'id':request.requestId,'path':preview['path'].removeprefix('/scripts/'),'timeoutMs':request.timeoutMs}
    @route.post('/api/projects/{pid}/lua-coding/runs/{rid}')
    def finish(pid:str,rid:str,request:RunFinish):
        require_project(repo,pid)
        with repo.lock:
            value=load(repo,pid);record=next((r for r in value.runs if r.id==rid),None)
            if not record: raise HTTPException(404,'运行记录不存在。')
            if record.transport!='usb': raise HTTPException(409,'WiFi运行记录须从设备接口读取。')
            if record.state!='submitted': raise HTTPException(409,'运行记录已经结束，未覆盖。')
            record.state=request.state;record.output=request.output
            return store(repo,pid,value)
    from .lua_wifi import add_routes
    add_routes(route,repo,service)
    return route
