## 1. 用户入口与开发入口文档收口

- [ ] 1.1 复核并最小更新 `README.md`，确保分支定位、开发入口和文档分流只表达当前 Apple Silicon macOS 事实
- [ ] 1.2 更新 `docs/developer-guide.md`，把源码态启动、Tauri 调试、release app 闸口、产物名和运行时路径切到当前 mac-only 事实

## 2. 配置与踩坑文档事实源收口

- [ ] 2.1 更新 `config/listener.md`，统一当前源码态/Tauri 配置路径、默认 provider、`/api/config` save/apply 边界和已验证构建说明
- [ ] 2.2 更新 `docs/wechat-listening-pitfalls.md`，把当前 mac 分支有效事实与 Windows 旧实现参考显式分层，并同步 `.app build + smoke` / `DMG` 专项验收口径

## 3. 交叉核对与验收

- [ ] 3.1 执行文档关键词扫描，清理或重标当前步骤里的 `.exe`、`%LOCALAPPDATA%`、`taskkill`、`uiautomation`、`windows_system` 漂移项
- [ ] 3.2 按文档回跑最小开发/构建验证，并记录任何仍需依赖 GUI 专项验收或未完成 config changes 的边界
