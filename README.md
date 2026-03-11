# wechat-pc-auto

这个分支现在的主路径已经不是 Tk 侧边栏，而是：

- Python 本地后端：`listener_app/backend_main.py`
- 桌面前端：`desktop-shell/`（React + Vite + Tauri 壳）
- 本地契约：`HTTP + WebSocket`

旧 Tk 入口 `listener_app/sidebar_translate_listener.py` 还在，但只作为开发回退，不再是主路径。

如果你要的是“低打扰抓左侧会话预览，顺手翻成英文练习”，这条路对。
如果你要的是“完整聊天正文审计、自动回复、自动发文件”，这个分支不做。

## 当前主路径

- 只维护 `session-only`
- 只维护左侧会话列表 `preview-only`
- 只维护单 worker 扫描左侧可见会话
- 只维护 Python 运行时 + 本地 API + 桌面壳
- 不再提供发送消息、发送文件、自动回复、写输入框等主动操作能力

## 安装

先装 Python 依赖：

```bash
pip install -r requirements.txt
```

再装前端依赖：

```bash
cd desktop-shell
npm install
```

接入 DeepLX / 云 TTS 时，推荐把真实密钥放进 `.env.local`：

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

`.env.local` 的读取位置要分清：

- 源码态：仓库根目录 `.env.local`
- Tauri 壳：优先 `%LOCALAPPDATA%\com.wechatauto.shell\.env.local`
- Tauri 壳回退：`wechat-auto-shell.exe` 同目录 `.env.local`

默认不自动把 `.env.local` 打进 installer。原因不是矫情，是避免把你本机密钥顺手分发出去。

## 启动

### 1. 启动 Python 本地后端

```bash
python listener_app/backend_main.py --config ".\config\listener.json"
```

默认端口：

- HTTP：`http://127.0.0.1:8765`
- WebSocket：`ws://127.0.0.1:8766/events`

### 2. 启动桌面前端开发页

```bash
cd desktop-shell
npm run dev
```

默认会打开 Vite 开发页：`http://127.0.0.1:1420`

前端默认直连本地后端；如果你改了端口，可以覆盖：

```bash
VITE_BACKEND_HTTP_URL=http://127.0.0.1:8765
VITE_BACKEND_WS_URL=ws://127.0.0.1:8766/events
```

### 3. 可选：启动 Tauri 壳

如果本机已经装好 Rust toolchain（`cargo` / `rustc`），可以在 `desktop-shell/` 下执行：

```bash
npm run tauri dev
```

`npm run tauri dev` 现在会先自动构建 PyInstaller sidecar，再由 Tauri 壳托管 backend。
没有 Rust toolchain 时，只能先跑 `npm run dev` 验证前端页面和本地 API，不要装作 Tauri 壳已经可用。

### 4. 旧 Tk 开发回退入口

```bash
python listener_app/sidebar_translate_listener.py --config ".\config\listener.json"
```

这条路只用于开发期回退和对照，不再是主路径。

## 测试与构建

当前主路径至少要区分四件事，别再混着说：

- 开发运行：`backend_main.py + npm run dev`
- sidecar 构建：`python scripts/build_desktop_shell_sidecars.py`
- 桌面壳调试：`npm run tauri dev`
- 桌面壳构建：`npm run tauri build`

最小验证命令：

```bash
python listener_app/backend_main.py --config ".\config\listener.json"
cd desktop-shell
npm run build
```

需要桌面壳时，再执行：

```bash
cd desktop-shell
npm run tauri dev
npm run tauri build
```

详细命令、产物位置和验收边界，看 `docs/desktop-shell-build.md`。

## 当前架构

- `listener_app/backend_main.py`
  新主入口；负责启动 Python 本地后端和本地 API 服务。
- `listener_app/backend_runtime.py`
  Tk 无关的运行时编排层；负责 worker 监督、翻译、TTS、会话状态。
- `listener_app/runtime_api.py`
  本地 HTTP + WebSocket 契约层。
- `listener_app/runtime_engine.py`
  运行时状态机与事件分发。
- `listener_app/runtime_store.py`
  会话/消息存储与去重边界。
- `listener_app/group_listener_worker.py`
  单进程 UIA 监听 worker；主路径按 `all_sessions` 扫描左侧可见会话。
- `desktop-shell/`
  React + Vite + shadcn 风格桌面壳；通过本地 HTTP + WebSocket 消费运行时状态。
- `listener_app/sidebar_translate_listener.py`
  旧 Tk 开发回退入口，不再是主 UI 路径。
- `wechat_auto/window.py`
  微信主窗口定位与过滤。
- `wechat_auto/controls.py`
  UIA 控件树定位与会话列表文本解析。

## 你必须接受的限制

- 当前抓的是左侧会话预览，不是右侧聊天区全文。
- 长消息会被微信预览截断，程序拿不回后半段。
- 连续刷屏时只能抓到轮询时刻露出来的那些预览变化，不可能零漏。
- 当前主路径监听的是左侧可见会话；看不见的会话，本轮就抓不到。
- 这套东西适合“低打扰监听 + 翻译学习”，不适合“完整审计 / 完整归档”。

## 打包现状

现在别再说“新主路径不能打包成一体化桌面壳”，这话已经过期了。

- `desktop-shell` 现在可以通过 `npm run tauri build` 产出一体化桌面壳 `exe/msi/nsis`
- 壳启动后会自动拉起 `wechat-auto-backend.exe` 和 `group_listener_worker.exe`
- 运行时配置、日志和锁落到 `%LOCALAPPDATA%\com.wechatauto.shell`
- 旧 Tk 路径的 Windows 打包文档还在，见 `docs/windows-packaging.md`

真正还保留的边界只有两条：

- `.env.local` 不会自动塞进安装包，用户要自己提供
- 当前 sidecar 用的是 PyInstaller `onefile`，任务管理器里看到同名双进程通常是 bootloader + payload，不等于重复启动

## 配置与排障

- 配置字段说明看 `config/listener.md`
- 监听坑位和恢复机制看 `docs/wechat-listening-pitfalls.md`
- 当前主路径测试/构建看 `docs/desktop-shell-build.md`
- 旧 Tk 打包说明看 `docs/windows-packaging.md`

## 项目结构

```text
config/
├── doubao_tts.json
├── tencent_tts.json
├── listener.json
└── listener.md
desktop-shell/
├── src/
├── src-tauri/
└── package.json
docs/
├── desktop-shell-build.md
├── wechat-listening-pitfalls.md
└── windows-packaging.md
listener_app/
├── backend_main.py
├── backend_runtime.py
├── group_listener_worker.py
├── runtime_api.py
├── runtime_engine.py
├── runtime_models.py
├── runtime_store.py
├── sidebar_runtime_support.py
├── sidebar_shared.py
├── sidebar_translate_listener.py
├── sidebar_translate_runtime.py
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
