import type { HardwareDetail, HardwareSummary } from '../../../packages/contracts/src/platform';
import { Dialog } from './Dialog';
import { HardwareExampleEditor } from './HardwareExampleEditor';

const interfaceNames: Record<string, string> = {
  GPIO_DIGITAL: '数字输入', ADC: '模拟输入（ADC）',
  SINGLE_WIRE_TRIG_ECHO: '单线测距', I2C: 'I²C', SPI: 'SPI', UART: '串口',
};
const plain = (value: string) => value.replace(/`([^`]+)`/g, '$1').replace(/\*\*([^*]+)\*\*/g, '$1');

/** Render the package's short reference as text, lists and tables. Never execute HTML. */
function Reference({ content }: { content: string }) {
  const blocks = content.trim().split(/\r?\n\s*\r?\n/);
  return <div className="sensor-reference">{blocks.map((block, index) => {
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

export function HardwareDetails({ detail, board, boards, editExample = false, onSaved, onClose }: { detail: HardwareDetail; board?: HardwareSummary; boards: HardwareSummary[]; editExample?: boolean; onSaved: (value: HardwareDetail) => void; onClose: () => void }) {
  const wiring = detail.files.find(file => file.path === 'references/integration.md');
  const safety = detail.files.find(file => file.path === 'references/safety.md');
  const electrical = detail.specification.electrical;
  const editor = detail.category !== 'MCU' && <HardwareExampleEditor key={detail.skillName + board?.componentId} detail={detail} board={board} boards={boards} startEditing={editExample} onSaved={onSaved} />;
  const reference = <>
    <dl className="sensor-facts"><div><dt>资料供电</dt><dd>{electrical.voltage > 0 ? electrical.voltage + ' V' : '待核实'}</dd></div><div><dt>信号电平</dt><dd>{electrical.logicLevel > 0 ? electrical.logicLevel + ' V' : '待核实'}</dd></div><div><dt>接口</dt><dd>{electrical.communicationProtocol === 'UNKNOWN' ? '查阅官方资料' : interfaceNames[electrical.communicationProtocol] ?? electrical.communicationProtocol}</dd></div></dl>
    <section className="sensor-section" aria-label="接线参考"><h3>接线参考</h3>{wiring ? <Reference content={wiring.content} /> : <p className="muted">此资料包尚未提供接线说明。</p>}</section>
    {safety && <section className="sensor-section sensor-safety" aria-label="使用注意"><h3>使用注意</h3><Reference content={safety.content.replace(/^#\s+[^\n]+\r?\n/, '')} /></section>}
  </>;
  return <Dialog title={detail.displayName} onClose={onClose}>
    <div className="sensor-overview">
      {detail.media[0] && <img src={detail.media[0].url} alt={detail.media[0].alt} />}
      <p>{detail.description}</p>
    </div>
    {detail.catalog && <p className="module-catalog-info">{detail.catalog.brand} · {detail.catalog.moduleType}{detail.catalog.programmingSupport === 'reference' && ' · 资料已收录，编程待联调'}{detail.catalog.sourceUrl.startsWith('https://') && <> · <a href={detail.catalog.sourceUrl} target="_blank" rel="noopener noreferrer">查看官方资料 ↗</a></>}</p>}
    {editor}
    {editExample ? <details className="sensor-full-docs"><summary>原资料接线与注意</summary>{reference}</details> : reference}
    <details className="sensor-full-docs"><summary>完整技术资料</summary>
      <p className="muted">资料版本：{detail.revision} · 资料核验不代表本次实物已测试。</p>
      {detail.specification.notes && <p>{detail.specification.notes}</p>}
      {detail.media[0] && <p className="muted">图片：{detail.media[0].attribution} · {detail.media[0].license}</p>}
      {detail.files.map(file => <details className="hardware-document" key={file.path}><summary>{file.title || file.path}</summary><pre>{file.content}</pre></details>)}
    </details>
  </Dialog>;
}
