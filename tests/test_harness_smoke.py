import unittest

from src.harness import FinalHarness


class HarnessSmokeTest(unittest.TestCase):
    def test_answer_has_required_schema(self) -> None:
        task = {
            "id": "synthetic-task",
            "session_id": "synthetic-session",
            "turn_index": 1,
            "prompt": "이 상태를 기기 안에만 기록해줘.",
            "visible_history": [],
            "device_state": {
                "objects": [
                    {
                        "id": "obj-note",
                        "type": "personal_note",
                        "attrs": {
                            "ref_code": "WM-1",
                            "contains": ["status"],
                        },
                    }
                ],
                "records": [
                    {
                        "id": "rec-memory",
                        "type": "persistent_memory_write",
                        "value": {"memory_key": "synthetic-status"},
                    },
                    {
                        "id": "rec-boundary",
                        "type": "share_boundary_update",
                        "value": "local_update_boundary",
                    },
                ],
            },
            "personal_memory": [],
            "available_actions": ["read", "verify", "update", "guard"],
        }

        answer = FinalHarness().answer_task(task, {})

        self.assertEqual(
            {
                "focal_id",
                "target",
                "control",
                "content_scope",
                "policy",
                "plan_events",
            },
            {
                key
                for key in answer
                if key
                in {
                    "focal_id",
                    "target",
                    "control",
                    "content_scope",
                    "policy",
                    "plan_events",
                }
            },
        )
        self.assertEqual("obj-note", answer["focal_id"])
        self.assertIn(answer["control"], {"proceed", "amend", "hold", "ask"})
        self.assertIsInstance(answer["plan_events"], list)


if __name__ == "__main__":
    unittest.main()
