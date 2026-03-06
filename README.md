# wechat-pc-auto

[![PyPI version](https://badge.fury.io/py/wechat-pc-auto.svg)](https://badge.fury.io/py/wechat-pc-auto)
[![Python versions](https://img.shields.io/pypi/pyversions/wechat-pc-auto.svg)](https://pypi.org/project/wechat-pc-auto/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/yourname/wechat-pc-auto?style=social)](https://github.com/yourname/wechat-pc-auto)

一个**稳定、纯 UI 自动化**的微信 PC 版消息与文件发送工具，基于 `uiautomation` 实现，无需截图识别。

支持发送文本、多文件，智能打开聊天，适配最新微信版本。

适用于：监控告警、定时汇报、日志推送、文件自动传输等场景。

## 安装

```bash
pip install wechat-pc-auto
```
## 快速开始

```python
from wechat_auto import WxAuto

wx = WxAuto()
wx.load_wechat()  # 自动激活微信

# 发送消息 + 文件到文件传输助手
wx.send_msg("自动化测试成功！\n多行消息正常显示", who="文件传输助手")
wx.send_files([
    "C:/report.pdf",
    "C:/screenshot.jpg"
], who="文件传输助手")
```
查看完整示例：examples/legacy/demo_send_to_file_helper.py

## 仅接收消息监听（不自动回复）

```python
from wechat_auto import WxAuto

def on_message(name, content, wx):
    print(f"[新消息] {name}: {content}")
    return None

wx = WxAuto()
wx.load_wechat()
wx.listen_messages(callback=on_message, interval=2)
```

如果你需要自动回复，使用：

```python
wx.listen(callback=on_message, interval=2, auto_reply=True)
```
更多历史示例见：`examples/legacy/`

## 侧边栏监听 + 英文翻译

监听目标与翻译策略由 `config/listener.json` 控制。默认仅展示英文；翻译失败时回退显示中文并附带失败原因。
当前主维护链路只聚焦“监听 + 翻译 + 展示”；发送消息、文件发送、输入框写入等能力保留兼容，但不是当前持续优化重点。
后续优化默认只围绕 `session` 模式展开；`chat` / `mixed` 仅保留兼容，不再作为主路径承接恢复能力和性能优化。
当前支持先启动本程序、后启动微信；若微信中途关闭并重新打开，主链路会继续尝试恢复监听。

```bash
python examples/sidebar_translate_listener.py --config "D:\code\wechat-pc-auto\config\listener.json"
```

接入 DeepLX：

```bash
python examples/sidebar_translate_listener.py --config "D:\code\wechat-pc-auto\config\listener.json"
```

或设置环境变量：

```bash
set DEEPLX_URL=http://127.0.0.1:1188/translate
python examples/sidebar_translate_listener.py --config "D:\code\wechat-pc-auto\config\listener.json"
```

注意：若使用环境变量，`config/listener.json` 中 `translate.deeplx_url` 需留空字符串，否则会优先使用配置值。

## 打包为 EXE（Windows）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1
```

默认输出：
- `artifacts/dist/wechat-listener/`（`--onedir`）
- 主程序：`wechat-listener.exe`
- 打包脚本会自动复制配置模板到产物旁：
  - `-OneFile`：`artifacts/dist/config/listener.json`
  - `--onedir`：`artifacts/dist/wechat-listener/config/listener.json`

可选参数：
- `-OneFile`：打成单文件 exe（启动更慢，兼容性略弱于 onedir）。
- `-Console`：保留控制台窗口，便于看日志。

运行规则：
- 配置文件默认读取 `exe` 同级目录下的 `config/listener.json`。
- 若该文件不存在，程序会从打包内置模板自动生成一份。
- 监听 worker 由主 exe 以内嵌模式拉起，不需要额外的 worker.exe。

## 注意事项

- 仅支持 Windows 系统 + 微信 PC 版
- 请确保微信已登录且未被最小化
- 首次运行可能需要管理员权限（uiautomation 需要）
- 不支持发送表情包（可发送文本中的emoji）
- 可在 `config/listener.json` 设置 `listen.load_retry_seconds`，支持“先启动监听，再打开微信”自动重试

## 项目特点

- 无需截图识别，完全基于 UI 自动化
- 适配不同微信版本窗口类名
- 智能选择最快方式进入聊天
- 真正的文件剪贴板复制（非路径文本）
- 模块化设计，易于扩展（如后续可加接收消息、自动回复等）

## 新特性（v1.1.0）
- 支持实时监听新消息
- 自动识别未读红点并点击
- 智能判断消息是否为别人发的
- 支持自定义自动回复逻辑

## v1.1.2 修复bugs
- “复制文件到剪贴板异常：argument 1: OverflowError: int too long to convert” bug
- 当微信窗口在最上层时，不再发送 Ctrl+Alt+W 激活微信窗口

## 项目结构

```
wechat_auto/
├── __init__.py  
├── core.py         # 主入口
├── window.py       # 窗口管理
├── chat.py         # 智能打开聊天
├── sender.py       # 发送消息和文件
├── clipboard.py    # 系统级文件复制
├── listener.py     # 监听消息
└── logger.py       # 日志
```

## 开源协议

MIT License - 随意使用、修改、商用均可

## 致谢

感谢 uiautomation 作者 yinkaisheng，以及所有在调试过程中提供反馈的用户。

Star 支持一下吧，让更多人用上稳定的微信自动化工具


