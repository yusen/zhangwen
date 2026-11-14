"""Additional controller channels in the existing Project/Artifact store.

No server serial, model tools or device execution. CAS is scoped to each
channel; the checkpoint is persisted inside one original SQLite transaction.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, field_validator, model_validator, ValidationError

from zhangwen.artifacts.models import ArtifactPreview, ArtifactPreviewKind, ArtifactStatus
from .models import Boundary, CodeInput, ChatInput
from .programming_modes import board_mode


def now(): return datetime.now(UTC).isoformat()
def sha(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()


class Version(Boundary):
    revision: int = Field(ge=1, strict=True)
    code: str = Field(max_length=65536)
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    createdAt: str
    boardId: str | None = Field(default=None, min_length=1, max_length=150)
    componentIds: list[str] | None = Field(default=None, max_length=32)

    @model_validator(mode='after')
    def integrity(self):
        CodeInput.code_size(self.code)
        if sha(self.code) != self.checksum: raise ValueError('通道代码摘要不一致。')
        datetime.fromisoformat(self.createdAt)
        return self


class Message(Boundary):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=80000)
    status: Literal['COMPLETED'] = 'COMPLETED'
    createdAt: str
    boardId: str | None = Field(default=None, min_length=1, max_length=150)
    componentIds: list[str] | None = Field(default=None, max_length=32)
    intent: Literal['integration'] | None = None
    integrationModuleId: str | None = Field(default=None, min_length=1, max_length=150)

    @field_validator('createdAt')
    @classmethod
    def timestamp(cls, value):
        datetime.fromisoformat(value)
        return value


class Channel(Boundary):
    id: str = Field(pattern='^[a-f0-9]{32}$')
    name: str = Field(min_length=1, max_length=80)
    boardId: str = Field(min_length=1, max_length=150)
    componentIds: list[str] = Field(default_factory=list, max_length=32)
    hardwareRevisions: dict[str, str]
    revision: int = Field(ge=1, strict=True)
    versions: list[Version] = Field(min_length=1, max_length=200)
    messages: list[Message] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def pointers(self):
        if not self.name.strip(): raise ValueError('通道名称不能为空。')
        if [v.revision for v in self.versions] != list(range(1, len(self.versions)+1)):
            raise ValueError('通道代码版本须连续。')
        if self.revision != len(self.versions) + len(self.messages) // 2 or len(self.messages) % 2:
            raise ValueError('通道版本与保存、对话记录不一致。')
        if set(self.hardwareRevisions) != {self.boardId, *self.componentIds}:
            raise ValueError('通道器件修订不完整。')
        if len(set(self.componentIds)) != len(self.componentIds) or self.boardId in self.componentIds:
            raise ValueError('通道器件重复。')
        return self


class Checkpoint(Boundary):
    schemaVersion: Literal[1] = 1
    revision: int = Field(default=0, ge=0, strict=True)
    channels: list[Channel] = Field(default_factory=list, max_length=7)

    @model_validator(mode='after')
    def integrity(self):
        if len({c.id for c in self.channels}) != len(self.channels): raise ValueError('通道标识重复。')
        if len(self.model_dump_json().encode()) > 8 * 1024 * 1024: raise ValueError('通道历史超过8MiB。')
        return self


class Save(CodeInput):
    expectedRevision: int = Field(ge=0, strict=True)
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def name_text(cls, value):
        if not value.strip(): raise ValueError('通道名称不能为空。')
        return value.strip()


class Expected(Boundary):
    expectedRevision: int = Field(ge=1, strict=True)


class Generate(Expected):
    message: str = Field(min_length=1, max_length=4000)
    code: str = Field(max_length=65536)
    intent: Literal['integration'] | None = None
    integrationModuleId: str | None = Field(default=None, min_length=1, max_length=150)

    @field_validator('code')
    @classmethod
    def code_size(cls, value): return CodeInput.code_size(value)


def load(repo, pid):
    repo.get(pid)
    with repo.connect() as conn:
        row = conn.execute('SELECT v.preview_json FROM artifacts a JOIN artifact_versions v ON v.id=a.current_version_id WHERE a.id=? AND a.project_id=?', ('zhangwen_channels_'+pid, pid)).fetchone()
    return Checkpoint.model_validate_json(json.loads(row[0])['code']) if row else Checkpoint()


def insert(repo, conn, pid, checkpoint):
    value = Checkpoint.model_validate(checkpoint.model_dump())
    aid = 'zhangwen_channels_'+pid
    vid = 'artifact_version_'+uuid.uuid4().hex
    stamp = now()
    text = value.model_dump_json()
    preview = ArtifactPreview(kind=ArtifactPreviewKind.CODE, code=text, language='json', summary='同一项目的独立主控开发通道；历史不授予设备执行权限。')
    conn.execute("""INSERT INTO artifacts(id,project_id,title,kind,status,source_agent_id,current_version_id,created_at,updated_at)
        VALUES(?,?,'主控开发通道','CODE','DRAFT','zhangwen-channels',?,?,?)
        ON CONFLICT(id) DO UPDATE SET current_version_id=excluded.current_version_id,updated_at=excluded.updated_at""", (aid,pid,vid,stamp,stamp))
    version = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?',(aid,)).fetchone()[0]
    conn.execute("""INSERT INTO artifact_versions(id,artifact_id,project_id,version,status,mime_type,preview_json,dependencies_json,source_entity_type,source_entity_id,checksum,created_at)
        VALUES(?,?,?,?,'DRAFT','application/json',?,'[]','zhangwen_channels',?,?,?)""", (vid,aid,pid,version,preview.model_dump_json(),uuid.uuid4().hex,sha(text),stamp))
    repo.artifacts._apply_artifact_context(conn,artifact_id=aid,version_id=vid,project_id=pid,source_agent_id='zhangwen-channels',status=ArtifactStatus.DRAFT)


def validate_hardware(repo, value):
    for channel in value.channels:
        repo.hardware_revisions(channel.boardId, channel.componentIds)
        if board_mode(repo, channel.boardId) != 'micropython':
            raise HTTPException(422, '附加串口通道使用MicroPython；Mosaico Lua/Claw请使用项目原主通道。')


def find(value, cid):
    channel = next((c for c in value.channels if c.id == cid), None)
    if channel is None: raise HTTPException(404, '当前项目中不存在此通道。')
    return channel


def store(repo, pid, value):
    value.revision += 1
    try:
        value = Checkpoint.model_validate(value.model_dump())
    except ValidationError as exc:
        raise HTTPException(422,'通道历史超过容量或内容校验失败；原记录保持，请导出后另建通道或项目。') from exc
    with repo.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        insert(repo, conn, pid, value)


def save(repo, pid, cid, request):
    with repo.lock:
        value = load(repo,pid)
        if cid:
            channel = find(value,cid)
            if channel.revision != request.expectedRevision: raise HTTPException(409, '通道已更新，草稿保留；请重新读取后核对。')
            # Stamp legacy records before changing hardware, preserving their actual origin.
            for record in [*channel.versions, *channel.messages]:
                if record.boardId is None: record.boardId = channel.boardId
                if record.componentIds is None: record.componentIds = list(channel.componentIds)
        else:
            if request.expectedRevision != 0 or len(value.channels) >= 7: raise HTTPException(409, '最多添加7个附加通道；新通道版本须为0。')
            channel = Channel(id=uuid.uuid4().hex, name=request.name, boardId=request.boardId, componentIds=request.componentIds,
                              hardwareRevisions=repo.hardware_revisions(request.boardId,request.componentIds), revision=1,
                              versions=[Version(revision=1,code=request.code,checksum=sha(request.code),createdAt=now(),boardId=request.boardId,componentIds=request.componentIds)])
            value.channels.append(channel)
        if cid:
            channel.name = request.name
            channel.boardId = request.boardId
            channel.componentIds = request.componentIds
            channel.hardwareRevisions = repo.hardware_revisions(request.boardId,request.componentIds)
            channel.versions.append(Version(revision=len(channel.versions)+1,code=request.code,checksum=sha(request.code),createdAt=now(),boardId=request.boardId,componentIds=request.componentIds))
            channel.revision += 1
        validate_hardware(repo,value)
        store(repo,pid,value)
        return channel.model_dump()


def summary(repo, pid):
    return [dict(id=c.id,name=c.name,boardId=c.boardId,componentIds=c.componentIds,
                 revision=c.revision,codeRevision=c.versions[-1].revision,checksum=c.versions[-1].checksum)
            for c in load(repo,pid).channels]


def router(repo, generate):
    routes = APIRouter(prefix='/api/projects/{pid}/channels')
    locks = {}

    @routes.get('')
    def listing(pid: str): return load(repo,pid).model_dump()

    @routes.post('', status_code=201)
    def create(pid: str, request: Save): return save(repo,pid,None,request)

    @routes.put('/{cid}')
    def update(pid: str, cid: str, request: Save): return save(repo,pid,cid,request)

    @routes.post('/{cid}/upload-manifest')
    def manifest(pid: str, cid: str, request: Expected):
        with repo.lock:
            channel = find(load(repo,pid),cid)
            if channel.revision != request.expectedRevision: raise HTTPException(409,'通道版本已变化，未提交上传。')
            revisions = repo.hardware_revisions(channel.boardId, channel.componentIds)
            if revisions != channel.hardwareRevisions: raise HTTPException(409,'器件资料已更新，请核对并保存通道。')
            version = channel.versions[-1]
            checked = repo.check(CodeInput(code=version.code,boardId=channel.boardId,componentIds=channel.componentIds))
            if not checked['valid']: raise HTTPException(422,'程序静态检查未通过。')
            return dict(projectId=pid,channelId=cid,revision=channel.revision,boardId=channel.boardId,hardwareRevisions=revisions,
                        files=[dict(path='main.py',content=version.code,sha256=version.checksum,size=len(version.code.encode()))])

    @routes.post('/{cid}/chat')
    async def chat(pid: str, cid: str, request: Generate):
        lock = locks.setdefault((pid,cid),asyncio.Lock())
        if lock.locked(): raise HTTPException(409,'此通道正在生成，请等待完成。')
        async with lock:
            with repo.lock:
                channel = find(load(repo,pid),cid)
                if channel.revision != request.expectedRevision: raise HTTPException(409,'通道已改变，请先核对版本。')
                board = channel.boardId
                components = list(channel.componentIds)
                history = [m.model_dump() for m in channel.messages if m.boardId in (None, board)]
                try:
                    model_request = ChatInput(message=request.message,code=request.code,boardId=board,componentIds=components,intent=request.intent,integrationModuleId=request.integrationModuleId)
                except ValidationError as exc:
                    raise HTTPException(422, '联调对象必须是当前已加入的模块。') from exc
            # One model request; no device or command capability is exposed.
            reply = await generate(model_request,history,pid,cid)
            with repo.lock:
                value = load(repo,pid)
                channel = find(value,cid)
                if channel.revision != request.expectedRevision: raise HTTPException(409,'生成期间通道已更新，未覆盖；请保留本地草稿。')
                origin = dict(boardId=board,componentIds=components,intent=request.intent,integrationModuleId=request.integrationModuleId)
                channel.messages.extend([Message(role='user',content=request.message,createdAt=now(),**origin),Message(role='assistant',content=reply,createdAt=now(),**origin)])
                channel.revision += 1
                store(repo,pid,value)
                return channel.model_dump()

    return routes
