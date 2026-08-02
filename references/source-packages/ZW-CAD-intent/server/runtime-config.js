import { existsSync } from 'node:fs';
import path from 'node:path';

export function resolvePythonExecutable({
  projectRoot,
  env = process.env,
  fileExists = existsSync,
} = {}) {
  const configured = String(env.ZW_CAD_INTENT_PYTHON || env.PYTHON || '').trim();
  if (configured) return configured;

  const candidates = [
    path.join(projectRoot, 'runtime', 'python', 'python.exe'),
    path.resolve(projectRoot, '..', 'runtime', 'python', 'python.exe'),
  ];
  return candidates.find(fileExists) || 'python';
}

export function resolveServerHost(env = process.env) {
  return String(env.ZW_CAD_INTENT_HOST || '').trim();
}

export function listenHttpServer(server, { port, host = '', onListening } = {}) {
  if (host) return server.listen(port, host, onListening);
  return server.listen(port, onListening);
}
