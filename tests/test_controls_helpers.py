import importlib.util
import pathlib
import sys
import types
import unittest


def _load_controls_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    module_path = repo_root / "wechat_auto" / "controls.py"
    spec = importlib.util.spec_from_file_location("wechat_auto.controls", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {module_path}")

    fake_uiautomation = types.ModuleType("uiautomation")
    fake_uiautomation.Control = object
    saved_module = sys.modules.get("uiautomation")
    sys.modules["uiautomation"] = fake_uiautomation
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if saved_module is None:
            sys.modules.pop("uiautomation", None)
        else:
            sys.modules["uiautomation"] = saved_module


controls = _load_controls_module()


class FakeControl:
    def __init__(
        self,
        *,
        exists: bool = True,
        control_type: str = "ListControl",
        automation_id: str = "",
        class_name: str = "",
        name: str = "",
        children=None,
    ):
        self._exists = exists
        self.ControlTypeName = control_type
        self.AutomationId = automation_id
        self.ClassName = class_name
        self.Name = name
        self._children = list(children or [])

    def Exists(self, timeout=0.2):
        return self._exists

    def GetChildren(self):
        return list(self._children)


class FakeWindow:
    def __init__(self, handle: int, session_controls=None):
        self.NativeWindowHandle = handle
        self._session_controls = list(session_controls or [])
        self.list_call_count = 0

    def ListControl(self, **kwargs):
        self.list_call_count += 1
        if self._session_controls:
            return self._session_controls.pop(0)
        return FakeControl(exists=False)


class ControlsHelpersTest(unittest.TestCase):
    def setUp(self):
        controls.clear_control_cache()

    def test_find_session_list_reuses_cached_control(self):
        session = FakeControl(exists=True, automation_id="session_list")
        window = FakeWindow(handle=1001, session_controls=[session])

        found_first = controls.find_session_list(window)
        calls_after_first = window.list_call_count
        found_second = controls.find_session_list(window)

        self.assertIs(found_first, session)
        self.assertIs(found_second, session)
        self.assertEqual(calls_after_first, 3)
        self.assertEqual(window.list_call_count, calls_after_first)

    def test_find_session_list_rebuilds_after_cached_control_expires(self):
        stale = FakeControl(exists=True, automation_id="session_list")
        fresh = FakeControl(exists=True, automation_id="session_list")
        window = FakeWindow(
            handle=1002,
            session_controls=[
                stale,
                FakeControl(exists=False),
                FakeControl(exists=False),
                fresh,
            ],
        )

        found_first = controls.find_session_list(window)
        stale._exists = False
        found_second = controls.find_session_list(window)

        self.assertIs(found_first, stale)
        self.assertIs(found_second, fresh)
        self.assertEqual(window.list_call_count, 6)

    def test_clear_control_cache_for_window_forces_lookup_again(self):
        session = FakeControl(exists=True, automation_id="session_list")
        window = FakeWindow(
            handle=1003,
            session_controls=[
                session,
                FakeControl(exists=False),
                FakeControl(exists=False),
                session,
            ],
        )

        controls.find_session_list(window)
        calls_after_first = window.list_call_count
        controls.clear_control_cache(window)
        controls.find_session_list(window)

        self.assertEqual(calls_after_first, 3)
        self.assertEqual(window.list_call_count, 6)


if __name__ == "__main__":
    unittest.main()
