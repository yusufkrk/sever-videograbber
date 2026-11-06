"""İndirme ayarları ve bunların yt-dlp parametrelerine dönüştürülmesi."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from platformdirs import user_downloads_dir

QUALITIES: tuple[str, ...] = ("best", "2160", "1440", "1080", "720", "480", "360", "240", "144")
AUDIO_FORMATS: tuple[str, ...] = ("mp3", "m4a", "opus", "flac", "wav")
CONTAINERS: tuple[str, ...] = ("mp4", "mkv", "webm")
AUDIO_BITRATES: tuple[str, ...] = ("128", "192", "256", "320")

DEFAULT_TEMPLATE = "%(title).150B [%(id)s].%(ext)s"
PLAYLIST_TEMPLATE = "%(playlist_title).80B/%(playlist_index)03d - %(title).120B [%(id)s].%(ext)s"

# Kapak resmi gömmeyi destekleyen kapsayıcılar (yt-dlp EmbedThumbnail).
_THUMBNAIL_OK = {"mp4", "mkv", "m4a", "mp3", "opus", "flac"}


def default_output_dir() -> Path:
    return Path(user_downloads_dir()) / "Sever VideoGrabber"


@dataclass
class DownloadOptions:
    """Bir indirme işleminin tüm ayarları. Tüm alanların mantıklı varsayılanları vardır."""

    output_dir: Path = field(default_factory=default_output_dir)
    quality: str = "best"
    audio_only: bool = False
    audio_format: str = "mp3"
    audio_quality: str = "192"
    container: str = "mp4"
    playlist: bool = False
    playlist_items: str | None = None
    subtitles: list[str] = field(default_factory=list)
    auto_subtitles: bool = False
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    filename_template: str = DEFAULT_TEMPLATE
    playlist_template: str = PLAYLIST_TEMPLATE
    cookies_file: Path | None = None
    cookies_from_browser: str | None = None
    proxy: str | None = None
    rate_limit: str | None = None
    retries: int = 10
    archive_file: Path | None = None
    overwrite: bool = False
    restrict_filenames: bool = False

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir).expanduser()
        self.quality = str(self.quality).lower().removesuffix("p")
        self.audio_format = self.audio_format.lower()
        self.container = self.container.lower()
        self.audio_quality = str(self.audio_quality).lower().removesuffix("k")
        if isinstance(self.subtitles, str):
            self.subtitles = [s.strip() for s in self.subtitles.split(",") if s.strip()]
        for name in ("cookies_file", "archive_file"):
            value = getattr(self, name)
            if value:
                setattr(self, name, Path(value).expanduser())
        self.validate()

    def validate(self) -> None:
        if self.quality not in QUALITIES:
            raise ValueError(f"quality: {self.quality!r} — {', '.join(QUALITIES)}")
        if self.audio_format not in AUDIO_FORMATS:
            raise ValueError(f"audio_format: {self.audio_format!r} — {', '.join(AUDIO_FORMATS)}")
        if self.container not in CONTAINERS:
            raise ValueError(f"container: {self.container!r} — {', '.join(CONTAINERS)}")
        if not self.audio_quality.isdigit():
            raise ValueError(f"audio_quality: {self.audio_quality!r}")
        if self.retries < 0:
            raise ValueError("retries >= 0")

    def updated(self, **changes: Any) -> DownloadOptions:
        """Verilen alanları değiştirilmiş yeni bir kopya döndürür (``None`` değerleri yok sayılır)."""
        valid = {f.name for f in fields(self)}
        clean = {k: v for k, v in changes.items() if v is not None and k in valid}
        return replace(self, **clean)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadOptions:
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})

    # ------------------------------------------------------------------ yt-dlp

    def format_selector(self) -> tuple[str, list[str]]:
        """``(format, format_sort)`` çiftini döndürür."""
        if self.audio_only:
            return "ba/b", ["abr", "asr"]
        sort: list[str] = []
        if self.quality != "best":
            # "res:720" → 720p'ye eşit/küçük en iyi çözünürlüğü tercih et; yoksa en yakın.
            sort.append(f"res:{self.quality}")
        if self.container == "mp4":
            # H.264/AAC: Windows, telefon, WhatsApp vb. her yerde oynar.
            sort.append("ext:mp4:m4a")
        elif self.container == "webm":
            sort.append("ext:webm:webm")
        return "bv*+ba/b", sort

    def postprocessors(self) -> list[dict[str, Any]]:
        pps: list[dict[str, Any]] = []
        final_ext = self.audio_format if self.audio_only else self.container
        if self.audio_only:
            pps.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": self.audio_quality,
                    "nopostoverwrites": False,
                }
            )
        elif self.subtitles and self.container in ("mp4", "mkv", "webm"):
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
        if self.embed_metadata and final_ext != "wav":
            pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})
        if self.embed_thumbnail and final_ext in _THUMBNAIL_OK:
            pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
        return pps

    def wants_thumbnail(self) -> bool:
        final_ext = self.audio_format if self.audio_only else self.container
        return self.embed_thumbnail and final_ext in _THUMBNAIL_OK

    def to_ydl_params(self) -> dict[str, Any]:
        """Bu ayarları ``yt_dlp.YoutubeDL`` parametre sözlüğüne çevirir."""
        fmt, sort = self.format_selector()
        params: dict[str, Any] = {
            "format": fmt,
            "format_sort": sort,
            "paths": {"home": str(self.output_dir)},
            # Oynatma listesinin kendi kapak/açıklama dosyaları yazılmasın.
            "outtmpl": {
                "default": self.filename_template,
                "pl_thumbnail": "",
                "pl_description": "",
                "pl_infojson": "",
            },
            "noplaylist": not self.playlist,
            "retries": self.retries,
            "fragment_retries": self.retries,
            "file_access_retries": 3,
            "concurrent_fragment_downloads": 4,
            "overwrites": self.overwrite,
            "continuedl": True,
            "windowsfilenames": True,
            "restrictfilenames": self.restrict_filenames,
            "trim_file_name": 200,
            "postprocessors": self.postprocessors(),
            "writethumbnail": self.wants_thumbnail(),
            "noprogress": True,
            "quiet": True,
            "no_warnings": False,
            "color": {"stdout": "never", "stderr": "never"},
        }
        if not self.audio_only:
            params["merge_output_format"] = self.container
            if self.subtitles:
                params["writesubtitles"] = True
                params["writeautomaticsub"] = self.auto_subtitles
                params["subtitleslangs"] = list(self.subtitles)
        if self.playlist_items:
            params["playlist_items"] = self.playlist_items
        if self.cookies_file:
            params["cookiefile"] = str(self.cookies_file)
        if self.cookies_from_browser:
            browser, _, profile = self.cookies_from_browser.partition(":")
            params["cookiesfrombrowser"] = (browser.lower(), profile or None, None, None)
        if self.proxy:
            params["proxy"] = self.proxy
        if self.rate_limit:
            from yt_dlp.utils import parse_bytes

            limit = parse_bytes(self.rate_limit)
            if limit is None:
                raise ValueError(f"rate_limit: {self.rate_limit!r} (örn. 2M, 500K)")
            params["ratelimit"] = limit
        if self.archive_file:
            params["download_archive"] = str(self.archive_file)
        return params
