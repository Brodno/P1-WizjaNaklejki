import os
import sys
import base64
import json
import io
from PIL import Image
from dotenv import load_dotenv
from google import genai

# Zaladowanie klucza z lokalnego folderu
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
api_key = os.getenv("GEMINI_API_KEY")

def test_gemini_on_images():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    img_folder = os.path.join(base_dir, "testy_kamery")
    images = ["paczka_1.jpg", "paczka_2.jpg", "paczka_3.jpg"]
    
    print("="*60)
    print("🧠 DIAGNOSTYKA GEMINI 2.0 FLASH")
    print("="*60)

    client = genai.Client(api_key=api_key)

    for img_name in images:
        img_path = os.path.join(img_folder, img_name)
        if not os.path.exists(img_path):
            continue

        print(f"📸 Testuje: {img_name}...")
        
        try:
            img = Image.open(img_path)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    "What do you see on this label? Please describe everything first, then extract: 1. Batch ID, 2. Date (DD/MM/YYYY), 3. Time (HH:MM). Return as JSON at the end.",
                    img
                ]
            )
            print(f"--- ODPOWIEDZ DLA {img_name} ---")
            print(response.text)
        except Exception as e:
            print(f"❌ Błąd: {e}")
        print("-" * 40)

if __name__ == "__main__":
    test_gemini_on_images()
