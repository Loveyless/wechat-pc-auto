## Context

当前桌面壳的主路径已经是 `backend_main.py + desktop-shell/`，single-instance、`/healthz` readiness、owned-backend marker 和 `app_local_data_dir` runtime root 这些语义也已经在 Rust bootstrap 里成形。  
真正还没有迁到 mac 的，是操作系统绑定层和构建闭环：

- `desktop-shell/src-tauri/src/backend/bootstrap.rs` 仍直接依赖 `backend::win32`
- `desktop-shell/src-tauri/Cargo.toml` 仍强绑定 `windows-sys`
- `scripts/build_desktop_shell_sidecars.py` 固定查找/安装 `.exe`
- `scripts/smoke_desktop_shell_release.py` 固定使用 `%LOCALAPPDATA%`、`taskkill` 和 `wechat-auto-shell.exe`
- `docs/desktop-shell-build.md` / `docs/wechat-listening-pitfalls.md` 仍把 Windows build 输出写成当前事实

这次 change 不是重新设计 shell 协议，而是把已有桌面壳能力落到 `Apple Silicon macOS` 的可运行实现，同时保持当前分支已经确认的产品边界。

## Goals / Non-Goals

**Goals:**

- 在 `arm64 macOS` 上保留当前桌面壳的 managed-backend、single-instance、`/healthz` readiness 和 runtime root 语义。
- 让 Tauri sidecar 构建链与 `externalBin` 命名在 mac 上可解释、可验证，并去掉 `.exe` / `taskkill` / Win32 mutex 依赖。
- 让 release smoke 在 mac 上验证 “壳启动、健康就绪、二次启动聚焦、退出后 backend 清理” 这几类关键观察点。
- 把构建/排障文档更新为 mac-only 正式事实。

**Non-Goals:**

- 不改桌面前端 UI，不重写现有本地 `HTTP + WebSocket` runtime API。
- 不同时维护 Windows / Intel Mac 双实现。
- 不把 notarization、签名或正式分发流程纳入这次 change 的阻塞范围。
- 不回退到“手工先起一份 `backend_main.py`”作为桌面壳的正式交付模式。

## Decisions

### Decision: 用 mac-compatible 平台 helper 替换 `backend::win32`，但保留 bootstrap 核心语义

Rust bootstrap 继续保留现有职责：
- 解析 `app_local_data_dir`
- 维护 backend marker
- 通过 `/healthz` 探测 readiness
- 复用已有 backend
- 在退出和 restart 时清理 owned backend

变化只发生在平台绑定 helper：
- 用 mac-compatible 的实现替代 `win32.rs`
- 通过进程身份探测、命令级 kill 和受控 fallback 完成“是否存活 / 启动 token / 清理 owned backend”
- 不再依赖 Win32 mutex 或 `taskkill`

这样做的原因是当前 change 的目标是平台迁移，不是重写 bootstrap 协议。把平台细节收口到 helper 层，能避免把 `/healthz`、marker 和 restart 逻辑再拆一遍。

**Alternatives considered**

- **直接在 `bootstrap.rs` 里内联所有 mac 逻辑**：拒绝，因为会把平台细节重新打散进热路径。
- **继续保留 `win32.rs`，只在 mac 上绕过部分调用**：拒绝，因为当前分支已经明确不再维护 Windows 事实。

### Decision: `app_local_data_dir` 继续作为 runtime root 真相源，marker / log / config 路径全部沿用这套根目录

当前 `bootstrap.rs` 已经把 `app.path().app_local_data_dir()` 作为 runtime root 源头，Python 侧也通过 `WECHAT_AUTO_RUNTIME_ROOT` 在 runtime root 下初始化 `config/`、`logs/` 和 `.env.local`。  
本 change 保持这条边界不变，只把 smoke、文档和测试里的 Windows 路径假设全部改成 mac 路径事实。

这样做的原因是 runtime root 已经是桌面壳 owned-backend 语义的一部分。若这次顺手改成别的根目录，会把问题从“平台适配”扩大成“重新定义运行时目录契约”。

