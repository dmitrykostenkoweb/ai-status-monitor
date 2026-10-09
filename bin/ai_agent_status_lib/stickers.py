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
from collections import deque
import urllib.error
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
        "hmm… 2 + 2 = ?", "hold on, thinking…", "let me read that…", "reading the docs. for once.",
        "connecting the dots…", "big brain time", "wait, why does this work?", "following the stack trace",
        "grep, grep, grep…", "it's all making sense now", "plotting a cunning plan", "one more file, I promise",
        "squinting at your code", "loading genius.exe", "who wrote this? oh. me.", "consulting the rubber duck",
        "enhance… enhance…", "reading between the lines", "so many tabs open", "deep in the call stack",
        "detective mode: on", "hmm, interesting…",
    ),
    "coding": (
        "typing, typing!", "shipping code, do not disturb", "keyboard go brrr", "it compiles in my head",
        "refactoring like a pro", "adding just one more feature", "trust me, I'm an AI", "writing tests. probably.",
        "deleting more than I add", "copy, paste, improve", "in the zone 🔥", "this diff is beautiful",
        "semicolons everywhere", "running it… fingers crossed", "hold my coffee", "making the linter happy",
        "art, not code", "naming things is hard", "tiny commits, big dreams", "fixing yesterday's me",
        "hacker voice: I'm in", "lines go up",
    ),
    "waiting": (
        "hello? anyone there?", "your turn!", "need a yes from you", "knock knock 👀", "may I? pretty please?",
        "waiting for the boss", "press Enter, I dare you", "I'll just wait here…", "permission to proceed?",
        "ping! you there?", "the suspense is killing me", "coffee break? I'll wait.", "one click and I'm off",
        "blink twice if you agree", "*taps desk*", "still here. still waiting.", "I brought snacks. approve?",
        "your call, captain", "awaiting orders", "don't leave me hanging",
    ),
    "done": (
        "done!", "I deserve a coffee", "ta-da!", "mic drop 🎤", "nailed it", "ship it! 🚀", "all green, my friend",
        "another one bites the dust", "easy peasy", "task complete. high five?", "look ma, no bugs!",
        "your move, human", "and that's a wrap", "victory lap time", "chef's kiss 👌", "flawless victory",
        "achievement unlocked", "boom. done.", "time for a break", "nothing left to fix. today.",
    ),
    "error": (
        "this is fine.", "everything is under control.", "well… that broke", "oops. that was not me.",
        "it worked on my machine", "the server said no", "let's pretend that didn't happen", "plot twist!",
        "error 418: I'm a teapot", "a small fire. nothing serious.", "the logs are not happy",
        "have you tried turning it off and on?", "houston, we have a problem", "red is my new favorite color",
        "nobody panic", "stack trace says hi", "that escalated quickly", "I can explain…", "ctrl+z, anyone?",
        "brb, debugging",
    ),
    "limit": (
        "save your tokens, friend", "running on fumes", "token diet starts now", "almost out of juice 🔋",
        "spend wisely", "limits, limits everywhere", "maybe take a walk?", "rationing my words", "the meter is ticking",
        "low battery mode", "budget meeting needed", "every token counts", "running out of words",
        "time to touch grass?",
    ),
    "idle": (
        "zzz…", "still here, just napping", "wake me up when you need me", "dreaming of clean code", "on standby",
        "it's quiet… too quiet", "counting electric sheep", "taking five", "lunch break?", "screensaver mode",
        "waiting for inspiration", "ready when you are", "just chilling", "stretching my neurons",
    ),
}

