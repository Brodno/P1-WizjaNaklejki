import pyautogui
import time
import winsound

def celuj_z_dzwiekiem(label):
    print("\n--- KROK: %s ---" % label)
    print("Masz 5 sekund... CELUJ MYSZKĄ.")
    
    for i in range(5, 0, -1):
        # Krótki sygnał odliczania (Hz, ms)
        winsound.Beep(1000, 100)
        time.sleep(1)
    
    # Długi sygnał zapisu
    winsound.Beep(2000, 500)
    x, y = pyautogui.position()
    print("✅ ZAPISANO %s: X=%d, Y=%d" % (label, x, y))
    return (x, y)

def start_kalibracji():
    print("=== ASYSTENT KALIBRACJI RPA ===")
    print("Słuchaj dźwięków. Krótki beep = odliczanie, Długi beep = ZAPIS.")
    
    p1 = celuj_z_dzwiekiem("POLE HHMMSS (123456)")
    p2 = celuj_z_dzwiekiem("POLE HH:MM (12:34)")
    p3 = celuj_z_dzwiekiem("PRZYCISK DRUKUJ")
    
    print("\n\n=== WYNIKI DO SKOPIOWANIA ===")
    print("PUNKT_HHMMSS = (%d, %d)" % (p1[0], p1[1]))
    print("PUNKT_HH_MM = (%d, %d)" % (p2[0], p2[1]))
    print("PUNKT_DRUKUJ = (%d, %d)" % (p3[0], p3[1]))
    print("==============================")

if __name__ == "__main__":
    start_kalibracji()
