# AGENTS

执行本仓库与“微信监听/侧边栏/翻译”相关任务前，先阅读：
- `docs/wechat-listening-pitfalls.md`

## 路径职责总览

### 根目录
- `.git/`：Git 元数据目录。
- `.env.local`：本地环境变量（例如 `DEEPLX_URL`），仅本机使用，已在 `.gitignore` 中忽略。
- `config/listener.json`：监听/翻译/展示主配置（目标会话、翻译策略、侧边栏参数）。
- `.gitignore`：Git 忽略规则。
- `AGENTS.md`：仓库工作约束与路径职责说明（本文件）。
- `LICENSE`：MIT 许可证。
- `README.md`：项目使用文档与示例命令。
- `pyproject.toml`：Python 包构建与依赖声明。
- `requirements.txt`：运行依赖列表。
- `@AutomationLog.txt`：本地调试日志文件（运行期产物）。

### 核心代码 `wechat_auto/`
- `wechat_auto/__init__.py`：包导出入口（`WxAuto`）。
- `wechat_auto/core.py`：`WxAuto` 主类，聚合加载窗口、打开会话、发送、监听能力。
- `wechat_auto/window.py`：微信主窗口定位与激活逻辑（含 WeChat/Weixin 主窗口筛选）。
- `wechat_auto/controls.py`：UIA 控件定位与通用文本判定工具（会话列表、消息列表、搜索框）。
- `wechat_auto/chat.py`：打开指定会话（会话列表优先，搜索框回退）。
- `wechat_auto/listener.py`：通用未读会话与最后消息读取能力。
- `wechat_auto/sender.py`：发送文本/文件。
- `wechat_auto/clipboard.py`：Windows `CF_HDROP` 文件剪贴板实现。
- `wechat_auto/logger.py`：统一日志输出函数。

### 当前主流程脚本 `examples/`
- `examples/group_listener_worker.py`：监听 worker 进程；输出 JSON 行事件；监听目标由 `config/listener.json` 或 CLI 参数决定。
- `examples/sidebar_translate_listener.py`：侧边栏 UI + DeepLX 翻译 + worker 管理；读取配置并启动 worker。

### 历史示例 `examples/legacy/`
- `examples/legacy/auto_reply.py`：自动回复示例（历史能力，非当前主流程）。
- `examples/legacy/demo_send_to_file_helper.py`：发送文本/文件示例（历史能力）。
- `examples/legacy/listen_group_to_inputbox.py`：监听并写入输入框示例（历史能力）。
- `examples/legacy/listen_only.py`：仅监听打印示例（历史能力）。

### 文档与运行产物
- `docs/wechat-listening-pitfalls.md`：监听架构、坑位、排障与实现契约。
- `logs/`：运行日志目录（例如侧边栏日志）。
- `dist/`：构建产物目录（wheel/tar.gz）。
- `wechat_pc_auto.egg-info/`：打包元数据目录（构建产物）。

## 文件级路径清单（当前仓库）
- `LICENSE`：MIT 许可证文本。
- `README.md`：项目说明、安装、示例命令。
- `AGENTS.md`：仓库工作约束与路径职责。
- `pyproject.toml`：构建系统与项目元数据。
- `requirements.txt`：依赖列表。
- `.gitignore`：忽略规则。
- `.env.local`：本地环境变量。
- `config/listener.json`：监听与翻译主配置。
- `@AutomationLog.txt`：本地调试日志。
- `docs/wechat-listening-pitfalls.md`：监听与翻译链路踩坑文档。
- `examples/sidebar_translate_listener.py`：侧边栏 UI、翻译、worker 管理。
- `examples/group_listener_worker.py`：监听 worker，输出 JSON 事件。
- `examples/legacy/auto_reply.py`：自动回复历史示例。
- `examples/legacy/demo_send_to_file_helper.py`：发送文本/文件历史示例。
- `examples/legacy/listen_group_to_inputbox.py`：监听写入输入框历史示例。
- `examples/legacy/listen_only.py`：仅监听打印历史示例。
- `wechat_auto/__init__.py`：包导出入口。
- `wechat_auto/core.py`：`WxAuto` 主类。
- `wechat_auto/window.py`：窗口定位与激活。
- `wechat_auto/controls.py`：UIA 控件查找与文本判定。
- `wechat_auto/chat.py`：打开指定会话。
- `wechat_auto/listener.py`：读取未读会话与最后消息。
- `wechat_auto/sender.py`：发送文本/文件。
- `wechat_auto/clipboard.py`：文件剪贴板实现。
- `wechat_auto/logger.py`：日志输出。
- `wechat_pc_auto.egg-info/PKG-INFO`：构建生成的包元数据。
- `wechat_pc_auto.egg-info/SOURCES.txt`：构建生成的源码清单。
- `wechat_pc_auto.egg-info/requires.txt`：构建生成的依赖清单。
- `wechat_pc_auto.egg-info/top_level.txt`：构建生成的顶层包名清单。
- `wechat_pc_auto.egg-info/dependency_links.txt`：构建生成的依赖链接占位文件。
- `dist/wechat_pc_auto-1.0.0-py3-none-any.whl`：历史构建产物。
- `dist/wechat_pc_auto-1.0.0.tar.gz`：历史构建产物。
- `dist/wechat_pc_auto-1.1.0-py3-none-any.whl`：历史构建产物。
- `dist/wechat_pc_auto-1.1.0.tar.gz`：历史构建产物。
- `dist/wechat_pc_auto-1.1.1-py3-none-any.whl`：历史构建产物。
- `dist/wechat_pc_auto-1.1.1.tar.gz`：历史构建产物。

## 维护约束
- 监听主链路默认只维护 `examples/sidebar_translate_listener.py` + `examples/group_listener_worker.py`。
- 任何监听相关改动都要同步更新 `docs/wechat-listening-pitfalls.md`。
- 任何 `config/listener.json` 字段新增/删除/语义变更，必须同步更新 `config/listener.md` 对应说明与示例。
