# Windows EXE 打包说明

## 目标
- 将 `examples/sidebar_translate_listener.py` 打包为可分发的 Windows `exe`。
- 保留当前双进程架构（侧边栏 + worker），但 worker 由同一个 exe 以内嵌模式启动。

## 前提
- Windows 10/11
- Python 3.8+
- 已安装项目依赖（`requirements.txt`）

## 构建命令
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1
```

可选参数：
- `-OneFile`：打包为单文件 exe。
- `-Console`：保留控制台窗口（便于诊断）。
- `-PythonExe <path>`：指定 Python 可执行文件。

示例：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1 -OneFile -Console
```

## 输出路径
- 默认输出目录：`artifacts/dist/wechat-listener/`
- 主程序：`wechat-listener.exe`
- 构建脚本会自动在输出目录旁生成 `config/listener.json`（以及 `config/listener.md` 说明）：
  - `-OneFile`：`artifacts/dist/config/listener.json`
  - 默认 onedir：`artifacts/dist/wechat-listener/config/listener.json`

## 配置与运行
- 程序默认读取：`<exe目录>\config\listener.json`
- 若该配置不存在，程序会从内置模板自动生成。
- `.env.local` 建议与 exe 放同级目录，用于注入 `DEEPLX_URL` 等本地敏感配置。

## 兼容性说明
- 打包模式下，主进程通过 `--worker-mode` 拉起内嵌 worker，不依赖 `group_listener_worker.py` 文件路径。
- worker/主进程通信仍使用 stdout JSON 行协议，行为与源码运行保持一致。

## 常见问题
- 启动后提示找不到微信：
  - 确认微信 PC 已安装并可启动；
  - 可通过 `listen.load_retry_seconds` 开启持续重试（默认 10 秒）。
- 翻译报 401/403：
  - 检查 `DEEPLX_URL` 是否有效；
  - 建议把 key 放 `.env.local`，不要硬编码到 `listener.json`。
