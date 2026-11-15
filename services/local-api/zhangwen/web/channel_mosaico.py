"""Controller-scoped reuse of the existing fixed Lua/Claw device protocols.

All durable state stays in the original channel Artifact. No synthetic Projects,
live grants in snapshots, model tools, automatic connections or task retries.
"""
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import Field, ValidationError
from starlette.responses import JSONResponse

from . import channels, chat_coding, lua_coding, mosaico_device
from .models import Boundary, ChatInput
from .programming_modes import board_mode


class ScopedRepository:
    def __init__(self, repo, pid, cid):
        self.base = repo
        self.pid = pid
        self.controller_id = cid

    def __getattr__(self, name):
        return getattr(self.base, name)

    def channel(self, pid):
        if pid != self.pid:
            raise HTTPException(409, '请求项目与当前主控不一致，未操作设备。')
        value = channels.find(channels.load(self.base, pid), self.controller_id)
        if board_mode(self.base, value.boardId) != 'chat-coding':
            raise HTTPException(409, '此主控已改变型号，请重新读取器件。')
        return value

    def get(self, pid):
        channel = self.channel(pid)
        project = self.base.get(pid)
        version = channel.versions[-1]
        return {**project, 'name':channel.name, 'boardId':channel.boardId,
                'componentIds':channel.componentIds, 'hardwareRevisions':channel.hardwareRevisions,
                'revision':channel.revision, 'programmingMode':'chat-coding',
                'code':version.code, 'checksum':version.checksum,
                'messages':[dict(id=f'{channel.id}_{i}', **m.model_dump())
                            for i,m in enumerate(channel.messages) if m.boardId in (None,channel.boardId)]}

    def mosaico_state(self, pid):
        return self.channel(pid).mosaico or channels.MosaicoState()

    def write_mosaico(self, conn, pid, **changes):
        # Caller holds the original repository lock. Use its original transaction.
        self.channel(pid)
        value = channels.load(self.base, pid)
        channel = channels.find(value, self.controller_id)
        state = channel.mosaico or channels.MosaicoState()
        try:
            channel.mosaico = channels.MosaicoState.model_validate({**state.model_dump(), **changes})
            value.revision += 1
            channels.insert(self.base, conn, pid, value)
        except ValidationError as exc:
            raise HTTPException(422, '此主控历史超过容量或校验失败，原记录保持，请导出后另建主控。') from exc


class SourceInput(Boundary):
    source: str = Field(pattern='^(local|device)$')


class LuaGenerate(ChatInput):
    expectedRevision: int = Field(ge=1, strict=True)


