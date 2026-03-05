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
    "focus_refresh": false,
    "worker_debug": false
  },
  "translate": {
    "enabled": true,
    "provider": "deeplx",
    "deeplx_url": "",
    "source_lang": "auto",
    "target_lang": "EN",
    "timeout_seconds": 8.0
  },
  "display": {
    "english_only": true,
    "on_translate_fail": "show_cn_with_reason",
    "width": 460,
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
- `targets`：监听目标数组。当前版本使用第一个元素作为目标会话名。
- `load_retry_seconds`：微信未启动/未就绪时的重试间隔（秒），默认 `10.0`。
- `interval_seconds`：轮询间隔（秒）。越小越实时，但占用更高。
- `focus_refresh`：是否每轮强制切回微信刷新 UIA。`true` 更稳但会抢焦点。
- `worker_debug`：是否输出 worker 调试日志（例如 `debug session_preview=...`）。

### `translate`
- `enabled`：是否启用翻译。`true` 调用翻译服务，`false` 原文透传。
- `provider`：翻译提供方。当前支持 `deeplx` / `passthrough`。
- `deeplx_url`：DeepLX 接口地址。
- `source_lang`：源语言，`auto` 表示自动检测。
- `target_lang`：目标语言，例如 `EN`。
- `timeout_seconds`：翻译请求超时时间（秒）。
- `deeplx_url` 为**配置优先**；若要使用 `.env.local` 的 `DEEPLX_URL`，这里必须留空字符串。

### `display`
- `english_only`：`true` 时只显示翻译后的文本（替换原文展示）。
- `on_translate_fail`：翻译失败回退策略。  
  - `show_cn_with_reason`：显示中文并附失败原因。  
  - `show_cn`：只显示中文。  
  - `show_reason`：只显示失败原因。
- `width`：侧边栏宽度。
- `side`：侧边栏停靠位置，`left` 或 `right`。
- 置顶仅通过侧边栏头部“置顶”按钮手动切换，不再提供启动配置项。

### `logging`
- `file`：运行日志输出文件路径。相对路径按项目根目录解析（例如 `logs/sidebar_listener.log`）。

## 当前消息渲染规则（代码行为）
- 图片占位文本会被过滤，不显示到侧边栏：`[图片]` / `[image]` / `[images]` / `[photo]`。
- 若消息是 `发送人: 正文` 格式，仅翻译“正文”，发送人姓名保持原样。
- 若消息不含发送人前缀，视为“自己消息”，在侧边栏右对齐显示。
- UI 不显示 `source=session_preview`，该字段仅用于内部去重与日志。
