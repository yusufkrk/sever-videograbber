"""Masaüstü arayüzü.

Arayüz, yerel bir HTTP sunucusunun sunduğu tek bir HTML sayfasıdır. pywebview varsa
yerel bir pencere içinde (Windows'ta Edge WebView2, macOS'ta WebKit) açılır; yoksa
(örn. GTK/Qt kurulu olmayan Linux) varsayılan tarayıcıda açılır.
"""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from ..i18n import t, ui_strings
from .server import GuiServer

__all__ = ["GuiServer", "run_gui", "selftest"]


def _hide_own_console() -> None:
    """Windows'ta exe çift tıklamayla açıldıysa arkadaki siyah konsolu gizler.

    Konsol başka bir programa (cmd, PowerShell) aitse dokunulmaz.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        procs = (ctypes.c_uint * 4)()
        if kernel32.GetConsoleProcessList(procs, 4) == 1:  # konsolu yalnızca biz kullanıyoruz
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def _storage_dir() -> str:
    from platformdirs import user_data_dir

    path = Path(user_data_dir("sever-videograbber", appauthor=False)) / "webview"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _icon_path() -> str | None:
    try:
        from importlib import resources

        icon = resources.files("sever_videograbber.gui").joinpath("web/icon.png")
        return str(icon) if icon.is_file() else None
    except Exception:
        return None


def run_gui(conf: dict[str, Any] | None = None, *, force_browser: bool = False) -> int:
    server = GuiServer(conf)
    webview = None
    if not force_browser:
        try:
            import webview  # type: ignore[no-redef]
        except Exception:
            webview = None

    if webview is not None:
        window_ref: dict[str, Any] = {}

        def pick_folder(current: str) -> str | None:
            window = window_ref.get("w")
            if not window:
                return None
            kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
            result = window.create_file_dialog(kind, directory=current or "")
            if not result:
                return None
            return result[0] if isinstance(result, (list, tuple)) else str(result)

        server.pick_folder = pick_folder
        server.start()
        strings = ui_strings()
        window = webview.create_window(
            "Sever VideoGrabber",
            server.url,
            width=1040,
            height=780,
            min_size=(720, 560),
            background_color="#0e0f13",
            text_select=True,
        )
        window_ref["w"] = window

        def on_closing() -> bool:
            if server.jobs.active_count() == 0:
                return True
            return bool(
                window.create_confirmation_dialog(strings["confirm_quit_title"], strings["confirm_quit"])
            )

        try:
            window.events.closing += on_closing
        except Exception:
            pass

        _hide_own_console()
        try:
            webview.start(private_mode=False, storage_path=_storage_dir(), icon=_icon_path())
        except Exception as exc:  # WebView2 yok vb. — tarayıcıya düş
            print(t("gui_no_display", url=server.url), file=sys.stderr)
            print(f"  ({type(exc).__name__}: {exc})", file=sys.stderr)
            server.pick_folder = None
            return _browser_loop(server, started=True)
        server.stop()
        return 0

    return _browser_loop(server, started=False)


def _browser_loop(server: GuiServer, *, started: bool) -> int:
    if not started:
        server.start()
    print(t("gui_browser_mode"))
    print(f"  {server.url}")
    threading.Timer(0.3, lambda: webbrowser.open(server.url)).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


def selftest(timeout: float = 45.0) -> tuple[bool, str]:
    """Gerçek bir pencere açar, sayfanın yüklendiğini doğrular ve kapatır.

    Paketlenmiş exe'de pencere bileşenlerinin (WebView2, pythonnet) eksiksiz geldiğini
    test etmek için kullanılır: ``videograbber gui --selftest``.
    """
    try:
        import webview
    except Exception as exc:
        return False, f"pywebview: {exc}"
    server = GuiServer()
    server.start()
    result = {"ok": False, "msg": "timeout"}
    window = webview.create_window("Sever VideoGrabber selftest", server.url, width=640, height=480)

    def check() -> None:
        try:
            if not window.events.loaded.wait(timeout):
                result["msg"] = "page did not load"
                return
            version = window.evaluate_js("(typeof BOOT !== 'undefined' && BOOT.token) ? BOOT.version : null")
            result.update(
                ok=bool(version), msg=f"window + page OK (v{version})" if version else "no bootstrap"
            )
        except Exception as exc:
            result["msg"] = f"{type(exc).__name__}: {exc}"
        finally:
            window.destroy()

    try:
        webview.start(check, private_mode=True)
    except Exception as exc:
        result["msg"] = f"{type(exc).__name__}: {exc}"
    finally:
        server.stop()
    return bool(result["ok"]), str(result["msg"])
