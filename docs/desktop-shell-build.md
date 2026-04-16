# 当前主路径测试与构建

适用范围：

- `listener_app/backend_main.py`
- `listener_app/group_listener_worker.py`
- `desktop-shell/`

这份文档只讲当前分支的主路径：`Python backend + React/Tauri 桌面壳`。  
当前分支目标是 `Apple Silicon macOS`，不再把 Windows `.exe`、`msi`、`nsis` 或 `%LOCALAPPDATA%` 当成当前事实。

## 结论

- `npm run tauri dev` / `npm run tauri build` 会先构建 PyInstaller sidecar，再由 Tauri 自动托管 backend。
- 桌面壳继续按 `single-instance` 运行：第二次启动只聚焦已有窗口，不得再拉第二个壳窗口。
- 当前 sidecar 安装名已经切到 target-triple 规则；在 Apple Silicon macOS 上，构建后会落：
  - `desktop-shell/src-tauri/binaries/wechat-auto-backend-aarch64-apple-darwin`
  - `desktop-shell/src-tauri/binaries/group_listener_worker-aarch64-apple-darwin`
- 桌面壳运行时根目录固定在：
  - `~/Library/Application Support/com.wechatauto.shell`
- 仓库跟踪的默认 bundle 配置现在以“fresh runtime root 首启可进入设置页”为目标：
  - `translate.enabled=false`
  - `tts.provider=macos_system`

别把“密钥仍然外置”误读成“不是一体化”。  
真正的边界只有一个：`.env.local` 不会被自动打进产物。

## 前提

- 已安装 Python 依赖：`python3 -m pip install -r requirements.txt`
- 已安装 PyInstaller：`python3 -m pip install --user pyinstaller`
- 已安装前端依赖：`cd desktop-shell && npm install`
- 已安装 Rust toolchain：`cargo` / `rustc`

如果终端里找不到 `cargo`、`rustc` 或 `python3 -m PyInstaller`，先修环境，不要把环境问题甩给仓库。

## 命令

### 源码态后端 + 前端开发页

```bash
python3 listener_app/backend_main.py --config "./config/listener.json"
cd desktop-shell
npm run dev
```

源码态默认端口：

- HTTP：`http://127.0.0.1:8765`
- WebSocket：`ws://127.0.0.1:8766/events`

### Tauri 壳调试

```bash
cd desktop-shell
npm run tauri dev
```

这条命令现在会先自动执行：

```bash
python3 ../scripts/build_desktop_shell_sidecars.py --python python3
```

然后由 Tauri 壳托管 sidecar，不再要求你手工先跑 `backend_main.py`。

### Tauri 壳构建

```bash
cd desktop-shell
npm run tauri build
```

这条命令同样会先自动构建 sidecar，再产出 release shell。  
当前 smoke 默认先探测 `desktop-shell/src-tauri/target/release/wechat-auto-shell`，若存在 bundle app，则也会探测 `desktop-shell/src-tauri/target/release/bundle/macos/WeChat Auto Shell.app/Contents/MacOS/WeChat Auto Shell`。

### sidecar 构建

```bash
python3 scripts/build_desktop_shell_sidecars.py --python python3
```

这条命令会执行：

- 源码态 worker `--help` 预检
- backend `--check-tts-deps` 预检
- PyInstaller backend/worker 打包
- 打包后最小 smoke
- sidecar 安装到 `desktop-shell/src-tauri/binaries/`

### 前端 / Rust 回归

```bash
cd desktop-shell
npm test
npm run build
npm run test:rust
```

别把 `npm run build` 省掉。  
`desktop-shell/src-tauri/tauri.test.conf.json` 会通过 `TAURI_CONFIG` 清空测试态 `bundle.externalBin`；fast regression 不该为了跑 Rust 单测再先打一次 sidecar。

## 运行时落点

Tauri 壳启动后，运行时根目录固定在：

```text
~/Library/Application Support/com.wechatauto.shell
```

这里会保存：

- `config/listener.json` 和其他 `config/*.json`
- `logs/desktop-shell-bootstrap.log`
- `logs/.runtime/backend-sidecar.json`

别把源码态和壳运行时当成同一套配置：

