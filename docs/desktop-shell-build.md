# 当前主路径测试与构建

适用范围：

- `listener_app/backend_main.py`
- `listener_app/group_listener_worker.py`
- `desktop-shell/`

这份文档只讲当前分支的主路径：`Python backend + React/Tauri 桌面壳`。  
当前分支目标是 `Apple Silicon macOS`，不再把 Windows `.exe`、`msi`、`nsis` 或 `%LOCALAPPDATA%` 当成当前事实。

## 结论

- `npm run tauri dev` 会先构建 PyInstaller sidecar，再由 Tauri 自动托管 backend。
- 当前自动化发布闸口默认执行 `npm run tauri -- build --bundles app`，先验证可交付的 `.app`；完整 `DMG` 仍可通过 `npm run tauri build` 产出，但它依赖 Finder AppleScript，属于 GUI 专项验收。
- 桌面壳继续按 `single-instance` 运行：第二次启动只聚焦已有窗口，不得再拉第二个壳窗口。
- 当前 sidecar 安装名已经切到 target-triple 规则；在 Apple Silicon macOS 上，构建后会落：
  - `desktop-shell/src-tauri/binaries/wechat-auto-backend-aarch64-apple-darwin`
  - `desktop-shell/src-tauri/binaries/group_listener_worker-aarch64-apple-darwin`
- 桌面壳运行时根目录固定在：
  - `~/Library/Application Support/com.wechatauto.shell`
- 仓库跟踪的默认 bundle 配置现在以“fresh runtime root 首启可进入设置页”为目标：
  - `translate.enabled=false`
  - `tts.provider=macos_system`
- GitHub Release 现在分成两条线：
  - Windows 老分支继续使用 `.github/workflows/windows-release-on-tag.yml`，tag 规则保持 `v*`
  - 当前 mac 分支使用 `.github/workflows/macos-release-on-tag.yml`，tag 规则是 `mac-v*`
- mac tag 是否标记成 prerelease 只看是否包含 `-rc.`，不要再沿用“只要 tag 里有 `-` 就是 prerelease”的 Windows 旧判断。
- 当前 mac GitHub Release 不再允许发布 unsigned / unnotarized `.app zip`：
  - workflow 必须拿到 Apple 签名证书和公证凭据
  - 构建后还会额外执行 `codesign --verify`、`spctl --assess`、`xcrun stapler validate`
  - 这条链不过就直接失败，避免用户下载后被 Gatekeeper 报 “已损坏”
- 具体的双分支维护、tag 操作顺序和 GitHub Release 核对清单，统一看 `docs/release-maintenance.md`。

别把“密钥仍然外置”误读成“不是一体化”。  
真正的边界只有一个：`.env.local` 不会被自动打进产物。

## 前提

- 已安装 Python 依赖：`python3 -m pip install -r requirements.txt`
- 已安装 PyInstaller：`python3 -m pip install --user pyinstaller`
- 已安装前端依赖：`cd desktop-shell && npm install`
- 已安装 Rust toolchain：`cargo` / `rustc`
- 如果要跑当前 mac GitHub Release workflow，还必须先在仓库 Secrets 里配置：
  - 必填：`APPLE_CERTIFICATE`、`APPLE_CERTIFICATE_PASSWORD`
  - 二选一：
    - `APPLE_ID`、`APPLE_PASSWORD`、`APPLE_TEAM_ID`
    - `APPLE_API_KEY`、`APPLE_API_ISSUER`、`APPLE_API_PRIVATE_KEY`
  - 可选：`APPLE_SIGNING_IDENTITY`、`APPLE_PROVIDER_SHORT_NAME`

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

### 默认 release app 构建

```bash
cd desktop-shell
npm run tauri -- build --bundles app
```

这条命令同样会先自动构建 sidecar，再产出 `WeChat Auto Shell.app`。  
当前自动化发布闸口默认使用这条命令；`scripts/smoke_desktop_shell_release.py` 的默认 build 路径也已经切到这里，并优先启动 `desktop-shell/src-tauri/target/release/bundle/macos/WeChat Auto Shell.app/Contents/MacOS/wechat-auto-shell` 做 smoke。

### GitHub Release tag 约定

当前仓库不要再把 mac 分支 tag 和 Windows 老分支混用：

- Windows 老分支：
  - stable tag：`v0.1.0`
  - rc tag：`v0.1.0-rc.1`
- 当前 mac 分支：
  - stable tag：`mac-v0.1.0`
  - rc tag：`mac-v0.1.0-rc.1`

如果你要先同步版本入口，再拿推荐 tag，可以执行：

```bash
python3 scripts/sync_desktop_shell_release_version.py --channel stable --base-version 0.1.0 --tag-prefix mac-v
python3 scripts/sync_desktop_shell_release_version.py --channel rc --base-version 0.1.0 --rc-number 1 --tag-prefix mac-v
```

