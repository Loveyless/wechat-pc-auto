import importlib.util
import pathlib
import unittest


def _load_sidebar_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script_path = repo_root / "examples" / "sidebar_translate_listener.py"
    spec = importlib.util.spec_from_file_location("sidebar_translate_listener", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sidebar = _load_sidebar_module()


class SidebarHelpersTest(unittest.TestCase):
    def test_normalize_message_for_dedupe(self):
        raw = "  hello\u200b   world  "
        self.assertEqual(sidebar.normalize_message_for_dedupe(raw), "hello world")

    def test_cross_source_equivalent_prefix(self):
        self.assertTrue(sidebar.is_cross_source_equivalent("abc", "abc"))
        self.assertTrue(sidebar.is_cross_source_equivalent("abc def", "abc"))
        self.assertFalse(sidebar.is_cross_source_equivalent("abc", "xyz"))

    def test_validate_positive_float(self):
        self.assertEqual(sidebar.validate_positive_float("x", 0.5), 0.5)
        with self.assertRaises(RuntimeError):
            sidebar.validate_positive_float("x", 0)
        with self.assertRaises(RuntimeError):
            sidebar.validate_positive_float("x", -1)

    def test_validate_int_min(self):
        self.assertEqual(sidebar.validate_int_min("w", 300, 280), 300)
        with self.assertRaises(RuntimeError):
            sidebar.validate_int_min("w", 200, 280)

    def test_read_config_type_validation(self):
        self.assertEqual(sidebar.read_config_float({}, "interval_seconds", 1.0), 1.0)
        self.assertEqual(sidebar.read_config_int({}, "width", 420), 420)

        with self.assertRaises(RuntimeError):
            sidebar.read_config_float({"interval_seconds": "bad"}, "interval_seconds", 1.0)
        with self.assertRaises(RuntimeError):
            sidebar.read_config_int({"width": "bad"}, "width", 420)

    def test_append_message_with_limit(self):
        cache = []
        for idx in range(5):
            msg = sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="u",
                text_en=f"m{idx}",
                created_at="10:00:00",
                is_self=False,
            )
            sidebar.append_message_with_limit(cache, msg, limit=3)
        self.assertEqual(len(cache), 3)
        self.assertEqual([item.text_en for item in cache], ["m2", "m3", "m4"])

    def test_append_message_active_chat_rerenders_from_cache(self):
        ui = object.__new__(sidebar.SidebarUI)
        ui.chat_messages = {"g1": []}
        ui.unread_counts = {"g1": 0}
        ui.chat_order = ["g1"]
        ui.active_chat = "g1"
        ui.message_limit = 2
        ui._ensure_chat = lambda chat_name: None
        ui._refresh_target_list = lambda: None

        render_calls = []
        insert_calls = []
        ui._render_active_chat = lambda: render_calls.append(
            [item.text_en for item in ui.chat_messages["g1"]]
        )
        ui._insert_message = lambda msg: insert_calls.append(msg.text_en)

        for idx in range(3):
            msg = sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="u",
                text_en=f"m{idx}",
                created_at="10:00:00",
                is_self=False,
            )
            sidebar.SidebarUI.append_message(ui, msg)

        self.assertEqual(render_calls[-1], ["m1", "m2"])
        self.assertEqual(insert_calls, [])

    def test_build_worker_status_text_single_target(self):
        text = sidebar.build_worker_status_text(
            "session",
            {"g1": "waiting_wechat"},
            {"g1": "wechat not ready, retry in 10.0s"},
        )
        self.assertIn("[g1] waiting_wechat", text)
        self.assertIn("retry in 10.0s", text)

    def test_build_worker_status_text_multi_target_summary(self):
        text = sidebar.build_worker_status_text(
            "session",
            {"g1": "running", "g2": "waiting_wechat", "g3": "running"},
            {"g1": "ok", "g2": "wechat not ready", "g3": "ok"},
        )
        self.assertIn("mode=session", text)
        self.assertIn("running=2", text)
        self.assertIn("waiting_wechat=1", text)
        self.assertIn("g2=waiting_wechat: wechat not ready", text)

    def test_compute_worker_restart_delay_caps(self):
        self.assertEqual(sidebar.compute_worker_restart_delay(1), 3.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(2), 6.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(3), 12.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(4), 24.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(5), 30.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(9), 30.0)

    def test_truncate_target_label(self):
        self.assertEqual(sidebar.truncate_target_label("测试群123"), "测试群123")
        self.assertEqual(sidebar.truncate_target_label("测试群1234"), "测试群123...")
        self.assertEqual(sidebar.truncate_target_label("ABCDEFG"), "ABCDEF...")

    def test_toggle_target_panel_shortcut_returns_break(self):
        ui = object.__new__(sidebar.SidebarUI)
        calls = []
        ui.toggle_target_panel = lambda: calls.append("toggle")

        result = sidebar.SidebarUI.on_toggle_target_panel_shortcut(ui)

        self.assertEqual(calls, ["toggle"])
        self.assertEqual(result, "break")

    def test_build_worker_status_text_shows_worker_backoff(self):
        text = sidebar.build_worker_status_text(
            "session",
            {"g1": "running", "g2": "worker_backoff"},
            {"g1": "ok", "g2": "code=1, retry in 3.0s"},
        )
        self.assertIn("worker_backoff=1", text)
        self.assertIn("g2=worker_backoff: code=1, retry in 3.0s", text)


if __name__ == "__main__":
    unittest.main()
