"""GIF sticker reactions: status → sticker mapping, local GIF pool and the optional KLIPY source.

Everything here is GTK-free so it can be unit tested. The widget calls `StickerSource.pick()`
on a short-lived worker thread whenever an agent's sticker status changes; it never blocks
the GTK main loop and every failure degrades to "local file" → "placeholder" → no sticker.
"""

from __future__ import annotations

import json
import random
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


# Sticker keys from the design spec, in the order the debug cycle shows them.
STICKER_KEYS = ("analyzing", "coding", "waiting", "done", "error", "limit", "idle")

STICKER_COLORS = {
    "analyzing": "#F5C542",
    "coding": "#60A5FA",
    "waiting": "#C084FC",
    "done": "#4ADE80",
    "error": "#F87171",
    "limit": "#FB923C",
    "idle": "#8B93A1",
}

# Structured status kinds (see status_model.STATUS_KINDS) → sticker key. Kinds that are not
# listed (neutral, stale) never pop a sticker.
KIND_TO_STICKER = {
    "thinking": "analyzing",
    "reading": "analyzing",
    "analyzing": "analyzing",
    "coding": "coding",
    "command": "coding",
    "waiting": "waiting",
    "done": "done",
    "error": "error",
    "idle": "idle",
}

# These need attention, so their sticker stays until the status changes.
STICKY_KEYS = frozenset({"waiting", "error"})

# Usage bars at or above this utilisation pop the `limit` sticker once per window.
LIMIT_THRESHOLD_PERCENT = 90.0

# Speech-bubble lines per sticker (short: the bubble wraps at ~18 characters per line).
DEFAULT_BUBBLES: dict[str, tuple[str, ...]] = {
    "analyzing": (
        "hmm… 2 + 2 = ?",
        "hold on, thinking…",
        "let me read that…",
        "reading the docs. for once.",
        "connecting the dots…",
        "big brain time",
        "wait, why does this work?",
        "following the stack trace",
        "grep, grep, grep…",
        "it's all making sense now",
        "plotting a cunning plan",
        "one more file, I promise",
        "squinting at your code",
        "loading genius.exe",
    ),
    "coding": (
        "typing, typing!",
        "shipping code, do not disturb",
        "keyboard go brrr",
        "it compiles in my head",
        "refactoring like a pro",
        "adding just one more feature",
        "trust me, I'm an AI",
        "writing tests. probably.",
        "deleting more than I add",
        "copy, paste, improve",
        "in the zone 🔥",
        "this diff is beautiful",
        "semicolons everywhere",
        "running it… fingers crossed",
    ),
    "waiting": (
        "hello? anyone there?",
        "your turn!",
        "need a yes from you",
        "knock knock 👀",
        "may I? pretty please?",
        "waiting for the boss",
        "press Enter, I dare you",
        "I'll just wait here…",
        "permission to proceed?",
        "ping! you there?",
        "the suspense is killing me",
        "coffee break? I'll wait.",
        "one click and I'm off",
    ),
    "done": (
        "done!",
        "I deserve a coffee",
        "ta-da!",
        "mic drop 🎤",
        "nailed it",
        "ship it! 🚀",
        "all green, my friend",
        "another one bites the dust",
        "easy peasy",
        "task complete. high five?",
        "look ma, no bugs!",
        "your move, human",
        "and that's a wrap",
    ),
    "error": (
        "this is fine.",
        "everything is under control.",
        "well… that broke",
        "oops. that was not me.",
        "it worked on my machine",
        "the server said no",
        "let's pretend that didn't happen",
        "plot twist!",
        "error 418: I'm a teapot",
        "a small fire. nothing serious.",
        "the logs are not happy",
        "have you tried turning it off and on?",
    ),
    "limit": (
        "save your tokens, friend",
        "running on fumes",
        "token diet starts now",
        "almost out of juice 🔋",
        "spend wisely",
        "limits, limits everywhere",
        "maybe take a walk?",
        "rationing my words",
        "the meter is ticking",
    ),
    "idle": (
        "zzz…",
        "still here, just napping",
        "wake me up when you need me",
        "dreaming of clean code",
        "on standby",
        "it's quiet… too quiet",
        "counting electric sheep",
        "taking five",
        "lunch break?",
    ),
}

# KLIPY search phrases per sticker; one is chosen at random for each new search.
DEFAULT_QUERIES: dict[str, tuple[str, ...]] = {
    "analyzing": ("thinking", "calculating", "hmm", "math lady", "detective", "confused", "galaxy brain", "reading"),
    "coding": ("typing fast", "hacker", "cat keyboard", "programmer", "coding", "busy working", "matrix", "speed typing"),
    "waiting": ("waiting", "skeleton waiting", "hello is anyone there", "tapping fingers", "dog waiting door",
                "still waiting", "knock knock", "impatient"),
    "done": ("victory dance", "nailed it", "celebration", "mic drop", "success kid", "high five", "mission accomplished",
             "happy dance"),
    "error": ("this is fine", "explosion", "fail", "facepalm", "oops", "everything is fine fire", "panic", "computer crash"),
    "limit": ("low battery", "running on empty", "out of fuel", "tired", "exhausted", "empty wallet"),
    "idle": ("sleeping", "tumbleweed", "bored", "sleeping cat", "nap time", "yawn", "waiting forever"),
}

