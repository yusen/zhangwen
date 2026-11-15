"""Explicit WiFi setup and fixed Lua HTTP runner. No model/native Agent calls.

Reference esp-claw 519bd95900d29bfc9daf3619ff779753e3153f05.
Installing startup support, rebooting, uploading and running are separate actions.
"""
import base64
import hashlib
import json
import re
import uuid
from typing import Literal
from fastapi import HTTPException
from pydantic import Field

from . import lua_coding as lua
from .mosaico_device import Operation, FileWrite

BRIDGE_PATH='/scripts/zhangwen_wifi_bridge.lua'
RULE_PATH='/router_rules/router_rules.json'
PROTOCOL='zhangwen-wifi-lua/v1'
API='/api/lua/zhangwen'
TERMINAL={'done','failed','timeout','stopped','rejected'}


def bridge_source():
    from .hardware import RELEASE_CATALOG
    return (RELEASE_CATALOG.parent/'mosaico/zhangwen_wifi_bridge.lua').read_text(encoding='utf-8')


def checksum(raw):return hashlib.sha256(raw).hexdigest() if raw is not None else None


async def identity(service):
    status=await service.json('/api/status')
    if not re.fullmatch('[a-f0-9]{16}',str(status.get('boot_id',''))):
        raise HTTPException(409,'WiFi运行需要新版Claw的启动标识，请核对固件。')
    root=status.get('storage_base_path','')
    if not re.fullmatch(r'/(?:nand|fatfs|sdcard|data)(?:/data)?',root):
        raise HTTPException(409,'未识别当前固件的DATA存储路径，未写入或执行。')
    return status


async def status(service):
    device=await identity(service)
    reply=await service.client.request(service.target(),'GET',API+'/info')
    if reply.status==404:
        bridge=await service.read_file(BRIDGE_PATH)
        installed=checksum(bridge)==lua.sha(bridge_source())
        return {'ready':False,'serviceReady':False,'phase':'needs-restart' if installed else 'needs-install','bootId':device['boot_id'],
                'message':'运行服务文件已安装，但接口尚未启动。请确认启动规则已安装，再重启设备并重新连接。' if installed else '尚未安装WiFi运行服务。请先查看初始化清单并安装，再单独重启设备。'}
    info=reply.json()
    if info.get('protocol')!=PROTOCOL:raise HTTPException(409,'WiFi运行服务版本不匹配，请核对后重新安装。')
    raw=await service.read_file(BRIDGE_PATH)
    if checksum(raw)!=lua.sha(bridge_source()):raise HTTPException(409,'设备运行服务文件与掌问版本不同，未运行。请先核对安装清单。')
    return {'ready':True,'serviceReady':True,'phase':'ready','bootId':device['boot_id'],'message':'WiFi运行服务已就绪，无需USB或板载模型API。'}


async def preflight(service,pid,revision=None):
    """Read-only checks on reconnect; never upload, restart, run or alter history."""
    lua.require_project(service.repo,pid)
    connection=service.connection_id
    result=await status(service)
    result['connectionId']=connection
    result['scriptVerified']=False
    value=lua.load(service.repo,pid)
    base=service.target(connection)
    result['recoverableRunIds']=[r.id for r in lua.unresolved_runs(value)
        if r.deviceEndpoint==base and r.bootId and r.bootId!=result['bootId']] if result.get('serviceReady') else []
    if revision is not None:
        preview=await lua.manifest(service,pid,revision)
        result.update(path=preview['path'],checksum=preview['checksum'],deviceChecksum=preview['expectedChecksum'],
                      scriptVerified=preview['expectedChecksum']==preview['checksum'])
    service.target(connection)
    if (await identity(service))['boot_id']!=result['bootId']:
        raise HTTPException(409,'检测期间设备已重启，请重新检测；未上传或运行。')
    if result['ready']:
        if revision is None:
            result.update(ready=False,phase='needs-code',message='WiFi运行服务已就绪。请先接受并保存Lua，再上传。')
        elif not result['scriptVerified']:
            result.update(ready=False,phase='needs-upload',message='WiFi运行服务已就绪，但设备文件与当前已保存Lua不一致。请查看上传清单并上传。')
        else:
            result['message']='WiFi运行已就绪：服务在线，设备Lua与当前已保存版本回读一致。点击运行才会执行。'
    return result


