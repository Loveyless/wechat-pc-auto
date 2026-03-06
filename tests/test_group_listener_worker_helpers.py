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


if __name__ == "__main__":
    unittest.main()
