# 当前主路径测试与构建

适用范围：

- `listener_app/backend_main.py`
- `listener_app/group_listener_worker.py`
- `desktop-shell/`

这份文档只讲当前主路径：`Python backend + React/Tauri 桌面壳`。
Tk 回退打包链已经下线，不要再把仓库理解成“双桌面入口并存”。

## 结论

- 当前主路径已经支持 Tauri 一体化桌面壳。
- `npm run tauri dev` / `npm run tauri build` 会先构建 PyInstaller sidecar，再由 Tauri 自动托管 backend。
- 桌面壳现在按 `single-instance` 运行：第二次启动只聚焦已有窗口，不得再拉第二个壳窗口。
- `npm run tauri build` 产物可以直接双击，壳会自动拉起：
  - `wechat-auto-backend.exe`
  - `group_listener_worker.exe`
- 运行时配置、日志、锁不再写回源码目录，而是落到：
  - `%LOCALAPPDATA%\com.wechatauto.shell`

别再把“密钥仍然外置”误读成“不是一体化”。
真正的边界只有一个：`.env.local` 不会被自动打进安装包。

## 前提

- 已安装 Python 依赖：`pip install -r requirements.txt`
- 已安装前端依赖：`cd desktop-shell && npm install`
- 已安装 Rust toolchain：`cargo` / `rustc`

如果终端里找不到 `cargo`，先修 PATH，不要把环境问题甩给仓库。

## 命令

### 源码态后端 + 前端开发页

```bash
python listener_app/backend_main.py --config ".\config\listener.json"
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
python ..\scripts\build_desktop_shell_sidecars.py
```

然后由 Tauri 壳托管 sidecar，不再要求你手工先跑 `backend_main.py`。

### Tauri 壳构建

```bash
cd desktop-shell
npm run tauri build
```

这条命令同样会先自动构建 sidecar，再产出 release 壳和 installer。

### 前端/Rust 回归

```bash
cd desktop-shell
npm test
npm run build

cd src-tauri
cargo test
```

别把 `npm run build` 省掉。
`desktop-shell/src-tauri/tauri.conf.json` 把 `frontendDist` 固定指到 `../dist`；在干净环境里不先产出这个目录，`cargo test` 会直接在 `tauri::generate_context!()` 这里炸掉。

## 产物

`npm run tauri build` 当前会产出：

- `desktop-shell/src-tauri/target/release/wechat-auto-shell.exe`
- `desktop-shell/src-tauri/target/release/wechat-auto-backend.exe`
- `desktop-shell/src-tauri/target/release/group_listener_worker.exe`
- `desktop-shell/src-tauri/target/release/bundle/msi/*.msi`
- `desktop-shell/src-tauri/target/release/bundle/nsis/*-setup.exe`

sidecar 源文件同时会被放进：

- `desktop-shell/src-tauri/binaries/`

## 运行时落点

Tauri 壳启动后，运行时根目录固定在：

```text
%LOCALAPPDATA%\com.wechatauto.shell
```

这里会保存：

- `config/listener.json` 和其他 `config/*.json`
- `logs/desktop-shell-bootstrap.log`
- `logs/.runtime/backend-sidecar.json`

## 启动契约

- `/healthz` 只有在 HTTP 200 且响应 JSON 的 `status == "ok"` 时才算 ready。
- managed backend 冷启动阶段前端状态应显示 `starting`，不能再拿 `reconnecting` 伪装。
- 首次连上前就 fatal 的错误是 `startup_failed`，不是 `degraded`。
- `reconnecting` 只允许用于“已经成功连过一次 WebSocket 之后”的断线重连。
- 第二次启动 `wechat-auto-shell.exe` 时，只允许聚焦已有 `main` 窗口；不允许再 spawn 第二个壳，也不允许再补拉一份 backend sidecar。

配置复制规则是：

- 首次启动时，把 bundle 里的 `config/*.json` 拷到运行时目录
- 运行时目录里已经存在的配置，不覆盖

## `.env.local` 规则

源码态默认读仓库根目录 `.env.local`。

Tauri 壳运行时按这个顺序找 `.env.local`：

1. `%LOCALAPPDATA%\com.wechatauto.shell\.env.local`
2. `wechat-auto-shell.exe` 同目录 `.env.local`

这不是多余设计，是为了同时满足两件事：

- 运行时目录可写，适合用户自己覆盖
- 安装目录可读，适合本机自用时手工放一份

