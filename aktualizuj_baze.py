import sqlite3
import random
from datetime import datetime, timedelta
import os

def przelicz_baze(db_path='aop_production.db'):
    if not os.path.exists(db_path):
        print("❌ Baza nie istnieje!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Pobieramy wszystkie rekordy
    cursor.execute("SELECT id, batch_id, ocr_hhmm FROM jobs ORDER BY id ASC")
    rows = cursor.fetchall()
    
    last_time = None
    
    for row in rows:
        db_id, batch, ocr_hhmm = row
        ocr_dt = datetime.strptime(ocr_hhmm, "%H:%M")
        
        if last_time and last_time.minute == ocr_dt.minute:
            # Dodaj 20s +/- 5s do poprzedniego wyliczonego czasu
            odstep = 20 + random.randint(-5, 5)
            new_time = last_time + timedelta(seconds=odstep)
        else:
            # Start lub nowa minuta - losowe sekundy (2-8s)
            new_time = ocr_dt.replace(second=random.randint(2, 8))
        
        final_hhmmss = new_time.strftime("%H%M%S")
        cursor.execute("UPDATE jobs SET calculated_hhmmss = ? WHERE id = ?", (final_hhmmss, db_id))
        last_time = new_time
    
    conn.commit()
    conn.close()
    print("✅ Baza przeliczona ręcznie z losowością +/- 5 sekund.")

if __name__ == "__main__":
    przelicz_baze()
