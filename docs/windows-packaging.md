# Windows 打包说明

这条 `session-only` 分支支持直接打包成 Windows 应用，但不是“一个 exe 包打天下”的花活。

正确产物是：
- 一个主程序：`wechat_sidebar.exe`
- 一个同目录 worker：`group_listener_worker.exe`

主程序负责侧边栏 UI、翻译、单 worker 管理。  
worker 负责实际监听并通过标准输出回传 JSON 事件。  
把它们拆成两个 exe，不是重复造轮子，而是为了避免把 GUI 程序硬拿去当 stdout worker，最后把事件流彻底搞死。

## 前提

- Windows 11
- Python 3.11
- 已安装依赖：`pip install -r requirements.txt`
- 已安装 PyInstaller：`python -m pip install pyinstaller`

## 构建

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1
```

如果你想要主程序保留控制台窗口，便于调试日志：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1 -Console
```

如果你确认这是本机自用包，且希望把仓库根目录 `.env.local` 一起复制到产物目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1 -CopyDotEnvLocal
```

默认不复制。这个开关是故意做成显式的，不是忘了做自动化。
原因很简单：`.env.local` 里通常放的是本机私密配置，自动塞进产物等于顺手把密钥打包出去。

脚本在真正调用 PyInstaller 之前，还会先跑一次源码态 TTS 依赖预检：

```powershell
python .\listener_app\sidebar_translate_listener.py --config .\config\listener.json --check-tts-deps
```

这一步失败就别继续打包。当前默认 `tts.provider=tencent_cloud`，没先装 `requirements.txt` 里的腾讯云 SDK 时，这里就会直接拦下。
这是对的，不是脚本多事；继续打包只会得到一个默认配置下朗读必坏的残废产物。

## 产物位置

默认输出目录：

```text
artifacts\windows-app\wechat_sidebar\
```

目录里至少会有：

```text
wechat_sidebar.exe
group_listener_worker.exe
_internal\
```

构建成功后，脚本会自动清理 `build\pyinstaller\` 中间目录和对应日志；如果顶层 `build\` 目录因此变空，也会一并删除，只保留 `artifacts\windows-app\wechat_sidebar\` 最终产物。

构建脚本现在还会额外跑一次：

```powershell
group_listener_worker.exe --help
```

这不是多余动作，而是最小冒烟验证。
PyInstaller 显示“Build completed”不代表 onefile worker 一定能正常解压和启动；`--help` 过了，至少说明打包产物本身没当场炸。

现在还会额外跑一次：

```powershell
wechat_sidebar.exe --check-tts-deps
```

这一步专门盯 TTS 朗读链路的打包回归。
原因很直接：
- 豆包 TTS 运行时依赖 `websockets`
- 腾讯云 TTS 运行时依赖 `tencentcloud` SDK
- 这两条链路当前都带函数内动态导入；如果不显式收集，PyInstaller 很容易把主程序打出来了，但朗读一触发就报 `No module named 'websockets'` 或 `No module named 'tencentcloud'`

这不是“可选优化”，而是你这次没声音的直接成因。

## 运行约束

- 只启动 `wechat_sidebar.exe`
- `group_listener_worker.exe` 必须和主程序放在同一目录
- 第一次启动时，如果主程序目录下还没有 `config\listener.json`，程序会从打包内置模板自动拷一份出来
- `.env.local` 也按主程序目录解析；如果你要给 DeepLX 配地址，就把 `.env.local` 放在 `wechat_sidebar.exe` 同目录
- 若你在打包时传了 `-CopyDotEnvLocal`，脚本会把仓库根目录 `.env.local` 复制到这里
- 日志、运行时锁、默认配置都写在主程序目录，不写回源码目录

## 最小验证

构建完成后，先确认这两个文件都在：

```powershell
Get-ChildItem .\artifacts\windows-app\wechat_sidebar\
```

再做一个最小 worker 验证：

```powershell
.\artifacts\windows-app\wechat_sidebar\group_listener_worker.exe --help
```

然后启动主程序：

```powershell
.\artifacts\windows-app\wechat_sidebar\wechat_sidebar.exe
```

## 常见问题

### 1) 主程序能启动，但立刻提示 worker 失败

先看 `group_listener_worker.exe` 是否还在主程序目录。  
没有它，主程序没法监听。

### 2) 打包后找不到配置

正常情况下，第一次启动会自动生成：

```text
config\listener.json
```

如果没有生成，优先看主程序目录是否有写权限。

### 3) 打包后 DeepLX 不生效

主程序不再读源码目录下的 `.env.local`。
要把 `.env.local` 放到 `wechat_sidebar.exe` 同目录。
如果只是本机自用包，也可以在打包时直接传 `-CopyDotEnvLocal`。

### 3.1) 打包后消息能进侧边栏，但朗读没声音

先看日志里有没有这类行：

```text
tts failed backend=doubao error=No module named 'websockets'
```

如果有，问题不是豆包鉴权，也不是你没点到正文。
是打包时没把 `websockets` 带进主程序，朗读在导入阶段就死了。

当前构建脚本已经显式加了：

```text
--collect-submodules websockets
--collect-submodules tencentcloud
```

并且在真正打包前就会先跑源码态 `--check-tts-deps` 预检。
如果这一步已经报 `No module named 'tencentcloud'`，别再怀疑 PyInstaller；先把运行时依赖装对。

并且会在构建后自动跑：

```powershell
wechat_sidebar.exe --check-tts-deps
```

这一步不过，就不要把包当成“可用产物”。

### 4) 双击 `wechat_sidebar.exe` 没反应

这通常不是 exe 没启动，而是启动阶段就自己退了。  
当前最常见原因是：

- `config\listener.json` 里 `translate.enabled=true`
- `provider=deeplx`
- 但打包目录下没有 `.env.local`
- 同时 `translate.deeplx_url` 也没直接写进配置

这种情况下，控制台版会直接报：

```text
[sidebar] invalid config: translate.enabled=true and provider=deeplx require translate.deeplx_url or DEEPLX_URL
```

修法只有两个：

- 把 `.env.local` 放到 `wechat_sidebar.exe` 同目录
- 或者打包时加 `-CopyDotEnvLocal`
- 或者直接把 `translate.deeplx_url` 写进 `config\listener.json`

不要把“点了没反应”误判成 DLL 警告导致。
这次场景里，真正的直接原因是 DeepLX 配置缺失，不是 `UIAutomationClient_VC140_*.dll` 构建告警。

### 5) 构建时看到 `UIAutomationClient_VC140_X64.dll/X86.dll required via ctypes not found`

先说结论：对当前仓库主链路，这通常是噪音，不是打包失败。

原因很简单：

- 当前仓库通过 `uiautomation` 只走 UIA 控件定位和会话读取
- `uiautomation` 里这两个 `UIAutomationClient_VC140_*` DLL 属于可选 Bitmap 辅助库
- 它们缺失时，上游库自己写明“仅 Bitmap 相关功能不可用”
- 当前 `session-only` 监听和侧边栏翻译链路不走 Bitmap / 截图 / 图像处理 API

所以这类告警不该继续被当成阻断项。
现在构建脚本会把它们降级成说明性 `NOTE`，但其他未知告警仍然保留。

只有在你后面真要引入 `uiautomation` 的 Bitmap/截图能力时，才需要认真处理这两个 DLL 或对应 VC++ 运行库。

### 6) 什么时候该用 `-CopyDotEnvLocal`

只在“本机自用打包”场景用。
如果你准备把 `artifacts\windows-app\wechat_sidebar\` 发给别人、传到网盘、传到代码托管附件，就别用这个开关。

原因不是形式主义，而是 `.env.local` 可能包含：

- `DEEPLX_URL`
- 其他后续新增的 API endpoint / token / 私有配置

一旦被复制进产物目录，这些信息就跟着产物一起走了。
需要分发时，宁可让目标机自己放 `.env.local`，也不要把你本机的环境文件烘焙进去。
