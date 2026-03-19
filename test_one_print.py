import sqlite3
import time
import pyautogui
import os

# --- KONFIGURACJA NAUCZONA ---
PUNKT_HHMMSS = (2453, 496)
PUNKT_HH_MM = (2404, 527)
PUNKT_DRUKUJ = (2181, 95)
DB_PATH = 'aop_production.db'

def get_first_pending():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, calculated_hhmmss, ocr_hhmm FROM jobs WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1")
        return cursor.fetchone()

def update_status(job_id, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()

def run_single_print():
    job = get_first_pending()
    
    if not job:
        print("📭 Brak zadań PENDING w bazie. Uruchom test_seria_10.py najpierw.")
        return

    job_id, hhmmss, hhmm = job
    print(f"🚀 TESTOWY WYDRUK ID {job_id}: [{hhmmss}] i [{hhmm}]")
    print("Masz 2 sekundy na upewnienie się, że okno jest aktywne...")
    time.sleep(2)

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
        print(f"✅ TEST ZAKOŃCZONY POMYŚLNIE. Sprawdź Zebra Designer!")
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        update_status(job_id, 'ERROR')

if __name__ == "__main__":
    run_single_print()
