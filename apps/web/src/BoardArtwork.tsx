import { useState } from 'react';
import type { HardwareSummary } from '../../../packages/contracts/src/mu';

/** Existing package photos take precedence; boards without media get a labelled diagram. */
export function BoardArtwork({ board }: { board?: HardwareSummary }) {
  const [failed, setFailed] = useState('');
  const photo = board?.media.find(item => item.path.includes('cover')) ?? board?.media[0];
  if (photo && failed !== photo.url) return <img className="board-artwork" src={photo.url} alt={board?.displayName} onError={() => setFailed(photo.url)} />;
  const id = board?.componentId ?? '';
  const mpython = id.includes('mpython');
  const label = id.includes('v2') ? '2.0' : id.includes('v3') ? '3.0' : id.includes('c3') ? 'C3' : id.includes('xiao') ? 'S3' : 'MCU';
  return <svg className="board-artwork board-diagram" viewBox="0 0 80 64" role="img" aria-label={`${board?.displayName ?? '主控板'}示意图`}>
    <rect x={mpython ? 5 : 19} y="3" width={mpython ? 70 : 42} height="58" rx="6" fill={mpython ? '#233e65' : '#286451'} stroke="#c4d2e2" />
    <rect x="31" y="1" width="18" height="9" rx="2" fill="#c5cbd2" />
    {mpython ? <><rect x="19" y="15" width="42" height="25" rx="2" fill="#172029" stroke="#91a6bc" /><circle cx="13" cy="45" r="4" fill="#f4cb71" /><circle cx="67" cy="45" r="4" fill="#f4cb71" /></> : <rect x="29" y="16" width="22" height="27" fill="#b5bac4" stroke="#e6e9ed" />}
    {[0, 1, 2, 3, 4, 5].map(pin => <rect key={pin} x={mpython ? 14 + pin * 9 : 22 + pin * 6} y="55" width="4" height="7" fill="#d5b55c" />)}
    <text x="40" y={mpython ? 32 : 35} textAnchor="middle" fontSize="11" fontFamily="sans-serif" fill={mpython ? '#fff' : '#213143'}>{label}</text>
  </svg>;
}
