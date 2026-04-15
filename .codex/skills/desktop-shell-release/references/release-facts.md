# Release Facts

## 适用范围

当前正式桌面交付路径只有：

- `listener_app/backend_main.py`
- `desktop-shell/`

不要把历史 Tk 路径当成可发版桌面入口。

## 版本入口

- 版本同步脚本：`scripts/sync_desktop_shell_release_version.py`
- Python 包：`pyproject.toml`
- 前端包：`desktop-shell/package.json`
- npm lockfile 根包：`desktop-shell/package-lock.json`
- Rust 包：`desktop-shell/src-tauri/Cargo.toml`
- Tauri bundle 配置：`desktop-shell/src-tauri/tauri.conf.json`
- Cargo lockfile 当前仓库包：`desktop-shell/src-tauri/Cargo.lock`

脚本当前支持两种仓库内发布形态：

- `--channel stable --base-version 0.1.0`
  - Python：`0.1.0`
  - Desktop：`0.1.0`
  - 推荐 tag：`v0.1.0`
- `--channel rc --base-version 0.1.0 --rc-number 2`
  - Python：`0.1.0rc2`
  - Desktop：`0.1.0-2`
  - 推荐 tag：`v0.1.0-rc.2`

## 发布闸口

仓库文档要求的发布闸口在 `docs/desktop-shell-build.md` 和 `docs/wechat-listening-pitfalls.md`：

1. `python scripts/build_desktop_shell_sidecars.py --python python`
2. `cd desktop-shell && npm test`
3. `cd desktop-shell && npm run build`
4. `cd desktop-shell && npm run test:rust`
5. `cd desktop-shell && npm run tauri -- build`
6. `python scripts/smoke_desktop_shell_release.py --skip-build`

只有这些都过，才把桌面壳当成可交付 release。

## Tag Workflow

`.github/workflows/windows-release-on-tag.yml` 的事实：

- 触发条件：`v*` tag
- 会重复跑完整 Windows 发布闸口
- 会上传这些资产：
  - `msi`
  - `nsis setup.exe`
  - `SHA256SUMS.txt`
- `wechat-auto-shell.exe`、`wechat-auto-backend.exe`、`group_listener_worker.exe` 保留为本地 build 输出和 workflow artifact，不作为 GitHub Release 对外下载项
- `github.ref_name` 包含 `-` 时，GitHub Release 会被标成 prerelease

## 验证观察点

- `desktop-shell/src-tauri/target/release/wechat-auto-shell.exe`
- `desktop-shell/src-tauri/target/release/bundle/msi/*.msi`
- `desktop-shell/src-tauri/target/release/bundle/nsis/*-setup.exe`
- `http://127.0.0.1:8765/healthz`
- `%LOCALAPPDATA%\\com.wechatauto.shell\\logs\\desktop-shell-bootstrap.log`

## 失败时优先怀疑什么

- 版本入口没改全，导致构建产物和 tag 语义不一致
- 跳过了 sidecar build 或 release smoke
- tag 打在旧提交上，而不是带版本改动的新提交上
- 选了某个预发布版本格式，但桌面壳打包链不接受；这时应以实际构建结果为准，而不是继续硬改字符串
