"""TOML ayar dosyası desteği.

Konum: ``VIDEOGRABBER_CONFIG`` ortam değişkeni veya işletim sistemine göre:

* Windows: ``%APPDATA%\\sever-videograbber\\config.toml``
* macOS:   ``~/Library/Application Support/sever-videograbber/config.toml``
* Linux:   ``~/.config/sever-videograbber/config.toml``
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

APP_DIR_NAME = "sever-videograbber"

DEFAULT_CONFIG = """\
# Sever VideoGrabber v3 ayar dosyası
# Komut satırı seçenekleri bu ayarları her zaman geçersiz kılar.
# Bir satırı etkinleştirmek için baştaki '#' işaretini kaldır.

# Arayüz dili: "tr" veya "en"
# lang = "tr"

# İndirilen dosyaların kaydedileceği klasör
# output_dir = "~/Downloads/Sever VideoGrabber"

# Video kalitesi: best, 2160, 1440, 1080, 720, 480, 360, 240, 144
# quality = "1080"

# Video kapsayıcısı: mp4 (en uyumlu), mkv, webm
# container = "mp4"

# Ses ayarları (--audio ile kullanılır): mp3, m4a, opus, flac, wav
# audio_format = "mp3"
# audio_quality = "192"

# Altyazı dilleri (videoya gömülür)
# subtitles = ["tr", "en"]
# auto_subtitles = false

# Kapak resmi ve meta verileri dosyaya göm
# embed_thumbnail = true
# embed_metadata = true

# Dosya adı şablonu (yt-dlp şablon sözdizimi)
# filename_template = "%(title).150B [%(id)s].%(ext)s"

# Instagram / X gibi giriş isteyen siteler için tarayıcı çerezleri: chrome, firefox, edge, brave…
# cookies_from_browser = "firefox"

# Aynı anda kaç link indirilsin
# jobs = 2

# Daha önce indirilenleri atlamak için arşiv dosyası
# archive_file = "~/Downloads/Sever VideoGrabber/arsiv.txt"

# proxy = "socks5://127.0.0.1:1080"
# rate_limit = "5M"
# retries = 10
"""


def config_path() -> Path:
    env = os.environ.get("VIDEOGRABBER_CONFIG")
    if env:
        return Path(env).expanduser()
    return Path(user_config_dir(APP_DIR_NAME, appauthor=False, roaming=True)) / "config.toml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Ayar dosyasını okur. Dosya yoksa boş sözlük döner; bozuksa ``ValueError`` fırlatır."""
    path = path or config_path()
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise ValueError(str(exc)) from exc


def write_default_config(path: Path | None = None, *, force: bool = False) -> tuple[Path, bool]:
    """Örnek ayar dosyasını yazar. ``(yol, yazıldı_mı)`` döner."""
    path = path or config_path()
    if path.exists() and not force:
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return path, True
