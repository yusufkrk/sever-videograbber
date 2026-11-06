"""yt-dlp hata mesajlarını kullanıcı dostu açıklamalara çevirir."""

from __future__ import annotations

import re

from .i18n import t


class GrabberError(Exception):
    """Sever VideoGrabber'ın fırlattığı, kullanıcıya gösterilebilir hata."""

    def __init__(self, message: str, *, raw: str | None = None, code: str = "generic") -> None:
        super().__init__(message)
        self.raw = raw or message
        self.code = code


# (regex, mesaj anahtarı) — sıra önemlidir, ilk eşleşen kazanır.
_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"could not (copy|find|decrypt).*cookie|cookie.*database|failed to decrypt", "cookie_db"),
    (r"ffmpeg|ffprobe|postprocessing", "ffmpeg"),
    (r"sign in to confirm you.?re not a bot|confirm you.?re not a bot", "bot"),
    (r"age.?restrict|confirm your age|inappropriate for some users", "age"),
    (r"private video|this video is private|private account|is private", "private"),
    (
        r"login required|log in|requires? (an? )?(account|authentication|login)|"
        r"you need to log in|use --cookies|empty media response|authorization",
        "login",
    ),
    (r"not available in your country|geo.?restrict|blocked in your", "geo"),
    (
        r"video unavailable|video is unavailable|is no longer available|has been removed|no longer available|does not exist|"
        r"account.*(terminated|suspended)|http error 404|not found",
        "removed",
    ),
    (r"http error 429|too many requests|rate.?limit", "ratelimit"),
    (r"live event will begin|premieres in|is not live|this live event", "live"),
    (
        r"unsupported url|no video could be found|no video (formats )?found|no media found|there.?s no video",
        "unsupported",
    ),
    (
        r"getaddrinfo|name or service not known|timed? ?out|connection (reset|refused|aborted)|"
        r"unable to download webpage|ssl|network is unreachable",
        "network",
    ),
)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def clean_message(raw: str) -> str:
    msg = _ANSI.sub("", str(raw)).strip()
    msg = re.sub(r"^ERROR:\s*", "", msg)
    msg = re.sub(r"^\[[\w:]+\]\s*[\w-]*:\s*", "", msg)
    return msg


def classify(raw: str) -> str:
    low = clean_message(raw).lower()
    for pattern, code in _PATTERNS:
        if re.search(pattern, low):
            return code
    return "generic"


def friendly(raw: str | BaseException) -> GrabberError:
    """Ham bir hatayı açıklamalı bir :class:`GrabberError`'a dönüştürür."""
    text = clean_message(str(raw))
    code = classify(text)
    message = t("err_generic", msg=text) if code == "generic" else t(f"err_{code}")
    return GrabberError(message, raw=text, code=code)
