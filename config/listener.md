# listener.json 配置说明

打包为 EXE 后，默认配置路径为：`<exe目录>\config\listener.json`。
## 启动参数约束
- `examples/sidebar_translate_listener.py` 启动时仅保留 `--config`。
- 其余运行行为（监听、翻译、展示、日志、调试）统一从 `listener.json` 读取，不再提供命令行覆盖参数。

## 完整配置示例
```json
{
  "listen": {
    "mode": "session",
    "targets": [
      "ssh 前端进阶交流群3群「禁广告」"
    ],
    "load_retry_seconds": 10.0,
    "interval_seconds": 1.0,
    "dedupe_window_seconds": 2.5,
    "session_preview_dedupe_window_seconds": 20.0,
    "cross_source_merge_window_seconds": 3.0,
    "focus_refresh": false,
    "worker_debug": false
  },
  "translate": {
    "enabled": true,
    "provider": "deeplx",
    "source_lang": "auto",
    "target_lang": "EN",
    "timeout_seconds": 8.0
  },
  "display": {
    "english_only": true,
    "on_translate_fail": "show_cn_with_reason",
    "width": 420,
    "side": "right"
  },
  "logging": {
    "file": "logs/sidebar_listener.log"
  }
}
```

## 字段说明

### `listen`
- `mode`：监听模式。  
  - `session`：只监听会话列表预览，不主动打开会话。  
  - `chat` / `mixed`：会尝试切到目标会话（会影响当前微信焦点）。
- `targets`：监听目标数组。  
  - 长度为 `1`：启动一个侧边栏窗口。  
- 长度 `>1`：自动启动多个侧边栏窗口（每个目标一个窗口/一个子进程）。
- 若某个 target 已有侧边栏实例在运行，再次启动时会自动跳过该 target，避免重复窗口/重复监听。
- `load_retry_seconds`：微信未启动/未就绪时的重试间隔（秒），默认 `10.0`。
- `interval_seconds`：轮询间隔（秒）。越小越实时，但占用更高。
  - 必须 `> 0`，否则启动阶段会直接报错退出。
- `dedupe_window_seconds`：普通来源（如 `chat`）去重窗口秒数，默认 `2.5`。  
  - 值过小：重复消息更容易漏拦。  
  - 值过大：短时间内相同正文的真实消息可能被合并掉。
- `session_preview_dedupe_window_seconds`：`session_preview` 去重窗口秒数，默认 `20.0`。  
  - 这是 `session` 模式最关键参数。  
  - 值过小：会话预览抖动导致重复展示概率上升。  
  - 值过大：群里短时间重复发送相同内容时，第二条可能被抑制。
- `cross_source_merge_window_seconds`：跨来源归并窗口秒数，默认 `3.0`。  
  - 主要影响 `mixed` 模式，用于合并 `chat` 与 `session_preview` 的近实时重复事件。  
  - `session` 模式下该参数基本无影响。
- `focus_refresh`：是否每轮强制切回微信刷新 UIA。`true` 更稳但会抢焦点。
- `worker_debug`：是否输出 worker 调试日志（例如 `debug session_preview=...`）。

### `translate`
- `enabled`：是否启用翻译。`true` 调用翻译服务，`false` 原文透传。
- `provider`：翻译提供方。当前支持 `deeplx` / `passthrough`。
- `deeplx_url`：DeepLX 接口地址。
- `source_lang`：源语言，`auto` 表示自动检测。
- `target_lang`：目标语言，例如 `EN`。
- `timeout_seconds`：翻译请求超时时间（秒）。
  - 必须 `> 0`，否则启动阶段会直接报错退出。
- `deeplx_url` 为配置优先；未配置或空字符串时回退 `.env.local` 的 `DEEPLX_URL`。

### `display`
- `english_only`：`true` 时只显示翻译后的文本（替换原文展示）。
- `on_translate_fail`：翻译失败回退策略。  
  - `show_cn_with_reason`：显示中文并附失败原因。  
  - `show_cn`：只显示中文。  
  - `show_reason`：只显示失败原因。
- `width`：侧边栏宽度。
  - 必须 `>= 280`，否则启动阶段会直接报错退出。
- `side`：侧边栏停靠位置，`left` 或 `right`。
- 置顶仅通过侧边栏头部“置顶”按钮手动切换，不再提供启动配置项。

### `logging`
- `file`：运行日志输出文件路径。相对路径按项目根目录解析（例如 `logs/sidebar_listener.log`）。
- 日志按大小自动轮转：默认单文件约 `10MB` 时切分，保留最近 `5` 个历史文件（`.1` ~ `.5`）。

## 当前消息渲染规则（代码行为）
- 图片占位文本会被过滤，不显示到侧边栏：`[图片]` / `[image]` / `[images]` / `[photo]`。
- 若消息是 `发送人: 正文` 格式，仅翻译“正文”，发送人姓名保持原样。
- 若消息不含发送人前缀，视为“自己消息”，在侧边栏右对齐显示。
- UI 不显示 `source=session_preview`，该字段仅用于内部去重与日志。
- 当前侧边栏仅用于监听与展示，不提供消息发送输入框。
- 多目标模式下，窗口会做级联摆放避免完全重叠；日志文件会自动追加后缀（如 `.t1`、`.t2`）避免多进程抢写同一日志文件。
- 翻译在后台线程执行，避免网络抖动时卡住侧边栏 UI。
- 翻译队列是有界队列（默认上限 `300`）；队列满时会丢弃最旧待翻译任务并记录 `translate queue overflow` 日志。

## 多目标运行约束
- `listen.targets` 长度大于 1 时，必须使用 `listen.mode=session`。
- `listen.targets` 长度大于 1 时，必须保持 `listen.focus_refresh=false`（避免多窗口互相抢焦点）。
