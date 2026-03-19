# 📜 Dziennik Zmian - AOP Label Master

Plik zawiera historię rozwoju systemu automatyzacji druku.

> ⚠️ **ZASADA NIENARUSZALNA:** Z tego pliku nigdy nic nie usuwamy.
> Każda wersja — od v1.0 do ostatniej — musi tu pozostać na zawsze.
> Nowe wpisy dodajemy NA GÓRZE, stare zostają bez zmian.

---

## [v5.1b] - 2026-03-03 (Auto-Trigger — State Machine + 3-Frame Preview)

### Dodano
- **Maszyna stanowa:** `waiting_motion → waiting_stability → cooldown → waiting_motion`. System nie odpala skanu dopóki nie wykryje ruchu (wjazd paczki). Czeka aż się ustabilizuje, wtedy skanuje. Eliminuje false-triggery na pustej taśmie.
- **Podgląd 3 ostatnich klatek:** W panelu Auto-Trigger widoczne 3 kolejne klatki ROI z diff score i ikoną pod każdą (🟢 spokój / 🟠 lekki ruch / 🔴 silny ruch).
- **`MOTION_THRESHOLD = 15.0`:** Nowy próg wykrywania wjazdu paczki (wyższy niż `STABILITY_THRESHOLD`).

### Zmieniono
- `trigger_state` + `roi_history` dodane do session_state.
- Przy wyjściu z cooldownu: reset historii klatek i `prev_roi_bytes` — czyste porównanie dla kolejnej paczki.

## [v5.1] - 2026-03-03 (Auto-Trigger)

### Dodano
- **Auto-Trigger:** Mechanizm automatycznego wykrywania stabilności obrazu w ROI (OpenCV `absdiff`). Gdy kamera widzi nieruchomą paczkę przez 2 kolejne sekundy — system odpala skan automatycznie. Operator tylko zatwierdza wynik.
- **`do_scan()` jako oddzielna funkcja:** Logika OCR wyodrębniona z `if btn_snap:` do funkcji wielokrotnego użytku — wywoływana zarówno z przycisku, jak i auto-triggera.
- **`@st.fragment(run_every=1)` — `auto_trigger_panel()`:** Fragment Streamlit odpytuje kamerę co 1 sekundę niezależnie od reszty UI. Wyświetla status: 🟢 Stabilność / 🔴 Ruch / ⏳ Cooldown / ⭕ Wyłączony.
- **Sidebar: toggle + slider cooldown:** Toggle `🔄 AUTO-TRIGGER` włącza/wyłącza mechanizm. Slider `Cooldown (s)` ustawia blokadę po skanie (3-15s, domyślnie 5s).

### Parametry
| Parametr | Wartość | Opis |
|---|---|---|
| `STABILITY_THRESHOLD` | 5.0 px | Maksymalna różnica między klatkami (mean pixel diff) |
| `STABLE_FRAMES_NEEDED` | 2 | Ile razy z rzędu stabilnie = trigger (≈2 sekundy) |
| `AUTO_COOLDOWN_SEC` | 5 | Blokada po triggerze (konfigurowalna sliderem) |

---

## [v5.3] - 2026-03-02 (Shadow Learning & Dockerization)

### Dodano
- **Shadow Dataset Builder:** Implementacja protokołu cichego uczenia. Każde zatwierdzone skanowanie w dashboardzie (auto i manual) zapisuje parę obraz+JSON w `/data/training_data/`. Buduje to złoty zbiór danych pod przyszły darmowy model lokalny.
- **Dockerization (Unicorn Standard):** Stworzono środowisko kontenerowe z izolacją procesu (`appuser` zamiast roota) i optymalizacją warstw (multi-stage build).
- **Architektura Hybrydowa:** Przygotowanie pod rozdzielenie "Mózgu" (Dashboard + AI działający w izolowanym Dockerze) od "Ręki" (skrypt RPA działający na Windowsie i "klikający" na podstawie wspólnej bazy).

### Zmieniono
- `dashboard.py` wywołuje teraz w tle `db.save_training_sample()` po sukcesie rozpoznania.

---

## [v5.0] - 2026-02-27 (Intelligence Update)