- `python3 listener_app/backend_main.py --config "./config/listener.json"` 读取仓库里的 `config/listener.json`
- `npm run tauri dev`、release shell 和 smoke 读取 `~/Library/Application Support/com.wechatauto.shell/config/listener.json`

这两套配置目录不会自动同步。  
桌面壳设置页保存时，也只会写当前 backend 正在使用的那套配置。

## 启动契约

- `/healthz` 只有在 HTTP 200 且响应 JSON 的 `status == "ok"` 时才算 ready。
- managed backend 冷启动阶段前端状态应显示 `starting`，不能再拿 `reconnecting` 伪装。
- 首次连上前就 fatal 的错误是 `startup_failed`，不是 `degraded`。
- `reconnecting` 只允许用于“已经成功连过一次 WebSocket 之后”的断线重连。
- 第二次启动桌面壳时，只允许聚焦已有 `main` 窗口；不允许再 spawn 第二个壳，也不允许再补拉一份 backend sidecar。
- 关闭当前壳后，owned backend 的 `/healthz` 最终必须不可达；release smoke 已把 cleanup 校验纳入默认观察点。

## `.env.local` 规则

源码态默认读仓库根目录 `.env.local`。

Tauri 壳运行时按这个顺序找 `.env.local`：

1. `~/Library/Application Support/com.wechatauto.shell/.env.local`
2. shell 可执行文件同目录 `.env.local`

默认仍不自动复制 `.env.local` 进产物。  
fresh runtime root 不带 `.env.local` 也应该能进壳和设置页；只有启用 DeepLX / OpenAI-compatible / 云 TTS 时，才要求额外 URL 或凭据。

## 发布闸口

推荐按这个顺序验：

1. `python3 scripts/build_desktop_shell_sidecars.py --python python3`
2. `cd desktop-shell && npm test`
3. `cd desktop-shell && npm run build`
4. `cd desktop-shell && npm run test:rust`
5. `python3 scripts/smoke_desktop_shell_release.py`

只有这几步都过，才允许把 release shell 当成可交付产物。

`scripts/smoke_desktop_shell_release.py` 当前会做这些事：

- 必要时执行 `cd desktop-shell && npm run tauri -- build`
- 启动探测到的 mac release shell
- 轮询 `http://127.0.0.1:8765/healthz`
- 检查 `~/Library/Application Support/com.wechatauto.shell/logs/desktop-shell-bootstrap.log`
- 再启动第二次壳，确认出现 `single-instance relaunch detected, focus existing window`
- 断言整轮 smoke 里只出现一次 `spawning backend sidecar`
- 关闭壳后确认 backend health 不再可达
- 断言 bootstrap log 里不能出现 `backend stderr:`、`backend error:`、`bootstrap failed:`、traceback 或 panic 片段

## 图标输入

- `desktop-shell/src-tauri/icons/icon.svg`：仓库里的设计源
- `desktop-shell/src-tauri/icons/icon.png`：当前 mac build / test 使用的显式 PNG 输入
- `desktop-shell/src-tauri/icons/icon.ico`：仍保留给跨平台配置里的 Windows 图标链路

需要重生图标时，执行：

```bash
python3 scripts/generate_desktop_shell_icon.py
```

## 常见误判

### 1) 旧 runtime root 污染了 fresh install 结果

- 壳运行时配置不在仓库目录，而在 `~/Library/Application Support/com.wechatauto.shell`
- 如果要验证“真正首启默认值”，先隔离或备份这个目录

### 2) `npm run test:rust` 通过，不等于 packaged smoke 通过

- Rust 单测只验证测试态 Tauri 配置和纯逻辑
- sidecar 命名、release shell 路径、`/healthz`、single-instance 和 cleanup 要看 `scripts/smoke_desktop_shell_release.py`

### 3) 关闭壳窗口不等于 cleanup 验收通过

真正的验收是同时满足：

- `http://127.0.0.1:8765/healthz` 不再可达
- `desktop-shell-bootstrap.log` 有 relaunch / cleanup 相关记录
- 再次启动时不会复用一份“残活但无主”的 backend

## 回滚边界

- release shell 如果回归，优先回退到源码态主路径：`python3 listener_app/backend_main.py --config "./config/listener.json"` + `cd desktop-shell && npm run dev`
- 如果回归来自打包链，先修 sidecar / smoke / single-instance，不要靠恢复 Windows 旧链路掩盖问题
