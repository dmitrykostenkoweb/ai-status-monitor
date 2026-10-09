from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib import stickers
from ai_agent_status_lib.status_model import STATUS_KINDS


GIF_BYTES = b"GIF89a" + b"\x00" * 32


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def klipy_item(slug: str, *, ad: bool = False, sizes: tuple[str, ...] = ("sm", "md")) -> dict[str, object]:
    item: dict[str, object] = {
        "slug": slug,
        "file": {size: {"gif": {"url": f"https://static.klipy.com/{slug}-{size}.gif"}} for size in sizes},
    }
    if ad:
        item["type"] = "ad"
    return item


def search_payload(*items: dict[str, object]) -> bytes:
    return json.dumps({"result": True, "data": {"data": list(items)}}).encode()


class StickerMappingTests(unittest.TestCase):
    def test_every_mapped_kind_exists_and_maps_to_a_known_sticker(self) -> None:
        for kind, key in stickers.KIND_TO_STICKER.items():
            with self.subTest(kind=kind):
                self.assertIn(kind, STATUS_KINDS)
                self.assertIn(key, stickers.STICKER_KEYS)
        for key in stickers.STICKER_KEYS:
            self.assertIn(key, stickers.STICKER_COLORS)
            self.assertTrue(stickers.DEFAULT_BUBBLES[key])
            self.assertTrue(stickers.DEFAULT_QUERIES[key])

    def test_bubble_texts_and_queries_are_short_unique_and_plentiful(self) -> None:
        for key in stickers.STICKER_KEYS:
            with self.subTest(key=key):
                bubbles = stickers.DEFAULT_BUBBLES[key]
                queries = stickers.DEFAULT_QUERIES[key]
                self.assertGreaterEqual(len(bubbles), 8)
                self.assertEqual(len(set(bubbles)), len(bubbles))
                self.assertEqual(len(set(queries)), len(queries))
                # The bubble wraps at ~18 chars per line; keep every line to at most 3 lines.
                self.assertTrue(all(len(text) <= 40 for text in bubbles), [t for t in bubbles if len(t) > 40])

    def test_polish_example_overrides_every_bubble(self) -> None:
        bubbles, queries = stickers.load_sticker_texts(ROOT / "examples" / "stickers.pl.json")
        for key in stickers.STICKER_KEYS:
            with self.subTest(key=key):
                self.assertNotEqual(bubbles[key], stickers.DEFAULT_BUBBLES[key])
                self.assertTrue(all(len(text) <= 40 for text in bubbles[key]))
        self.assertEqual(queries, stickers.DEFAULT_QUERIES)
        self.assertIn("Dima? Halo?", bubbles["waiting"])

    def test_sticker_for_kind(self) -> None:
        self.assertEqual(stickers.sticker_for_kind("thinking"), "analyzing")
        self.assertEqual(stickers.sticker_for_kind("command"), "coding")
        self.assertEqual(stickers.sticker_for_kind("waiting"), "waiting")
        self.assertIsNone(stickers.sticker_for_kind("neutral"))
        self.assertIsNone(stickers.sticker_for_kind("stale"))
        self.assertIsNone(stickers.sticker_for_kind(None))

    def test_sticker_texts_accept_valid_overrides_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stickers.json"
            self.assertEqual(stickers.load_sticker_texts(path)[0], stickers.DEFAULT_BUBBLES)

            path.write_text(json.dumps({
                "bubbles": {"waiting": ["Dima? Halo?", "", 3], "nope": ["x"], "done": []},
                "queries": {"coding": [" hacker "]},
            }), encoding="utf-8")
            bubbles, queries = stickers.load_sticker_texts(path)
            self.assertEqual(bubbles["waiting"], ("Dima? Halo?",))
            self.assertEqual(bubbles["done"], stickers.DEFAULT_BUBBLES["done"])
            self.assertNotIn("nope", bubbles)
            self.assertEqual(queries["coding"], ("hacker",))

            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(stickers.load_sticker_texts(path)[1], stickers.DEFAULT_QUERIES)

    def test_image_magic_bytes(self) -> None:
        self.assertTrue(stickers.is_image_file(GIF_BYTES[:16]))
        self.assertTrue(stickers.is_image_file(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8))
        self.assertTrue(stickers.is_image_file(b"RIFF\x00\x00\x00\x00WEBPVP8 "))
        self.assertFalse(stickers.is_image_file(b"<html><body>"))