async def plan(service,pid):
    lua.require_project(service.repo,pid)
    connection=service.connection_id;device=await identity(service)
    modules=await service.json('/api/lua-modules')
    ids={m.get('module_id') for m in modules.get('items',[])}
    if not {'http_server','json','storage'}<=ids:raise HTTPException(409,'当前固件缺少WiFi运行需要的Lua模块，请核对最新Claw固件。')
    raw=await service.read_file(RULE_PATH)
    if raw is None:raise HTTPException(409,'未找到当前固件的路由规则文件，未另建或覆盖。')
    try:
        rules=json.loads(raw)
        if not isinstance(rules,list) or len(rules)>31 or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in rules):raise ValueError()
        if len({r['id'] for r in rules})!=len(rules):raise ValueError()
    except (ValueError,UnicodeError):raise HTTPException(409,'当前路由规则格式或条数无法安全合并，原文件保持。')
    rule={'id':'zhangwen_wifi_bridge_v1','description':'ZhangWen fixed WiFi Lua runner; project scripts never run at boot.',
          'enabled':True,'consume_on_match':False,
          'match':{'source_cap':'app_claw','event_type':'startup','event_key':'boot_completed','content_type':'trigger'},
          'actions':[{'type':'run_script','input':{'path':device['storage_base_path']+BRIDGE_PATH,
              'async':True,'timeout_ms':0,'name':'zhangwen_wifi_bridge','exclusive':'zhangwen-bridge','replace':False}}]}
    existing=next((r for r in rules if r['id']==rule['id']),None)
    if existing is not None and existing!=rule:raise HTTPException(409,'设备已有同名但内容不同的启动规则，请先人工核对，不会覆盖。')
    merged=rules if existing else [rule,*rules]
    content=json.dumps(merged,ensure_ascii=False,indent=2)+'\n'
    # Preserve original bytes if the desired rule is already present.
    if existing:content=raw.decode('utf-8')
    bridge=await service.read_file(BRIDGE_PATH)
    files=[{'path':BRIDGE_PATH,'content':bridge_source(),'expectedChecksum':checksum(bridge)},
           {'path':RULE_PATH,'content':content,'expectedChecksum':checksum(raw)}]
    for f in files:f.update(checksum=lua.sha(f['content']),size=len(f['content'].encode('utf-8')))
    service.target(connection)
    return {'projectId':pid,'connectionId':connection,'bootId':device['boot_id'],'preservedRules':len(rules),
            'files':files,'planChecksum':lua.sha(json.dumps(files,sort_keys=True,ensure_ascii=False))}


class Setup(Operation):
    projectId: str
    planChecksum: str = Field(pattern='^[a-f0-9]{64}$')


class Refresh(Operation):
    projectId: str
    runId: str = Field(pattern='^[a-f0-9]{32}$')


class Recovery(Refresh):
    bootId: str = Field(pattern='^[a-f0-9]{16}$')
    confirmed: Literal[True]


