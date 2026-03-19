# AOP Vision System — Label Scanner

System OCR do automatycznej analizy etykiet produkcyjnych w czasie rzeczywistym.
Kamera odczytuje etykietę → AI ekstrahuje dane OEE → zapis do bazy → drukowanie z komputera.

## Co robi

- Skanuje etykiety z linii produkcyjnej przez kamerę
- Rozpoznaje tekst przez EasyOCR + modele Vision (Claude / Gemini)
- Zapisuje dane do lokalnej bazy SQLite
- Umożliwia drukowanie etykiet bezpośrednio z aplikacji (Zebra RPA)
- Dashboard Streamlit + desktopowy interfejs PyQt6

## Stack

Python · Claude API · Gemini Vision API · EasyOCR · YOLOv8 · OpenCV · Streamlit · PyQt6 · SQLite · Docker

## Uruchomienie

```bash
pip install -r requirements.txt
cp .env.example .env  # uzupełnij klucze API
python dashboard.py   # wersja webowa (Streamlit)
# lub
python app_qt.py      # wersja desktopowa (PyQt6)
```

## Konfiguracja

Skopiuj `.env.example` do `.env` i uzupełnij:

```
ANTHROPIC_API_KEY=your-key
GEMINI_API_KEY=your-key
```

## Status

Wersja **v5.3** — stabilna, wdrożona produkcyjnie.
