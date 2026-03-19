# Roadmap: naklejki → Przemysłowy System Inspekcji Wizyjnej
**Zapisano:** 2026-03-07
**Kontekst:** Notatki z analizy architektonicznej. Baza do rozbudowy systemu.

---

## Gdzie jesteśmy teraz

Projekt naklejki = **działający proof of concept** dla 1 kamery:
- Odczyt daty i godziny z paczki ✓
- Gemini 3 Pro = 86% skuteczności (benchmark w `ocr_benchmark.db`) ✓
- Dashboard Streamlit + baza SQLite ✓
- Silnik wizyjny `vision_engine.py` ✓

To jest kamera nr 1 z docelowego systemu 5-kamerowego.

---

## Docelowa architektura przemysłowa

```
Czujnik 1 → Kamera 1 → Wątek 1 → Model A → Relay → OK/NOK ─┐
Czujnik 2 → Kamera 2 → Wątek 2 → Model B → Relay → OK/NOK  │
Czujnik 3 → Kamera 3 → Wątek 3 → Model C → Relay → OK/NOK  ├→ PLC / lampki
Czujnik 4 → Kamera 4 → Wątek 4 → OCR     → Relay → OK/NOK  │
Czujnik 5 → Kamera 5 → Wątek 5 → Model D → Relay → OK/NOK ─┘
                                      ↓
                               Baza danych (SQLite → PostgreSQL)
                                      ↓
                            Raport zmianowy / Dashboard
```

---

## Hardware — decyzje

### Komputer przetwarzający

| Scenariusz | Hardware | Cena | Kiedy |
|-----------|---------|------|-------|
| PoC / pilot | Raspberry Pi 5 (8GB) | ~350 PLN | teraz |
| Produkcja wolna (<60 szt/min) | Raspberry Pi 5 + AI HAT+ (Hailo) | ~630 PLN | pierwsi klienci |
| Produkcja standardowa | Jetson Orin Nano 8GB | ~1 000 PLN | docelowo |
| 5+ kamer / szybka linia | Jetson Orin NX 8GB | ~1 400 PLN | skala |

**Dla linii 30 szt/min: Raspberry Pi 5 wystarczy.**
30 szt/min = 1 paczka co 2 sekundy = mnóstwo czasu na analizę.

### Kamery

**WAŻNE: Global shutter** — obowiązkowy dla linii >60 szt/min.
Przy 30 szt/min rolling shutter często wystarczy (prędkość ~0,1 m/s, blur <1mm przy 10ms ekspozycji).

| Model | Typ | Cena | Zastosowanie |
|-------|-----|------|-------------|
| Hikrobot MV-CS016-10GM | GigE, global shutter, 1.6MP | ~500 PLN | budżetowy start |
| Hikrobot MV-CS050-10GM | GigE, global shutter, 5MP | ~700 PLN | gdy potrzeba wyższej rozdzielczości |
| Basler ace2 a2A1920 | GigE, global shutter, 5MP | ~1 500 PLN | premium, klient widzi markę |
| Logitech C920 USB | rolling shutter | ~200 PLN | tylko PoC / wolne linie |

**Podłączenie 5 kamer do Jetsona:**
- USB3 hub aktywny (własne zasilanie): ~150-200 PLN + 5× kamera USB3
- Lub carrier board Seeed Studio J401 (4× CSI + USB): ~350 PLN

### Oświetlenie — decyduje o skuteczności OCR

| Typ | Do czego | Cena |
|-----|---------|------|
| Ring LED ciągły | inspekcja etykiety, wolne linie | ~200-300 PLN |
| Backlight (podświetlenie) | daty na folii, kody inkjet | ~400-800 PLN |
| Koaksjalne | daty laserowe, błyszczące powierzchnie | ~600-1 200 PLN |
| Stroboskop + kontroler | linie >100 szt/min | ~300-500 PLN |

**Tunel z czarnej tektury/blachy** wokół stanowiska = izolacja od zmiennego światła dziennego. Kosztuje 50 PLN, robi większą różnicę niż droższy procesor.

### Sygnały OK/NOK

- **USB relay board 8-kanałowy**: ~80-120 PLN — najprostsze, z Pythona: `relay.on(1)`
- **GPIO Jetsona + optokopler**: izolacja galwaniczna, standard przemysłowy
- Wyjście 24V DC kompatybilne z większością PLC i sygnalizatorów

### Trigger (wyzwalanie kamery)

Czujnik fotoelektryczny odbiciowy na taśmie → sygnał cyfrowy → trigger kamery.
Marki: Sick, Keyence, TURCK, Banner. Cena: 200-400 PLN.

---

## Modele AI — przejście z Gemini na lokalne

### Dlaczego lokalne?

| | Gemini API | Lokalny model |
|--|-----------|--------------|
| Koszt/skan | ~0,01-0,03 PLN | 0 PLN |
| 10 000 skanów/dzień | ~4 500-9 000 PLN/mies. | 0 PLN |
| Internet wymagany | TAK | NIE |
| RODO | zdjęcia wychodzą poza zakład | brak problemu |
| Dokładność (ogólna) | 86% (benchmark) | zależy od trenowania |
| Dokładność (specyficzny klient) | 86% (ogólna) | 90-96% po fine-tuningu |

### Modele do zastąpienia Gemini

**OCR (odczyt daty/godziny):**
- `PaddleOCR` — rekomendowany, GPU-accelerated, zero trenowania na start
- `EasyOCR` — prostsze API, podobna dokładność
- Instalacja: `pip install paddlepaddle paddleocr`
- Czas na Pi 5 CPU: ~800-1 200ms | Na Jetsonie GPU: ~50-100ms

