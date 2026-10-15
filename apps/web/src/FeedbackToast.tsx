import { useEffect, useState } from 'react';
import { Check, LoaderCircle, X } from 'lucide-react';

export function FeedbackToast({ error, notice, sequence, busy, progress, onCancel }: {
  error: string; notice: string; sequence: number; busy: string; progress: number | null; onCancel: () => void;
}) {
  const [visible, setVisible] = useState(true);
  const [paused, setPaused] = useState(false);
  const text = error || (busy ? `${busy}中…` : notice);
  useEffect(() => { setVisible(true); setPaused(false); }, [text, busy, sequence]);
  useEffect(() => {
    if (!text || busy || paused || !visible) return;
    const timer = window.setTimeout(() => setVisible(false), error ? 8000 : 4000);
    return () => window.clearTimeout(timer);
  }, [text, error, busy, sequence, paused, visible]);
  if (!text || !visible) return null;
  return <div className={`feedback feedback-toast ${error ? 'error' : ''}`}
    role={error ? 'alert' : 'status'} aria-atomic="true"
    onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
    onFocusCapture={() => setPaused(true)} onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false); }}>
    {error ? <X size={17} /> : busy ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />}
    <span className="feedback-text">{text}</span>
    {progress !== null && <div className="toast-progress"><progress aria-label="上传进度" value={progress} max="100" /><span>{progress}%</span><button onClick={onCancel}>取消上传</button></div>}
    {!busy && <button className="icon-button" aria-label="关闭提示" onClick={() => setVisible(false)}><X size={16} /></button>}
  </div>;
}
