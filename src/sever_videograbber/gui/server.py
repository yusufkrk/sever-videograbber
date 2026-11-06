"""Arayüzün konuştuğu küçük yerel HTTP sunucusu (yalnızca 127.0.0.1).

Güvenlik: her API isteği, sayfaya gömülü rastgele bir jeton (``X-Token``) taşımak
zorundadır ve ``Host`` başlığı doğrulanır; böylece başka web siteleri bu sunucuya
istek gönderemez (CSRF / DNS rebinding koruması).
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .._version import __version__
from ..i18n import get_language, t, ui_strings
from ..options import AUDIO_FORMATS, QUALITIES, DownloadOptions
from ..platforms import dedupe, normalize_url
from .jobs import JobManager

BROWSERS = ("chrome", "firefox", "edge", "brave", "opera", "vivaldi", "chromium", "safari")


def open_path(path: Path, *, select: bool = False) -> None:
    """Dosyayı/klasörü işletim sisteminin dosya yöneticisinde açar."""
    path = path.resolve()
    if sys.platform == "win32":
        if select and path.is_file():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if select else ["open", str(path)])
    else:
        target = path.parent if select and path.is_file() else path
        subprocess.Popen(["xdg-open", str(target)])


class GuiServer:
    def __init__(self, conf: dict[str, Any] | None = None, *, max_parallel: int | None = None) -> None:
        self.conf = {k: v for k, v in (conf or {}).items() if k not in ("jobs", "lang")}
        parallel = max_parallel or int((conf or {}).get("jobs", 2))
        self.jobs = JobManager(max_parallel=parallel)
        self.token = secrets.token_urlsafe(24)
        self.pick_folder: Callable[[str], str | None] | None = None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> None:
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="gui-http", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.jobs.cancel_all()
        self.httpd.shutdown()
        self.httpd.server_close()

    # ------------------------------------------------------------------ yardımcılar

    def base_options(self) -> DownloadOptions:
        try:
            return DownloadOptions.from_dict(self.conf)
        except (ValueError, TypeError):
            return DownloadOptions()

    def bootstrap(self) -> dict[str, Any]:
        base = self.base_options()
        return {
            "token": self.token,
            "version": __version__,
            "lang": get_language(),
            "strings": ui_strings(),
            "native": self.pick_folder is not None,
            "defaults": {
                "output_dir": str(base.output_dir),
                "quality": base.quality,
                "audio_format": base.audio_format,
                "audio_only": base.audio_only,
                "browser": base.cookies_from_browser or "",
            },
            "qualities": list(QUALITIES),
            "audio_formats": list(AUDIO_FORMATS),
            "browsers": list(BROWSERS),
        }

    def render_index(self) -> bytes:
        html = resources.files("sever_videograbber.gui").joinpath("web/index.html").read_text("utf-8")
        boot = json.dumps(self.bootstrap(), ensure_ascii=False).replace("</", "<\\/")
        return html.replace("/*__BOOTSTRAP__*/null", boot).encode("utf-8")

    # ------------------------------------------------------------------ API

    def api(self, route: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if route == "/api/jobs":
            return 200, {"version": self.jobs.version, "jobs": self.jobs.snapshot()}

        if route == "/api/download":
            raw = str(body.get("text", ""))
            urls, invalid = [], []
            for part in raw.split():
                url = normalize_url(part)
                (urls if url else invalid).append(url or part)
            urls = dedupe(urls)
            if not urls:
                return 400, {"error": t("gui_no_valid_links")}
            changes: dict[str, Any] = {
                "audio_only": bool(body.get("audio_only")),
                "playlist": bool(body.get("playlist")),
            }
            for key in ("quality", "audio_format", "output_dir"):
                if body.get(key):
                    changes[key] = str(body[key])
            browser = str(body.get("browser") or "")
            changes["cookies_from_browser"] = browser if browser in BROWSERS else None
            try:
                opts = self.base_options().updated(**changes)
                if not browser:
                    opts.cookies_from_browser = None
            except (ValueError, TypeError) as exc:
                return 400, {"error": str(exc)}
            return 200, {"ids": self.jobs.add(urls, opts), "invalid": invalid}

        if route in ("/api/cancel", "/api/retry", "/api/remove"):
            job_id = str(body.get("id", ""))
            if route == "/api/cancel":
                return 200, {"ok": self.jobs.cancel(job_id)}
            if route == "/api/retry":
                return 200, {"id": self.jobs.retry(job_id)}
            self.jobs.remove(job_id)
            return 200, {"ok": True}

        if route == "/api/clear":
            self.jobs.clear_finished()
            return 200, {"ok": True}

        if route == "/api/open":
            job = self.jobs.get(str(body.get("id", "")))
            if body.get("id") is None:
                folder = Path(str(body.get("path", ""))).expanduser()
                if not folder.is_dir():
                    folder = self.base_options().output_dir
                folder.mkdir(parents=True, exist_ok=True)
                open_path(folder)
                return 200, {"ok": True}
            if not job or not job.files:
                return 404, {"error": "not found"}
            target = job.files[0]
            if body.get("target") == "file" and len(job.files) == 1 and target.exists():
                open_path(target)
            else:
                open_path(target, select=True) if target.exists() else open_path(target.parent)
            return 200, {"ok": True}

        if route == "/api/pick-folder":
            if not self.pick_folder:
                return 200, {"path": None, "supported": False}
            return 200, {"path": self.pick_folder(str(body.get("current", ""))), "supported": True}

        return 404, {"error": "unknown route"}

    # ------------------------------------------------------------------ HTTP

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_version = f"SeverVideoGrabber/{__version__}"

            def log_message(self, *args: Any) -> None:  # sessiz
                pass

            def _host_ok(self) -> bool:
                host = self.headers.get("Host", "")
                return host in (f"127.0.0.1:{server.port}", f"localhost:{server.port}")

            def _send(self, status: int, body: bytes, ctype: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, data: dict[str, Any]) -> None:
                self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

            def do_GET(self) -> None:
                if not self._host_ok():
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                path = urlparse(self.path).path
                if path in ("/", "/index.html"):
                    return self._send(200, server.render_index(), "text/html; charset=utf-8")
                if path == "/favicon.ico":
                    return self._send(204, b"", "image/x-icon")
                return self._json(404, {"error": "not found"})

            def do_POST(self) -> None:
                if not self._host_ok() or self.headers.get("X-Token") != server.token:
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                try:
                    length = min(int(self.headers.get("Content-Length") or 0), 1_000_000)
                    body = json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(body, dict):
                        raise ValueError
                except ValueError:
                    return self._json(400, {"error": "bad json"})
                try:
                    status, data = server.api(urlparse(self.path).path, body)
                except Exception as exc:  # arayüze hata dön, sunucuyu düşürme
                    status, data = 500, {"error": f"{type(exc).__name__}: {exc}"}
                self._json(status, data)

        return Handler
