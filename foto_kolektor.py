"""
AOP VISION LAB
--------------
Podglad kamery | Zoom | Zaznacz ROI | Analiza OCR na zywo

Sterowanie:
  Lewy klik + drag  - zaznacz obszar do analizy
  Rolka myszy       - zoom in/out
  SPACJA            - analizuj zaznaczony obszar
  G                 - Gemini 3 Pro (domyslny, najlepszy)
  S                 - Sonnet 4.6 (fallback)
  ESC               - wyjdz
"""

import cv2
import os
import json
import threading
import numpy as np
from datetime import datetime
from PIL import Image
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_engine import AOPVision

# --- SCIEZKI ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_camera.json")
SAVE_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_test", "captures")
os.makedirs(SAVE_DIR, exist_ok=True)

# --- LAYOUT OKNA ---
CAM_W   = 1000
PANEL_W = 560
WIN_W   = CAM_W + PANEL_W
WIN_H   = 720

vision = AOPVision()

# --- STAN GLOBALNY ---
g = {
    "zoom":         1.0,
    "zoom_cx":      960,    # centrum zoomu w pikselach oryginalnej klatki
    "zoom_cy":      540,
    "roi":          None,   # (x1, y1, x2, y2) w oryginalnych wsp. klatki
    "drawing":      False,
    "drag_start":   None,
    "drag_end":     None,
    "analyzing":    False,
    "model":        "g3pro",   # domyslny: Gemini 3 Pro
    "scan_count":   0,         # licznik analiz w sesji
    "cost_total":   0.0,       # szacowany koszt sesji (PLN)
    "result":       None,
    "history":      [],
    "roi_preview":  None,   # miniatura ostatniego ROI (ndarray BGR)
    "save_count":   0,
    "status":       "Gotowy. Zaznacz obszar i wcisnij SPACJA.",
    "status_ok":    True,
    "frame_h":      1080,
    "frame_w":      1920,
}

# ------------------------------------------------------------------ #
#  POMOCNICZE: przeliczanie wspolrzednych                             #
# ------------------------------------------------------------------ #

