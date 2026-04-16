## Why

当前分支顶层定位已经明确切到 `Apple Silicon macOS`，但开发、配置、构建和踩坑文档仍然混着 Windows 当前态表述，导致维护者和新同学很难判断哪份文档才是当前分支的事实源。  
这件事必须现在单独成 change，因为监听 runtime、TTS runtime 和 Tauri sidecar/build 三条 mac 主链路都已经有完成的 change，文档再不收口，就会继续把已经稳定的 mac 事实和迁移前 Windows 说明混成双真相。

## What Changes

- 更新 `README.md`，把当前分支定位、用户入口、开发入口和文档分流收口到 `Apple Silicon macOS` 单一事实源，并继续保留明确的迁移边界。
- 更新 `config/listener.md`，让源码态启动、Tauri 运行时根目录、默认 provider、配置 DTO/save/apply 语义和当前代码事实保持一致；对仍受未完成 config changes 影响的细节显式标注迁移中或兼容边界。
- 更新 `docs/developer-guide.md` 与 `docs/desktop-shell-build.md`，统一最小开发启动、sidecar 构建、release app 验证闸口和 `DMG` 专项验收的口径，不再把 `.exe`、`msi`、`nsis`、`%LOCALAPPDATA%` 当成当前步骤。
- 更新 `docs/wechat-listening-pitfalls.md`，保留当前分支有效的产品边界、运行契约和迁移期高风险点，同时把保留的 Windows 旧实现信息显式标记为历史对照参考。

## Capabilities

### New Capabilities

- `macos-docs-fact-source`: 定义当前 Apple Silicon macOS 分支文档的权威事实源、历史对照标签和跨文档一致性要求。

### Modified Capabilities

- None.

## Impact

- **Affected code**:
  - `README.md`
  - `config/listener.md`
  - `docs/developer-guide.md`
  - `docs/desktop-shell-build.md`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - None. 本 change 只收口文档表达，不新增或修改运行时 API。
- **Dependencies / systems**:
  - 已完成的 mac listener/runtime、TTS runtime、Tauri sidecar/build change
  - 仍在进行中的 translate/TTS config contracts 与 desktop config GUI change 所带来的文档漂移风险
