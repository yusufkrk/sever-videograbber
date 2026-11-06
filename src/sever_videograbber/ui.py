"""Rich tabanlı terminal arayüzü: banner, canlı ilerleme çubukları, özet tabloları."""

from __future__ import annotations

import threading
from typing import Any, ClassVar

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from ._version import __version__
from .core import DownloadResult, MediaInfo, ProgressEvent
from .i18n import t
from .options import DownloadOptions
from .platforms import Platform

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

LOGO = r"""
 ___ _____   _____ ___  __   ___    _          ___          _    _
/ __| __\ \ / / __| _ \ \ \ / (_)__| |___ ___ / __|_ _ __ _| |__| |__  ___ _ _
\__ \ _| \ V /| _||   /  \ V /| / _` / -_) _ \ (_ | '_/ _` | '_ \ '_ \/ -_) '_|
|___/___| \_/ |___|_|_\   \_/ |_\__,_\___\___/\___|_| \__,_|_.__/_.__/\___|_|
"""

_GRADIENT = ("#ff3b5c", "#ff5b4a", "#ff7b38", "#ff9b26")


# ----------------------------------------------------------------------- biçimlendirme


def human_size(n: float | None) -> str:
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_speed(bps: float | None) -> str:
    return f"{human_size(bps)}/s" if bps else ""


def human_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def human_count(n: int | None) -> str:
    if n is None:
        return "—"
    from .i18n import get_language

    return f"{n:,}".replace(",", ".") if get_language() == "tr" else f"{n:,}"


def truncate(text: str | None, width: int) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def platform_tag(p: Platform) -> str:
    return f"[bold {p.color}]{escape(p.name)}[/]"


# ----------------------------------------------------------------------- banner


def print_banner(con: Console | None = None) -> None:
    con = con or console
    if con.width < 84:
        con.print(f"[bold #ff3b5c]SEVER VIDEOGRABBER[/] [dim]v{__version__}[/]")
        con.print(f"[dim]{t('tagline')}[/]\n")
        return
    lines = [ln for ln in LOGO.splitlines() if ln.strip()]
    logo = Text()
    for i, line in enumerate(lines):
        logo.append(line + "\n", style=f"bold {_GRADIENT[i % len(_GRADIENT)]}")
    logo.append(f"\n v{__version__}  ", style="bold white")
    logo.append(t("tagline"), style="dim")
    con.print(Panel(logo, box=box.ROUNDED, border_style="#ff5b4a", padding=(0, 2)))


def print_settings(opts: DownloadOptions, jobs: int, con: Console | None = None) -> None:
    con = con or console
    if opts.audio_only:
        mode = t("mode_audio", fmt=opts.audio_format.upper(), kbps=opts.audio_quality)
    else:
        quality = t("best") if opts.quality == "best" else f"{opts.quality}p"
        mode = t("mode_video", quality=quality, container=opts.container.upper())
    extras = []
    if opts.playlist:
        extras.append("playlist")
    if opts.subtitles:
        extras.append("subs:" + ",".join(opts.subtitles))
    if opts.cookies_from_browser:
        extras.append(f"cookies:{opts.cookies_from_browser}")
    if jobs > 1:
        extras.append(f"jobs:{jobs}")
    line = f"[bold]{mode}[/]"
    if extras:
        line += "  [dim]" + " · ".join(extras) + "[/]"
    con.print(f"  {line}")
    con.print(f"  [dim]{t('saved_to')}:[/] {escape(str(opts.output_dir))}\n")


# ----------------------------------------------------------------------- ilerleme


class ProgressUI:
    """:class:`ProgressEvent` olaylarını canlı rich ilerleme çubuklarına dönüştürür."""

    _STATUS_STYLE: ClassVar[dict[str, str]] = {
        "queued": "dim",
        "extracting": "cyan",
        "downloading": "bold blue",
        "processing": "magenta",
        "finished": "bold green",
        "skipped": "yellow",
        "error": "bold red",
    }

    def __init__(self, con: Console | None = None) -> None:
        self.console = con or console
        self.title_width = max(18, min(48, self.console.width - 70))
        self.progress = Progress(
            TextColumn("{task.fields[icon]}"),
            TextColumn("{task.fields[platform]}", justify="left"),
            TextColumn("{task.description}"),
            BarColumn(bar_width=None if self.console.width < 100 else 28),
            TextColumn("{task.fields[pct]:>4}", style="bold"),
            TextColumn("{task.fields[detail]}", style="dim"),
            console=self.console,
            transient=False,
            expand=False,
            refresh_per_second=8,
        )
        self._tasks: dict[int, TaskID] = {}
        self._lock = threading.Lock()

    def __enter__(self) -> ProgressUI:
        self.progress.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.progress.stop()

    def log(self, level: str, msg: str) -> None:
        style = {"warning": "yellow", "error": "red", "trace": "dim"}.get(level, "dim")
        self.progress.console.print(f"[{style}]{escape(msg)}[/]")

    def _task(self, ev: ProgressEvent) -> TaskID:
        with self._lock:
            if ev.task_id not in self._tasks:
                self._tasks[ev.task_id] = self.progress.add_task(
                    "",
                    total=None,
                    icon="⏳",
                    platform=platform_tag(ev.platform),
                    pct="",
                    detail="",
                )
            return self._tasks[ev.task_id]

    def handle(self, ev: ProgressEvent) -> None:
        task = self._task(ev)
        title = truncate(ev.title or ev.url, self.title_width)
        style = self._STATUS_STYLE.get(ev.status, "")
        desc = f"[{style}]{escape(title):<{self.title_width}}[/]"
        icon, pct, detail = "⏳", "", ""
        update: dict[str, Any] = {}

        if ev.status == "queued":
            detail = t("st_queued")
        elif ev.status == "extracting":
            icon, detail = "🔎", t("st_extracting")
        elif ev.status == "downloading":
            icon = "⬇️ "
            frac = ev.fraction
            if frac is not None:
                update.update(total=1000, completed=int(frac * 1000))
                pct = f"{frac * 100:.0f}%"
            parts = []
            if ev.item_count and ev.item_index:
                parts.append(f"[{ev.item_index}/{ev.item_count}]")
            if ev.phase:
                parts.append(t(f"phase_{ev.phase}"))
            if ev.total:
                parts.append(f"{human_size(ev.downloaded)}/{human_size(ev.total)}")
            if ev.speed:
                parts.append(human_speed(ev.speed))
            if ev.eta is not None:
                parts.append(f"ETA {human_time(ev.eta)}")
            detail = " · ".join(parts)
        elif ev.status == "processing":
            icon, detail = "⚙️ ", t("st_processing")
            update.update(total=None)
        elif ev.status in ("finished", "skipped"):
            icon = "✅" if ev.status == "finished" else "⏭️ "
            update.update(total=1, completed=1)
            pct = "100%"
            detail = t("st_finished") if ev.status == "finished" else t("st_skipped")
        elif ev.status == "error":
            icon = "❌"
            update.update(total=1, completed=0)
            detail = truncate(ev.message or t("st_error"), 60)

        self.progress.update(task, description=desc, icon=icon, pct=pct, detail=detail, **update)