async def install(service,request):
    repo=service.repo;service.target(request.connectionId);lua.require_project(repo,request.projectId)
    with repo.lock:
        value=lua.load(repo,request.projectId)
        if any(s.id==request.requestId for s in value.wifiSetups):raise HTTPException(409,'此安装已提交，先核对文件和记录，不会重发。')
    proposal=await plan(service,request.projectId)
    if request.planChecksum!=proposal['planChecksum']:raise HTTPException(409,'设备文件已改变，请重新查看安装清单。')
    with repo.lock:
        value=lua.load(repo,request.projectId)
        if any(s.id==request.requestId for s in value.wifiSetups):raise HTTPException(409,'此安装已提交，未重复写入。')
        value.wifiSetups.append(lua.WifiSetupRecord(id=request.requestId,createdAt=lua.now(),state='pending',planChecksum=request.planChecksum,
            files=[lua.WifiSetupFile(path=f['path'],checksum=f['checksum']) for f in proposal['files']]))
        lua.store(repo,request.projectId,value)
    try:
        for f in proposal['files']:
            if f['checksum']==f['expectedChecksum']:continue
            result=await service.write_file(FileWrite(connectionId=request.connectionId,requestId=uuid.uuid4().hex,projectId=request.projectId,
                path=f['path'],content=base64.b64encode(f['content'].encode()).decode(),expectedChecksum=f['expectedChecksum']))
            with repo.lock:
                value=lua.load(repo,request.projectId);record=next(s for s in value.wifiSetups if s.id==request.requestId)
                next(item for item in record.files if item.path==f['path']).backupId=result['backupId'];lua.store(repo,request.projectId,value)
    except BaseException:
        with repo.lock:
            value=lua.load(repo,request.projectId);next(s for s in value.wifiSetups if s.id==request.requestId).state='outcome-unknown';lua.store(repo,request.projectId,value)
        raise
    with repo.lock:
        value=lua.load(repo,request.projectId);next(s for s in value.wifiSetups if s.id==request.requestId).state='verified';lua.store(repo,request.projectId,value)
    return {'message':'两份文件已安装并回读校验。尚未启动服务，也未运行项目代码；请显式重启设备后手动重新连接。'}