class LocalPoolTests(unittest.TestCase):
    def test_shuffle_bag_deals_everything_before_repeating(self) -> None:
        bag = stickers.ShuffleBag(random.Random(1))
        items = ("a", "b", "c", "d", "e")
        dealt = [bag.draw("coding", items) for _ in range(50)]
        for start in range(0, 50, 5):
            self.assertEqual(sorted(dealt[start:start + 5]), list(items))
        self.assertTrue(all(first != second for first, second in zip(dealt, dealt[1:])))
        self.assertEqual([bag.draw("solo", ["only"]) for _ in range(3)], ["only"] * 3)
        self.assertIsNone(bag.draw("empty", []))
        self.assertEqual(bag.draw("coding", ("new",)), "new", "a changed list starts a new bag")

    def test_recent_memory_avoids_everything_shown_lately(self) -> None:
        memory = stickers.RecentMemory(size=10, rng=random.Random(2))
        items = [str(index) for index in range(10)]
        first_round = [memory.pick(items) for _ in range(10)]
        self.assertEqual(sorted(first_round), sorted(items), "all ten before any repeat")
        self.assertEqual(memory.pick(items), first_round[0], "then the one shown longest ago")
        self.assertIsNone(memory.pick([]))

    def test_local_pool_lists_images_and_tolerates_missing_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gifs = Path(directory)
            folder = gifs / "done"
            folder.mkdir()
            for name in ("b.gif", "a.PNG", "notes.txt"):
                (folder / name).write_bytes(GIF_BYTES)
            (folder / "nested.gif").mkdir()

            self.assertEqual([path.name for path in stickers.local_pool(gifs, "done")], ["a.PNG", "b.gif"])
            self.assertEqual(stickers.local_pool(gifs, "waiting"), [])


