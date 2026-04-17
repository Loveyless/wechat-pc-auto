# Apple Silicon macOS 适配开发计划

分支：`spike/tauri-react-refactor-mac`

更新时间：`2026-04-16`

## 目标

- 把当前仓库的主路径从 `Windows / Weixin / UIAutomation` 迁到 `Apple Silicon macOS / 微信 macOS 客户端 / Accessibility API`。
- 保留本项目现有主能力：
  - 左侧会话列表预览监听
  - 本地 `HTTP + WebSocket` runtime API
  - 桌面壳消息展示与设置页
  - 翻译能力
  - TTS 朗读能力
- 当前分支不再兼容 Windows。
- 当前分支只面向 `M1 / M2 / M3 / M4` 及之后的 `arm64 macOS`，不覆盖 Intel Mac。

## 非目标

- 不新增参考仓库里的浮窗、词典、单词本、SQLite 历史库、AI 总结、Text2SQL、托盘闪动等额外功能。
- 不把当前项目升级成“完整聊天记录抓取器”；主语义仍是 `all_sessions + preview_only`。
- 不在本分支同时维护 Windows 和 macOS 双实现。
- 不为了兼容老路径而保留 `.exe`、`taskkill`、Win32 mutex、`uiautomation` 这类 Windows 基础设施。

## 当前仓库事实

### 当前主链路

- 当前正式路径是 `listener_app/backend_main.py + desktop-shell/`。
- 当前桌面壳只消费本地 `HTTP + WebSocket`，不直连 worker stdout。
- 当前监听主语义已经收敛为：
  - `session-only`
  - `all_sessions`
  - `preview-only`

### 当前最强 Windows 绑定点

- Python 监听层：
  - `wechat_auto/window.py`
  - `wechat_auto/controls.py`
  - `listener_app/group_listener_worker.py`
- Python TTS 与进程治理：
  - `listener_app/sidebar_tts.py`
  - `listener_app/sidebar_runtime_support.py`
  - `listener_app/sidebar_shared.py`
  - `listener_app/backend_main.py`
- Tauri backend：
  - `desktop-shell/src-tauri/src/backend/win32.rs`
  - `desktop-shell/src-tauri/src/backend/bootstrap.rs`
  - `desktop-shell/src-tauri/src/main.rs`
- 构建与交付：
  - `scripts/build_desktop_shell_sidecars.py`
  - `scripts/smoke_desktop_shell_release.py`
  - `docs/desktop-shell-build.md`
  - `docs/wechat-listening-pitfalls.md`
- 配置默认值当前仍是 Windows 取向：
  - `config/listener.json` 中默认 `tts.provider=windows_system`

### 当前可以尽量保留的部分

- runtime 编排和消息契约：
  - `listener_app/backend_runtime.py`
  - `listener_app/runtime_api.py`
  - `listener_app/runtime_engine.py`
  - `listener_app/runtime_models.py`
  - `listener_app/runtime_store.py`
  - `listener_app/runtime_config.py`
- 翻译链路的大部分 shared 逻辑：
  - `listener_app/sidebar_translate_runtime.py`
- 前端页面、设置页和本地 API 消费模式：
  - `desktop-shell/src/**`

## 参考仓库与借鉴边界

参考仓库：

- `https://github.com/congwa/wechat-translate`

这次只借鉴它的 mac 适配方法，不借它的产品范围。

### 可借鉴点

- 使用 `Accessibility API + AppleScript + CGWindow` 定位微信主窗口与读取 AX 树。
- 适配层独立收口，不把 macOS 特有细节散落到业务层。
- 会话预览的解析策略：
  - `chat_name`
  - `preview_body`
  - `unread_count`
  - `sender_hint`
- 有弹窗、菜单、sheet 时暂停轮询，避免读到不稳定 AX 树。
- 使用系统原生 TTS 路径，而不是继续走 Windows 播放链路。

### 明确不引入的点

- 浮窗跟随/独立置顶双模式
- 右侧详情补全驱动的高保真消息库
- SQLite 历史消息系统
- 词典、单词本、发音缓存
- AI 总结、Agent、Text2SQL
- 额外托盘产品能力

