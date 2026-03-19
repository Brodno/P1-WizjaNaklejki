import sqlite3
import time
import pyautogui
import os

# --- KONFIGURACJA NAUCZONA ---
PUNKT_HHMMSS = (2453, 496)
PUNKT_HH_MM = (2404, 527)
PUNKT_DRUKUJ = (2181, 95)
DB_PATH = 'aop_production.db'

def get_all_pending():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Pobieramy WSZYSTKIE PENDING
        cursor.execute("SELECT id, calculated_hhmmss, ocr_hhmm FROM jobs WHERE status = 'PENDING' ORDER BY id ASC")
        return cursor.fetchall()

def update_status(job_id, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()

def run_all_pending():
    jobs = get_all_pending()
    
    if not jobs:
        print("📭 Brak zadań PENDING w bazie.")
        return

    print(f"🚀 ROZPOCZYNAM WYDRUK OSTATNICH {len(jobs)} REKORDÓW...")
    print("Masz 2 sekundy na aktywację okna...")
    time.sleep(2)

    for job in jobs:
        job_id, hhmmss, hhmm = job
        print(f"🖨️ Drukuję ID {job_id}: [{hhmmss}] i [{hhmm}]")
        
        try:
            update_status(job_id, 'PRINTING')
            
            # 1. Pole HHMMSS
            pyautogui.click(PUNKT_HHMMSS)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.press('backspace')
            pyautogui.typewrite(hhmmss)
            
            # 2. Pole HH:MM
            pyautogui.click(PUNKT_HH_MM)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.press('backspace')
            pyautogui.typewrite(hhmm)
            
            # 3. Kliknij DRUKUJ
            pyautogui.click(PUNKT_DRUKUJ)
            
            update_status(job_id, 'DONE')
            print(f"✅ Zadanie {job_id} wydrukowane.")
            time.sleep(0.5) # Przerwa między naklejkami
            
        except Exception as e:
            print(f"❌ Błąd zadania {job_id}: {e}")
            update_status(job_id, 'ERROR')

if __name__ == "__main__":
    run_all_pending()
