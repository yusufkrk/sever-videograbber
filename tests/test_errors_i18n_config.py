import pytest

from sever_videograbber import config as cfg
from sever_videograbber.errors import classify, clean_message, friendly
from sever_videograbber.i18n import _MESSAGES, set_language, t


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies-from-browser", "bot"),
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", "private"),
        (
            "ERROR: [Instagram] xyz: Requested content is not available, rate-limit reached or "
            "login required. Use --cookies-from-browser or --cookies for the authentication.",
            "login",
        ),
        ("ERROR: [youtube] abc: Video unavailable", "removed"),
        ("ERROR: [youtube] abc: This video is unavailable", "removed"),
        ("ERROR: Unsupported URL: https://example.com", "unsupported"),
        ("ERROR: [twitter] 1: No video could be found in this tweet", "unsupported"),
        ("ERROR: unable to download webpage: HTTP Error 429: Too Many Requests", "ratelimit"),
        ("ERROR: Postprocessing: ffprobe and ffmpeg not found", "ffmpeg"),
        ("ERROR: [youtube] abc: Sign in to confirm your age", "age"),
        ("ERROR: Could not copy Chrome cookie database", "cookie_db"),
        ("ERROR: something completely different", "generic"),
    ],
)
def test_classify(raw, code):
    assert classify(raw) == code


def test_clean_message_strips_prefix_and_ansi():
    assert clean_message("\x1b[0;31mERROR:\x1b[0m [youtube] abc: Video unavailable") == "Video unavailable"


def test_friendly_is_localized():
    set_language("en")
    assert "login" in str(friendly("login required")).lower()
    set_language("tr")
    err = friendly("login required")
    assert err.code == "login"
    assert "giriş" in str(err)
    assert "weird" in str(friendly("weird thing"))


def test_all_languages_have_same_keys():
    keys = {lang: set(msgs) for lang, msgs in _MESSAGES.items()}
    assert keys["tr"] == keys["en"]


def test_t_formats_and_falls_back():
    set_language("tr")
    assert t("invalid_url", url="x") == "Geçersiz link atlandı: x"
    assert t("missing-key") == "missing-key"
    assert set_language("de") == "en"


def test_config_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "sub" / "config.toml"
    monkeypatch.setenv("VIDEOGRABBER_CONFIG", str(path))
    assert cfg.config_path() == path
    assert cfg.load_config() == {}
    written_path, written = cfg.write_default_config()
    assert written and written_path == path
    assert cfg.load_config() == {}  # tüm satırlar yorum
    _, again = cfg.write_default_config()
    assert again is False
    path.write_text('quality = "720"\nsubtitles = ["tr"]\n', encoding="utf-8")
    assert cfg.load_config() == {"quality": "720", "subtitles": ["tr"]}


def test_config_invalid(tmp_path):
    bad = tmp_path / "c.toml"
    bad.write_text("quality = ", encoding="utf-8")
    with pytest.raises(ValueError):
        cfg.load_config(bad)
