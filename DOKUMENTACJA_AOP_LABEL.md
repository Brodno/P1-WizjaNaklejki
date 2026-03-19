# 🏭 AOP VISION & RPA MASTER v5.0 — Dokumentacja Techniczna

Zintegrowany system wizyjnego rozpoznawania danych z paczek (AI Vision) i automatyzacji druku etykiet (Zebra RPA).

---

## 🚀 1. Architektura Systemu (v5.0)

### A. Warstwa Wizyjna
- **Primary: Gemini 3 Pro** (`gemini-3-pro-image-preview`, Google AI Studio)
  - Najlepszy wynik benchmarku: 12/14 poprawnych odczytów godziny
  - Koszt: ~0.008 PLN/skan
  - Klucz: `GEMINI_API_KEY` w `.env`
- **Fallback: Claude Sonnet 4.6** (Anthropic API)
  - Aktywowany automatycznie gdy Gemini zawiedzie
  - Koszt: ~0.08 PLN/skan
- **Offline: EasyOCR** (lokalny, bez internetu)
  - Niska skuteczność na folii termokurczliwej — tylko awaryjnie

### B. Temporal Intelligence
- System śledzi historię ostatnich N potwierdzonych godzin
- Każdy nowy odczyt sprawdzany względem okna ±10 min od ostatniego
- Odchylenie > 10 min → ostrzeżenie + ręczna weryfikacja

### C. 3-ścieżkowy Flow po Skanie
1. **Kompletny + wiarygodny** → auto-kolejka + dźwięk 2× wysokie piknięcie
2. **Czas podejrzany** → ekran weryfikacji z ostrzeżeniem + 2× niski ton
3. **Brak godziny** → pole do wpisania z podpowiedzią z historii + długi niski ton

### D. Logika Sekund (`db_manager.py`)
- Ta sama minuta co poprzednia → `last_time + 20s ± 5s`
- Nowa minuta → `HH:MM + losowe 2-8s`
- Pierwszy rekord → `HH:MM + losowe 2-8s`

### E. Warstwa RPA (Zebra Master)
- **Ghost Mode:** Bot emuluje ruchy operatora w Zebra Designer
- Kursor wraca na miejsce po każdym wydruku
- **Safety:** ESC przerywa tryb auto

---

## 🛠️ 2. Instrukcja Uruchomienia

### Start systemu
```
START_AOP.bat
```
Skrypt zabija wiszące procesy Python/Streamlit i uruchamia dashboard.

### Konfiguracja kamery (pierwsze uruchomienie)
1. W sidebarze wybierz właściwą kamerę (0/1/2...)
2. Kliknij **KONFIGURATOR (OKNO)**
3. **WSAD** — przesuń ramkę ROI nad etykietę
4. **Rolka** — zoom na szczegóły
5. **+/-** — rozmiar prostokąta
6. **ENTER** — zapisz i zamknij

### Narzędzie zbierania próbek (`foto_kolektor.py`)
```
python foto_kolektor.py
```
- `klik + przeciągnij` — zaznacz ROI
- `SPACJA` — analizuj i zapisz próbkę
- `G` — Gemini 3 Pro, `S` — Sonnet 4.6
- `rolka` — zoom
- `ESC` — wyjście

Próbki trafiają do: `data_test/captures/`

---

## 📂 3. Struktura Plików

| Plik | Opis |
|:---|:---|
| `dashboard.py` | Główny UI — skaner, kolejka, RPA, temporal intelligence |
| `vision_engine.py` | Silniki OCR: Gemini 3 Pro, Sonnet 4.6, Google Vision, lokalny |
| `camera_monitor.py` | Konfigurator ROI (okno OpenCV, spotlight, zoom) |
| `foto_kolektor.py` | Narzędzie zbierania próbek + analiza live z wynikami |
| `benchmark_ocr.py` | Porównanie modeli OCR na zebranych próbkach |
| `db_manager.py` | Baza SQLite + logika czasu (+20s ±5s) |
| `config_manager.py` | Ładowanie konfiguracji RPA (punkty kliknięć) |
| `config_camera.json` | Ustawienia kamery: `cam_id`, `roi_x/y/w/h` |
| `ocr_benchmark.db` | Wyniki benchmarku (SQLite) |
| `aop_production.db` | Kolejka paczek do druku (SQLite, czyści się co 24h) |
| `START_AOP.bat` | Launcher |
| `.env` | Klucze API (nie commitować!) |

---

## 💰 4. Koszty API

