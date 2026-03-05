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

### 9) 先启动监听、后启动微信
现象：
- 先启动监听脚本时微信尚未打开，worker 会报“未找到微信窗口”。

处理：
- `group_listener_worker.py` 支持 `--load-retry-seconds`，微信未就绪时按间隔持续重试。
- `sidebar_translate_listener.py` 从 `config/listener.json` 的 `listen.load_retry_seconds` 读取该值（默认 `10.0` 秒）。

### 10) 打包后 worker 路径失效
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
- 左侧消息（非自己消息）UI 头部展示格式为“`[时间] 发送人`”，正文只展示消息内容，不再重复 `发送人:` 前缀。
- 消息正文字号比时间/昵称行大 `2px`；时间与昵称保持基础字号不变。
- 侧边栏窗口初始高度为 `700px`；若屏幕高度不足，自动收缩到可显示范围内。
- UI 字体优先顺序：`Cascadia Code` -> `JetBrains Mono` -> `黑体`；都不可用时回退系统默认字体。
- 默认行为必须是低干扰：
  - 不抢焦点（除非 `listen.focus_refresh=true`）
  - 不置顶（除非用户手动开启“置顶”开关）
