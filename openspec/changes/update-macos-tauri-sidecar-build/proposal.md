## Why

当前分支已经明确收敛到 `Apple Silicon macOS`，但桌面壳的 sidecar 托管、构建脚本和 release smoke 仍然绑定在 Windows 事实源上：Rust bootstrap 直接依赖 `win32.rs`，构建链固定产出 `.exe`，release smoke 也仍然假设 `%LOCALAPPDATA%` 和 `taskkill` 存在。  
这件事必须现在单独成 change，因为 `docs/apple-silicon-mac-adaptation-plan.md` 已经把 “mac sidecar 托管 + 本地构建闭环” 定义为独立阶段；如果这段不先落地，`npm run tauri dev` / `npm run tauri build` 在当前分支上的通过与否就没有稳定口径。

## What Changes

- 把 `desktop-shell/src-tauri/src/backend/bootstrap.rs` 从 Windows 专属 helper 切到 mac-compatible 的进程身份、锁和退出清理实现，不再依赖 Win32 mutex、`taskkill` 或 `.exe` 约定。
- 保留当前桌面壳的 single-instance、owned-backend、`/healthz` readiness 和 `app_local_data_dir` runtime root 语义，但把这些语义落实到 `arm64 macOS` 的 sidecar 启动与清理链路。
- 重写 `scripts/build_desktop_shell_sidecars.py`、`scripts/smoke_desktop_shell_release.py` 与相关测试/接线，让 sidecar 构建、release smoke 和本地 build 输出都使用 mac target triple 与无扩展名 sidecar 命名。
- 更新桌面壳构建与踩坑文档，让 “mac-only 构建闭环、release smoke 观察点、runtime root 与 cleanup 语义” 成为仓库内正式事实。

## Capabilities

### New Capabilities

- `desktop-shell-bootstrap`: 定义 Apple Silicon macOS 下桌面壳 sidecar 托管、runtime root、single-instance 下的 owned-backend 复用与退出清理语义。
- `desktop-shell-release-verification`: 定义 Apple Silicon macOS 下 sidecar 构建产物命名、release smoke 观察点和构建验收入口。

### Modified Capabilities

- None.

## Impact

- **Affected code**:
  - `desktop-shell/src-tauri/src/main.rs`
  - `desktop-shell/src-tauri/src/backend/mod.rs`
  - `desktop-shell/src-tauri/src/backend/bootstrap.rs`
  - `desktop-shell/src-tauri/src/backend/win32.rs`（删除或替换）
  - `desktop-shell/src-tauri/Cargo.toml`
  - `desktop-shell/src-tauri/tauri.conf.json`
  - `desktop-shell/package.json`
  - `scripts/build_desktop_shell_sidecars.py`
  - `scripts/smoke_desktop_shell_release.py`
  - `tests/test_smoke_desktop_shell_release.py`
  - `docs/desktop-shell-build.md`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - Tauri `bundle.externalBin` sidecar 命名与查找约定
  - 桌面壳 managed backend 的 runtime root / marker / bootstrap log 语义
  - release smoke 对 `/healthz`、single-instance、cleanup 的验收口径
- **Dependencies / systems**:
  - Apple Silicon macOS 进程管理与 `app_local_data_dir`
  - PyInstaller sidecar 构建产物
  - Tauri shell sidecar 托管与 release build 目录