# KLIPY search phrases per sticker: specific, meme-y phrases whose *first* page of results
# is on topic (generic words like "focus" or deep result pages drift off-topic fast).
# They are dealt like a shuffled deck, so variety comes from the number of phrases.
DEFAULT_QUERIES: dict[str, tuple[str, ...]] = {
    "analyzing": (
        "math lady meme", "thinking meme", "confused travolta", "calculating meme", "galaxy brain meme",
        "sherlock thinking", "detective pikachu thinking", "hmm thinking", "big brain meme", "let me think meme",
        "nerd thinking", "reading glasses meme", "processing meme", "hmm interesting meme", "confused math",
        "thinking hard meme", "investigating meme", "mind blown meme", "the office thinking", "zoom enhance meme",
    ),
    "coding": (
        "hackerman", "hacker typing meme", "typing fast meme", "cat typing", "programmer meme", "coding meme",
        "keyboard smash meme", "spongebob typing", "matrix code meme", "im in hacker", "nerd typing", "cat keyboard",
        "developer meme", "working hard meme", "busy typing meme", "typing furiously", "hacker cat",
        "programming meme", "speed typing meme", "computer work meme",
    ),
    "waiting": (
        "skeleton waiting", "waiting meme", "mr bean waiting", "tapping fingers meme", "dog waiting door",
        "still waiting meme", "hello is anyone there meme", "waiting patiently meme", "checking watch meme",
        "impatient waiting", "knock knock meme", "spongebob waiting", "waiting for you meme", "bored waiting meme",
        "are you there meme", "waiting forever meme", "hurry up meme", "staring waiting meme",
    ),
    "done": (
        "victory dance", "nailed it meme", "success kid", "mic drop meme", "mission accomplished meme",
        "celebration meme", "happy dance meme", "we did it meme", "thumbs up meme", "applause meme",
        "fist pump meme", "yes yes yes meme", "the office celebration", "high five meme", "winning meme",
        "leonardo dicaprio cheers", "dance party meme", "nice meme",
    ),
    "error": (
        "this is fine dog", "this is fine meme", "facepalm meme", "epic fail meme", "oops meme",
        "everything is on fire meme", "shocked pikachu", "disaster girl", "oh no meme", "computer crash meme",
        "panic meme", "explosion meme", "screaming meme", "computer rage", "error meme", "fail meme",
        "surprised pikachu", "it's broken meme",
    ),
    "limit": (
        "low battery meme", "running on empty meme", "no money meme", "tired meme", "exhausted meme",
        "empty wallet meme", "broke meme", "out of energy meme", "dead battery meme", "running out of time meme",
    ),
    "idle": (
        "sleeping meme", "bored meme", "tumbleweed", "sleeping cat", "nap time meme", "yawn meme", "sloth meme",
        "relax meme", "chilling meme", "zzz meme",
    ),
}

# Speech-bubble templates that say what the agent is doing right now ({target} comes from
# the hook's activity: a file name, a command or its description, a search pattern…).
# A "<type>:post" entry is used right after the tool finished; it falls back to "<type>".
DEFAULT_ACTIVITY_TEMPLATES: dict[str, tuple[str, ...]] = {
    "read": ("reading {target}…", "peeking at {target} 👀", "studying {target}", "opening {target}"),
    "read:post": ("hmm, {target}…", "digesting {target}", "so that's {target}…"),
    "edit": ("editing {target}…", "patching {target} 🔧", "rewriting {target}", "tweaking {target}"),
    "edit:post": ("{target} updated ✓", "done with {target}", "{target} looks better"),
    "command": ("{target}…", "running: {target}", "{target} 🤞"),
    "command:post": ("checking: {target}", "reading the output…", "{target} — let's see"),
    "search": ("hunting for '{target}'", "grep '{target}'…", "where is '{target}'?"),
    "web": ("browsing {target}…", "looking up {target}", "reading {target}"),
    "agent": ("sending a helper: {target}", "delegating: {target}", "sub-agent on it: {target}"),
    "plan": ("updating the to-do list", "planning the next steps", "ticking boxes ✓"),
    "permission": ("may I use {target}?", "need your OK for {target}", "approve {target}? 🙏"),
}

IMAGE_SUFFIXES = (".gif", ".webp", ".png", ".jpg", ".jpeg")

KLIPY_API_BASE = "https://api.klipy.com/api/v1"
# Only the first, most relevant page of results is used: deeper pages drift off-topic.
KLIPY_PER_PAGE = 16
KLIPY_PAGES = 1
# Self-imposed cap on new searches (cached ones are free) below the test key's 100/hour.
KLIPY_SEARCHES_PER_HOUR = 60
# How many recently shown GIFs (across all stickers and windows) are never re-picked.
RECENT_GIF_MEMORY = 200
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


def load_activity_templates(path: Path) -> dict[str, tuple[str, ...]]:
    """Activity bubble templates with overrides from `stickers.json` → "activity" (e.g. Polish).

    "{target}" is optional in a template; non-string or empty entries are ignored.
    """
    templates = dict(DEFAULT_ACTIVITY_TEMPLATES)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return templates
    overrides = loaded.get("activity") if isinstance(loaded, dict) else None
    if not isinstance(overrides, dict):
        return templates
    for key, values in overrides.items():
        if key not in DEFAULT_ACTIVITY_TEMPLATES or not isinstance(values, list):
            continue
        cleaned = tuple(value.strip() for value in values if isinstance(value, str) and value.strip())
        if cleaned:
            templates[key] = cleaned
    return templates


