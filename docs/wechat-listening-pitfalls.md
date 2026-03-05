# 微信监听踩坑参考（Windows / Weixin / UIAutomation）

## 适用范围
本说明覆盖以下实现：
- `examples/group_listener_worker.py`
- `examples/sidebar_translate_listener.py`
- `wechat_auto/window.py`
- `wechat_auto/controls.py`
- `wechat_auto/chat.py`

目标：在不改微信客户端的前提下，稳定监听指定会话消息并在侧边栏展示（可接 DeepLX 翻译）。

当前监听目标来源于配置文件：`config/listener.json` 的 `listen.targets`。

## 架构结论
- 监听与 UI 必须分离：`group_listener_worker.py` 负责抓消息，`sidebar_translate_listener.py` 负责展示与翻译。
- 默认推荐 `session` 模式，不推荐 `chat` 模式作为唯一监听来源。
- 默认关闭焦点抢占与侧边栏置顶，避免打断用户操作。
- 现支持多目标：每个 target 独立侧边栏窗口 + 独立 worker 子进程。

## 关键坑位与处理

### 1) 主窗口误匹配（弹层/托盘窗口）
现象：
- 进程存在，但拿到的是 `mmui::XDialog` / `XPopover` / 托盘相关窗口，后续监听失败。

根因：
- Weixin 顶层窗口不止一个，按标题/类名粗匹配会命中非主窗口。

处理：
- 在 `wechat_auto/window.py` 中对窗口打分并过滤：
  - 主窗口类优先：`MainWindow` / `WeChatMainWnd*`
  - 弹层/托盘类降权：`popover` / `trayicon` / `shadow` / `toolsavebits`
  - 非主窗口直接跳过

### 2) `chat` 模式不稳定
现象：
- 已进入目标会话，但消息列表初始为空或不可读，导致基线签名为 `None`，后续不触发新消息事件。

处理：
- 增加 `wait_initial_chat_signature()`，启动阶段等待首次可读签名。
- 即便如此，`chat` 模式仍受 UI 状态影响，建议仅作补充模式。

结论：
- 默认使用 `session` 模式，依赖会话列表预览增量触发。

### 3) 会话预览不刷新
现象：
- `session` 模式长期读到同一预览文本，不产出消息事件。

根因：
- 某些环境下 UIA 读取会话列表可能保持旧快照。

处理：
- 配置项 `listen.focus_refresh=true` 时，worker 轮询会执行 `SwitchToThisWindow`。
- 默认关闭该配置，避免频繁抢焦点；仅在出现“预览不刷新”时开启。

### 4) 抢焦点副作用
现象：
- 监听期间周期性切回微信，影响当前工作窗口。

处理：
- 默认不做轮询抢焦点。
- 仅 `listen.focus_refresh=true` 时才允许抢焦点。

### 5) 侧边栏置顶影响操作
处理：
- 侧边栏默认不置顶。
- 仅在需要时用侧边栏头部“置顶”开关临时切换。

### 6) Worker 日志与事件混流
现象：
- `wx_auto` 普通日志不是 JSON；若按“纯 JSON 流”解析会报错。

处理：
- `sidebar_translate_listener.py` 对 worker stdout 做两类处理：
  - JSON：按事件处理（`status` / `message` / `log`）
  - 非 JSON：作为 `worker raw` 记录

### 7) DeepLX 返回 403（error code: 1010）
现象：
- 翻译调用报 `HTTP Error 403: Forbidden`，响应体常见 `error code: 1010`。

根因：
- 某些 DeepLX 网关会对 Python 默认请求特征做风控，`urllib` 默认 UA 容易被拦截。

处理：
- 在 `examples/sidebar_translate_listener.py` 的 `DeepLXTranslator` 请求头中显式设置：
  - `User-Agent`（浏览器风格）
  - `Accept`
  - `Content-Type: application/json; charset=utf-8`
  - `Origin` / `Referer`
- 保留错误响应体片段，便于定位风控/配额问题。

### 8) 中文乱码（侧边栏显示 `�`）
现象：
- 侧边栏日志或消息中出现中文乱码（`�` 或错码文本）。

