/** Only literal private IPv4 HTTP control panels; discard the native page hash. */
export function mosaicoPanelEndpoint(value: string): string | null {
  const match = /^http:\/\/((?:\d{1,3}\.){3}\d{1,3})(?::([0-9]{1,5}))?\/?(?:#[a-zA-Z][a-zA-Z0-9-]*)?$/.exec(value.trim());
  if (!match) return null;
  const octets = match[1].split('.').map(Number);
  if (octets.some((n, i) => n > 255 || String(n) !== match[1].split('.')[i])) return null;
  const [a, b] = octets;
  if (!(a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168))) return null;
  const port = match[2] ? Number(match[2]) : 80;
  if (port < 1 || port > 65535) return null;
  return `http://${match[1]}${port === 80 ? '' : `:${port}`}`;
}
