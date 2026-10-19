#!/usr/bin/env bash
# macOS 13.5+ (Intel / Apple Silicon). Bash 3.2 compatible; no Homebrew/sudo.
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"
runtime=${ZHANGWEN_RUNTIME_DIR:-"$project_root/.runtime"}
mkdir -p "$runtime"
os=$(uname -s)
arch=$(uname -m)
download_source=${ZHANGWEN_DOWNLOAD_SOURCE:-global}
case "$download_source" in cn|global) ;; *) echo 'Invalid download source.' >&2; exit 1 ;; esac
if [ "$os" = Darwin ]; then
  mac_version=$(sw_vers -productVersion)
  major=${mac_version%%.*}; remainder=${mac_version#*.}; minor=${remainder%%.*}
  if [ "$major" -lt 13 ] || { [ "$major" -eq 13 ] && [ "$minor" -lt 5 ]; }; then
    echo 'Automatic runtime setup requires macOS 13.5 or later.' >&2; exit 1
  fi
fi
case "$os:$arch" in
  Darwin:arm64) node_platform=darwin-arm64; python_platform=aarch64-apple-darwin
    node_sha=a1a54f46a750d2523d628d924aab61758a51c9dad3e0238beb14141be9615dd3 ;;
  Darwin:x86_64) node_platform=darwin-x64; python_platform=x86_64-apple-darwin
    node_sha=f2879eb810e25993a0578e5d878930266fd2eafcffe9f2839b3d8db354d4879e ;;
  *) echo 'Automatic runtime setup requires macOS 13.5+ (Intel / Apple Silicon).' >&2; exit 1 ;;
esac
case "$arch" in
  arm64) python_sha=10f26ea5fc7c4d9c012faf372898a801f34b8fd7730c677576263224d56835fe ;;
  x86_64) python_sha=e640143d4dde2edff1865c3e88e44b046478b790af4f8b3ac4d228e53952dda0 ;;
esac
lock="$runtime/bootstrap-unix.lock"
if ! mkdir "$lock" 2>/dev/null; then
  echo "Another setup may be running. After it closes, remove $lock if left by an interrupted setup." >&2; exit 1
fi
trap 'rmdir "$lock" 2>/dev/null || true' EXIT
download_verified() {
  local url=$1 name=$2 expected=$3 file="$runtime/$2"
  if [ ! -f "$file" ] || [ "$(shasum -a 256 "$file" | cut -d ' ' -f 1)" != "$expected" ]; then
    echo "Downloading $name ..."
    curl --fail --location --retry 3 --connect-timeout 15 --max-time 600 "$url" -o "$file.partial"
    [ "$(shasum -a 256 "$file.partial" | cut -d ' ' -f 1)" = "$expected" ] || { echo "SHA-256 mismatch: $name" >&2; return 1; }
    mv "$file.partial" "$file"
  fi
}
node_ok() {
  [ -x "$1" ] && "$1" -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' >/dev/null 2>&1
}
echo 'Checking installed Node.js, npm and Python (offline) ...'
node_dir="$runtime/node-v24.14.0-$node_platform"
node_exe=''
for candidate in "$node_dir/bin/node" "$(command -v node || true)"; do
  if node_ok "$candidate"; then
    npm_cli="$(dirname "$candidate")/../lib/node_modules/npm/bin/npm-cli.js"
    if [ -f "$npm_cli" ] && "$candidate" "$npm_cli" --version >/dev/null 2>&1; then
      node_exe=$candidate; export ZHANGWEN_NPM_CLI="$npm_cli"; break
    elif command -v npm >/dev/null && npm --version >/dev/null 2>&1; then
      node_exe=$candidate; break
    fi
  fi