| Model | Koszt/skan | 100 skanów/dzień | 2 miesiące |
|:---|:---|:---|:---|
| Gemini 3 Pro | ~0.008 PLN | ~0.80 PLN | ~48 PLN |
| Sonnet 4.6 (fallback) | ~0.08 PLN | rzadko | marginalny |
| **Razem (est.)** | | **~1 PLN/dzień** | **~60 PLN** |

Budżet 1000 PLN / 2 miesiące = bezpieczna rezerwa 16×.

---

## 🔑 5. Klucze API (`.env`)

```
ANTHROPIC_API_KEY=sk-ant-...      # Claude Sonnet/Haiku
GEMINI_API_KEY=AIzaSy...          # Gemini 3 Pro (Google AI Studio)
VERTEX_EXPRESS_KEY=AQ.Ab8...      # Vertex AI Express (Gemini 2.5 Flash Lite)
```

Google Vision używa pliku serwisowego: `../../sixth-arbor-471809-m2-209ff1b2b2d1.json`

---

## 📊 6. Wyniki Benchmarku (2026-02-27)

Testowane na 14 zdjęciach ROI paczek Lavazza z folią termokurczliwą.

| Model | Batch poprawny | Data poprawna | Godzina poprawna | Czas/skan |
|:---|:---|:---|:---|:---|
| **Gemini 3 Pro** | ~85% | ~93% | **12/14 (86%)** | ~5s |
| Sonnet 4.6 | ~80% | ~65% | 6/14 (43%) | ~4.3s |
| Google Vision | ~15% | **100%** | 2/14 (14%) | **0.33s** |
| Haiku 4.5 | 0% | ~50% | 0% | 1.8s |
| Lokalny EasyOCR | śmieci | śmieci | 0% | 2.6s |

**Główny problem:** Godzina drukowana małą czcionką po prawej stronie etykiety — ROI musi ją obejmować.

---

## 🗺️ 7. Roadmap (v5.1 - v6.0+)

### 🎯 Faza 1: Automatyzacja i Zbiór Danych (v5.1 - v5.5)
- [ ] **v5.1: Industrial Auto-Trigger**
  - Implementacja monitora stabilności klatki (OpenCV `absdiff`).
  - Wyzwalanie skanu tylko gdy obraz w ROI jest "nieruchomy" przez 500ms.
  - Blokada dublowania skanu tej samej paczki.
- [ ] **v5.2: Shadow Dataset Builder (Background Learning)**
  - Każde zatwierdzone przez operatora skanowanie zapisuje parę: `image_roi.jpg` + `metadata.json`.
  - Tworzenie struktury `/data/training_data/` — budowanie "złotego zbioru danych" bez dodatkowego wysiłku.
- [ ] **v5.3: Dockerization (Unicorn Standard 2026)**
  - Przygotowanie `Dockerfile` (multi-stage, non-root) i `docker-compose.yml`.
  - Izolacja środowiska: Python + OpenCV + SQLite + Streamlit w jednym kontenerze.

### 🧠 Faza 2: Inteligencja Lokalna i Skalowanie (v5.6 - v6.0)
- [ ] **v5.6: Hybrid Vision Router**
  - System najpierw odpytuje lekki model lokalny (np. EasyOCR + korekta heurystyczna).
  - Jeśli `confidence_score` < 0.9 -> automatyczne wysłanie do Gemini 3 Pro (API).
- [ ] **v6.0: AOP Custom OCR Model**
  - Wytrenowanie dedykowanego modelu (np. TrOCR lub MobileNetV3) na zebranych ~1000 próbkach.
  - Całkowita rezygnacja z zewnętrznych API (koszt = 0 PLN, czas < 0.2s, 100% Offline).

---

## 🛡️ 8. AOP Global AI Strategy (Zasady Nienaruszalne)

1. **Filar "Data First":** Nigdy nie marnujemy odpowiedzi z płatnego API. Każda poprawna odpowiedź (potwierdzona przez człowieka) musi trafić do lokalnego zbioru treningowego.
2. **Filar "Verification is Labeling":** UI jest zaprojektowane tak, by kliknięcie "Zatwierdź" przez operatora było jednocześnie etykietowaniem danych dla sieci neuronowej.
3. **Filar "Hybrid Fallback":** Zawsze dążymy do modelu lokalnego. API chmurowe (Gemini/Claude) jest tylko "nauczycielem" i tymczasowym wsparciem do czasu uzbierania danych.

---

*Ostatnia aktualizacja: 2026-03-02 | Wersja: 5.0 (Strategiczna)*
