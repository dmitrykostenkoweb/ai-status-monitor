from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib.status_model import describe_activity
from ai_agent_status_lib.status_model import parse_activity
from ai_agent_status_lib.status_model import summarize_command


class DescribeActivityTests(unittest.TestCase):
    def test_claude_tools(self) -> None:
        cases = [
            (("PreToolUse", "Read", {"file_path": "/home/u/p/README.md"}), ("read", "README.md", "pre")),
            (("PreToolUse", "Edit", {"file_path": "/home/u/p/bin/stickers.py"}), ("edit", "stickers.py", "pre")),
            (("PostToolUse", "Write", {"file_path": "/tmp/x/notes.txt"}), ("edit", "notes.txt", "post")),
            (("PreToolUse", "Bash", {"command": "pytest -q", "description": "Run the sticker tests"}),
             ("command", "Run the sticker tests", "pre")),
            (("PreToolUse", "Bash", {"command": "git push origin main"}), ("command", "git push", "pre")),
            (("PreToolUse", "Grep", {"pattern": "KLIPY_.*"}), ("search", "KLIPY_.*", "pre")),
            (("PreToolUse", "WebFetch", {"url": "https://docs.klipy.com/x?key=1"}), ("web", "docs.klipy.com", "pre")),
            (("PreToolUse", "WebSearch", {"query": "gtk input shape"}), ("web", "gtk input shape", "pre")),
            (("PreToolUse", "Task", {"description": "Find hook docs", "subagent_type": "Explore"}),
             ("agent", "Find hook docs", "pre")),
            (("PreToolUse", "TodoWrite", {"todos": []}), ("plan", "", "pre")),
        ]
        for (event, tool, tool_input), expected in cases:
            with self.subTest(tool=tool):
                activity = describe_activity(event, tool, {"tool_input": tool_input})
                self.assertIsNotNone(activity)
                self.assertEqual((activity["type"], activity["target"], activity["phase"]), expected)

    def test_permission_and_codex_payloads(self) -> None:
        self.assertEqual(
            describe_activity("Notification", "", {"message": "Claude needs your permission to use Bash"})["target"],
            "Bash",
        )
        self.assertIsNone(describe_activity("Notification", "", {"message": "Claude is waiting for your input"}))
        self.assertEqual(
            describe_activity("PermissionRequest", "Bash", {"tool_input": {"command": "rm -rf build"}})["target"],
            "rm",
        )
        codex_shell = describe_activity("PreToolUse", "functions.exec_command",
                                        {"tool_input": {"command": ["bash", "-lc", "npm test -- --watch"]}})
        self.assertEqual((codex_shell["type"], codex_shell["target"]), ("command", "npm test"))
        patch = describe_activity("PreToolUse", "apply_patch",
                                  {"tool_input": {"input": "*** Begin Patch\n*** Update File: src/app.py\n@@"}})
        self.assertEqual((patch["type"], patch["target"]), ("edit", "app.py"))

    def test_never_leaks_prompts_arguments_or_full_paths(self) -> None:
        self.assertIsNone(describe_activity("UserPromptSubmit", "", {"prompt": "my secret plan"}))
        self.assertEqual(summarize_command("API_TOKEN=s3cret curl -H 'Authorization: x' https://a"), "curl")
        self.assertEqual(summarize_command("mysql -u root -pHunter2 db"), "mysql")
        self.assertEqual(summarize_command("sudo apt install foo"), "apt install")
        self.assertEqual(summarize_command(["git", "commit", "-m", "private message"]), "git commit")
        read = describe_activity("PreToolUse", "Read", {"tool_input": {"file_path": "/home/dima/secret/plan.md"}})
        self.assertNotIn("dima", read["target"])
        long = describe_activity("PreToolUse", "Bash", {"tool_input": {"description": "x" * 80}})
        self.assertLessEqual(len(long["target"]), 40)

    def test_malformed_input_is_ignored(self) -> None:
        for payload in ({}, {"tool_input": "not json"}, {"tool_input": None}, {"tool_input": {"file_path": 3}}):
            with self.subTest(payload=payload):
                describe_activity("PreToolUse", "Read", payload)  # must not raise
        self.assertIsNone(describe_activity("PreToolUse", "SomethingNew", {"tool_input": {}}))

    def test_parse_activity_validates_status_file_values(self) -> None:
        self.assertEqual(parse_activity({"type": "edit", "target": "a.py", "phase": "post"}),
                         {"type": "edit", "target": "a.py", "phase": "post"})
        for bad in (None, "edit", {"type": "hack", "target": "x"}, {"type": "edit", "target": 3},
                    {"type": "edit", "target": "x", "phase": "later"}):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_activity(bad))


if __name__ == "__main__":
    unittest.main()
