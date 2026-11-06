# Değişiklik Günlüğü / Changelog

Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/), sürümleme [SemVer](https://semver.org/lang/tr/) kurallarına uyar.

## [3.2.0] — 2026-11-06

### Eklenenler
- 🍎 **Gerçek macOS uygulaması** (`Sever VideoGrabber.app`): zip'i aç, Uygulamalar'a sürükle, çift tıkla.
  Terminal veya `chmod` gerekmez. Apple Silicon ve **Intel** Mac'ler için ayrı paketler.
- Release sırasında Windows ve macOS'ta pencerenin otomatik açılış testi (`videograbber gui --selftest`)
- README'ye Mac ilk açılış rehberi

### Değişenler
- macOS dosyaları artık `SeverVideoGrabber-macos-*.zip` adıyla yayınlanıyor (eski `videograbber-macos-arm64` yerine)

## [3.1.0] — 2026-11-06

### Eklenenler
- 🖥️ **Masaüstü penceresi**: link yapıştır, Video/Ses ve kalite seç, İndir. Kapak resimli indirme kartları,
  canlı ilerleme, iptal / tekrar dene, tek tıkla oynat ve klasörde göster, koyu & açık tema, sürükle-bırak.
- Giriş isteyen siteler için pencereden tarayıcı seçimi ve buna göre yönlendiren hata mesajları
- `videograbber gui` (`--web` ile tarayıcıda) ve `videograbber wizard` komutları
- Uygulama ikonu; `doctor` komutunda arayüz kontrolü

### Değişenler
- Argümansız çalıştırma (ve exe'ye çift tıklama) artık terminal sihirbazı yerine pencereyi açar.
  Sihirbaz `videograbber wizard` ile kullanılabilir.

## [3.0.0] — 2026-11-06

İlk açık kaynak sürüm — sıfırdan yeniden yazıldı.

### Eklenenler
- yt-dlp tabanlı yeni indirme motoru: YouTube, Instagram, X/Twitter, TikTok ve 1000+ site
- Kalite seçimi (144p–4K), her yerde oynayan MP4 (H.264/AAC) tercihi
- Sadece ses: MP3 / M4A / OPUS / FLAC / WAV, kapak resmi ve etiket gömme
- Oynatma listeleri: kendi klasörüne numaralı indirme, `--items` ile öğe seçimi
- Paralel indirme (`-j`), dosyadan toplu indirme (`-i`), arşiv ile tekrar indirmeyi önleme
- Altyazı indirme ve gömme
- Tarayıcı çerezleriyle giriş isteyen sitelerden indirme (`--browser`)
- Canlı ilerleme çubukları, özet tablosu, anlaşılır Türkçe/İngilizce hata mesajları
- Etkileşimli mod (argümansız çalıştırınca)
- `info`, `doctor`, `config` komutları; TOML ayar dosyası; `--json` çıktı
- Python kütüphanesi API'si (`VideoGrabber`, `DownloadOptions`)
- ffmpeg ve deno (JS motoru) pakete dahil — ek kurulum yok
- Windows / macOS / Linux için tek dosyalık programlar (GitHub Releases)

[3.2.0]: https://github.com/yusufkrk/sever-videograbber/releases/tag/v3.2.0
[3.1.0]: https://github.com/yusufkrk/sever-videograbber/releases/tag/v3.1.0
[3.0.0]: https://github.com/yusufkrk/sever-videograbber/releases/tag/v3.0.0
