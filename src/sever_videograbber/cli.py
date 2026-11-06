"""Komut satırı arayüzü.

videograbber URL [URL ...] [seçenekler]     # indir (varsayılan komut)
videograbber info URL [--formats] [--json]  # bilgi göster
videograbber doctor                         # sistem kontrolü
videograbber config [--init|--path|--show]  # ayar dosyası
videograbber                                # etkileşimli mod
"""

from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import sys
import time
from pathlib import Path
from typing import Any

from rich.markup import escape

from . import config as cfg
from ._version import __version__
from .core import VideoGrabber
from .errors import GrabberError
from .i18n import SUPPORTED_LANGS, set_language, t
from .options import AUDIO_BITRATES, AUDIO_FORMATS, CONTAINERS, QUALITIES, DownloadOptions
from .platforms import dedupe, normalize_url, read_url_file
from .tools import find_ffmpeg, find_js_runtime
from .ui import ProgressUI, console, err_console, print_banner, print_info, print_settings, print_summary

COMMANDS = ("download", "info", "doctor", "config", "gui", "wizard")
EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_INTERRUPT = 0, 1, 2, 130

_HELP: dict[str, dict[str, str]] = {
    "tr": {
        "desc": "Sever VideoGrabber v3 — YouTube, Instagram, X/Twitter, TikTok ve 1000+ siteden "
        "video & ses indir. Argümansız çalıştırılırsa masaüstü penceresi açılır.",
        "epilog": "Örnekler:\n"
        "  videograbber https://youtu.be/dQw4w9WgXcQ\n"
        "  videograbber -q 720 URL1 URL2\n"
        "  videograbber -a --audio-format mp3 URL          (sadece ses)\n"
        "  videograbber -p URL                             (tüm oynatma listesi)\n"
        "  videograbber -i linkler.txt -j 3                (dosyadan, 3 paralel)\n"
        "  videograbber --browser chrome INSTAGRAM_URL     (giriş isteyen siteler)\n"
        "  videograbber info --formats URL\n"
        "  videograbber doctor",
        "cmd_download": "link(ler)i indir (varsayılan komut)",
        "cmd_info": "indirmeden bilgi göster",
        "cmd_doctor": "sistem kontrolü (ffmpeg, JS motoru, sürümler)",
        "cmd_config": "ayar dosyasını yönet",
        "cmd_gui": "masaüstü penceresini aç (argümansız çalıştırmayla aynı)",
        "cmd_wizard": "terminalde adım adım sihirbaz",
        "gui_web": "pencere yerine varsayılan tarayıcıda aç",
        "urls": "indirilecek link(ler); '-' stdin'den okur",
        "g_output": "Çıktı",
        "g_format": "Format & kalite",
        "g_extra": "Altyazı, kapak, meta veri",
        "g_net": "Ağ & giriş",
        "g_general": "Genel",
        "output": "kayıt klasörü",
        "template": "dosya adı şablonu (yt-dlp sözdizimi)",
        "archive": "arşiv dosyası: daha önce indirilenleri atla",
        "overwrite": "var olan dosyaların üzerine yaz",
        "restrict": "dosya adlarında sadece ASCII karakter kullan",
        "quality": "video kalitesi (varsayılan: best)",
        "audio": "sadece sesi indir",
        "audio_format": "ses formatı (varsayılan: mp3)",
        "audio_quality": "ses kalitesi kbps (varsayılan: 192)",
        "container": "video kapsayıcısı (varsayılan: mp4)",
        "playlist": "link bir listedeyse tüm oynatma listesini indir",
        "items": "listeden seçili öğeler, örn. '1-5,8,-1'",
        "subs": "altyazı dilleri, örn. 'tr,en' (videoya gömülür)",
        "auto_subs": "otomatik oluşturulan altyazıları da al",
        "no_thumb": "kapak resmini gömme",
        "no_meta": "meta verileri gömme",
        "browser": "çerezleri tarayıcıdan al (chrome, firefox, edge, brave, opera…)",
        "cookies": "Netscape formatında cookies.txt dosyası",
        "proxy": "proxy adresi, örn. socks5://127.0.0.1:1080",
        "rate": "hız limiti, örn. 2M veya 500K",
        "retries": "yeniden deneme sayısı (varsayılan: 10)",
        "input": "linkleri dosyadan oku (her satıra bir link)",
        "jobs": "aynı anda kaç link indirilsin (varsayılan: 1)",
        "json": "sonuçları JSON olarak yazdır (betikler için)",
        "verbose": "ayrıntılı günlük",
        "quiet": "sadece hataları ve özeti göster",
        "lang": "arayüz dili",
        "formats": "tüm formatları listele",
        "c_init": "örnek ayar dosyası oluştur",
        "c_force": "var olan dosyanın üzerine yaz",
        "c_path": "ayar dosyasının yolunu yazdır",
        "c_show": "geçerli ayarları göster",
        "version": "sürümü göster",
        "help": "bu yardımı göster",
    },
    "en": {
        "desc": "Sever VideoGrabber v3 — download video & audio from YouTube, Instagram, X/Twitter, "
        "TikTok and 1000+ sites. Run without arguments to open the desktop window.",
        "epilog": "Examples:\n"
        "  videograbber https://youtu.be/dQw4w9WgXcQ\n"
        "  videograbber -q 720 URL1 URL2\n"
        "  videograbber -a --audio-format mp3 URL          (audio only)\n"
        "  videograbber -p URL                             (whole playlist)\n"
        "  videograbber -i links.txt -j 3                  (from file, 3 in parallel)\n"
        "  videograbber --browser chrome INSTAGRAM_URL     (sites that need login)\n"
        "  videograbber info --formats URL\n"
        "  videograbber doctor",
        "cmd_download": "download link(s) (default command)",
        "cmd_info": "show info without downloading",
        "cmd_doctor": "system check (ffmpeg, JS runtime, versions)",
        "cmd_config": "manage the config file",
        "cmd_gui": "open the desktop window (same as running without arguments)",
        "cmd_wizard": "step-by-step wizard in the terminal",
        "gui_web": "open in your default browser instead of a window",
        "urls": "link(s) to download; '-' reads from stdin",
        "g_output": "Output",
        "g_format": "Format & quality",
        "g_extra": "Subtitles, thumbnail, metadata",
        "g_net": "Network & login",
        "g_general": "General",
        "output": "output folder",
        "template": "filename template (yt-dlp syntax)",
        "archive": "archive file: skip already downloaded items",
        "overwrite": "overwrite existing files",
        "restrict": "use ASCII-only filenames",
        "quality": "video quality (default: best)",
        "audio": "download audio only",
        "audio_format": "audio format (default: mp3)",
        "audio_quality": "audio quality in kbps (default: 192)",
        "container": "video container (default: mp4)",
        "playlist": "download the whole playlist if the link is part of one",
        "items": "playlist items, e.g. '1-5,8,-1'",
        "subs": "subtitle languages, e.g. 'en,tr' (embedded)",
        "auto_subs": "include auto-generated subtitles",
        "no_thumb": "don't embed the thumbnail",
        "no_meta": "don't embed metadata",
        "browser": "load cookies from a browser (chrome, firefox, edge, brave, opera…)",
        "cookies": "cookies.txt file in Netscape format",
        "proxy": "proxy URL, e.g. socks5://127.0.0.1:1080",
        "rate": "rate limit, e.g. 2M or 500K",
        "retries": "number of retries (default: 10)",
        "input": "read links from a file (one per line)",
        "jobs": "number of links to download in parallel (default: 1)",
        "json": "print results as JSON (for scripts)",
        "verbose": "verbose logging",
        "quiet": "only show errors and the summary",
        "lang": "interface language",
        "formats": "list all formats",
        "c_init": "create an example config file",
        "c_force": "overwrite an existing file",
        "c_path": "print the config file path",
        "c_show": "show the current settings",
        "version": "show version",
        "help": "show this help",
    },
}


