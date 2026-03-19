import cv2
import numpy as np
import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_camera.json")

# Globalne ustawienia
settings = {"cam_id": 1, "roi_x": 660, "roi_y": 440, "roi_w": 600, "roi_h": 200}
view_zoom = 1.0 

def load_cam_settings():
    global settings
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict): settings.update(data)
        except: pass

def save_cam_settings():
    with open(CONFIG_PATH, 'w') as f:
        json.dump(settings, f)

def enhance_frame(frame):
    """
    Stosuje filtry przemyslowe, aby obraz byl 'wyrazniejszy' dla oka i OCR.
    """
    # 1. Kontrast CLAHE
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    enhanced = cv2.merge((cl,a,b))
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    # 2. Wyostrzenie (Unsharp Mask)
    gaussian_3 = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    enhanced = cv2.addWeighted(enhanced, 1.5, gaussian_3, -0.5, 0)
    
    return enhanced

def mouse_wheel_handler(event, x, y, flags, param):
    global view_zoom
    if event == cv2.EVENT_MOUSEWHEEL:
        if flags > 0: view_zoom = min(5.0, view_zoom + 0.2)
        else: view_zoom = max(1.0, view_zoom - 0.2)

def run_pro_monitor():
    global view_zoom
    load_cam_settings()
    # Wymuszamy DirectShow
    cap = cv2.VideoCapture(settings["cam_id"], cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    cv2.namedWindow("AOP INDUSTRIAL VIEW")
    cv2.setMouseCallback("AOP INDUSTRIAL VIEW", mouse_wheel_handler)

    print("--- PODGLAD PRZEMYSLOWY AKTYWNY ---")
    print("Sterowanie: WSAD - Ruch | +/- Rozmiar | Rolka - Zoom | ENTER - Zapisz | ESC - Wyjdz")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # --- OBRÓBKA WZMACNIAJĄCA ---
        # Stosujemy filtry tylko do podgladu, zeby bylo 'ladnie i ostro'
        processed = enhance_frame(frame)
        
        h, w, _ = processed.shape
        rx, ry, rw, rh = settings["roi_x"], settings["roi_y"], settings["roi_w"], settings["roi_h"]

        # --- SPOTLIGHT EFFECT ---
        overlay = processed.copy()
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(mask, (rx, ry), (rx+rw, ry+rh), 255, -1)
        
        # Przyciemniamy wszystko poza ROI
        processed[mask == 0] = processed[mask == 0] // 4 
        # Rysujemy ramke
        cv2.rectangle(processed, (rx, ry), (rx+rw, ry+rh), (0, 255, 0), 2)

        # --- ZOOM PODGLĄDU ---
        vw, vh = int(w / view_zoom), int(h / view_zoom)
        cx, cy = rx + int(rw/2), ry + int(rh/2)
        vx1 = max(0, min(w - vw, cx - int(vw/2)))
        vy1 = max(0, min(h - vh, cy - int(vh/2)))
        
        zoom_view = processed[vy1:vy1+vh, vx1:vx1+vw]
        
        # Statystyki na ekranie
        cv2.putText(zoom_view, f"TRYB SKANERA: LIVE ENHANCED | ZOOM: {view_zoom:.1f}x", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("AOP INDUSTRIAL VIEW", cv2.resize(zoom_view, (1280, 720)))

        key = cv2.waitKey(1) & 0xFF
        if key == 27: break
        elif key == 13: 
            save_cam_settings()
            print("✅ Konfiguracja zapisana.")
            break
        elif key == ord('w'): settings["roi_y"] -= 5
        elif key == ord('s'): settings["roi_y"] += 5
        elif key == ord('a'): settings["roi_x"] -= 5
        elif key == ord('d'): settings["roi_x"] += 5
        elif key == ord('+') or key == ord('='):
            settings["roi_w"] = max(50, settings["roi_w"] - 10)
            settings["roi_h"] = max(20, settings["roi_h"] - 4)
        elif key == ord('-') or key == ord('_'):
            settings["roi_w"] = min(w, settings["roi_w"] + 10)
            settings["roi_h"] = min(h, settings["roi_h"] + 4)

        # Zabezpieczenie ROI
        settings["roi_x"] = max(0, min(w - settings["roi_w"], settings["roi_x"]))
        settings["roi_y"] = max(0, min(h - settings["roi_h"], settings["roi_y"]))

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_pro_monitor()
