## Context

当前正式桌面路径已经收敛为 `listener_app/backend_main.py + desktop-shell/`，前端只依赖本地 `HTTP + WebSocket` runtime API，不直接读取 worker stdout。
真正还没有完成 mac 迁移的是底层监听实现：`wechat_auto/window.py`、`wechat_auto/controls.py`、`listener_app/group_listener_worker.py` 仍然假设 `Win32 + uiautomation` 存在，而 `backend_runtime.py` 已经把主语义固定成 `monitor_scope=all_sessions` 和 `message_fidelity=preview_only`。
本 change 既是平台迁移，又是高风险行为保持任务：不能因为切到底层实现就顺手改 API 面、改前端消费方式，或把左侧会话预览监听偷偷扩成右侧正文抓取。

## Goals / Non-Goals

**Goals:**
- 在 `Apple Silicon macOS` 上提供可运行的微信窗口定位、辅助功能权限检查和左侧会话列表预览读取链路。
- 让 worker 在 mac 上继续输出当前前端兼容的 `status` / `session_snapshot` / `message` 事件，不改 `backend_main.py + desktop-shell/` 的消费方式。
- 让 runtime 在微信未启动、权限缺失、窗口临时丢失、弹窗遮挡时保持存活并进入可解释、可恢复状态。
- 把 mac listener/runtime 的依赖、测试和文档收敛成仓库内正式事实。

**Non-Goals:**
- 不引入右侧聊天区正文抓取作为默认路径。
- 不恢复发送消息、自动回复、写输入框等主动操作。
- 不为了兼容旧分支继续维护 Windows / Intel Mac 双实现。
- 不重写 `runtime_api.py`、`runtime_engine.py` 或前端状态模型的整体结构。

## Decisions

### Decision: 读取真相源改为 macOS Accessibility + WeChat 窗口枚举，激活/刷新只保留为辅助动作

`wechat_auto/window.py` 与 `wechat_auto/controls.py` 将引入 mac-only 适配层，负责：
- 检查 WeChat 进程和主窗口是否存在
- 检查当前 Python 进程是否具备辅助功能权限
- 枚举并筛掉 `menu / popover / sheet / dialog` 这类非主窗口
- 从左侧 `session_list` 及 `session_item_*` 节点读取 `chat_name / preview / unread_count`

设计上把“读”和“激活”分开：
- **读路径** 依赖 macOS Accessibility 和窗口枚举能力，作为唯一真相源
- **激活/刷新** 只在必要时用于恢复可见窗口或刷新 AX 树，不作为主链路的每轮必做动作

这样做的原因是当前产品边界只需要稳定读取左侧会话预览，而不是模拟用户输入。持续抢焦点既会影响使用，也会把平台迁移误做成自动化操作重构。

**Alternatives considered**
- **继续沿用 `uiautomation` 并仅修改文档**：拒绝，因为这不会让 mac 分支可运行。
- **默认改成右侧聊天区抓取**：拒绝，因为这会改变 `preview_only` 产品边界。

### Decision: worker 事件契约保持稳定，只新增更细的状态值

`group_listener_worker.py` 继续保持“一行一个 JSON 事件”的主契约，并继续输出当前 runtime 已消费的 `status` / `session_snapshot` / `message` 事件类型。
本 change 只新增更细的状态语义，例如：
- `permission_required`
- `waiting_wechat`
- `connecting`
- `ui_paused`
- `window_lost`
- `reconnecting`
- `running`

这意味着：
- `/healthz`、`/api/runtime`、`/api/sessions` 不增加新的 endpoint
- `backend_runtime.py` 继续通过现有事件入口维护 runtime 和 session 快照
- 前端仍使用同一套本地 API，只是能看到更可解释的 worker 状态

**Alternatives considered**
- **改掉 worker 事件类型，另起一套 mac 专用协议**：拒绝，因为这会扩大前后端改动面。
- **把权限缺失和弹窗遮挡都压成通用错误日志**：拒绝，因为 runtime 需要机器可解释的恢复状态。

