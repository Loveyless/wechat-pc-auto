<p align="center">
  <img src="./desktop-shell/src-tauri/icons/icon.svg" alt="WeChat Auto Shell" width="112" height="112" />
</p>

<img width="1490" height="806" alt="image" src="https://github.com/user-attachments/assets/51f58dd2-f642-4b7c-97f0-b923c9136eff" />

# WeChat Auto Shell for Apple Silicon macOS

这是当前仓库的 `Apple Silicon macOS` 适配分支，目标是把原本面向 Windows 的微信预览监听桌面壳迁到 `M1+ / arm64 macOS`。

当前分支只定义 mac 版本目标与迁移边界：

- 只面向 `M1 / M2 / M3 / M4` 及之后的 `arm64 macOS`
- 不再兼容 Windows
- 不覆盖 Intel Mac
- 不新增参考仓库的浮窗、SQLite、词典、AI 等额外功能

当前项目要做的事仍然很单一：盯住微信左侧会话列表，把最新预览整理到独立界面里，并按需接翻译和朗读。

它不是聊天机器人，也不是“完整聊天记录抓取器”。它不发消息、不自动回复、不写输入框，也不读取右侧聊天区全文。

## 当前状态

- 这个分支已经明确切换为 mac 版，不再维护 Windows 兼容。
- 当前仓库里仍然存在不少 Windows 遗留实现和文档，后续会按阶段迁到 mac-only。
- 详细范围、分阶段任务和验证口径见 [docs/apple-silicon-mac-adaptation-plan.md](./docs/apple-silicon-mac-adaptation-plan.md)。

## 它适合谁

- 想低打扰跟踪微信群或私聊最新动静的人
- 想把英文或中英混合消息顺手翻译成可读文本的人
- 想在 Apple Silicon Mac 上单独看状态、消息预览和日志的人
- 想要一个不改微信客户端的监听方案的人

## 你会得到什么

- 监听微信左侧可见会话预览，自动提取最新变化
- 在本地桌面壳里查看会话列表、消息卡片、运行状态和健康信息
- 按需接入翻译服务，把外语消息转换成更容易读的文本
- 按需接入朗读能力，让消息可以直接播出来
- 单实例桌面壳，重复启动只聚焦已有窗口

## 你需要先接受的限制

- 当前抓的是左侧会话预览，不是右侧聊天区全文
- 长消息会被微信预览截断，后半段拿不回来
- 当前只覆盖左侧可见会话，看不见的会话本轮抓不到
- 这套方案适合低干扰浏览、翻译、朗读，不适合完整审计或归档
- 不提供发送消息、发送文件、自动回复、写输入框等主动操作

## 普通用户怎么理解它

- 这条分支的目标是 `Apple Silicon macOS` 桌面版本，不再是 Windows 版说明书。
- 根文档现在优先定义范围、边界和迁移方向，不把旧 Windows 启动方式继续包装成当前版本事实。
- 在 mac 构建链与 sidecar 接通前，不承诺现有旧命令可以直接代表这个分支已适配完成。

## 开发启动方式

当前分支仍处于 mac 迁移中。

现阶段先看这两份文档：

- 迁移计划：[docs/apple-silicon-mac-adaptation-plan.md](./docs/apple-silicon-mac-adaptation-plan.md)
- 深水区约束：[docs/wechat-listening-pitfalls.md](./docs/wechat-listening-pitfalls.md)

当前已经验证过的开发启动、构建和 smoke 命令，以维护者文档里的执行说明为准，不再回退到旧 Windows 说明。

如果你在仓库深层文档或旧代码里看到下面这些内容，请默认当成“待迁移的旧实现信息”，不要把它们理解为当前分支的目标事实：

- Windows
- `.exe`
- `%LOCALAPPDATA%`
- `taskkill`
- `uiautomation`
- `windows_system`

## 文档分流

- 分支定位与边界：看这份 `README.md`
- 迁移计划：看 [docs/apple-silicon-mac-adaptation-plan.md](./docs/apple-silicon-mac-adaptation-plan.md)
- 配置契约：看 [config/listener.md](./config/listener.md)
- 开发者 / 维护者：看 [docs/developer-guide.md](./docs/developer-guide.md)
- 桌面壳构建与 release 验收：看 [docs/desktop-shell-build.md](./docs/desktop-shell-build.md)

## 协议

MIT License
