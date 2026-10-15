import type { HardwareSummary } from '../../../packages/contracts/src/mu';
import { useState } from 'react';
import { moduleBrand, moduleDirection, moduleType, type ModuleDirection } from './hardwareLibrary';

export function ModuleFilters({ items, brand, direction, type, onBrand, onType, onClear }: {
  items: HardwareSummary[]; brand: string; direction: ModuleDirection | 'all'; type: string;
  onBrand: (brand: string) => void; onType: (direction: ModuleDirection | 'all', type: string) => void; onClear: () => void;
}) {
  const [expanded, setExpanded] = useState(() => window.matchMedia('(min-width: 601px)').matches);
  const brands = [...new Set(items.map(moduleBrand))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const branded = items.filter(item => brand === 'all' || moduleBrand(item) === brand);
  const order = ['开关量', '环境', '液体', '距离', '姿态', '声音', '电', '光和图像', '重量', '生物识别', '舵机', '电机', '步进电机', '泵', '继电器', '音频播放', '屏幕', '灯光', '其他输入', '其他输出'];
  const types = (side: ModuleDirection) => [...new Set(items.filter(item => moduleDirection(item) === side).map(moduleType))]
    .sort((a, b) => (order.indexOf(a) < 0 ? 99 : order.indexOf(a)) - (order.indexOf(b) < 0 ? 99 : order.indexOf(b)));
  const selectType = (side: ModuleDirection | 'all', value: string) => {
    onType(side, value);
    if (window.matchMedia('(max-width: 600px)').matches) setExpanded(false);
  };
  return <details className="catalog-filter-panel" open={expanded} onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary>筛选模块<span>{brand === 'all' ? '全部品牌' : brand} · {type || (direction === 'all' ? '全部模块' : direction === 'input' ? '输入模块' : '输出模块')}</span></summary>
    <div className="catalog-filter-rows">
      <div className="catalog-filter-row" role="group" aria-label="品牌筛选"><strong>品牌</strong><div className="filter-options">
        <button aria-pressed={brand === 'all'} onClick={() => onBrand('all')}>全部品牌<span>{items.length}</span></button>
        {brands.map(value => <button key={value} aria-pressed={brand === value} onClick={() => onBrand(value)}>{value}<span>{items.filter(item => moduleBrand(item) === value).length}</span></button>)}
      </div></div>
      <div className="catalog-filter-row" role="group" aria-label="模块类型"><strong>类型</strong><div className="filter-options">
        {(['all', 'input', 'output'] as const).map(value => <button key={value} aria-pressed={direction === value && !type} onClick={() => selectType(value, '')}>{value === 'all' ? '全部模块' : value === 'input' ? '输入模块' : '输出模块'}<span>{branded.filter(item => value === 'all' || moduleDirection(item) === value).length}</span></button>)}
      </div></div>
      {(['input', 'output'] as const).map(side => <div className="catalog-filter-row" role="group" aria-label={side === 'input' ? '传感器类型' : '执行器类型'} key={side}><strong>{side === 'input' ? '传感器类型' : '执行器类型'}</strong><div className="filter-options">
        {types(side).map(value => <button key={value} aria-pressed={direction === side && type === value} disabled={!branded.some(item => moduleDirection(item) === side && moduleType(item) === value)} onClick={() => selectType(side, value)}>{value}</button>)}
      </div></div>)}
      <button className="clear-catalog-filters" onClick={onClear}>清空筛选</button>
    </div>
  </details>;
}
