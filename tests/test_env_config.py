from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib.env_config import DEFAULT_VALUES
from ai_agent_status_lib.env_config import load_settings
from ai_agent_status_lib.env_config import parse_agents
from ai_agent_status_lib.env_config import parse_dotenv
from ai_agent_status_lib.env_config import write_env_value


class AgentsSettingTests(unittest.TestCase):
    def test_parses_agent_lists(self) -> None:
        cases = {
            "claude,codex": ("claude", "codex"),
            "codex, claude": ("claude", "codex"),
            " Claude ": ("claude",),
            "codex": ("codex",),
            "all": ("claude", "codex"),
            "both": ("claude", "codex"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_agents(raw), expected)
        for invalid in ("", " , ", "gpt", "claude,gpt", "claude,all", None, 1):
            with self.subTest(invalid=invalid):
                self.assertIsNone(parse_agents(invalid))

    def test_resolves_agents_from_env_file_and_falls_back_on_invalid_values(self) -> None:
        warnings: list[str] = []
        settings = load_settings(
            environ={"HOME": "/home/test"},
            env_path=Path("/nonexistent/.env"),
            dotenv_values={"AI_STATUS_AGENTS": "codex"},
            legacy={},
        )
        self.assertEqual(settings.agents, ("codex",))
        self.assertEqual(settings.as_env()["AI_STATUS_AGENTS"], "codex")

        fallback = load_settings(
            environ={"HOME": "/home/test", "AI_STATUS_AGENTS": "nope"},
            env_path=Path("/nonexistent/.env"),
            dotenv_values={"AI_STATUS_AGENTS": "claude"},
            legacy={},
            diagnostic=warnings.append,
        )
        self.assertEqual(fallback.agents, ("claude",))
        self.assertTrue(any("AI_STATUS_AGENTS" in message for message in warnings))

        default = load_settings(
            environ={"HOME": "/home/test"},
            env_path=Path("/nonexistent/.env"),
            dotenv_values={},
            legacy={},
        )
        self.assertEqual(default.agents, ("claude", "codex"))

    def test_write_env_value_replaces_one_key_and_keeps_other_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# keep me\nAI_STATUS_THEME=light\nAI_STATUS_AGENTS=claude,codex\n",
                encoding="utf-8",
            )

            write_env_value(path, "AI_STATUS_AGENTS", "codex")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "# keep me\nAI_STATUS_THEME=light\nAI_STATUS_AGENTS=codex\n",
            )
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(parse_dotenv(path)["AI_STATUS_THEME"], "light")

    def test_write_env_value_appends_missing_key_and_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "existing.env"
            existing.write_text("AI_STATUS_THEME=dark\n", encoding="utf-8")
            write_env_value(existing, "AI_STATUS_AGENTS", "claude")
            self.assertEqual(parse_dotenv(existing), {"AI_STATUS_THEME": "dark", "AI_STATUS_AGENTS": "claude"})

            created = Path(directory) / "nested" / ".env"
            write_env_value(created, "AI_STATUS_AGENTS", "codex")
            self.assertEqual(parse_dotenv(created), {"AI_STATUS_AGENTS": "codex"})
            self.assertEqual(os.listdir(created.parent), [".env"])

        with self.assertRaises(ValueError):
            write_env_value(Path("/unused"), "NOT_A_KEY", "x")

    def test_bash_loader_and_template_stay_in_sync_with_python_defaults(self) -> None:
        template = parse_dotenv(ROOT / ".env.default")
        self.assertEqual(set(template), set(DEFAULT_VALUES))
        self.assertEqual(template["AI_STATUS_AGENTS"], DEFAULT_VALUES["AI_STATUS_AGENTS"])

        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("AI_STATUS_AGENTS=codex\n", encoding="utf-8")
            script = 'source "$1"; ai_status_load_env "$2"; printf %s "$AI_STATUS_AGENTS"'
            environment = {key: value for key, value in os.environ.items() if not key.startswith("AI_STATUS_")}
            result = subprocess.run(
                ["bash", "-c", script, "_", str(ROOT / "bin" / "ai-agent-status-env"), str(env_file)],
                capture_output=True, text=True, check=True, env=environment,
            )
            self.assertEqual(result.stdout, "codex")

            env_file.write_text("AI_STATUS_AGENTS=gpt\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", "-c", script, "_", str(ROOT / "bin" / "ai-agent-status-env"), str(env_file)],
                capture_output=True, text=True, check=True, env=environment,
            )
            self.assertEqual(result.stdout, "claude,codex")


if __name__ == "__main__":
    unittest.main()
