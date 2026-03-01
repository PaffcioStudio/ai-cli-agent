# Media Pipeline

Moduł do pobierania i konwersji mediów z internetu (YouTube, Vimeo, SoundCloud i 1000+ innych źródeł via yt-dlp).

## Szybki start

```bash
# Pobierz wideo
ai pobierz https://youtube.com/watch?v=dQw4w9WgXcQ

# Pobierz i przekonwertuj do MP3
ai pobierz i przekonwertuj na mp3 https://youtube.com/watch?v=...

# Tylko audio (bez wideo)
ai pobierz tylko audio z https://youtube.com/watch?v=...

# Specyficzna jakość
ai pobierz w 720p https://youtube.com/watch?v=...
```

## Architektura

```
1. Detekcja narzędzi (yt-dlp, ffmpeg)
          ↓
2. Instalacja jeśli brakuje (apt → pip → GitHub release)
          ↓
3. Pobieranie do ~/Downloads/ai-downloads/tmp/
          ↓
4. Walidacja pliku (rozmiar > 10KB, metadane)
          ↓
5. Konwersja (opcjonalnie, via ffmpeg)
          ↓
6. Walidacja outputu
          ↓
7. Przeniesienie do ~/Downloads/ai-downloads/
          ↓
8. Cleanup tmp/ (TYLKO po sukcesie)
          ↓
9. Raport: tytuł, rozmiar, czas trwania, lokalizacja
```

## Klasy

### MediaPipeline

Główny orchestrator. Inicjalizowany lazy (`agent.media_pipeline`).

```python
pipeline = MediaPipeline(work_dir=Path("~/Downloads/ai-downloads"), logger=logger)
```

### ToolStatus (enum)

`AVAILABLE`, `MISSING`, `OUTDATED`, `BROKEN`

### MediaTaskError

Wyjątek specyficzny dla błędów pipeline'u.

## API

### check_tool

```python
status, version = pipeline.check_tool("yt-dlp")
# status: ToolStatus
# version: str lub None
```

### ensure_tool

```python
result = pipeline.ensure_tool("yt-dlp", method="auto")
# result: {"success": bool, "action": str, "message": str}
# method: "auto" | "apt" | "pip" | "github"
```

Fallback chain (auto): `apt` → `pip` → `GitHub release binary`

### download_media

```python
result = pipeline.download_media(
    url="https://youtube.com/watch?v=...",
    output_format="best",  # best | worst | 720p | 1080p
    audio_only=False
)
# result: {"success": bool, "filepath": Path, "title": str,
#          "size_mb": float, "duration": str, "error": str}
```

Timeout: 10 minut.

### convert_to_audio

```python
result = pipeline.convert_to_audio(
    video_path=Path("/tmp/video.mp4"),
    audio_format="mp3",  # mp3 | m4a | opus
    bitrate="192k"        # 128k | 192k | 320k
)
```

## Przykładowy raport końcowy

```
✓ Pobrano: Rick Astley - Never Gonna Give You Up
  Rozmiar: 42.5 MB
  Czas trwania: 03:32
✓ Przekonwertowano do MP3 (192 kbps)
  Rozmiar: 8.2 MB
📁 Lokalizacja: ~/Downloads/ai-downloads/Rick_Astley_Never_Gonna_Give_You_Up.mp3
🧹 Usunięto plik tymczasowy: tak
```

## Konfiguracja timeoutów

W `~/.config/ai/config.json`:

```json
{
  "media": {
    "download_timeout_minutes": 10,
    "convert_timeout_minutes": 5,
    "default_audio_bitrate": "192k",
    "download_dir": "~/Downloads/ai-downloads"
  }
}
```

## Bezpieczeństwo

Akcje `download_media` i `convert_media` mają risk level `EXECUTE` - zawsze wymagają potwierdzenia użytkownika, chyba że `allow_execute` wyłączone przez capabilities.

## Przyszłe rozszerzenia

- Playlist support (`download_playlist(url, max_videos=10)`)
- Pobieranie napisów
- Ekstrakcja miniaturki
- Przycinanie wideo (`trim_video(path, start, end)`)
- Quality presets (`preset="podcast"` - audio 64k)
