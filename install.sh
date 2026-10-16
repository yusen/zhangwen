#!/usr/bin/env bash
# Run: curl -fsSL https://raw.githubusercontent.com/yusen/zhangwen/main/install.sh | bash
set -euo pipefail
[ "$(uname -s)" = Darwin ] || { echo 'This installer requires macOS 13.5+.' >&2; exit 1; }
install_root=${ZHANGWEN_INSTALL_DIR:-"$HOME/Library/Application Support/ZhangWen"}
mkdir -p "$install_root/versions"
install_root=$(cd "$install_root" && pwd)
lock="$install_root/install.lock"
mkdir "$lock" 2>/dev/null || { echo "Another installer may be running; interrupted setup lock: $lock" >&2; exit 1; }
trap 'rmdir "$lock" 2>/dev/null || true' EXIT
revision=${ZHANGWEN_REVISION:-}
if [ -z "$revision" ]; then
  revision=$(curl -fsSL --retry 3 --connect-timeout 15 --max-time 60 -H 'User-Agent: zhangwen-installer' https://api.github.com/repos/yusen/zhangwen/git/ref/heads/main | sed -nE 's/.*"sha": *"([0-9a-f]{40})".*/\1/p' | head -n 1)
fi
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid GitHub revision.' >&2; exit 1; }
app="$install_root/versions/$revision"
verify_package() {
  [ -f "$1/DEPLOYMENT.sha256" ] || return 1
  # Reject paths outside the extracted root before feeding the checksum tool.
  awk 'length($1)!=64 || $1 ~ /[^0-9a-f]/ || $2 ~ /^\// || $2 ~ /(^|\/)\.\.(\/|$)/ {exit 1}' "$1/DEPLOYMENT.sha256" || return 1
  (cd "$1" && shasum -a 256 -c DEPLOYMENT.sha256 >/dev/null 2>&1)
}
if ! verify_package "$app"; then
  [ ! -e "$app" ] || { echo "Modified/incomplete version preserved: $app. Move it aside and retry." >&2; exit 1; }
  work=$(mktemp -d "$install_root/download-XXXXXX")
  echo "Downloading platform $revision ..."
  curl -fL --retry 3 --connect-timeout 15 --max-time 600 "https://codeload.github.com/yusen/zhangwen/zip/$revision" -o "$work/source.zip"
  unzip -Z1 "$work/source.zip" | awk '/^\/|\\|(^|\/)\.\.($|\/)/ {exit 1}' || { echo 'Unsafe archive entry.' >&2; exit 1; }
  unzip -q "$work/source.zip" -d "$work/extracted"
  set -- "$work/extracted"/*
  [ "$#" -eq 1 ] && verify_package "$1" || { echo 'Deployment file verification failed.' >&2; exit 1; }
  mv "$1" "$app"
else echo 'Platform files are current; skipping source download.'
fi
export ZHANGWEN_DATA_DIR="$install_root/data"
export ZHANGWEN_RUNTIME_DIR="$install_root/runtime"
bash "$app/scripts/bootstrap-unix.sh" --prepare-only
cat > "$install_root/启动掌问.command" <<'LAUNCH'
#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
revision=$(cat "$root/current.txt")
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 1
export ZHANGWEN_DATA_DIR="$root/data"
export ZHANGWEN_RUNTIME_DIR="$root/runtime"
exec bash "$root/versions/$revision/start-web.sh"
LAUNCH
chmod +x "$install_root/启动掌问.command"
app_args=(--install-root "$install_root")
if [ -n "${ZHANGWEN_APPLICATIONS_DIR:-}" ]; then app_args+=(--applications-dir "$ZHANGWEN_APPLICATIONS_DIR"); fi
"$app/.venv/bin/python" "$app/scripts/create-macos-app.py" "${app_args[@]}"
printf '%s\n' "$revision" > "$install_root/current.txt.tmp"
mv "$install_root/current.txt.tmp" "$install_root/current.txt"
echo "Installed: $app"
echo "Data: $ZHANGWEN_DATA_DIR"
rmdir "$lock"
trap - EXIT
if [ "${ZHANGWEN_NO_START:-0}" != 1 ]; then exec bash "$install_root/启动掌问.command"; fi