## 技术路线决策

### 总体方向

保留当前项目的总体分层，不切去“整仓 Rust 重写”：

- 继续保留 `Python backend + React/Tauri shell` 总结构。
- Python 侧只重写操作系统绑定层。
- Tauri 侧只重写 backend 托管与 sidecar 生命周期。
- 前端只做最小必要适配，不顺手改产品结构。

### 为什么不直接照搬参考仓库

- 参考仓库本质上是另一套产品，不是当前仓库的同构分支。
- 当前仓库已有完整的 runtime API、状态机和桌面壳界面，直接废掉重做会扩大改动面。
- 用户要求是“只适配本项目原有功能”，不是“做一个简化版 wechat-translate”。

## 分层改造方案

### 1. 微信窗口与会话读取层

目标：替换当前 `Win32 + uiautomation` 方案。

处理方式：

- 取消对 `uiautomation` 的依赖。
- 在 Python 侧引入 macOS 可用的能力组合：
  - `PyObjC`
  - `Accessibility API`
  - `Quartz / CGWindow`
  - 必要时辅以 `osascript`
- 重写以下模块：
  - `wechat_auto/window.py`
  - `wechat_auto/controls.py`
- `listener_app/group_listener_worker.py` 保留“每行一个 JSON 事件”的输出契约，但底层读取逻辑改为 mac AX 实现。

实现原则：

- 默认仍以左侧会话预览为真相源。
- 不默认引入右侧聊天区正文采集。
- 若 mac 微信 AX 结构导致“只读左栏不可行”，再把右侧详情作为降级备选，不先扩范围。

### 2. runtime 与消息契约层

目标：尽量不动前后端契约。

保留：

- `runtime_api.py` 的 HTTP / WebSocket 暴露方式
- `runtime_store.py` 的消息缓存与去重边界
- `runtime_engine.py` 的运行态状态编排
- `runtime_config.py` 的配置 schema owner 角色

需要调整：

- 等待微信、重连、窗口丢失、弹窗阻塞这些状态，要按 mac AX 真实行为重新校准。
- 现有 `focus_refresh` 语义基于 Windows 前台切换；迁到 mac 后要改成更安全的刷新策略，不能照搬。

### 3. TTS 层

目标：保留“自动朗读当前活跃会话新消息”的产品能力，但替换底层实现。

处理方式：

- 删除 `windows_system` 作为默认 provider。
- 新分支引入 `macos_system` 作为默认 provider。
- 本地系统 TTS 优先使用 macOS 原生能力：
  - 第一优先：系统命令 `say`
  - 若后续发现回调、打断、状态同步不够，再升级为 `NSSpeechSynthesizer`
- 云 TTS provider 继续保留：
  - `doubao`
  - `less_tts`
  - `tencent_cloud`
- 云 TTS 的“合成”逻辑可以沿用，但“播放”逻辑必须替换为 mac 兼容路径。

约束：

- 不保留 `winsound`
- 不保留 `winmm MCI`
- 不保留 `System.Speech`

### 4. Tauri backend 与 sidecar 托管

目标：让桌面壳在 mac 上稳定拉起 Python backend，并在退出时清干净。

处理方式：

- 删除 `desktop-shell/src-tauri/src/backend/win32.rs`。
- 把 `bootstrap.rs` 改成 mac-only 版本：
  - 不再使用 Windows named mutex
  - 不再使用 `taskkill`
  - 不再以 `.exe` 命名 sidecar
- 进程治理改为：
  - 受控 child process
  - mac 下按 `pid / process group` 清理
  - 退出链路同时覆盖 `ExitRequested` 与 `Exit`

运行时目录目标：

- 不再使用 `%LOCALAPPDATA%`
- 统一改为 Tauri 在 macOS 的 `app_local_data_dir`
- 计划中的逻辑落点应等价于：
  - `~/Library/Application Support/com.wechatauto.shell`

### 5. 构建与打包

目标：先完成 `arm64 macOS` 的开发与本地构建闭环，再考虑正式分发质量。

阶段目标：

- 第一阶段只要求：
  - 源码态可跑
  - `npm run tauri dev` 可跑
