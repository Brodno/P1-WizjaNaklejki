"""
AOP OCR BENCHMARK
-----------------
Testuje wszystkie zdjecia z data_test/captures/ przez 4 silniki:
  - Claude Sonnet 4.6
  - Claude Haiku 4.5
  - Gemini 2.0 Flash
  - Lokalny EasyOCR (offline)

Wyniki trafiaja do bazy SQLite i sa wyswietlane jako tabela.
"""

import os
import sys
import json
import time
import sqlite3
from datetime import datetime
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_engine import AOPVision

# --- SCIEZKI ---
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CAPTURES   = os.path.join(BASE_DIR, "data_test", "captures")
DB_PATH    = os.path.join(BASE_DIR, "ocr_benchmark.db")

vision = AOPVision()

# ------------------------------------------------------------------ #
#  BAZA DANYCH                                                        #
# ------------------------------------------------------------------ #

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT,
            model       TEXT,
            batch       TEXT,
            date        TEXT,
            time        TEXT,
            error       TEXT,
            duration_ms INTEGER,
            created_at  TEXT,
            UNIQUE(filename, model)
        )
    """)
    conn.commit()
    conn.close()

def save_result(filename, model, result, duration_ms):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO results
            (filename, model, batch, date, time, error, duration_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        filename,
        model,
        result.get("batch", ""),
        result.get("date",  ""),
        result.get("time",  ""),
        result.get("error", ""),
        duration_ms,
        datetime.now().isoformat(timespec="seconds"),
    ))
    conn.commit()
    conn.close()

# ------------------------------------------------------------------ #
#  SILNIKI                                                            #
# ------------------------------------------------------------------ #

MODELS = {
    "sonnet":   lambda img_pil, _: vision.analyze_with_sonnet_4_6(img_pil),
    "g3pro":    lambda img_pil, _: vision.analyze_with_gemini3_pro(img_pil),
    "g3flash":  lambda img_pil, _: vision.analyze_with_gemini3_flash(img_pil),
    "google":   lambda img_pil, _: vision.analyze_with_google_vision(img_pil),
}

# ------------------------------------------------------------------ #
#  BENCHMARK                                                          #
# ------------------------------------------------------------------ #

def run_benchmark(skip_existing=True):
    import cv2

    files = sorted([
        f for f in os.listdir(CAPTURES)
        if f.lower().endswith(".jpg") and not f.startswith("desktop")
    ])

    if not files:
        print("Brak plikow w data_test/captures/")
        return

    print(f"\n{'='*60}")
    print(f"  AOP OCR BENCHMARK  |  {len(files)} zdjec  |  {len(MODELS)} modele")
    print(f"{'='*60}\n")

    for i, fname in enumerate(files, 1):
        fpath = os.path.join(CAPTURES, fname)
        img_pil  = Image.open(fpath).convert("RGB")
        cv_frame = cv2.imread(fpath)

        print(f"[{i:02}/{len(files):02}] {fname}")

        for model_name, fn in MODELS.items():
            # Pomijaj juz istniejace
            if skip_existing:
                conn = sqlite3.connect(DB_PATH)
                exists = conn.execute(
                    "SELECT 1 FROM results WHERE filename=? AND model=?",
                    (fname, model_name)
                ).fetchone()
                conn.close()
                if exists:
                    print(f"       {model_name:<10} [pominiety - juz w bazie]")
                    continue

            t0 = time.time()
            try:
                result = fn(img_pil, cv_frame)
            except Exception as e:
                result = {"error": str(e)}
            ms = int((time.time() - t0) * 1000)

            save_result(fname, model_name, result, ms)

            if "error" not in result or not result["error"]:
                print(f"       {model_name:<10}  "
                      f"batch={str(result.get('batch') or '?'):<10}  "
                      f"date={str(result.get('date') or '?'):<14}  "
                      f"time={str(result.get('time') or '?'):<8}  "
                      f"({ms}ms)")
            else:
                print(f"       {model_name:<10}  BLAD: {str(result['error'])[:50]}  ({ms}ms)")

        print()

    print("Benchmark zakonczony. Generuje tabele...\n")

# ------------------------------------------------------------------ #
#  TABELA WYNIKOW                                                     #
# ------------------------------------------------------------------ #

COL = {
    "sonnet":  "Sonnet 4.6",
    "g3pro":   "Gemini 3 Pro",
    "g3flash": "Gemini 3 Flash",
    "google":  "Google Vision",
}

def print_table():
    conn   = sqlite3.connect(DB_PATH)
    files  = [r[0] for r in conn.execute(
        "SELECT DISTINCT filename FROM results ORDER BY filename"
    ).fetchall()]
    models = list(COL.keys())

    # Szerokosc kolumn
    fn_w  = 28
    col_w = 30

    header_models = "".join(f"  {COL[m]:<{col_w}}" for m in models)
    sep = "-" * (fn_w + 2 + len(header_models))

    print(sep)
    print(f"{'Plik':<{fn_w}}  {header_models}")
    print(sep)

    # Zliczanie zgodnosci
    agree_batch = 0
    agree_date  = 0
    agree_time  = 0
    total       = 0

    for fname in files:
        short = fname.replace("roi_", "").replace(".jpg", "")[:fn_w]
        row_vals = {}

        for m in models:
            r = conn.execute(
                "SELECT batch, date, time, error FROM results WHERE filename=? AND model=?",
                (fname, m)
            ).fetchone()
            if r:
                if r[3]:   # error
                    row_vals[m] = f"ERR: {r[3][:20]}"
                else:
                    row_vals[m] = f"{r[0] or '?'} | {r[1] or '?'} | {r[2] or '?'}"
            else:
                row_vals[m] = "(brak)"

        row = "".join(f"  {row_vals.get(m, ''):<{col_w}}" for m in models)
        print(f"{short:<{fn_w}}  {row}")

        # Zgodnosc miedzy modelami (ignoruj 'lokalny' jesli blad)
        api_models = [m for m in ("sonnet","g3pro","g3flash","google") if m in row_vals]
        batches = set()
        dates   = set()
        times   = set()
        for m in api_models:
            r = conn.execute(
                "SELECT batch, date, time, error FROM results WHERE filename=? AND model=?",
                (fname, m)
            ).fetchone()
            if r and not r[3]:
                if r[0]: batches.add(r[0])
                if r[1]: dates.add(r[1])
                if r[2]: times.add(r[2])
        if len(api_models) > 1:
            total += 1
            if len(batches) == 1: agree_batch += 1
            if len(dates)   == 1: agree_date  += 1
            if len(times)   == 1: agree_time  += 1

    conn.close()

    print(sep)

    if total > 0:
        print(f"\n  ZGODNOSC MODELI API (Sonnet / Haiku / Gemini):")
        print(f"    Partia: {agree_batch}/{total} ({100*agree_batch//total}%)")
        print(f"    Data:   {agree_date}/{total}  ({100*agree_date//total}%)")
        print(f"    Godzina:{agree_time}/{total}  ({100*agree_time//total}%)")

    # Sredni czas
    conn = sqlite3.connect(DB_PATH)
    print(f"\n  SREDNI CZAS ODPOWIEDZI:")
    for m in models:
        rows = conn.execute(
            "SELECT AVG(duration_ms) FROM results WHERE model=? AND error=''", (m,)
        ).fetchone()
        avg = rows[0] if rows[0] else 0
        print(f"    {COL[m]:<14} {avg:>6.0f} ms")
    conn.close()

    print()

# ------------------------------------------------------------------ #
#  MAIN                                                               #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    init_db()
    run_benchmark(skip_existing=True)
    print_table()