IMAGE_SUFFIXES = (".gif", ".webp", ".png", ".jpg", ".jpeg")

KLIPY_API_BASE = "https://api.klipy.com/api/v1"
KLIPY_PER_PAGE = 24
# Search responses (lists of URLs, not media) are reused for a while to spare the API.
KLIPY_RESULTS_TTL_SECONDS = 60 * 60
KLIPY_MAX_DOWNLOAD_BYTES = 6 * 1024 * 1024
KLIPY_TIMEOUT_SECONDS = 6.0
# KLIPY serves media from klipy.com, static.klipy.com, static1.klipy.com, static2.klipy.com.
KLIPY_MEDIA_DOMAIN = "klipy.com"
# Smallest rendition that still looks sharp in a 140×94 px sticker comes first.
KLIPY_SIZE_PREFERENCE = ("sm", "xs", "md", "hd")


def sticker_for_kind(kind: object) -> str | None:
    return KIND_TO_STICKER.get(kind) if isinstance(kind, str) else None


def load_sticker_texts(path: Path) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """Bubble texts and KLIPY queries, with per-key overrides from an optional `stickers.json`.

    Format: {"bubbles": {"waiting": ["Dima? Halo?"]}, "queries": {"coding": ["hacker"]}}.
    Unknown keys and non-string entries are ignored; a broken file falls back to defaults.
    """
    bubbles = dict(DEFAULT_BUBBLES)
    queries = dict(DEFAULT_QUERIES)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return bubbles, queries
    if not isinstance(loaded, dict):
        return bubbles, queries
    for section, target in (("bubbles", bubbles), ("queries", queries)):
        overrides = loaded.get(section)
        if not isinstance(overrides, dict):
            continue
        for key, values in overrides.items():
            if key not in STICKER_KEYS or not isinstance(values, list):
                continue
            cleaned = tuple(value.strip() for value in values if isinstance(value, str) and value.strip())
            if cleaned:
                target[key] = cleaned
    return bubbles, queries


