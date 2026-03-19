import os
import cv2
import numpy as np
import re
import json
import base64
import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

class AOPVision:
    def __init__(self):
        self.reader = None
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.vertex_key = os.getenv("VERTEX_EXPRESS_KEY")

    def _call_anthropic(self, model, img_base64, prompt):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_key, 
            "anthropic-version": "2023-06-01", 
            "anthropic-beta": "prompt-caching-2024-07-31", # Standard 2026
            "content-type": "application/json"
        }
        
        payload = {
            "model": model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_base64}},
                {"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}} # Oszczędność na powtarzalnym prompcie
            ]}]
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10).json()
            if "content" not in res:
                return {"error": res.get("error", {}).get("message", str(res))[:80]}
            txt = res["content"][0]["text"]
            match = re.search(r'\{.*\}', txt, re.DOTALL)
            return json.loads(match.group()) if match else {"error": "Format error"}
        except Exception as e:
            return {"error": str(e)}

    def analyze_with_sonnet_4_6(self, pil_image):
        """Model flagowy 2026: Najwyzsza precyzja OCR."""
        import io
        buffered = io.BytesIO()
        self._resize_for_api(pil_image).save(buffered, format="JPEG", quality=82)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = "Extract precisely: 1. Batch ID, 2. Best Before Date (DD/MM/YYYY), 3. Production Time (HH:MM). JSON: {\"batch\": \"...\", \"date\": \"...\", \"time\": \"...\"}"
        return self._call_anthropic("claude-sonnet-4-6", img_base64, prompt)

    def analyze_with_haiku_4_5(self, pil_image):
        """Model szybki 2026: Dobry balans ceny do jakosci."""
        import io
        buffered = io.BytesIO()
        pil_image.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = 'Extract from industrial label: Batch ID, Date (DD/MM/YYYY), Time (HH:MM). Respond with ONLY a raw JSON object, no markdown, no explanation: {"batch": "...", "date": "...", "time": "..."}'
        return self._call_anthropic("claude-haiku-4-5-20251001", img_base64, prompt)

    def analyze_locally(self, cv2_frame):
        """Lokalny odczyt (Fallback/Offline)"""
        try:
            import easyocr
            if self.reader is None: self.reader = easyocr.Reader(['en'], gpu=False)
            h, w = cv2_frame.shape[:2]
            img = cv2.resize(cv2_frame, (w*3, h*3))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            processed = clahe.apply(gray)
            res = self.reader.readtext(processed, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/:')
            txt = " ".join([r[1] for r in res]).upper()
            
            batch = re.search(r'[A-Z0-9]{2}\d{2}[A-Z0-9]{2}', txt)
            date_m = re.search(r'\d{2}/\d{2}/\d{4}', txt)
            rot = cv2.rotate(processed, cv2.ROTATE_90_CLOCKWISE)
            res_v = self.reader.readtext(rot, allowlist='0123456789:')
            txt_v = " ".join([r[1] for r in res_v])
            time_m = re.search(r'(\d{2})[:\s](\d{2})', txt_v)
            
            return {
                "batch": batch.group(0) if batch else "UNKNOWN",
                "date": date_m.group(0) if date_m else "UNKNOWN",
                "time": f"{time_m.group(1)}:{time_m.group(2)}" if time_m else "00:00"
            }
        except Exception as e: return {"error": str(e)}

    def _resize_for_api(self, pil_image, max_width=1200):
        """Skaluje obraz do max_width przed wysłaniem — mniejszy payload = szybsza odpowiedź."""
        if pil_image.width > max_width:
            ratio = max_width / pil_image.width
            new_h = int(pil_image.height * ratio)
            return pil_image.resize((max_width, new_h), Image.LANCZOS)
        return pil_image

    def _call_gemini_rest(self, model, pil_image, retries=2):
        """Wspolny klient REST dla modeli Gemini (Google AI Studio)."""
        try:
            import io as _io
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            buf = _io.BytesIO()
            self._resize_for_api(pil_image).save(buf, format="JPEG", quality=82)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            payload = {"contents": [{"parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                {"text": ("Extract from this industrial label: "
                          "1. Batch ID (alphanumeric code like CH14KC), "
                          "2. Best Before Date (DD/MM/YYYY), "
                          "3. Production Time (HH:MM). "
                          "Return JSON only: {\"batch\": \"...\", \"date\": \"...\", \"time\": \"...\"}")}
            ]}]}
            for attempt in range(retries):
                res = requests.post(url, json=payload, timeout=10).json()
                if "candidates" in res:
                    txt = res["candidates"][0]["content"]["parts"][0]["text"]
                    match = re.search(r'\{.*?\}', txt, re.DOTALL)
                    return json.loads(match.group()) if match else {"error": f"Format: {txt[:80]}"}
                err = res.get("error", {})
                if err.get("code") == 503 and attempt < retries - 1:
                    import time; time.sleep(0.5)
                    continue
                return {"error": f"{err.get('code','?')}: {err.get('message','?')[:60]}"}
        except Exception as e:
            return {"error": str(e)}

    def analyze_with_gemini3_pro(self, pil_image):
        """Gemini 3 Pro Image Preview."""
        return self._call_gemini_rest("gemini-3-pro-image-preview", pil_image)

    def analyze_with_gemini3_flash(self, pil_image):
        """Gemini 3 Flash Preview."""
        return self._call_gemini_rest("gemini-3-flash-preview", pil_image)

    def analyze_with_gemini_flash(self, pil_image):
        """Vertex AI Express - Gemini 2.5 Flash Lite (multimodal REST)."""
        try:
            import io as _io
            url = (f"https://aiplatform.googleapis.com/v1/publishers/google/models/"
                   f"gemini-2.5-flash-lite:generateContent?key={self.vertex_key}")
            buffered = _io.BytesIO()
            pil_image.save(buffered, format="JPEG", quality=90)
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            payload = {"contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                {"text": ("Extract from this industrial label: "
                          "1. Batch ID (alphanumeric code), "
                          "2. Best Before Date (DD/MM/YYYY), "
                          "3. Production Time (HH:MM). "
                          "Return JSON only: {\"batch\": \"...\", \"date\": \"...\", \"time\": \"...\"}")}
            ]}]}

            res = requests.post(url, json=payload, timeout=20).json()
            txt = res["candidates"][0]["content"]["parts"][0]["text"]
            match = re.search(r'\{.*?\}', txt, re.DOTALL)
            return json.loads(match.group()) if match else {"error": f"Format: {txt[:80]}"}
        except Exception as e:
            return {"error": str(e)}

    def analyze_with_google_vision(self, pil_image):
        """Google Cloud Vision API - DOCUMENT_TEXT_DETECTION."""
        try:
            from google.cloud import vision as gv
            import io as _io
            key_path = os.path.join(os.path.dirname(__file__), "..", "..", "sixth-arbor-471809-m2-209ff1b2b2d1.json")
            key_path = os.path.normpath(key_path)
            client = gv.ImageAnnotatorClient.from_service_account_file(key_path)

            buf = _io.BytesIO()
            pil_image.save(buf, format="JPEG", quality=95)
            image = gv.Image(content=buf.getvalue())
            response = client.document_text_detection(image=image)
            full_text = response.full_text_annotation.text.strip()
            lines = [l.strip() for l in full_text.splitlines() if l.strip()]

            date_pat = re.compile(r'\d{2}[/\.\-]\d{2}[/\.\-]\d{4}')
            time_pat = re.compile(r'\b(\d{2})[:\s](\d{2})\b')
            # Batch to linia ktora NIE jest sama data i ma litery+cyfry
            batch_val = "?"
            for line in lines:
                if date_pat.search(line) and len(line.strip()) < 14:
                    continue  # to jest linia tylko z data
                b = re.search(r'[A-Z]{1,3}\d{1,2}[A-Z]{1,3}', line.upper())
                if b:
                    batch_val = b.group(0)
                    break

            date_val = "?"
            time_val = "?"
            for line in lines:
                if not date_val or date_val == "?":
                    dm = date_pat.search(line)
                    if dm:
                        date_val = dm.group(0)
                tm = time_pat.search(line)
                if tm and not (date_pat.search(line) and len(line.strip()) < 14):
                    time_val = f"{tm.group(1)}:{tm.group(2)}"

            return {"batch": batch_val, "date": date_val, "time": time_val}
        except Exception as e:
            return {"error": str(e)}

    def analyze_with_gemini(self, pil_image):
        """Backup: Gemini 2.0 Flash"""
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=["Extract: Batch ID, Date, Time (HH:MM). Return JSON.", pil_image]
            )
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            return json.loads(match.group()) if match else {"error": "Format error"}
        except Exception as e: return {"error": str(e)}