但默认仍不自动复制 `.env.local` 进产物。
原因很简单：这玩意通常带密钥，自动打包出去就是泄漏。

## 发布闸口

推荐按这个顺序验：

1. 执行 `python scripts/build_desktop_shell_sidecars.py --python python`
2. 执行 `cd desktop-shell && npm test`
3. 执行 `cd desktop-shell && npm run build`
4. 执行 `cd desktop-shell/src-tauri && cargo test`
5. 执行 `python scripts/smoke_desktop_shell_release.py`
6. 只有这五步都过，才允许把 release 壳当成可交付产物

`scripts/smoke_desktop_shell_release.py` 会实际做这些事：

- 执行 `npm run tauri -- build`
- 启动 `desktop-shell/src-tauri/target/release/wechat-auto-shell.exe`
- 轮询 `http://127.0.0.1:8765/healthz`
- 检查 `%LOCALAPPDATA%\com.wechatauto.shell\logs\desktop-shell-bootstrap.log`
- 再启动第二次壳，确认出现 `single-instance relaunch detected, focus existing window`
- 断言整轮 smoke 里只出现一次 `spawning backend sidecar`
- 断言本轮 bootstrap log 里不能出现 `backend stderr:`、`backend error:`、`bootstrap failed:` 或 traceback / panic 片段

2026-03-11 已在当前仓库实际跑过：

- `python scripts/build_desktop_shell_sidecars.py --python python`
- `cd desktop-shell && npm install`
- `cd desktop-shell && npm test`
- `cd desktop-shell && npm run build`
- `cd desktop-shell/src-tauri && cargo test`
- `python scripts/smoke_desktop_shell_release.py`

当前 sidecar 构建会额外显式收集 `charset_normalizer`，并通过仓库内 PyInstaller hook 动态补齐它的发行版级 `__mypyc` 顶层模块；否则 frozen 包里 `requests` 会把真实导入失败降级成 `RequestsDependencyWarning`。
如果 packaged backend 的 `--check-tts-deps` 仍然打出 `RequestsDependencyWarning`，构建脚本现在会直接失败，不再把这种 warning 当成“可以先忍”的噪音。
`scripts/packaging_manifest.json` 现在是 PyInstaller 依赖采集和 smoke 脏告警规则的单一来源；改这里，不要再手改两套脚本参数。

## 常见误判

### 1) 任务管理器里看到两个 `wechat-auto-backend.exe`

先别乱扣“重复启动”的帽子。

当前 sidecar 用的是 PyInstaller `onefile`。
Windows 下常见表现就是：

- 一个同名父进程：bootloader / 解包器
- 一个同名子进程：真正跑 Python 代码

`group_listener_worker.exe` 也可能出现同样的双进程形态。

真正的重复 spawn 要看的是：

- `desktop-shell-bootstrap.log` 里是否同一轮出现了两次 `spawning backend sidecar`
- `backend-sidecar.json` 记录的 pid/token 是否被无意义覆盖

### 2) 冷启动时先看到 `reconnecting`

现在如果还看到这个，优先怀疑前端状态机回归了。

当前正确语义是：

- 冷启动中的 managed backend: `starting`
- 首次启动失败: `startup_failed`
- 连通过后再断线: `reconnecting`

判断是不是坏了，看结果，不看单次过渡：

- `http://127.0.0.1:8765/healthz` 最终是否返回 `{"status":"ok"}`
- `/api/runtime` 是否能返回 `worker_state`
- `%LOCALAPPDATA%\com.wechatauto.shell\logs\desktop-shell-bootstrap.log` 是否能看到一次 `spawning backend sidecar`

### 3) 打包后壳能起，但启动阶段直接失败

优先看两类问题：

- `translate.enabled=true` 但 `translate.deeplx_url` / `DEEPLX_URL` 没给
- `.env.local` 放错位置

这类问题现在会 fail-fast，不会再假装“壳起了所以算成功”。

## 回滚边界

- release 壳如果回归，优先回退到当前源码态主路径：`backend_main.py + npm run dev`，或者 `npm run tauri dev` 做开发期排障。
- 当前正式桌面 UI 只有 `desktop-shell/`；不要再发明历史 UI fallback。
- 如果回归来自打包链，先修 sidecar / smoke / single-instance，再谈重新发包；不要靠 resurrect 已删除路径掩盖问题。
