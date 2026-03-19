import sqlite3
from datetime import datetime
import os

def pokaz_baze(db_path='aop_production.db'):
    # Upewnij się, że szukamy bazy w tym samym folderze co skrypt
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_full_path = os.path.join(base_dir, db_path)
    
    try:
        if not os.path.exists(db_full_path):
            print(f"📭 Plik bazy {db_path} jeszcze nie istnieje.")
            return

        conn = sqlite3.connect(db_full_path)
        cursor = conn.cursor()
        
        teraz = datetime.now().strftime('%H:%M:%S')
        print(f"\n--- STAN BAZY DANYCH: {teraz} ---")
        print(f"{'ID':<3} | {'BATCH':<15} | {'OCR HH:MM':<10} | {'WYDANY HHMMSS':<15} | {'STATUS':<10}")
        print("-" * 65)
        
        cursor.execute("SELECT id, batch_id, ocr_hhmm, calculated_hhmmss, status FROM jobs ORDER BY id ASC")
        rows = cursor.fetchall()
        
        if not rows:
            print("📭 Baza jest pusta.")
        else:
            for row in rows:
                print(f"{row[0]:<3} | {row[1]:<15} | {row[2]:<10} | {row[3]:<15} | {row[4]:<10}")
        
        conn.close()
    except Exception as e:
        print(f"❌ Błąd dostępu do bazy: {e}")

if __name__ == "__main__":
    pokaz_baze()
