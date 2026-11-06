"""Basit çok dilli (Türkçe / English) mesaj desteği.

Dil seçimi sırası: ``--lang`` → ``VIDEOGRABBER_LANG`` ortam değişkeni → sistem dili → Türkçe.
"""

from __future__ import annotations

import locale
import os

_MESSAGES: dict[str, dict[str, str]] = {
    "tr": {
        "tagline": "YouTube · Instagram · X/Twitter · TikTok · 1000+ site",
        # genel
        "no_urls": "İndirilecek link bulunamadı. Örnek: videograbber https://youtu.be/...",
        "invalid_url": "Geçersiz link atlandı: {url}",
        "file_not_found": "Dosya bulunamadı: {path}",
        "interrupted": "İptal edildi.",
        "saved_to": "Kayıt klasörü",
        "settings": "Ayarlar",
        "mode_video": "Video ({quality}, {container})",
        "mode_audio": "Ses ({fmt}, {kbps} kbps)",
        "best": "en iyi",
        # durumlar
        "st_queued": "Sırada",
        "st_extracting": "Bilgi alınıyor…",
        "st_downloading": "İndiriliyor",
        "st_processing": "İşleniyor…",
        "st_finished": "Tamamlandı",
        "st_skipped": "Zaten indirilmiş",
        "st_error": "Hata",
        "phase_video": "video",
        "phase_audio": "ses",
        # özet
        "summary_title": "Özet",
        "col_title": "Başlık",
        "col_platform": "Platform",
        "col_status": "Durum",
        "col_size": "Boyut",
        "col_file": "Dosya",
        "summary_line": "{ok} başarılı, {fail} başarısız — {elapsed}",
        "open_folder_hint": "Dosyalar: {path}",
        # info
        "info_uploader": "Yükleyen",
        "info_duration": "Süre",
        "info_views": "İzlenme",
        "info_date": "Tarih",
        "info_entries": "Video sayısı",
        "info_formats": "Formatlar",
        "info_playlist": "Oynatma listesi",
        "col_id": "ID",
        "col_ext": "Uzantı",
        "col_res": "Çözünürlük",
        "col_fps": "FPS",
        "col_codec": "Codec",
        "col_bitrate": "Bitrate",
        # doctor
        "doctor_title": "Sistem Kontrolü",
        "doctor_ok": "Her şey hazır! İndirmeye başlayabilirsin.",
        "doctor_missing_ffmpeg": "ffmpeg bulunamadı — video+ses birleştirme ve MP3 dönüştürme çalışmaz.",
        "doctor_missing_js": "JavaScript motoru bulunamadı — bazı YouTube formatları eksik olabilir. "
        "`pip install deno` ile kurabilirsin.",
        "doctor_component": "Bileşen",
        "doctor_version": "Sürüm",
        "doctor_location": "Konum",
        "src_system": "sistem",
        "src_bundled": "dahili",
        "src_missing": "YOK",
        # config
        "config_created": "Ayar dosyası oluşturuldu: {path}",
        "config_exists": "Ayar dosyası zaten var: {path} (üzerine yazmak için --force)",
        "config_none": "Henüz ayar dosyası yok. Oluşturmak için: videograbber config --init",
        "config_invalid": "Ayar dosyası okunamadı ({path}): {error}",
        # interaktif
        "i_welcome": "Linki yapıştır ve Enter'a bas. Birden fazla link için aralarına boşluk koy.",
        "i_url_prompt": "Link(ler)",
        "i_empty_exit": "(Çıkmak için boş bırakıp Enter'a bas)",
        "i_type_prompt": "Ne indirilsin?",
        "i_type_video": "Video",
        "i_type_audio": "Sadece ses (MP3 vb.)",
        "i_quality_prompt": "Kalite",
        "i_audio_fmt_prompt": "Ses formatı",
        "i_folder_prompt": "Kayıt klasörü",
        "i_playlist_prompt": "Bu bir oynatma listesi gibi görünüyor. Tüm listeyi indireyim mi?",
        "i_again": "Başka bir şey indirmek ister misin?",
        "i_bye": "Görüşürüz! 👋",
        "i_press_enter": "Kapatmak için Enter'a bas…",
        # hatalar
        "err_unsupported": "Bu link desteklenmiyor veya içinde video bulunamadı.",
        "err_private": "Bu içerik gizli / özel. Erişim için giriş yapmış çerezler gerekiyor.",
        "err_login": "Bu platform giriş istiyor. Tarayıcında giriş yapıp şunu dene: --browser chrome "
        "(veya firefox, edge, brave…)",
        "err_bot": "Platform bot doğrulaması istedi. --browser chrome ile tarayıcı çerezlerini kullanmayı dene.",
        "err_age": "Yaş kısıtlamalı içerik. --browser chrome ile giriş yapılmış çerezleri kullan.",
        "err_geo": "Bu içerik senin ülkende engellenmiş. --proxy ile farklı bir bölge dene.",
        "err_removed": "İçerik kaldırılmış veya artık mevcut değil.",
        "err_ratelimit": "Platform çok fazla istek gönderildiğini söylüyor (429). Biraz bekleyip tekrar dene.",
        "err_network": "Bağlantı hatası. İnternetini kontrol edip tekrar dene.",
        "err_ffmpeg": "ffmpeg hatası. `videograbber doctor` komutuyla sistemini kontrol et.",
        "err_live": "Canlı yayın henüz başlamadı veya indirilemiyor.",
        "err_cookie_db": "Tarayıcı çerezleri okunamadı. Tarayıcıyı tamamen kapatıp tekrar dene.",
        "err_generic": "Beklenmeyen hata: {msg}",
    },
    "en": {
        "tagline": "YouTube · Instagram · X/Twitter · TikTok · 1000+ sites",
        "no_urls": "No links to download. Example: videograbber https://youtu.be/...",
        "invalid_url": "Skipped invalid link: {url}",
        "file_not_found": "File not found: {path}",
        "interrupted": "Cancelled.",
        "saved_to": "Output folder",
        "settings": "Settings",
        "mode_video": "Video ({quality}, {container})",
        "mode_audio": "Audio ({fmt}, {kbps} kbps)",
        "best": "best",
        "st_queued": "Queued",
        "st_extracting": "Fetching info…",
        "st_downloading": "Downloading",
        "st_processing": "Processing…",
        "st_finished": "Done",
        "st_skipped": "Already downloaded",
        "st_error": "Error",
        "phase_video": "video",
        "phase_audio": "audio",
        "summary_title": "Summary",
        "col_title": "Title",
        "col_platform": "Platform",
        "col_status": "Status",
        "col_size": "Size",
        "col_file": "File",
        "summary_line": "{ok} succeeded, {fail} failed — {elapsed}",
        "open_folder_hint": "Files: {path}",
        "info_uploader": "Uploader",
        "info_duration": "Duration",
        "info_views": "Views",
        "info_date": "Date",
        "info_entries": "Entries",
        "info_formats": "Formats",
        "info_playlist": "Playlist",
        "col_id": "ID",
        "col_ext": "Ext",
        "col_res": "Resolution",
        "col_fps": "FPS",
        "col_codec": "Codec",
        "col_bitrate": "Bitrate",
        "doctor_title": "System Check",
        "doctor_ok": "All set! You're ready to download.",
        "doctor_missing_ffmpeg": "ffmpeg not found — merging video+audio and MP3 conversion won't work.",
        "doctor_missing_js": "No JavaScript runtime found — some YouTube formats may be missing. "
        "Install one with `pip install deno`.",
        "doctor_component": "Component",
        "doctor_version": "Version",
        "doctor_location": "Location",
        "src_system": "system",
        "src_bundled": "bundled",
        "src_missing": "MISSING",
        "config_created": "Config file created: {path}",
        "config_exists": "Config file already exists: {path} (use --force to overwrite)",
        "config_none": "No config file yet. Create one with: videograbber config --init",
        "config_invalid": "Could not read config file ({path}): {error}",
        "i_welcome": "Paste a link and press Enter. Separate multiple links with spaces.",
        "i_url_prompt": "Link(s)",
        "i_empty_exit": "(Leave empty and press Enter to quit)",
        "i_type_prompt": "What to download?",
        "i_type_video": "Video",
        "i_type_audio": "Audio only (MP3 etc.)",
        "i_quality_prompt": "Quality",
        "i_audio_fmt_prompt": "Audio format",
        "i_folder_prompt": "Output folder",
        "i_playlist_prompt": "This looks like a playlist. Download the whole list?",
        "i_again": "Download something else?",
        "i_bye": "See you! 👋",
        "i_press_enter": "Press Enter to close…",
        "err_unsupported": "This link is not supported or contains no video.",
        "err_private": "This content is private. Logged-in cookies are required.",
        "err_login": "This platform requires login. Log in with your browser and try: --browser chrome "
        "(or firefox, edge, brave…)",
        "err_bot": "The platform asked for bot verification. Try --browser chrome to use your browser cookies.",
        "err_age": "Age-restricted content. Use --browser chrome with a logged-in browser.",
        "err_geo": "This content is blocked in your country. Try a different region with --proxy.",
        "err_removed": "The content was removed or is no longer available.",
        "err_ratelimit": "The platform says too many requests (429). Wait a bit and try again.",
        "err_network": "Network error. Check your connection and try again.",
        "err_ffmpeg": "ffmpeg error. Run `videograbber doctor` to check your setup.",
        "err_live": "The live stream hasn't started yet or can't be downloaded.",
        "err_cookie_db": "Could not read browser cookies. Fully close the browser and try again.",
        "err_generic": "Unexpected error: {msg}",
    },
}

SUPPORTED_LANGS = tuple(_MESSAGES)
_current = "tr"


def detect_language() -> str:
    env = os.environ.get("VIDEOGRABBER_LANG", "").lower()[:2]
    if env in _MESSAGES:
        return env
    try:
        loc = (locale.getlocale()[0] or "").lower()
    except ValueError:
        loc = ""
    if loc.startswith(("tr", "turkish")):
        return "tr"
    if loc:
        return "en"
    return "tr"


def set_language(lang: str | None) -> str:
    global _current
    _current = (lang or detect_language()).lower()[:2]
    if _current not in _MESSAGES:
        _current = "en"
    return _current


def get_language() -> str:
    return _current


def t(key: str, **kwargs: object) -> str:
    text = _MESSAGES[_current].get(key) or _MESSAGES["tr"].get(key) or key
    return text.format(**kwargs) if kwargs else text
