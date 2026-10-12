from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib import uninstaller  # noqa: E402
from ai_agent_status_lib import windows_app  # noqa: E402

HOOK = "/home/u/.local/bin/ai-agent-status-hook --agent claude"


class StripHooksTests(unittest.TestCase):
    def test_removes_only_our_handlers_and_empty_groups(self) -> None:
        data = {
            "model": "x",
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "notify-send done"}]},
                    {"hooks": [{"type": "command", "command": HOOK}]},
                ],
                "PreToolUse": [
                    {"matcher": "*", "hooks": [{"type": "command", "command": HOOK},
                                               {"type": "command", "command": "other"}]},
                ],
                "Notification": [{"hooks": [{"type": "command", "command": HOOK}]}],
            },
        }
        self.assertEqual(uninstaller.strip_hooks(data), 3)
        self.assertEqual(data["model"], "x")
        self.assertEqual(data["hooks"]["Stop"], [{"hooks": [{"type": "command", "command": "notify-send done"}]}])
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"], [{"type": "command", "command": "other"}])
        self.assertNotIn("Notification", data["hooks"])

    def test_leaves_malformed_data_alone(self) -> None:
        for data in ([], {"hooks": []}, {"hooks": {"Stop": "x"}}, {"hooks": {"Stop": ["x", {"hooks": "y"}]}}):
            with self.subTest(data=data):
                before = json.dumps(data)
                self.assertEqual(uninstaller.strip_hooks(data), 0)
                self.assertEqual(json.dumps(data), before)


class UninstallRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.bin = self.home / ".local" / "bin"
        self.cache = self.home / ".cache" / "ai-cli-status-monitor"
        self.config = self.home / ".config" / "ai-cli-status-monitor"
        self.data = self.home / ".local" / "share" / "ai-cli-status-monitor"
        for directory in (self.bin / "ai_agent_status_lib", self.cache / "statuses", self.config, self.data / "venv"):
            directory.mkdir(parents=True)
        for name in ("ai-agent-status-hook", "ai-agent-status-widget", "ai-agent-status-uninstall"):
            (self.bin / name).write_text("#")
        (self.bin / "someone-elses-tool").write_text("#")
        (self.config / ".env").write_text("AI_STATUS_MAX_ROWS=5\n")
        self.settings = self.home / ".claude" / "settings.json"
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": HOOK}]}]}}))
        self.messages: list[str] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_uninstall(self, purge: bool = False, cache: Path | None = None) -> None:
        with mock.patch.object(uninstaller.platform_support, "PLATFORM", "linux"):
            uninstaller.run(self.home, self.bin, cache or self.cache, self.config, self.data,
                            purge=purge, report=self.messages.append)

    def test_removes_our_files_and_hooks_and_keeps_settings(self) -> None:
        self.run_uninstall()
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())
        self.assertFalse((self.bin / "ai_agent_status_lib").exists())
        self.assertEqual(sorted(path.name for path in self.bin.iterdir()), ["someone-elses-tool"])
        self.assertTrue((self.config / ".env").exists())
        self.assertEqual(json.loads(self.settings.read_text()), {"hooks": {}})
        self.assertEqual(len(list(self.settings.parent.glob("settings.json.bak.*"))), 1)

    def test_purge_deletes_settings(self) -> None:
        self.run_uninstall(purge=True)
        self.assertFalse(self.config.exists())

    def test_wsl_bridge_never_deletes_the_windows_cache(self) -> None:
        windows_cache = Path("/mnt/c/Users/p/AppData/Local/ai-cli-status-monitor/cache")
        targets = uninstaller.plan(self.home, self.bin, windows_cache, self.config, self.data, purge=False)
        self.assertNotIn(windows_cache, targets)
        self.assertIn(self.data, targets)


class WindowsAppTests(unittest.TestCase):
    def test_shortcut_starts_the_widget_without_a_console(self) -> None:
        bin_dir = Path("C:/Users/p/AppData/Local/ai-cli-status-monitor/bin")
        with mock.patch.object(windows_app.platform_support, "gui_python", return_value="C:/Python/pythonw.exe"):
            values = windows_app.shortcut_values(bin_dir, Path("C:/data/ai-cli-status-widget.ico"), "C:/Python/python.exe")
        self.assertEqual(values["AI_STATUS_LNK_NAME"], "AI Status Monitor.lnk")
        self.assertEqual(values["AI_STATUS_LNK_TARGET"], "C:/Python/pythonw.exe")
        self.assertEqual(values["AI_STATUS_LNK_ARGS"], f'"{bin_dir / "ai-agent-status-widget-start"}"')
        self.assertTrue(values["AI_STATUS_LNK_ICON"].endswith("ai-cli-status-widget.ico,0"))

    def test_uninstall_entry_uses_a_console_python(self) -> None:
        values = windows_app.uninstall_values(Path("C:/bin"), Path("C:/data"), Path("C:/data/i.ico"),
                                              "C:/Python/pythonw.exe", "0.5.2")
        self.assertEqual(values["DisplayName"], "AI Status Monitor")
        self.assertEqual(values["DisplayVersion"], "0.5.2")
        self.assertTrue(values["UninstallString"].startswith('"C:/Python/python.exe" '))
        self.assertTrue(values["UninstallString"].endswith('ai-agent-status-uninstall"'))
        self.assertEqual(values["QuietUninstallString"], values["UninstallString"] + " --yes")
        self.assertEqual((values["NoModify"], values["NoRepair"]), (1, 1))

    def test_install_reports_created_shortcuts_and_survives_failures(self) -> None:
        seen: dict[str, str] = {}

        def runner(command, **kwargs):
            seen.update(kwargs["env"])
            self.assertEqual(command[0], "powershell.exe")
            return subprocess.CompletedProcess(command, 0, stdout="C:\\Start\\AI Status Monitor.lnk\r\n")

        notes = windows_app.install(Path("C:/bin"), Path("C:/data"), "C:/Python/python.exe", "0.5.2", runner)
        self.assertIn("C:\\Start\\AI Status Monitor.lnk", notes[0])
        self.assertEqual(seen["AI_STATUS_LNK_NAME"], "AI Status Monitor.lnk")

        def missing(command, **_kwargs):
            raise FileNotFoundError(command[0])

        notes = windows_app.install(Path("C:/bin"), Path("C:/data"), "C:/Python/python.exe", "0.5.2", missing)
        self.assertIn("Could not create", notes[0])
        self.assertEqual(windows_app.uninstall(missing)[:1], [])


if __name__ == "__main__":
    unittest.main()