### Dodano
- **Temporal Intelligence:** System śledzi historię odczytanych godzin i wykrywa podejrzane wartości (odchylenie >10 min od ostatniego potwierdzonego czasu).
- **3-ścieżkowy flow po skanie:**
  - ✅ Kompletny + wiarygodny → **auto-kolejka** bez kliknięcia + 2× wysokie piknięcie
  - ⚠️ Czas podejrzany → ekran weryfikacji z ostrzeżeniem + 2× niski ton
  - 🔔 Brak godziny → pole ręcznego uzupełnienia z **podpowiedzią z historii** + długi niski ton
- **Licznik kosztów sesji** w sidebarze i w metrykach (PLN per skan).
- **Sidebar Temporal Panel:** Pokazuje ostatni potwierdzony czas i oczekiwane okno dla następnego skanu.
- **Fallback automatyczny:** Gdy Gemini 3 Pro zwróci błąd → system odpala Sonnet 4.6 bez przerywania pracy.

### Zmieniono
- **Silnik główny: Gemini 3 Pro** (`gemini-3-pro-image-preview`) jako domyślny OCR — najlepsze wyniki w benchmarku (12/14 poprawnych odczytów godziny vs 6/14 Sonnet).
- Dashboard zaktualizowany do `v5.0`.

---

## [v4.6] - 2026-02-27 (Vision Lab + Benchmark)

### Dodano
- **`foto_kolektor.py` — AOP Vision Lab:**
  - Podgląd kamery z zoomem (rolka myszy, centrowanie na kursorze)
  - Zaznaczanie ROI myszą (klik + przeciągnij) z efektem spotlight
  - Analiza OCR na żywo — wyniki po prawej stronie
  - Auto-zapis każdego analizowanego ROI do `data_test/captures/`
  - Przełączanie modeli: `G` = Gemini 3 Pro, `S` = Sonnet 4.6
  - Licznik kosztów sesji
- **`benchmark_ocr.py` — Porównanie modeli:**
  - Testuje wszystkie zdjęcia z `data_test/captures/` przez 5 silników
  - Wyniki zapisywane do `ocr_benchmark.db` (SQLite)
  - Tabela porównawcza + zgodność + średni czas odpowiedzi
  - Generuje wykres JPG (`data_test/wyniki_godziny.jpg`)
  - `skip_existing=True` — nie powtarza już przetestowanych kombinacji
- **`vision_engine.py` — Nowe silniki:**
  - `analyze_with_gemini3_pro()` — Gemini 3 Pro Image Preview (Google AI Studio)
  - `analyze_with_gemini3_flash()` — Gemini 3 Flash Preview
  - `analyze_with_gemini_flash()` — Vertex AI Express (Gemini 2.5 Flash Lite)
  - `analyze_with_google_vision()` — Google Cloud Vision API (DOCUMENT_TEXT_DETECTION)
  - Wspólny klient REST `_call_gemini_rest()` z retry na 503

### Naprawiono
- `camera_monitor.py`: ścieżka do `config_camera.json` zmieniona na bezwzględną — konfigurator poprawnie ładuje ustawienia gdy uruchamiany z dashboardu.
- `dashboard.py`: selector kamery w sidebarze — zmiana kamery zapisuje `cam_id` do pliku i przeładowuje aplikację.

### Wyniki benchmarku (14 zdjęć, folia termokurczliwa):
| Model | Batch | Data | Godzina | Czas/skan |
|---|---|---|---|---|
| Gemini 3 Pro | ~85% | ~93% | **12/14** | ~5s |
| Sonnet 4.6 | ~80% | ~65% | 6/14 | ~4.3s |
| Google Vision | ~15% | 100% | 2/14 | **0.33s** |
| Haiku 4.5 | 0% | ~50% | 0% | 1.8s |
| Gemini 2.0 Flash | rate limit | — | — | 25s |
| Lokalny EasyOCR | śmieci | śmieci | 0% | 2.6s |

---

## [v4.5] - 2026-02-25 (Industrial Stability)

### Dodano
- **Silnik Claude 3 Haiku:** Wdrożenie najszybszego i najtańszego modelu wizyjnego (ok. 0.001 PLN/skan) jako głównego mózgu systemu.
- **Weryfikacja Human-in-the-Loop:** Nowy interfejs z 3 polami edycji (Partia, Data, Godzina) zapobiegający pomyłkom bota.
- **Konfigurator Spotlight v2:** Profesjonalne okno celowania z cyfrowym zoomem (rolka myszy) i efektem podświetlenia ROI.
- **Pancerny Launcher:** Skrypt `.bat` automatycznie zabijający wiszące procesy i startujący system w 2 sekundy.
- **Lokalny .env:** Pełna separacja kluczy API dla folderu `Projekty/naklejki`.

