## 1. Mac 窗口与会话读取适配

- [x] 1.1 将 `wechat_auto/window.py` 改为 mac-only 的微信进程、主窗口、权限与 popup 检测实现
- [ ] 1.2 将 `wechat_auto/controls.py` 改为 mac 会话列表与预览快照读取实现，并保留当前预览解析辅助函数
- [ ] 1.3 为 window/control 适配层补单元测试或 fake 覆盖，锁定 preview 解析、窗口筛选与异常降级行为

## 2. Worker 与 runtime 接通

- [ ] 2.1 更新 `listener_app/group_listener_worker.py` 以使用 mac 适配层，并补 `permission_required`、`ui_paused`、`window_lost`、`reconnecting` 等状态流
- [ ] 2.2 更新 `listener_app/backend_runtime.py` 与 `listener_app/backend_main.py`，保证现有 `/healthz`、`/api/runtime`、`/api/sessions` 消费面保持不变且能表达新状态
- [ ] 2.3 更新 `listener_app/sidebar_runtime_support.py`、`pyproject.toml` 与 `requirements.txt`，让 mac worker 依赖与启动环境和当前分支目标一致

## 3. 文档与验收

- [ ] 3.1 更新 `docs/wechat-listening-pitfalls.md`，把 mac 权限、popup 暂停、窗口恢复与受限降级写成正式事实
- [ ] 3.2 运行目标 Python 测试与最小源码态检查，并记录无法在当前会话自动完成的手工验收步骤和风险