def _h(key: str) -> str:
    from .i18n import get_language

    return _HELP.get(get_language(), _HELP["en"])[key]


# ----------------------------------------------------------------------- parser


def _common(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group(_h("g_general"))
    g.add_argument("-v", "--verbose", action="store_true", help=_h("verbose"))
    g.add_argument("--quiet", action="store_true", help=_h("quiet"))
    g.add_argument("--lang", choices=SUPPORTED_LANGS, help=_h("lang"))
    g.add_argument("-h", "--help", action="help", help=_h("help"))


def _network(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group(_h("g_net"))
    g.add_argument("--browser", dest="cookies_from_browser", metavar="NAME", help=_h("browser"))
    g.add_argument("--cookies", dest="cookies_file", metavar="FILE", help=_h("cookies"))
    g.add_argument("--proxy", metavar="URL", help=_h("proxy"))
    g.add_argument("--rate-limit", dest="rate_limit", metavar="RATE", help=_h("rate"))
    g.add_argument("--retries", type=int, metavar="N", help=_h("retries"))


def build_parser() -> argparse.ArgumentParser:
    fmt = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="videograbber",
        description=_h("desc"),
        epilog=_h("epilog"),
        formatter_class=fmt,
        add_help=False,
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"Sever VideoGrabber {__version__}", help=_h("version")
    )
    parser.add_argument("-h", "--help", action="help", help=_h("help"))
    sub = parser.add_subparsers(dest="command", metavar="{download,info,doctor,config,gui,wizard}")

    # download --------------------------------------------------------------
    d = sub.add_parser(
        "download",
        help=_h("cmd_download"),
        description=_h("desc"),
        epilog=_h("epilog"),
        formatter_class=fmt,
        add_help=False,
    )
    d.add_argument("urls", nargs="*", metavar="URL", help=_h("urls"))

    g = d.add_argument_group(_h("g_output"))
    g.add_argument("-o", "--output", dest="output_dir", metavar="DIR", help=_h("output"))
    g.add_argument("-t", "--template", dest="filename_template", metavar="TPL", help=_h("template"))
    g.add_argument("--archive", dest="archive_file", metavar="FILE", help=_h("archive"))
    g.add_argument("--overwrite", action="store_true", default=None, help=_h("overwrite"))
    g.add_argument(
        "--ascii-names", dest="restrict_filenames", action="store_true", default=None, help=_h("restrict")
    )

    g = d.add_argument_group(_h("g_format"))
    g.add_argument(
        "-q",
        "--quality",
        choices=QUALITIES,
        metavar="{" + ",".join(QUALITIES) + "}",
        type=lambda s: s.lower().removesuffix("p"),
        help=_h("quality"),
    )
    g.add_argument("-a", "--audio", dest="audio_only", action="store_true", default=None, help=_h("audio"))
    g.add_argument("--audio-format", choices=AUDIO_FORMATS, type=str.lower, help=_h("audio_format"))
    g.add_argument("--audio-quality", metavar="{" + ",".join(AUDIO_BITRATES) + "}", help=_h("audio_quality"))
    g.add_argument("-c", "--container", choices=CONTAINERS, type=str.lower, help=_h("container"))
    g.add_argument("-p", "--playlist", action="store_true", default=None, help=_h("playlist"))
    g.add_argument("--items", dest="playlist_items", metavar="SPEC", help=_h("items"))

    g = d.add_argument_group(_h("g_extra"))
    g.add_argument("-s", "--subs", dest="subtitles", metavar="LANGS", help=_h("subs"))
    g.add_argument(
        "--auto-subs", dest="auto_subtitles", action="store_true", default=None, help=_h("auto_subs")
    )
    g.add_argument(
        "--no-thumbnail", dest="embed_thumbnail", action="store_false", default=None, help=_h("no_thumb")
    )
    g.add_argument(
        "--no-metadata", dest="embed_metadata", action="store_false", default=None, help=_h("no_meta")
    )

    _network(d)

    g = d.add_argument_group(_h("g_general"))
    g.add_argument("-i", "--input", dest="input_file", metavar="FILE", help=_h("input"))
    g.add_argument("-j", "--jobs", type=int, metavar="N", help=_h("jobs"))
    g.add_argument("--json", action="store_true", help=_h("json"))
    g.add_argument("-v", "--verbose", action="store_true", help=_h("verbose"))
    g.add_argument("--quiet", action="store_true", help=_h("quiet"))
    g.add_argument("--lang", choices=SUPPORTED_LANGS, help=_h("lang"))
    g.add_argument("-h", "--help", action="help", help=_h("help"))

    # info ------------------------------------------------------------------
    i = sub.add_parser("info", help=_h("cmd_info"), add_help=False)
    i.add_argument("url", metavar="URL")
    i.add_argument("-f", "--formats", action="store_true", help=_h("formats"))
    i.add_argument("--json", action="store_true", help=_h("json"))
    _network(i)
    _common(i)

    # doctor ----------------------------------------------------------------
    doc = sub.add_parser("doctor", help=_h("cmd_doctor"), add_help=False)
    _common(doc)

    # config ----------------------------------------------------------------
    c = sub.add_parser("config", help=_h("cmd_config"), add_help=False)
    mx = c.add_mutually_exclusive_group()
    mx.add_argument("--init", action="store_true", help=_h("c_init"))
    mx.add_argument("--path", action="store_true", help=_h("c_path"))
    mx.add_argument("--show", action="store_true", help=_h("c_show"))
    c.add_argument("--force", action="store_true", help=_h("c_force"))
    _common(c)

    # gui / wizard ----------------------------------------------------------
    gp = sub.add_parser("gui", help=_h("cmd_gui"), add_help=False)
    gp.add_argument("--web", action="store_true", help=_h("gui_web"))
    gp.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    _common(gp)
    wz = sub.add_parser("wizard", help=_h("cmd_wizard"), add_help=False)
    _common(wz)
    return parser


# ----------------------------------------------------------------------- yardımcılar


def _prescan_lang(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
    return None


def _load_config_safely() -> dict[str, Any]:
    try:
        return cfg.load_config()
    except ValueError as exc:
        err_console.print(f"[yellow]⚠ {t('config_invalid', path=cfg.config_path(), error=exc)}[/]")
        return {}


def build_options(args: argparse.Namespace, conf: dict[str, Any]) -> DownloadOptions:
    base = DownloadOptions.from_dict(conf)
    overrides = {k: v for k, v in vars(args).items() if v is not None}
    return base.updated(**overrides)


def collect_urls(args: argparse.Namespace) -> list[str]:
    raw: list[str] = []
    for item in args.urls:
        if item == "-":
            raw.extend(sys.stdin.read().split())
        else:
            raw.extend(item.split())
    urls: list[str] = []
    for item in raw:
        url = normalize_url(item)
        if url:
            urls.append(url)
        else:
            err_console.print(f"[yellow]⚠ {t('invalid_url', url=escape(item))}[/]")
    if args.input_file:
        path = Path(args.input_file).expanduser()
        if not path.is_file():
            raise GrabberError(t("file_not_found", path=path), code="usage")
        urls.extend(read_url_file(str(path)))
    return dedupe(urls)


# ----------------------------------------------------------------------- komutlar


def cmd_download(args: argparse.Namespace, conf: dict[str, Any]) -> int:
    try:
        urls = collect_urls(args)
    except GrabberError as exc:
        err_console.print(f"[red]✖ {exc}[/]")
        return EXIT_USAGE
    if not urls:
        err_console.print(f"[red]✖ {t('no_urls')}[/]")
        return EXIT_USAGE

    conf_dl = {k: v for k, v in conf.items() if k not in ("jobs", "lang")}
    try:
        opts = build_options(args, conf_dl)
    except (ValueError, TypeError) as exc:
        err_console.print(f"[red]✖ {escape(str(exc))}[/]")
        return EXIT_USAGE
    jobs = max(1, args.jobs or int(conf.get("jobs", 1)))

    if args.json:
        grabber = VideoGrabber(opts)
        started = time.monotonic()
        results = grabber.download_many(urls, jobs=jobs)
        out = {
            "version": __version__,
            "elapsed": round(time.monotonic() - started, 2),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return EXIT_OK if all(r.ok for r in results) else EXIT_FAIL

    if not args.quiet:
        print_banner()
        print_settings(opts, jobs)

    started = time.monotonic()
    ui = ProgressUI()
    grabber = VideoGrabber(
        opts,
        on_progress=None if args.quiet else ui.handle,
        on_log=ui.log if args.verbose else None,
        verbose=args.verbose,
    )
    try:
        if args.quiet:
            results = grabber.download_many(urls, jobs=jobs)
        else:
            with ui:
                results = grabber.download_many(urls, jobs=jobs)
    except KeyboardInterrupt:
        grabber.cancel()
        err_console.print(f"\n[yellow]{t('interrupted')}[/]")
        return EXIT_INTERRUPT

    print_summary(results, time.monotonic() - started)
    if args.verbose:
        for r in results:
            for w in r.warnings:
                console.print(f"[yellow]⚠ {escape(w)}[/]")
    for r in results:
        for e in r.item_errors:
            console.print(f"[yellow]⚠ {escape(e)}[/]")
    return EXIT_OK if all(r.ok for r in results) else EXIT_FAIL


def cmd_info(args: argparse.Namespace, conf: dict[str, Any]) -> int:
    url = normalize_url(args.url)
    if not url:
        err_console.print(f"[red]✖ {t('invalid_url', url=escape(args.url))}[/]")
        return EXIT_USAGE
    net = {
        k: getattr(args, k)
        for k in ("cookies_from_browser", "cookies_file", "proxy", "rate_limit", "retries")
    }
    conf_dl = {k: v for k, v in conf.items() if k not in ("jobs", "lang")}
    try:
        opts = DownloadOptions.from_dict(conf_dl).updated(**net)
    except (ValueError, TypeError) as exc:
        err_console.print(f"[red]✖ {escape(str(exc))}[/]")
        return EXIT_USAGE
    grabber = VideoGrabber(
        opts,
        verbose=args.verbose,
        on_log=(lambda lvl, m: err_console.print(f"[dim]{escape(m)}[/]")) if args.verbose else None,
    )
    try:
        if args.json:
            info = grabber.get_info(url)
        else:
            with console.status(t("st_extracting")):
                info = grabber.get_info(url)
    except GrabberError as exc:
        err_console.print(f"[red]✖ {exc}[/]")
        if args.verbose and exc.raw != str(exc):
            err_console.print(f"[dim]{escape(exc.raw)}[/]")
        return EXIT_FAIL
    if args.json:
        print(json.dumps(info.raw, ensure_ascii=False, indent=2, default=str))
    else:
        print_info(info, show_formats=args.formats)
    return EXIT_OK


def _latest_pypi_version(package: str) -> str | None:
    import urllib.request

    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=4) as resp:
            return json.load(resp)["info"]["version"]
    except Exception:
        return None


def cmd_doctor(args: argparse.Namespace, conf: dict[str, Any]) -> int:
    import yt_dlp.version
    from rich import box
    from rich.table import Table

    if not args.quiet:
        print_banner()
    with console.status("…"):
        ffmpeg = find_ffmpeg()
        js = find_js_runtime()
        latest_ytdlp = _latest_pypi_version("yt-dlp")
    ytdlp_ver = yt_dlp.version.__version__

    table = Table(box=box.SIMPLE_HEAD, title=t("doctor_title"), title_justify="left", title_style="bold")
    table.add_column("", width=2)
    table.add_column(t("doctor_component"))
    table.add_column(t("doctor_version"))
    table.add_column(t("doctor_location"), overflow="fold")

    def src(tool_source: str) -> str:
        return t(f"src_{tool_source}")

    table.add_row("✅", "Sever VideoGrabber", __version__, "")
    table.add_row(
        "✅",
        "Python",
        _platform.python_version(),
        f"{_platform.system()} {_platform.release()} ({_platform.machine()})",
    )
    ytdlp_ok = latest_ytdlp is None or latest_ytdlp == ytdlp_ver
    table.add_row(
        "✅" if ytdlp_ok else "⚠️",
        "yt-dlp",
        ytdlp_ver + ("" if ytdlp_ok else f" → [yellow]{latest_ytdlp}[/]"),
        "",
    )
    table.add_row(
        "✅" if ffmpeg.found else "❌",
        f"ffmpeg ({src(ffmpeg.source)})",
        ffmpeg.version or "—",
        escape(ffmpeg.path or ""),
    )
    table.add_row(
        "✅" if js.found else "⚠️",
        f"JS: {js.name} ({src(js.source)})",
        js.version or "—",
        escape(js.path or ""),
    )
    config_file = cfg.config_path()
    try:
        from importlib.metadata import version as _pkg_version

        import webview  # noqa: F401

        table.add_row("✅", "GUI: pywebview", _pkg_version("pywebview"), "")
    except Exception:
        table.add_row("ℹ️", "GUI: pywebview", "—", t("doctor_gui_browser"))
    gui_failed = False
    if os.environ.get("CI") == "true" and getattr(sys, "frozen", False) and sys.platform == "win32":
        # GitHub Actions'ta derlenen Windows exe'sinde pencereyi gerçekten açıp dener.
        from .gui import selftest

        ok, msg = selftest()
        gui_failed = not ok
        table.add_row("✅" if ok else "❌", "GUI selftest", "", escape(msg))
    table.add_row("📄", "config", "✓" if config_file.exists() else "—", escape(str(config_file)))
    try:
        out_dir = build_options(
            argparse.Namespace(), {k: v for k, v in conf.items() if k not in ("jobs", "lang")}
        ).output_dir
        table.add_row("📁", t("saved_to"), "", escape(str(out_dir)))
    except (ValueError, TypeError):
        pass
    console.print(table)

    problems = 0
    if not ffmpeg.found:
        problems += 1
        console.print(f"[red]✖ {t('doctor_missing_ffmpeg')}[/]")
    if not js.found:
        console.print(f"[yellow]⚠ {t('doctor_missing_js')}[/]")
    if not ytdlp_ok:
        console.print("[yellow]⚠ yt-dlp:[/] pip install -U yt-dlp")
    if gui_failed:
        problems += 1
    if not problems:
        console.print(f"[green]✔ {t('doctor_ok')}[/]")
    return EXIT_OK if not problems else EXIT_FAIL


def cmd_config(args: argparse.Namespace, conf: dict[str, Any]) -> int:
    path = cfg.config_path()
    if args.path:
        print(path)
        return EXIT_OK
    if args.init:
        path, written = cfg.write_default_config(force=args.force)
        msg = t("config_created", path=path) if written else t("config_exists", path=path)
        console.print(("[green]✔ " if written else "[yellow]⚠ ") + escape(msg) + "[/]")
        return EXIT_OK if written else EXIT_FAIL
    if not path.exists():
        console.print(f"[dim]{t('config_none')}[/]")
        console.print(f"[dim]{escape(str(path))}[/]")
        return EXIT_OK
    console.print(f"[dim]# {escape(str(path))}[/]")
    console.print(json.dumps(conf, ensure_ascii=False, indent=2, default=str))
    return EXIT_OK


def cmd_gui(args: argparse.Namespace, conf: dict[str, Any]) -> int:
    try:
        from .gui import run_gui
    except Exception as exc:  # pragma: no cover - bozuk kurulum
        err_console.print(f"[yellow]⚠ GUI: {escape(str(exc))}[/]")
        return cmd_wizard(args, conf)
    if getattr(args, "selftest", False):
        from .gui import selftest

        ok, msg = selftest()
        print(("OK " if ok else "FAIL ") + msg)
        return EXIT_OK if ok else EXIT_FAIL
    return run_gui(conf, force_browser=bool(getattr(args, "web", False)))


def cmd_wizard(args: argparse.Namespace, conf: dict[str, Any]) -> int:
    from .interactive import run_interactive

    return run_interactive(conf)


# ----------------------------------------------------------------------- giriş noktası


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _fix_windows_console()
    conf = _load_config_safely()
    set_language(_prescan_lang(argv) or conf.get("lang"))

    if not argv:
        return cmd_gui(argparse.Namespace(web=False), conf)

    if argv[0] not in COMMANDS and argv[0] not in ("-h", "--help", "-V", "--version"):
        argv.insert(0, "download")

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    handler = {
        "download": cmd_download,
        "info": cmd_info,
        "doctor": cmd_doctor,
        "config": cmd_config,
        "gui": cmd_gui,
        "wizard": cmd_wizard,
    }[args.command]
    try:
        return handler(args, conf)
    except KeyboardInterrupt:
        err_console.print(f"\n[yellow]{t('interrupted')}[/]")
        return EXIT_INTERRUPT


def _fix_windows_console() -> None:
    """Windows konsolunda Türkçe karakterler ve emojiler düzgün görünsün."""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
            except (AttributeError, ValueError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
