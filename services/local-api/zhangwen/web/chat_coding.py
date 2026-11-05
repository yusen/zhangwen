"""User-submitted Claw WebIM tasks; no shell, firmware, file-write or model tools.

Protocol reference: espressif/esp-claw@519bd95900d29bfc9daf3619ff779753e3153f05.
Only numeric RFC1918 destinations, fixed routes, bounded JSON, no redirects/proxies.
Connections live in memory; checkpoints contain historical evidence, never live grants.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import Field, field_validator, model_validator

from zhangwen.artifacts.models import ArtifactPreview, ArtifactPreviewKind, ArtifactStatus
from zhangwen.llm.contracts import ChatMessage, ChatMessageStatus, ChatRole
from .models import Boundary
from .programming_modes import board_mode
from .claw_legacy import LegacyChannel


class Record(Boundary):
    protocol: str | None = Field(default=None, pattern=r'^(session-v1|legacy-websocket)$')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    kind: str = Field(pattern=r'^(submission|device-history|observation)$')
    createdAt: str = Field(max_length=60)
    text: str = Field(max_length=16000)
    state: str | None = Field(default=None, pattern=r'^(pending|submitted|outcome-unknown|rejected)$')
    session: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    bootId: str | None = Field(default=None, min_length=1, max_length=100)
    runId: int | None = Field(default=None, ge=0, strict=True)
    taskRevision: int | None = Field(default=None, ge=1, strict=True)
    taskChecksum: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    role: str | None = Field(default=None, pattern=r'^(user|assistant|system|tool)$')
    files: list[str] = Field(default_factory=list,max_length=4)
    links: list[dict[str,str]] = Field(default_factory=list,max_length=16)

    @field_validator('files')
    @classmethod
    def file_paths(cls,value):
        if any(not re.fullmatch(r'/inbox/webim/[a-f0-9]{32}_[A-Za-z0-9._-]{1,100}',p) for p in value):raise ValueError('附件路径不匹配。')
        return value

    @field_validator('createdAt')
    @classmethod
    def date(cls, value):
        datetime.fromisoformat(value)
        return value


class Checkpoint(Boundary):
    schemaVersion: int = Field(default=1, ge=1, le=1, strict=True)
    records: list[Record] = Field(default_factory=list, max_length=400)

    @model_validator(mode='after')
    def bounded(self):
        if len({r.id for r in self.records}) != len(self.records):
            raise ValueError('Chat Coding记录ID重复。')
        if len(self.model_dump_json().encode()) > 2 * 1024 * 1024:
            raise ValueError('Chat Coding记录超过2MiB，未截断。')
        return self


class ConnectInput(Boundary):
    endpoint: str = Field(min_length=1, max_length=100)


class SendInput(Boundary):
    clientMessageId: str = Field(pattern=r'^[a-f0-9]{32}$')
    expectedRevision: int = Field(ge=1)
    files: list[str] = Field(default_factory=list,max_length=4)

    @field_validator('files')
    @classmethod
    def file_paths(cls,value):return Record.file_paths(value)


class ObserveInput(Boundary):
    text: str = Field(min_length=1, max_length=2000)


def endpoint_url(value):
    try:
        parsed = urlsplit(value.strip())
        ip = ipaddress.IPv4Address(parsed.hostname or '')
        private = any(ip in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
        if parsed.scheme != 'http' or not private or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment or (parsed.port is not None and parsed.port not in range(1, 65536)):
            raise ValueError()
        return f'http://{ip}' + (f':{parsed.port}' if parsed.port and parsed.port != 80 else '')
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, '请输入设备面板显示的局域网IPv4地址，如 http://192.168.1.20；不接受域名、路径或账号密码。') from exc


def now():
    return datetime.now(UTC).isoformat()


def load_checkpoint(repo, project_id):
    repo.get(project_id)
    with repo.connect() as conn:
        row = conn.execute('''SELECT v.version, v.preview_json FROM artifacts a
            JOIN artifact_versions v ON v.id=a.current_version_id WHERE a.id=? AND a.project_id=?''',
            (repo.artifact_id(project_id, 'chat_coding'), project_id)).fetchone()
    if not row:
        return 0, Checkpoint()
    return row['version'], Checkpoint.model_validate_json(json.loads(row['preview_json'])['code'])


def insert_checkpoint(repo, conn, project_id, checkpoint, revision=1):
    """Shared by runtime commits and the existing portable import transaction."""
    content = checkpoint.model_dump_json(exclude_none=True)
    source_id = uuid.uuid4().hex
    aid = f'zhangwen_chat_coding_{project_id}'
    vid = f'artifact_version_{aid}_{source_id}'
    stamp = now()
    preview = ArtifactPreview(kind=ArtifactPreviewKind.CODE, code=content, language='json', summary='设备Chat Coding回执与用户观察；不代表硬件成功。')
    conn.execute('''INSERT INTO artifacts (id,project_id,title,kind,status,source_agent_id,current_version_id,created_at,updated_at)
        VALUES (?,?,'Chat Coding记录','DOCUMENT','DRAFT','zhangwen-chat-coding',?,?,?)
        ON CONFLICT(id) DO UPDATE SET current_version_id=excluded.current_version_id,updated_at=excluded.updated_at''', (aid,project_id,vid,stamp,stamp))
    conn.execute('''INSERT INTO artifact_versions (id,artifact_id,project_id,version,status,mime_type,preview_json,dependencies_json,source_entity_type,source_entity_id,checksum,created_at)
        VALUES (?,?,?,?,'DRAFT','application/json',?,'[]','zhangwen_chat_coding',?,?,?)''',
        (vid,aid,project_id,revision,preview.model_dump_json(),source_id,hashlib.sha256(content.encode()).hexdigest(),stamp))
    repo.artifacts._apply_artifact_context(conn, artifact_id=aid, version_id=vid, project_id=project_id, source_agent_id='zhangwen-chat-coding', status=ArtifactStatus.DRAFT)


def insert_conversation_records(repo, conn, project_id, records):
    conversation_id = conn.execute('SELECT id FROM conversations WHERE project_id=? ORDER BY created_at LIMIT 1', (project_id,)).fetchone()[0]
    for record in records:
        # Original Conversation; separate channel from local AI, not executable tools.
        role = 'assistant' if record.kind == 'device-history' and record.role != 'user' else 'user'
        message = ChatMessage(id='msg_'+uuid.uuid4().hex, role=ChatRole(role), content=record.text,
            status=ChatMessageStatus.COMPLETED, createdAt=record.createdAt, updatedAt=record.createdAt,
            metadata={'chatCoding': True, 'recordId': record.id, 'kind': record.kind})
        repo.projects._insert_message(conn, conversation_id, project_id, message)


def commit(repo, project_id, records):
    with repo.lock:
        revision, previous = load_checkpoint(repo, project_id)
        checkpoint = Checkpoint(records=records)
        previous_ids = {r.id for r in previous.records}
        with repo.connect() as conn:
            insert_checkpoint(repo, conn, project_id, checkpoint, revision+1)
            insert_conversation_records(repo, conn, project_id, [r for r in checkpoint.records if r.id not in previous_ids])


class ClawClient:
    async def request(self, base, method, path, body=None):
        # All caller paths are constants or contain validated session hex/cursors.
        try:
            async with asyncio.timeout(16), httpx.AsyncClient(timeout=httpx.Timeout(12, connect=4), follow_redirects=False, trust_env=False) as client:
                async with client.stream(method, base+path, json=body) as response:
                    if not 200 <= response.status_code < 300:
                        raise HTTPException(502, f'设备接口返回HTTP {response.status_code}；请核对Claw固件与WebIM接口。')
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 512*1024:
                            raise HTTPException(502, '设备响应过大，未继续读取。')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except HTTPException:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise HTTPException(502, '无法连接设备地址。请核对电脑与Mosaico处于同一局域网、屏幕地址和端口；设备IP可能已变化。') from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise HTTPException(502, '设备响应超时，请检查网络或设备Web服务状态；发送结果未知时不会重发任务。') from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, '设备接口未返回有效JSON。请核对地址是否为Claw控制面板及固件状态。') from exc


class ChatCodingService:
    def __init__(self, repo, client=None, legacy_factory=None):
        self.repo = repo
        self.client = client or ClawClient()
        self.connections = {}
        self.locks = {}
        self.connection_lock = asyncio.Lock()
        self.legacy_factory = legacy_factory or LegacyChannel.open
        self.channels = {}
        self.readers = {}
        self.connection_errors = {}
        self.attachment_check = None

    def project(self, pid):
        project = self.repo.get(pid)
        if board_mode(self.repo, project['boardId']) != 'chat-coding':
            raise HTTPException(422, '此项目未选择Chat Coding主控。')
        return project

    def lock(self, pid):
        return self.locks.setdefault(pid, asyncio.Lock())

    def state(self, pid):
        self.project(pid)
        revision, cp = load_checkpoint(self.repo, pid)
        live = self.connections.get(pid, {})
        return {**cp.model_dump(exclude_none=True), 'revision': revision, 'connected': bool(live), **live,
                **({'connectionError':self.connection_errors[pid]} if pid in self.connection_errors else {})}

    async def connect(self, pid, endpoint):
        self.project(pid)
        base = endpoint_url(endpoint)
        async with self.connection_lock, self.lock(pid):
            if any(c['endpoint'] == base for p,c in self.connections.items() if p != pid):
                raise HTTPException(409, '此设备地址已被另一个掌问项目连接，请先在该项目断开。')
            if pid in self.connections:
                raise HTTPException(409, '请先断开当前连接，再连接设备；断开不会停止设备任务。')
            status = await self.client.request(base, 'GET', '/api/webim/status')
            basic = await self.client.request(base, 'GET', '/api/status')
            # Observed on the user's Mosaico: old firmware has no sessions API,
            # boot ID or persistent history. Never invent those capabilities.
            if ('boot_id' not in status and 'boot_id' not in basic and status.get('ok') is True
                    and type(status.get('bound')) is bool and type(basic.get('wifi_connected')) is bool
                    and basic.get('ip') == urlsplit(base).hostname):
                sid = uuid.uuid4().hex
                channel = await self.legacy_factory(base, sid)
                live = {'endpoint':base, 'bound':status['bound'], 'protocol':'legacy-websocket',
                        'session':sid, 'runState':'unavailable'}
                self.channels[pid] = channel
                self.connections[pid] = live
                self.connection_errors.pop(pid, None)
                self.readers[pid] = asyncio.create_task(self.read_legacy(pid, live, channel))
                return self.state(pid)
            sessions = await self.client.request(base, 'GET', '/api/webim/sessions?source=web&cursor=0')
            boot = status.get('boot_id')
            if not isinstance(boot, str) or not 1 <= len(boot) <= 100 or basic.get('boot_id') != boot or sessions.get('boot_id') != boot or type(status.get('bound')) is not bool or not isinstance(sessions.get('items'), list):
                raise HTTPException(502, '设备接口不匹配或连接时重启。需要支持会话API的Claw WebIM固件；未确认板型。')
            self.connections[pid] = {'endpoint':base, 'bootId':boot, 'bound':status['bound'], 'runState':'idle', 'protocol':'session-v1'}
            self.connection_errors.pop(pid, None)
        return self.state(pid)

    async def read_legacy(self, pid, live, channel):
        reason = '旧版实时通道已断开，请重新连接。断线期间的回复无法从设备补读，任务不会重发。'
        try:
            async for event in channel:
                # Legacy firmware broadcasts all chats. Never retain other chats.
                if event.get('chat_id') != live['session']:
                    continue
                if (event.get('role') != 'assistant' or type(event.get('seq')) is not int
                        or event['seq'] <= 0 or not isinstance(event.get('text'), str)):
                    raise ValueError('Invalid legacy reply')
                async with self.lock(pid):
                    if self.connections.get(pid) is not live:
                        return
                    _, cp = load_checkpoint(self.repo, pid)
                    rid = f"device_{live['session']}_{event['seq']}"
                    previous = next((r for r in cp.records if r.id == rid), None)
                    if previous:
                        if previous.text != event['text']:
                            raise ValueError('Legacy sequence changed')
                        continue
                    sequences = [int(r.id.rsplit('_',1)[1]) for r in cp.records
                                 if r.kind == 'device-history' and r.session == live['session']]
                    if sequences and event['seq'] <= max(sequences):
                        raise ValueError('Legacy sequence reset')
                    links=[]
                    for item in event.get('links',[])[:16]:
                        if isinstance(item,dict) and isinstance(item.get('url'),str) and isinstance(item.get('label',''),str):
                            # Only native file paths; never execute or proxy an Agent URL.
                            url=item['url']
                            if re.fullmatch(r'/files/(?!.*(?:\.\.|[\\%?#\x00-\x1f]))[^ ]{1,230}',url):links.append({'url':url,'label':item.get('label','')[:200]})
                    record = Record(id=rid, kind='device-history', createdAt=now(), text=event['text'],links=links,
                                    session=live['session'], role='assistant', protocol='legacy-websocket')
                    commit(self.repo, pid, [*cp.records, record])
        except asyncio.CancelledError:
            raise
        except Exception:
            reason = '旧版实时回复未能完整读取或保存，已断开并保留原记录。请核对设备面板；不会重发任务。'
        finally:
            if self.connections.get(pid) is live:
                self.connections.pop(pid, None)
                self.connection_errors[pid] = reason
            if self.channels.get(pid) is channel:
                self.channels.pop(pid, None)
                self.readers.pop(pid, None)
            await channel.close()

    async def disconnect(self, pid):
        async with self.lock(pid):
            self.connections.pop(pid, None)
            self.connection_errors.pop(pid, None)
            channel = self.channels.pop(pid, None)
            reader = self.readers.pop(pid, None)
        if reader:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        if channel:
            await channel.close()

    async def close(self):
        for pid in list(self.connections.keys() | self.channels.keys()):
            await self.disconnect(pid)

    async def check_boot(self, pid):
        live = self.connections.get(pid)
        if not live:
            raise HTTPException(409, '请先连接设备。')
        status = await self.client.request(live['endpoint'], 'GET', '/api/webim/status')
        if live.get('protocol') == 'legacy-websocket':
            channel = self.channels.get(pid)
            if (not channel or channel.closed or status.get('ok') is not True or 'boot_id' in status):
                raise HTTPException(409, '旧版实时通道或协议已变化，请断开后重新连接；任务未发送。')
            if status.get('bound') is not True:
                raise HTTPException(409, '设备Web聊天通道未绑定，请在设备原生面板完成配置。')
            return live
        if status.get('boot_id') != live['bootId']:
            self.connections.pop(pid, None)
            raise HTTPException(409, '设备启动标识变化，已断开；请核对实物并重新连接，不会重发任务。')
        if status.get('bound') is not True:
            raise HTTPException(409, '设备Web聊天通道未绑定，请在设备原生面板完成配置。')
        return live

    async def send(self, pid, request):
        async with self.lock(pid):
            project = self.project(pid)
            if project['revision'] != request.expectedRevision:
                raise HTTPException(409, '任务版本已改变，请重新保存和核对。')
            text = project['code'].strip()
            if not text or len(text.encode()) > 4000:
                raise HTTPException(422, '任务须为1到4000字节的已保存文本。')
            _, cp = load_checkpoint(self.repo, pid)
            # Persistent deduplication survives service restarts; never replay a write.
            old = next((r for r in cp.records if r.id == request.clientMessageId), None)
            if old:
                if old.kind != 'submission' or old.text != text or old.files != request.files:
                    raise HTTPException(409, '同一任务标识对应的内容不同。')
                return self.state(pid)
            if len(cp.records) > 390:
                raise HTTPException(409, '记录接近容量上限，请另建项目；原记录未截断。')
            live = await self.check_boot(pid)
            legacy = live.get('protocol') == 'legacy-websocket'
            if not legacy and live.get('runState') != 'idle':
                raise HTTPException(409, '设备会话仍在处理，请先刷新状态。')
            if any(r.kind == 'submission' and r.session == live.get('session') and r.state in {'pending','outcome-unknown'} for r in cp.records):
                raise HTTPException(409, '上次发送结果未知，请在设备面板核对；不会自动重发。')
            base = live['endpoint']
            if request.files:
                if not self.attachment_check:raise HTTPException(409,'当前连接不支持附件上传。')
                await self.attachment_check(pid,base,request.files)
            if legacy:
                record = Record(id=request.clientMessageId, kind='submission', createdAt=now(), text=text,
                                state='pending', session=live['session'], taskRevision=project['revision'],
                                taskChecksum=project['checksum'], protocol='legacy-websocket',files=request.files)
                records = [*cp.records, record]
                commit(self.repo, pid, records)
                try:
                    result = await self.client.request(base, 'POST', '/api/webim/send',
                                                       {'chat_id':live['session'], 'text':text, 'files':request.files})
                    if result.get('ok') is not True:
                        raise ValueError('Invalid legacy receipt')
                    record.state = 'submitted'
                except BaseException:
                    record.state = 'outcome-unknown'
                    commit(self.repo, pid, records)
                    raise HTTPException(502, '旧版任务可能已到达设备，结果未知。请核对设备，不要重复发送。')
                commit(self.repo, pid, records)
                return self.state(pid)
            if not live.get('session'):
                session = await self.client.request(base, 'POST', '/api/webim/sessions', {})
                sid = session.get('session')
                if not isinstance(sid,str) or not re.fullmatch('[a-f0-9]{32}',sid) or session.get('boot_id') != live['bootId'] or session.get('can_send') is not True or session.get('run_state') != 'idle' or session.get('reply_channel') != 'web':
                    raise HTTPException(502, '设备新会话接口不匹配或尚不可发送，任务未发送。')
                live['session'] = sid
            # Recheck after session creation; an existing session may have changed state.
            info = await self.client.request(base, 'GET', '/api/webim/sessions/'+live['session'])
            if info.get('boot_id') != live['bootId'] or info.get('session') != live['session'] or info.get('can_send') is not True or info.get('run_state') != 'idle':
                raise HTTPException(409, '设备会话身份或状态已改变，任务未发送。')
            record = Record(id=request.clientMessageId,kind='submission',createdAt=now(),text=text,state='pending',session=live['session'],bootId=live['bootId'],taskRevision=project['revision'],taskChecksum=project['checksum'],files=request.files)
            records = [*cp.records, record]
            commit(self.repo,pid,records)  # Persist intent before any device submission.
            try:
                result = await self.client.request(base,'POST','/api/webim/send',{'session':live['session'],'client_message_id':record.id,'text':text,'files':request.files})
                if result.get('boot_id') != live['bootId'] or result.get('client_message_id') != record.id or type(result.get('run_id')) is not int or result['run_id'] < 0 or result.get('state') != 'queued':
                    raise HTTPException(502,'设备回执不匹配。')
                record.state='submitted';record.runId=result['run_id'];live['runState']='queued'
            except BaseException:
                record.state='outcome-unknown'
                commit(self.repo,pid,records)
                raise HTTPException(502,'任务可能已到达设备，发送结果未知。请刷新会话或到设备面板核对，不要重复发送。')
            commit(self.repo,pid,records)
        return self.state(pid)

    async def sync(self,pid):
        async with self.lock(pid):
            self.project(pid)
            live=await self.check_boot(pid)
            if live.get('protocol') == 'legacy-websocket':
                # The reader already persists live events. No history API exists.
                return self.state(pid)
            if not live.get('session'):
                return self.state(pid)
            _,cp=load_checkpoint(self.repo,pid)
            records=list(cp.records); known={r.id:r for r in records}; cursor=0
            for page in range(4):
                data=await self.client.request(live['endpoint'],'GET',f"/api/webim/sessions/{live['session']}/messages?before={cursor}&limit=50")
                if data.get('boot_id') != live['bootId'] or data.get('run_state') not in {'idle','queued','running'} or not isinstance(data.get('messages'),list) or type(data.get('has_more')) is not bool:
                    raise HTTPException(502,'设备会话记录格式或启动标识变化，未更新本机证据。')
                for m in data['messages']:
                    if not isinstance(m,dict) or type(m.get('seq')) is not int or m['seq']<0 or m.get('role') not in {'user','assistant','system','tool'} or not isinstance(m.get('text'),str):
                        raise HTTPException(502,'设备消息格式不匹配。')
                    rid=f"device_{live['session']}_{m['seq']}"
                    if rid not in known:
                        record=Record(id=rid,kind='device-history',createdAt=now(),text=m['text'],session=live['session'],bootId=live['bootId'],role=m['role'])
                        records.append(record);known[rid]=record
                    elif known[rid].text != m['text']:
                        raise HTTPException(409,'设备历史消息发生变化，保留原证据。')
                live['runState']=data['run_state']
                if not data['has_more']:
                    break
                next_cursor=data.get('next_before')
                if type(next_cursor) is not int or next_cursor<=0 or (cursor and next_cursor>=cursor):
                    raise HTTPException(502,'设备历史分页游标无效。')
                cursor=next_cursor
            else:
                raise HTTPException(413,'设备会话超过本次读取上限，请在原生面板查看完整记录；本机记录未截断。')
            if records != cp.records:
                commit(self.repo,pid,records)
        return self.state(pid)


def router(service):
    route=APIRouter(prefix='/api/projects/{pid}/chat-coding')

    @route.get('')
    def state(pid:str):
        return service.state(pid)

    @route.post('/connect')
    async def connect(pid:str,request:ConnectInput):
        return await service.connect(pid,request.endpoint)

    @route.post('/disconnect')
    async def disconnect(pid:str):
        service.project(pid)
        await service.disconnect(pid)
        return service.state(pid)

    @route.post('/send')
    async def send(pid:str,request:SendInput):
        return await service.send(pid,request)

    @route.post('/sync')
    async def sync(pid:str):
        return await service.sync(pid)

    @route.post('/observations')
    async def observe(pid:str,request:ObserveInput):
        async with service.lock(pid):
            service.project(pid)
            if not request.text.strip():raise HTTPException(422,'请填写实际观察。')
            _,cp=load_checkpoint(service.repo,pid)
            commit(service.repo,pid,[*cp.records,Record(id=uuid.uuid4().hex,kind='observation',createdAt=now(),text=request.text.strip())])
        return service.state(pid)
    return route
