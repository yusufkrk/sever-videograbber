import json
import threading
import time

import pytest

from sever_videograbber import cli
from sever_videograbber.core import DownloadResult, VideoGrabber
from sever_videograbber.errors import GrabberError
from sever_videograbber.options import DownloadOptions
from sever_videograbber.platforms import detect_platform


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEOGRABBER_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("VIDEOGRABBER_LANG", "tr")


def parse(*argv):
    argv = list(argv)
    if argv[0] not in cli.COMMANDS:
        argv.insert(0, "download")
    return cli.build_parser().parse_args(argv)


def test_prescan_lang():
    assert cli._prescan_lang(["x", "--lang", "en"]) == "en"
    assert cli._prescan_lang(["--lang=tr"]) == "tr"
    assert cli._prescan_lang(["x"]) is None


def test_cli_overrides_config():
    args = parse("https://youtu.be/a", "-q", "720p", "-a", "--no-thumbnail", "-s", "tr,en")
    opts = cli.build_options(args, {"quality": "1080", "audio_format": "m4a", "container": "mkv"})
    assert opts.quality == "720"
    assert opts.audio_only is True
    assert opts.audio_format == "m4a"  # config'den geldi
    assert opts.container == "mkv"
    assert opts.embed_thumbnail is False
    assert opts.subtitles == ["tr", "en"]


def test_flags_default_to_config_values():
    args = parse("https://youtu.be/a")
    opts = cli.build_options(args, {"embed_thumbnail": False, "playlist": True})
    assert opts.embed_thumbnail is False
    assert opts.playlist is True


def test_collect_urls_from_args_and_file(tmp_path):
    f = tmp_path / "l.txt"
    f.write_text("https://youtu.be/b\nhttps://youtu.be/a\n", encoding="utf-8")
    args = parse("https://youtu.be/a", "çöp", "-i", str(f))
    assert cli.collect_urls(args) == ["https://youtu.be/a", "https://youtu.be/b"]


def test_collect_urls_missing_file():
    args = parse("-i", "yok-boyle-bir-dosya.txt")
    with pytest.raises(GrabberError):
        cli.collect_urls(args)


def test_no_urls_exit_code():
    assert cli.main(["download"]) == cli.EXIT_USAGE


def test_invalid_quality_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        cli.main(["https://youtu.be/a", "-q", "999"])
    assert exc.value.code == 2


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    from sever_videograbber import __version__

    assert __version__ in capsys.readouterr().out


def test_config_init_and_path(capsys, tmp_path):
    assert cli.main(["config", "--path"]) == 0
    assert "config.toml" in capsys.readouterr().out
    assert cli.main(["config", "--init"]) == 0
    assert (tmp_path / "config.toml").exists()
    assert cli.main(["config", "--init"]) == 1  # zaten var


def _fake_download(self, url, *, task_id=0):
    time.sleep(0.05)
    ok = "fail" not in url
    return DownloadResult(
        url=url,
        platform=detect_platform(url),
        title=f"t{task_id}",
        ok=ok,
        error=None if ok else GrabberError("nope", code="removed"),
    )


def test_download_many_preserves_order_in_parallel(monkeypatch):
    monkeypatch.setattr(VideoGrabber, "download", _fake_download)
    urls = [f"https://youtu.be/{i}" for i in range(6)]
    results = VideoGrabber(DownloadOptions()).download_many(urls, jobs=3)
    assert [r.url for r in results] == urls
    assert [r.title for r in results] == [f"t{i}" for i in range(6)]


def test_json_output_and_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(VideoGrabber, "download", _fake_download)
    code = cli.main(["https://youtu.be/ok", "https://youtu.be/fail", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_FAIL
    assert [r["ok"] for r in data["results"]] == [True, False]
    assert data["results"][1]["error_code"] == "removed"


def test_cancel_stops_queue(monkeypatch):
    calls = []

    def slow(self, url, *, task_id=0):
        calls.append(url)
        self.cancel()
        return DownloadResult(url=url, platform=detect_platform(url), ok=True)

    monkeypatch.setattr(VideoGrabber, "download", slow)
    results = VideoGrabber().download_many(["https://a.com/1", "https://a.com/2"], jobs=1)
    assert len(calls) == 1
    assert results[1].error is not None and results[1].error.code == "cancelled"


def test_progress_callback_errors_are_swallowed():
    def boom(_):
        raise RuntimeError("ui bug")

    g = VideoGrabber(on_progress=boom)
    g._emit(None)  # type: ignore[arg-type]  # istisna fırlatmamalı
    assert isinstance(g._cancel, threading.Event)


@pytest.mark.network
def test_real_download(tmp_path):
    opts = DownloadOptions(output_dir=tmp_path, quality="144", embed_thumbnail=False)
    result = VideoGrabber(opts).download("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    assert result.ok, result.error
    assert result.files and result.files[0].suffix == ".mp4"
    assert result.size > 10_000