class MosaicoChannels:
    def __init__(self, repo, main_device, main_chat, generate):
        self.repo, self.main_device, self.main_chat, self.generate = repo, main_device, main_chat, generate
        self.entries = {}
        self.endpoint_lock = asyncio.Lock()
        main_device.endpoint_guard = lambda base: self.guard(None, base)
        main_chat.endpoint_guard = lambda base: self.guard(None, base)
        repo.controller_change_guard = self.validate_change

    def validate_change(self, pid, cid, board_id):
        entry = self.entries.get((pid,cid))
        if entry and (entry['device'].endpoint or entry['chat'].connections) and (
                channels.find(channels.load(self.repo,pid),cid).boardId != board_id):
            raise HTTPException(409, '此主控仍连接设备，请先断开，再更换型号。')

    @asynccontextmanager
    async def guard(self, owner, base):
        async with self.endpoint_lock:
            pairs = [(None, self.main_device, self.main_chat)] + [
                (key, entry['device'], entry['chat']) for key,entry in self.entries.items()]
            if owner is not None and any(key == owner and (
                    device.endpoint and device.endpoint != base or any(live['endpoint'] != base for live in chat.connections.values()))
                    for key,device,chat in pairs):
                raise HTTPException(409, '此主控已连接其他设备地址，请先断开后再更换。')
            if any(key != owner and (device.endpoint == base or any(
                    live['endpoint'] == base for live in chat.connections.values())) for key,device,chat in pairs):
                raise HTTPException(409, '此设备地址已由其他主控连接，请先断开该主控，避免交叉操作。')
            yield

    def entry(self, pid, cid):
        scoped = ScopedRepository(self.repo, pid, cid)
        scoped.channel(pid)
        key = (pid, cid)
        if key in self.entries:
            return self.entries[key]
        chat = chat_coding.ChatCodingService(scoped)
        device = mosaico_device.MosaicoService(scoped, chat)
        device.endpoint_guard = lambda base: self.guard(key, base)
        chat.endpoint_guard = lambda base: self.guard(key, base)
        chat.attachment_check = device.check_attachments
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.include_router(chat_coding.router(chat))
        app.include_router(mosaico_device.router(device))
        app.include_router(lua_coding.router(scoped, device))
        generation_lock = asyncio.Lock()

        @app.get('/api/projects/{project_id}')
        def project(project_id: str):
            return scoped.get(project_id)

        @app.get('/api/projects/{project_id}/mosaico-source')
        def source(project_id: str):
            return {'source':scoped.mosaico_state(project_id).source}

        @app.post('/api/projects/{project_id}/mosaico-source')
        def save_source(project_id: str, request: SourceInput):
            with self.repo.lock, self.repo.connect() as conn:
                scoped.write_mosaico(conn, project_id, source=request.source)
            return {'source':request.source}

        @app.post('/api/projects/{project_id}/chat')
        async def generate(project_id: str, request: LuaGenerate):
            if generation_lock.locked():
                raise HTTPException(409, '此主控正在生成，请等待完成。')
            async with generation_lock:
                with self.repo.lock:
                    channel = scoped.channel(project_id)
                    if request.expectedRevision != channel.revision:
                        raise HTTPException(409, '主控已改变，输入保留，请核对后生成。')
                    if (request.boardId != channel.boardId or request.componentIds != channel.componentIds
                            or request.intent != 'lua-coding'):
                        raise HTTPException(409, '请先保存此主控的器件，再生成Lua。')
                    history = [m.model_dump() for m in channel.messages
                               if m.intent == 'lua-coding' and m.boardId == channel.boardId]
                    lua_revision = lua_coding.load(scoped, project_id).revision
                reply = await self.generate(ChatInput(**request.model_dump(exclude={'expectedRevision'})), history, project_id, cid)
                with self.repo.lock:
                    value = channels.load(self.repo, project_id)
                    channel = channels.find(value, cid)
                    if (channel.revision != request.expectedRevision
                            or lua_coding.load(scoped, project_id).revision != lua_revision):
                        raise HTTPException(409, '生成期间主控或Lua已更新，未覆盖；请保留草稿。')
                    origin = dict(boardId=channel.boardId, componentIds=channel.componentIds, intent='lua-coding')
                    channel.messages.extend([
                        channels.Message(role='user', content=request.message, createdAt=channels.now(), **origin),
                        channels.Message(role='assistant', content=reply, createdAt=channels.now(), **origin)])
                    channel.revision += 1
                    state = channel.mosaico or channels.MosaicoState()
                    code = lua_coding.reply_code(reply)
                    if code is not None:
                        state.lua.versions.append(lua_coding.Version(revision=len(state.lua.versions)+1,
                            code=code, checksum=lua_coding.sha(code), source='ai', createdAt=channels.now()))
                        state.lua.revision += 1
                    channel.mosaico = state
                    channels.store(self.repo, project_id, value)
                    return {'messages':scoped.get(project_id)['messages']}

        entry = dict(repo=scoped, device=device, chat=chat, app=app)
        self.entries[key] = entry
        return entry

    async def __call__(self, scope, receive, send):
        # Outer application enforces loopback Host/Origin/session/body limits.
        params = scope['path_params']
        try:
            entry = self.entry(params['pid'], params['cid'])
        except HTTPException as exc:
            await JSONResponse({'detail':exc.detail}, status_code=exc.status_code)(scope, receive, send)
            return
        root = scope['root_path']
        path = scope['path'].removeprefix(root)
        child = {**scope, 'root_path':'', 'path':'/api'+path, 'raw_path':('/api'+path).encode()}
        await entry['app'](child, receive, send)

    async def close(self):
        for entry in self.entries.values():
            await entry['device'].stop_logs()
            await entry['chat'].close()
