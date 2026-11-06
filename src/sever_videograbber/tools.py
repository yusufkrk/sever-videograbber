"""Harici araçların (ffmpeg, JavaScript motoru) bulunması.

Kullanıcının hiçbir şey kurmasına gerek kalmaması için:

* ffmpeg sistemde yoksa ``imageio-ffmpeg`` paketinin içindeki hazır ffmpeg kullanılır.
* YouTube'un imza çözümü için gereken JS motoru olarak ``deno`` paketi (pip) kullanılır;
  bulunamazsa sistemdeki deno / node / bun denenir.
"""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    name: str
    path: str | None
    version: str | None
    source: str  # "system" | "bundled" | "missing"

    @property
    def found(self) -> bool:
        return self.path is not None


def _version_of(path: str, args: list[str]) -> str | None:
    try:
        out = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    first = out.strip().splitlines()[0] if out.strip() else ""
    match = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", first)
    return match.group(1) if match else (first or None)


@functools.lru_cache(maxsize=1)
def find_ffmpeg() -> Tool:
    system = shutil.which("ffmpeg")
    if system:
        return Tool("ffmpeg", system, _short_ffmpeg_version(system), "system")
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        return Tool("ffmpeg", bundled, _short_ffmpeg_version(bundled), "bundled")
    except Exception:
        return Tool("ffmpeg", None, None, "missing")


def _short_ffmpeg_version(path: str) -> str | None:
    line = _version_of(path, ["-version"])
    if not line:
        return None
    parts = line.split()
    return parts[2] if len(parts) > 2 and parts[0] == "ffmpeg" else line


def _frozen_binary(name: str) -> str | None:
    """PyInstaller ile paketlenmiş .exe içinde gelen ikili dosyayı bulur."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    candidate = os.path.join(base, name + (".exe" if sys.platform == "win32" else ""))
    return candidate if os.path.isfile(candidate) else None


@functools.lru_cache(maxsize=1)
def find_js_runtime() -> Tool:
    frozen = _frozen_binary("deno")
    if frozen:
        return Tool("deno", frozen, _version_of(frozen, ["--version"]), "bundled")
    try:
        from deno import find_deno_bin

        path = find_deno_bin()
        if path:
            return Tool("deno", path, _version_of(path, ["--version"]), "bundled")
    except Exception:
        pass
    for name in ("deno", "node", "bun"):
        path = shutil.which(name)
        if path:
            return Tool(name, path, _version_of(path, ["--version"]), "system")
    return Tool("js", None, None, "missing")


def ytdlp_tool_params() -> dict:
    """ffmpeg ve JS motoru için yt-dlp parametrelerini döndürür."""
    params: dict = {}
    ffmpeg = find_ffmpeg()
    if ffmpeg.found and ffmpeg.source == "bundled":
        params["ffmpeg_location"] = ffmpeg.path
    js = find_js_runtime()
    if js.found:
        params["js_runtimes"] = {js.name: {"path": js.path}}
    return params