当前 `macos-release-on-tag.yml` 会发布这些公开资产：

- `wechat-auto-shell-<version>-macos-apple-silicon.zip`
- `SHA256SUMS.txt`

这条 workflow 现在还会在发布前强制校验：

- 签名证书和公证凭据已配置
- `WeChat Auto Shell.app` 通过 `codesign --verify`
- `WeChat Auto Shell.app` 通过 `spctl --assess`
- `WeChat Auto Shell.app` 的 notarization ticket 通过 `xcrun stapler validate`

`DMG` 仍然只作为可选 GUI 专项验收产物，不在默认 mac GitHub Release 自动化里承诺。

### GitHub Release 标题与公开资产命名

为避免双 release 页面看起来像两套完全无关的产物，当前仓库固定使用下面这套展示命名：

- Windows 老分支：
  - release 标题：`WeChat Auto Shell Windows <version>`
  - 公开资产：
    - `wechat-auto-shell-<version>-windows-x64.msi`
    - `wechat-auto-shell-<version>-windows-x64-setup.exe`
    - `SHA256SUMS.txt`
- 当前 mac 分支：
  - release 标题：`WeChat Auto Shell macOS Apple Silicon <version>`
  - 公开资产：
    - `wechat-auto-shell-<version>-macos-apple-silicon.zip`
    - `SHA256SUMS.txt`

这里的 `<version>` 不直接按 tag 去前缀计算：

- 以桌面壳真实 bundle 版本为准，读取来源是：
  - `desktop-shell/package.json`
  - `desktop-shell/src-tauri/tauri.conf.json`
- stable 示例：
  - `v0.1.0` -> `0.1.0`
  - `mac-v0.1.0` -> `0.1.0`
- RC 示例：
  - `v0.1.0-rc.1` -> `0.1.0-1`
  - `mac-v0.1.0-rc.1` -> `0.1.0-1`

### 可选：DMG 构建（GUI 专项验收）

```bash
cd desktop-shell
npm run tauri build
```

这条命令会继续尝试产出 `DMG`，但当前 mac 打包器会在最后一步调用 Finder AppleScript 做窗口美化。  
只有在可交互 Finder 会话里，这一步才应该作为正式验收；如果 `.app` 构建和 smoke 已通过，而 `DMG` 卡在 `bundle_dmg.sh` / `osascript`，应把它归类为 `DMG` 专项风险，不要误判成桌面壳主链路回归。

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
5. `cd desktop-shell && npm run tauri -- build --bundles app`
6. `python3 scripts/smoke_desktop_shell_release.py --skip-build --shell-exe "desktop-shell/src-tauri/target/release/bundle/macos/WeChat Auto Shell.app/Contents/MacOS/wechat-auto-shell"`

只有这 6 步都过，才允许把当前 mac release app 当成可交付产物。  
若还要发布 `DMG`，再额外在 GUI 会话里执行 `cd desktop-shell && npm run tauri build`。

`scripts/smoke_desktop_shell_release.py` 当前会做这些事：

- 必要时执行 `cd desktop-shell && npm run tauri -- build --bundles app`
- 优先启动探测到的 mac bundle app 可执行文件；找不到时才回退到 `target/release/wechat-auto-shell`
- 轮询 `http://127.0.0.1:8765/healthz`
- 检查 `~/Library/Application Support/com.wechatauto.shell/logs/desktop-shell-bootstrap.log`
- 再启动第二次壳，确认出现 `single-instance relaunch detected, focus existing window`
- 断言整轮 smoke 里只出现一次 `spawning backend sidecar`
- 关闭壳后确认 backend health 不再可达
- 断言 bootstrap log 里不能出现 `backend stderr:`、`backend error:`、`bootstrap failed:`、traceback 或 panic 片段

完整 `DMG` 构建不再是默认 smoke 闸口的一部分。  
如果要验 `DMG`，应在可交互 Finder 会话里单独跑 `npm run tauri build`；自动化默认只对 `.app` 和实际启动链路背书。

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

### 4) `DMG` 打包失败不等于 release app 回归

- `npm run tauri build` 的最后一段 `DMG` bundling 依赖 Finder AppleScript；它和 sidecar 托管、`.app` 启动、`/healthz`、single-instance、cleanup 不是同一层问题。
- 当前默认自动化闸口已经改成 `.app build + --skip-build smoke`；如果这条链通过，而 `DMG` 在 `bundle_dmg.sh` / `osascript` 失败，应把问题归到 GUI 专项验收，不要把它回报成桌面壳主链路坏了。

## 回滚边界

- release shell 如果回归，优先回退到源码态主路径：`python3 listener_app/backend_main.py --config "./config/listener.json"` + `cd desktop-shell && npm run dev`
- 如果回归来自打包链，先修 sidecar / smoke / single-instance，不要靠恢复 Windows 旧链路掩盖问题