- 第二阶段再做：
  - PyInstaller sidecar 的 mac 构建
  - `npm run tauri build` 本地构建
  - smoke 脚本改造

明确边界：

- 当前计划不覆盖 Intel mac。
- 当前计划不把 notarization / 公证 / 开发者证书作为首阶段阻塞项。

## 模块级改造清单

| 模块 | 处理策略 | 说明 |
| --- | --- | --- |
| `wechat_auto/window.py` | 重写 | 改成 mac 微信窗口定位与激活实现 |
| `wechat_auto/controls.py` | 重写 | 改成 AX 节点搜索、会话列表与文本提取 |
| `listener_app/group_listener_worker.py` | 重构 | 保留 JSON 事件契约，改底层读取链路 |
| `listener_app/sidebar_tts.py` | 重构 | 引入 `macos_system`，替换 Windows 播放实现 |
| `listener_app/sidebar_runtime_support.py` | 局部改造 | 进程清理、锁活性与子进程治理改为 mac-only |
| `listener_app/sidebar_shared.py` | 局部改造 | 运行时目录、worker 可执行名、路径解析改为 mac-only |
| `listener_app/backend_main.py` | 局部改造 | owner watchdog 与 TTS 预检适配 mac-only |
| `desktop-shell/src-tauri/src/backend/win32.rs` | 删除 | 当前分支不再需要 Windows backend helper |
| `desktop-shell/src-tauri/src/backend/bootstrap.rs` | 重写 | 改成 mac sidecar 托管与退出清理 |
| `desktop-shell/src-tauri/src/main.rs` | 局部改造 | 保留 single-instance 和 cleanup，但切换到 mac-only backend |
| `scripts/build_desktop_shell_sidecars.py` | 重写 | 输出 `aarch64-apple-darwin` 产物，不再生成 `.exe` |
| `scripts/smoke_desktop_shell_release.py` | 重写 | 改成 mac smoke 路径 |
| `config/listener.json` | 更新 | 默认 TTS provider 改为 `macos_system` |
| `config/listener.md` | 更新 | 同步新 provider、运行时目录和构建方式 |
| `docs/wechat-listening-pitfalls.md` | 更新 | 同步 mac 监听坑位与权限说明 |
| `docs/desktop-shell-build.md` | 更新 | 同步 mac build / sidecar / smoke |

## 阶段计划

### 阶段 0：分支与计划落地

目标：

- 新建 `-mac` 分支
- 锁定范围和非目标
- 输出本计划书

完成判据：

- 分支已切换
- 计划书已入库

### 阶段 1：mac 监听适配 Spike

目标：

- 在本机 `Apple Silicon macOS` 上确认最小可行读取链路：
  - 检测微信进程
  - 定位主窗口
  - 读取左侧会话列表
  - 提取 `chat_name / preview / unread`

交付：

- mac 版本 `wechat_auto/window.py`
- mac 版本 `wechat_auto/controls.py`
- 最小调试脚本或最小调试入口

验收：

- 微信已启动并授权辅助功能时，可以稳定读到当前可见会话列表
- 微信未启动或未授权时，错误信息明确

### 阶段 2：worker 与 runtime 接通

目标：

- 让 `group_listener_worker.py` 在 mac 上产出与当前前端兼容的事件流
- 保持 `preview-only` 主语义不变

交付：

- worker 重连、去重、状态事件迁到 mac
- popup / menu / dialog 出现时暂停轮询

验收：

- `backend_main.py` 源码态启动后，前端可以收到会话预览变化
- 微信关闭再打开后可恢复
- 不会因为弹窗导致整条链路崩掉

### 阶段 3：TTS 与配置迁移

目标：

- 把默认 TTS provider 换成 mac 系统朗读
- 保持设置页和 `/api/config` 契约可用

交付：

- `macos_system` provider
- 云 TTS 的 mac 播放链路
- 配置文档同步

验收：

- fresh config 不依赖云密钥也能启动
- 自动朗读当前活跃会话新消息可用
- 关闭自动朗读后不应继续播报

### 阶段 4：Tauri sidecar 与本地构建闭环

