## Context

当前仓库已经有明确的 mac-only 顶层定位，但文档事实源还没有完全收口：

- `README.md` 已被用户改到 mac-only 定位，适合作为用户入口和分支边界真相源。
- `docs/desktop-shell-build.md` 和 `docs/wechat-listening-pitfalls.md` 刚刚收口了 `.app build + smoke` 与 `DMG` 专项验收的最新事实。
- `config/listener.md` 已经写入当前启动方式、运行时根目录、默认 provider 和 `/api/config` DTO/save/apply 语义，但其中部分 translate/TTS provider 细节仍会受未完成 config change 继续影响。
- `docs/developer-guide.md` 仍大面积保留 Windows 命令、产物名和路径，是当前最明显的深层文档事实漂移点。

这次 change 不是重定义运行时行为，而是把已经验证过的 mac 主链路事实写成跨文档一致的说明，同时把还没稳定的部分明确标成“迁移中 / 兼容读”，避免文档超前宣称。

## Goals / Non-Goals

**Goals:**

- 让 `README.md`、`config/listener.md`、`docs/developer-guide.md`、`docs/desktop-shell-build.md`、`docs/wechat-listening-pitfalls.md` 对当前 mac 分支的开发入口、运行时路径、构建闸口和风险边界给出一致说明。
- 保留必要的 Windows 历史对照信息，但明确标注为旧实现参考，避免继续冒充当前分支步骤。
- 让维护者按文档能完成最小开发启动和 release app 验证，并清楚知道 `DMG` 属于 GUI 专项验收而非默认自动闸口。

**Non-Goals:**

- 不修改业务代码或运行时 API，只收口文档。
- 不在文档里提前写死仍受 `update-translate-tts-config-contracts` 或 `add-desktop-config-gui-and-apply-flow` 影响的未来结构。
- 不把现有多份文档重写成大教程；仍保持查表式、面向执行。

## Decisions

### Decision: 采用“顶层入口 + 深层执行说明 + 历史对照标签”三层事实源

- `README.md` 只负责分支定位、用户边界、文档分流和高层开发入口。
- `config/listener.md`、`docs/developer-guide.md`、`docs/desktop-shell-build.md` 承担具体执行步骤和维护说明。
- `docs/wechat-listening-pitfalls.md` 保留迁移期旧实现参考，但每处 Windows 当前态都必须显式带“旧实现 / 对照参考”语境。

这样做的原因是根文档和深层文档面向的读者不同；若把所有事实都挤进 README，会再次造成高层说明和执行细节混杂。

**Alternatives considered**

- **把所有步骤都塞回 README**：拒绝，因为普通用户和维护者需要的信息密度不同。
- **完全删除 Windows 对照内容**：拒绝，因为迁移期仍需要保留历史对照，但必须明确降级为参考。

### Decision: 对未稳定的 config/settings 细节采用“当前已验证 + 兼容边界 + 未完成项不写死”的写法

`config/listener.md` 和 `docs/wechat-listening-pitfalls.md` 已经碰到正在进行中的 config/settings change。  
本 change 只写当前代码和已验证命令能支撑的事实，例如：

- 当前源码态启动命令
- 当前 Tauri 运行时根目录
- 当前 `/api/config` 已经暴露的 DTO/save/apply 语义
- 当前默认 build/smoke 闸口

对仍可能继续变化的 provider 细节，不提前宣称“最终完成”，而是保留兼容读或迁移中边界。

**Alternatives considered**

- **直接把 plan/后续设想写进文档当当前事实**：拒绝，因为这会制造新的文档超前问题。
- **为避免漂移完全不碰 `config/listener.md`**：拒绝，因为当前文档已经承载配置事实，继续放任会让用户读到过期信息。

### Decision: 默认 release 验证统一收口为 `.app build + smoke`，`DMG` 单列专项验收

当前 `.app` build + smoke 已经有真实命令和验证结果支撑，而 `DMG` 最后一步依赖 Finder AppleScript。  
因此文档统一采用：

- 默认自动化闸口：`npm run tauri -- build --bundles app` + `python3 scripts/smoke_desktop_shell_release.py --skip-build ...`
- GUI 专项验收：`npm run tauri build`

这样做的原因是这条边界已经被实际验证；继续把完整 `DMG` build 写成默认闸口，会把 GUI 会话前提错误地包装成桌面壳主链路要求。

**Alternatives considered**

- **继续把 `npm run tauri build` 写成默认 release gate**：拒绝，因为它会把 `DMG` AppleScript 风险混入主链路。

## Risks / Trade-offs

- **[未完成 config changes 仍会继续改文档真相源]** → 在 `config/listener.md` 和 pitfalls 中只写当前已验证事实，对未来结构保留兼容边界和迁移中表述。
- **[用户已有未提交文档改动]** → 读取并沿用当前内容，不回退或覆盖用户已经在收的 mac-only 方向。
- **[Windows 历史对照删太狠会影响迁移排障]** → 保留参考，但统一加显式标签，不再放在默认步骤里。

## Migration Plan

1. 先收口 `README.md`、`docs/developer-guide.md`、`docs/desktop-shell-build.md` 这三份用户入口和执行入口文档。
2. 再更新 `config/listener.md`，把当前配置事实与兼容边界写清，但不超前宣称未完成的 config 结构。
3. 最后调整 `docs/wechat-listening-pitfalls.md` 的引导和标签，让当前分支有效事实与旧实现对照分层更清楚。
4. 用关键词扫描、命令核对和最小开发/构建回归验证文档与代码一致性。

**Rollback strategy**

- 若某份文档改动与用户现有未提交内容冲突，优先保留用户已写明的 mac-only 方向，再做最小补丁，不做回退。
- 若上游 config change 在本轮执行中暴露出新的未稳定点，则文档改写回“兼容读/迁移中”表述，不强行定稿。

## Open Questions

- None. 当前范围已经足够明确：这是文档事实源收口，不扩成新的运行时行为 change。
