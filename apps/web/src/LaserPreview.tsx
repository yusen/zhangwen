import { useState } from 'react';
import { ScanLine } from 'lucide-react';
import type { CadResult, DesignSpec } from '../../../packages/contracts/src/structure';

export function LaserPreview({ result }: { result?: CadResult }) {
  const [view, setView] = useState<'preview' | 'cut'>('preview');
  const drawing = (result?.laserDrawing as DesignSpec['drawing']) ?? result?.designSpec?.drawing;
  return <div className="structure-preview laser-preview">
    <div className="structure-view-tabs" role="group" aria-label="激光图纸视图">
      <button aria-pressed={view === 'preview'} onClick={() => setView('preview')}>设计预览</button>
      <button aria-pressed={view === 'cut'} onClick={() => setView('cut')}>切割图</button>
      {drawing && <span>{drawing.width} × {drawing.height} mm · 厚 {drawing.thickness} mm</span>}
    </div>
    {drawing ? <div className={`laser-sheet ${view}`}><svg role="img" aria-label={view === 'preview' ? '激光切割设计预览' : '激光切割路径图'} viewBox={`-5 -5 ${drawing.width + 10} ${drawing.height + 10}`}>
      <rect className="laser-stock" width={drawing.width} height={drawing.height} />
      {drawing.shapes.map((shape, i) => {
        const props = {className: `laser-path ${shape.operation}`, key: i, vectorEffect: 'non-scaling-stroke' as const};
        if (shape.kind === 'rect') return <rect {...props} x={shape.x} y={shape.y} width={shape.width} height={shape.height} />;
        if (shape.kind === 'circle') return <circle {...props} cx={shape.x} cy={shape.y} r={shape.radius} />;
        if (shape.kind === 'text') return <path {...props} className="laser-path engrave laser-text" d={result?.laserTextPaths?.[String(i)] ?? ''} fillRule="evenodd" />;
        const points = shape.points.map(p => p.join(',')).join(' ');
        return shape.closed ? <polygon {...props} points={points} /> : <polyline {...props} points={points} />;
      })}
    </svg><p>红线切割 · 蓝线雕刻 · 毫米尺寸{result?.status !== 'artifact' && ' · 待确认草案'}</p></div>
      : <div className="structure-preview-empty"><ScanLine size={44} strokeWidth={1.3} /><h3>把想法变成激光切割图纸</h3><p>描述尺寸、材料与轮廓，或先选择左侧模板。</p><span>SVG / DXF · 不依赖 LaserMaker</span></div>}
  </div>;
}
