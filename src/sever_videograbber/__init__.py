"""Sever VideoGrabber — YouTube, Instagram, X/Twitter, TikTok ve 1000+ siteden video & ses indirici.

Kütüphane olarak kullanım::

    from sever_videograbber import VideoGrabber, DownloadOptions

    grabber = VideoGrabber(DownloadOptions(quality="1080", output_dir="indirilenler"))
    result = grabber.download("https://youtu.be/dQw4w9WgXcQ")
    print(result.files)
"""

from ._version import __version__
from .core import DownloadResult, MediaInfo, ProgressEvent, VideoGrabber
from .errors import GrabberError
from .options import AUDIO_FORMATS, CONTAINERS, QUALITIES, DownloadOptions

__app_name__ = "Sever VideoGrabber"

__all__ = [
    "AUDIO_FORMATS",
    "CONTAINERS",
    "QUALITIES",
    "DownloadOptions",
    "DownloadResult",
    "GrabberError",
    "MediaInfo",
    "ProgressEvent",
    "VideoGrabber",
    "__app_name__",
    "__version__",
]
