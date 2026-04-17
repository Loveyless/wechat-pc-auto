import unittest
from unittest import mock

from wechat_auto.window import AccessibilityPermissionError, JxaAutomationError, WeChatWindow


class FakeScriptRunner:
    def __init__(
        self,
        *,
        process=None,
        windows=None,
        ax_windows=None,
        window_error=None,
        window_by_name_error=None,
        popup_payload=False,
    ):
        self.process = process
        self.windows = list(windows or [])
        self.ax_windows = ax_windows
        self.window_error = window_error
        self.window_by_name_error = window_by_name_error
        self.popup_payload = popup_payload
        self.calls = []

    def __call__(self, script: str, timeout: float):
        self.calls.append((script, timeout))
        if "const candidates =" in script:
            return self.process
        if "const windows = proc.windows();" in script:
            if "function findProcessByPid" not in script and self.window_by_name_error is not None:
                raise self.window_by_name_error
            if self.window_error is not None:
                raise self.window_error
            return list(self.windows)
        if '"AXMainWindow"' in script and '"AXFocusedWindow"' in script:
            if isinstance(self.ax_windows, Exception):
                raise self.ax_windows
            return list(self.ax_windows or [])
        if "has_popup" in script:
            if isinstance(self.popup_payload, Exception):
                raise self.popup_payload
            return (
                self.popup_payload
                if isinstance(self.popup_payload, dict)
                else {"has_popup": bool(self.popup_payload)}
            )
        if "app.activate();" in script:
            return {"ok": True}
        return None


class WindowHelpersTest(unittest.TestCase):
    def test_load_returns_waiting_wechat_when_process_missing(self):
        window = WeChatWindow(script_runner=FakeScriptRunner(process=None))
        ps_result = mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch("wechat_auto.window.subprocess.run", return_value=ps_result):
            loaded = window.load()

        self.assertFalse(loaded)
        self.assertEqual(window.get_last_state(), "waiting_wechat")
        self.assertIn("not running", window.get_last_detail())

    def test_load_returns_permission_required_when_window_query_is_blocked(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            window_error=AccessibilityPermissionError("assistive access denied"),
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertFalse(loaded)
        self.assertEqual(window.get_last_state(), "permission_required")
        self.assertIn("permission", window.get_last_detail())

    def test_load_returns_ui_paused_when_only_popup_windows_exist(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            windows=[
                {
                    "title": "右键菜单",
                    "role": "AXWindow",
                    "subrole": "AXDialog",
                    "miniaturized": False,
                    "position": [10, 10],
                    "size": [200, 100],
                }
            ],
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertFalse(loaded)
        self.assertEqual(window.get_last_state(), "ui_paused")
        self.assertIn("popup", window.get_last_detail())

    def test_load_returns_ready_when_normal_window_exists(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [1200, 900],
                },
                {
                    "title": "上下文菜单",
                    "role": "AXMenu",
                    "subrole": "",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [120, 80],
                },
            ],
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertTrue(loaded)
        self.assertEqual(window.get_last_state(), "ready")
        self.assertIsNotNone(window.get_window())
        self.assertTrue(window.get_window().Exists(0.0))

    def test_load_does_not_activate_window_by_default(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [1200, 900],
                }
            ],
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertTrue(loaded)
        self.assertFalse(any("app.activate();" in script for script, _ in runner.calls))

    def test_load_uses_ps_fallback_when_process_query_misses(self):
        runner = FakeScriptRunner(
            process=None,
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [1200, 900],
                }
            ],
        )
        window = WeChatWindow(script_runner=runner)
        ps_result = mock.Mock(returncode=0, stdout=" 1234 微信\n", stderr="")

        with mock.patch("wechat_auto.window.subprocess.run", return_value=ps_result):
            loaded = window.load()

        self.assertTrue(loaded)
        self.assertEqual(window.get_last_state(), "ready")

    def test_load_ps_fallback_skips_helper_process_before_main_process(self):
        runner = FakeScriptRunner(
            process=None,
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [1200, 900],
                }
            ],
        )
        window = WeChatWindow(script_runner=runner)
        ps_result = mock.Mock(returncode=0, stdout=" 1234 WeChatAppEx\n 456 微信\n", stderr="")

        with mock.patch("wechat_auto.window.subprocess.run", return_value=ps_result):
            loaded = window.load()

        self.assertTrue(loaded)
        self.assertEqual(window.get_last_state(), "ready")
        self.assertIsNotNone(window.get_window())
        self.assertEqual(window.get_window().process_name, "微信")
        self.assertEqual(window.get_window().pid, 456)

    def test_load_uses_pid_window_query_after_ps_fallback(self):
        runner = FakeScriptRunner(
            process=None,
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [1200, 900],
                }
            ],
            window_by_name_error=JxaAutomationError("System Events byName lookup failed"),
        )
        window = WeChatWindow(script_runner=runner)
        ps_result = mock.Mock(returncode=0, stdout=" 456 微信\n", stderr="")

        with mock.patch("wechat_auto.window.subprocess.run", return_value=ps_result):
            loaded = window.load()

        self.assertTrue(loaded)
        self.assertEqual(window.get_last_state(), "ready")
        self.assertTrue(any("function findProcessByPid" in script for script, _ in runner.calls))

    def test_restore_current_window_uses_pid_lookup_before_by_name(self):
        runner = FakeScriptRunner(
            process=None,
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": True,
                    "position": [0, 0],
                    "size": [1200, 900],
                }
            ],
            window_by_name_error=JxaAutomationError("System Events byName lookup failed"),
        )
        window = WeChatWindow(script_runner=runner)
        window._last_process_name = "微信"
        window._last_pid = 456

        restored = window.restore_current_window()

        self.assertTrue(restored)
        self.assertTrue(any("function findProcessByPid" in script for script, _ in runner.calls))

    def test_load_returns_ui_paused_when_ax_child_popup_exists(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": [0, 0],
                    "size": [1200, 900],
                }
            ],
            popup_payload=True,
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertFalse(loaded)
        self.assertEqual(window.get_last_state(), "ui_paused")

    def test_load_uses_ax_window_fallback_when_system_events_returns_empty(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            windows=[],
            ax_windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": None,
                    "size": None,
                }
            ],
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertTrue(loaded)
        self.assertEqual(window.get_last_state(), "ready")
        self.assertTrue(any('"AXFocusedWindow"' in script for script, _ in runner.calls))

    def test_load_uses_ax_window_fallback_when_system_events_raises_object_error(self):
        runner = FakeScriptRunner(
            process={"name": "WeChat", "pid": 1234},
            window_error=JxaAutomationError("execution error: Error: Error: 不能获取对象。 (-1728)"),
            ax_windows=[
                {
                    "title": "微信",
                    "role": "AXWindow",
                    "subrole": "AXStandardWindow",
                    "miniaturized": False,
                    "position": None,
                    "size": None,
                }
            ],
        )
        window = WeChatWindow(script_runner=runner)

        loaded = window.load()

        self.assertTrue(loaded)
        self.assertEqual(window.get_last_state(), "ready")

    def test_popup_query_script_skips_menu_bar_subtree(self):
        window = WeChatWindow(script_runner=FakeScriptRunner(process={"name": "WeChat", "pid": 1234}))

        script = window._build_popup_query_script(1234)

        self.assertIn("axmenubar", script)
        self.assertIn("axmenubaritem", script)
        self.assertIn("shouldSkipSubtree", script)


if __name__ == "__main__":
    unittest.main()
