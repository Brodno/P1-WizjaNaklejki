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

def test_haiku_pro_prompt():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    img_folder = os.path.join(base_dir, "testy_kamery")
    img_path = os.path.join(img_folder, "paczka_3.jpg")
    
    print("="*60)
    print("🦢 TEST HAIKU - PRO PROMPT (Paczka 3)")
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
    
    # NOWY, LEPSZY PROMPT
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_base64}},
            {"type": "text", "text": "You are an industrial label reader. Analyze this Lavazza label carefully.
Step 1: Locate the Batch ID (often 6 characters like CH14KC).
Step 2: Locate the Best Before Date (DD/MM/YYYY).
Step 3: Locate the Production Time (HH:MM).

Double check: Is the month 08 or 09? Is the time 03:30 or 20:33?
Return ONLY JSON: {"batch": "...", "date": "...", "time": "..."}"}
        ]}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        print(response.json()['content'][0]['text'])
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    test_haiku_pro_prompt()