### Decision: 弹窗 / menu / sheet 视为“暂停读取”，窗口丢失视为“可重连”，都不应直接打崩 runtime

macOS WeChat 的 AX 树在上下文菜单、弹窗、sheet 或浮层出现时并不稳定。
因此 worker 必须在这类场景下进入暂停轮询的状态，而不是把一次读取失败当成永久错误：
- 检测到 popup/menu/sheet/dialog 时进入 `ui_paused`
- 主窗口消失时进入 `window_lost -> reconnecting`
- 场景消失后自动恢复到 `running`

这保持了与当前文档对 `waiting_wechat`、`window_lost`、backoff supervisor 的一致性，也让 `backend_runtime.py` 继续把“后端可服务”和“微信当前是否可读”区分开。

**Alternatives considered**
- **任意 AX 读取失败都直接退出 worker**：拒绝，因为会把短暂 UI 扰动放大成整链路不可用。
- **完全忽略 popup/menu/sheet**：拒绝，因为会把不稳定 AX 树误当作有效快照。

### Decision: `all_sessions + preview_only` 继续是唯一交付语义，`sender_hint` 只做可选增强

worker 与 runtime 的交付底线固定为：
- 扫描左侧当前可见会话列表
- 产出 `chat_name / preview / unread_count`
- 通过现有 `/api/sessions` 和消息事件流交给前端

如果首轮无法稳定拿到 richer 字段，例如 `sender_hint`，允许只交付最小字段集。
但禁止为了补齐字段改走右侧正文抓取或改变消息保真度分层。

**Alternatives considered**
- **把 `sender_hint` 设为必需字段**：拒绝，因为这会把实现与 AX 细节过度耦合。
- **用右侧正文补齐缺失字段**：拒绝，因为这已超出当前 change 边界。

## Risks / Trade-offs

- **[辅助功能权限缺失或系统未授权]** → 在窗口层显式暴露权限检查结果，worker 进入 `permission_required`，并在文档中提供最小手工恢复步骤。
- **[WeChat AX 标识在版本升级后漂移]** → 读取层优先走 `AXIdentifier`，同时保留基于标题/值/层级的受控 fallback，并用单元测试锁住解析行为。
- **[mac 读取实现需要新增系统依赖或更严格的环境前提]** → 把依赖变化落到 `pyproject.toml` / `requirements.txt`，并确保源码态验证命令仍然明确。
- **[popup/menu 检测过于激进导致短时漏读]** → 采用“暂停轮询并恢复”而非退出；优先接受短暂漏轮询，也不接受把整条链路打崩。
- **[本地无法自动化验证真实 WeChat + 权限场景]** → 保留单元测试覆盖纯逻辑部分，并在文档/CSV 中记录受限验收步骤与风险等级。

## Migration Plan

1. 先在 `wechat_auto/window.py` 与 `wechat_auto/controls.py` 落 mac-only 读取与权限诊断能力，确认能表达“进程 / 主窗口 / session_list / popup”这四类事实。
2. 将 `group_listener_worker.py` 切到 mac 适配层，保持现有 `status` / `session_snapshot` / `message` 事件契约，并补 `permission_required` / `ui_paused` 等状态。
3. 更新 `backend_runtime.py`、`backend_main.py`、`sidebar_runtime_support.py` 对新状态和值的监督与依赖接线，但不改对外 API 面。
4. 补 Python 单元测试、依赖声明和 listener 文档，再做源码态受限验收。

**Rollback strategy**
- 如果 mac 读取层在真实 WeChat 上不稳定，优先回退到“保留诊断入口但不切默认 worker”的状态，而不是把不稳定实现继续挂到正式 runtime。
- 如果新状态导致前端或 runtime 行为异常，保留 mac 读取层，先回退状态映射和 supervisor 接线，不恢复 Windows 主实现。

## Open Questions

- None. 当前 plan 已经明确 change 只覆盖 mac listener/runtime 迁移，不扩产品范围，也不要求另一套 API 或双平台兼容。