目标：

- 让 `npm run tauri dev` 和 `npm run tauri build` 能在 `arm64 macOS` 跑通

交付：

- mac sidecar 构建脚本
- mac bootstrap / cleanup
- mac smoke 脚本

验收：

- `npm run tauri dev` 自动托管 backend
- 关闭壳后 backend / worker 不残留
- 二次启动只聚焦已有窗口，不重复拉起 backend

### 阶段 5：文档收口与回归

目标：

- 把当前分支的运行说明、构建说明、坑位文档全部切换到 mac-only 事实源

交付：

- 更新：
  - `README.md`
  - `config/listener.md`
  - `docs/desktop-shell-build.md`
  - `docs/wechat-listening-pitfalls.md`
  - `docs/developer-guide.md`

验收：

- 文档不再混写 Windows 和 mac 路径
- 新同学按文档可完成本地开发启动

## 配置与默认值调整计划

需要改的默认值：

- `tts.provider`：`windows_system` -> `macos_system`
- 运行时根目录描述：`%LOCALAPPDATA%...` -> `~/Library/Application Support/...`
- worker 可执行名：去掉 `.exe`

暂不改的产品语义：

- `translate.enabled=false` 仍保留为 fresh install 首启安全值
- `all_sessions + preview_only` 仍保留为当前主路径
- 不恢复 `chat / mixed`

## 风险与难点

### 1. 微信 macOS AX 树不稳定

- 不同微信版本的 `AXIdentifier` 和节点层级可能变化。
- 这会直接影响 `session_list`、聊天标题和会话预览抓取。

策略：

- 先做本机版本验证
- 读取逻辑尽量采用“主路径 + 回退路径”双层设计

### 2. 辅助功能权限不是代码问题，但会表现成代码不可用

- 首次授权后通常需要重启被测应用或当前程序。
- 如果权限状态判断不清晰，用户会误判成“监听坏了”。

策略：

- 明确做权限检测与错误提示
- 文档写清首次授权流程

### 3. mac 打包后 sidecar 与权限模型可能影响稳定性

- 源码态可跑，不代表打包后也能直接拿到同样权限。
- Accessibility、codesign、bundle 路径都可能影响结果。

策略：

- 第一阶段先把源码态跑通
- 第二阶段再做 build / smoke

### 4. TTS 的“能播”与“能稳定中断/切换”不是一回事

- `say` 命令易落地，但控制粒度有限。
- 若自动朗读需要更细的中断与状态同步，后续可能要升级到底层 API。

策略：

- 先用 `say` 完成主能力
- 只在功能缺口被验证后再升级复杂度

## 验证矩阵

### 开发阶段最小验证

1. 源码态 backend：
   - `python listener_app/backend_main.py --config ./config/listener.json`
2. 前端开发页：
   - `cd desktop-shell && npm run dev`
3. Tauri 开发壳：
   - `cd desktop-shell && npm run tauri dev`

### 关键观察点

- 微信未启动时：
  - 后端保持存活
  - 状态显示 `waiting_wechat` 或等价状态
- 微信启动后：
  - 无需重启程序即可恢复
- 新预览到来时：
  - 前端收到消息事件
  - 翻译链路可用
  - TTS 在开启状态下可播报
- 关闭桌面壳时：
  - backend / worker 不残留
- 二次启动桌面壳时：
  - 不重复拉起第二套 runtime

## 执行顺序建议

1. 先做 mac 监听 Spike，不先碰 Tauri build。
2. Spike 通过后再接 worker 与 runtime。
3. runtime 通了以后再迁 TTS。
4. 源码态闭环稳定后，再做 Tauri sidecar 和 build。
5. 所有事实稳定后，最后再统一改文档。

## 本计划的完成定义

满足以下条件才算这一轮 mac 改造完成：

- 当前分支在 `Apple Silicon macOS` 上可源码态运行
- `npm run tauri dev` 可运行且自动托管 backend
- 主能力 `监听预览 + 翻译 + 展示 + TTS` 全部可用
- 不再依赖任何 Windows 特有能力
- 仓库文档已经切换到 mac-only 事实源
