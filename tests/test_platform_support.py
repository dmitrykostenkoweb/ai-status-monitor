from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib import platform_support  # noqa: E402
from ai_agent_status_lib import process_control  # noqa: E402
from ai_agent_status_lib import window_switch  # noqa: E402
from ai_agent_status_lib.env_config import DEFAULT_VALUES  # noqa: E402
from ai_agent_status_lib.env_config import load_settings  # noqa: E402
from ai_agent_status_lib.env_config import platform_default_values  # noqa: E402
from ai_agent_status_lib.usage_limits import _claude_keychain_token  # noqa: E402


def load_installer():
    spec = importlib.util.spec_from_file_location("ai_status_installer", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PlatformDetectionTests(unittest.TestCase):
    def test_maps_sys_platform_values(self) -> None:
        self.assertEqual(platform_support.current_platform("linux"), "linux")
        self.assertEqual(platform_support.current_platform("darwin"), "macos")
        self.assertEqual(platform_support.current_platform("win32"), "windows")
        self.assertEqual(platform_support.current_platform("cygwin"), "windows")
        self.assertEqual(platform_support.current_platform("freebsd13"), "linux")

    def test_directory_defaults_per_platform(self) -> None:
        for system in ("linux", "macos"):
            with self.subTest(system=system):
                values = platform_default_values(system)
                self.assertEqual(values["AI_STATUS_CACHE_DIR"], DEFAULT_VALUES["AI_STATUS_CACHE_DIR"])
                self.assertEqual(values["AI_STATUS_DATA_DIR"], DEFAULT_VALUES["AI_STATUS_DATA_DIR"])
        windows = platform_default_values("windows")
        self.assertEqual(windows["AI_STATUS_CACHE_DIR"], "$HOME/AppData/Local/ai-cli-status-monitor/cache")
        self.assertEqual(windows["AI_STATUS_CONFIG_DIR"], "$HOME/AppData/Roaming/ai-cli-status-monitor")
        self.assertEqual(windows["AI_STATUS_TITLE"], DEFAULT_VALUES["AI_STATUS_TITLE"])
        home = Path("/h")
        self.assertEqual(platform_support.default_env_file(home, "windows"),
                         home / "AppData" / "Roaming" / "ai-cli-status-monitor" / ".env")
        self.assertEqual(platform_support.default_env_file(home, "macos"),
                         home / ".config" / "ai-cli-status-monitor" / ".env")
        self.assertEqual(platform_support.default_bin_dir(home, "linux"), home / ".local" / "bin")

    def test_home_falls_back_to_userprofile(self) -> None:
        self.assertEqual(platform_support.home_dir({"USERPROFILE": "C:/Users/me"}), Path("C:/Users/me"))
        self.assertEqual(platform_support.home_dir({"HOME": "/home/me", "USERPROFILE": "x"}), Path("/home/me"))

    def test_load_settings_uses_windows_directories(self) -> None:
        with mock.patch.object(platform_support, "PLATFORM", "windows"):
            settings = load_settings(environ={"USERPROFILE": "/users/me"}, dotenv_values={}, legacy={})
        self.assertEqual(settings.cache_dir, Path("/users/me/AppData/Local/ai-cli-status-monitor/cache"))
        self.assertEqual(settings.env_file, Path("/users/me/AppData/Roaming/ai-cli-status-monitor/.env"))


class ProcessTreeTests(unittest.TestCase):
    def test_walk_ancestors_stops_at_root_cycles_and_limit(self) -> None:
        table = {50: 40, 40: 30, 30: 1}
        self.assertEqual(platform_support.walk_ancestors(50, lambda pid: table.get(pid, 0)), [50, 40, 30])
        loop = {5: 6, 6: 5}
        self.assertEqual(platform_support.walk_ancestors(5, lambda pid: loop[pid]), [5, 6])
        chain = {pid: pid - 1 for pid in range(2, 100)}
        self.assertEqual(len(platform_support.walk_ancestors(99, lambda pid: chain[pid], limit=4)), 4)

    def test_ps_table_parses_macos_output(self) -> None:
        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 0, stdout="  1     0\n 300   1\n 301 300\nbad line\n")
        self.assertEqual(platform_support._ps_parent_table(runner), {1: 0, 300: 1, 301: 300})

    def test_current_process_chain_starts_with_self(self) -> None:
        pids = platform_support.ancestor_pids()
        self.assertEqual(pids[0], os.getpid())
        if platform_support.PLATFORM == "linux":
            self.assertIn(os.getppid(), pids)

    def test_terminal_session_key_is_stable(self) -> None:
        self.assertEqual(platform_support.terminal_session_key(), platform_support.terminal_session_key())