---

## [v3.0.1] - 2026-02-25

### Dodano
- **Obsługa IMX477:** Potwierdzona integracja z nową kamerą przemysłową Sony.
- **ROI (Region of Interest):** Implementacja wycinania i przybliżania środka kadru dla zwiększenia precyzji OCR.
- **Benchmark Gemini:** Potwierdzona 100% skuteczność odczytu serii CH14KC na nowych zdjęciach.
- **Zależności:** Doinstalowano brakujące biblioteki (scikit-image, ninja itp.) dla pełnej obsługi lokalnego OCR.

---

## [v3.0] - 2026-02-24 (Wielka Integracja)

### Scalenie Projektów
- **Vision + RPA:** Połączono niezależne projekty skanera wizyjnego i automatu druku w jeden spójny system.
- **Mózg AI (Gemini):** Pełna integracja z modelem Gemini 2.0 Flash do precyzyjnego odczytu trudnych etykiet.
- **Silnik Lokalny (EasyOCR):** Dodano alternatywny tryb offline dla błyskawicznego skanowania bez internetu.
- **Kamera Live:** Bezpośredni podgląd i robienie zdjęć paczek wewnątrz Dashboardu Streamlit.
- **Automatyczna Kolejka:** Każdy skan paczki automatycznie generuje rekord w bazie danych z wyliczonym czasem (+20s) i trafia do kolejki druku.

---

## [v2.7] - 2026-02-23

### Przywrócono
- **Główny Przycisk Ręczny:** Przycisk `🔥 WYDRUKUJ NASTĘPNĄ` wrócił do centrum sterowania.
- **Hybrydowe Sterowanie:** Pełna integracja automatu, przycisku ręcznego oraz indywidualnych guzików przy każdym rekordzie.

---

## [v2.6] - 2026-02-23 (Finalna wersja dnia)
### Dodano
- **Interaktywna Baza:** Każdy rekord w historii ma teraz indywidualny przycisk `🖨️ DRUKUJ`.
- **UX Update:** Zamiana statycznej tabeli na listę aktywnych wierszy z kolorowymi statusami.

---

## [v2.5] - 2026-02-23
### Dodano
- **Mouse Memory (Powrót kursora):** Bot zapamiętuje pozycję myszki użytkownika i odkłada kursor na miejsce po zakończeniu wydruku.

---

## [v2.4] - 2026-02-23
### Naprawiono
- **Eliminacja migania UI:** Zastosowanie `st.fragment` do odświeżania statystyk i tabeli bez przeładowania całej strony (Zero-Flicker).

---

## [v2.3] - 2026-02-23
### Przywrócono
- **Przycisk Ręczny:** Dodano guziki `🔥 WYDRUKUJ NASTĘPNĄ` dla trybu krokowej kontroli.

---

## [v2.2] - 2026-02-23
### Dodano
- **Selekcja Checkbox:** Możliwość zaznaczenia wielu konkretnych rekordów do poprawki.

---

## [v2.1] - 2026-02-23
### Dodano
- **Masowy Re-print:** Suwak pozwalający cofnąć status dla X ostatnich naklejek jednym ruchem.

---

## [v2.0] - 2026-02-23
### Dodano
- **Mechanizm Poprawek:** Możliwość przywracania wydrukowanych naklejek z powrotem do kolejki (status PENDING).

---

## [v1.7 - v1.9] - 2026-02-23
### Naprawiono
- **Problem Dublowania:** Przejście na bezpośrednie zapytania SQL (Direct Query) zamiast cache'owania w RAM.
- **Bezpieczeństwo:** Dodano obsługę klawisza ESC (Stop) oraz Fail-Safe (myszka w róg ekranu).
- **Kalibracja:** Uproszczony system "Celuj teraz!" w sidebarze.

---

## [v1.0 - v1.6] - 2026-02-23
### Dodano
- Fundamenty bazy danych SQLite.
- Logika czasu produkcyjnego (+20s ±5s).
- Pierwszy Dashboard w Streamlit.
- Asystent kalibracji z sygnałami dźwiękowymi.
- Automatyczna kolejka druku (INSERT → PENDING → PRINTING → DONE).

---

*Ostatnia aktualizacja: 2026-03-02 | Wersja: 5.3*
