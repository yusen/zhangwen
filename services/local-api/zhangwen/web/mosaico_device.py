"""Fixed Mosaico management APIs for explicit user controls, never model tools.

Wire reference: esp-claw f95614dc and the user's native frontend. No arbitrary
URL proxy, shell, auto-retry, firmware endpoint, recursive or root deletion.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import re
import tarfile
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

import aiohttp
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import Field, field_validator

from .models import Boundary
from .chat_coding import endpoint_url
from .claw_legacy import deny_redirect
from .programming_modes import board_mode
from zhangwen.artifacts.models import ArtifactPreview, ArtifactPreviewKind, ArtifactStatus

MAX_FILE = 1_000_000
GROUPS = {'basic':'wifi,time', 'llm':'llm', 'asr':'asr', 'im':'im', 'search':'search',
          'capabilities':'capabilities', 'skills':'skills'}
FIELDS = {
 'basic': 'wifi_ssid wifi_password time_timezone',
 'llm': 'llm_api_key llm_backend_type llm_profile llm_model llm_base_url llm_auth_type llm_timeout_ms llm_max_tokens llm_max_tokens_field llm_reasoning_effort llm_supports_tools llm_supports_vision llm_default_image_max_bytes llm_image_remote_url_only',
 'asr': 'asr_api_key asr_endpoint asr_language_hint asr_model asr_provider asr_workspace_id',
 'im': 'qq_app_id qq_app_secret feishu_app_id feishu_app_secret tg_bot_token wechat_token wechat_base_url wechat_cdn_base_url wechat_account_id',
 'search': 'search_brave_key search_tavily_key search_http_allowlist',
 'capabilities': 'enabled_cap_groups llm_visible_cap_groups', 'skills': 'enabled_lua_modules',
}
SECRET = {k for fields in FIELDS.values() for k in fields.split() if any(t in k for t in ('password','api_key','secret','bot_token','wechat_token','brave_key','tavily_key'))}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_path(value):
    if (not isinstance(value,str) or len(value.encode()) > 240 or not value.startswith('/')
            or re.search(r'[\\\x00-\x1f\x7f?#%]', value)
            or any(p in {'.','..',''} for p in value.split('/')[1:]) and value != '/'):
        raise HTTPException(422, '设备路径须为根目录内的绝对路径，不能包含上级目录或转义字符。')
    return value


@dataclass
class Reply:
    status: int
    body: bytes

    def json(self):
        try:
            value=json.loads(self.body)
            if not isinstance(value,dict): raise ValueError()
            return value
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(502,'设备返回格式不匹配。') from exc


class NativeClient:
    async def request(self, base, method, path, *, data=None, content=None):
        try:
            async with asyncio.timeout(20), httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=httpx.Timeout(16,connect=4)) as client:
                async with client.stream(method,base+path,json=data,content=content) as response:
                    if response.status_code not in {200,201,204,404}:
                        raise HTTPException(502,f'设备接口返回HTTP {response.status_code}，未自动重试。')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw)>MAX_FILE:raise HTTPException(413,'设备响应超过1 MB，未截断后冒充完整内容。')
                    return Reply(response.status_code,bytes(raw))
        except HTTPException:raise
        except (httpx.HTTPError,TimeoutError) as exc:
            raise HTTPException(502,'设备连接失败或超时，请核对局域网与地址。写入结果未知时不会自动重试。') from exc


class LogChannel:
    @classmethod
    async def open(cls,base):
        trace=aiohttp.TraceConfig();trace.on_request_redirect.append(deny_redirect)
        session=aiohttp.ClientSession(trust_env=False,trace_configs=[trace],timeout=aiohttp.ClientTimeout(total=8,connect=4))
        try:
            socket=await asyncio.wait_for(session.ws_connect(base+'/ws/logs',heartbeat=15,max_msg_size=65536,timeout=aiohttp.ClientWSTimeout(ws_close=2)),8)
            channel=cls();channel.session=session;channel.socket=socket;return channel
        except BaseException:
            await session.close();raise

    async def __aiter__(self):
        async for event in self.socket:
            if event.type==aiohttp.WSMsgType.TEXT:yield event.data
            elif event.type in {aiohttp.WSMsgType.BINARY,aiohttp.WSMsgType.ERROR}:raise ValueError('Invalid log frame')

    async def close(self):
        try:await self.socket.close()
        finally:await self.session.close()


class Connect(Boundary):
    endpoint: str = Field(max_length=200)


class Operation(Boundary):
    connectionId: str = Field(pattern='^[a-f0-9]{32}$')
    requestId: str = Field(pattern='^[a-f0-9]{32}$')


class ConfigSave(Operation):
    section: str
    revision: str = Field(pattern='^[a-f0-9]{64}$')
    patch: dict[str,str]


class FileWrite(Operation):
    projectId: str
    path: str
    content: str = Field(max_length=1_340_000)
    expectedChecksum: str | None = Field(default=None,pattern='^[a-f0-9]{64}$')

    @field_validator('path')
    @classmethod
    def valid_path(cls,value):return file_path(value)

    @field_validator('content')
    @classmethod
    def valid_content(cls,value):
        try:raw=base64.b64decode(value,validate=True)
        except (ValueError,TypeError) as exc:raise ValueError('文件编码不正确。') from exc
        if not 0<len(raw)<=MAX_FILE:raise ValueError('文件须为1字节至1 MB。')
        return value


class PathWrite(Operation):
    path: str
    @field_validator('path')
    @classmethod
    def valid_path(cls,value):return file_path(value)


class FileDelete(PathWrite):
    projectId: str
    expectedChecksum: str = Field(pattern='^[a-f0-9]{64}$')


class DirectoryDelete(PathWrite):
    projectId: str


class WechatStart(Operation):
    accountId: str = Field(default='',max_length=100)


class MosaicoService:
    def __init__(self,repo,chat,client=None,log_factory=None):
        self.repo=repo;self.chat=chat;self.client=client or NativeClient();self.log_factory=log_factory or LogChannel.open
        self.endpoint=None;self.connection_id=None;self.basic={};self.unknown=None
        self.lock=asyncio.Lock();self.operations={};self.logs=deque(maxlen=1000);self.log_seq=0
        self.log_channel=None;self.log_reader=None;self.log_error='';self.logs_dropped=0
        self.fingerprints={};self.attachments={}

    def state(self):
        return {'connected':bool(self.endpoint),**({'endpoint':self.endpoint,'connectionId':self.connection_id,'status':self.basic} if self.endpoint else {}),**({'unknownWrite':self.unknown} if self.unknown else {})}

    def target(self,connection_id=None):
        if not self.endpoint or (connection_id is not None and connection_id!=self.connection_id):
            raise HTTPException(409,'设备连接已改变，请重新核对连接。')
        return self.endpoint

    async def json(self,path,method='GET',data=None):
        base=self.target();generation=self.connection_id
        reply=await self.client.request(base,method,path,data=data)
        if generation!=self.connection_id:raise HTTPException(409,'读取期间连接已改变。')
        if reply.status==404:raise HTTPException(404,'当前固件未提供此功能。')
        return reply.json()

    async def connect(self,endpoint):
        base=endpoint_url(endpoint)
        async with self.lock:
            if self.endpoint:raise HTTPException(409,'请先断开当前设备再连接。')
            basic=(await self.client.request(base,'GET','/api/status')).json()
            web=(await self.client.request(base,'GET','/api/webim/status')).json()
            if not isinstance(basic.get('wifi_connected'),bool) or type(web.get('bound')) is not bool:
                raise HTTPException(502,'不是兼容的Mosaico WebIM管理接口。')
            self.endpoint=base;self.connection_id=uuid.uuid4().hex;self.basic=basic;self.unknown=None
        return self.state()

    async def disconnect(self):
        async with self.lock:
            base=self.endpoint
            await self.stop_logs()
            self.endpoint=None;self.connection_id=None;self.basic={};self.unknown=None
            for pid,live in list(self.chat.connections.items()):
                if live['endpoint']==base:await self.chat.disconnect(pid)
        return self.state()

    async def config_raw(self,section):
        if section not in GROUPS:raise HTTPException(422,'未知配置分组。')
        raw=await self.json('/api/config?groups='+GROUPS[section])
        return {k:v for k,v in raw.items() if k in FIELDS[section].split() and isinstance(v,str)}

    async def config(self,section):
        raw=await self.config_raw(section)
        return {'section':section,'revision':digest(json.dumps(raw,sort_keys=True,ensure_ascii=False).encode()),
                'values':{k:v for k,v in raw.items() if k not in SECRET},'available':list(raw),
                'secrets':[k for k,v in raw.items() if k in SECRET and v]}

    async def apply(self,request,prepare,mutate,scope=''):
        async with self.lock:
            self.target(request.connectionId)
            key=(request.connectionId,request.requestId)
            fingerprint=digest((scope+type(request).__name__+request.model_dump_json()).encode())
            if key in self.operations:
                if self.fingerprints[key]!=fingerprint:raise HTTPException(409,'同一操作标识对应的内容不同，未提交。')
                old=self.operations[key]
                if isinstance(old,dict):return old
                raise HTTPException(409,'此操作已提交且结果未知，不会重发。请先读取设备当前状态。')
            if self.unknown:raise HTTPException(409,'上次设备写入结果未知，请先核对当前状态并断开后重新连接；不会重发。')
            if len(self.operations)>=1000:raise HTTPException(409,'本次服务操作记录已满，请保存项目后重启本机服务。')
            prepared=await prepare()
            self.fingerprints[key]=fingerprint
            self.operations[key]='unknown'
            try:
                result=await mutate(prepared)
                self.operations[key]=result
                return result
            except BaseException as exc:
                self.unknown='上次写入可能已到达设备，结果未知。请读取设备当前状态并核对，不要重复提交。'
                if isinstance(exc,asyncio.CancelledError):raise
                raise HTTPException(502,self.unknown) from exc

    async def save_config(self,request):
        async def prepare():
            raw=await self.config_raw(request.section)
            if digest(json.dumps(raw,sort_keys=True,ensure_ascii=False).encode())!=request.revision:
                raise HTTPException(409,'设备配置已被其他页面修改，请重新读取后合并。')
            if not request.patch or any(k not in raw or not isinstance(v,str) or len(v.encode())>8000 or '\0' in v for k,v in request.patch.items()):
                raise HTTPException(422,'配置仅能修改当前固件提供的字段。')
            if 'wifi_ssid' in request.patch and not request.patch['wifi_ssid'].strip():raise HTTPException(422,'Wi-Fi名称不能为空。')
            if request.patch.get('wifi_password') and len(request.patch['wifi_password'])<8:raise HTTPException(422,'Wi-Fi密码至少8位。')
            return None
        async def mutate(_):
            result=await self.json('/api/config','POST',request.patch)
            if result.get('ok') is not True:raise ValueError('No receipt')
            current=await self.config_raw(request.section)
            if any(current.get(k)!=v for k,v in request.patch.items()):raise ValueError('Readback differs')
            return {'state':'verified','message':'设备已保存，回读一致。需重启生效的配置请在核对后手动重启。'}
        return await self.apply(request,prepare,mutate,'config')

    async def read_file(self,path):
        path=file_path(path)
        generation=self.connection_id
        reply=await self.client.request(self.target(),'GET','/files'+quote(path,safe='/'))
        if generation!=self.connection_id:raise HTTPException(409,'读取期间连接已改变。')
        return None if reply.status==404 else reply.body

    def project(self,pid):
        p=self.repo.get(pid)
        if board_mode(self.repo,p['boardId'])!='chat-coding':raise HTTPException(422,'文件写入的备份须关联已保存的Mosaico项目。')

    def backup(self,pid,path,content,operation):
        self.project(pid)
        # Original Artifact version history, outside project upload manifests and AI.
        aid='zhangwen_mosaico_backups_'+pid;bid=uuid.uuid4().hex;vid='artifact_version_'+bid
        stamp=datetime.now(UTC).isoformat()
        payload=json.dumps({'path':path,'exists':content is not None,'content':base64.b64encode(content or b'').decode(),
                            'sha256':digest(content) if content is not None else None,'operation':operation,'createdAt':stamp},ensure_ascii=False)
        preview=ArtifactPreview(kind=ArtifactPreviewKind.CODE,code=payload,language='json',summary='Mosaico显式文件操作前的原始备份，不属于上传清单。')
        with self.repo.lock,self.repo.connect() as conn:
            version=conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?',(aid,)).fetchone()[0]
            conn.execute("""INSERT INTO artifacts(id,project_id,title,kind,status,source_agent_id,current_version_id,created_at,updated_at)
              VALUES (?,?,'Mosaico文件备份','DOCUMENT','DRAFT','zhangwen-mosaico',?,?,?)
              ON CONFLICT(id) DO UPDATE SET current_version_id=excluded.current_version_id,updated_at=excluded.updated_at""",(aid,pid,vid,stamp,stamp))
            conn.execute("""INSERT INTO artifact_versions(id,artifact_id,project_id,version,status,mime_type,preview_json,dependencies_json,source_entity_type,source_entity_id,checksum,created_at)
              VALUES(?,?,?,?,'DRAFT','application/json',?,'[]','zhangwen_mosaico_backup',?,?,?)""",(vid,aid,pid,version,preview.model_dump_json(),bid,digest(payload.encode()),stamp))
            self.repo.artifacts._apply_artifact_context(conn,artifact_id=aid,version_id=vid,project_id=pid,source_agent_id='zhangwen-mosaico',status=ArtifactStatus.DRAFT)
        return vid

    def backups(self,pid):
        self.project(pid)
        with self.repo.connect() as conn:
            rows=conn.execute("SELECT id,preview_json FROM artifact_versions WHERE project_id=? AND source_entity_type='zhangwen_mosaico_backup' ORDER BY created_at DESC LIMIT 100",(pid,)).fetchall()
        items=[];total=0
        for row in rows:
            value={'id':row['id'],**json.loads(json.loads(row['preview_json'])['code'])}
            total+=len(value['content'])
            if total>8_000_000:break
            items.append(value)
        return items

    async def archive(self,path):
        root=file_path(path);generation=self.connection_id;buffer=io.BytesIO();total=0;count=0
        async def walk(folder,depth,archive):
            nonlocal total,count
            if depth>8:raise HTTPException(413,'目录超过8层，请分目录下载。')
            listing=await self.json('/api/files?path='+quote(folder,safe=''))
            for entry in listing.get('entries',[]):
                child=file_path(entry['path']);prefix=folder.rstrip('/')+'/'
                if not child.startswith(prefix) or '/' in child[len(prefix):]:raise HTTPException(502,'设备目录响应不匹配。')
                count+=1
                if count>200:raise HTTPException(413,'目录超过200项，请分目录下载。')
                name=child[len(root.rstrip('/'))+1:]
                item=tarfile.TarInfo(name)
                if entry['is_dir']:
                    item.type=tarfile.DIRTYPE;archive.addfile(item);await walk(child,depth+1,archive)
                else:
                    raw=await self.read_file(child)
                    if raw is None:raise HTTPException(409,'下载期间文件已改变，请重新读取。')
                    total+=len(raw)
                    if total>8_000_000:raise HTTPException(413,'目录超过8 MB，请分目录下载。')
                    item.size=len(raw);archive.addfile(item,io.BytesIO(raw))
        async with asyncio.timeout(60):
            with tarfile.open(fileobj=buffer,mode='w') as archive:await walk(root,0,archive)
        if generation!=self.connection_id:raise HTTPException(409,'打包期间设备连接已改变，未返回混合内容。')
        return {'content':base64.b64encode(buffer.getvalue()).decode(),'encoding':'base64'}

    async def delete_directory(self,request):
        async def prepare():
            self.project(request.projectId)
            if request.path=='/':raise HTTPException(422,'不能删除根目录。')
            listing=await self.json('/api/files?path='+quote(request.path,safe=''))
            if listing.get('entries')!=[]:raise HTTPException(409,'只可删除空目录，请先逐个备份处理文件。')
            return self.backup(request.projectId,request.path,None,'delete-empty-directory')
        async def mutate(backup):
            result=await self.json('/api/files?path='+quote(request.path,safe=''),'DELETE')
            if result.get('ok') is not True:raise ValueError()
            parent=request.path.rsplit('/',1)[0] or '/'
            listing=await self.json('/api/files?path='+quote(parent,safe=''))
            if any(e['path']==request.path for e in listing.get('entries',[])):raise ValueError()
            return {'state':'verified','backupId':backup,'message':'空目录已删除并核对，目录路径已记录到项目备份。'}
        return await self.apply(request,prepare,mutate,'directory-delete')

    async def attachment(self,request):
        if not re.fullmatch(r'/inbox/webim/[a-f0-9]{32}_[A-Za-z0-9._-]{1,100}',request.path):raise HTTPException(422,'附件路径不匹配。')
        # Explicit upload also creates its native inbox. No work on page load.
        async def prepare():
            self.project(request.projectId)
            raw=base64.b64decode(request.content,validate=True)
            if not 0<len(raw)<=MAX_FILE:raise HTTPException(422,'附件须为1字节至1 MB。')
            if await self.read_file(request.path) is not None:raise HTTPException(409,'附件路径已有文件。')
            return raw,self.backup(request.projectId,request.path,None,'chat-attachment')
        async def mutate(prepared):
            raw,bid=prepared
            result=await self.json('/api/files/mkdir','POST',{'path':'/inbox/webim','recursive':True})
            if result.get('ok') is not True:raise ValueError()
            result=(await self.client.request(self.target(),'POST','/api/files/upload?path='+quote(request.path,safe=''),content=raw)).json()
            if result.get('ok') is not True or await self.read_file(request.path)!=raw:raise ValueError()
            self.attachments[(request.projectId,request.path)]=(self.target(),digest(raw))
            return {'path':request.path,'state':'verified','backupId':bid,'message':'附件已上传并回读，尚未发送给设备Agent。'}
        return await self.apply(request,prepare,mutate,'attachment')

    async def check_attachments(self,pid,base,paths):
        for path in paths:
            known=self.attachments.get((pid,path))
            if not known or known[0]!=base or self.target()!=base:raise HTTPException(409,'附件不属于当前项目连接，请重新上传。')
            raw=await self.read_file(path)
            if raw is None or digest(raw)!=known[1]:raise HTTPException(409,'附件已改变，请重新上传并核对。')

    async def write_file(self,request,delete=False):
        backup_id=None
        async def prepare():
            nonlocal backup_id
            if request.path=='/':raise HTTPException(422,'不能写入或删除设备根目录。')
            current=await self.read_file(request.path)
            if (digest(current) if current is not None else None)!=request.expectedChecksum:
                raise HTTPException(409,'设备文件已变化，请重新读取再保存；未覆盖。')
            raw=None if delete else base64.b64decode(request.content,validate=True)
            if not delete and (not raw or len(raw)>MAX_FILE):raise HTTPException(422,'文件须为1字节至1 MB。')
            backup_id=self.backup(request.projectId,request.path,current,'delete' if delete else 'write')
            return raw
        async def mutate(raw):
            base=self.target()
            if delete:
                reply=await self.client.request(base,'DELETE','/api/files?path='+quote(request.path,safe=''))
            else:
                reply=await self.client.request(base,'POST','/api/files/upload?path='+quote(request.path,safe=''),content=raw)
            if reply.json().get('ok') is not True:raise ValueError('No receipt')
            after=await self.read_file(request.path)
            if (delete and after is not None) or (not delete and after!=raw):raise ValueError('Readback differs')
            return {'state':'verified','backupId':backup_id,'sha256':digest(raw) if raw is not None else None,'message':'设备文件已删除并核对。' if delete else '设备已写入，回读校验通过；运行和实物效果需另行观察。'}
        try:return await self.apply(request,prepare,mutate)
        except (ValueError,TypeError) as exc:raise HTTPException(422,'文件编码不正确。') from exc

    async def simple_write(self,request,path,data=None):
        async def prepare():
            if path=='/api/files/mkdir' and request.path=='/':raise HTTPException(422,'根目录已存在。')
        async def mutate(_):
            result=await self.json(path,'POST',data)
            if result.get('ok') is not True:raise ValueError('No receipt')
            return result
        return await self.apply(request,prepare,mutate,path)

    async def start_logs(self):
        async with self.lock:
            if self.log_reader:return self.log_state()
            status=await self.json('/api/logs/status')
            if status.get('enabled') is not True:raise HTTPException(409,'设备未启用实时日志，请在设备Debug设置启用后再读取。')
            try:self.log_channel=await self.log_factory(self.target())
            except Exception as exc:raise HTTPException(502,'实时日志通道无法连接。') from exc
            self.logs.clear();self.logs_dropped=0;self.log_error=''
            self.log_reader=asyncio.create_task(self.read_logs(self.log_channel))
            return self.log_state()

    async def read_logs(self,channel):
        try:
            async for text in channel:
                if not isinstance(text,str) or len(text)>65536:raise ValueError()
                self.log_seq+=1
                if len(self.logs)==self.logs.maxlen:self.logs_dropped+=1
                self.logs.append({'seq':self.log_seq,'text':text})
        except asyncio.CancelledError:raise
        except Exception:self.log_error='日志读取中断；不会自动重连。'
        finally:
            await channel.close()
            if self.log_channel is channel:
                if not self.log_error:self.log_error='实时日志已断开；需要时手动开始读取。'
                self.log_channel=None;self.log_reader=None

    def log_state(self):
        return {'active':self.log_reader is not None,'entries':list(self.logs),'dropped':self.logs_dropped,'error':self.log_error}

    async def stop_logs(self):
        reader=self.log_reader;self.log_reader=None
        if reader:reader.cancel();await asyncio.gather(reader,return_exceptions=True)
        if self.log_channel:await self.log_channel.close();self.log_channel=None
        return self.log_state()


def router(service):
    route=APIRouter(prefix='/api/mosaico')
    @route.get('')
    def state():return service.state()
    @route.post('/connect')
    async def connect(request:Connect):return await service.connect(request.endpoint)
    @route.post('/disconnect')
    async def disconnect():return await service.disconnect()
    @route.get('/status')
    async def status():
        service.basic=await service.json('/api/status');return service.state()
    @route.get('/config/{section}')
    async def config(section:str):return await service.config(section)
    @route.post('/config')
    async def save(request:ConfigSave):return await service.save_config(request)
    @route.get('/capabilities')
    async def capabilities():return await service.json('/api/capabilities')
    @route.get('/skills')
    async def skills():return await service.json('/api/lua-modules')
    @route.get('/files')
    async def files(path:str='/'):return await service.json('/api/files?path='+quote(file_path(path),safe=''))
    @route.get('/file')
    async def read(path:str):
        raw=await service.read_file(path)
        return {'path':path,'content':base64.b64encode(raw or b'').decode(),'sha256':digest(raw) if raw is not None else None,'size':len(raw or b''),'encoding':'base64','missing':raw is None}
    @route.get('/archive')
    async def archive(path:str='/'):return await service.archive(path)
    @route.post('/directory-delete')
    async def delete_directory(request:DirectoryDelete):return await service.delete_directory(request)
    @route.post('/attachment')
    async def attachment(request:FileWrite):return await service.attachment(request)
    @route.post('/file')
    async def write(request:FileWrite):return await service.write_file(request)
    @route.post('/file-delete')
    async def delete(request:FileDelete):return await service.write_file(request,delete=True)
    @route.post('/mkdir')
    async def mkdir(request:PathWrite):return await service.simple_write(request,'/api/files/mkdir',{'path':request.path})
    @route.get('/backups/{pid}')
    def backups(pid:str):return {'items':service.backups(pid)}
    @route.get('/wechat')
    async def wechat():return await service.json('/api/wechat/login/status')
    @route.post('/wechat/start')
    async def start(request:WechatStart):return await service.simple_write(request,'/api/wechat/login/start',{'account_id':request.accountId,'force':True})
    @route.post('/wechat/cancel')
    async def cancel(request:Operation):return await service.simple_write(request,'/api/wechat/login/cancel')
    @route.post('/restart')
    async def restart(request:Operation):
        result=await service.simple_write(request,'/api/restart')
        await service.disconnect()
        return {'state':'accepted','message':'设备接收了重启请求，掌问已断开；请等设备启动后手动重新连接。'}
    @route.get('/logs')
    def logs():return service.log_state()
    @route.post('/logs/start')
    async def start_logs():return await service.start_logs()
    @route.post('/logs/stop')
    async def stop_logs():return await service.stop_logs()
    return route