def is_image_file(head: bytes) -> bool:
    """Magic-byte check so a hostile or broken download never reaches GdkPixbuf as junk."""
    return (
        head.startswith((b"GIF87a", b"GIF89a", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff"))
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


class ShuffleBag:
    """Deals every item once in random order before any item repeats (per key).

    When a bag is refilled, the next first item is never the one just dealt, so even a
    two-item list alternates instead of repeating.
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.bags: dict[str, list[str]] = {}
        self.signatures: dict[str, tuple[str, ...]] = {}
        self.last: dict[str, str] = {}

    def draw(self, key: str, items: tuple[str, ...] | list[str]) -> str | None:
        items = tuple(dict.fromkeys(items))
        if not items:
            return None
        if self.signatures.get(key) != items or not self.bags.get(key):
            bag = list(items)
            self.rng.shuffle(bag)
            if len(bag) > 1 and bag[-1] == self.last.get(key):
                bag[0], bag[-1] = bag[-1], bag[0]
            self.bags[key] = bag
            self.signatures[key] = items
        chosen = self.bags[key].pop()
        self.last[key] = chosen
        return chosen


class RecentMemory:
    """Remembers recently shown items and prefers ones not seen lately.

    `pick()` chooses randomly among items not in the memory; when every candidate was
    shown recently it falls back to the one shown longest ago.
    """

    def __init__(self, size: int = RECENT_GIF_MEMORY, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.recent: deque[str] = deque(maxlen=size)
        self.lock = threading.Lock()

    def pick(self, items: list[str]) -> str | None:
        if not items:
            return None
        with self.lock:
            seen = set(self.recent)
            fresh = [item for item in items if item not in seen]
            if fresh:
                chosen = self.rng.choice(fresh)
            else:
                order = {item: index for index, item in enumerate(self.recent)}
                chosen = min(items, key=lambda item: order.get(item, -1))
            if chosen in self.recent:
                self.recent.remove(chosen)
            self.recent.append(chosen)
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
        self.results: dict[tuple[str, int], tuple[float, list[KlipyResult]]] = {}
        self.search_times: deque[float] = deque()
        self.lock = threading.Lock()

    def search_url(self, query: str, page: int = 1) -> str:
        params = urllib.parse.urlencode({
            "q": query,
            "page": page,
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

    def cached(self, query: str, page: int = 1) -> list[KlipyResult] | None:
        with self.lock:
            entry = self.results.get((query, page))
            if entry is not None and self.clock() - entry[0] < KLIPY_RESULTS_TTL_SECONDS:
                return entry[1]
            return None

    def cached_for(self, queries: tuple[str, ...] | list[str]) -> list[KlipyResult]:
        """Every still-fresh cached result for any of these phrases (any page)."""
        wanted = set(queries)
        now = self.clock()
        merged: dict[str, KlipyResult] = {}
        with self.lock:
            for (query, _page), (fetched, results) in self.results.items():
                if query in wanted and now - fetched < KLIPY_RESULTS_TTL_SECONDS:
                    for result in results:
                        merged.setdefault(result.id, result)
        return list(merged.values())

    def can_search(self) -> bool:
        """True while fewer than KLIPY_SEARCHES_PER_HOUR new searches ran in the last hour."""
        now = self.clock()
        with self.lock:
            while self.search_times and now - self.search_times[0] >= 3600:
                self.search_times.popleft()
            return len(self.search_times) < KLIPY_SEARCHES_PER_HOUR

    def search(self, query: str, page: int = 1) -> list[KlipyResult]:
        cached = self.cached(query, page)
        if cached is not None:
            return cached
        now = self.clock()
        with self.lock:
            self.search_times.append(now)
        try:
            payload = json.loads(self._get(self.search_url(query, page), 2 * 1024 * 1024).decode("utf-8"))
            results = parse_klipy_search(payload)
        except Exception:
            # Never surface the URL: it contains the API key.
            raise RuntimeError("KLIPY search failed") from None
        with self.lock:
            self.results[(query, page)] = (now, results)
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


# ---- in-app "get a free KLIPY key" guide ----
KLIPY_PARTNER_URL = "https://partner.klipy.com"
KLIPY_GUIDE_PLATFORM_NAME = "AI Status Monitor"
KLIPY_GUIDE_WEBSITE = "https://github.com/dmitrykostenkoweb/ai-status-monitor"
KLIPY_GUIDE_KEY_NAME = "AI-Status-Monitor-Linux"
KLIPY_GUIDE_DESCRIPTION = (
    "AI Status Monitor is an open-source desktop widget for Linux (Python + GTK) that shows "
    "the live status of AI coding agents (Claude Code, Codex CLI) running in the user's terminals. "
    "When an agent's status changes (thinking, coding, waiting, done, error) the widget shows a small "
    "sticker with a GIF next to that agent. The app calls the GIF Search API directly from the "
    "user's machine with a status-related query, picks one result and loads it straight from the "
    "KLIPY URL into memory - no server, no proxy, no media caching. Content filter: high. "
    "Stickers with KLIPY content carry a KLIPY mark."
)

KLIPY_KEY_STATUS_MESSAGES = {
    "ok": "✓ The key works. Stickers now use GIFs from KLIPY.",
    "invalid": "✗ KLIPY rejected this key. Copy it again from the Partner Panel.",
    "rate_limited": "The key is valid but has hit its hourly limit. GIFs come back within the hour.",
    "offline": "Could not reach KLIPY. Check your internet connection and try again.",
    "error": "KLIPY answered unexpectedly. Try again in a moment.",
}


def verify_klipy_key(
    api_key: str,
    customer_id: str = "key-check",
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: float = KLIPY_TIMEOUT_SECONDS,
) -> str:
    """One test search; returns a KLIPY_KEY_STATUS_MESSAGES key. Never echoes the key."""
    key = api_key.strip()
    if not key:
        return "invalid"
    client = KlipyClient(key, customer_id, opener=opener, timeout=timeout)
    try:
        body = client._get(client.search_url("hello"), 2 * 1024 * 1024)
        payload = json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 429:
            return "rate_limited"
        if error.code in (401, 403, 404):
            return "invalid"
        return "error"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "offline"
    except Exception:
        return "error"
    if isinstance(payload, dict) and payload.get("result") is True:
        return "ok"
    return "invalid"


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
        self.activity_templates = dict(DEFAULT_ACTIVITY_TEMPLATES)
        self.rng = rng or random.Random()
        # Shared by every sticker and session window: no GIF comes back until ~200 others did.
        self.recent = RecentMemory(rng=self.rng)
        self.texts = ShuffleBag(self.rng)
        self.phrases = ShuffleBag(self.rng)
        self.log = log or (lambda _message: None)

    def bubble(self, key: str) -> str:
        return self.texts.draw(key, self.bubbles.get(key, ())) or ""

    def activity_bubble(self, activity: Mapping[str, str] | None) -> str | None:
        """What the agent is doing right now, phrased with a (shuffled) template."""
        if not activity:
            return None
        kind = activity.get("type", "")
        phase_key = f"{kind}:post" if activity.get("phase") == "post" else kind
        templates = self.activity_templates.get(phase_key) or self.activity_templates.get(kind)
        if not templates:
            return None
        template = self.texts.draw(f"activity:{phase_key}", templates) or templates[0]
        return template.replace("{target}", activity.get("target", ""))

    def klipy_results(self, key: str) -> list[KlipyResult]:
        """A fresh search (new phrase, random page) while under the hourly budget,
        otherwise everything already fetched for this sticker."""
        assert self.klipy is not None
        queries = self.queries.get(key) or DEFAULT_QUERIES.get(key, ())
        if not queries:
            return []
        query = self.phrases.draw(key, queries)
        cached = self.klipy.cached(query, 1)
        if cached is not None:
            return cached
        if self.klipy.can_search():
            return self.klipy.search(query, 1)
        self.log("sticker: KLIPY hourly search budget used up; reusing earlier results")
        return self.klipy.cached_for(queries)

    def pick_klipy(self, key: str) -> tuple[bytes, str] | None:
        if self.klipy is None:
            return None
        try:
            by_id = {result.id: result for result in self.klipy_results(key)}
            chosen = self.recent.pick(list(by_id))
            return (self.klipy.load(by_id[chosen]), chosen) if chosen is not None else None
        except Exception as error:
            self.log(f"sticker: {error}; using the local GIF pool")
            return None

    def pick_local(self, key: str) -> Path | None:
        pool = {str(path): path for path in local_pool(self.gifs_dir, key)}
        chosen = self.recent.pick(list(pool))
        return pool[chosen] if chosen is not None else None

    def pick(self, key: str, activity: Mapping[str, str] | None = None) -> StickerChoice:
        bubble = self.activity_bubble(activity) or self.bubble(key)
        klipy = self.pick_klipy(key)
        if klipy is not None:
            data, slug = klipy
            return StickerChoice(key, None, bubble, "klipy", data=data, title=slug)
        image = self.pick_local(key)
        if image is not None:
            return StickerChoice(key, image, bubble, "local")
        return StickerChoice(key, None, bubble, "placeholder")
