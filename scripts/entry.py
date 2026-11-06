"""PyInstaller giriş noktası (exe / .app)."""

import multiprocessing
import os
import sys


def _ensure_streams() -> None:
    # Pencereli (.app) derlemede stdout/stderr olmayabilir; yazdırma çökmesin.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _ensure_streams()
    # Eski macOS sürümleri Finder'dan açılışta "-psn_0_12345" argümanı ekler.
    sys.argv = [sys.argv[0], *[a for a in sys.argv[1:] if not a.startswith("-psn_")]]

    from sever_videograbber.cli import main

    sys.exit(main())
