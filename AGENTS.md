# AGENTS

执行本仓库与“微信监听 / 桌面壳 / 翻译 / TTS”相关任务前，先阅读：
- `docs/wechat-listening-pitfalls.md`

## 路径职责总览

### 根目录
- `.git/`：Git 元数据目录。
- `.env.local`：本地环境变量，仅本机使用，已在 `.gitignore` 中忽略。
- `config/listener.json`：当前主路径运行配置。
- `config/listener.md`：`listener.json` 字段说明与 provider 配置示例。
- `.gitignore`：Git 忽略规则。
- `.gitattributes`：仓库级行尾与文本规则。
- `README.md`：项目使用说明、运行命令、交付边界。
- `pyproject.toml`：Python 包构建与项目元数据。
- `requirements.txt`：Python 运行依赖。
- `@AutomationLog.txt`：本地调试日志文件（运行期产物）。

### 核心代码 `wechat_auto/`
- `wechat_auto/__init__.py`：包导出入口（`WxAuto`）。
- `wechat_auto/core.py`：`WxAuto` 主类，仅保留微信窗口加载与只读会话查询能力。
- `wechat_auto/window.py`：微信主窗口定位与过滤逻辑。
- `wechat_auto/controls.py`：UIA 控件树定位与文本判定工具。
- `wechat_auto/logger.py`：统一日志输出函数。

### 当前主流程脚本 `listener_app/`
- `listener_app/backend_main.py`：源码态后端入口；负责启动 runtime 与本地 API。
- `listener_app/backend_runtime.py`：主路径 runtime 编排；负责 worker 监督、翻译、TTS、会话状态与健康状态。
- `listener_app/runtime_api.py`：本地 HTTP + WebSocket 契约层。
- `listener_app/runtime_config.py`：当前主路径唯一配置 schema owner。
- `listener_app/runtime_engine.py`：运行时状态机与事件分发。
- `listener_app/runtime_models.py`：运行时消息/事件模型。
- `listener_app/runtime_store.py`：会话与消息存储、去重边界。
- `listener_app/group_listener_worker.py`：微信 UIA 监听 worker；输出 JSON 行事件。
- `listener_app/sidebar_translate_runtime.py`：翻译 provider、DeepLX runtime 与失败 fallback。
- `listener_app/sidebar_runtime_support.py`：日志轮转、worker 启停支撑、运行时锁与 stdout/stderr reader。
- `listener_app/sidebar_tts.py`：Windows System / 豆包 / 腾讯云 TTS runtime、依赖探测与播放器工厂。
- `listener_app/sidebar_shared.py`：共享常量、路径/配置工具、文本归一化与通用校验。

### 桌面壳 `desktop-shell/`
- `desktop-shell/src/`：React + Vite 前端。
- `desktop-shell/src-tauri/`：Tauri 壳、single-instance、sidecar bootstrap。
- `desktop-shell/package.json`：前端测试、构建与 Tauri 命令入口。

### 脚本与文档
- `scripts/build_desktop_shell_sidecars.py`：构建 `wechat-auto-backend.exe` 与 `group_listener_worker.exe` sidecar。
- `scripts/smoke_desktop_shell_release.py`：release 壳 smoke；验证 `/healthz`、bootstrap log 与 single-instance。
- `scripts/packaging_manifest.json`：PyInstaller 依赖采集与 smoke 脏告警规则的单一来源。
- `docs/desktop-shell-build.md`：当前主路径测试、构建、产物与交付边界。
- `docs/wechat-listening-pitfalls.md`：监听链路、健康契约、打包与排障约束。
- `logs/`：源码态运行日志目录。

## 文件级路径清单（当前仓库）
- `README.md`：项目说明、运行命令、验证步骤。
- `config/listener.md`：主路径配置字段说明。
- `docs/desktop-shell-build.md`：桌面壳测试与构建文档。
- `docs/wechat-listening-pitfalls.md`：踩坑与契约文档。
- `listener_app/backend_main.py`：源码态后端入口。
- `listener_app/backend_runtime.py`：runtime 编排层。
- `listener_app/runtime_api.py`：本地 API。
- `listener_app/runtime_config.py`：配置 schema owner。
- `listener_app/runtime_engine.py`：状态机与事件分发。
- `listener_app/runtime_store.py`：消息与会话存储。
- `listener_app/group_listener_worker.py`：监听 worker。
- `listener_app/sidebar_translate_runtime.py`：翻译 runtime。
- `listener_app/sidebar_runtime_support.py`：worker 支撑与日志。
- `listener_app/sidebar_tts.py`：TTS runtime。
- `listener_app/sidebar_shared.py`：共享 helper。
- `desktop-shell/src/`：前端界面。
- `desktop-shell/src-tauri/`：Tauri 壳与 sidecar bootstrap。

## 维护约束
- 当前正式桌面 UI 只有 `backend_main.py + desktop-shell/`；Tk 回退路径已下线，不要再加回 `sidebar_translate_listener.py` / `sidebar_ui.py` 一类入口。
- 监听主链路默认维护：
  - `listener_app/backend_main.py`
  - `listener_app/backend_runtime.py`
  - `listener_app/runtime_api.py`
  - `listener_app/runtime_config.py`
  - `listener_app/runtime_engine.py`
  - `listener_app/runtime_store.py`
  - `listener_app/group_listener_worker.py`
  - `listener_app/sidebar_translate_runtime.py`
  - `listener_app/sidebar_runtime_support.py`
  - `listener_app/sidebar_tts.py`
  - `listener_app/sidebar_shared.py`
  - `desktop-shell/src/**`
  - `desktop-shell/src-tauri/**`
- 当前分支不再维护发送消息、发送文件、自动回复、写输入框等主动操作能力。
- 任何监听、健康契约、打包或 TTS 相关改动，都要同步更新 `docs/wechat-listening-pitfalls.md`。
- 任何 `config/listener.json` 字段新增、删除或语义变更，都必须同步更新 `config/listener.md`。
