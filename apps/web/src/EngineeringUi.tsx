import { useId, type ReactNode, type RefObject } from 'react';
import { ArrowUp, CheckCheck, CircuitBoard, Cpu, FileCode2, LoaderCircle, Maximize, Minimize, Play, Settings, Sparkles, Square, Terminal, Unplug, Usb, ZoomIn, ZoomOut } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import { ToolbarButton } from './ToolbarButton';
import { ModuleCard } from './ModuleCard';
import { moduleDirection, selectableModules } from './hardwareLibrary';
import { MICROBIT_BOARD } from './controllerDiagnostics';

/** Shared controls for every MicroPython controller, including a single-board project. */
export function EngineeringActions({ boardId, uploadDisabled, runDisabled, checkDisabled, firmwareDisabled, running, attention, terminalOpen, reason, onUpload, onRun, onTerminal, onSelfTest, onFirmware }: {
  boardId: string; uploadDisabled: boolean; runDisabled: boolean; checkDisabled: boolean; firmwareDisabled: boolean;
  running: boolean; attention: boolean; terminalOpen: boolean; reason?: string;
  onUpload: () => void; onRun: () => void; onTerminal: () => void; onSelfTest: () => void; onFirmware: () => void;
}) {
  return <div className="tool-group" role="group" aria-label="设备操作">
    <ToolbarButton icon={ArrowUp} label="上传并运行" variant="hardware" disabled={uploadDisabled} disabledReason={reason} onClick={onUpload} title="上传并运行 main.py：保存、备份、回读校验，通过后自动运行"/>
    <ToolbarButton icon={running || attention ? Square : Play} label={running || attention ? '停止' : '运行'} emphasis active={running} disabled={runDisabled} disabledReason={reason} onClick={onRun}/>
    <ToolbarButton icon={Terminal} label="REPL" active={terminalOpen} aria-pressed={terminalOpen} onClick={onTerminal}/>
    <ToolbarButton icon={CheckCheck} label="主控自检" disabled={checkDisabled} onClick={onSelfTest} title="先自检主控，再逐项测试模块；固定读取程序，不覆盖 main.py"/>
    <ToolbarButton icon={Cpu} label={boardId === MICROBIT_BOARD ? '固件准备' : '固件刷入'} variant="hardware" disabled={firmwareDisabled} onClick={onFirmware} title="准备当前主控对应固件；请先断开设备"/>
  </div>;
}

export function EngineeringConnection({ state, disabled, filesActive, onFiles, onConnect }: { state: string; disabled: boolean; filesActive: boolean; onFiles: () => void; onConnect: () => void }) {
  const active=state!=='disconnected';
  return <><button className={`connection toolbar-status ${filesActive?'is-connected':''}`} aria-haspopup="dialog" aria-pressed={filesActive} disabled={disabled} onClick={onFiles} title="连接后读取、添加或导出板上的文件"><Usb size={17}/><span>板载文件</span></button>
    <button className={`connection toolbar-status ${active?'is-connected':''}`} disabled={disabled} onClick={onConnect}>{disabled?<LoaderCircle size={17} className="spin"/>:active?<Unplug size={17}/>:<Usb size={17}/>}<span>{state==='disconnected'?'连接设备':state==='attention'?'需要重连 · 断开':disabled?'设备处理中':'已连接 · 断开'}</span></button></>;
}

export function EngineeringChatHeader({ configured, disabled, onSettings }: { configured: boolean; disabled: boolean; onSettings: () => void }) {
  return <div className="panel-head"><h2><Sparkles size={18}/>智能工程师</h2><button className="api-settings-entry" disabled={disabled} onClick={onSettings} aria-label="掌问 AI 设置"><Settings size={14}/><span>{configured?'已配置':'未配置'}</span> · 设置</button></div>;
}