# ----------------------------------------------------------------------- özet / bilgi


def print_summary(results: list[DownloadResult], elapsed: float, con: Console | None = None) -> None:
    con = con or console
    if not results:
        return
    table = Table(
        box=box.SIMPLE_HEAD,
        title=t("summary_title"),
        title_justify="left",
        title_style="bold",
        expand=False,
        padding=(0, 1),
    )
    table.add_column("", width=2)
    table.add_column(t("col_platform"))
    table.add_column(t("col_title"), overflow="fold", max_width=48)
    table.add_column(t("col_size"), justify="right")
    table.add_column(t("col_status"), overflow="fold", max_width=60)

    for r in results:
        if r.ok:
            icon = "⏭️" if r.skipped else "✅"
            status = (
                t("st_skipped")
                if r.skipped
                else (r.files[0].name if len(r.files) == 1 else f"{len(r.files)} files")
            )
            if r.item_errors:
                status += f" [yellow](+{len(r.item_errors)} {t('st_error').lower()})[/]"
            status_markup = f"[green]{escape(status)}[/]" if not r.item_errors else status
        else:
            icon = "❌"
            status_markup = f"[red]{escape(str(r.error))}[/]"
        table.add_row(
            icon,
            platform_tag(r.platform),
            escape(r.title or r.url),
            human_size(r.size) if r.ok else "—",
            status_markup,
        )

    con.print()
    con.print(table)
    ok = sum(1 for r in results if r.ok)
    fail = len(results) - ok
    style = "green" if fail == 0 else ("yellow" if ok else "red")
    con.print(f"[{style}]{t('summary_line', ok=ok, fail=fail, elapsed=human_time(elapsed))}[/]")
    folders = {f.parent for r in results for f in r.files}
    if len(folders) == 1:
        con.print(f"[dim]{t('open_folder_hint', path=escape(str(folders.pop())))}[/]")


def print_info(info: MediaInfo, show_formats: bool, con: Console | None = None) -> None:
    con = con or console
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")
    grid.add_column()
    grid.add_row(t("col_platform"), platform_tag(info.platform))
    grid.add_row(t("col_title"), f"[bold]{escape(info.title or '—')}[/]")
    if info.uploader:
        grid.add_row(t("info_uploader"), escape(info.uploader))
    if info.is_playlist:
        grid.add_row(t("info_playlist"), "✓")
        grid.add_row(t("info_entries"), human_count(info.entry_count))
    else:
        grid.add_row(t("info_duration"), human_time(info.duration))
        if info.view_count is not None:
            grid.add_row(t("info_views"), human_count(info.view_count))
        if info.upload_date:
            d = info.upload_date
            grid.add_row(t("info_date"), f"{d[6:8]}.{d[4:6]}.{d[0:4]}" if len(d) == 8 else d)
    grid.add_row("URL", f"[link={info.url}]{escape(info.url)}[/link]")
    con.print(Panel(grid, box=box.ROUNDED, border_style=info.platform.color, expand=False))

    if show_formats and info.formats:
        table = Table(box=box.SIMPLE_HEAD, title=t("info_formats"), title_justify="left")
        for col, justify in (
            ("col_id", "left"),
            ("col_ext", "left"),
            ("col_res", "right"),
            ("col_fps", "right"),
            ("col_codec", "left"),
            ("col_bitrate", "right"),
            ("col_size", "right"),
        ):
            table.add_column(t(col), justify=justify)  # type: ignore[arg-type]
        for f in info.formats:
            if f["kind"] == "audio":
                res, codec = "audio", f["acodec"] or ""
            else:
                res = f["resolution"] or ""
                codec = " + ".join(c for c in (f["vcodec"], f["acodec"]) if c)
            table.add_row(
                str(f["format_id"]),
                str(f["ext"] or ""),
                res,
                f"{f['fps']:.0f}" if f["fps"] else "",
                truncate(codec, 28),
                f"{f['tbr']:.0f}k" if f["tbr"] else "",
                human_size(f["filesize"]),
            )
        con.print(table)
