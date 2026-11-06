from pathlib import Path

import pytest

from sever_videograbber.options import DownloadOptions


def keys(pps):
    return [p["key"] for p in pps]


def test_defaults_are_valid():
    opts = DownloadOptions()
    params = opts.to_ydl_params()
    assert params["format"] == "bv*+ba/b"
    assert params["merge_output_format"] == "mp4"
    assert params["noplaylist"] is True
    assert "ext:mp4:m4a" in params["format_sort"]
    assert keys(params["postprocessors"]) == ["FFmpegMetadata", "EmbedThumbnail"]
    assert params["writethumbnail"] is True


@pytest.mark.parametrize("q", ["720", "720p", "720P"])
def test_quality_normalization(q):
    assert DownloadOptions(quality=q).quality == "720"
    assert DownloadOptions(quality=q).format_selector()[1][0] == "res:720"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quality": "999"},
        {"audio_format": "ogg"},
        {"container": "avi"},
        {"audio_quality": "loud"},
        {"retries": -1},
    ],
)
def test_invalid_values_raise(kwargs):
    with pytest.raises(ValueError):
        DownloadOptions(**kwargs)


def test_audio_only():
    opts = DownloadOptions(audio_only=True, audio_format="m4a", audio_quality="320k")
    params = opts.to_ydl_params()
    assert params["format"] == "ba/b"
    assert "merge_output_format" not in params
    pp = params["postprocessors"][0]
    assert pp["key"] == "FFmpegExtractAudio"
    assert pp["preferredcodec"] == "m4a"
    assert pp["preferredquality"] == "320"


def test_wav_skips_thumbnail_and_metadata():
    params = DownloadOptions(audio_only=True, audio_format="wav").to_ydl_params()
    assert keys(params["postprocessors"]) == ["FFmpegExtractAudio"]
    assert params["writethumbnail"] is False


def test_webm_has_no_thumbnail_embed():
    params = DownloadOptions(container="webm").to_ydl_params()
    assert "EmbedThumbnail" not in keys(params["postprocessors"])


def test_subtitles_from_string():
    opts = DownloadOptions(subtitles="tr, en,", auto_subtitles=True)
    params = opts.to_ydl_params()
    assert opts.subtitles == ["tr", "en"]
    assert params["writesubtitles"] is True
    assert params["writeautomaticsub"] is True
    assert params["subtitleslangs"] == ["tr", "en"]
    assert keys(params["postprocessors"])[0] == "FFmpegEmbedSubtitle"


def test_network_options():
    opts = DownloadOptions(
        cookies_from_browser="firefox:default-release",
        cookies_file="~/cookies.txt",
        proxy="socks5://127.0.0.1:1080",
        rate_limit="2M",
        archive_file="arsiv.txt",
        playlist=True,
        playlist_items="1-3",
    )
    params = opts.to_ydl_params()
    assert params["cookiesfrombrowser"] == ("firefox", "default-release", None, None)
    assert params["cookiefile"] == str(Path("~/cookies.txt").expanduser())
    assert params["proxy"] == "socks5://127.0.0.1:1080"
    assert params["ratelimit"] == 2 * 1024 * 1024
    assert params["download_archive"] == "arsiv.txt"
    assert params["noplaylist"] is False
    assert params["playlist_items"] == "1-3"


def test_bad_rate_limit():
    with pytest.raises(ValueError):
        DownloadOptions(rate_limit="hızlı").to_ydl_params()


def test_updated_ignores_none_and_unknown():
    base = DownloadOptions(quality="1080")
    new = base.updated(quality=None, audio_only=True, verbose=True)
    assert new.quality == "1080"
    assert new.audio_only is True
    assert base.audio_only is False


def test_from_dict_ignores_unknown_keys():
    opts = DownloadOptions.from_dict({"quality": "480", "lang": "en", "jobs": 4})
    assert opts.quality == "480"


def test_playlist_outputs_disabled():
    outtmpl = DownloadOptions().to_ydl_params()["outtmpl"]
    assert outtmpl["pl_thumbnail"] == ""
