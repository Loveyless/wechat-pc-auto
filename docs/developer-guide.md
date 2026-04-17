# 开发者文档

这份文档只服务开发、调试、回归和打包。普通用户看 `README.md` 即可；这里默认读者已经接受当前分支只面向 `Apple Silicon macOS`。

## 适用范围

- 当前正式路径只有 `listener_app/backend_main.py + desktop-shell/`
- Tk 回退链已经下线，不要再按“双桌面入口并存”理解仓库
- 当前分支不维护发送消息、发送文件、自动回复、写输入框等主动操作能力

## 先装环境

```bash
python3 -m pip install -r requirements.txt
cd desktop-shell
npm install
```

如果你要跑 Tauri 壳，还要保证本机能用 `cargo` / `rustc`。缺 Rust toolchain 时，只能验证源码态 backend 和 Vite 页面，别把它硬说成桌面壳已通过。

## 启动方式

### 源码态 backend + 前端开发页

```bash
python3 listener_app/backend_main.py --config "./config/listener.json"
cd desktop-shell
npm run dev
```

默认地址：

- HTTP：`http://127.0.0.1:8765`
- WebSocket：`ws://127.0.0.1:8766/events`

### Tauri 壳调试

```bash
cd desktop-shell
npm run tauri dev
```

这条命令会先跑：

```bash
python3 ../scripts/build_desktop_shell_sidecars.py --python python3
```

然后由 Tauri 壳托管 backend sidecar。不要手工再起一份 `backend_main.py` 去制造双实例和配置混淆。

## 测试与构建

### 最小回归

```bash
cd desktop-shell
npm test
npm run build
npm run test:rust
```

`npm run build` 不能省。`tauri::generate_context!()` 依赖 `desktop-shell/dist`，不先构建，Rust 测试就会失败。

### 默认 release app 交付闸口

```bash
python3 scripts/build_desktop_shell_sidecars.py --python python3
cd desktop-shell
npm test
npm run build
npm run test:rust
npm run tauri -- build --bundles app
cd ..
python3 scripts/smoke_desktop_shell_release.py --skip-build --shell-exe "desktop-shell/src-tauri/target/release/bundle/macos/WeChat Auto Shell.app/Contents/MacOS/wechat-auto-shell"
```

上面这套没跑完，就别把当前 mac release app 当成可交付产物。

### 可选：DMG 专项验收

```bash
cd desktop-shell
npm run tauri build
```

这一步会继续尝试产出 `DMG`，但最后的窗口美化依赖 Finder AppleScript。  
只有在可交互 Finder 会话里，它才应该被当成正式验收；如果 `.app build + smoke` 已过，而 `DMG` 卡在 `bundle_dmg.sh` / `osascript`，应把问题归为 GUI 专项验收风险，不要误判成桌面壳主链路回归。

## 产物

当前 mac 构建链的关键产物是：

- `desktop-shell/src-tauri/binaries/wechat-auto-backend-aarch64-apple-darwin`
- `desktop-shell/src-tauri/binaries/group_listener_worker-aarch64-apple-darwin`
- `desktop-shell/src-tauri/target/release/wechat-auto-shell`
- `desktop-shell/src-tauri/target/release/bundle/macos/WeChat Auto Shell.app`

`DMG` 只作为额外的 GUI 专项验收输出，不再是默认自动化发布闸口的一部分。

## 运行时边界

- 源码态 `python3 listener_app/backend_main.py --config "./config/listener.json"` 读取仓库里的 `config/listener.json`
- `npm run tauri dev`、release app 和 smoke 读取 `~/Library/Application Support/com.wechatauto.shell/config/listener.json`
- 这两套配置目录不会自动同步；桌面壳设置页只会改当前 backend 正在使用的那一套
- `.env.local` 在源码态默认读仓库根目录；Tauri 壳优先读 `~/Library/Application Support/com.wechatauto.shell/.env.local`

## 关键文档入口

- 配置契约与字段说明：[`config/listener.md`](../config/listener.md)
- 桌面壳测试、构建、产物与发布闸口：[`docs/desktop-shell-build.md`](./desktop-shell-build.md)
- 双分支维护、tag 规则与 GitHub Release 操作：[`docs/release-maintenance.md`](./release-maintenance.md)
- 监听、健康契约、打包与排障坑位：[`docs/wechat-listening-pitfalls.md`](./wechat-listening-pitfalls.md)

## 目录总览

```text
config/          运行配置与字段说明
listener_app/    Python backend、runtime、worker、TTS、translate
desktop-shell/   React + Vite + Tauri 桌面壳
scripts/         sidecar 构建与 release smoke
wechat_auto/     微信窗口与可访问性读取基础能力
docs/            深水区文档
```
