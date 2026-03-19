import os
import sys
import time
from PIL import Image

# Ścieżki
BASE_DIR = r"C:\Users\rymko\Desktop\CLAUDE\oferta kompletna\AOP+++"
NAKLEJKI_DIR = os.path.join(BASE_DIR, "Projekty", "naklejki")
sys.path.append(NAKLEJKI_DIR)

from vision_engine import AOPVision

def run_gemini_benchmark():
    vision = AOPVision()
    img_folder = os.path.join(BASE_DIR, "testy_kamery")
    
    if not os.path.exists(img_folder):
        print(f"Folder nie istnieje: {img_folder}")
        return
        
    images = [f for f in os.listdir(img_folder) if f.endswith('.jpg')]
    
    print("="*60)
    print("🧠 BENCHMARK OCR - METODA AI (Gemini 2.0 Flash)")
    print("="*60)
    
    for img_name in sorted(images):
        img_path = os.path.join(img_folder, img_name)
        try:
            img = Image.open(img_path)
            start_time = time.time()
            result = vision.analyze_with_gemini(img)
            duration = time.time() - start_time
            print(f"📸 PLIK: {img_name} ({duration:.2f}s)")
            if "error" not in result:
                print(f"   ✅ BATCH: {result.get('batch', '???')}")
                print(f"   ✅ CZAS:  {result.get('time', '???')}")
            else:
                print(f"   ⚠️ BŁĄD:  {result['error']}")
        except Exception as e:
            print(f"❌ Błąd przy {img_name}: {e}")
        print("-" * 40)
        time.sleep(1)

if __name__ == "__main__":
    run_gemini_benchmark()