done
if [ -z "$node_exe" ]; then
  name="node-v24.14.0-$node_platform.tar.gz"
  node_url="https://nodejs.org/dist/v24.14.0/$name"
  if [ "$download_source" = cn ]; then node_url="https://cdn.npmmirror.com/binaries/node/v24.14.0/$name"; fi
  download_verified "$node_url" "$name" "$node_sha"
  tar -xzf "$runtime/$name" -C "$runtime"
  node_exe="$node_dir/bin/node"
  export ZHANGWEN_NPM_CLI="$node_dir/lib/node_modules/npm/bin/npm-cli.js"
  node_ok "$node_exe" && "$node_exe" "$ZHANGWEN_NPM_CLI" --version >/dev/null
fi
export PATH="$(dirname "$node_exe"):$PATH"
python_ok() {
  # Apple's developer-tool shim can open an Xcode installation dialog on a
  # fresh Mac. Use an independent interpreter or the managed Python instead.
  case "$1" in /usr/bin/python|/usr/bin/python3) return 1 ;; esac
  [ -n "$1" ] && [ -x "$1" ] && "$1" -c 'import platform, sys; assert sys.version_info >= (3,12) and (sys.platform != "darwin" or platform.machine() != "x86_64" or sys.version_info < (3,14))' >/dev/null 2>&1
}
python_venv_ok() {
  python_ok "$1" && "$1" -c 'import venv, ensurepip' >/dev/null 2>&1
}
python_exe="$project_root/.venv/bin/python"
if ! python_ok "$python_exe" || ! "$python_exe" -c 'import sys; assert sys.prefix != sys.base_prefix' 2>/dev/null; then
  base_python=''
  for candidate in "${ZHANGWEN_PYTHON:-}" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if python_venv_ok "$candidate"; then base_python=$candidate; break; fi
  done
  # Reuse shared managed Python independently of the source version.
  managed_python="$runtime/python/cpython-3.13.7-20250918-$python_platform/bin/python3"
  if [ -z "$base_python" ]; then
    for candidate in "$managed_python" "$runtime"/python/*/bin/python3; do
      if python_venv_ok "$candidate"; then base_python=$candidate; break; fi
    done
  fi
  if [ -z "$base_python" ]; then
    echo 'No working Python with venv support was found. Preparing standalone Python ...'
    name="cpython-3.13.7+20250918-$python_platform-install_only_stripped.tar.gz"
    python_url="https://github.com/astral-sh/python-build-standalone/releases/download/20250918/${name//+/%2B}"
    if [ "$download_source" = cn ]; then python_url="https://cdn.npmmirror.com/binaries/python-build-standalone/20250918/${name//+/%2B}"; fi
    download_verified "$python_url" "$name" "$python_sha"
    python_home="$runtime/python/cpython-3.13.7-20250918-$python_platform"
    [ ! -e "$python_home" ] || { echo "Unusable managed Python preserved: $python_home" >&2; exit 1; }
    stage=$(mktemp -d "$runtime/python-extract-XXXXXX")
    tar -xzf "$runtime/$name" -C "$stage"
    python_venv_ok "$stage/python/bin/python3" || { echo 'Downloaded Python did not pass its venv/ensurepip check.' >&2; exit 1; }
    mkdir -p "$runtime/python"
    mv "$stage/python" "$python_home"
    rmdir "$stage"
    python_venv_ok "$managed_python" || { echo 'Standalone Python did not pass its execution check.' >&2; exit 1; }
    base_python=$managed_python
  fi
  if [ -e "$project_root/.venv" ] || [ -L "$project_root/.venv" ]; then
    [ ! -L "$project_root/.venv" ] || { echo 'Refusing to move a linked .venv.' >&2; exit 1; }
    mv "$project_root/.venv" "$runtime/venv-invalid-$(date +%s)"
  fi
  echo "Using Python: $base_python"
  "$base_python" -m venv "$project_root/.venv"
fi
python_ok "$python_exe"
"$python_exe" -c 'import sys; assert sys.prefix != sys.base_prefix'
rmdir "$lock"
trap - EXIT
exec "$node_exe" scripts/setup.mjs "$@"
