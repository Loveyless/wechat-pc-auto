# 当前主路径测试与构建

适用范围：

- `listener_app/backend_main.py`
- `listener_app/group_listener_worker.py`
- `desktop-shell/`

这份文档只讲当前主路径：`Python backend + React/Tauri 桌面壳`。
旧 Tk 路径的 Windows 打包仍看 `docs/windows-packaging.md`。

## 结论

- 当前主路径已经支持 Tauri 一体化桌面壳。
- `npm run tauri dev` / `npm run tauri build` 会先构建 PyInstaller sidecar，再由 Tauri 自动托管 backend。
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

## 最小验证

推荐按这个顺序验：

1. 执行 `npm run tauri build`
2. 直接运行 `desktop-shell/src-tauri/target/release/wechat-auto-shell.exe`
3. 访问 `http://127.0.0.1:8765/healthz`，预期返回 `{"status":"ok"}`
4. 看 `%LOCALAPPDATA%\com.wechatauto.shell\logs\desktop-shell-bootstrap.log`
   - 预期能看到 `spawned backend sidecar pid=...`
   - 二次启动壳时，预期看到 `reuse backend marker ...`，而不是再 spawn 一份
5. 若要查 sidecar 身份，看 `%LOCALAPPDATA%\com.wechatauto.shell\logs\.runtime\backend-sidecar.json`

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

这不一定是故障。

当前 `/healthz` 只有在 backend 完成启动后才会 ready。
Tauri 壳会先拉起 sidecar，再等它变成健康状态；如果 15 秒内还没 ready，前端会短暂重连，等 API 真起来后恢复。

判断是不是坏了，看结果，不看瞬时状态：

- `http://127.0.0.1:8765/healthz` 最终是否返回 `{"status":"ok"}`
- `/api/runtime` 是否能返回 `worker_state`

### 3) 打包后壳能起，但启动阶段直接失败

优先看两类问题：

- `translate.enabled=true` 但 `translate.deeplx_url` / `DEEPLX_URL` 没给
- `.env.local` 放错位置

这类问题现在会 fail-fast，不会再假装“壳起了所以算成功”。
