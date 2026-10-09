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
    def test_never_repeats_the_same_file_twice_in_a_row(self) -> None:
        chooser = stickers.NoRepeatChooser(random.Random(1))
        picks = [chooser.choose("coding", ["a", "b", "c"]) for _ in range(50)]
        self.assertTrue(all(first != second for first, second in zip(picks, picks[1:])))
        self.assertEqual(chooser.choose("solo", ["only"]), "only")
        self.assertEqual(chooser.choose("solo", ["only"]), "only")
        self.assertIsNone(chooser.choose("empty", []))

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
            Path(directory) / "cache",
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

            now[0] += stickers.KLIPY_RESULTS_TTL_SECONDS + 1
            client.search("thinking")
            self.assertEqual(len(calls), 2)

    def test_search_failure_never_leaks_the_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(directory, {}, [], [0.0])
            with self.assertRaises(RuntimeError) as caught:
                client.search("thinking")
            self.assertNotIn("secret", str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)

    def test_downloads_once_validates_images_and_prunes_the_cache(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(directory, {"a-sm.gif": GIF_BYTES, "bad-sm.gif": b"<html>"}, calls, [0.0])
            good = stickers.KlipyResult("a", "https://static.klipy.com/a-sm.gif")

            path = client.download(good)
            self.assertEqual(path.read_bytes(), GIF_BYTES)
            self.assertEqual(client.download(good), path)
            self.assertEqual(len(calls), 1)

            with self.assertRaises(RuntimeError):
                client.download(stickers.KlipyResult("bad", "https://static.klipy.com/bad-sm.gif"))
            self.assertEqual(sorted(p.name for p in client.cache_dir.iterdir()), [path.name])

            older = client.cache_dir / "older.gif"
            older.write_bytes(GIF_BYTES)
            os.utime(older, (time.time() - 100, time.time() - 100))
            client.prune(limit=len(GIF_BYTES))
            self.assertTrue(path.exists())
            self.assertFalse(older.exists())

    def test_customer_id_is_created_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cfg" / "klipy_customer_id"
            first = stickers.load_customer_id(path)
            self.assertEqual(len(first), 32)
            self.assertEqual(stickers.load_customer_id(path), first)


class StickerSourceTests(unittest.TestCase):
    def test_prefers_klipy_then_local_pool_then_placeholder(self) -> None:
        class FakeKlipy:
            def __init__(self, fail: bool) -> None:
                self.fail = fail

            def search(self, query: str) -> list[stickers.KlipyResult]:
                if self.fail:
                    raise RuntimeError("KLIPY search failed")
                return [stickers.KlipyResult("x", "https://static.klipy.com/x.gif")]

            def download(self, result: stickers.KlipyResult) -> Path:
                return Path("/cache/x.gif")

        messages: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            gifs = Path(directory)
            (gifs / "done").mkdir()
            (gifs / "done" / "party.gif").write_bytes(GIF_BYTES)

            online = stickers.StickerSource(gifs, klipy=FakeKlipy(fail=False), rng=random.Random(3))  # type: ignore[arg-type]
            choice = online.pick("done")
            self.assertEqual((choice.source, choice.image), ("klipy", Path("/cache/x.gif")))
            self.assertIn(choice.bubble, stickers.DEFAULT_BUBBLES["done"])

            offline = stickers.StickerSource(gifs, klipy=FakeKlipy(fail=True), log=messages.append)  # type: ignore[arg-type]
            choice = offline.pick("done")
            self.assertEqual((choice.source, choice.image.name if choice.image else None), ("local", "party.gif"))
            self.assertTrue(messages)

            self.assertEqual(stickers.StickerSource(gifs).pick("idle").source, "placeholder")


if __name__ == "__main__":
    unittest.main()
