import os
import requests
import json
from dotenv import load_dotenv

# Zaladowanie klucza z lokalnego folderu
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
api_key = os.getenv("ANTHROPIC_API_KEY")

def test_api():
    print(f"🔍 Testowanie klucza: {api_key[:10]}...{api_key[-5:]}")
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Odpowiedz jednym slowem: CZY DZIALASZ?"}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            res_data = response.json()
            print(f"✅ ODPOWIEDZ CLAUDE: {res_data['content'][0]['text']}")
        else:
            print(f"❌ BLAD: {response.text}")
            
    except Exception as e:
        print(f"❌ BLAD POLACZENIA: {e}")

if __name__ == "__main__":
    test_api()