def is_image_file(head: bytes) -> bool:
    """Magic-byte check so a hostile or broken download never reaches GdkPixbuf as junk."""
    return (
        head.startswith((b"GIF87a", b"GIF89a", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff"))
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


class NoRepeatChooser:
    """Random choice that never returns the same item twice in a row for a given key."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.last: dict[str, str] = {}

    def choose(self, key: str, items: list[str]) -> str | None:
        if not items:
            return None
        candidates = [item for item in items if item != self.last.get(key)] or items
        chosen = self.rng.choice(candidates)
        self.last[key] = chosen
        return chosen


def local_pool(gifs_dir: Path, key: str) -> list[Path]:
    folder = gifs_dir / key
    try:
        return sorted(
            path for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
    except OSError:
        return []


@dataclass(frozen=True)
class KlipyResult:
    id: str
    url: str


def _pick_rendition(file_info: Any) -> str | None:
    if not isinstance(file_info, dict):
        return None
    for size in KLIPY_SIZE_PREFERENCE:
        rendition = file_info.get(size)
        if not isinstance(rendition, dict):
            continue
        gif = rendition.get("gif")
        url = gif.get("url") if isinstance(gif, dict) else None
        if isinstance(url, str) and is_klipy_media_url(url):
            return url
    return None


def is_klipy_media_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == KLIPY_MEDIA_DOMAIN or host.endswith("." + KLIPY_MEDIA_DOMAIN))


def parse_klipy_search(payload: Any) -> list[KlipyResult]:
    """Extract GIF results from a KLIPY search response, skipping ads and malformed items.

    KLIPY wraps results as {"result": true, "data": {"data": [item, ...], ...}}; each item has
    `file` → size (`hd`/`md`/`sm`/`xs`) → format (`gif`/`webp`/`mp4`) → {"url", ...}. Only GIF
    renditions are used because GdkPixbuf animates GIF out of the box.
    """
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    results: list[KlipyResult] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") == "ad":
            continue
        url = _pick_rendition(item.get("file"))
        if url is None:
            continue
        identifier = item.get("slug") or item.get("id") or url
        results.append(KlipyResult(id=str(identifier), url=url))
    return results


def load_customer_id(path: Path) -> str:
    """A random, per-install id KLIPY uses to tell end users apart; created on first use."""
    try:
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    value = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n", encoding="utf-8")
    except OSError:
        pass
    return value


class KlipyClient:
    """KLIPY GIF search; media is loaded straight from KLIPY's URLs into memory.

    Per KLIPY's integration requirements the media is never stored, mirrored or kept on disk:
    every sticker downloads its GIF from the URL in the API response and only holds it in
    memory while it is shown. Search responses (URL lists) are reused for
    `KLIPY_RESULTS_TTL_SECONDS` so a busy session does not hammer the API.
    """

    def __init__(
        self,
        api_key: str,
        customer_id: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = KLIPY_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.customer_id = customer_id
        self.opener = opener
        self.clock = clock
        self.timeout = timeout
        self.results: dict[str, tuple[float, list[KlipyResult]]] = {}
        self.lock = threading.Lock()

    def search_url(self, query: str) -> str:
        params = urllib.parse.urlencode({
            "q": query,
            "per_page": KLIPY_PER_PAGE,
            "customer_id": self.customer_id,
            "content_filter": "high",
            "format_filter": "gif",
        })
        key = urllib.parse.quote(self.api_key, safe="")
        return f"{KLIPY_API_BASE}/{key}/gifs/search?{params}"

    def _get(self, url: str, limit: int) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "ai-cli-status-monitor"})
        with self.opener(request, timeout=self.timeout) as response:
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("response too large")
        return body

    def search(self, query: str) -> list[KlipyResult]:
        now = self.clock()
        with self.lock:
            cached = self.results.get(query)
            if cached is not None and now - cached[0] < KLIPY_RESULTS_TTL_SECONDS:
                return cached[1]
        try:
            payload = json.loads(self._get(self.search_url(query), 2 * 1024 * 1024).decode("utf-8"))
            results = parse_klipy_search(payload)
        except Exception:
            # Never surface the URL: it contains the API key.
            raise RuntimeError("KLIPY search failed") from None
        with self.lock:
            self.results[query] = (now, results)
        return results

    def load(self, result: KlipyResult) -> bytes:
        """Fetch one GIF directly from its KLIPY URL; the bytes live only in memory."""
        if not is_klipy_media_url(result.url):
            raise RuntimeError("KLIPY media URL rejected")
        try:
            body = self._get(result.url, KLIPY_MAX_DOWNLOAD_BYTES)
        except Exception:
            raise RuntimeError("KLIPY download failed") from None
        if not is_image_file(body[:16]):
            raise RuntimeError("KLIPY download is not an image")
        return body


@dataclass(frozen=True)
class StickerChoice:
    key: str
    image: Path | None  # a local file (local pool)
    bubble: str
    source: str  # "klipy", "local" or "placeholder"
    data: bytes | None = None  # KLIPY media, held in memory only
    title: str = ""

    @property
    def label(self) -> str:
        if self.image is not None:
            return self.image.name
        return self.title or ("in-memory GIF" if self.data else "placeholder")


class StickerSource:
    """Pick the image and bubble for a sticker: KLIPY when configured, else the local pool."""

    def __init__(
        self,
        gifs_dir: Path,
        bubbles: Mapping[str, tuple[str, ...]] | None = None,
        queries: Mapping[str, tuple[str, ...]] | None = None,
        klipy: KlipyClient | None = None,
        rng: random.Random | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.gifs_dir = gifs_dir
        self.bubbles = dict(bubbles or DEFAULT_BUBBLES)
        self.queries = dict(queries or DEFAULT_QUERIES)
        self.klipy = klipy
        self.rng = rng or random.Random()
        self.images = NoRepeatChooser(self.rng)
        self.texts = NoRepeatChooser(self.rng)
        self.log = log or (lambda _message: None)

    def bubble(self, key: str) -> str:
        return self.texts.choose(key, list(self.bubbles.get(key, ()))) or ""

    def pick_klipy(self, key: str) -> tuple[bytes, str] | None:
        if self.klipy is None:
            return None
        queries = self.queries.get(key) or DEFAULT_QUERIES.get(key, ())
        if not queries:
            return None
        query = self.rng.choice(list(queries))
        try:
            results = self.klipy.search(query)
            by_id = {result.id: result for result in results}
            chosen = self.images.choose(key, list(by_id))
            return (self.klipy.load(by_id[chosen]), chosen) if chosen is not None else None
        except Exception as error:
            self.log(f"sticker: {error}; using the local GIF pool")
            return None

    def pick_local(self, key: str) -> Path | None:
        pool = {str(path): path for path in local_pool(self.gifs_dir, key)}
        chosen = self.images.choose(key, list(pool))
        return pool[chosen] if chosen is not None else None

    def pick(self, key: str) -> StickerChoice:
        bubble = self.bubble(key)
        klipy = self.pick_klipy(key)
        if klipy is not None:
            data, slug = klipy
            return StickerChoice(key, None, bubble, "klipy", data=data, title=slug)
        image = self.pick_local(key)
        if image is not None:
            return StickerChoice(key, image, bubble, "local")
        return StickerChoice(key, None, bubble, "placeholder")
