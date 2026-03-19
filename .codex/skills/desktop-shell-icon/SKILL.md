---
name: desktop-shell-icon
description: 维护当前仓库 WeChat Auto Shell 的图标与品牌入口。用户提到修改桌面壳 icon、logo、README 顶部图、Windows 安装包图标、Tauri/NSIS 图标接线，或要把图标改动做成可打包可验证的完整闭环时，使用这个 skill。
---

# Desktop Shell Icon

维护 WeChat Auto Shell 图标时，不要只改一张图。默认目标是同时覆盖设计源、Windows 打包输入、Tauri 配置、README 展示和最小打包验证。

## 先读这些文件

- `docs/wechat-listening-pitfalls.md`
- `desktop-shell/src-tauri/icons/icon.svg`
- `desktop-shell/src-tauri/icons/icon.ico`
- `scripts/generate_desktop_shell_icon.py`
- `desktop-shell/src-tauri/tauri.conf.json`
- `README.md`
- `docs/desktop-shell-build.md`

图标改动属于打包链改动。别跳过坑位文档，也别只改视觉层。

## 工作流

### 1. 确认这次改动的边界

- 如果用户只是想讨论视觉方向，先给方向，不急着落文件。
- 如果用户要的是“下次打出来的 Windows 包就该带正确图标”，默认走完整闭环。
- 除非用户明确说“只改 README 展示”，否则不要只停在 `svg` 层。

### 2. 维护设计源

- 把设计源放在 `desktop-shell/src-tauri/icons/icon.svg`。
- 保持图标和当前产品视觉一致。当前仓库 UI 主色不是紫色套皮，先看前端已有配色再画。
- 如果图形结构变了，同时更新 `scripts/generate_desktop_shell_icon.py` 里的几何生成逻辑；不要手改 `ico` 二进制。

### 3. 重生 Windows 图标输入

- 执行：
  ```bash
  python scripts/generate_desktop_shell_icon.py
  ```
- 这一步会重写：
  - `desktop-shell/src-tauri/icons/icon.svg`
  - `desktop-shell/src-tauri/icons/icon.ico`
- 改完后至少确认 `icon.ico` 不是占位空文件。

### 4. 接好 Tauri 打包链

- 检查 `desktop-shell/src-tauri/tauri.conf.json`。
- Windows 图标链路至少要同时维护：
  - `bundle.icon`
  - `bundle.windows.nsis.installerIcon`
- 只配 `bundle.icon` 不够。那样 `exe/WiX` 可能正常，`NSIS setup.exe` 还是默认图标。

### 5. 同步对外展示与文档

- README 顶部如果展示产品图标，同步更新 `README.md`。
- 如果改动影响图标来源、打包输入或验证方式，同步更新：
  - `docs/desktop-shell-build.md`
  - `docs/wechat-listening-pitfalls.md`

### 6. 验证，不要凭感觉收工

最少执行：

```bash
python scripts/generate_desktop_shell_icon.py
cd desktop-shell
npm run tauri -- build
cd ..
python scripts/smoke_desktop_shell_release.py --skip-build
```

然后确认：

- `desktop-shell/src-tauri/target/release/nsis/x64/installer.nsi` 里的 `INSTALLERICON` 不是空字符串。
- 生成的 `wechat-auto-shell.exe` 和 `*-setup.exe` 能提取出目标图标，而不是系统默认空白图标。
- release smoke 通过，说明图标改动没有顺手打坏 sidecar 启动链。

## 常见错误

- 只改 `svg`，不重生 `ico`。结果：README 好看，Windows 包还是旧图标。
- 只配 `bundle.icon`，不配 `bundle.windows.nsis.installerIcon`。结果：主程序换了，安装器没换。
- 手工替换 `icon.ico`。结果：下次再改图时不可重复、不可维护。
- 不跑打包验证。结果：你以为图标改完了，实际发出去的包还是半残。

## 交付标准

- 设计源、Windows 输入、Tauri 配置和文档保持一致。
- `npm run tauri -- build` 通过。
- `python scripts/smoke_desktop_shell_release.py --skip-build` 通过。
- 最终说明里明确告诉用户：改了什么、为什么、影响、验证结果。
