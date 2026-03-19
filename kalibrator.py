import pyautogui
import time

def kalibruj_multi():
    punkty = {}
    print("\n--- MULTI-KALIBRATOR RPA ---")
    
    # Punkt 1: HHMMSS
    print("\n1. Masz 5s... NAJEDŹ na pole dla HHMMSS (np. 123456)")
    time.sleep(5)
    punkty['HHMMSS'] = pyautogui.position()
    print(f"✅ Zapisano: {punkty['HHMMSS']}")
    
    # Punkt 2: HH:MM
    print("\n2. Masz 5s... NAJEDŹ na pole dla HH:MM (np. 12:34)")
    time.sleep(5)
    punkty['HH_MM'] = pyautogui.position()
    print(f"✅ Zapisano: {punkty['HH_MM']}")
    
    # Punkt 3: PRZYCISK DRUKUJ
    print("\n3. Masz 5s... NAJEDŹ na przycisk DRUKUJ (lub miejsce, które zatwierdza)")
    time.sleep(5)
    punkty['DRUKUJ'] = pyautogui.position()
    print(f"✅ Zapisano: {punkty['DRUKUJ']}")
    
    print("\n--- WYNIKI DO SKOPIOWANIA ---")
    print(f"PUNKT_HHMMSS = {punkty['HHMMSS']}")
    print(f"PUNKT_HH_MM = {punkty['HH_MM']}")
    print(f"PUNKT_DRUKUJ = {punkty['DRUKUJ']}")
    print("-" * 30)

if __name__ == "__main__":
    kalibruj_multi()
