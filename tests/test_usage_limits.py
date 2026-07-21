from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib.usage_limits import build_usage_groups
from ai_agent_status_lib.usage_limits import build_usage_rows
from ai_agent_status_lib.usage_limits import collect_codex_usage
from ai_agent_status_lib.usage_limits import collect_claude_usage
from ai_agent_status_lib.usage_limits import demo_usage_states
from ai_agent_status_lib.usage_limits import load_usage_cache
from ai_agent_status_lib.usage_limits import parse_claude_usage
from ai_agent_status_lib.usage_limits import parse_codex_rate_limits
from ai_agent_status_lib.usage_limits import refresh_usage
from ai_agent_status_lib.usage_limits import UsageSourceError
from ai_agent_status_lib.usage_limits import usage_color_class
from ai_agent_status_lib.usage_limits import write_usage_cache


FETCHED_AT = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)


class UsageParserTests(unittest.TestCase):
    def test_parses_claude_five_hour_and_weekly_windows(self) -> None:
        payload = {
            "five_hour": {
                "utilization": 76.0,
                "resets_at": "2026-07-21T12:50:00+00:00",
            },
            "seven_day": {
                "utilization": 43,
                "resets_at": "2026-07-24T09:00:00Z",
            },
        }

        limits = parse_claude_usage(payload, fetched_at=FETCHED_AT)

        self.assertEqual([limit["window"] for limit in limits], ["5h", "Weekly"])
        self.assertEqual([limit["used_percent"] for limit in limits], [76.0, 43.0])
        self.assertEqual(limits[0]["provider"], "claude")
        self.assertEqual(limits[0]["fetched_at"], "2026-07-21T10:00:00+00:00")
        self.assertEqual(limits[1]["resets_at"], "2026-07-24T09:00:00+00:00")
        self.assertFalse(limits[0]["stale"])

    def test_parses_codex_weekly_window_without_assuming_primary(self) -> None:
        rate_limits = {
            "primary": {"used_percent": 12, "window_minutes": 300, "resets_at": 1784628000},
            "secondary": {"used_percent": 5.0, "window_minutes": 10080, "resets_at": 1785142107},
        }

        limits = parse_codex_rate_limits(rate_limits, fetched_at=FETCHED_AT)

        self.assertEqual(len(limits), 1)
        self.assertEqual(limits[0]["provider"], "codex")
        self.assertEqual(limits[0]["window"], "Weekly")
        self.assertEqual(limits[0]["used_percent"], 5.0)
        self.assertEqual(limits[0]["resets_at"], "2026-07-27T08:48:27+00:00")

    def test_rejects_invalid_percentages_and_reset_timestamps(self) -> None:
        claude = parse_claude_usage(
            {
                "five_hour": {"utilization": 101, "resets_at": "2026-07-21T12:50:00Z"},
                "seven_day": {"utilization": 40, "resets_at": "not-a-date"},
            },
            fetched_at=FETCHED_AT,
        )
        codex = parse_codex_rate_limits(
            {"primary": {"used_percent": -1, "window_minutes": 10080, "resets_at": 1785142107}},
            fetched_at=FETCHED_AT,
        )

        self.assertEqual(claude, [])
        self.assertEqual(codex, [])