def zoom_region():
    """Zwraca (vx1, vy1, vw, vh) - widoczny prostokat w orig. klatce."""
    fw, fh = g["frame_w"], g["frame_h"]
    vw = int(fw / g["zoom"])
    vh = int(fh / g["zoom"])
    vx1 = max(0, min(fw - vw, g["zoom_cx"] - vw // 2))
    vy1 = max(0, min(fh - vh, g["zoom_cy"] - vh // 2))
    return vx1, vy1, vw, vh

def disp_to_frame(dx, dy):
    vx1, vy1, vw, vh = zoom_region()
    fx = int(vx1 + dx * vw / CAM_W)
    fy = int(vy1 + dy * vh / WIN_H)
    return (max(0, min(g["frame_w"] - 1, fx)),
            max(0, min(g["frame_h"] - 1, fy)))

def frame_to_disp(fx, fy):
    vx1, vy1, vw, vh = zoom_region()
    dx = int((fx - vx1) * CAM_W / vw)
    dy = int((fy - vy1) * WIN_H / vh)
    return dx, dy

# ------------------------------------------------------------------ #
#  MOUSE CALLBACK                                                     #
# ------------------------------------------------------------------ #

def on_mouse(event, x, y, flags, _):
    if x > CAM_W:
        return

    if event == cv2.EVENT_MOUSEWHEEL:
        step = 0.25
        if flags > 0:
            g["zoom"] = min(8.0, g["zoom"] + step)
        else:
            g["zoom"] = max(1.0, g["zoom"] - step)
        # centruj zoom na kursor
        fx, fy = disp_to_frame(x, y)
        g["zoom_cx"] = fx
        g["zoom_cy"] = fy
        return

    fx, fy = disp_to_frame(x, y)

    if event == cv2.EVENT_LBUTTONDOWN:
        g["drawing"]    = True
        g["drag_start"] = (fx, fy)
        g["drag_end"]   = (fx, fy)

    elif event == cv2.EVENT_MOUSEMOVE and g["drawing"]:
        g["drag_end"] = (fx, fy)

    elif event == cv2.EVENT_LBUTTONUP:
        g["drawing"] = False
        if g["drag_start"] and g["drag_end"]:
            x1 = min(g["drag_start"][0], g["drag_end"][0])
            y1 = min(g["drag_start"][1], g["drag_end"][1])
            x2 = max(g["drag_start"][0], g["drag_end"][0])
            y2 = max(g["drag_start"][1], g["drag_end"][1])
            if x2 - x1 > 15 and y2 - y1 > 10:
                g["roi"] = (x1, y1, x2, y2)
                # centrum zoomu przechodzi na srodek ROI
                g["zoom_cx"] = (x1 + x2) // 2
                g["zoom_cy"] = (y1 + y2) // 2
        g["drag_start"] = None
        g["drag_end"]   = None

# ------------------------------------------------------------------ #
#  ANALIZA OCR (w osobnym watku)                                      #
# ------------------------------------------------------------------ #

def run_ocr(frame_copy):
    if g["roi"] is None:
        g["status"] = "Najpierw zaznacz obszar (przeciagnij myszka)"
        g["status_ok"] = False
        g["analyzing"] = False
        return

    x1, y1, x2, y2 = g["roi"]
    roi_crop = frame_copy[y1:y2, x1:x2]
    if roi_crop.size == 0:
        g["analyzing"] = False
        return

    # Zapis probki
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    filepath = os.path.join(SAVE_DIR, f"roi_{ts}.jpg")
    cv2.imwrite(filepath, roi_crop, [cv2.IMWRITE_JPEG_QUALITY, 97])
    g["save_count"] += 1

    # Miniatura do podgladu (szerokoscia PANEL_W - 20)
    ph = max(1, int((PANEL_W - 20) * roi_crop.shape[0] / max(1, roi_crop.shape[1])))
    g["roi_preview"] = cv2.resize(roi_crop, (PANEL_W - 20, min(ph, 200)))

    pil_img = Image.fromarray(cv2.cvtColor(roi_crop, cv2.COLOR_BGR2RGB))

    # Koszt szacunkowy na skan (PLN)
    COST = {"g3pro": 0.008, "sonnet": 0.08}

    if g["model"] == "g3pro":
        result = vision.analyze_with_gemini3_pro(pil_img)
    else:
        result = vision.analyze_with_sonnet_4_6(pil_img)

    g["analyzing"]  = False
    g["scan_count"] += 1
    g["cost_total"] += COST.get(g["model"], 0.0)

    if "error" not in result:
        g["result"]  = result
        g["history"].insert(0, (datetime.now().strftime("%H:%M:%S"), result))
        g["history"] = g["history"][:8]
        g["status"]    = f"OK  |  {g['scan_count']} skanow | ~{g['cost_total']:.3f} PLN"
        g["status_ok"] = True
    else:
        # Fallback na Sonnet jesli Gemini zawiedzie
        if g["model"] == "g3pro":
            result = vision.analyze_with_sonnet_4_6(pil_img)
            g["cost_total"] += COST["sonnet"]
            if "error" not in result:
                g["result"]  = result
                g["history"].insert(0, (datetime.now().strftime("%H:%M:%S"), result))
                g["history"] = g["history"][:8]
                g["status"]    = f"OK (fallback Sonnet) | ~{g['cost_total']:.3f} PLN"
                g["status_ok"] = True
                return
        g["status"]    = f"Blad API: {str(result['error'])[:50]}"
        g["status_ok"] = False

# ------------------------------------------------------------------ #
#  RYSOWANIE PANELU WYNIKOW                                           #
# ------------------------------------------------------------------ #

def draw_panel(canvas):
    panel = canvas[:, CAM_W:]
    panel[:] = (22, 22, 32)

    y = 18

    # Naglowek
    cv2.putText(panel, "WYNIKI OCR", (16, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 200, 255), 2)
    y += 22

    model_txt   = "Gemini 3 Pro (domyslny)" if g["model"] == "g3pro" else "Sonnet 4.6  (fallback)"
    model_color = (60, 210, 120) if g["model"] == "g3pro" else (80, 140, 255)
    cv2.putText(panel, model_txt, (16, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, model_color, 1)
    y += 16
    cv2.putText(panel, "G=Gemini3Pro  S=Sonnet  SPACJA=Analizuj  ESC=Wyjdz",
                (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (90, 90, 110), 1)
    y += 14

    cv2.line(panel, (8, y), (PANEL_W - 8, y), (55, 55, 75), 1)
    y += 12

    # Miniatura ROI
    if g["roi_preview"] is not None:
        img = g["roi_preview"]
        rh, rw = img.shape[:2]
        # clip do panelu
        rh = min(rh, WIN_H - y - 200)
        if rh > 5:
            panel[y:y+rh, 10:10+rw] = img[:rh]
            y += rh + 8

    # Wynik biezacy
    if g["analyzing"]:
        cv2.putText(panel, "Analizuje...", (16, y + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 210, 255), 2)
        y += 55
    elif g["result"]:
        r = g["result"]
        fields = [
            ("Partia", r.get("batch", "---")),
            ("Data",   r.get("date",  "---")),
            ("Godz",   r.get("time",  "---")),
        ]
        for label, val in fields:
            cv2.putText(panel, label + ":", (16, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 140, 165), 1)
            cv2.putText(panel, str(val), (110, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 100), 2)
            y += 26
        y += 6
    else:
        cv2.putText(panel, "Brak wynikow", (16, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (70, 70, 90), 1)
        y += 28

    cv2.line(panel, (8, y), (PANEL_W - 8, y), (55, 55, 75), 1)
    y += 12

    # Historia
    cv2.putText(panel, "Historia:", (16, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (110, 110, 130), 1)
    y += 16
    for ts, r in g["history"][:6]:
        line = f"{ts}  {r.get('batch','?')}  {r.get('date','?')}  {r.get('time','?')}"
        cv2.putText(panel, line, (8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 170), 1)
        y += 16

    # Status na dole
    sy = WIN_H - 36
    cv2.line(panel, (8, sy - 10), (PANEL_W - 8, sy - 10), (55, 55, 75), 1)
    color = (50, 210, 50) if g["status_ok"] else (60, 100, 255)
    for i, chunk in enumerate([g["status"][j:j+38] for j in range(0, len(g["status"]), 38)]):
        cv2.putText(panel, chunk, (8, sy + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
    cv2.putText(panel, f"Zapisanych prob: {g['save_count']}",
                (8, WIN_H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 80, 100), 1)

# ------------------------------------------------------------------ #
#  PETLA GLOWNA                                                       #
# ------------------------------------------------------------------ #

def main():
    try:
        with open(CONFIG_PATH, 'r') as f:
            cam_id = json.load(f).get("cam_id", 0)
    except:
        cam_id = 0

    cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    cv2.namedWindow("AOP VISION LAB", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("AOP VISION LAB", WIN_W, WIN_H)
    cv2.setMouseCallback("AOP VISION LAB", on_mouse)

    last_frame = None

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        last_frame      = frame
        g["frame_h"], g["frame_w"] = frame.shape[:2]

        # --- ZOOM & CROP ---
        vx1, vy1, vw, vh = zoom_region()
        cam_view    = frame[vy1:vy1+vh, vx1:vx1+vw].copy()
        cam_display = cv2.resize(cam_view, (CAM_W, WIN_H))

        # --- SPOTLIGHT na ROI ---
        if g["roi"]:
            rx1, ry1, rx2, ry2 = g["roi"]
            dx1, dy1 = frame_to_disp(rx1, ry1)
            dx2, dy2 = frame_to_disp(rx2, ry2)

            darkened = (cam_display * 0.28).astype(np.uint8)
            cam_display = darkened.copy()

            cdx1 = max(0, dx1); cdy1 = max(0, dy1)
            cdx2 = min(CAM_W - 1, dx2); cdy2 = min(WIN_H - 1, dy2)
            if cdx2 > cdx1 and cdy2 > cdy1:
                cam_display[cdy1:cdy2, cdx1:cdx2] = \
                    (frame[vy1:vy1+vh, vx1:vx1+vw].copy()
                     .__class__.__new__(np.ndarray.__class__) if False
                     else cv2.resize(frame[vy1:vy1+vh, vx1:vx1+vw],
                                     (CAM_W, WIN_H))[cdy1:cdy2, cdx1:cdx2])
            cv2.rectangle(cam_display, (dx1, dy1), (dx2, dy2), (0, 255, 80), 2)

        # --- PODGLAD RYSOWANIA ---
        if g["drawing"] and g["drag_start"] and g["drag_end"]:
            sdx, sdy = frame_to_disp(*g["drag_start"])
            edx, edy = frame_to_disp(*g["drag_end"])
            cv2.rectangle(cam_display, (sdx, sdy), (edx, edy), (255, 160, 0), 1)

        # --- INFO NA KADRZE ---
        roi_txt = (f"ROI: {g['roi'][2]-g['roi'][0]}x{g['roi'][3]-g['roi'][1]}px"
                   if g["roi"] else "Zaznacz obszar (klik+drag)")
        cv2.putText(cam_display,
                    f"ZOOM {g['zoom']:.1f}x  |  {roi_txt}",
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 255, 180), 1)

        # --- SKLAD FINALNEGO OBRAZU ---
        canvas = np.empty((WIN_H, WIN_W, 3), dtype=np.uint8)
        canvas[:, :CAM_W]  = cam_display
        draw_panel(canvas)
        cv2.line(canvas, (CAM_W, 0), (CAM_W, WIN_H), (70, 70, 90), 1)

        cv2.imshow("AOP VISION LAB", canvas)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break
        elif key == 32 and not g["analyzing"] and last_frame is not None:
            g["analyzing"]  = True
            g["status"]     = "Wysylam do API..."
            g["status_ok"]  = True
            threading.Thread(target=run_ocr, args=(last_frame.copy(),), daemon=True).start()
        elif key in (ord('g'), ord('G')):
            g["model"]      = "g3pro"
            g["status"]     = "Model: Gemini 3 Pro  (~0.008 PLN/skan)"
            g["status_ok"]  = True
        elif key in (ord('s'), ord('S')):
            g["model"]      = "sonnet"
            g["status"]     = "Model: Sonnet 4.6  (~0.08 PLN/skan)"
            g["status_ok"]  = True

    cap.release()
    cv2.destroyAllWindows()
    print(f"Zamknieto. Zapisano {g['save_count']} prob w: {SAVE_DIR}")

if __name__ == "__main__":
    main()