**Detekcja obiektów (czy naklejka jest, pozycja):**
- `YOLOv8n` — już w projekcie (`yolov8n.pt`), zero trenowania dla podstawowych klas
- Fine-tuning na konkretne etykiety klienta: 50-200 zdjęć wystarczy

**Naklejka prosto / krzywo:**
- OpenCV contour detection + kąt bounding boxa
- Zero AI, zero trenowania, działa w ~20ms nawet na Pi
- `cv2.minAreaRect()` → angle → jeśli >5° → krzywo → FAIL

### Ile trenowania naprawdę potrzeba?

| Zadanie | Zdjęcia | Czas labelowania | Czas trenowania (RTX 3090) |
|---------|---------|-----------------|--------------------------|
| Druk laserowy/termiczny — OCR | 0 | 0 | 0 (out-of-the-box) |
| Inkjet dot-matrix — OCR | 100-200 | ~2-3h | ~20 min |
| Detekcja: czy naklejka jest | 50-100 | ~1h | ~15 min |
| Klasyfikacja: prosto/krzywo/brak | 150-300 | ~3-4h | ~25 min |
| Inspekcja szczelności / uszkodzenia | 200-500 | ~4-6h | ~30 min |

Narzędzie do labelowania: **Roboflow** (free tier: 3 projekty, 1000 zdjęć, augmentacja automatyczna).

---

## Podział na dwie prędkości decyzji

Kluczowy pattern dla systemów inspekcji:

```python
# NATYCHMIAST (<100ms) — blokuje lub przepuszcza paczkę
def fast_check(frame):
    label_present = detect_label(frame)      # YOLOv8 lub OpenCV ~30ms
    label_straight = check_angle(frame)      # OpenCV ~20ms
    return label_present and label_straight  # → sygnał GPIO

# W TLE (~800-1500ms) — nie blokuje linii
def slow_check(frame):
    date = paddle_ocr(frame)                 # PaddleOCR ~1000ms
    save_to_db(date, timestamp)              # → raport zmianowy
```

Przy 30 szt/min masz 2 sekundy na wszystko — oba zadania mieszczą się.

---

## Upgrade path: naklejki → system przemysłowy

```
Naklejki (teraz)              Wersja przemysłowa
─────────────────────         ──────────────────────────────
Gemini API (chmura)      →    PaddleOCR lokalnie (darmowe)
Ręczny trigger            →    Czujnik fotoelektryczny
Kamera USB (dowolna)      →    Kamera GigE global shutter
1 kamera, 1 stanowisko    →    5 kamer, 5 wątków, 5 sygnałów
Streamlit dashboard       →    + raport zmianowy PDF/mail o 6:00
SQLite lokalna            →    SQLite → opcjonalnie PostgreSQL
```

Architektura bazy danych, dashboard, silnik wizyjny — **nie zmienia się**.
To są 4 punkty do zmiany, nie przepisanie od zera.

---

## Przykład konfiguracji 5 kamer dla typowej linii pakującej

| # | Pozycja | Sprawdza | Model | Sygnał |
|---|---------|---------|-------|--------|
| 1 | Wejście linii | Paczka nieuszkodzona | YOLOv8 klasyfikacja | Odrzutnik |
| 2 | Przed etykietownicą | Brak etykiety z poprzedniej zmiany | YOLOv8 detekcja | Alarm |
| 3 | Po etykietownicą | Naklejka prosto, kompletna | OpenCV + YOLOv8 | Odrzutnik |
| 4 | Stanowisko OCR | Odczyt daty ważności | PaddleOCR | Odrzutnik |
| 5 | Wyjście linii | Kontrola końcowa | YOLOv8 multi-class | Odrzutnik |

Jeden Jetson Orin Nano 8GB (~1 000 PLN) obsługuje wszystkie 5.

---

## Smart cameras (TURCK, ADLINK z Jetsonem wbudowanym)

Istnieje kategoria kamer z wbudowanym Jetsonem — wszystko w jednym urządzeniu.

- **ADLINK NVS-6310** (Jetson Orin NX wbudowany): ~$1 200-1 800, IP67, przemysłowa
- **TURCK Vision**: specjalizowane w inspekcji jakości, własne SDK — trudniejsze do customizacji
- Zaleta: 1 urządzenie = kamera + komputer, brak oddzielnego okablowania
- Wada: drogie ($800-1 800/szt.), zamknięty ekosystem, trudno wrzucić własny YOLOv8

**Dla MŚP na start:** osobna kamera + osobny Jetson = tańsze i bardziej elastyczne.
Smart cameras = etap 3 gdy masz 10+ klientów i standaryzujesz sprzęt.

---

## Notatki techniczne do zapamiętania

- `cv2.minAreaRect()` → angle detection dla krzywych naklejek
- PaddleOCR install: `pip install paddlepaddle-gpu paddleocr` (wersja GPU)
- YOLOv8 TensorRT export dla Jetsona: `yolo export model=best.pt format=engine device=0`
- Blur detection (czy zdjęcie ostre): `cv2.Laplacian(gray, cv2.CV_64F).var()` — jeśli <100 → rozmyte, powtórz
- USB relay Python: biblioteka `pyserial` lub dedykowane `hidapi`
- Roboflow free tier: roboflow.com — labeling + augmentacja + export do YOLOv8 format

---

*Dokument żywy. Aktualizować przy każdym nowym wdrożeniu lub teście sprzętowym.*