**Alternatives considered**

- **把 runtime root 改回仓库目录或可执行同目录**：拒绝，因为会破坏现有壳运行时与源码态配置隔离。
- **在 smoke 脚本里硬编码另一套临时目录**：拒绝，因为会让 smoke 结果与实际壳行为脱节。

### Decision: sidecar 构建和 Tauri 接线统一遵守 “target triple + 平台扩展名” 规则

构建链以 `rustc` host target triple 为准：
- Windows 仍是 `name-<target>.exe`
- macOS / Linux 使用 `name-<target>`，不附 `.exe`

`tauri.conf.json` 继续使用 `bundle.externalBin` 的裸前缀写法，Rust 侧继续通过 `app.shell().sidecar("<name>")` 启动。  
这样能与 Tauri v2 的 sidecar 命名规则对齐，避免 mac 上复制出了文件但 Tauri 找不到 sidecar。

**Alternatives considered**

- **继续固定复制 `.exe`，在 mac 上靠额外重命名兼容**：拒绝，因为这会让构建和运行时命名脱节。
- **手工把完整 target 文件名写进 Rust `sidecar()` 调用**：拒绝，因为 Tauri 侧要求传 sidecar 基名而不是完整路径。

### Decision: release smoke 在 mac 上验证“可运行壳”而不是只验证脚本返回码

`scripts/smoke_desktop_shell_release.py` 将继续承担真正的 packaged smoke：
- 必要时触发 `npm run tauri build`
- 定位 mac release shell 可执行文件
- 等待 `/healthz`
- 检查 bootstrap log
- 第二次启动验证 single-instance 聚焦而非重复 spawn
- 关闭壳后确认 health 不再可达

这样做的原因是当前 change 的风险不在“命令能跑完”，而在“构建出来的壳是否真的托管 sidecar、是否重复 spawn、是否能收干净”。

**Alternatives considered**

- **只保留 `npm run tauri build` 作为验收**：拒绝，因为 build 通过不等于 sidecar 和 cleanup 语义正确。
- **只做单元测试，不做 packaged smoke**：拒绝，因为 `externalBin` 命名和 release 目录布局必须通过真实产物验证。

## Risks / Trade-offs

- **[mac 进程身份与清理实现不如 Win32 API 精细]** → helper 优先提供稳定的 “存活判断 + token + 清理” 最小集，并保留 `CommandChild.kill()` 作为兜底。
- **[不同 Tauri build 输出位置可能导致 smoke 找错可执行文件]** → 先用固定优先级查找常见 mac release 落点，并允许脚本参数覆盖。
- **[文档更新容易与用户当前未提交的 mac-only 文案冲突]** → 只更新本 change 必须同步的构建与排障文档，不顺手改用户正在整理的 README/分支说明。
- **[本地环境未必具备完整 Tauri/mac 打包前提]** → 保留受限验收路径，在 CSV `notes` 明确未验证项、手工步骤和风险等级。

## Migration Plan

1. 先替换 Rust bootstrap 的平台 helper，并补针对 runtime root、marker 和 sidecar 命名的 Rust 回归。
2. 再调整 PyInstaller sidecar 构建脚本、`package.json` / Tauri 接线，确保 mac target triple 命名与 `externalBin` 一致。
3. 重写 release smoke 默认路径与清理逻辑，并补 Python 测试。
4. 最后更新 `docs/desktop-shell-build.md` 与 `docs/wechat-listening-pitfalls.md`，再执行目标回归与受限验收。

**Rollback strategy**

- 如果 mac helper 导致 managed-backend 启动/清理退化，先回退 helper 接线并保留现有 shell 其它逻辑，不把不稳定 helper 挂到正式路径。
- 如果 sidecar 命名或 release smoke 仍不稳定，允许暂时只把 `npm run tauri dev` 作为开发闭环，但不得把 `npm run tauri build` 产物宣称为已验收 release。

## Open Questions

- None. 当前 plan 已明确 change 只覆盖 mac sidecar 与构建闭环，不扩到 notarization、正式发布或新的桌面协议。
