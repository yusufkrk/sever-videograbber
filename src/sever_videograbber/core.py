"""Sever VideoGrabber çekirdeği: yt-dlp üzerine kurulu, iş parçacığı güvenli indirme motoru."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled, DownloadError

from .errors import GrabberError, friendly
from .options import DownloadOptions
from .platforms import Platform, detect_platform
from .tools import ytdlp_tool_params

ProgressCallback = Callable[["ProgressEvent"], None]
LogCallback = Callable[[str, str], None]  # (seviye, mesaj)


@dataclass
class ProgressEvent:
    """İndirme sırasında arayüze gönderilen durum bildirimi."""

    task_id: int
    url: str
    status: str  # queued | extracting | downloading | processing | finished | skipped | error
    platform: Platform
    title: str | None = None
    downloaded: int | None = None
    total: int | None = None
    speed: float | None = None
    eta: int | None = None
    phase: str | None = None  # "video" | "audio" | None
    item_index: int | None = None
    item_count: int | None = None
    message: str | None = None

    @property
    def fraction(self) -> float | None:
        if self.downloaded is not None and self.total:
            return min(self.downloaded / self.total, 1.0)
        return None


@dataclass
class MediaInfo:
    url: str
    platform: Platform
    id: str | None
    title: str | None
    uploader: str | None
    duration: float | None
    view_count: int | None
    upload_date: str | None
    thumbnail: str | None
    is_playlist: bool
    entry_count: int | None
    formats: list[dict[str, Any]]
    raw: dict[str, Any] = field(repr=False)


@dataclass
class DownloadResult:
    url: str
    platform: Platform
    title: str | None = None
    ok: bool = False
    skipped: bool = False
    files: list[Path] = field(default_factory=list)
    error: GrabberError | None = None
    warnings: list[str] = field(default_factory=list)
    item_errors: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def size(self) -> int:
        return sum(p.stat().st_size for p in self.files if p.exists())

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "platform": self.platform.key,
            "title": self.title,
            "ok": self.ok,
            "skipped": self.skipped,
            "files": [str(p) for p in self.files],
            "size": self.size,
            "error": str(self.error) if self.error else None,
            "error_code": self.error.code if self.error else None,
            "item_errors": self.item_errors,
            "elapsed": round(self.elapsed, 2),
        }


class _Collector:
    """yt-dlp'nin ``logger`` arayüzü: mesajları toplar, istenirse dışarı aktarır."""

    _SKIP_MARKERS = ("has already been recorded in the archive", "has already been downloaded")
    _NOISE = ("ffprobe not found", "ffprobe and ffmpeg not found")

    def __init__(self, on_log: LogCallback | None, verbose: bool) -> None:
        self.on_log = on_log
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.skip_seen = False

    def _emit(self, level: str, msg: str) -> None:
        if self.on_log:
            self.on_log(level, msg)

    def debug(self, msg: str) -> None:
        if any(m in msg for m in self._SKIP_MARKERS):
            self.skip_seen = True
        if self.verbose and not msg.startswith("[debug] "):
            self._emit("debug", msg)
        elif self.verbose and msg.startswith("[debug] "):
            self._emit("trace", msg)

    info = debug

    def warning(self, msg: str) -> None:
        if any(n in msg for n in self._NOISE):
            return
        self.warnings.append(msg)
        if self.verbose:
            self._emit("warning", msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        if self.verbose:
            self._emit("error", msg)


class VideoGrabber:
    """Yüksek seviyeli indirme API'si.

    :param options: İndirme ayarları (varsayılan: :class:`DownloadOptions()`).
    :param on_progress: Her durum değişikliğinde çağrılır. Birden fazla iş parçacığından
        çağrılabilir; geri çağırma işlevi iş parçacığı güvenli olmalıdır.
    :param on_log: ``(seviye, mesaj)`` alan günlük geri çağırması (``verbose`` ile).
    """

    def __init__(
        self,
        options: DownloadOptions | None = None,
        *,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        verbose: bool = False,
    ) -> None:
        self.options = options or DownloadOptions()
        self.on_progress = on_progress
        self.on_log = on_log
        self.verbose = verbose
        self._cancel = threading.Event()

    # ------------------------------------------------------------------ yardımcılar

    def cancel(self) -> None:
        """Devam eden tüm indirmeleri en kısa sürede durdurur."""
        self._cancel.set()

    def _emit(self, event: ProgressEvent) -> None:
        if self.on_progress:
            try:
                self.on_progress(event)
            except Exception:  # arayüz hatası indirmeyi bozmamalı
                pass

    def _base_params(self, collector: _Collector) -> dict[str, Any]:
        params = self.options.to_ydl_params()
        params.update(ytdlp_tool_params())
        params["logger"] = collector
        params["ignoreerrors"] = True  # hatalar collector'da toplanır, liste devam eder
        return params

    # ------------------------------------------------------------------ bilgi

    def get_info(self, url: str) -> MediaInfo:
        """İndirmeden medya bilgisini (başlık, süre, formatlar…) getirir."""
        collector = _Collector(self.on_log, self.verbose)
        params = self._base_params(collector)
        params.update({"skip_download": True, "extract_flat": "in_playlist", "noplaylist": False})
        params.pop("download_archive", None)
        params["postprocessors"] = []
        with YoutubeDL(params) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise friendly(collector.errors[-1] if collector.errors else "Unsupported URL")
        info = ydl.sanitize_info(info)
        is_playlist = info.get("_type") in ("playlist", "multi_video")
        entries = info.get("entries") or []
        return MediaInfo(
            url=url,
            platform=detect_platform(url),
            id=info.get("id"),
            title=info.get("title"),
            uploader=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
            duration=info.get("duration"),
            view_count=info.get("view_count"),
            upload_date=info.get("upload_date"),
            thumbnail=info.get("thumbnail"),
            is_playlist=is_playlist,
            entry_count=info.get("playlist_count") or (len(entries) if is_playlist else None),
            formats=[_simplify_format(f) for f in info.get("formats") or []],
            raw=info,
        )

    # ------------------------------------------------------------------ indirme

    def download(self, url: str, *, task_id: int = 0) -> DownloadResult:
        """Tek bir linki (video veya oynatma listesi) indirir. Asla istisna fırlatmaz
        (``KeyboardInterrupt`` hariç); sonuç :class:`DownloadResult` içinde döner."""
        platform = detect_platform(url)
        result = DownloadResult(url=url, platform=platform)
        collector = _Collector(self.on_log, self.verbose)
        started = time.monotonic()
        state: dict[str, Any] = {
            "title": None,
            "count": None,
            "is_playlist": False,
            "downloaded_any": False,
        }

        def event(status: str, **kw: Any) -> None:
            kw.setdefault("title", state["title"])
            kw.setdefault("item_count", state["count"])
            self._emit(ProgressEvent(task_id, url, status, platform, **kw))

        def progress_hook(d: dict[str, Any]) -> None:
            if self._cancel.is_set():
                raise DownloadCancelled()
            info = d.get("info_dict") or {}
            if d.get("status") == "downloading":
                state["downloaded_any"] = True
                phase = None
                if info.get("vcodec") == "none":
                    phase = "audio"
                elif info.get("acodec") == "none":
                    phase = "video"
                is_pl = state["is_playlist"]
                event(
                    "downloading",
                    title=state["title"] if is_pl else info.get("title") or state["title"],
                    downloaded=d.get("downloaded_bytes"),
                    total=d.get("total_bytes") or d.get("total_bytes_estimate"),
                    speed=d.get("speed"),
                    eta=d.get("eta"),
                    phase=phase,
                    item_index=info.get("playlist_index") if is_pl else None,
                    item_count=(info.get("n_entries") or info.get("playlist_count") or state["count"])
                    if is_pl
                    else None,
                )

        def pp_hook(d: dict[str, Any]) -> None:
            if d.get("status") == "started":
                event("processing", message=d.get("postprocessor"))

        def post_hook(path: str) -> None:
            p = Path(path)
            if p not in result.files:
                result.files.append(p)

        params = self._base_params(collector)
        params["progress_hooks"] = [progress_hook]
        params["postprocessor_hooks"] = [pp_hook]
        params["post_hooks"] = [post_hook]

        event("extracting")
        try:
            self.options.output_dir.mkdir(parents=True, exist_ok=True)
            with YoutubeDL(params) as ydl:
                info = ydl.extract_info(url, download=False, process=False)
                # Basit yönlendirmeleri (kısa linkler vb.) çöz ki türü doğru belirleyelim.
                hops = 0
                while info and info.get("_type") == "url" and hops < 5:
                    info = ydl.extract_info(
                        info["url"], download=False, process=False, ie_key=info.get("ie_key")
                    )
                    hops += 1
                if info:
                    if info.get("_type") in ("playlist", "multi_video"):
                        ydl.params["outtmpl"]["default"] = self.options.playlist_template
                        state["is_playlist"] = True
                        state["count"] = info.get("playlist_count")
                    state["title"] = info.get("title")
                    result.title = state["title"]
                    event("extracting")
                    ydl.process_ie_result(info, download=True)
        except DownloadCancelled:
            result.error = GrabberError("cancelled", code="cancelled")
        except DownloadError as exc:
            result.error = friendly(collector.errors[-1] if collector.errors else exc.msg or exc)
        except GrabberError as exc:
            result.error = exc
        except OSError as exc:
            result.error = friendly(str(exc))
        except Exception as exc:  # beklenmedik yt-dlp iç hataları
            result.error = friendly(f"{type(exc).__name__}: {exc}")

        result.elapsed = time.monotonic() - started
        result.warnings = collector.warnings
        if self._cancel.is_set() and not result.error:
            result.error = GrabberError("cancelled", code="cancelled")

        if result.error is None:
            if result.files:
                result.ok = True
                result.skipped = collector.skip_seen and not state["downloaded_any"]
                # oynatma listesinde bazı öğeler başarısız olduysa bildir
                result.item_errors = [friendly(e).args[0] for e in collector.errors]
            elif collector.skip_seen:
                result.ok = result.skipped = True
            elif collector.errors:
                result.error = friendly(collector.errors[-1])
                result.item_errors = [friendly(e).args[0] for e in collector.errors[:-1]]
            else:
                result.error = friendly("No video formats found")

        if result.title is None and result.files:
            result.title = result.files[0].stem
        if result.ok:
            event("skipped" if result.skipped else "finished", message=_files_label(result.files))
        else:
            event("error", message=str(result.error))
        return result

    def download_many(self, urls: Iterable[str], *, jobs: int = 1) -> list[DownloadResult]:
        """Birden çok linki indirir. ``jobs`` > 1 ise paralel çalışır. Sonuç sırası giriş
        sırasıyla aynıdır."""
        url_list = list(urls)
        for i, url in enumerate(url_list):
            self._emit(ProgressEvent(i, url, "queued", detect_platform(url)))
        results: list[DownloadResult | None] = [None] * len(url_list)
        jobs = max(1, min(jobs, len(url_list) or 1))

        if jobs == 1:
            for i, url in enumerate(url_list):
                if self._cancel.is_set():
                    break
                results[i] = self.download(url, task_id=i)
        else:
            pool = ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="grab")
            try:
                futures = {pool.submit(self.download, url, task_id=i): i for i, url in enumerate(url_list)}
                for fut in as_completed(futures):
                    results[futures[fut]] = fut.result()
            except KeyboardInterrupt:
                self.cancel()
                pool.shutdown(wait=True, cancel_futures=True)
                raise
            finally:
                pool.shutdown(wait=True)

        return [
            r
            if r is not None
            else DownloadResult(
                url=u,
                platform=detect_platform(u),
                error=GrabberError("cancelled", code="cancelled"),
            )
            for r, u in zip(results, url_list, strict=True)
        ]


def _files_label(files: list[Path]) -> str | None:
    if not files:
        return None
    return files[0].name if len(files) == 1 else f"{len(files)} files"


def _simplify_format(f: dict[str, Any]) -> dict[str, Any]:
    vcodec = f.get("vcodec")
    acodec = f.get("acodec")
    if vcodec == "none" and acodec not in (None, "none"):
        kind = "audio"
    elif acodec == "none" and vcodec not in (None, "none"):
        kind = "video"
    else:
        kind = "av"
    return {
        "format_id": f.get("format_id"),
        "ext": f.get("ext"),
        "kind": kind,
        "resolution": f.get("resolution") or (f"{f.get('height')}p" if f.get("height") else None),
        "height": f.get("height"),
        "fps": f.get("fps"),
        "vcodec": None if vcodec == "none" else vcodec,
        "acodec": None if acodec == "none" else acodec,
        "tbr": f.get("tbr"),
        "abr": f.get("abr"),
        "filesize": f.get("filesize") or f.get("filesize_approx"),
        "note": f.get("format_note"),
    }
