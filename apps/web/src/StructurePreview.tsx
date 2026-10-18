import { useEffect, useRef, useState } from 'react';
import { Box, RotateCcw } from 'lucide-react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import type { CadResult, CadSize } from '../../../packages/contracts/src/structure';

type View = 'assembly' | 'exploded' | 'base' | 'lid' | 'hardware';
const names: [View, string][] = [['assembly', '整体'], ['exploded', '爆炸'], ['base', '底壳'], ['lid', '上盖'], ['hardware', '硬件']];
export const sizeText = (s?: CadSize) => s ? `${s.length_x} × ${s.width_y} × ${s.height_z} mm` : '待确定';

export function StructurePreview({ result }: { result?: CadResult }) {
  const host = useRef<HTMLDivElement>(null);
  const reset = useRef<() => void>(() => {});
  const [view, setView] = useState<View>('assembly');
  const [status, setStatus] = useState('');
  const state = result?.design_state;
  const exports = result?.exports;
  const ready = result?.build?.status === 'artifact_exports';
  const standalone = result?.designKind === 'parametric';
  useEffect(() => {
    if (!host.current || !ready) return;
    const container = host.current;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
    catch { setStatus('此浏览器暂不能启用 3D 视图，可下载 STEP/STL 在建模软件查看。'); return; }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene(); scene.up.set(0, 0, 1);
    const camera = new THREE.PerspectiveCamera(42, 1, .1, 10000); camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x7d8790, 2.8));
    const light = new THREE.DirectionalLight(0xffffff, 2.5); light.position.set(100, -120, 180); scene.add(light);
    const grid = new THREE.GridHelper(240, 24, 0x8494a8, 0xa0aec0); grid.rotateX(Math.PI / 2);
    (grid.material as THREE.Material).transparent = true; (grid.material as THREE.Material).opacity = .22; scene.add(grid);
    const axes = new THREE.AxesHelper(25); scene.add(axes);
    const group = new THREE.Group(); scene.add(group);
    let disposed = false, frame = 0;
    const controller = new AbortController();
    const materials: THREE.Material[] = [], geometries: THREE.BufferGeometry[] = [];
    const resize = () => { const w = Math.max(container.clientWidth, 1), h = Math.max(container.clientHeight, 1); renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); };
    const observer = new ResizeObserver(resize); observer.observe(container); resize();
    const render = () => { if (disposed) return; controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(render); }; render();
    const parts = standalone ? ['base'] : view === 'assembly' || view === 'exploded' ? ['base', 'lid', 'hardware'] : [view];
    setStatus('正在载入真实模型…');
    void (async () => {
      try {
        await Promise.all(parts.map(async part => {
          const item = exports?.find(e => e.id === `cadquery_${part}_stl`);
          if (!item?.url) { if (part === 'hardware') return; throw new Error('此版本缺少对应模型文件。'); }
          const response = await fetch(item.url, { signal: controller.signal });
          if (!response.ok) throw new Error('模型文件读取失败，请重新生成或检查文件。');
          const geometry = new STLLoader().parse(await response.arrayBuffer());
          if (disposed) { geometry.dispose(); return; }
          geometries.push(geometry);
          const material = new THREE.MeshStandardMaterial({color: part === 'hardware' ? 0x5d9e82 : part === 'lid' ? 0xd9e5ed : 0x829db7,
            roughness: .68, metalness: .05, transparent: view === 'exploded' && part === 'lid', opacity: view === 'exploded' && part === 'lid' ? .55 : 1});
          materials.push(material); const mesh = new THREE.Mesh(geometry, material);
          if (view === 'exploded' && part === 'lid') mesh.position.z += Math.max(20, (state?.enclosure_parameters.outer_box_size.height_z ?? 40) * .6);
          group.add(mesh);
        }));
        if (disposed) return;
        const bounds = new THREE.Box3().setFromObject(group);
        if (bounds.isEmpty()) throw new Error('此版本没有可显示的模型。');
        const center = bounds.getCenter(new THREE.Vector3()), size = bounds.getSize(new THREE.Vector3());
        const distance = Math.max(size.length(), 60) * 1.5;
        reset.current = () => { camera.position.copy(center).add(new THREE.Vector3(distance, -distance, distance * .8)); controls.target.copy(center); controls.update(); };
        reset.current(); setStatus('真实模型 · 拖动旋转，滚轮缩放');
      } catch (error) { if (!disposed) { group.visible = false; setStatus(error instanceof Error ? error.message : '模型载入失败'); } }
    })();
    return () => { disposed = true; controller.abort(); cancelAnimationFrame(frame); observer.disconnect(); controls.dispose(); geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); grid.geometry.dispose(); (grid.material as THREE.Material).dispose(); axes.geometry.dispose(); (Array.isArray(axes.material) ? axes.material : [axes.material]).forEach(m => m.dispose()); renderer.dispose(); renderer.domElement.remove(); reset.current = () => {}; };
  }, [ready, exports, view, state, standalone]);

  return <div className="structure-preview">
    <div className="structure-view-tabs" role="group" aria-label="模型视图">{(standalone ? names.slice(0, 1) : names).map(([key, name]) => <button key={key} disabled={!ready} aria-pressed={view === key} onClick={() => setView(key)}>{name}</button>)}<button disabled={!ready} aria-label="重置模型视角" onClick={() => reset.current()}><RotateCcw size={15} /></button></div>
    {ready ? <><div ref={host} className="structure-canvas" role="img" aria-label="真实结构模型预览" /><p className="structure-view-status" role="status">{status}</p></> : state ? <>
      <div className="structure-draft"><svg role="img" aria-label="结构布局草案俯视图" viewBox="-100 -85 200 170">
        {(() => { const s = state.enclosure_parameters.outer_box_size; const k = 145 / Math.max(s.length_x, s.width_y); return <g transform={`scale(${k})`}><rect className="draft-shell" x={-s.length_x / 2} y={-s.width_y / 2} width={s.length_x} height={s.width_y} rx={3} />{state.layout_plan?.hardware_transforms.map((h, i) => <g key={`${h.hardware_id}-${i}`}><rect className={`draft-part ${h.mount_surface === 'lid_inner' ? 'on-lid' : ''}`} x={h.center.x - h.bounding_box.length_x / 2} y={-h.center.y - h.bounding_box.width_y / 2} width={h.bounding_box.length_x} height={h.bounding_box.width_y} rx={1} /><text x={h.center.x} y={-h.center.y} fontSize={4 / k} textAnchor="middle">{i + 1}</text></g>)}</g>; })()}
      </svg><strong>{sizeText(state.enclosure_parameters.outer_box_size)}</strong><span>2D 布局草案 · 尚非真实模型</span></div>
      {result?.build && <p className="structure-build-warning" role="status">{result.build.message || '真实模型暂不可用，请检查后重新生成。'}</p>}
    </> : <div className="structure-preview-empty"><Box size={48} strokeWidth={1.3} /><h3>从想法到可装配的结构</h3><p>描述作品、选择硬件，再确认尺寸与布局。</p><span>矩形带盖外壳 · FDM 3D 打印</span></div>}
  </div>;
}
