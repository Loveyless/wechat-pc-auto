import importlib.util
import pathlib
import sys
import types
import unittest


def _load_worker_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script_path = repo_root / "examples" / "group_listener_worker.py"
    spec = importlib.util.spec_from_file_location("group_listener_worker", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {script_path}")

    fake_wechat_auto = types.ModuleType("wechat_auto")
    fake_controls = types.ModuleType("wechat_auto.controls")
    fake_wechat_auto.WxAuto = object
    fake_wechat_auto.controls = fake_controls
    fake_controls.clear_control_cache = lambda window=None: None
    fake_controls.find_message_list = lambda window: None
    fake_controls.find_session_list = lambda window: None
    fake_controls.is_meaningful_message_text = lambda text: bool(text)
    fake_controls.normalize_session_name = lambda text: text

    saved_modules = {
        "wechat_auto": sys.modules.get("wechat_auto"),
        "wechat_auto.controls": sys.modules.get("wechat_auto.controls"),
    }
    sys.modules["wechat_auto"] = fake_wechat_auto
    sys.modules["wechat_auto.controls"] = fake_controls
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in saved_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


worker = _load_worker_module()


class GroupListenerWorkerHelpersTest(unittest.TestCase):
    def test_extract_session_preview_strips_unread_prefix(self):
        raw = "测试群\n[3条] 张三: 收到\n今天 10:00\n消息免打扰"
        self.assertEqual(worker.extract_session_preview(raw), "张三: 收到")

    def test_extract_session_unread_count(self):
        raw = "测试群\n[12条] hello\n今天 10:00"
        self.assertEqual(worker.extract_session_unread_count(raw), 12)
        self.assertEqual(worker.extract_session_unread_count("测试群\nhello\n今天 10:00"), 0)

    def test_should_emit_session_preview_accepts_unread_growth(self):
        self.assertTrue(worker.should_emit_session_preview("收到", 2, "收到", 1))
        self.assertTrue(worker.should_emit_session_preview("收到", 0, "ok", 0))
        self.assertFalse(worker.should_emit_session_preview("收到", 0, "收到", 2))

    def test_wait_for_wechat_ready_retries_until_success(self):
        class FakeWx:
            def __init__(self):
                self.calls = 0

            def load_wechat(self):
                self.calls += 1
                return self.calls >= 3

        fake_wx = FakeWx()
        events = []
        sleeps = []
        original_emit = worker.emit
        worker.emit = events.append
        try:
            ready = worker.wait_for_wechat_ready(
                fake_wx,
                retry_seconds=1.5,
                probe=False,
                reconnect=False,
                sleep_fn=sleeps.append,
            )
        finally:
            worker.emit = original_emit

        self.assertTrue(ready)
        self.assertEqual(sleeps, [1.5, 1.5])
        self.assertEqual(
            [event["state"] for event in events if event.get("type") == "status"],
            ["waiting_wechat", "waiting_wechat"],
        )

    def test_wait_for_wechat_ready_probe_stops_after_first_failure(self):
        class FakeWx:
            def load_wechat(self):
                return False

        events = []
        sleeps = []
        original_emit = worker.emit
        worker.emit = events.append
        try:
            ready = worker.wait_for_wechat_ready(
                FakeWx(),
                retry_seconds=2.0,
                probe=True,
                reconnect=True,
                sleep_fn=sleeps.append,
            )
        finally:
            worker.emit = original_emit

        self.assertFalse(ready)
        self.assertEqual(sleeps, [])
        self.assertEqual(events[0]["state"], "reconnecting")

    def test_connect_target_runtime_session_mode_skips_chat_signature_scan(self):
        class FakeWx:
            def __init__(self):
                self.window = object()

            def load_wechat(self):
                return True

        calls = []
        original_emit = worker.emit
        original_wait = worker.wait_initial_chat_signature
        original_find_target = worker.find_target_session_raw
        original_clear_cache = worker.clear_control_cache
        worker.emit = lambda event: None
        worker.wait_initial_chat_signature = (
            lambda *args, **kwargs: calls.append("chat_signature") or (1, "hello")
        )
        worker.find_target_session_raw = lambda *args, **kwargs: "测试群\n预览正文"
        worker.clear_control_cache = lambda window=None: calls.append("clear_cache")
        try:
            runtime = worker.connect_target_runtime(
                FakeWx(),
                args=types.SimpleNamespace(mode="session", probe=False),
                target_group="测试群",
                retry_seconds=1.0,
            )
        finally:
            worker.emit = original_emit
            worker.wait_initial_chat_signature = original_wait
            worker.find_target_session_raw = original_find_target
            worker.clear_control_cache = original_clear_cache

        self.assertEqual(calls, ["clear_cache"])
        self.assertIsNone(runtime["last_chat_sig"])
        self.assertEqual(runtime["last_session_preview"], "预览正文")


if __name__ == "__main__":
    unittest.main()