export function EngineeringComposer({ value, onChange, onSend, disabled, generating, inputRef }: { value: string; onChange: (value: string) => void; onSend: () => void; disabled: boolean; generating: boolean; inputRef?: RefObject<HTMLTextAreaElement> }) {
  const id=useId();
  return <form className="chat-form inline-chat-form" onSubmit={event=>{event.preventDefault();if(!disabled&&value.trim())onSend();}}><label className="sr-only" htmlFor={id}>发送给掌问 AI</label><textarea ref={inputRef} id={id} value={value} onChange={event=>onChange(event.target.value)} onKeyDown={event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&!event.nativeEvent.isComposing&&!disabled&&value.trim()){event.preventDefault();onSend();}}} placeholder="告诉智能工程师，你想让作品怎样工作…" maxLength={4000}/><button className="primary icon-button" aria-label="发送" disabled={disabled||!value.trim()}>{generating?<LoaderCircle size={19} className="spin"/>:<ArrowUp size={20}/>}</button></form>;
}

export function EngineeringFilebar({ versions, zoom, fullscreen, onZoom, onFullscreen, tools }: { versions: ReactNode; zoom: number; fullscreen: boolean; onZoom: (value: number) => void; onFullscreen: () => void; tools: ReactNode }) {
  return <div className="filebar"><span><FileCode2 size={16}/>main.py</span><span className="filebar-space"/>{versions}<div className="editor-view-controls"><button aria-label="缩小代码" title="缩小代码" disabled={zoom<=80} onClick={()=>onZoom(Math.max(80,zoom-10))}><ZoomOut size={16}/></button><span aria-label="代码字号比例">{zoom}%</span><button aria-label="放大代码" title="放大代码" disabled={zoom>=160} onClick={()=>onZoom(Math.min(160,zoom+10))}><ZoomIn size={16}/></button><button aria-label={fullscreen?'退出代码全屏':'代码全屏'} title={fullscreen?'退出全屏（Esc）':'代码全屏'} onClick={onFullscreen}>{fullscreen?<Minimize size={16}/>:<Maximize size={16}/>}</button></div>{tools}</div>;
}

export function EngineeringModuleList({ boardId, hardware, componentIds, loading, disabled, chatCoding=false, onDetail, onEditExample, onLoad }: { boardId: string; hardware: HardwareSummary[]; componentIds: string[]; loading?: boolean; disabled: boolean; chatCoding?: boolean; onDetail: (item: HardwareSummary) => void; onEditExample: (item: HardwareSummary) => void; onLoad: (item: HardwareSummary) => void }) {
  const items=componentIds.map(id=>hardware.find(item=>item.componentId===id)).filter((item):item is HardwareSummary=>!!item&&!!moduleDirection(item));
  const library=selectableModules(hardware);
  return <div className="catalog-list selected-sensor-list">{loading?<p className="muted">正在读取项目…</p>:(['input','output','support'] as const).map(direction=>{
    const group=items.filter(item=>moduleDirection(item)===direction);
    const title=direction==='input'?'输入模块':direction==='output'?'输出模块':'配套模块';
    return !!group.length&&<section className="module-group" key={direction} aria-label={`已加入的${title}`}><h3>{title}<span>{group.length}</span></h3><div className="module-grid">{group.map(item=><ModuleCard key={item.componentId} item={item} boardId={boardId} boards={hardware.filter(board=>board.category==='MCU')} disabled={disabled} outside={!library.some(value=>value.componentId===item.componentId)} onDetail={()=>onDetail(item)} onEditExample={()=>onEditExample(item)} onLoad={()=>onLoad(item)}/>)}</div></section>;
  })}{!loading&&boardId&&!items.length&&<div className="selected-sensors-empty"><CircuitBoard size={42}/><strong>{chatCoding?'查看板载能力':'为项目添加模块'}</strong>{chatCoding?<><p>板载器件无需另加模块。固件接口与实测状态请查看主控资料。</p><button onClick={()=>{const board=hardware.find(item=>item.componentId===boardId);if(board)onDetail(board);}}>查看Mosaico使用资料</button><p>需要外接器件时，点击“管理项目器件”。</p></>:<p>点击「管理项目器件」，添加传感器、执行器或显示模块。</p>}</div>}</div>;
}
