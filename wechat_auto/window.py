from __future__ import annotations

import json
import subprocess
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Callable

from .logger import log

WECHAT_PROCESS_CANDIDATES = ("WeChat", "Weixin")
JXA_TIMEOUT_SECONDS = 4.0
POLL_RETRY_INTERVAL_SECONDS = 0.05
POPUP_ROLE_TOKENS = ("menu", "popover", "sheet", "dialog")
POPUP_SUBROLE_TOKENS = ("dialog", "systemdialog", "floating")


class JxaAutomationError(RuntimeError):
    """JXA 调用失败。"""


class AccessibilityPermissionError(JxaAutomationError):
    """当前进程没有辅助功能权限。"""


def _is_accessibility_error(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    return (
        "-25211" in text
        or "assistive access" in text
        or "辅助访问" in text
        or "辅助功能" in text
        or "not allowed assistive access" in text
    )


def _run_jxa_json(script: str, timeout: float = JXA_TIMEOUT_SECONDS) -> Any:
    try:
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise JxaAutomationError(f"osascript timeout after {timeout:.1f}s") from exc

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0:
        detail = stderr or stdout or f"osascript failed with exit={completed.returncode}"
        if _is_accessibility_error(detail):
            raise AccessibilityPermissionError(detail)
        raise JxaAutomationError(detail)

    if not stdout:
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise JxaAutomationError(f"invalid JXA JSON payload: {stdout[:200]}") from exc


@dataclass
class WindowCandidate:
    process_name: str
    pid: int
    title: str
    role: str
    subrole: str
    miniaturized: bool
    position: list[int] | None
    size: list[int] | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, process_name: str, pid: int) -> "WindowCandidate":
        title = str(payload.get("title") or "").strip()
        role = str(payload.get("role") or "").strip()
        subrole = str(payload.get("subrole") or "").strip()
        raw_position = payload.get("position")
        raw_size = payload.get("size")
        position = [int(v) for v in raw_position] if isinstance(raw_position, list) else None
        size = [int(v) for v in raw_size] if isinstance(raw_size, list) else None
        return cls(
            process_name=process_name,
            pid=int(pid),
            title=title,
            role=role,
            subrole=subrole,
            miniaturized=bool(payload.get("miniaturized")),
            position=position,
            size=size,
        )

    @property
    def area(self) -> int:
        if not self.size or len(self.size) != 2:
            return 0
        return max(0, int(self.size[0])) * max(0, int(self.size[1]))


