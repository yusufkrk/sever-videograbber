"""Kurulum gerektirmeyen programı derler. ffmpeg ve deno içinde gömülü gelir.

Kullanım:
    pip install ".[dev]"
    python scripts/build_exe.py

Çıktı:
    Windows: dist/videograbber.exe                 (tek dosya, çift tıkla → pencere)
    Linux:   dist/videograbber                     (tek dosya)
    macOS:   dist/Sever VideoGrabber.app           (çift tıklanabilir uygulama)
             dist/SeverVideoGrabber.zip            (dağıtım için, ditto ile paketlenmiş)
"""

from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_NAME = "Sever VideoGrabber"
BUNDLE_ID = "io.github.yusufkrk.severvideograbber"
IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"


def version() -> str:
    ns: dict[str, str] = {}
    exec((ROOT / "src" / "sever_videograbber" / "_version.py").read_text(), ns)
    return ns["__version__"]


def pyinstaller_args() -> list[str]:
    sep = os.pathsep
    args = [
        str(ROOT / "scripts" / "entry.py"),
        "--noconfirm",
        "--clean",
        f"--distpath={DIST}",
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
    if IS_MAC:
        # .app paketi: Finder'dan çift tıklanır, arkada Terminal açılmaz.
        args += [f"--name={APP_NAME}", "--onedir", "--windowed", f"--osx-bundle-identifier={BUNDLE_ID}"]
        icon = ROOT / "docs" / "images" / "icon.icns"
    else:
        # Windows'ta konsol açık derlenir ki komut satırından da çalışsın;
        # çift tıklamayla açılınca konsol kendini gizler (gui._hide_own_console).
        args += ["--name=videograbber", "--onefile", "--console"]
        icon = ROOT / "docs" / "images" / "icon.ico"
    if icon.exists() and (IS_MAC or IS_WIN):
        args.append(f"--icon={icon}")

    try:
        import webview  # noqa: F401

        args += ["--collect-submodules=webview", "--collect-data=webview", "--copy-metadata=pywebview"]
        if IS_WIN:
            args += ["--collect-all=pythonnet", "--collect-all=clr_loader"]
    except ImportError:
        print("! pywebview yok — program arayüzü tarayıcıda açacak", file=sys.stderr)

    try:
        from deno import find_deno_bin

        args.append(f"--add-binary={find_deno_bin()}{sep}.")
    except Exception:
        print("! deno bulunamadı — JS motoru olmadan derlenecek (pip install deno)", file=sys.stderr)
    return args


def finish_mac_app() -> None:
    app = DIST / f"{APP_NAME}.app"
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as fh:
        info = plistlib.load(fh)
    ver = version()
    info.update(
        {
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleShortVersionString": ver,
            "CFBundleVersion": ver,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHumanReadableCopyright": "MIT License — github.com/yusufkrk/sever-videograbber",
        }
    )
    with plist_path.open("wb") as fh:
        plistlib.dump(info, fh)
    # Info.plist değişince imza bozulur: ad-hoc olarak yeniden imzala (Apple Silicon şartı).
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    archive = DIST / "SeverVideoGrabber.zip"
    archive.unlink(missing_ok=True)
    # ditto, sembolik bağlantıları ve izinleri koruyarak .app'i zipler (Finder ile aynı).
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(archive)], check=True)
    print(f"✔ {app}\n✔ {archive}")


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    PyInstaller.__main__.run(pyinstaller_args())
    if IS_MAC:
        finish_mac_app()


if __name__ == "__main__":
    main()
