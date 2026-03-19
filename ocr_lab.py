import cv2
import easyocr
import numpy as np
import matplotlib.pyplot as plt
import os

def test_ocr(image_path):
    if not os.path.exists(image_path):
        print(f"❌ Nie znaleziono pliku: {image_path}")
        return

    print(f"🔍 Analiza obrazu: {image_path}...")
    
    # 1. Wczytanie obrazu
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 2. Inicjalizacja EasyOCR (na razie EN, bo szybciej do testów)
    print("🚀 Inicjalizacja silnika OCR (to może potrwać przy pierwszym razu)...")
    reader = easyocr.Reader(['en']) 

    # 3. Odczyt tekstu
    results = reader.readtext(image_path)

    print("
--- WYNIKI OCR ---")
    for (bbox, text, prob) in results:
        if prob > 0.4: # Wyświetlaj tylko pewne wyniki
            print(f"Detected: [{text}] (Pewność: {prob:.2f})")
    print("------------------
")

    # 4. Wizualizacja (opcjonalnie, jeśli masz podgląd)
    for (bbox, text, prob) in results:
        (tl, tr, br, bl) = bbox
        tl = (int(tl[0]), int(tl[1]))
        br = (int(br[0]), int(br[1]))
        cv2.rectangle(img, tl, br, (0, 255, 0), 2)
        cv2.putText(img, text, (tl[0], tl[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imwrite('ocr_result_debug.jpg', img)
    print("✅ Wynik zapisany do: ocr_result_debug.jpg")

if __name__ == "__main__":
    # Testujemy na Twoim zdjęciu
    test_ocr('20pack RO.jpeg')
