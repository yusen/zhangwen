import { useRef, useState } from 'react';
import type { HardwareDetail, HardwareSummary } from '../../../packages/contracts/src/platform';
import { Dialog } from './Dialog';
import { HardwareExampleEditor } from './HardwareExampleEditor';
import { HardwareVerification } from './HardwareVerification';
import { HardwareMechanicalEditor } from './HardwareMechanicalEditor';
import { PersonalModuleFacts } from './PersonalModuleFacts';
import { guideCode, guideLabels, guideValues, renderGuideText } from './moduleExamples';

const interfaceNames: Record<string, string> = {
  GPIO_DIGITAL: '数字输入', ADC: '模拟输入（ADC）',
  SINGLE_WIRE_TRIG_ECHO: '单线测距', I2C: 'I²C', SPI: 'SPI', UART: '串口',
};
const plain = (value: string) => value.replace(/`([^`]+)`/g, '$1').replace(/\*\*([^*]+)\*\*/g, '$1');
function Reference({ content }: { content: string }) {
  return <div className="sensor-reference">{content.trim().split(/\r?\n\s*\r?\n/).map((block, index) => {
    const lines = block.split(/\r?\n/);
    if (lines.every(line => line.trim().startsWith('|')) && lines.length >= 3 && /\|\s*:?-{3}/.test(lines[1])) {
      const cells = (line: string) => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => plain(cell.trim()));
      return <div className="sensor-table-scroll" key={index}><table><thead><tr>{cells(lines[0]).map((cell, n) => <th key={n}>{cell}</th>)}</tr></thead><tbody>{lines.slice(2).map((line, n) => <tr key={n}>{cells(line).map((cell, c) => <td key={c}>{cell}</td>)}</tr>)}</tbody></table></div>;
    }
    if (lines.every(line => /^\s*[-*]\s/.test(line))) return <ul key={index}>{lines.map((line, n) => <li key={n}>{plain(line.replace(/^\s*[-*]\s/, ''))}</li>)}</ul>;
    if (/^#{1,6}\s/.test(block)) return <h4 key={index}>{plain(block.replace(/^#{1,6}\s/, ''))}</h4>;
    return <p key={index}>{plain(block)}</p>;
  })}</div>;
}

type Tab = 'use' | 'mechanical' | 'sources';
type Page = 'main' | 'example' | 'facts' | 'verification' | 'test';
const tabs: { id: Tab; name: string }[] = [{ id: 'use', name: '使用方法' }, { id: 'mechanical', name: '尺寸与安装' }, { id: 'sources', name: '参考资料' }];
export function HardwareDetails({ detail, board, boards, editExample = false, initialTab = 'use', onSaved, onClose }: { detail: HardwareDetail; board?: HardwareSummary; boards: HardwareSummary[]; editExample?: boolean; initialTab?: Tab; onSaved: (value: HardwareDetail) => void; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [page, setPage] = useState<Page>(editExample ? 'example' : 'main');
  const menu = useRef<HTMLDetailsElement>(null);
  const electrical = detail.specification.electrical;
  const wiring = detail.files.find(file => file.path === 'references/integration.md');
  const safety = detail.files.find(file => file.path === 'references/safety.md');
  const saved = detail.localExamples?.find(item => item.boardId === board?.componentId);
  const guide = detail.moduleGuides?.find(item => item.boardId === board?.componentId);
  const setup = guide ? guideValues(guide, saved?.setup) : {};
  const code = saved?.code.trim() ? saved.code : guide ? guideCode(guide, setup) : '';
  const changePage = (value: Page) => { if (menu.current) menu.current.open = false; setPage(value); };
  const more = <details className="resource-menu" ref={menu}><summary aria-label="模块更多操作">⋯</summary><div>
    {detail.category !== 'MCU' && <button onClick={() => changePage('example')}>编辑案例</button>}
    {detail.personal && <button onClick={() => changePage('facts')}>修改参数</button>}
    {detail.category !== 'MCU' && <button onClick={() => changePage('verification')}>核实详情与记录</button>}
  </div></details>;
  return <Dialog title={detail.displayName} onClose={onClose} className="hardware-resource-dialog" headerActions={detail.category === 'MCU' ? undefined : more}>
    {page !== 'main' ? <>
      <button className="resource-back" onClick={() => changePage('main')}>← 返回资料</button>
      {page === 'example' && <HardwareExampleEditor key={detail.skillName + board?.componentId} detail={detail} board={board} boards={boards} startEditing onSaved={onSaved} />}
      {page === 'facts' && <PersonalModuleFacts key={detail.skillName} detail={detail} onSaved={onSaved} startOpen />}
      {(page === 'verification' || page === 'test') && <HardwareVerification key={page + board?.componentId} detail={detail} board={board} boards={boards} view={page === 'test' ? 'test' : 'details'} onNavigate={value => changePage(value === 'summary' ? 'main' : value === 'details' ? 'verification' : 'test')} onEditExample={() => changePage('example')} onSaved={onSaved} />}
    </> : <>
      <div className="resource-overview">{detail.media[0] && <img src={detail.media[0].url} alt={detail.media[0].alt} />}<div><p>{detail.description}</p><small>当前主控：{board?.displayName ?? (detail.category === 'MCU' ? detail.displayName : '尚未选择')}{detail.personal && ' · 我的模块'}</small></div></div>
      <div className="resource-tabs" role="tablist" aria-label="模块资料分类">{tabs.map((item, index) => <button key={item.id} id={`module-tab-${item.id}`} role="tab" aria-selected={tab === item.id} aria-controls={`module-panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        setTab(tabs[next].id); document.getElementById(`module-tab-${tabs[next].id}`)?.focus();
      }}>{item.name}</button>)}</div>
      <section role="tabpanel" id="module-panel-use" aria-labelledby="module-tab-use" hidden={tab !== 'use'}>
        <dl className="sensor-facts"><div><dt>供电</dt><dd>{electrical.voltage > 0 ? electrical.voltage + ' V' : '待补充'}</dd></div><div><dt>信号电平</dt><dd>{electrical.logicLevel > 0 ? electrical.logicLevel + ' V' : detail.category === 'POWER' || detail.category === 'STRUCTURE' ? '按用途确认' : '待补充'}</dd></div><div><dt>接口</dt><dd>{electrical.communicationProtocol === 'UNKNOWN' ? '待补充' : interfaceNames[electrical.communicationProtocol] ?? electrical.communicationProtocol}</dd></div></dl>
        {detail.verificationRecords?.filter(row => row.boardId === board?.componentId && row.dimension === 'electrical' && (row.stale || row.state === 'failed')).map(row => <p className={`verification-badge ${row.stale ? 'pending' : 'failed'}`} key={row.dimension}>供电与电平：{row.stale ? '资料已变化，请复核' : '用户记录存在异常，请查看核实详情'}</p>)}
        {detail.personal && (!electrical.voltage || !electrical.logicLevel) && <button className="resource-inline" onClick={() => changePage('facts')}>补充已知参数</button>}
        <section className="sensor-section"><h3>接线</h3>
          {saved?.notes && <p className="resource-notes">{saved.notes}</p>}
          {guide?.connections.length ? <><p className="muted">{saved?.setup ? '当前主控已保存接线，请与实物核对。' : '以下为参考接线，请与实物核对。'}</p><dl className="module-guide-wiring" aria-label="接线对应">{guide.connections.map(connection => <div key={connection.signal}><dt>{connection.signal}</dt><dd>{renderGuideText(connection.target, guideLabels(guide, setup))}</dd></div>)}</dl></> : !saved?.notes && (detail.personal ? <p className="muted">接线说明待补充。</p> : wiring && <details><summary>查看接线参考</summary><Reference content={wiring.content} /></details>)}
          {detail.i2c && <p>I²C 地址：{saved?.i2cAddress || saved?.setup?.address || detail.i2c.defaultAddress || '待确认'}{!saved?.i2cAddress && !saved?.setup?.address && '（资料参考）'}</p>}
        </section>
        <section className="sensor-section"><div className="resource-section-head"><h3>当前主控示例</h3>{detail.category !== 'MCU' && <button onClick={() => changePage('example')}>{code ? '编辑案例' : '补充接线与案例'}</button>}</div>
          {code ? <><p className="muted">{saved?.code.trim() ? '本机保存案例' : '内置参考案例'} · {board?.displayName} · 待按实物验证</p><details className="resource-code"><summary>查看示例程序</summary><pre>{code}</pre></details></> : <p className="muted">当前主控暂无示例，可在参考资料中查看原文。</p>}
        </section>
        {detail.category !== 'MCU' && <HardwareVerification detail={detail} board={board} boards={boards} view="summary" onNavigate={value => changePage(value === 'details' ? 'verification' : 'test')} onSaved={onSaved} />}
        {safety && <details className="resource-caution"><summary>使用注意</summary><Reference content={safety.content.replace(/^#\s+[^\n]+\r?\n/, '')} /></details>}
      </section>
      <section role="tabpanel" id="module-panel-mechanical" aria-labelledby="module-tab-mechanical" hidden={tab !== 'mechanical'}><HardwareMechanicalEditor key={detail.skillName} detail={detail} onSaved={onSaved} /></section>
      <section role="tabpanel" id="module-panel-sources" aria-labelledby="module-tab-sources" hidden={tab !== 'sources'}>
        <p className="muted">资料修订：{detail.revision}</p>
        {detail.catalog?.sourceUrl.startsWith('https://') && <p><a href={detail.catalog.sourceUrl} target="_blank" rel="noopener noreferrer">查看官方说明 ↗</a></p>}
        {detail.specification.notes && <p className="resource-notes">{detail.specification.notes}</p>}
        {detail.files.map(file => <details className="hardware-document" key={file.path}><summary>{file.title || file.path}</summary><pre>{file.content}</pre></details>)}
        {detail.media[0] && <small>图片：{detail.media[0].attribution} · {detail.media[0].license}</small>}
      </section>
    </>}
  </Dialog>;
}
