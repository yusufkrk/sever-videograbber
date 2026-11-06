import pytest

from sever_videograbber.platforms import dedupe, detect_platform, normalize_url, read_url_file


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://youtu.be/abc", "https://youtu.be/abc"),
        ("  youtu.be/abc  ", "https://youtu.be/abc"),
        ("www.instagram.com/reel/xyz/", "https://www.instagram.com/reel/xyz/"),
        ("<https://x.com/a/status/1>", "https://x.com/a/status/1"),
        ("ftp://example.com/file", None),
        ("javascript:alert(1)", None),
        ("merhaba", None),
        ("", None),
        ("# yorum", None),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    ("url", "key"),
    [
        ("https://www.youtube.com/watch?v=1", "youtube"),
        ("https://music.youtube.com/watch?v=1", "youtube"),
        ("https://youtu.be/1", "youtube"),
        ("https://www.instagram.com/p/1", "instagram"),
        ("https://x.com/a/status/1", "twitter"),
        ("https://twitter.com/a/status/1", "twitter"),
        ("https://vm.tiktok.com/abc", "tiktok"),
        ("https://www.reddit.com/r/a", "reddit"),
        ("https://notyoutube.com/x", "generic"),
        ("https://example.com", "generic"),
    ],
)
def test_detect_platform(url, key):
    assert detect_platform(url).key == key


def test_read_url_file(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text(
        "﻿# listem\nhttps://youtu.be/a\n\n  youtu.be/b   # yorum\nçöp satır\n",
        encoding="utf-8",
    )
    assert read_url_file(str(f)) == ["https://youtu.be/a", "https://youtu.be/b"]


def test_dedupe_keeps_order():
    assert dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]
