import { ArrowRight, FolderOpen, LoaderCircle, Moon, Plus, RefreshCw, Sun } from 'lucide-react';
import palmMark from './assets/palm-mark.png';
import './start-screen.css';

type Props = {
  loading: boolean;
  ready: boolean;
  busy: string;
  error: string;
  theme: 'light' | 'dark';
  onTheme: () => void;
  onNew: () => void;
  onLoad: () => void;
  onRetry: () => void;
};

export function StartScreen({ loading, ready, busy, error, theme, onTheme, onNew, onLoad, onRetry }: Props) {
  const disabled = loading || !ready || !!busy;
  return <div className="start-screen">
    <header className="workspace-titlebar">
      <span className="title-brand"><span><img src={palmMark} alt="" width={24} height={24} /></span><strong>掌问：智能体造物工作台</strong></span>
      <span className="start-header-label">对话即创造</span>
      <button className="theme-toggle" aria-label={theme === 'light' ? '切换深色主题' : '切换浅色主题'} onClick={onTheme}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</button>
    </header>
    <main className="start-main" aria-label="项目初始页" aria-busy={loading || !!busy}>
      <section className="start-content" aria-labelledby="start-title">
        <img className="start-mark" src={palmMark} alt="" width={64} height={64} />
        <h1 id="start-title">从一个想法开始</h1>
        <p className="start-description">新建一个项目，或加载已有项目继续创作。</p>
        <div className="start-actions">
          <button className="start-project-action" aria-label="新建项目" disabled={disabled} onClick={onNew}>
            <span className="start-action-icon"><Plus size={26} aria-hidden="true" /></span>
            <span className="start-action-copy"><strong>新建项目</strong><span>选择本地文件夹，开始新的创作</span></span>
            <ArrowRight size={19} aria-hidden="true" />
          </button>
          <button className="start-project-action" aria-label="加载项目" disabled={disabled} onClick={onLoad}>
            <span className="start-action-icon"><FolderOpen size={26} aria-hidden="true" /></span>
            <span className="start-action-copy"><strong>加载项目</strong><span>打开项目文件夹或最近的项目</span></span>
            <ArrowRight size={19} aria-hidden="true" />
          </button>
        </div>
        <div className="start-feedback">
          {(loading || busy) && <p role="status"><LoaderCircle size={17} className="spin" aria-hidden="true" />{loading ? '正在准备工作台…' : busy + '…'}</p>}
          {error && !loading && <div className="start-error" role="alert"><p>{error}</p>{!ready && <button onClick={onRetry}><RefreshCw size={16} />重新连接</button>}</div>}
          {!loading && !busy && !error && <p>加载项目后，可继续查看历史对话和代码版本。</p>}
        </div>
      </section>
    </main>
    <footer className="start-footer">智能工程师<span aria-hidden="true">·</span>结构工程师<span aria-hidden="true">·</span>学习设计师</footer>
  </div>;
}
