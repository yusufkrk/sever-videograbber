"""Tek dosyalık çalıştırılabilir (exe / binary) üretir.

Kullanım:
    pip install -e ".[dev]" deno
    python scripts/build_exe.py

Çıktı: dist/videograbber(.exe) — ffmpeg ve deno içinde gömülü gelir, kurulum gerektirmez.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    sep = os.pathsep
    args = [
        str(ROOT / "scripts" / "entry.py"),
        "--name=videograbber",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build'}",
        f"--specpath={ROOT / 'build'}",
        "--collect-data=imageio_ffmpeg",
        "--collect-binaries=imageio_ffmpeg",
        "--collect-data=yt_dlp_ejs",
        "--collect-submodules=yt_dlp",
        "--collect-submodules=sever_videograbber",
        "--copy-metadata=yt-dlp",
        "--collect-data=sever_videograbber",
    ]
    try:
        import webview  # noqa: F401

        args += ["--collect-submodules=webview", "--collect-data=webview", "--copy-metadata=pywebview"]
        if platform.system() == "Windows":
            args += ["--collect-all=pythonnet", "--collect-all=clr_loader"]
    except ImportError:
        print("! pywebview yok — exe arayüzü tarayıcıda açacak", file=sys.stderr)
    icon = ROOT / "assets" / "icon.ico"
    if icon.exists() and platform.system() == "Windows":
        args.append(f"--icon={icon}")

    try:
        from deno import find_deno_bin

        args.append(f"--add-binary={find_deno_bin()}{sep}.")
    except Exception:
        print("! deno bulunamadı — exe JS motoru olmadan derlenecek (pip install deno)", file=sys.stderr)

    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
