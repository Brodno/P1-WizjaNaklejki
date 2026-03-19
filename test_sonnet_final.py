import os
import sys
from PIL import Image
from dotenv import load_dotenv

# Dodajemy sciezke do projektu
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_path)
from vision_engine import AOPVision

def verify_sonnet_production():
    vision = AOPVision()
    # Sciezka do obrazu testowego
    img_folder = os.path.join(os.path.dirname(os.path.dirname(base_path)), "testy_kamery")
    img_path = os.path.join(img_folder, "paczka_3.jpg")
    
    print("="*60)
    print("🧪 WERYFIKACJA PRODUKCYJNA: CLAUDE SONNET 4.6")
    print("="*60)
    print(f"📁 Plik: {img_path}")
    
    if not os.path.exists(img_path):
        print(f"❌ Brak obrazu testowego!")
        return

    try:
        img = Image.open(img_path)
        print("📡 Wysylanie do Sonnet 4.6... (Czekaj ok. 3-5s)")
        result = vision.analyze_with_sonnet_4_6(img)
        
        print("-" * 30)
        print("--- WYNIK ANALIZY ---")
        if "error" not in result:
            print(f"📦 BATCH:  {result.get('batch')}")
            print(f"📅 DATA:   {result.get('date')}")
            print(f"🕒 CZAS:   {result.get('time')}")
            print("-" * 30)
            print("✅ Model dziala i zwraca poprawne dane.")
        else:
            print(f"❌ BLAD MODELU: {result['error']}")
            
    except Exception as e:
        print(f"❌ BLAD KRYTYCZNY: {e}")

if __name__ == "__main__":
    verify_sonnet_production()
