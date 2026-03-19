import os
import sys
import base64
import requests
import json
import io
from PIL import Image
from dotenv import load_dotenv

# Zaladowanie klucza z lokalnego folderu
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
api_key = os.getenv("ANTHROPIC_API_KEY")

def test_haiku_on_images():
    # Dynamiczna sciezka
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    img_folder = os.path.join(base_dir, "testy_kamery")
    
    images = ["paczka_1.jpg", "paczka_2.jpg", "paczka_3.jpg"]
    
    print("="*60)
    print("🦢 DIAGNOSTYKA CLAUDE 3 HAIKU")
    print("="*60)
    print(f"📁 Folder obrazow: {img_folder}")

    for img_name in images:
        img_path = os.path.join(img_folder, img_name)
        if not os.path.exists(img_path):
            print(f"❌ Brak pliku: {img_path}")
            continue

        print(f"📸 Testuje: {img_name}...")
        
        # Przygotowanie obrazu
        try:
            with Image.open(img_path) as img:
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"❌ Blad ladowania obrazu: {e}")
            continue

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_base64}},
                {"type": "text", "text": "What do you see on this label? Please describe everything first, then extract: 1. Batch ID, 2. Date (DD/MM/YYYY), 3. Time (HH:MM). Return as JSON at the end."}
            ]}]
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                content = res_data['content'][0]['text']
                print(f"--- ODPOWIEDZ DLA {img_name} ---")
                print(content)
            else:
                print(f"❌ Błąd API ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"❌ Błąd: {e}")
        print("-" * 40)

if __name__ == "__main__":
    test_haiku_on_images()