class KlipyTests(unittest.TestCase):
    def test_parses_results_skipping_ads_and_preferring_small_gifs(self) -> None:
        payload = json.loads(search_payload(
            klipy_item("cat", sizes=("hd", "sm", "xs")),
            klipy_item("sponsored", ad=True),
            klipy_item("big", sizes=("hd",)),
            {"slug": "broken", "file": {"sm": {"gif": {"url": "http://insecure.example/x.gif"}}}},
            "junk",
        ))

        results = stickers.parse_klipy_search(payload)

        self.assertEqual([result.id for result in results], ["cat", "big"])
        self.assertEqual(results[0].url, "https://static.klipy.com/cat-sm.gif")
        self.assertEqual(results[1].url, "https://static.klipy.com/big-hd.gif")
        self.assertEqual(stickers.parse_klipy_search({"data": None}), [])
        self.assertEqual(stickers.parse_klipy_search([]), [])

    def make_client(self, directory: str, responses: dict[str, bytes], calls: list[str], now: list[float]) -> stickers.KlipyClient:
        def opener(request: object, *, timeout: float) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            calls.append(url)
            for fragment, body in responses.items():
                if fragment in url:
                    return FakeResponse(body)
            raise OSError("unexpected url")

        return stickers.KlipyClient(
            "secret key/1",
            "customer-1",
            opener=opener,
            clock=lambda: now[0],
        )

    def test_search_results_are_cached_until_the_ttl_expires(self) -> None:
        calls: list[str] = []
        now = [1000.0]
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(directory, {"/gifs/search": search_payload(klipy_item("a"))}, calls, now)

            self.assertEqual([r.id for r in client.search("thinking")], ["a"])
            client.search("thinking")
            self.assertEqual(len(calls), 1)
            self.assertIn("/api/v1/secret%20key%2F1/gifs/search?", calls[0])
            self.assertIn("q=thinking", calls[0])
            self.assertIn("customer_id=customer-1", calls[0])
            self.assertIn("format_filter=gif", calls[0])
            self.assertIn("content_filter=high", calls[0])
            self.assertIn("per_page=50", calls[0])
            self.assertIn("page=1", calls[0])
            client.search("thinking", page=2)
            self.assertIn("page=2", calls[-1])
            self.assertEqual(len(calls), 2)
            calls.pop()

            now[0] += stickers.KLIPY_RESULTS_TTL_SECONDS + 1
            client.search("thinking")
            self.assertEqual(len(calls), 2)

    def test_hourly_search_budget_falls_back_to_cached_results(self) -> None:
        calls: list[str] = []
        now = [5000.0]
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(directory, {"/gifs/search": search_payload(klipy_item("a"), klipy_item("b"))},
                                      calls, now)
            for index in range(stickers.KLIPY_SEARCHES_PER_HOUR):
                client.search(f"phrase {index}")
            self.assertFalse(client.can_search())
            self.assertEqual(sorted(r.id for r in client.cached_for(["phrase 0", "phrase 7"])), ["a", "b"])
            now[0] += 3601
            self.assertTrue(client.can_search(), "the budget is a sliding one-hour window")

    def test_search_failure_never_leaks_the_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(directory, {}, [], [0.0])
            with self.assertRaises(RuntimeError) as caught:
                client.search("thinking")
            self.assertNotIn("secret", str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)

    def test_loads_media_into_memory_only_and_validates_it(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(directory, {"a-sm.gif": GIF_BYTES, "bad-sm.gif": b"<html>"}, calls, [0.0])
            good = stickers.KlipyResult("a", "https://static.klipy.com/a-sm.gif")

            self.assertEqual(client.load(good), GIF_BYTES)
            self.assertEqual(client.load(good), GIF_BYTES)
            self.assertEqual(len(calls), 2, "media is loaded from KLIPY each time, never from a local copy")
            self.assertEqual(list(Path(directory).iterdir()), [], "nothing is written to disk")

            with self.assertRaises(RuntimeError):
                client.load(stickers.KlipyResult("bad", "https://static.klipy.com/bad-sm.gif"))
            with self.assertRaises(RuntimeError):
                client.load(stickers.KlipyResult("evil", "https://evil.example/klipy.com.gif"))
            self.assertEqual(len(calls), 3, "a non-KLIPY URL is rejected before any request")

    def test_only_klipy_media_hosts_are_accepted(self) -> None:
        for url in ("https://static.klipy.com/x.gif", "https://static2.klipy.com/x.gif", "https://klipy.com/x.gif"):
            self.assertTrue(stickers.is_klipy_media_url(url), url)
        for url in ("http://static.klipy.com/x.gif", "https://klipy.com.evil.example/x.gif",
                    "https://notklipy.com/x.gif", "not a url"):
            self.assertFalse(stickers.is_klipy_media_url(url), url)

    def test_parses_the_documented_search_response(self) -> None:
        documented = {
            "result": True,
            "data": {
                "data": [{
                    "id": 8041071659142944, "slug": "hello-hi-662", "title": "Hello", "type": "gif",
                    "file": {
                        "hd": {"gif": {"url": "https://static.klipy.com/ii/x/14/af/um0L4dFH.gif", "width": 498}},
                        "sm": {"gif": {"url": "https://static.klipy.com/ii/x/14/af/y6iepZM7.gif", "width": 220}},
                        "xs": {"gif": {"url": "https://static.klipy.com/ii/x/14/af/A4bPjSsj.gif", "width": 90}},
                    },
                }],
                "current_page": 1, "per_page": 24, "has_next": True,
            },
        }
        self.assertEqual(stickers.parse_klipy_search(documented), [
            stickers.KlipyResult("hello-hi-662", "https://static.klipy.com/ii/x/14/af/y6iepZM7.gif"),
        ])

    def test_customer_id_is_created_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cfg" / "klipy_customer_id"
            first = stickers.load_customer_id(path)
            self.assertEqual(len(first), 32)
            self.assertEqual(stickers.load_customer_id(path), first)


class KlipyKeyCheckTests(unittest.TestCase):
    def check(self, outcome: object) -> str:
        import urllib.error

        def opener(request: object, *, timeout: float) -> FakeResponse:
            if isinstance(outcome, Exception):
                raise outcome
            return FakeResponse(outcome)  # type: ignore[arg-type]

        return stickers.verify_klipy_key("secret-key", opener=opener)

    def test_reports_each_outcome_without_leaking_the_key(self) -> None:
        import io
        import urllib.error

        def http_error(code: int) -> urllib.error.HTTPError:
            return urllib.error.HTTPError("https://api.klipy.com/x", code, "x", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]

        self.assertEqual(self.check(json.dumps({"result": True, "data": {"data": []}}).encode()), "ok")
        self.assertEqual(self.check(json.dumps({"result": False}).encode()), "invalid")
        self.assertEqual(self.check(http_error(404)), "invalid")
        self.assertEqual(self.check(http_error(401)), "invalid")
        self.assertEqual(self.check(http_error(429)), "rate_limited")
        self.assertEqual(self.check(http_error(500)), "error")
        self.assertEqual(self.check(urllib.error.URLError("no route")), "offline")
        self.assertEqual(self.check(b"not json"), "error")
        self.assertEqual(stickers.verify_klipy_key("   "), "invalid")
        for status in ("ok", "invalid", "rate_limited", "offline", "error"):
            self.assertNotIn("secret", stickers.KLIPY_KEY_STATUS_MESSAGES[status])

    def test_guide_texts_are_ready_to_paste(self) -> None:
        self.assertTrue(stickers.KLIPY_GUIDE_WEBSITE.startswith("https://github.com/"))
        self.assertTrue(stickers.KLIPY_PARTNER_URL.startswith("https://partner.klipy.com"))
        self.assertIn("KLIPY", stickers.KLIPY_GUIDE_DESCRIPTION)
        self.assertLess(len(stickers.KLIPY_GUIDE_DESCRIPTION), 1000)


class StickerSourceTests(unittest.TestCase):
    def test_many_picks_spread_over_phrases_pages_and_gifs(self) -> None:
        searches: list[tuple[str, int]] = []

        class CountingKlipy:
            def cached(self, query: str, page: int = 1) -> None:
                return None

            def can_search(self) -> bool:
                return True

            def search(self, query: str, page: int = 1) -> list[stickers.KlipyResult]:
                searches.append((query, page))
                return [stickers.KlipyResult(f"{query}-{page}-{n}", f"https://static.klipy.com/{n}.gif") for n in range(50)]

            def load(self, result: stickers.KlipyResult) -> bytes:
                return GIF_BYTES

        source = stickers.StickerSource(Path("/nonexistent"), klipy=CountingKlipy(), rng=random.Random(4))  # type: ignore[arg-type]
        picks = [source.pick("coding") for _ in range(45)]
        queries = stickers.DEFAULT_QUERIES["coding"]
        self.assertEqual(sorted({query for query, _page in searches[:len(queries)]}), sorted(queries),
                         "every phrase is used once before any repeats")
        self.assertGreater(len({page for _query, page in searches}), 1, "pages vary")
        self.assertEqual(len({pick.title for pick in picks}), 45, "no GIF repeats")
        bubbles = [pick.bubble for pick in picks[:len(stickers.DEFAULT_BUBBLES["coding"])]]
        self.assertEqual(len(set(bubbles)), len(bubbles), "every bubble line once before repeats")

    def test_prefers_klipy_then_local_pool_then_placeholder(self) -> None:
        class FakeKlipy:
            def __init__(self, fail: bool) -> None:
                self.fail = fail

            def cached(self, query: str, page: int = 1) -> None:
                return None

            def can_search(self) -> bool:
                return True

            def search(self, query: str, page: int = 1) -> list[stickers.KlipyResult]:
                if self.fail:
                    raise RuntimeError("KLIPY search failed")
                return [stickers.KlipyResult("x", "https://static.klipy.com/x.gif")]

            def load(self, result: stickers.KlipyResult) -> bytes:
                return GIF_BYTES

        messages: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            gifs = Path(directory)
            (gifs / "done").mkdir()
            (gifs / "done" / "party.gif").write_bytes(GIF_BYTES)

            online = stickers.StickerSource(gifs, klipy=FakeKlipy(fail=False), rng=random.Random(3))  # type: ignore[arg-type]
            choice = online.pick("done")
            self.assertEqual((choice.source, choice.image, choice.data, choice.label), ("klipy", None, GIF_BYTES, "x"))
            self.assertIn(choice.bubble, stickers.DEFAULT_BUBBLES["done"])

            offline = stickers.StickerSource(gifs, klipy=FakeKlipy(fail=True), log=messages.append)  # type: ignore[arg-type]
            choice = offline.pick("done")
            self.assertEqual((choice.source, choice.image.name if choice.image else None), ("local", "party.gif"))
            self.assertTrue(messages)

            self.assertEqual(stickers.StickerSource(gifs).pick("idle").source, "placeholder")


if __name__ == "__main__":
    unittest.main()