class CommandTests(unittest.TestCase):
    def test_sound_players_per_platform(self) -> None:
        self.assertEqual(platform_support.sound_commands("/a.mp3", "macos"), [("afplay", ["afplay", "/a.mp3"])])
        windows = platform_support.sound_commands("C:/it's.mp3", "windows")
        self.assertEqual([binary for binary, _ in windows], ["powershell", "pwsh"])
        self.assertIn("[Uri]'C:/it''s.mp3'", windows[0][1][-1])
        self.assertEqual(platform_support.sound_commands("/a.mp3", "linux")[0][0], "mpv")

    def test_missing_linux_qt_packages(self) -> None:
        self.assertEqual(platform_support.missing_linux_qt_packages(lambda _name: None), ["libxcb-cursor0"])
        self.assertEqual(platform_support.missing_linux_qt_packages(lambda name: f"lib{name}.so.0"), [])

    def test_open_command(self) -> None:
        self.assertEqual(platform_support.open_command("/tmp", "macos"), ["open", "/tmp"])
        self.assertIsNone(platform_support.open_command("/tmp", "windows"))

    def test_hook_command_keeps_posix_shape_and_quotes_windows(self) -> None:
        self.assertEqual(
            process_control.hook_command(Path("/home/u/.local/bin"), "claude", platform="linux"),
            "/home/u/.local/bin/ai-agent-status-hook --agent claude",
        )
        self.assertEqual(
            process_control.hook_command(Path("/Users/Jane Doe/.local/bin"), "codex", platform="macos"),
            "'/Users/Jane Doe/.local/bin/ai-agent-status-hook' --agent codex",
        )
        command = process_control.hook_command(
            Path("C:\\Users\\me\\AppData\\Local\\ai-cli-status-monitor\\bin"), "codex",
            platform="windows", python="C:\\Python312\\python.exe",
        )
        self.assertTrue(command.startswith('"C:/Python312/python.exe" "C:/Users/me/AppData/Local/'))
        self.assertTrue(command.endswith('/ai-agent-status-hook" --agent codex'))

    def test_script_argv(self) -> None:
        script = Path("/bin/ai-agent-status-update")
        self.assertEqual(process_control.script_argv(script, "--check", platform="linux"), [str(script), "--check"])
        self.assertEqual(
            process_control.script_argv(script, platform="windows", python="C:/py/python.exe"),
            ["C:/py/python.exe", str(script)],
        )


class WindowSwitchTests(unittest.TestCase):
    WINDOWS = [
        {"id": "0x1", "pid": 100, "title": "user@host: ~/alpha"},
        {"id": "0x2", "pid": 100, "title": "user@host: ~/beta"},
        {"id": "0x3", "pid": 200, "title": "editor - gamma"},
    ]

    def test_parse_wmctrl_listing(self) -> None:
        listing = "0x01 0 100 host title one\n0x02 0 nope host x\n0x03 -1 7 host\n"
        self.assertEqual(
            window_switch.parse_wmctrl_listing(listing),
            [{"id": "0x01", "pid": 100, "title": "title one"}, {"id": "0x03", "pid": 7, "title": ""}],
        )

    def test_choose_window_by_pid_then_title(self) -> None:
        self.assertEqual(window_switch.choose_window(self.WINDOWS, [999, 200], "x")["id"], "0x3")
        self.assertEqual(window_switch.choose_window(self.WINDOWS, [100], "beta")["id"], "0x2")
        self.assertEqual(window_switch.choose_window(self.WINDOWS, [100], "none")["id"], "0x1")
        self.assertEqual(window_switch.choose_window(self.WINDOWS, [5], "gamma")["id"], "0x3")
        self.assertIsNone(window_switch.choose_window(self.WINDOWS, [5], ""))

    def test_macos_command_passes_title_and_pids_as_arguments(self) -> None:
        command = window_switch.macos_switch_command([10, 20], "proj")
        self.assertEqual(command[0], "osascript")
        self.assertEqual(command[-3:], ["proj", "10", "20"])

    def test_macos_switch_reports_result(self) -> None:
        logs: list[str] = []
        with mock.patch.object(window_switch.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, stdout="ok\n", stderr="")) as run:
            self.assertTrue(window_switch.switch_to_session("p", "/x/p", [1, 2], platform="macos", log=logs.append))
        self.assertIn("p", run.call_args.args[0])
        with mock.patch.object(window_switch.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, stdout="none\n", stderr="")):
            self.assertFalse(window_switch.switch_to_session("p", "", [1], platform="macos", log=logs.append))
        self.assertTrue(logs)


