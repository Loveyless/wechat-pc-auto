import unittest

from listener_app.runtime_engine import ListenerRuntime
from listener_app.runtime_models import (
    CAPTURE_LEVEL_FULL,
    CAPTURE_LEVEL_PREVIEW,
    build_message,
    infer_capture_level,
)
from listener_app.runtime_store import RuntimeStore


class RuntimeModelsTest(unittest.TestCase):
    def test_infer_capture_level(self):
        self.assertEqual(infer_capture_level("session_preview"), CAPTURE_LEVEL_PREVIEW)
        self.assertEqual(infer_capture_level("chat"), CAPTURE_LEVEL_FULL)

    def test_build_message_uses_preview_capture_level(self):
        msg = build_message(
            message_id="m1",
            session_name="测试群",
            created_at="10:00",
            source="session_preview",
            text_original="hello",
        )
        self.assertEqual(msg.session_id, "测试群")
        self.assertEqual(msg.capture_level, CAPTURE_LEVEL_PREVIEW)
        self.assertEqual(msg.text_display, "hello")


class RuntimeStoreTest(unittest.TestCase):
    def test_snapshot_contains_translation_and_tts_state(self):
        store = RuntimeStore(message_limit=2)
        store.set_translation_state(enabled=True, provider="deeplx", pending_count=1)
        store.set_tts_state(auto_read_enabled=True, provider="system", available=True)
        snapshot = store.snapshot()
        self.assertEqual(snapshot["translation"]["provider"], "deeplx")
        self.assertEqual(snapshot["translation"]["pending_count"], 1)
        self.assertEqual(snapshot["tts"]["provider"], "system")
        self.assertTrue(snapshot["tts"]["available"])

    def test_append_message_creates_session(self):
        store = RuntimeStore(message_limit=2)
        msg = build_message(
            message_id="m1",
            session_name="测试群",
            created_at="10:00",
            source="session_preview",
            text_original="hello",
        )
        store.append_message(msg)
        sessions = store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_name"], "测试群")
        self.assertTrue(sessions[0]["has_preview_only_messages"])

    def test_replace_message_updates_existing_message(self):
        store = RuntimeStore(message_limit=2)
        original = build_message(
            message_id="m1",
            session_name="测试群",
            created_at="10:00",
            source="session_preview",
            text_original="hello",
        )
        store.append_message(original)
        updated = build_message(
            message_id="m1",
            session_name="测试群",
            created_at="10:01",
            source="chat",
            text_original="hello",
            text_translated="HELLO",
            text_display="HELLO",
        )
        self.assertTrue(store.replace_message(updated))
        messages = store.get_session_messages("测试群")
        self.assertEqual(messages[0]["text_translated"], "HELLO")
        self.assertEqual(messages[0]["capture_level"], CAPTURE_LEVEL_FULL)

    def test_replace_message_after_overflow_uses_updated_index(self):
        store = RuntimeStore(message_limit=2)
        for message_id, text in (("m1", "one"), ("m2", "two"), ("m3", "three")):
            store.append_message(
                build_message(
                    message_id=message_id,
                    session_name="测试群",
                    created_at="10:00",
                    source="session_preview",
                    text_original=text,
                )
            )
        updated = build_message(
            message_id="m2",
            session_name="测试群",
            created_at="10:01",
            source="chat",
            text_original="two",
            text_translated="TWO",
            text_display="TWO",
        )
        self.assertTrue(store.replace_message(updated))
        messages = store.get_session_messages("测试群")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["message_id"], "m2")
        self.assertEqual(messages[0]["text_display"], "TWO")


class RuntimeEngineTest(unittest.TestCase):
    def test_record_preview_message_publishes_events(self):
        runtime = ListenerRuntime(message_limit=10)
        q = runtime.subscribe()
        runtime.record_preview_message(session_name="测试群", text="hello", created_at="10:00")
        first = q.get(timeout=1)
        second = q.get(timeout=1)
        self.assertEqual(first.event_type, "message.created")
        self.assertEqual(second.event_type, "session.upsert")

    def test_set_runtime_options_updates_translation_and_tts_state(self):
        runtime = ListenerRuntime(message_limit=10)
        runtime.set_runtime_options(
            translate_enabled=True,
            translate_provider="deeplx",
            tts_auto_read_enabled=True,
            tts_provider="system",
            tts_available=True,
        )
        snapshot = runtime.snapshot()
        self.assertTrue(snapshot["translation"]["enabled"])
        self.assertEqual(snapshot["translation"]["provider"], "deeplx")
        self.assertTrue(snapshot["tts"]["auto_read_enabled"])
        self.assertEqual(snapshot["tts"]["provider"], "system")

    def test_sync_session_snapshot_updates_order_and_preview_contract(self):
        runtime = ListenerRuntime(message_limit=10)
        runtime.set_runtime_contract(
            monitor_scope="all_sessions",
            message_fidelity="preview_only",
        )
        runtime.sync_session_snapshot(
            [
                {
                    "session_name": "群2",
                    "latest_preview": "b",
                    "unread_count": 2,
                    "updated_at": "10:01",
                    "preview_only": True,
                },
                {
                    "session_name": "群1",
                    "latest_preview": "a",
                    "unread_count": 1,
                    "updated_at": "10:00",
                    "preview_only": True,
                },
            ]
        )
        snapshot = runtime.snapshot()
        self.assertEqual(snapshot["runtime"]["monitor_scope"], "all_sessions")
        self.assertEqual(snapshot["runtime"]["message_fidelity"], "preview_only")
        self.assertEqual([item["session_name"] for item in snapshot["sessions"]], ["群2", "群1"])


if __name__ == "__main__":
    unittest.main()
