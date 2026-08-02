import { spawnSync } from 'node:child_process';

export const REQUIRED_PYTHON_PACKAGES = ['cadquery', 'OCP', 'trimesh', 'fastapi', 'uvicorn'];
export const CADQUERY_RUNTIME_PACKAGES = ['cadquery', 'OCP'];
const PYTHON_VERSION_TIMEOUT_MS = 3000;
const PYTHON_PACKAGE_IMPORT_TIMEOUT_MS = 15000;

export function checkEnvironment(python, {
  spawn = spawnSync,
  requiredPythonPackages = REQUIRED_PYTHON_PACKAGES,
} = {}) {
  const pythonVersion = spawn(python, ['--version'], {
    encoding: 'utf8',
    timeout: PYTHON_VERSION_TIMEOUT_MS,
    windowsHide: true,
  });
  const pythonAvailable = pythonVersion.status === 0;
  const packageChecks = requiredPythonPackages.map((name) => checkPythonPackage({
    python,
    name,
    spawn,
    pythonAvailable,
  }));
  const missingPythonPackages = packageChecks
    .filter((item) => item.status !== 'pass')
    .map((item) => item.name);
  const cadqueryChecks = packageChecks.filter((item) => CADQUERY_RUNTIME_PACKAGES.includes(item.name));
  const cadqueryAvailable = pythonAvailable
    && cadqueryChecks.length === CADQUERY_RUNTIME_PACKAGES.length
    && cadqueryChecks.every((item) => item.status === 'pass');

  return {
    python,
    pythonAvailable,
    pythonVersion: outputText(pythonVersion),
    cadqueryAvailable,
    cadqueryError: cadqueryAvailable ? '' : summarizePackageErrors(cadqueryChecks, pythonAvailable),
    requiredPythonPackages,
    missingPythonPackages,
    packageChecks,
  };
}

function checkPythonPackage({ python, name, spawn, pythonAvailable }) {
  if (!pythonAvailable) {
    return {
      name,
      importName: name,
      status: 'skipped',
      available: false,
      error: 'Python is not available.',
    };
  }
  const result = spawn(python, ['-c', `import importlib; importlib.import_module(${JSON.stringify(name)}); print("ok")`], {
    encoding: 'utf8',
    timeout: PYTHON_PACKAGE_IMPORT_TIMEOUT_MS,
    windowsHide: true,
  });
  return {
    name,
    importName: name,
    status: result.status === 0 ? 'pass' : 'missing',
    available: result.status === 0,
    error: result.status === 0 ? '' : packageImportError(name, result),
  };
}

function summarizePackageErrors(packageChecks, pythonAvailable) {
  if (!pythonAvailable) return 'Python is not available.';
  const missing = packageChecks.filter((item) => item.status !== 'pass');
  if (!missing.length) return '';
  return missing.map((item) => `${item.name}: ${item.error}`).join('\n');
}

function outputText(result = {}) {
  return (result.stdout || result.stderr || '').trim();
}

function packageImportError(name, result = {}) {
  if (result.error?.code === 'ETIMEDOUT' || result.signal === 'SIGTERM') {
    return `${name} import timed out after ${PYTHON_PACKAGE_IMPORT_TIMEOUT_MS}ms`;
  }
  return outputText(result) || `${name} import failed`;
}
