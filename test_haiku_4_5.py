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

def test_haiku_4_5():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    img_folder = os.path.join(base_dir, "testy_kamery")
    img_path = os.path.join(img_folder, "paczka_3.jpg")
    
    print("="*60)
    print("🚀 TEST CLAUDE HAIKU 4.5 (v2026)")
    print("="*60)

    with Image.open(img_path) as img:
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_base64}},
            {"type": "text", "text": "Extract precisely: Batch ID, Date, Time (HH:MM). JSON only."}
        ]}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        print(f"📡 Status: {response.status_code}")
        if response.status_code == 200:
            print(response.json()['content'][0]['text'])
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    test_haiku_4_5()