根因：
- worker 子进程 stdout 使用系统编码（常见 GBK），父进程按 UTF-8 解码，导致错码。

处理：
- worker 启动时强制 UTF-8：
  - 命令行增加 `-X utf8`
  - 环境变量增加 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`

### 9) 重复消息与“永久去重”误伤
现象：
- `mixed` 模式下同一条消息可能被 `chat` 和 `session_preview` 双显。
- 相同文案在后续再次出现时被错误丢弃（例如“收到”）。

根因：
- 使用进程生命周期的 `set` 去重会把“历史出现过的文本”永久视为重复。

处理：
- `group_listener_worker.py` 只做短防抖（默认 `0.8s`），用于抑制 UI 抖动和同轮询重复，不做永久去重。
- `group_listener_worker.py` 的 `session` 触发改为比较“预览正文”是否变化，不再比较整条 `session_raw`（避免时间/未读数抖动造成重复）。
- `sidebar_translate_listener.py` 改为：
  - 精确去重窗口：`session_preview` 默认 `20s`，其他来源默认 `2.5s`；
  - 跨来源归并窗口（默认 `3.0s`）：合并 `chat/session_preview` 近实时重叠事件；
  - TTL + 上限清理：避免去重缓存无限增长。
- 三个窗口均支持在 `config/listener.json` 的 `listen` 中配置：
  - `dedupe_window_seconds`（普通来源）
  - `session_preview_dedupe_window_seconds`（`session_preview` 来源）
  - `cross_source_merge_window_seconds`（跨来源归并）
- 结论：短时间内抑制重复，窗口外相同文案可再次展示。

调参影响（必须按模式看）：
- `session` 模式：优先关注 `session_preview_dedupe_window_seconds`。  
  - 过小：重复抖动更难压住。  
  - 过大：短时间同文案重复发送会被吞。
- `mixed` 模式：除上面外，还要看 `cross_source_merge_window_seconds`。  
  - 过小：`chat/session_preview` 双来源重复更容易双显。  
  - 过大：跨来源但非同条消息也可能被误并。
- `dedupe_window_seconds` 主要影响 `chat` 来源；纯 `session` 模式下影响很小。

### 10) 多目标监听的焦点冲突
现象：
- 多个目标同时监听时，如果使用 `chat/mixed` 或开启 `focus_refresh`，窗口会相互抢焦点，干扰明显。

根因：
- `chat/mixed` 会主动切会话；`focus_refresh=true` 会轮询 `SwitchToThisWindow`。

处理：
- 多目标模式强制约束：
  - `listen.mode=session`
  - `listen.focus_refresh=false`
- 采用“每个 target 一个侧边栏子进程”的隔离模型，避免共享状态互相污染。

### 11) 重复启动导致同 target 多窗口
现象：
- 误重复执行启动命令后，同一个 target 可能出现多个窗口，消息重复显示。

处理：
- 为每个 target 增加运行时锁（`logs/.runtime/target_*.lock`）。
- launcher 启动子进程前会检查锁并跳过已运行 target。
- 异常退出导致的陈旧锁会在下次启动时自动清理。

### 12) 翻译网络抖动卡 UI
现象：
- DeepLX 延迟或超时时，侧边栏滚动和交互明显卡顿。

根因：
- 若在 UI 线程直接做翻译请求，主线程会被网络 I/O 阻塞。

处理：
- 翻译改为后台单线程队列，UI 线程只负责去重与渲染。
- 翻译失败通过事件回流记录日志，不阻塞后续消息处理。

### 13) 长时间运行日志膨胀
现象：
- 多窗口持续运行时日志文件增长过快，排障时难以定位近期信息。

处理：
- 启用按大小轮转：单文件约 `10MB` 自动切分，保留最近 `5` 个历史文件。

### 14) 配置脏值导致运行中崩溃
现象：
- `listen.interval_seconds<=0` 或 `translate.timeout_seconds<=0` 时，worker/翻译线程会在运行期报错。
- `display.width` 过小会导致窗口布局异常。

处理：
- 侧边栏主进程启动时对关键配置做 fail-fast 校验，不合法直接退出并打印错误：
  - `listen.interval_seconds > 0`
  - `translate.timeout_seconds > 0`
  - `display.width >= 280`

### 15) PID 复用造成运行时锁误判
现象：
- 仅依赖 `pid` 判断锁活性时，极端情况下可能把“新进程复用旧 pid”误判为同一实例。

处理：
- 运行时锁同时记录 `pid` 与进程启动时间 token（Windows `GetProcessTimes`）。
- 清理陈旧锁前先校验 `pid+token` 一致性，减少误判概率。

### 16) 翻译队列无限增长
现象：
- 翻译服务慢于消息流入时，若队列无上限，内存会持续增长。

处理：
- 翻译队列改为有界（默认上限 `300`）。
- 队列满时丢弃最旧待翻译任务并输出 `translate queue overflow` 日志，优先保持系统可用。

### 17) 先启动监听、后启动微信
现象：
- 先启动监听脚本时微信尚未打开，worker 会报“未找到微信窗口”。

处理：
- `group_listener_worker.py` 支持 `--load-retry-seconds`，微信未就绪时按间隔持续重试。
- `sidebar_translate_listener.py` 从 `config/listener.json` 的 `listen.load_retry_seconds` 读取该值（默认 `10.0` 秒）。

### 18) 打包后 worker 路径失效
现象：
- 直接把脚本打包为 exe 后，主进程按 `.py` 路径拉起 worker 失败。

处理：
- `sidebar_translate_listener.py` 在打包模式使用 `--worker-mode` 启动内嵌 worker；
- 源码模式仍按 `examples/group_listener_worker.py` 运行，保持开发调试体验一致。

## 推荐运行命令

### 低干扰稳定方案（推荐）
```bash
python examples/sidebar_translate_listener.py ^
  --config "D:\code\wechat-pc-auto\config\listener.json"
