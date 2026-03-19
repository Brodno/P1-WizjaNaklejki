import cv2
import os
import sys
import time

# Ustawienie ścieżek bezwzględnych
BASE_DIR = r"C:\Users\rymko\Desktop\CLAUDE\oferta kompletna\AOP+++"
NAKLEJKI_DIR = os.path.join(BASE_DIR, "Projekty", "naklejki")
sys.path.append(NAKLEJKI_DIR)

from vision_engine import AOPVision

def run_benchmark():
    vision = AOPVision()
    img_folder = os.path.join(BASE_DIR, "testy_kamery")
    
    if not os.path.exists(img_folder):
        print(f"❌ Folder nie istnieje: {img_folder}")
        return

    images = [f for f in os.listdir(img_folder) if f.endswith('.jpg')]
    
    print("="*50)
    print("📊 BENCHMARK OCR - METODA LOKALNA (EasyOCR)")
    print("="*50)
    
    for img_name in sorted(images):
        img_path = os.path.join(img_folder, img_name)
        img = cv2.imread(img_path)
        
        if img is None:
            print(f"❌ {img_name}: Nie można załadować obrazu.")
            continue
            
        start_time = time.time()
        result = vision.analyze_locally(img)
        duration = time.time() - start_time
        
        print(f"📸 PLIK: {img_name} ({duration:.2f}s)")
        if "error" not in result:
            print(f"   🔹 BATCH: {result.get('batch', '???')}")
            print(f"   🔹 CZAS:  {result.get('time', '???')}")
        else:
            print(f"   ⚠️ BŁĄD:  {result['error']}")
        print("-" * 30)

if __name__ == "__main__":
    run_benchmark()