class KeychainTests(unittest.TestCase):
    def test_reads_token_from_keychain_json(self) -> None:
        payload = json.dumps({"claudeAiOauth": {"accessToken": " tok "}})

        def runner(command, **_kwargs):
            self.assertEqual(command[:2], ["security", "find-generic-password"])
            return subprocess.CompletedProcess(command, 0, stdout=payload + "\n")
        self.assertEqual(_claude_keychain_token(runner), "tok")
        self.assertIsNone(_claude_keychain_token(lambda command, **_k: subprocess.CompletedProcess(command, 44, stdout="")))

        def missing(*_args, **_kwargs):
            raise FileNotFoundError("security")
        self.assertIsNone(_claude_keychain_token(missing))


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.installer = load_installer()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.messages: list[str] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_add_hooks_merges_once_and_backs_up(self) -> None:
        path = self.root / ".codex" / "hooks.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"other": 1, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}))
        events = ("PreToolUse", "Stop")
        self.assertTrue(self.installer.add_hooks(path, "hook --agent codex", events, codex=True, report=self.messages.append))
        data = json.loads(path.read_text())
        self.assertEqual(data["other"], 1)
        self.assertEqual(len(data["hooks"]["Stop"]), 2)
        self.assertEqual(data["hooks"]["PreToolUse"][0]["matcher"], "*")
        self.assertNotIn("matcher", data["hooks"]["Stop"][1])
        backups = list(path.parent.glob("hooks.json.bak.*"))
        self.assertEqual(len(backups), 1)

        before = path.read_text()
        self.assertTrue(self.installer.add_hooks(path, "hook --agent codex", events, codex=True, report=self.messages.append))
        self.assertEqual(path.read_text(), before)
        self.assertIn(f"✅ Hooks already installed: {path}", self.messages)

    def test_add_hooks_refuses_invalid_json(self) -> None:
        path = self.root / "settings.json"
        path.write_text("{not json")
        self.assertFalse(self.installer.add_hooks(path, "cmd", ("Stop",), report=self.messages.append))
        self.assertEqual(path.read_text(), "{not json")
        self.assertIn("Manual snippet:", self.messages)

    def test_environment_config_is_created_private_and_preserved(self) -> None:
        runtime = self.root / "config" / ".env"
        created = self.installer.install_environment_config(
            runtime, ROOT / ".env.default", self.root / "config", self.root,
            environ={"AI_STATUS_MAX_ROWS": "7"}, report=self.messages.append,
        )
        self.assertTrue(created)
        text = runtime.read_text()
        self.assertIn("AI_STATUS_MAX_ROWS=7", text)
        if os.name == "posix":
            self.assertEqual(runtime.stat().st_mode & 0o777, 0o600)
        runtime.write_text("AI_STATUS_MAX_ROWS=3\n")
        self.assertFalse(self.installer.install_environment_config(
            runtime, ROOT / ".env.default", self.root / "config", self.root, environ={}, report=self.messages.append,
        ))
        self.assertEqual(runtime.read_text(), "AI_STATUS_MAX_ROWS=3\n")

    def test_widget_python_prefers_override_then_current_interpreter(self) -> None:
        installer = self.installer
        with mock.patch.object(installer, "can_import_qt", return_value=True):
            self.assertEqual(installer.ensure_widget_python(self.root, {"AI_STATUS_WIDGET_PYTHON": "/opt/py"}), "/opt/py")
            self.assertEqual(installer.ensure_widget_python(self.root, {}), sys.executable)
        with mock.patch.object(installer, "can_import_qt", return_value=False), \
                mock.patch.object(installer.subprocess, "run") as run:
            self.assertIsNone(installer.ensure_widget_python(self.root, {"AI_STATUS_SKIP_PIP": "1"}))
            run.assert_not_called()

    def test_interpreters_are_recorded_for_the_launchers(self) -> None:
        process_control.save_interpreters(self.root, sys.executable, sys.executable)
        self.assertEqual(process_control.base_interpreter(self.root), sys.executable)
        self.assertEqual(process_control.load_interpreters(self.root)["widget"], sys.executable)
        (self.root / "interpreters.json").write_text('{"base": "/does/not/exist"}')
        self.assertEqual(process_control.base_interpreter(self.root), sys.executable)
        self.assertEqual(
            process_control.widget_argv(Path("/b"), "/py", "--demo"),
            ["/py", str(Path("/b") / "ai-agent-status-widget"), "--demo"],
        )

    def test_launch_agent_plist_escapes_arguments(self) -> None:
        plist = self.installer.launch_agent_plist(["/usr/bin/python3", "/Users/a&b/widget"], Path("/tmp/w.log"))
        self.assertIn("<string>/Users/a&amp;b/widget</string>", plist)
        self.assertIn("<key>RunAtLoad</key>", plist)


if __name__ == "__main__":
    unittest.main()
