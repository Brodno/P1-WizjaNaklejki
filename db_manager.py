import sqlite3
import random
import os
import json
from datetime import datetime, timedelta

class VisionPrintSystem:
    def __init__(self, db_path='aop_production.db'):
        self.db_path = db_path
        self._init_db()
        # Ścieżka do zbioru treningowego (Shadow Learning)
        base_dir = os.path.dirname(os.path.abspath(db_path))
        self.train_dir = os.path.join(base_dir, "data", "training_data")
        os.makedirs(self.train_dir, exist_ok=True)

    def _init_db(self):
        """Inicjalizacja bazy i czyszczenie starych danych (starszych niż 24h)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT,
                    ocr_hhmm TEXT,
                    calculated_hhmmss TEXT,
                    status TEXT DEFAULT 'PENDING',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Usuwanie rekordów starszych niż 24h
            conn.execute("DELETE FROM jobs WHERE timestamp <= datetime('now', '-1 day')")
            conn.commit()

    def add_job_from_ocr(self, batch_id, ocr_hhmm):
        """ETAP 2: Logika czasu +20s i zapis do bazy."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT calculated_hhmmss FROM jobs WHERE batch_id = ? ORDER BY id DESC LIMIT 1", (batch_id,))
            last = cursor.fetchone()

            ocr_dt = datetime.strptime(ocr_hhmm, "%H:%M")
            
            if last:
                last_time = datetime.strptime(last[0], "%H%M%S")
                # Jeśli minuta w OCR się zgadza z naszym licznikiem, dodaj 20s +/- 5s
                if last_time.minute == ocr_dt.minute:
                    odstep = 20 + random.randint(-5, 5)
                    new_time = last_time + timedelta(seconds=odstep)
                else:
                    # Jeśli OCR przeszedł na nową minutę, resetujemy sekundy (2-8s)
                    new_time = ocr_dt.replace(second=random.randint(2, 8))
            else:
                # Pierwszy rekord: OCR HH:MM + losowe sekundy (2-8s)
                new_time = ocr_dt.replace(second=random.randint(2, 8))

            final_time = new_time.strftime("%H%M%S")
            cursor.execute("INSERT INTO jobs (batch_id, ocr_hhmm, calculated_hhmmss) VALUES (?, ?, ?)", 
                           (batch_id, ocr_hhmm, final_time))
            conn.commit()
            return final_time

    def get_all_jobs(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, batch_id, ocr_hhmm, calculated_hhmmss, status, timestamp FROM jobs ORDER BY id ASC")
            return cursor.fetchall()

    def save_training_sample(self, pil_image, batch_id, ocr_time, quality_score=None):
        """Zapisuje parę (obraz + json) do zbioru treningowego (Shadow Learning)."""
        if pil_image is None: return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        base_name = f"sample_{ts}"

        # 1. Zapisz obraz ROI
        img_path = os.path.join(self.train_dir, f"{base_name}.jpg")
        pil_image.save(img_path, "JPEG", quality=95)

        # 2. Zapisz metadane JSON
        meta_path = os.path.join(self.train_dir, f"{base_name}.json")
        meta = {
            "batch":         batch_id,
            "time":          ocr_time,
            "timestamp":     datetime.now().isoformat(),
            "quality_score": round(quality_score, 3) if quality_score is not None else None,
            "quality_pct":   f"{quality_score*100:.1f}%" if quality_score is not None else None,
        }
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=4)

        print(f"📸 Shadow Learning: Zapisano próbkę {base_name} | jakość: {meta['quality_pct']}")
        return base_name
