# Katkı Rehberi / Contributing

Katkıda bulunmak istediğin için teşekkürler! 🎉

## Geliştirme ortamı

[uv](https://docs.astral.sh/uv/) önerilir:

```bash
git clone https://github.com/yusufkrk/sever-videograbber.git
cd sever-videograbber
uv sync --extra dev
uv run videograbber doctor
```

## Testler ve kod stili

```bash
uv run pytest                # hızlı, internetsiz testler
uv run pytest -m network     # gerçek indirme yapan testler
uvx ruff check src tests
uvx ruff format src tests
```

## Proje yapısı

| Dosya | Görev |
| --- | --- |
| `src/sever_videograbber/core.py` | İndirme motoru (`VideoGrabber`), ilerleme olayları |
| `src/sever_videograbber/options.py` | `DownloadOptions` ve yt-dlp parametrelerine dönüşüm |
| `src/sever_videograbber/cli.py` | Komut satırı arayüzü |
| `src/sever_videograbber/interactive.py` | Etkileşimli sihirbaz |
| `src/sever_videograbber/gui/` | Masaüstü penceresi: `server.py` (yerel API), `jobs.py` (kuyruk), `web/index.html` (arayüz) |
| `src/sever_videograbber/ui.py` | Rich tabanlı terminal arayüzü |
| `src/sever_videograbber/errors.py` | Hata sınıflandırma ve kullanıcı dostu mesajlar |
| `src/sever_videograbber/i18n.py` | Türkçe / İngilizce mesajlar |
| `src/sever_videograbber/tools.py` | ffmpeg ve JS motoru tespiti |
| `scripts/build_exe.py` | PyInstaller ile tek dosyalık program derleme |

## Kurallar

- Kullanıcıya görünen her yeni mesajı `i18n.py`'de **hem `tr` hem `en`** olarak ekle (testler anahtar eşitliğini kontrol eder).
- Siteye özel indirme mantığı yazma; bu iş yt-dlp'nin. Bir site bozuksa önce yt-dlp'nin güncel sürümünü dene, gerekirse [yt-dlp'ye](https://github.com/yt-dlp/yt-dlp/issues) bildir.
- Yeni bir hata türü görürsen `errors.py`'deki kalıplara ekle ve `tests/test_errors_i18n_config.py`'ye örnek koy.
- DRM kırma veya erişim kısıtlarını aşma amaçlı katkılar kabul edilmez.

## Sürüm yayınlama (bakımcılar için)

1. `src/sever_videograbber/_version.py` ve `CHANGELOG.md`'yi güncelle.
2. `git tag v3.x.y && git push --tags` — Release iş akışı programları derleyip yayınlar.
