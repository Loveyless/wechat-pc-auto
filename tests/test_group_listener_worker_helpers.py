import importlib.util
import pathlib
import sys
import types
import unittest


def _load_worker_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script_path = repo_root / "listener_app" / "group_listener_worker.py"
    spec = importlib.util.spec_from_file_location("group_listener_worker", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {script_path}")

    fake_wechat_auto = types.ModuleType("wechat_auto")
    fake_controls = types.ModuleType("wechat_auto.controls")
    fake_wechat_auto.WxAuto = object
    fake_wechat_auto.controls = fake_controls
    fake_controls.clear_control_cache = lambda window=None: None
    fake_controls.find_session_list = lambda window: None
    fake_controls.normalize_session_name = (
        lambda text: text.splitlines()[0].strip() if text else ""
    )

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

    def test_parse_targets_supports_multiple_sources(self):
        args = types.SimpleNamespace(
            target=["群1", "群2", "群1"],
            group="群3",
            targets_json='["群4", "群2"]',
        )
        self.assertEqual(worker.parse_targets(args), ["群1", "群2", "群3", "群4"])

    def test_build_target_state_map_reads_all_targets_from_single_snapshot(self):
        class FakeItem:
            def __init__(self, name):
                self.Name = name

        class FakeSessionList:
            def Exists(self, timeout=0.3):
                return True

            def GetChildren(self):
                return [
                    FakeItem("群1\n[2条] 张三: 你好"),
                    FakeItem("群2\n李四: ok"),
                ]

        original_find_session_list = worker.find_session_list
        worker.find_session_list = lambda window: FakeSessionList()
        try:
            state_map = worker.build_target_state_map(object(), ["群1", "群2", "群3"])
        finally:
            worker.find_session_list = original_find_session_list

        self.assertEqual(state_map["群1"]["preview"], "张三: 你好")
        self.assertEqual(state_map["群1"]["unread"], 2)
        self.assertEqual(state_map["群2"]["preview"], "李四: ok")
        self.assertEqual(state_map["群2"]["unread"], 0)
        self.assertEqual(state_map["群3"]["preview"], "")
        self.assertEqual(state_map["群3"]["unread"], 0)

    def test_should_force_focus_refresh_only_when_stalled_or_missing(self):
        self.assertFalse(
            worker.should_force_focus_refresh(
                False,
                missing_target_polls=10,
                snapshot_repeat_polls=10,
                unread_total=3,
                now_ts=30.0,
                last_focus_refresh_at=0.0,
            )
        )
        self.assertFalse(
            worker.should_force_focus_refresh(
                True,
                missing_target_polls=1,
                snapshot_repeat_polls=worker.FOCUS_REFRESH_REPEAT_THRESHOLD,
                unread_total=0,
                now_ts=30.0,
                last_focus_refresh_at=0.0,
            )
        )
        self.assertTrue(
            worker.should_force_focus_refresh(
                True,
                missing_target_polls=worker.FOCUS_REFRESH_MISSING_TARGET_THRESHOLD,
                snapshot_repeat_polls=0,
                unread_total=0,
                now_ts=30.0,
                last_focus_refresh_at=0.0,
            )
        )
        self.assertTrue(
            worker.should_force_focus_refresh(
                True,
                missing_target_polls=0,
                snapshot_repeat_polls=worker.FOCUS_REFRESH_REPEAT_THRESHOLD,
                unread_total=2,
                now_ts=30.0,
                last_focus_refresh_at=0.0,
            )
        )
        self.assertFalse(
            worker.should_force_focus_refresh(
                True,
                missing_target_polls=worker.FOCUS_REFRESH_MISSING_TARGET_THRESHOLD,
                snapshot_repeat_polls=worker.FOCUS_REFRESH_REPEAT_THRESHOLD,
                unread_total=2,
                now_ts=5.0,
                last_focus_refresh_at=1.0,
            )
        )

    def test_compute_poll_sleep_seconds_uses_full_cycle_budget(self):
        self.assertAlmostEqual(
            worker.compute_poll_sleep_seconds(0.6, 10.0, 10.2),
            0.4,
        )
        self.assertEqual(worker.compute_poll_sleep_seconds(0.6, 10.0, 10.7), 0.0)
        self.assertEqual(
            worker.compute_poll_sleep_seconds(0.05, 10.0, 10.0),
            worker.MIN_LISTEN_INTERVAL_SECONDS,
        )

    def test_configure_std_streams_for_utf8_reconfigures_supported_streams(self):
        class FakeStream:
            def __init__(self):
                self.calls = []

            def reconfigure(self, **kwargs):
                self.calls.append(kwargs)

        stdout = FakeStream()
        stderr = FakeStream()

        worker.configure_std_streams_for_utf8(stdout=stdout, stderr=stderr)

        expected = [{"encoding": "utf-8", "errors": "replace"}]
        self.assertEqual(stdout.calls, expected)
        self.assertEqual(stderr.calls, expected)


if __name__ == "__main__":
    unittest.main()
