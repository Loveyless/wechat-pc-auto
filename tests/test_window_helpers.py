import unittest

from wechat_auto.window import AccessibilityPermissionError, WeChatWindow


class FakeScriptRunner:
    def __init__(self, *, process=None, windows=None, window_error=None):
        self.process = process
        self.windows = list(windows or [])
        self.window_error = window_error
        self.calls = []

    def __call__(self, script: str, timeout: float):
        self.calls.append((script, timeout))
        if "const candidates =" in script:
            return self.process
        if "const windows = proc.windows();" in script:
            if self.window_error is not None:
                raise self.window_error
            return list(self.windows)
        if "app.activate();" in script:
            return {"ok": True}
        return None


class WindowHelpersTest(unittest.TestCase):
    def test_load_returns_waiting_wechat_when_process_missing(self):
        window = WeChatWindow(script_runner=FakeScriptRunner(process=None))

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


if __name__ == "__main__":
    unittest.main()
