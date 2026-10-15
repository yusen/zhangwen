#!/usr/bin/env bash
# macOS 13.5+ (Intel / Apple Silicon). Bash 3.2 compatible; no Homebrew/sudo.
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"
runtime=${ZHANGWEN_RUNTIME_DIR:-"$project_root/.runtime"}
mkdir -p "$runtime"
os=$(uname -s)
arch=$(uname -m)
if [ "$os" = Darwin ]; then
  mac_version=$(sw_vers -productVersion)
  major=${mac_version%%.*}; remainder=${mac_version#*.}; minor=${remainder%%.*}
  if [ "$major" -lt 13 ] || { [ "$major" -eq 13 ] && [ "$minor" -lt 5 ]; }; then
    echo 'Automatic runtime setup requires macOS 13.5 or later.' >&2; exit 1
  fi
fi
case "$os:$arch" in
  Darwin:arm64) node_platform=darwin-arm64; uv_platform=aarch64-apple-darwin
    node_sha=a1a54f46a750d2523d628d924aab61758a51c9dad3e0238beb14141be9615dd3
    uv_sha=3f61099e261e449527141dbf125629fab33ad696468c8c90cebbac40185a306c ;;
  Darwin:x86_64) node_platform=darwin-x64; uv_platform=x86_64-apple-darwin
    node_sha=f2879eb810e25993a0578e5d878930266fd2eafcffe9f2839b3d8db354d4879e
    uv_sha=76638fdcfa91357858771551a1c88de1f7c3b270b33ab1866f8a0618d9e442d8 ;;
  *) echo 'Automatic runtime setup requires macOS 13.5+ (Intel / Apple Silicon).' >&2; exit 1 ;;
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
  download_verified "https://nodejs.org/dist/v24.14.0/$name" "$name" "$node_sha"
  tar -xzf "$runtime/$name" -C "$runtime"
  node_exe="$node_dir/bin/node"
  export ZHANGWEN_NPM_CLI="$node_dir/lib/node_modules/npm/bin/npm-cli.js"
  node_ok "$node_exe" && "$node_exe" "$ZHANGWEN_NPM_CLI" --version >/dev/null
fi
export PATH="$(dirname "$node_exe"):$PATH"
python_ok() {
  [ -n "$1" ] && [ -x "$1" ] && "$1" -c 'import sys; assert sys.version_info >= (3,11)' >/dev/null 2>&1
}
python_exe="$project_root/.venv/bin/python"
if ! python_ok "$python_exe" || ! "$python_exe" -c 'import sys; assert sys.prefix != sys.base_prefix' 2>/dev/null; then
  base_python=''
  for candidate in "${ZHANGWEN_PYTHON:-}" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if python_ok "$candidate" && "$candidate" -c 'import venv, ensurepip' >/dev/null 2>&1; then base_python=$candidate; break; fi
  done
  if [ -e "$project_root/.venv" ]; then
    [ ! -L "$project_root/.venv" ] || { echo 'Refusing to move a linked .venv.' >&2; exit 1; }
    mv "$project_root/.venv" "$runtime/venv-invalid-$(date +%s)"
  fi
  if [ -n "$base_python" ]; then
    echo "Using installed Python: $base_python"
    "$base_python" -m venv "$project_root/.venv"
  else
    uv_exe="$runtime/uv-$uv_platform/uv"
    if ! [ -x "$uv_exe" ] || ! "$uv_exe" --version >/dev/null 2>&1; then
      candidate=$(command -v uv || true)
      if [ -n "$candidate" ] && "$candidate" --version >/dev/null 2>&1; then uv_exe=$candidate
      else
        name="uv-$uv_platform.tar.gz"
        download_verified "https://github.com/astral-sh/uv/releases/download/0.8.22/$name" "$name" "$uv_sha"
        tar -xzf "$runtime/$name" -C "$runtime"
      fi
    fi
    export UV_PYTHON_INSTALL_DIR="$runtime/python" UV_CACHE_DIR="$project_root/.cache/uv" UV_NO_MODIFY_PATH=1 UV_NATIVE_TLS=true
    "$uv_exe" venv --python 3.13.7 --managed-python --seed "$project_root/.venv"
  fi
fi
python_ok "$python_exe"
rmdir "$lock"
trap - EXIT
exec "$node_exe" scripts/setup.mjs "$@"
