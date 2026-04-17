# Release 维护手册

适用分支：`spike/tauri-react-refactor`

这份文档只讲当前 Windows 维护线怎么发版，以及它和 mac 分支怎么分工。  
如果你现在要维护的是 `spike/tauri-react-refactor-mac`，不要在当前分支推 `mac-v*` tag；先切到对应分支，再看那条分支里的同名文档。

## 分支分工

| release 线 | 分支 | 平台 | tag 规则 | workflow | 默认公开资产 |
| --- | --- | --- | --- | --- | --- |
| 当前分支 | `spike/tauri-react-refactor` | Windows | `v0.x.y` / `v0.x.y-rc.n` | `.github/workflows/windows-release-on-tag.yml` | `msi`、`setup.exe`、`SHA256SUMS.txt` |
| 兼容分支 | `spike/tauri-react-refactor-mac` | Apple Silicon macOS | `mac-v0.x.y` / `mac-v0.x.y-rc.n` | `.github/workflows/macos-release-on-tag.yml` | `.app` 压缩包、`SHA256SUMS.txt` |

维护约束：

- 当前分支不要推 `mac-v*` tag；那是 mac release 线的触发器。
- mac 分支也不要推 `v*` tag；Windows release 只在当前分支维护。
- GitHub Releases 仍只有一个总入口：[GitHub Releases](https://github.com/Loveyless/wechat-pc-auto/releases)。
- GitHub 页面同一时刻只会有一个 `Latest`；当前仓库接受 win/mac 双 release 页面并存。

## 当前分支的版本规则

版本入口仍是：

- `pyproject.toml`
- `desktop-shell/package.json`
- `desktop-shell/package-lock.json`
- `desktop-shell/src-tauri/Cargo.toml`
- `desktop-shell/src-tauri/Cargo.lock`
- `desktop-shell/src-tauri/tauri.conf.json`

推荐先用脚本同步版本，再决定 tag：

```bash
python scripts/sync_desktop_shell_release_version.py --channel stable --base-version 0.1.0
python scripts/sync_desktop_shell_release_version.py --channel rc --base-version 0.1.0 --rc-number 1
```

当前分支的版本语义：

- stable：
  - Python：`0.1.0`
  - Desktop bundle：`0.1.0`
  - 推荐 tag：`v0.1.0`
- rc：
  - Python：`0.1.0rc1`
  - Desktop bundle：`0.1.0-1`
  - 推荐 tag：`v0.1.0-rc.1`

注意：

- GitHub Release 标题和公开资产名里的 `<version>` 取自真实 desktop bundle 版本，不直接按 tag 去前缀计算。
- RC 时最容易看错：tag 是 `v0.1.0-rc.1`，但公开资产版本仍是 `0.1.0-1`。

## 当前分支发版步骤

1. 先同步远端，确认你在 `spike/tauri-react-refactor` 且工作区干净。
2. 用版本同步脚本更新版本入口。
3. 把版本改动先提交到分支；不要先打 tag。
4. 跑完整发布闸口：

```bash
python scripts/build_desktop_shell_sidecars.py --python python
cd desktop-shell
npm test
npm run build
npm run test:rust
npm run tauri -- build
cd ..
python scripts/smoke_desktop_shell_release.py --skip-build
```

如果你还要单独验证 Python 包的 `sdist` / `wheel`，再额外手工执行：

```bash
python -m build --sdist --wheel
```

这一步不在当前 `windows-release-on-tag.yml` 的自动发布闸口里。

5. 只有上面全部通过，才允许打 annotated tag，例如：

```bash
git tag -a v0.1.0 -m "Windows release 0.1.0"
git tag -a v0.1.0-rc.1 -m "Windows rc 0.1.0-rc.1"
```

6. 先 push 分支，再 push tag：

```bash
git push origin spike/tauri-react-refactor
git push origin v0.1.0
```

7. 到 GitHub Release 页面确认：
  - workflow runner 是 `windows-latest`
  - release 标题是 `WeChat Auto Shell Windows <version>`
  - 公开资产是 `wechat-auto-shell-<version>-windows-x64.msi`、`wechat-auto-shell-<version>-windows-x64-setup.exe` 和 `SHA256SUMS.txt`
  - tag 含 `-` 时会标成 prerelease
  - `wechat-auto-shell.exe`、`wechat-auto-backend.exe`、`group_listener_worker.exe` 只留在 workflow artifact 和本地构建目录，不作为 GitHub Release 对外下载项

## 当前分支不负责什么

- 不负责 Apple Silicon macOS 的 release tag 和 GitHub Release 页面。
- 不负责 `mac-v*` tag。
- 不负责 `.app` 压缩包或 `DMG` 交付。

## 出问题时先查什么

- 版本入口没改全，导致 tag、bundle version 和公开资产版本对不上。
- 误推了 `mac-v*` tag，或者在 mac 分支上推了 `v*` tag。
- 跳过了 `python scripts/smoke_desktop_shell_release.py --skip-build`。
- 把本地 build 目录里的 raw exe 误当成最终公开 release 资产。
