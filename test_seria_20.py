import sqlite3
import random
from datetime import datetime, timedelta
import os
from db_manager import VisionPrintSystem

def run_test_series_20():
    db_path = 'aop_production.db'
    system = VisionPrintSystem(db_path)
    
    batch = "PRODUKCJA_B2"
    # Pobieramy aktualną godzinę jako bazę dla OCR
    base_time = datetime.now()
    
    print(f"🚀 GENEROWANIE SERII 20 REKORDÓW DLA BATCHU: {batch}")
    print("-" * 50)
    
    for i in range(1, 21):
        # Symulujemy upływ czasu - co 3 naklejki "mija" minuta w OCR
        sim_minutes = i // 3
        ocr_time = (base_time + timedelta(minutes=sim_minutes)).strftime("%H:%M")
        
        wyliczony = system.add_job_from_ocr(batch, ocr_time)
        print(f"Paczka {i:02d} | OCR: {ocr_time} | WYDRUK HHMMSS: {wyliczony} | Status: PENDING")

    print("-" * 50)
    print("✅ Gotowe. Sprawdź Dashboard (odświeży się automatycznie).")

if __name__ == "__main__":
    run_test_series_20()