def validate_receipt(reply,rid):
    if reply.get('id')!=rid or not isinstance(reply.get('output'),str) or len(reply['output'])>16000:
        raise HTTPException(502,'设备运行回执不完整或超出范围，结果待核对。')
    if reply.get('deviceState') not in {'queued','running','unknown',*TERMINAL}:raise HTTPException(502,'设备任务状态无法识别。')
    job=reply.get('jobId')
    if job is not None and (not isinstance(job,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',job)):raise HTTPException(502,'设备任务标识无法识别。')
    return reply


def update_record(repo,pid,rid,reply):
    reply=validate_receipt(reply,rid)
    with repo.lock:
        value=lua.load(repo,pid);record=next(r for r in value.runs if r.id==rid)
        previous=record.model_dump()
        record.output=reply['output'];record.jobId=reply.get('jobId');record.deviceState=reply['deviceState']
        record.state='returned' if record.deviceState in TERMINAL else ('outcome-unknown' if record.deviceState=='unknown' else 'submitted')
        if record.model_dump()!=previous:lua.store(repo,pid,value)
    return value


async def run(service,pid,request):
    repo=service.repo
    # Hold the same device lock as file writes/restart throughout preflight + submit.
    async with service.lock:
        base=service.target(request.connectionId)
        if service.unknown:raise HTTPException(409,'有结果未知的设备操作，请先核对并重新连接。')
        with repo.lock:
            value,_=lua.accepted(repo,pid,request.revision)
            if any(r.id==request.requestId for r in value.runs):raise HTTPException(409,'运行已提交，不会重复执行。')
            if lua.unresolved_runs(value):raise HTTPException(409,'有未核对的运行，请先读取结果；设备已重启时可明确归档旧运行。不会重发。')
        ready=await status(service)
        if not ready['ready']:raise HTTPException(409,ready['message'])
        preview=await lua.manifest(service,pid,request.revision)
        if preview['expectedChecksum']!=preview['checksum']:raise HTTPException(409,'设备文件与当前已接受Lua不同，请先上传并回读。')
        with repo.lock:
            value,_=lua.accepted(repo,pid,request.revision)
            if any(r.id==request.requestId for r in value.runs):raise HTTPException(409,'运行已提交。')
            value.runs.append(lua.RunRecord(id=request.requestId,revision=request.revision,createdAt=lua.now(),state='submitted',
                timeoutMs=request.timeoutMs,transport='wifi',bootId=ready['bootId'],deviceEndpoint=base))
            lua.store(repo,pid,value)
        try:
            reply=await service.json(API+'/run','POST',{'id':request.requestId,'path':preview['path'].removeprefix('/scripts/'),'timeoutMs':request.timeoutMs})
            # A reboot while submitting invalidates the outcome, even if an HTTP response arrived.
            if (await identity(service))['boot_id']!=ready['bootId']:raise HTTPException(409,'运行期间设备已重启，结果未知。')
            return update_record(repo,pid,request.requestId,reply)
        except BaseException:
            with repo.lock:
                value=lua.load(repo,pid);next(r for r in value.runs if r.id==request.requestId).state='outcome-unknown';lua.store(repo,pid,value)
            raise


async def refresh(service,request):
    repo=service.repo;lua.require_project(repo,request.projectId)
    async with service.lock:
        base=service.target(request.connectionId)
        with repo.lock:
            value=lua.load(repo,request.projectId);record=next((r for r in value.runs if r.id==request.runId and r.transport=='wifi'),None)
            if record is None:raise HTTPException(404,'WiFi运行记录不存在。')
            if any(r.runId==record.id for r in value.runRecoveries):raise HTTPException(409,'该旧运行已归档，原结果保持未知，不再更新。')
        if base!=record.deviceEndpoint or (await identity(service))['boot_id']!=record.bootId:
            raise HTTPException(409,'设备地址或启动标识已改变，保留原运行证据，不会重发。')
        reply=await service.json(API+'/job?id='+request.runId)
        if (await identity(service))['boot_id']!=record.bootId:raise HTTPException(409,'读取期间设备已重启，保留原证据。')
        return update_record(repo,request.projectId,request.runId,reply)


async def recover(service,request):
    """Explicit local archival, with only fixed device reads. Never run/reboot/retry."""
    repo=service.repo;lua.require_project(repo,request.projectId)
    async with service.lock:
        base=service.target(request.connectionId)
        if service.unknown:raise HTTPException(409,'设备操作结果未知，请先核对并重新连接。')
        with repo.lock:
            value=lua.load(repo,request.projectId)
            old=next((r for r in value.runRecoveries if r.id==request.requestId),None)
            if old:
                if old.runId!=request.runId or old.bootId!=request.bootId:raise HTTPException(409,'归档标识已被其他记录使用。')
                return value
            record=next((r for r in lua.unresolved_runs(value) if r.id==request.runId),None)
            if record is None:raise HTTPException(409,'该运行无需归档，请重新读取记录。')
            if record.deviceEndpoint!=base or not record.bootId:raise HTTPException(409,'请连接原设备地址核对，不能用其他地址归档。')
        ready=await status(service)
        if not ready.get('serviceReady') or ready['bootId']!=request.bootId or ready['bootId']==record.bootId:
            raise HTTPException(409,'尚未确认新的启动周期与运行服务；同一启动周期的未知任务不能归档。')
        if (await identity(service))['boot_id']!=request.bootId:
            raise HTTPException(409,'核对期间设备再次重启，请重新检测。')
        with repo.lock:
            value=lua.load(repo,request.projectId)
            if not any(r.id==record.id for r in lua.unresolved_runs(value)):raise HTTPException(409,'运行记录已更新，请重新读取。')
            value.runRecoveries.append(lua.RunRecovery(id=request.requestId,runId=record.id,previousBootId=record.bootId,
                bootId=request.bootId,deviceEndpoint=base,createdAt=lua.now()))
            return lua.store(repo,request.projectId,value)


def add_routes(route,repo,service):
    @route.get('/api/mosaico/lua-wifi-status')
    async def wifi_status(projectId:str|None=None,revision:int|None=None):
        async with service.lock:
            return await preflight(service,projectId,revision) if projectId else await status(service)
    @route.get('/api/mosaico/lua-wifi-plan')
    async def wifi_plan(projectId:str):
        async with service.lock:return await plan(service,projectId)
    @route.post('/api/mosaico/lua-wifi-install')
    async def wifi_install(request:Setup):return await install(service,request)
    @route.post('/api/projects/{pid}/lua-coding/wifi-run')
    async def wifi_run(pid:str,request:lua.RunStart):return await run(service,pid,request)
    @route.post('/api/mosaico/lua-wifi-refresh')
    async def wifi_refresh(request:Refresh):return await refresh(service,request)
    @route.post('/api/mosaico/lua-wifi-recover')
    async def wifi_recover(request:Recovery):return await recover(service,request)
