# MVP 构建信息

生成时间：2026-07-08
范围：ZW-005 至 ZW-016
分支：`codex/zw-005-016-autonomous`

## 自动验证命令

| 命令 | 结果 |
|---|---|
| `pnpm --filter @zhangwen/contracts build` | 通过 |
| `pnpm --filter @zhangwen/contracts typecheck` | 通过 |
| `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw016_mvp_integration.py -q --rootdir services/local-api` | 2 passed |
| `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` | 95 passed |
| `pnpm --filter @zhangwen/desktop test` | 48 passed |
| `pnpm --filter @zhangwen/desktop typecheck` | 通过 |
| `pnpm --filter @zhangwen/desktop build` | 通过 |
| `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen` | 通过 |
| `pnpm tauri:build` | 通过；Rust release target compiled |

备注：pytest 结束时仍有已知 Windows 临时目录 cleanup `PermissionError`，测试结果为通过。Starlette `httpx` deprecation warning 仍存在，不影响当前 MVP 自动验收。

## 前端构建产物

- `apps/desktop/dist/index.html`
- `apps/desktop/dist/assets/index-C4YSe-tD.css`
- `apps/desktop/dist/assets/index-G8MVQ-Rk.js`

## Tauri/Rust Release 产物

- `apps/desktop/src-tauri/target/release/zhangwen-desktop.exe`
- `apps/desktop/src-tauri/target/release/zhangwen_desktop_lib.dll`
- `apps/desktop/src-tauri/target/release/libzhangwen_desktop_lib.rlib`

## 构建边界

- `pnpm tauri:build` 当前执行 `pnpm build:desktop && cargo build --release --manifest-path apps/desktop/src-tauri/Cargo.toml`。
- 本次验证确认 Windows 桌面壳 release target 可编译。
- 未生成 NSIS 安装包、代码签名或公开发布产物；这些不属于 ZW-016 范围。

## 安全确认

- 未发现真实 API Key、Authorization、Bearer token、真实串口标识或个人绝对路径。
- 自动测试未调用真实 DeepSeek、真实串口、真实 Shell、真实 CadQuery、Flash 擦除或固件烧录。
- ZW-016 完成后停止连续开发；不得创建、规划或实现 ZW-017。
