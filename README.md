# wechat-pc-auto

这个分支已经收窄成纯监听链路，不再假装支持一堆主动操作。

- 只维护 `session-only` 监听
- 只维护单 worker 扫描左侧会话预览
- 只维护侧边栏展示 + DeepLX 翻译
- 不再提供发送消息、发送文件、自动回复、写输入框等主动操作能力

如果你要的是“低打扰抓群消息预览，顺手翻成英文练习”，这条路对。  
如果你要的是“完整消息流、自动回复、自动发文件”，这个分支不做。

## 安装

```bash
pip install -r requirements.txt
```

## 启动

监听目标、翻译策略、侧边栏参数都从 `config/listener.json` 读取；当前默认 TTS provider 是腾讯云，provider 的私有参数拆到独立 JSON（例如 `config/tencent_tts.json` / `config/doubao_tts.json`）：

```bash
python listener_app/sidebar_translate_listener.py --config ".\config\listener.json"
```

接入 DeepLX / 云 TTS 时，推荐把真实密钥放进项目根目录的 `.env.local`：

```bash
DEEPLX_URL=http://127.0.0.1:1188/translate
VOLCENGINE_TTS_APPID=<your-appid>
VOLCENGINE_TTS_ACCESS_TOKEN=<your-access-token>
TENCENTCLOUD_SECRET_ID=<your-secret-id>
TENCENTCLOUD_SECRET_KEY=<your-secret-key>
```

如果你不想依赖云 TTS，把 `config/listener.json` 里的 `tts.provider` 改回 `windows_system` 即可。
当前默认已经是腾讯云；如果你之前改过 provider，确保 `tts.provider=tencent_cloud`，并把 `tts.config_path` 指到 `config/tencent_tts.json`。
当前默认腾讯云配置示例里的英文音色是 `WeJames`，代号 `VoiceType=501008`；这不是 `SampleRate`。

或者临时在 PowerShell 中设置：

```powershell
$env:DEEPLX_URL="http://127.0.0.1:1188/translate"
python listener_app/sidebar_translate_listener.py --config ".\config\listener.json"
```

## 打包成 Windows 应用

这条分支支持直接打包成 Windows 应用，主程序和 worker 会一起构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1
```

如果你确认这是本机自用包，想把仓库根目录 `.env.local` 一起复制到产物目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1 -CopyDotEnvLocal
```

默认不复制。别把这个开关当默认配置，否则你就是在主动把本机环境变量跟着产物一起打出去。

默认产物目录：

```text
artifacts\windows-app\wechat_sidebar\
```

更完整的打包说明见：

- `docs/windows-packaging.md`

## 当前架构

- `listener_app/sidebar_translate_listener.py`
  负责主入口编排：配置读取、配置校验、翻译线程、去重和事件分发。
- `listener_app/sidebar_translate_runtime.py`
  负责 translate provider、DeepLX runtime 与失败 fallback。
- `listener_app/sidebar_runtime_support.py`
  负责日志轮转、worker 生命周期支撑、运行时锁与 stdout/stderr reader。
- `listener_app/sidebar_ui.py`
  负责 Tk 侧边栏 UI、消息缓存、快捷键、原文显示与 TTS 交互入口。
- `listener_app/sidebar_tts.py`
  负责 Windows System / 豆包 / 腾讯云 TTS runtime、依赖探测与播放器工厂。
- `listener_app/sidebar_shared.py`
  负责共享常量、路径/配置工具、文本归一化与通用校验。
- `listener_app/group_listener_worker.py`
  负责单进程多目标监听；一次 UIA 扫描覆盖全部 `listen.targets`。
- `wechat_auto/window.py`
  负责定位并激活微信主窗口。
- `wechat_auto/controls.py`
  负责 UIA 控件树定位与会话列表文本解析。

## 你必须接受的限制

- 当前抓的是左侧会话预览，不是右侧聊天区全文。
- 长消息会被微信预览截断，程序拿不回后半段。
- 连续刷屏时只能抓到轮询时刻露出来的那些预览变化，不可能零漏。
- 这套东西适合“低打扰监听 + 翻译学习”，不适合“完整审计 / 完整归档”。

## 配置与排障

- 配置字段说明看 `config/listener.md`
- 监听坑位和恢复机制看 `docs/wechat-listening-pitfalls.md`

## 项目结构

```text
config/
├── doubao_tts.json
├── tencent_tts.json
├── listener.json
└── listener.md
docs/
└── wechat-listening-pitfalls.md
listener_app/
├── group_listener_worker.py
├── sidebar_runtime_support.py
├── sidebar_shared.py
├── sidebar_translate_runtime.py
├── sidebar_translate_listener.py
├── sidebar_tts.py
└── sidebar_ui.py
wechat_auto/
├── __init__.py
├── core.py
├── controls.py
├── logger.py
└── window.py
```

## 开源协议

MIT License
