import re
from typing import Optional

import uiautomation as auto


_UNREAD_RE = re.compile(r"\[\d+条\]|\d+条新消息|未读")
_TIME_ONLY_RE = re.compile(r"^(?:昨天|今天|星期[一二三四五六日天])?\s*\d{1,2}:\d{2}$")
_CONTROL_CACHE: dict[tuple[int, str], auto.Control] = {}
_WINDOW_CACHE_KEYS: list[int] = []
_CONTROL_CACHE_MAX_WINDOWS = 16


def normalize_session_name(raw_name: str) -> str:
    """提取会话项第一行作为会话名称。"""
    if not raw_name:
        return ""
    lines = [line.strip() for line in raw_name.splitlines() if line.strip()]
    if not lines:
        return ""
    name = lines[0]
    name = re.sub(r"\s*\d+[+]?\s*条新消息$", "", name)
    return name.strip()


def is_unread_session(raw_name: str) -> bool:
    if not raw_name:
        return False
    return bool(_UNREAD_RE.search(raw_name))


def is_meaningful_message_text(text: str) -> bool:
    if not text:
        return False
    s = text.strip()
    if not s:
        return False
    if _TIME_ONLY_RE.match(s):
        return False
    return True


def _iter_controls(root, control_type: str, max_nodes: int = 800):
    stack = [(root, 0)]
    visited = 0
    while stack and visited < max_nodes:
        node, depth = stack.pop()
        visited += 1
        try:
            if node.ControlTypeName == control_type:
                yield node
            if depth >= 8:
                continue
            children = node.GetChildren()
            for child in reversed(children):
                stack.append((child, depth + 1))
        except Exception:
            continue


def _exists(ctrl, timeout: float = 0.2) -> bool:
    try:
        return bool(ctrl and ctrl.Exists(timeout))
    except Exception:
        return False


def _window_cache_key(window) -> int:
    try:
        hwnd = int(window.NativeWindowHandle)
        if hwnd:
            return hwnd
    except Exception:
        pass
    return id(window)


def _remember_window_key(window_key: int):
    if window_key in _WINDOW_CACHE_KEYS:
        _WINDOW_CACHE_KEYS.remove(window_key)
    _WINDOW_CACHE_KEYS.append(window_key)
    overflow = len(_WINDOW_CACHE_KEYS) - _CONTROL_CACHE_MAX_WINDOWS
    while overflow > 0:
        expired_key = _WINDOW_CACHE_KEYS.pop(0)
        stale_keys = [key for key in _CONTROL_CACHE if key[0] == expired_key]
        for stale_key in stale_keys:
            _CONTROL_CACHE.pop(stale_key, None)
        overflow -= 1


def _get_cached_control(window, control_name: str) -> Optional[auto.Control]:
    window_key = _window_cache_key(window)
    cached = _CONTROL_CACHE.get((window_key, control_name))
    if _exists(cached):
        _remember_window_key(window_key)
        return cached
    _CONTROL_CACHE.pop((window_key, control_name), None)
    return None


def _cache_control(window, control_name: str, ctrl) -> Optional[auto.Control]:
    if not _exists(ctrl):
        return None
    window_key = _window_cache_key(window)
    _CONTROL_CACHE[(window_key, control_name)] = ctrl
    _remember_window_key(window_key)
    return ctrl


def clear_control_cache(window=None):
    if window is None:
        _CONTROL_CACHE.clear()
        _WINDOW_CACHE_KEYS.clear()
        return

    window_key = _window_cache_key(window)
    stale_keys = [key for key in _CONTROL_CACHE if key[0] == window_key]
    for stale_key in stale_keys:
        _CONTROL_CACHE.pop(stale_key, None)
    try:
        _WINDOW_CACHE_KEYS.remove(window_key)
    except ValueError:
        pass


def find_session_list(window) -> Optional[auto.Control]:
    cached = _get_cached_control(window, "session_list")
    if cached:
        return cached

    candidates = [
        window.ListControl(AutomationId="session_list"),
        window.ListControl(Name="会话"),
        window.ListControl(AutomationId="search_list"),
    ]
    for ctrl in candidates:
        cached_ctrl = _cache_control(window, "session_list", ctrl)
        if cached_ctrl:
            return cached_ctrl

    best = None
    best_score = -1
    for ctrl in _iter_controls(window, "ListControl"):
        try:
            score = 0
            aid = (ctrl.AutomationId or "").lower()
            cls = ctrl.ClassName or ""
            name = ctrl.Name or ""
            children = ctrl.GetChildren()

            if "session" in aid:
                score += 120
            if "search_list" in aid:
                score += 90
            if name == "会话":
                score += 60
            if "XTableView" in cls:
                score += 20
            score += min(len(children), 50)
            if children and "ChatSession" in (children[0].ClassName or ""):
                score += 100

            if score > best_score:
                best_score = score
                best = ctrl
        except Exception:
            continue
    return _cache_control(window, "session_list", best)


def find_message_list(window) -> Optional[auto.Control]:
    cached = _get_cached_control(window, "message_list")
    if cached:
        return cached

    candidates = [
        window.ListControl(AutomationId="chat_message_list"),
        window.ListControl(Name="消息"),
    ]
    for ctrl in candidates:
        cached_ctrl = _cache_control(window, "message_list", ctrl)
        if cached_ctrl:
            return cached_ctrl

    best = None
    best_score = -1
    for ctrl in _iter_controls(window, "ListControl"):
        try:
            score = 0
            aid = (ctrl.AutomationId or "").lower()
            cls = ctrl.ClassName or ""
            name = ctrl.Name or ""
            children = ctrl.GetChildren()

            if "message" in aid:
                score += 120
            if name == "消息":
                score += 80
            if "RecyclerListView" in cls:
                score += 40
            if children and "Chat" in (children[0].ClassName or ""):
                score += 80
            score += min(len(children), 50)

            if score > best_score:
                best_score = score
                best = ctrl
        except Exception:
            continue
    return _cache_control(window, "message_list", best)


def find_search_box(window) -> Optional[auto.Control]:
    cached = _get_cached_control(window, "search_box")
    if cached:
        return cached

    direct = [
        window.EditControl(Name="搜索"),
        window.EditControl(ClassName="mmui::XValidatorTextEdit"),
    ]
    for ctrl in direct:
        cached_ctrl = _cache_control(window, "search_box", ctrl)
        if cached_ctrl:
            return cached_ctrl

    best = None
    best_score = -1
    for ctrl in _iter_controls(window, "EditControl"):
        try:
            score = 0
            name = ctrl.Name or ""
            cls = ctrl.ClassName or ""
            aid = (ctrl.AutomationId or "").lower()

            if "搜索" in name:
                score += 120
            if "validator" in cls.lower():
                score += 70
            if "chat_input" in aid or "chatinput" in cls.lower():
                score -= 100

            if score > best_score:
                best_score = score
                best = ctrl
        except Exception:
            continue
    return _cache_control(window, "search_box", best)

