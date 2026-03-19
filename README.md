<p align="center">
  <img src="./desktop-shell/src-tauri/icons/icon.svg" alt="WeChat Auto Shell" width="112" height="112" />
</p>

# WeChat Auto Shell

一个面向 Windows 的微信预览监听桌面壳：低打扰看左侧会话变化，把新消息整理到本地界面里，按需接翻译和 TTS。

它不是聊天机器人，不做主动发消息，不做自动回复，也不尝试读取完整聊天记录。它适合的是“看见左侧会话变化，快速浏览、翻译、朗读”的场景。

## 适合谁

- 想低打扰跟踪微信群/私聊的最新预览内容
- 想把微信里的英文/中英文消息顺手翻成可读文本
- 想在 Windows 上用本地桌面壳查看状态、日志和消息流
- 想要一个不改微信客户端的监听方案

## 核心能力

- 监听微信左侧可见会话预览，自动提取最新变化
- 桌面壳展示会话列表、消息卡片、运行状态和健康信息
- 支持翻译 provider：`deeplx`、`openai_compatible`、`passthrough`
- 支持 TTS：`windows_system`、`doubao`、`tencent_cloud`
- 支持单实例桌面壳，第二次启动只聚焦已有窗口
- 运行时配置、日志和锁都落在 `%LOCALAPPDATA%\com.wechatauto.shell`

## 你需要先接受的限制

- 当前抓的是左侧会话预览，不是右侧聊天区全文
- 长消息会被微信预览截断，后半段拿不回来
- 当前只覆盖左侧可见会话，看不见的会话本轮抓不到
- 这套方案适合低干扰浏览和翻译，不适合完整审计或归档
- 不提供发送消息、发送文件、自动回复、写输入框等主动操作

## 安装与启动

先装 Python 依赖：

```bash
pip install -r requirements.txt
```

再装前端依赖：

```bash
cd desktop-shell
npm install
```

### 源码态启动

开一个终端启动后端：

```bash
python listener_app/backend_main.py --config ".\config\listener.json"
```

再开一个终端启动前端开发页：

```bash
cd desktop-shell
npm run dev
```

- HTTP 默认地址：`http://127.0.0.1:8765`
- WebSocket 默认地址：`ws://127.0.0.1:8766/events`

### Tauri 桌面壳

如果本机已经装好 Rust toolchain：

```bash
cd desktop-shell
npm run tauri dev
```

`npm run tauri dev` 会先构建 PyInstaller sidecar，再由 Tauri 壳托管 backend。

### 打包

```bash
cd desktop-shell
npm run tauri build
```

这一步会产出 Windows 桌面壳、backend sidecar 和 worker sidecar。首次启动时，如果没有 `.env.local`，默认也应该能先进入壳和设置页。

## 默认配置

仓库跟踪的默认配置是“首启可用”的，不把密钥当成硬依赖：

- `translate.enabled=false`
- `tts.provider=windows_system`

如果你要接 DeepLX、OpenAI-compatible 翻译，或者启用豆包 / 腾讯云 TTS，再补对应 URL 和凭据即可。

## 发布产物

`npm run tauri build` 当前会产出：

- `wechat-auto-shell.exe`
- `wechat-auto-backend.exe`
- `group_listener_worker.exe`
- `msi`
- `nsis setup.exe`

第二次启动 `wechat-auto-shell.exe` 时，只会聚焦已有窗口，不会再拉第二份壳或 backend。
Windows 打包图标现在统一来自 `desktop-shell/src-tauri/icons/icon.svg` 和它生成的 `icon.ico`；别再拿空壳默认图标糊弄发布产物。

## 开发与构建

如果你在本地做回归，最少跑这几步：

```bash
cd desktop-shell
npm test
npm run build
npm run test:rust
```

更完整的交付闸口是：

```bash
python scripts/build_desktop_shell_sidecars.py --python python
cd desktop-shell
npm test
npm run build
npm run test:rust
python scripts/smoke_desktop_shell_release.py
```

## 配置与排障

- 配置说明：`config/listener.md`
- 桌面壳测试与构建：`docs/desktop-shell-build.md`
- 监听、健康契约和打包坑位：`docs/wechat-listening-pitfalls.md`

## 项目结构

```text
config/
desktop-shell/
docs/
listener_app/
wechat_auto/
```

## 协议

MIT License
