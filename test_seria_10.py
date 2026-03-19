import sqlite3
import random
from datetime import datetime, timedelta
import os
from db_manager import VisionPrintSystem

def run_test_series():
    # Zawsze usuń starą bazę do testu, żeby wynik był czytelny
    db_path = 'aop_production.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        
    system = VisionPrintSystem(db_path)
    
    batch = "BATCH_PROD_123"
    ocr_current = "10:00" # Symulowana godzina bazowa
    
    print(f"🚀 GENEROWANIE SERII TESTOWEJ DLA BATCHU: {batch}")
    print("-" * 50)
    
    for i in range(1, 11):
        # Symulacja przeskoku minuty w OCR co 3-4 rekordy
        if i > 3: ocr_current = "10:01"
        if i > 7: ocr_current = "10:02"
        
        wyliczony = system.add_job_from_ocr(batch, ocr_current)
        print(f"Paczka {i:02d} | OCR widzi: {ocr_current} | WYDRUK HHMMSS: {wyliczony}")

    print("-" * 50)
    print("✅ Gotowe. Plik bazy 'aop_production.db' został utworzony.")

if __name__ == "__main__":
    run_test_series()