class CodexCollectorTests(unittest.TestCase):
    def codex_event(self, used_percent: float = 5.0) -> dict[str, object]:
        return {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {
                    "primary": {
                        "used_percent": used_percent,
                        "window_minutes": 10080,
                        "resets_at": 1785142107,
                    }
                },
            },
        }

    def test_skips_malformed_newest_lines_and_finds_valid_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory)
            session = codex_home / "sessions" / "2026" / "07" / "21" / "rollout.jsonl"
            session.parent.mkdir(parents=True)
            session.write_text(
                json.dumps(self.codex_event())
                + "\n"
                + json.dumps({"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {}}})
                + "\n{malformed\n",
                encoding="utf-8",
            )

            limits = collect_codex_usage(codex_home, fetched_at=FETCHED_AT)

        self.assertEqual(len(limits), 1)
        self.assertEqual(limits[0]["used_percent"], 5.0)

    def test_bounds_recent_files_and_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory)
            sessions = codex_home / "sessions"
            sessions.mkdir()
            older = sessions / "older.jsonl"
            older.write_text(json.dumps(self.codex_event(9.0)) + "\n", encoding="utf-8")
            newer = sessions / "newer.jsonl"
            newer.write_text("{}\n{}\n", encoding="utf-8")
            os.utime(older, (100, 100))
            os.utime(newer, (200, 200))

            one_file = collect_codex_usage(codex_home, fetched_at=FETCHED_AT, max_files=1)
            two_files = collect_codex_usage(codex_home, fetched_at=FETCHED_AT, max_files=2, max_lines=1)

        self.assertEqual(one_file, [])
        self.assertEqual(two_files[0]["used_percent"], 9.0)


class FakeHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        return self.payload


class ClaudeCollectorTests(unittest.TestCase):
    def test_missing_credentials_fail_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / ".credentials.json"

            with self.assertRaisesRegex(UsageSourceError, "Claude usage unavailable"):
                collect_claude_usage(credentials, fetched_at=FETCHED_AT)

            self.assertFalse(credentials.exists())

    def test_timeout_error_does_not_expose_access_token(self) -> None:
        secret = "oauth-secret-must-not-leak"

        def timeout_opener(_request: object, *, timeout: float) -> FakeHttpResponse:
            self.assertEqual(timeout, 4.0)
            raise TimeoutError("simulated timeout")

        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / ".credentials.json"
            credentials.write_text(
                json.dumps({"claudeAiOauth": {"accessToken": secret, "refreshToken": "unused"}}),
                encoding="utf-8",
            )

            with self.assertRaises(UsageSourceError) as caught:
                collect_claude_usage(credentials, fetched_at=FETCHED_AT, opener=timeout_opener)

        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(str(caught.exception), "Claude usage unavailable")

    def test_collects_valid_usage_through_injected_http_transport(self) -> None:
        response_payload = {
            "five_hour": {
                "utilization": 76.0,
                "resets_at": "2026-07-21T12:50:00+00:00",
                "limit_dollars": None,
                "used_dollars": None,
                "remaining_dollars": None,
            },
            "seven_day": {
                "utilization": 43.0,
                "resets_at": "2026-07-24T09:00:00+00:00",
                "limit_dollars": None,
                "used_dollars": None,
                "remaining_dollars": None,
            },
            "seven_day_opus": None,
            "seven_day_sonnet": None,
        }

        def opener(request: object, *, timeout: float) -> FakeHttpResponse:
            self.assertEqual(timeout, 4.0)
            self.assertIn("Bearer oauth-test-token", str(getattr(request, "headers", {})))
            return FakeHttpResponse(json.dumps(response_payload).encode())

        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / ".credentials.json"
            credentials.write_text(
                json.dumps({"claudeAiOauth": {"accessToken": "oauth-test-token"}}),
                encoding="utf-8",
            )

            limits = collect_claude_usage(credentials, fetched_at=FETCHED_AT, opener=opener)

        self.assertEqual([limit["used_percent"] for limit in limits], [76.0, 43.0])

    def test_malformed_response_fails_with_generic_error(self) -> None:
        def opener(_request: object, *, timeout: float) -> FakeHttpResponse:
            return FakeHttpResponse(b"not-json")

        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / ".credentials.json"
            credentials.write_text(
                json.dumps({"claudeAiOauth": {"accessToken": "oauth-test-token"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(UsageSourceError, "^Claude usage unavailable$"):
                collect_claude_usage(credentials, fetched_at=FETCHED_AT, opener=opener)


class UsageCacheTests(unittest.TestCase):
    def limit(self, provider: str, window: str, reset: str, used: float = 25.0) -> dict[str, object]:
        return {
            "provider": provider,
            "window": window,
            "used_percent": used,
            "resets_at": reset,
            "fetched_at": "2026-07-21T10:00:00+00:00",
            "stale": False,
        }

    def test_cache_round_trip_marks_unexpired_records_stale_and_drops_expired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "usage_limits.json"
            write_usage_cache(
                cache,
                {
                    "claude": [
                        self.limit("claude", "5h", "2026-07-21T12:00:00+00:00"),
                        self.limit("claude", "Weekly", "2026-07-20T12:00:00+00:00"),
                    ],
                    "codex": [self.limit("codex", "Weekly", "2026-07-27T08:48:27+00:00")],
                },
            )

            loaded = load_usage_cache(cache, now=FETCHED_AT)

        self.assertEqual([item["window"] for item in loaded["claude"]], ["5h"])
        self.assertTrue(loaded["claude"][0]["stale"])
        self.assertTrue(loaded["codex"][0]["stale"])

    def test_cache_serializes_only_normalized_non_secret_fields(self) -> None:
        secret = "oauth-secret-must-not-leak"
        limit = self.limit("claude", "5h", "2026-07-21T12:00:00+00:00")
        limit["access_token"] = secret
        limit["raw_response"] = {"credential": secret}

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "usage_limits.json"
            write_usage_cache(cache, {"claude": [limit]})
            raw = cache.read_text(encoding="utf-8")

        self.assertNotIn(secret, raw)
        self.assertNotIn("access_token", raw)
        self.assertNotIn("raw_response", raw)

    def test_failed_atomic_replace_preserves_previous_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "usage_limits.json"
            old = self.limit("codex", "Weekly", "2026-07-27T08:48:27+00:00", used=5.0)
            new = self.limit("codex", "Weekly", "2026-07-27T08:48:27+00:00", used=99.0)
            write_usage_cache(cache, {"codex": [old]})
            before = cache.read_text(encoding="utf-8")

            def interrupted_replace(_source: object, _target: object) -> None:
                raise OSError("simulated interruption")

            with self.assertRaises(OSError):
                write_usage_cache(cache, {"codex": [new]}, replacer=interrupted_replace)

            self.assertEqual(cache.read_text(encoding="utf-8"), before)
            self.assertEqual(list(cache.parent.glob(".usage_limits.json.*")), [])


class UsageRefreshTests(unittest.TestCase):
    def limit(self, provider: str, window: str, used: float) -> dict[str, object]:
        return {
            "provider": provider,
            "window": window,
            "used_percent": used,
            "resets_at": "2026-07-27T08:48:27+00:00",
            "fetched_at": "2026-07-21T10:00:00+00:00",
            "stale": False,
        }

    def test_provider_failure_keeps_cache_while_other_provider_updates(self) -> None:
        def failed_claude() -> list[dict[str, object]]:
            raise UsageSourceError("Claude usage unavailable")

        def successful_codex() -> list[dict[str, object]]:
            return [self.limit("codex", "Weekly", 7.0)]

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "usage_limits.json"
            write_usage_cache(cache, {"claude": [self.limit("claude", "5h", 20.0)]})

            snapshot = refresh_usage(
                cache,
                now=FETCHED_AT,
                claude_collector=failed_claude,
                codex_collector=successful_codex,
            )

            persisted = load_usage_cache(cache, now=FETCHED_AT)

        self.assertEqual(snapshot["providers"]["claude"][0]["used_percent"], 20.0)
        self.assertTrue(snapshot["providers"]["claude"][0]["stale"])
        self.assertEqual(snapshot["providers"]["codex"][0]["used_percent"], 7.0)
        self.assertFalse(snapshot["providers"]["codex"][0]["stale"])
        self.assertEqual(snapshot["errors"], {"claude": "unavailable"})
        self.assertEqual(persisted["codex"][0]["used_percent"], 7.0)

    def test_targeted_refresh_preserves_other_provider(self) -> None:
        calls: list[str] = []

        def successful_claude() -> list[dict[str, object]]:
            calls.append("claude")
            return [self.limit("claude", "5h", 33.0)]

        def unexpected_codex() -> list[dict[str, object]]:
            calls.append("codex")
            raise AssertionError("Codex collector must not run")

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "usage_limits.json"
            write_usage_cache(
                cache,
                {
                    "claude": [self.limit("claude", "5h", 20.0)],
                    "codex": [self.limit("codex", "Weekly", 7.0)],
                },
            )

            snapshot = refresh_usage(
                cache,
                now=FETCHED_AT,
                provider_keys=("claude",),
                claude_collector=successful_claude,
                codex_collector=unexpected_codex,
            )
            persisted = load_usage_cache(cache, now=FETCHED_AT)

        self.assertEqual(calls, ["claude"])
        self.assertEqual(snapshot["providers"]["claude"][0]["used_percent"], 33.0)
        self.assertEqual(snapshot["providers"]["codex"][0]["used_percent"], 7.0)
        self.assertEqual(snapshot["errors"], {})
        self.assertEqual(persisted["codex"][0]["used_percent"], 7.0)

    def test_empty_provider_result_becomes_unavailable_without_raw_error(self) -> None:
        snapshot = refresh_usage(
            Path("/nonexistent/cache/path/that/is/not/written"),
            now=FETCHED_AT,
            claude_collector=lambda: [],
            codex_collector=lambda: [],
            persist=False,
        )

        self.assertEqual(snapshot["providers"], {"claude": [], "codex": []})
        self.assertEqual(snapshot["errors"], {"claude": "unavailable", "codex": "unavailable"})


class UsagePresentationTests(unittest.TestCase):
    def limit(
        self,
        provider: str,
        window: str,
        used: float,
        reset: str,
        *,
        stale: bool = False,
    ) -> dict[str, object]:
        return {
            "provider": provider,
            "window": window,
            "used_percent": used,
            "resets_at": reset,
            "fetched_at": "2026-07-21T10:00:00+00:00",
            "stale": stale,
        }

    def test_builds_ordered_rows_with_local_reset_labels(self) -> None:
        local_zone = timezone(timedelta(hours=2))
        snapshot = {
            "providers": {
                "claude": [
                    self.limit("claude", "Weekly", 43, "2026-07-24T09:00:00+00:00"),
                    self.limit("claude", "5h", 76, "2026-07-21T12:50:00+00:00"),
                ],
                "codex": [self.limit("codex", "Weekly", 5, "2026-07-27T08:48:27+00:00", stale=True)],
            },
            "errors": {"codex": "unavailable"},
        }

        rows = build_usage_rows(snapshot, now=FETCHED_AT, local_timezone=local_zone)

        self.assertEqual([(row["provider"], row["window"]) for row in rows], [
            ("Claude", "5h"),
            ("Claude", "Weekly"),
            ("Codex", "Weekly"),
        ])
        self.assertEqual(rows[0]["percent_text"], "76%")
        self.assertEqual(rows[0]["reset_text"], "resets 14:50")
        self.assertEqual(rows[1]["reset_text"], "resets Fri 11:00")
        self.assertEqual(rows[2]["state"], "stale")

    def test_assigns_progress_color_at_threshold_boundaries(self) -> None:
        cases = (
            (0, "usage-green"),
            (59.9, "usage-green"),
            (60, "usage-orange"),
            (84.9, "usage-orange"),
            (85, "usage-red"),
            (100, "usage-red"),
        )

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(usage_color_class(value), expected)
        for invalid in (None, "60", True):
            with self.subTest(invalid=invalid):
                self.assertEqual(usage_color_class(invalid), "")

    def test_groups_provider_rows_for_branded_layout(self) -> None:
        snapshot = {
            "providers": {
                "claude": [
                    self.limit("claude", "Weekly", 43, "2026-07-24T09:00:00+00:00"),
                    self.limit("claude", "5h", 76, "2026-07-21T12:50:00+00:00"),
                ],
                "codex": [self.limit("codex", "Weekly", 85, "2026-07-27T08:48:27+00:00")],
            },
            "errors": {},
        }

        groups = build_usage_groups(snapshot, now=FETCHED_AT, local_timezone=timezone.utc)

        self.assertEqual([group["provider_key"] for group in groups], ["claude", "codex"])
        self.assertEqual([row["window"] for row in groups[0]["rows"]], ["5h", "Weekly"])
        self.assertEqual([row["color_class"] for row in groups[0]["rows"]], [
            "usage-orange",
            "usage-green",
        ])
        self.assertEqual(groups[1]["rows"][0]["color_class"], "usage-red")

    def test_missing_provider_creates_unavailable_row(self) -> None:
        rows = build_usage_rows(
            {"providers": {"claude": [], "codex": []}, "errors": {}},
            now=FETCHED_AT,
            local_timezone=timezone.utc,
        )

        self.assertEqual([(row["provider"], row["state"]) for row in rows], [
            ("Claude", "unavailable"),
            ("Codex", "unavailable"),
        ])

    def test_demo_states_cover_current_refreshing_stale_partial_and_unavailable(self) -> None:
        states = demo_usage_states(FETCHED_AT)

        self.assertEqual([state["name"] for state in states], [
            "current",
            "refreshing",
            "stale",
            "partial",
            "unavailable",
        ])
        self.assertFalse(states[0]["refreshing"])
        self.assertTrue(states[1]["refreshing"])
        self.assertTrue(states[2]["snapshot"]["providers"]["claude"][0]["stale"])
        self.assertEqual(states[3]["snapshot"]["providers"]["claude"], [])
        self.assertEqual(states[4]["snapshot"]["providers"], {"claude": [], "codex": []})


if __name__ == "__main__":
    unittest.main()
