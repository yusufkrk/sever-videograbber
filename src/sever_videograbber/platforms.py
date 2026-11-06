"""URL'den platform tespiti ve URL temizleme yardımcıları."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    color: str
    domains: tuple[str, ...]
    needs_login_hint: bool = False


PLATFORMS: tuple[Platform, ...] = (
    Platform("youtube", "YouTube", "red", ("youtube.com", "youtu.be", "youtube-nocookie.com")),
    Platform("instagram", "Instagram", "magenta", ("instagram.com", "instagr.am"), True),
    Platform("twitter", "X / Twitter", "bright_white", ("twitter.com", "x.com", "t.co"), True),
    Platform("tiktok", "TikTok", "cyan", ("tiktok.com",)),
    Platform("facebook", "Facebook", "blue", ("facebook.com", "fb.watch", "fb.com"), True),
    Platform("reddit", "Reddit", "orange_red1", ("reddit.com", "redd.it")),
    Platform("vimeo", "Vimeo", "deep_sky_blue1", ("vimeo.com",)),
    Platform("twitch", "Twitch", "purple", ("twitch.tv",)),
    Platform("soundcloud", "SoundCloud", "dark_orange", ("soundcloud.com",)),
    Platform("dailymotion", "Dailymotion", "blue", ("dailymotion.com", "dai.ly")),
    Platform("pinterest", "Pinterest", "red", ("pinterest.com", "pin.it")),
    Platform("threads", "Threads", "bright_white", ("threads.net", "threads.com"), True),
    Platform("bluesky", "Bluesky", "dodger_blue1", ("bsky.app",)),
    Platform("linkedin", "LinkedIn", "blue", ("linkedin.com",), True),
    Platform("kick", "Kick", "green", ("kick.com",)),
)

GENERIC = Platform("generic", "Web", "white", ())

_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(r"^(www\.)?[\w-]+(\.[\w-]+)+(/|$)", re.IGNORECASE)


def normalize_url(raw: str) -> str | None:
    """Kullanıcının yapıştırdığı metni temizler; geçerli görünmüyorsa ``None`` döner.

    ``youtu.be/abc`` gibi şemasız adreslere ``https://`` eklenir.
    """
    text = raw.strip().strip("<>\"'")
    if not text or text.startswith("#"):
        return None
    if _URL_RE.match(text):
        scheme = text.split(":", 1)[0].lower()
        return text if scheme in ("http", "https") else None
    if _BARE_DOMAIN_RE.match(text):
        return "https://" + text
    return None


def detect_platform(url: str) -> Platform:
    host = (urlparse(url).hostname or "").lower()
    for platform in PLATFORMS:
        for domain in platform.domains:
            if host == domain or host.endswith("." + domain):
                return platform
    return GENERIC


def read_url_file(path: str) -> list[str]:
    """Her satırda bir link olan bir dosyayı okur. Boş satırlar ve ``#`` yorumları atlanır."""
    urls: list[str] = []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            url = normalize_url(line.split(" #", 1)[0])
            if url:
                urls.append(url)
    return urls


def dedupe(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out
