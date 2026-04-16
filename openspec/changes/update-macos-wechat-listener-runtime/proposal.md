## Why

仓库已经把正式分支定位切到 `Apple Silicon macOS`，但当前真正负责“微信窗口读取 + 会话预览监听 + worker 恢复”的主链路仍然绑定在 `Win32 + uiautomation` 上，导致 README 和迁移计划声明的 mac-only 目标还没有落到可运行实现。
这件事现在必须单独成 change，因为 `docs/apple-silicon-mac-adaptation-plan.md` 已经把“mac 监听适配 Spike”和“worker 与 runtime 接通”定义为最先完成的两阶段，而现有 `backend_main.py + desktop-shell/` 正常与否就取决于这一段能否迁到 mac 且继续维持现有 runtime 契约。

## What Changes

- 把 `wechat_auto/window.py`、`wechat_auto/controls.py`、`listener_app/group_listener_worker.py` 的底层读取实现从 `Win32 + uiautomation` 切到 `Apple Silicon macOS` 可用的窗口与 Accessibility 读取链路。
- 保持当前产品边界不变，继续只读取微信左侧可见会话列表预览，继续维持 `all_sessions + preview_only` 语义，不扩成右侧正文抓取器，也不恢复主动操作能力。
- 保持 `listener_app/backend_runtime.py`、`listener_app/runtime_api.py` 暴露给前端的本地 `HTTP + WebSocket` 接口不变，但让 worker 在微信未启动、辅助功能未授权、主窗口临时丢失、弹窗阻塞等场景下返回可解释且可恢复的状态。
- 更新运行时监督、测试和文档，使 mac listener/runtime 的权限、恢复、降级与验证口径成为仓库内正式事实，而不是继续沿用 Windows 旧约束。

## Capabilities

### New Capabilities
- `desktop-wechat-listener-runtime`: 定义 Apple Silicon macOS 下微信左侧会话预览监听、worker 恢复状态以及对现有 runtime API 的稳定兼容语义。

### Modified Capabilities
- None.

## Impact

- **Affected code**:
  - `wechat_auto/window.py`
  - `wechat_auto/controls.py`
  - `listener_app/group_listener_worker.py`
  - `listener_app/backend_runtime.py`
  - `listener_app/backend_main.py`
  - `listener_app/sidebar_runtime_support.py`
  - `listener_app/runtime_api.py`
  - `pyproject.toml`
  - `requirements.txt`
  - `tests/test_backend_runtime.py`
  - `tests/test_runtime_api.py`
  - `tests/test_group_listener_worker_helpers.py`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - `/healthz`
  - `/api/runtime`
  - `/api/sessions`
  - worker `status` / `session_snapshot` / `message` 事件语义
- **Dependencies / systems**:
  - Apple Silicon macOS Accessibility 权限与窗口读取能力
  - 本地源码态 `backend_main.py + desktop-shell/` 调试链路
  - worker supervisor、重连和降级状态流
