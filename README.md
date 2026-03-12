# wechat-pc-auto

当前只支持一条桌面主路径：

- Python 本地后端：`listener_app/backend_main.py`
- 桌面前端：`desktop-shell/`（React + Vite + Tauri）
- 本地契约：`HTTP + WebSocket`

别再把仓库理解成“双 UI 并存”。Tk 回退链路已经下线，现在只有 Tauri 桌面壳是正式桌面 UI。

## 这条分支做什么

- 只维护 `session-only`
- 只维护左侧会话预览 `preview-only`
- 只维护单 worker 扫描左侧可见会话
- 只维护 Python runtime + 本地 API + 桌面壳
- 不再提供发送消息、发送文件、自动回复、写输入框等主动操作能力

如果你要的是“低打扰抓左侧会话预览，顺手翻成英文练习”，这条路对。
如果你要的是“完整聊天正文审计 / 自动回复 / 主动发消息”，这个仓库不做。

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

接入 DeepLX / 云 TTS 时，真实密钥建议放 `.env.local`：

```bash
DEEPLX_URL=http://127.0.0.1:1188/translate
VOLCENGINE_TTS_APPID=<your-appid>
VOLCENGINE_TTS_ACCESS_TOKEN=<your-access-token>
TENCENTCLOUD_SECRET_ID=<your-secret-id>
TENCENTCLOUD_SECRET_KEY=<your-secret-key>
```

`.env.local` 的读取位置要分清：

- 源码态：仓库根目录 `.env.local`
- Tauri 壳：优先 `%LOCALAPPDATA%\com.wechatauto.shell\.env.local`
- Tauri 壳兜底：`wechat-auto-shell.exe` 同目录 `.env.local`

默认不会把 `.env.local` 打进安装包。原因很直接：这玩意通常带密钥，自动分发就是泄漏。

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

前端开发页默认地址：`http://127.0.0.1:1420`

如需覆盖后端地址：

```bash
VITE_BACKEND_HTTP_URL=http://127.0.0.1:8765
VITE_BACKEND_WS_URL=ws://127.0.0.1:8766/events
```

### 3. 可选：启动 Tauri 壳

如果本机已经装好 Rust toolchain（`cargo` / `rustc`）：

```bash
cd desktop-shell
npm run tauri dev
```

`npm run tauri dev` 会先构建 PyInstaller sidecar，再由 Tauri 壳托管 backend。
没有 Rust toolchain 时，只能先跑 `npm run dev` 验证前端页面和本地 API，不要装作壳已经可用。

## 测试与构建

当前主路径要分清五件事：

- 开发运行：`backend_main.py + npm run dev`
- sidecar 构建：`python scripts/build_desktop_shell_sidecars.py --python python`
- 前端回归：`cd desktop-shell && npm test`
- 前端构建 + Rust 回归：`cd desktop-shell && npm run build && cd src-tauri && cargo test`
- release smoke：`python scripts/smoke_desktop_shell_release.py`

最小源码态验证：

```bash
python listener_app/backend_main.py --config ".\config\listener.json"
cd desktop-shell
npm test
npm run build
cd src-tauri
cargo test
```

桌面壳真正的最小交付闸口是：

```bash
python scripts/build_desktop_shell_sidecars.py --python python
cd desktop-shell
npm test
npm run build
cd src-tauri
cargo test
cd ..\..
python scripts/smoke_desktop_shell_release.py
```

`cargo test` 在干净环境里会读取 `desktop-shell/src-tauri/tauri.conf.json` 的 `frontendDist=../dist`。
所以别再跳过 `npm run build`；你本地偶尔“直接 cargo test 也能过”，通常只是因为上一次构建残留了 `desktop-shell/dist`。

## 发布边界

- 正式交付目标是 `desktop-shell/` 这条桌面壳主路径。
- release 壳如果回归，允许回退到源码态主路径 `backend_main.py + npm run dev`，或者 `npm run tauri dev` 做开发期排障。
- 不要再发明“旧 UI fallback”；那条链已经下线，继续保留只会破坏边界一致性。
- 桌面壳现在是 `single-instance`：第二次启动只聚焦已有窗口，不允许再起第二个壳窗口或再补拉一份 backend sidecar。

详细命令、产物位置和验收边界看 `docs/desktop-shell-build.md`。

## 当前架构

- `listener_app/backend_main.py`
  源码态后端入口；负责启动 runtime 与本地 API。
- `listener_app/backend_runtime.py`
  运行时编排层；负责 worker 监督、翻译、TTS、会话状态与 `/healthz` 健康语义。
- `listener_app/runtime_api.py`
  本地 HTTP + WebSocket 契约层。
- `listener_app/runtime_config.py`
  当前主路径唯一配置 schema owner。
- `listener_app/runtime_engine.py`
  运行时状态机与事件分发。
- `listener_app/runtime_store.py`
  会话/消息存储与去重边界。
- `listener_app/group_listener_worker.py`
  单进程 UIA 监听 worker；主路径按 `all_sessions` 扫描左侧可见会话。
- `listener_app/sidebar_translate_runtime.py`
  翻译 provider、DeepLX runtime 与失败 fallback。
- `listener_app/sidebar_runtime_support.py`
  worker 启停支撑、日志轮转、运行时锁与 stdout/stderr reader。
- `listener_app/sidebar_tts.py`
  Windows System / 豆包 / 腾讯云 TTS runtime。
- `listener_app/sidebar_shared.py`
  共享常量、路径/配置工具、文本归一化与通用校验。
- `desktop-shell/`
  React + Vite + Tauri 桌面壳；通过本地 HTTP + WebSocket 消费运行时状态。
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

- `desktop-shell` 可以通过 `npm run tauri build` 产出一体化桌面壳 `exe / msi / nsis`
- 壳启动后会自动拉起 `wechat-auto-backend.exe` 和 `group_listener_worker.exe`
- 运行时配置、日志和锁落到 `%LOCALAPPDATA%\com.wechatauto.shell`
- sidecar 当前用的是 PyInstaller `onefile`；任务管理器里看到同名双进程通常是 bootloader + payload，不等于重复启动

真正还保留的边界只有两条：

- `.env.local` 不会自动塞进安装包，用户要自己提供
- release 壳必须通过 `scripts/smoke_desktop_shell_release.py`，不能只看 build 成功

## 配置与排障

- 配置字段说明：`config/listener.md`
- 主路径测试 / 构建 / 发布闸口：`docs/desktop-shell-build.md`
- 监听坑位、健康契约、打包排障：`docs/wechat-listening-pitfalls.md`

## 项目结构

```text
config/
├── doubao_tts.json
├── listener.json
├── listener.md
└── tencent_tts.json
desktop-shell/
├── src/
├── src-tauri/
└── package.json
docs/
├── desktop-shell-build.md
└── wechat-listening-pitfalls.md
listener_app/
├── backend_main.py
├── backend_runtime.py
├── group_listener_worker.py
├── runtime_api.py
├── runtime_config.py
├── runtime_engine.py
├── runtime_models.py
├── runtime_store.py
├── sidebar_runtime_support.py
├── sidebar_shared.py
├── sidebar_translate_runtime.py
└── sidebar_tts.py
wechat_auto/
├── __init__.py
├── controls.py
├── core.py
├── logger.py
└── window.py
```

## 开源协议

MIT License