```

### 接入 DeepLX
在 `config/listener.json` 设置 `translate.enabled=true` 且配置 `translate.deeplx_url`。

### 仅在必要时开启强刷新（会抢焦点）
在 `config/listener.json` 设置 `listen.focus_refresh=true`。

## 排障最小步骤
1. 先看侧边栏状态是否为 `running mode=...`。
2. 再看 `logging.file` 指向的日志文件是否有 `status: running`（相对路径按项目根目录解析）。
3. 若无消息事件，临时设 `listen.worker_debug=true`，观察 `debug session_preview=...` 是否变化。
4. `session_preview` 不变化时，再设 `listen.focus_refresh=true` 验证是否恢复。

## 契约约束（后续改动必须保持）
- `group_listener_worker.py` 输出事件必须保持 JSON 行格式（至少包含 `type` 字段）。
- `sidebar_translate_listener.py` 必须兼容非 JSON stdout 行，不得因解析失败退出。
- 多目标时必须“一目标一窗口一子进程”，禁止把多个目标塞进同一个 UI 事件队列。
- 当 `listen.targets` 长度大于 1：`listen.mode` 必须是 `session` 且 `listen.focus_refresh=false`。
- 同一 target 只允许一个活动侧边栏实例（由运行时锁保证）。
- 去重必须是“时间窗策略”，禁止恢复为全生命周期永久 `set` 去重。
- 启动阶段必须对 `listen.interval_seconds`、`translate.timeout_seconds`、`display.width` 做 fail-fast 校验。
- 运行时锁活性判断必须包含 `pid` 与进程启动时间 token，禁止仅靠 `pid` 判断。
- 翻译任务队列必须有上限并具备溢出日志，禁止无界增长。
- 左侧消息（非自己消息）UI 头部展示格式为“`[时间] 发送人`”，正文只展示消息内容，不再重复 `发送人:` 前缀。
- 消息正文字号比时间/昵称行大 `2px`；时间与昵称保持基础字号不变。
- 侧边栏窗口初始高度为 `550px`；若屏幕高度不足，自动收缩到可显示范围内。
- UI 字体优先顺序：`Cascadia Code` -> `JetBrains Mono` -> `黑体`；都不可用时回退系统默认字体。
- 默认行为必须是低干扰：
  - 不抢焦点（除非 `listen.focus_refresh=true`）
  - 不置顶（除非用户手动开启“置顶”开关）
