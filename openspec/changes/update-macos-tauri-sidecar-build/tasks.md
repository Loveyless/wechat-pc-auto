## 1. Rust bootstrap mac 适配

- [x] 1.1 用 mac-compatible helper 替换 `desktop-shell/src-tauri/src/backend/win32.rs` 的锁、进程身份和 owned-backend 清理实现，并更新 `bootstrap.rs` / `Cargo.toml` 接线
- [x] 1.2 补或更新 Rust 回归，覆盖 runtime root、marker 路径、target-triple 命名辅助逻辑和不再依赖 Win32 事实的 bootstrap 行为

## 2. Sidecar 构建与 Tauri 接线

- [x] 2.1 重写 `scripts/build_desktop_shell_sidecars.py`，让 PyInstaller 产物和 `desktop-shell/src-tauri/binaries/` 安装名遵守 mac 平台的 target-triple + 无 `.exe` 规则
- [x] 2.2 更新 `desktop-shell/package.json`、必要的 Tauri 接线与相关测试/脚本辅助逻辑，使 `npm run tauri dev` / `npm run tauri build` 继续复用同一套 sidecar 构建约定

## 3. Release smoke 与文档收口

- [x] 3.1 重写 `scripts/smoke_desktop_shell_release.py` 及其测试，让 smoke 在 mac 上校验 release shell 路径、`/healthz`、single-instance relaunch 和 cleanup 观察点
- [x] 3.2 更新 `docs/desktop-shell-build.md` 与 `docs/wechat-listening-pitfalls.md`，把 mac-only sidecar 命名、runtime root、release smoke 和 cleanup 语义写成正式事实
- [ ] 3.3 运行目标回归与构建命令；若受限于当前环境，记录受限验收步骤、缺口和风险等级
