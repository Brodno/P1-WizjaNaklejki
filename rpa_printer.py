import sqlite3
import time
import pyautogui
import os

# --- KONFIGURACJA NAUCZONA ---
PUNKT_HHMMSS = (2453, 496)
PUNKT_HH_MM = (2404, 527)
PUNKT_DRUKUJ = (2181, 95)
DB_PATH = 'aop_production.db'

def get_next_job():
    """Pobiera najstarsze zadanie PENDING z bazy."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Pobieramy oba formaty czasu: HH:MM oraz HHMMSS
        cursor.execute("SELECT id, calculated_hhmmss, ocr_hhmm FROM jobs WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1")
        return cursor.fetchone()

def update_status(job_id, status):
    """Aktualizuje status zadania w bazie."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()

def run_printer_loop():
    print(f"🚀 BOT RPA URUCHOMIONY (Obsługa 2 pól i przycisku)")
    print(f"Lokalizacja HHMMSS: {PUNKT_HHMMSS}")
    print(f"Lokalizacja HH:MM : {PUNKT_HH_MM}")
    print(f"Przycisk DRUKUJ  : {PUNKT_DRUKUJ}")
    print("-" * 50)
    
    while True:
        job = get_next_job()
        
        if job:
            job_id, hhmmss, hhmm = job
            print(f"🖨️ Przetwarzanie ID {job_id}: [{hhmmss}] i [{hhmm}]...")
            
            try:
                # 1. Zarezerwuj zadanie
                update_status(job_id, 'PRINTING')
                
                # --- AKCJA 1: POLE HHMMSS ---
                pyautogui.click(PUNKT_HHMMSS)
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
                pyautogui.typewrite(hhmmss)
                time.sleep(0.1)

                # --- AKCJA 2: POLE HH:MM ---
                pyautogui.click(PUNKT_HH_MM)
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
                pyautogui.typewrite(hhmm)
                time.sleep(0.1)
                
                # --- AKCJA 3: DRUKUJ ---
                pyautogui.click(PUNKT_DRUKUJ)
                time.sleep(0.5) # Czekamy na reakcję systemu
                
                # 3. Sukces
                update_status(job_id, 'DONE')
                print(f"✅ Zadanie {job_id} wydrukowane.")
                
            except Exception as e:
                print(f"❌ Błąd zadania {job_id}: {e}")
                update_status(job_id, 'ERROR')
        
        # Sprawdzaj kolejkę co 1 sekundę
        time.sleep(1)

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"❌ Baza danych {DB_PATH} nie istnieje! Uruchom najpierw test_seria_10.py")
    else:
        run_printer_loop()