class MacWeChatWindow:
    """给现有 worker 保持近似 UIA 风格的窗口句柄外观。"""

    def __init__(self, manager: "WeChatWindow", candidate: WindowCandidate):
        self._manager = manager
        self._process_name = candidate.process_name
        self._pid = candidate.pid
        self._title = candidate.title

    def Exists(self, timeout: float = 0.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            if self._manager.current_main_window() is not None:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(POLL_RETRY_INTERVAL_SECONDS)

    def SwitchToThisWindow(self) -> bool:
        return self._manager.activate_current_window()

    def IsMinimize(self) -> bool:
        current = self._manager.current_main_window()
        return bool(current and current.miniaturized)

    def Restore(self) -> bool:
        return self._manager.restore_current_window()

    def has_popup_or_menu(self) -> bool:
        return self._manager.has_popup_or_menu()

    def run_jxa(self, script: str, timeout: float = JXA_TIMEOUT_SECONDS) -> Any:
        return self._manager.run_jxa(script, timeout=timeout)

    @property
    def process_name(self) -> str:
        return self._process_name

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def title(self) -> str:
        return self._title


class WeChatWindow:
    def __init__(
        self,
        *,
        script_runner: Callable[[str, float], Any] | None = None,
    ):
        self.window: MacWeChatWindow | None = None
        self._script_runner = script_runner or _run_jxa_json
        self._last_state = "idle"
        self._last_detail = ""
        self._last_process_name = ""
        self._last_pid = 0

    def run_jxa(self, script: str, *, timeout: float = JXA_TIMEOUT_SECONDS) -> Any:
        return self._script_runner(script, timeout)

    def _set_status(self, state: str, detail: str) -> None:
        self._last_state = str(state or "").strip() or "unknown"
        self._last_detail = str(detail or "").strip()

    def get_last_state(self) -> str:
        return self._last_state

    def get_last_detail(self) -> str:
        return self._last_detail

    def _build_process_query_script(self) -> str:
        process_names = ", ".join(json.dumps(name) for name in WECHAT_PROCESS_CANDIDATES)
        return textwrap.dedent(
            f"""
            const systemEvents = Application("System Events");
            const candidates = [{process_names}];
            function readProcess(name) {{
              try {{
                const proc = systemEvents.processes.byName(name);
                const pid = Number(proc.unixId());
                const procName = String(proc.name() || "");
                if (!procName || !pid) {{
                  return null;
                }}
                return {{ name: procName, pid: pid }};
              }} catch (error) {{
                return null;
              }}
            }}
            let found = null;
            for (const name of candidates) {{
              const current = readProcess(name);
              if (current) {{
                found = current;
                break;
              }}
            }}
            JSON.stringify(found);
            """
        ).strip()

    def _build_window_query_script(self, process_name: str) -> str:
        quoted_name = json.dumps(process_name)
        return textwrap.dedent(
            f"""
            const systemEvents = Application("System Events");
            const proc = systemEvents.processes.byName({quoted_name});
            const windows = proc.windows();
            const items = windows.map(window => {{
              let position = null;
              let size = null;
              try {{
                position = window.position();
              }} catch (error) {{
                position = null;
              }}
              try {{
                size = window.size();
              }} catch (error) {{
                size = null;
              }}
              return {{
                title: String(window.name() || ""),
                role: String(window.role() || ""),
                subrole: String(window.subrole() || ""),
                miniaturized: Boolean(window.miniaturized()),
                position: position,
                size: size,
              }};
            }});
            JSON.stringify(items);
            """
        ).strip()

    def _build_activate_script(self, process_name: str) -> str:
        quoted_name = json.dumps(process_name)
        return textwrap.dedent(
            f"""
            const app = Application({quoted_name});
            app.activate();
            JSON.stringify({{ ok: true }});
            """
        ).strip()

    def _build_restore_script(self, process_name: str) -> str:
        quoted_name = json.dumps(process_name)
        return textwrap.dedent(
            f"""
            const systemEvents = Application("System Events");
            const proc = systemEvents.processes.byName({quoted_name});
            const windows = proc.windows();
            if (windows.length > 0) {{
              try {{
                windows[0].miniaturized = false;
              }} catch (error) {{
                // 有些 WeChat 版本不暴露 miniaturized，可忽略并直接 activate。
              }}
            }}
            const app = Application({quoted_name});
            app.activate();
            JSON.stringify({{ ok: true }});
            """
        ).strip()

    def _query_process_info(self) -> dict[str, Any] | None:
        payload = self.run_jxa(self._build_process_query_script())
        if not isinstance(payload, dict):
            return None
        name = str(payload.get("name") or "").strip()
        pid = int(payload.get("pid") or 0)
        if not name or pid <= 0:
            return None
        return {"name": name, "pid": pid}

    def _query_window_candidates(self, process_name: str, pid: int) -> list[WindowCandidate]:
        payload = self.run_jxa(self._build_window_query_script(process_name))
        if not isinstance(payload, list):
            return []
        return [
            WindowCandidate.from_payload(item, process_name=process_name, pid=pid)
            for item in payload
            if isinstance(item, dict)
        ]

    def _is_popup_candidate(self, candidate: WindowCandidate) -> bool:
        role = candidate.role.strip().lower()
        subrole = candidate.subrole.strip().lower()
        title = candidate.title.strip().lower()
        if any(token in role for token in POPUP_ROLE_TOKENS):
            return True
        if any(token in subrole for token in POPUP_SUBROLE_TOKENS):
            return True
        return any(token in title for token in ("菜单", "弹窗", "popup"))

    def _candidate_score(self, candidate: WindowCandidate) -> int:
        score = 0
        if not self._is_popup_candidate(candidate):
            score += 200
        title_lower = candidate.title.lower()
        if "微信" in candidate.title or "wechat" in title_lower or "weixin" in title_lower:
            score += 60
        if candidate.subrole.strip().lower() in ("", "axstandardwindow", "standard window"):
            score += 40
        if not candidate.miniaturized:
            score += 30
        score += min(candidate.area // 20000, 120)
        return score

    def _pick_main_window(self, candidates: list[WindowCandidate]) -> WindowCandidate | None:
        normal_windows = [item for item in candidates if not self._is_popup_candidate(item)]
        if not normal_windows:
            return None
        return max(normal_windows, key=self._candidate_score)

    def current_main_window(self) -> WindowCandidate | None:
        process = self._query_process_info()
        if not process:
            return None
        process_name = str(process["name"])
        pid = int(process["pid"])
        candidates = self._query_window_candidates(process_name, pid)
        return self._pick_main_window(candidates)

    def has_popup_or_menu(self) -> bool:
        process = self._query_process_info()
        if not process:
            return False
        process_name = str(process["name"])
        pid = int(process["pid"])
        candidates = self._query_window_candidates(process_name, pid)
        return any(self._is_popup_candidate(item) for item in candidates)

    def activate_current_window(self) -> bool:
        process_name = self._last_process_name or ""
        if not process_name:
            process = self._query_process_info()
            if not process:
                return False
            process_name = str(process["name"])
        try:
            self.run_jxa(self._build_activate_script(process_name))
            return True
        except JxaAutomationError:
            return False

    def restore_current_window(self) -> bool:
        process_name = self._last_process_name or ""
        if not process_name:
            process = self._query_process_info()
            if not process:
                return False
            process_name = str(process["name"])
        try:
            self.run_jxa(self._build_restore_script(process_name))
            return True
        except JxaAutomationError:
            return False

    def load(self) -> bool:
        log("尝试定位微信进程与主窗口...")
        self.window = None

        process = self._query_process_info()
        if not process:
            self._last_process_name = ""
            self._last_pid = 0
            self._set_status("waiting_wechat", "wechat process not running")
            log("未发现 WeChat 进程，等待微信启动")
            return False

        self._last_process_name = str(process["name"])
        self._last_pid = int(process["pid"])

        try:
            candidates = self._query_window_candidates(self._last_process_name, self._last_pid)
        except AccessibilityPermissionError:
            detail = "accessibility permission required for WeChat window inspection"
            self._set_status("permission_required", detail)
            log("缺少辅助功能权限，无法读取微信窗口")
            return False
        except JxaAutomationError as exc:
            detail = f"failed to query WeChat windows: {exc}"
            self._set_status("window_query_failed", detail)
            log(f"读取微信窗口失败：{exc}")
            return False

        if not candidates:
            detail = "wechat process is running but no readable window is available"
            self._set_status("waiting_wechat", detail)
            log("微信进程存在，但当前没有可读主窗口")
            return False

        picked = self._pick_main_window(candidates)
        if picked is None:
            detail = "wechat popup/menu/dialog blocks the main window"
            self._set_status("ui_paused", detail)
            log("检测到微信弹窗或菜单遮挡主窗口，暂不进入监听")
            return False

        self.window = MacWeChatWindow(self, picked)
        self._set_status("ready", f"connected to {self._last_process_name} pid={self._last_pid}")
        self.activate_current_window()
        log(f"已连接微信主窗口 pid={self._last_pid} title={picked.title!r}")
        return True

    def get_current_sessions(self) -> list[str]:
        """保留只读会话查询入口，具体读取逻辑在 controls.py 中实现。"""
        if not self.window or not self.window.Exists():
            log("微信窗口不存在，无法获取会话列表")
            return []

        from .controls import find_session_list, normalize_session_name

        session_list = find_session_list(self.window)
        if not session_list or not session_list.Exists(0.5):
            log("未找到会话列表控件")
            return []

        names: list[str] = []
        for item in session_list.GetChildren()[:30]:
            raw = getattr(item, "Name", "") or ""
            name = normalize_session_name(raw)
            if name and name not in names:
                names.append(name)
        log(f"获取到 {len(names)} 个会话")
        return names

    def get_window(self) -> MacWeChatWindow | None:
        return self.window
