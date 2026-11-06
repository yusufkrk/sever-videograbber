"""Etkileşimli mod: terminal bilmeyen kullanıcılar için adım adım sihirbaz.

Program argümansız çalıştırıldığında (ör. .exe dosyasına çift tıklanınca) açılır.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from rich.markup import escape
from rich.prompt import Confirm, InvalidResponse, Prompt

from .core import VideoGrabber
from .i18n import get_language, t
from .options import AUDIO_FORMATS, DownloadOptions
from .platforms import dedupe, normalize_url
from .ui import ProgressUI, console, print_banner, print_summary

_QUALITY_CHOICES = ("best", "2160", "1080", "720", "480", "360")
_PLAYLIST_HINTS = ("list=", "/playlist", "/sets/", "/album/", "/channel/", "/@", "/c/", "/user/")


class _YesNo(Confirm):
    """Dile göre e/h veya y/n kabul eden onay sorusu."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.choices = ["e", "h"] if get_language() == "tr" else ["y", "n"]

    def process_response(self, value: str) -> bool:
        value = value.strip().lower()
        if value in ("e", "evet", "y", "yes"):
            return True
        if value in ("h", "hayır", "hayir", "n", "no"):
            return False
        raise InvalidResponse(self.validate_error_message)


def _choose(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    """Numaralı bir menü gösterir ve seçilen değerin anahtarını döndürür."""
    for i, (_, label) in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}[/]) {label}")
    keys = [k for k, _ in options]
    default_idx = str(keys.index(default) + 1)
    answer = Prompt.ask(
        f"[bold]{prompt}[/]",
        choices=[str(i) for i in range(1, len(keys) + 1)],
        default=default_idx,
        show_choices=False,
        console=console,
    )
    return keys[int(answer) - 1]


def _ask_urls() -> list[str]:
    console.print(f"[dim]{t('i_empty_exit')}[/]")
    raw = Prompt.ask(
        f"[bold #ff5b4a]🔗 {t('i_url_prompt')}[/]", default="", show_default=False, console=console
    )
    urls = []
    for part in raw.split():
        url = normalize_url(part)
        if url:
            urls.append(url)
        else:
            console.print(f"[yellow]⚠ {t('invalid_url', url=escape(part))}[/]")
    return dedupe(urls)


def run_interactive(conf: dict[str, Any]) -> int:
    print_banner()
    console.print(f"[bold]{t('i_welcome')}[/]\n")
    base = DownloadOptions.from_dict({k: v for k, v in conf.items() if k not in ("jobs", "lang")})
    jobs = max(1, int(conf.get("jobs", 2)))
    exit_code = 0

    try:
        while True:
            urls = _ask_urls()
            if not urls:
                break

            kind = _choose(
                t("i_type_prompt"),
                [("video", f"🎬 {t('i_type_video')}"), ("audio", f"🎵 {t('i_type_audio')}")],
                "audio" if base.audio_only else "video",
            )
            changes: dict[str, Any] = {"audio_only": kind == "audio"}
            if kind == "video":
                labels = [(q, t("best") if q == "best" else f"{q}p") for q in _QUALITY_CHOICES]
                default_q = base.quality if base.quality in _QUALITY_CHOICES else "best"
                changes["quality"] = _choose(t("i_quality_prompt"), labels, default_q)
            else:
                labels = [(f, f.upper()) for f in AUDIO_FORMATS]
                changes["audio_format"] = _choose(t("i_audio_fmt_prompt"), labels, base.audio_format)

            folder = Prompt.ask(
                f"[bold]📁 {t('i_folder_prompt')}[/]", default=str(base.output_dir), console=console
            )
            changes["output_dir"] = folder

            if any(h in u for u in urls for h in _PLAYLIST_HINTS):
                changes["playlist"] = _YesNo.ask(
                    f"[bold]{t('i_playlist_prompt')}[/]", default=False, console=console
                )

            opts = base.updated(**changes)
            base = opts  # bir sonraki tur için seçimleri hatırla
            console.print()
            started = time.monotonic()
            ui = ProgressUI()
            grabber = VideoGrabber(opts, on_progress=ui.handle)
            try:
                with ui:
                    results = grabber.download_many(urls, jobs=jobs)
            except KeyboardInterrupt:
                grabber.cancel()
                console.print(f"\n[yellow]{t('interrupted')}[/]")
                results = []
            print_summary(results, time.monotonic() - started)
            if results and not all(r.ok for r in results):
                exit_code = 1
            console.print()
            if not _YesNo.ask(f"[bold]{t('i_again')}[/]", default=True, console=console):
                break
            console.print()
    except (KeyboardInterrupt, EOFError):
        console.print()

    console.print(f"[bold #ff5b4a]{t('i_bye')}[/]")
    if getattr(sys, "frozen", False):  # .exe çift tıklamayla açıldıysa pencere hemen kapanmasın
        try:
            input(t("i_press_enter"))
        except (KeyboardInterrupt, EOFError):
            pass
    return exit_code
