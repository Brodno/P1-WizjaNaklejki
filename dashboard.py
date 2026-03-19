import os
os.environ['OPENCV_LOG_LEVEL'] = 'OFF'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

import streamlit as st
import pandas as pd
import sqlite3
import time
import re
import pyautogui
import winsound
import keyboard
import cv2
import numpy as np
from datetime import datetime, timedelta
from PIL import Image
from config_manager import load_config, save_config
from db_manager import VisionPrintSystem
from vision_engine import AOPVision

# --- KONFIGURACJA ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'aop_production.db')
cfg     = load_config()
db      = VisionPrintSystem(DB_PATH)
vision  = AOPVision()

st.set_page_config(page_title="AOP MASTER v5.1", layout="wide", page_icon="🏭")

# --- SESSION STATE ---
for k, v in [
    ('last_scan',              None),
    ('auto_mode',              False),
    ('need_time',              False),   # True gdy brak godziny w skan
    ('scan_count',             0),
    ('cost_total',             0.0),
    ('auto_trigger',           False),
    ('trigger_cooldown_until', 0.0),     # timestamp kiedy cooldown mija
    ('stable_frames',          0),       # licznik kolejnych stabilnych klatek
    ('prev_roi_bytes',         None),    # poprzednia klatka ROI (bytes, grayscale)
    ('trigger_state',          'waiting_motion'),  # 'waiting_motion' | 'waiting_stability' | 'cooldown'
    ('roi_history',            []),      # ostatnie 3 klatki: [{'img': ndarray, 'diff': float}]
]:
    if k not in st.session_state:
        st.session_state[k] = v

# --- AUTO-TRIGGER CONFIG ---
MOTION_THRESHOLD     = 15.0  # diff > tego = paczka w ruchu (wjechała)
STABILITY_THRESHOLD  = 5.0   # diff < tego = paczka stoi (trigger możliwy)
STABLE_FRAMES_NEEDED = 2     # ile kolejnych stabilnych klatek = trigger (~2s)
AUTO_COOLDOWN_SEC    = 5     # sekund blokady po skanie

# ------------------------------------------------------------------ #
#  WALIDACJA I TEMPORAL INTELLIGENCE                                  #
# ------------------------------------------------------------------ #

BATCH_RE = re.compile(r'^[A-Z]{1,3}\d{1,2}[A-Z]{1,3}$')
DATE_RE  = re.compile(r'^\d{2}[/\.\-]\d{2}[/\.\-]\d{4}$')
TIME_RE  = re.compile(r'^(\d{1,2}):(\d{2})$')

def validate_field(val):
    """True jesli pole wygląda jak sensowna wartosc (nie ? / N/A / UNKNOWN)."""
    if not val: return False
    return val.strip().upper() not in ('?', 'N/A', 'UNKNOWN', 'UNREADABLE', '', '00:00', 'NONE')

def validate_time_format(val):
    m = TIME_RE.match(str(val or ''))
    if not m: return False
    h, mn = int(m.group(1)), int(m.group(2))
    return 0 <= h <= 23 and 0 <= mn <= 59

def ocr_status(res):
    """
    Zwraca ('ok', None) | ('brak_czasu', hint) | ('podejrzany', msg) | ('error', msg)
    """
    batch = res.get('batch', '')
    date  = res.get('date',  '')
    t     = res.get('time',  '')

    if not validate_field(batch) or not validate_field(date):
        return 'error', f"Brak numeru partii lub daty — odrzucam."

    if not validate_field(t) or not validate_time_format(t):
        hint = get_expected_time_hint()
        return 'brak_czasu', hint

    # Sprawdz wiarygodnosc czasowa
    plausible, msg = is_time_plausible(t)
    if not plausible:
        return 'podejrzany', msg

    return 'ok', None

def get_last_confirmed_times(n=5):
    """Pobiera ostatnie n potwierdzonych godzinh:mm z bazy."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ocr_hhmm FROM jobs ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]

def get_expected_time_hint():
    """Podpowiada oczekiwana godzine na podstawie historii."""
    times = get_last_confirmed_times(3)
    if not times:
        return datetime.now().strftime("%H:%M")
    # Zwroc ostatni znany czas
    return times[0]

def is_time_plausible(time_str, tolerance_min=10):
    """
    Sprawdza czy odczytana godzina jest sensowna wzgledem ostatnich rekordow.
    Zwraca (True/False, komunikat).
    """
    times = get_last_confirmed_times(5)
    if not times:
        return True, ""  # brak historii - akceptuj wszystko

    try:
        ocr_dt = datetime.strptime(time_str, "%H:%M")
    except:
        return False, f"Niepoprawny format czasu: {time_str}"

    # Porownaj z ostatnim potwierdzonym czasem
    last_str = times[0]
    try:
        last_dt = datetime.strptime(last_str, "%H:%M")
    except:
        return True, ""

    diff = abs((ocr_dt - last_dt).total_seconds()) / 60
    # Uwzgledniamy przejscie przez polnoc
    if diff > 720:
        diff = 1440 - diff

    if diff > tolerance_min:
        return False, (f"⚠️ Czas {time_str} odbiega o {diff:.0f} min "
                       f"od ostatniego ({last_str}). Sprawdz!")
    return True, ""

# ------------------------------------------------------------------ #
#  DZWIEKI                                                            #
# ------------------------------------------------------------------ #

def beep_ok():
    """Kompletny wynik, wiarygodny."""
    winsound.Beep(1200, 120)
    time.sleep(0.05)
    winsound.Beep(1500, 80)

def beep_warning():
    """Podejrzany czas — sprawdz!"""
    winsound.Beep(600, 300)
    time.sleep(0.05)
    winsound.Beep(400, 300)

def beep_manual():
    """Brak godziny — uzupelnij recznie."""
    winsound.Beep(500, 500)

def beep_error():
    winsound.Beep(300, 800)

# ------------------------------------------------------------------ #
#  HELPERY                                                            #
# ------------------------------------------------------------------ #

def update_job_status(job_id, status):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit(); conn.close()

def print_rpa_direct(job_data, config):
    try:
        old_x, old_y = pyautogui.position()
        pyautogui.click(config["PUNKT_HHMMSS"][0], config["PUNKT_HHMMSS"][1])
        pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
        pyautogui.typewrite(str(job_data['hhmmss']), interval=0.01)
        pyautogui.click(config["PUNKT_HH_MM"][0], config["PUNKT_HH_MM"][1])
        pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
        pyautogui.typewrite(str(job_data['hhmm']), interval=0.01)
        pyautogui.click(config["PUNKT_DRUKUJ"][0], config["PUNKT_DRUKUJ"][1])
        pyautogui.moveTo(old_x, old_y, duration=0.2)
        return True
    except: return False

if keyboard.is_pressed('esc'):
    st.session_state.auto_mode = False

# ------------------------------------------------------------------ #
#  LOGIKA SKANU (wywoływana z przycisku i auto-triggera)              #
# ------------------------------------------------------------------ #

def do_scan(roi_frame, img_pil, mode_str):
    """Analizuje ROI, aktualizuje session_state.
    Wywoływana zarówno z przycisku jak i auto-triggera."""
    with st.spinner('Analizuję...'):
        if "Gemini 3 Pro" in mode_str:
            res = vision.analyze_with_gemini3_pro(img_pil)
            if "error" in res:
                res = vision.analyze_with_haiku_4_5(img_pil)
            cost = 0.008
        elif "Gemini Flash" in mode_str:
            res = vision.analyze_with_gemini3_flash(img_pil)
            if "error" in res:
                res = vision.analyze_with_haiku_4_5(img_pil)
            cost = 0.003
        elif "Haiku" in mode_str:
            res = vision.analyze_with_haiku_4_5(img_pil)
            cost = 0.004
        elif "Sonnet" in mode_str:
            res = vision.analyze_with_sonnet_4_6(img_pil)
            cost = 0.08
        else:
            res = vision.analyze_locally(roi_frame)
            cost = 0.0

    st.session_state.scan_count += 1
    st.session_state.cost_total += cost

    if "error" not in res:
        status, detail = ocr_status(res)

        if status == 'ok':
            beep_ok()
            db.add_job_from_ocr(res['batch'], res['time'])
            db.save_training_sample(img_pil, res['batch'], res['time'])
            st.session_state.last_scan = None
            st.session_state.need_time = False
            st.success(f"✅ AUTO-ZAPISANO: **{res['batch']}** | {res['date']} | **{res['time']}**")

        elif status == 'podejrzany':
            beep_warning()
            st.session_state.last_scan = {
                "batch": res.get('batch', ''), "date": res.get('date', ''),
                "time": res.get('time', ''), "img": img_pil,
                "warning": detail
            }
            st.session_state.need_time = False

        elif status == 'brak_czasu':
            beep_manual()
            st.session_state.last_scan = {
                "batch": res.get('batch', ''), "date": res.get('date', ''),
                "time": '', "img": img_pil,
                "time_hint": detail
            }
            st.session_state.need_time = True

        else:  # error
            beep_error()
            st.error(f"❌ {detail}")
    else:
        beep_error()
        st.error(f"API Error: {res['error']}")

# ================================================================== #
#  UI                                                                 #
# ================================================================== #

st.title("🏭 AOP VISION MASTER v5.1")

col_cam, col_ctrl = st.columns([1.5, 1])

with col_cam:
    st.subheader("👁️ SKANER I PODGLĄD LIVE")

    def get_roi_config():
        import json
        p = os.path.join(os.path.dirname(__file__), "config_camera.json")
        if os.path.exists(p):
            with open(p, 'r') as f: return json.load(f)
        return {"cam_id": 1, "roi_x": 660, "roi_y": 440, "roi_w": 600, "roi_h": 200}

    roi_cfg = get_roi_config()
    cam_id  = roi_cfg["cam_id"]

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Operacje")
        if st.button("🖥️ KONFIGURATOR (OKNO)", use_container_width=True):
            import subprocess, sys
            script_path = os.path.join(os.path.dirname(__file__), "camera_monitor.py")
            subprocess.Popen([sys.executable, script_path])

        st.divider()
        st.caption("📷 Kamera")
        cam_options = {f"Kamera {i}": i for i in range(5)}
        selected_cam_label = st.selectbox("Wybierz kamerę:", list(cam_options.keys()),
                                          index=cam_id if cam_id < 5 else 0)
        new_cam_id = cam_options[selected_cam_label]
        if new_cam_id != cam_id:
            import json
            roi_cfg["cam_id"] = new_cam_id
            p = os.path.join(os.path.dirname(__file__), "config_camera.json")
            with open(p, 'w') as f: json.dump(roi_cfg, f)
            cam_id = new_cam_id
            st.success(f"Zapisano: {selected_cam_label}"); st.rerun()

        st.divider()
        live_toggle = st.toggle("📺 PODGLĄD W PRZEGLĄDARCE", value=False)
        mode = st.radio("Silnik Odczytu:",
                        ["Gemini 3 Pro (🎯 Najdokładniejszy ~14s)",
                         "Gemini Flash (⚡ Szybki ~3s)",
                         "Haiku 4.5 (🚀 Najszybszy ~2s)",
                         "Claude Sonnet (🎭 Dokładny ~6s)",
                         "Lokalny (🔒 Offline)"], index=2)

        st.divider()
        st.caption("🤖 Auto-Trigger")
        st.session_state.auto_trigger = st.toggle("🔄 AUTO-TRIGGER",
            value=st.session_state.auto_trigger,
            help="Wykrywa stabilność obrazu i odpala skan automatycznie")
        if st.session_state.auto_trigger:
            motion_val    = st.slider("Czułość ruchu (diff):", 5, 50, int(MOTION_THRESHOLD),
                                      help="Próg wykrycia wjazdu paczki. Za mało → reaguje na wibracje. Za dużo → nie widzi paczki.")
            stability_val = st.slider("Próg stabilności (diff):", 1, 20, int(STABILITY_THRESHOLD),
                                      help="Paczka 'stoi' gdy diff poniżej tej wartości. Zwiększ jeśli wibracje taśmy.")
            stable_n_val  = st.slider("Klatek stabilnych:", 1, 5, STABLE_FRAMES_NEEDED,
                                      help="Ile razy z rzędu musi być stabilnie (~1s każda klatka).")
            cooldown_val  = st.slider("Cooldown (s):", 3, 15, AUTO_COOLDOWN_SEC,
                                      help="Czas blokady po skanie — na zatwierdzenie i odsunięcie paczki.")
        else:
            motion_val    = MOTION_THRESHOLD
            stability_val = STABILITY_THRESHOLD
            stable_n_val  = STABLE_FRAMES_NEEDED
            cooldown_val  = AUTO_COOLDOWN_SEC

        st.divider()
        st.caption("🧠 Temporal Intelligence")
        last_times = get_last_confirmed_times(3)
        if last_times:
            st.write(f"Ostatni: **{last_times[0]}**")
            plaus, pmsg = is_time_plausible(last_times[0]) if len(last_times) > 1 else (True, "")
            st.caption(f"Oczekiwany: {last_times[0]} ±10 min")
        else:
            st.caption("Brak historii — pierwsza paczka.")

        st.divider()
        st.caption(f"💰 Koszt sesji: ~{st.session_state.cost_total:.3f} PLN")
        st.caption(f"📦 Skanów: {st.session_state.scan_count}")

    # --- PODGLAD LIVE ---
    preview_placeholder = st.empty()
    btn_snap = st.button("📸 SKANUJ PACZKĘ", type="primary", use_container_width=True)

    if live_toggle and not st.session_state.last_scan:
        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        try:
            while live_toggle:
                ret, frame = cap.read()
                if not ret or frame is None:
                    preview_placeholder.error("⚠️ Brak sygnału z kamery.")
                    break
                rx, ry, rw, rh = roi_cfg["roi_x"], roi_cfg["roi_y"], roi_cfg["roi_w"], roi_cfg["roi_h"]
                scale = 720/1080
                s_rx, s_ry = int(rx*scale), int(ry*scale)
                s_rw, s_rh = int(rw*scale), int(rh*scale)
                h_p, w_p, _ = frame.shape
                s_ry = max(0, min(h_p-1, s_ry)); s_rx = max(0, min(w_p-1, s_rx))
                roi_preview = frame[s_ry:s_ry+s_rh, s_rx:s_rx+s_rw]
                preview_placeholder.image(cv2.cvtColor(roi_preview, cv2.COLOR_BGR2RGB),
                                          caption="PODGLĄD LIVE", use_container_width=True)
                time.sleep(0.05)
        finally:
            cap.release()

    # --- LOGIKA SKANOWANIA ---
    if btn_snap:
        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        ret, frame = False, None
        for _ in range(5):
            ret, frame = cap.read()
            if ret and frame is not None: break
            time.sleep(0.1)
        cap.release()

        if ret and frame is not None:
            rx, ry, rw, rh = roi_cfg["roi_x"], roi_cfg["roi_y"], roi_cfg["roi_w"], roi_cfg["roi_h"]
            roi_frame = frame[ry:ry+rh, rx:rx+rw]
            img_pil   = Image.fromarray(cv2.cvtColor(roi_frame, cv2.COLOR_BGR2RGB))
            do_scan(roi_frame, img_pil, mode)
            st.rerun()
        else:
            beep_error()
            st.error("Kamera nie odpowiedziała.")

    # --- AUTO-TRIGGER PANEL ---
    @st.fragment(run_every=1)
    def auto_trigger_panel():
        st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
        if not st.session_state.auto_trigger:
            st.caption("⭕ Auto-Trigger: wyłączony")
            return

        now  = time.time()
        state = st.session_state.trigger_state

        # --- COOLDOWN: sprawdź czy minął ---
        if state == 'cooldown':
            remaining = st.session_state.trigger_cooldown_until - now
            if remaining > 0:
                st.caption(f"⏳ Cooldown: {remaining:.0f}s — czekam na następną paczkę")
                return
            else:
                st.session_state.trigger_state   = 'waiting_motion'
                st.session_state.stable_frames   = 0
                st.session_state.prev_roi_bytes  = None
                st.session_state.roi_history     = []
                state = 'waiting_motion'

        # --- CAPTURE ---
        at_roi_cfg = get_roi_config()
        at_cap = cv2.VideoCapture(at_roi_cfg['cam_id'], cv2.CAP_DSHOW)
        # Brak wymuszania rozdzielczości — kamera daje domyślną (np. 640×480), szybko
        ret, frame = at_cap.read()
        at_cap.release()
        if not ret or frame is None:
            st.caption("⚠️ Brak sygnału kamery")
            return

        # Skaluj współrzędne ROI z 1920×1080 do faktycznej rozdzielczości klatki
        fh, fw = frame.shape[:2]
        scale_x = fw / 1920.0
        scale_y = fh / 1080.0
        rx = int(at_roi_cfg["roi_x"] * scale_x)
        ry = int(at_roi_cfg["roi_y"] * scale_y)
        rw = max(1, int(at_roi_cfg["roi_w"] * scale_x))
        rh = max(1, int(at_roi_cfg["roi_h"] * scale_y))
        rx = min(rx, fw - 1); ry = min(ry, fh - 1)
        rw = min(rw, fw - rx); rh = min(rh, fh - ry)
        roi = frame[ry:ry+rh, rx:rx+rw]
        if roi.size == 0:
            st.caption(f"⚠️ ROI poza klatką ({fw}×{fh}) — ustaw ROI w Konfiguratorze")
            return
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # --- OBLICZ DIFF ---
        diff = 0.0
        if st.session_state.prev_roi_bytes is not None:
            prev = np.frombuffer(st.session_state.prev_roi_bytes, dtype=np.uint8).reshape(roi_gray.shape)
            diff = float(cv2.absdiff(roi_gray, prev).mean())

        # --- HISTORIA 3 KLATEK ---
        history = st.session_state.roi_history
        history.append({'img': roi_gray.copy(), 'diff': diff})
        if len(history) > 3:
            history = history[-3:]
        st.session_state.roi_history = history

        # --- PODGLĄD 3 KLATEK ---
        if len(history) >= 1:
            cols = st.columns(3)
            labels = ["(najstarsza)", "(środkowa)", "(bieżąca)"]
            padded = ([None] * (3 - len(history))) + history
            for i, entry in enumerate(padded):
                with cols[i]:
                    if entry is None:
                        st.caption("—")
                    else:
                        st.image(entry['img'], use_container_width=True, clamp=True)
                        d = entry['diff']
                        if d == 0.0:
                            icon = "🟡"
                        elif d < stability_val:
                            icon = "🟢"
                        elif d < motion_val:
                            icon = "🟠"
                        else:
                            icon = "🔴"
                        st.caption(f"{icon} diff={d:.1f}  {labels[i]}")

        # --- MASZYNA STANOWA ---
        if state == 'waiting_motion':
            st.caption("⏸️ Czeka na paczkę (brak ruchu = brak akcji)")
            # Ruch wykryty → przechodzimy do stabilizacji
            if diff > motion_val and st.session_state.prev_roi_bytes is not None:
                st.session_state.trigger_state  = 'waiting_stability'
                st.session_state.stable_frames  = 0

        elif state == 'waiting_stability':
            if diff < stability_val:
                st.session_state.stable_frames += 1
                st.caption(f"🔄 Paczka staje... {st.session_state.stable_frames}/{stable_n_val} klatek stabilnych")
                if st.session_state.stable_frames >= stable_n_val:
                    # === TRIGGER ===
                    img_pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
                    do_scan(roi, img_pil, mode)
                    st.session_state.stable_frames          = 0
                    st.session_state.trigger_state          = 'cooldown'
                    st.session_state.trigger_cooldown_until = time.time() + cooldown_val
                    st.rerun()
            else:
                # Paczka nadal w ruchu — reset licznika, zostajemy w tym stanie
                st.session_state.stable_frames = 0
                st.caption(f"🔴 Paczka jedzie... diff={diff:.1f}")

        # --- ZAPISZ KLATKĘ ---
        st.session_state.prev_roi_bytes = roi_gray.tobytes()

    auto_trigger_panel()

    # --- SEKCJA WERYFIKACJI / UZUPELNIENIA ---
    if st.session_state.last_scan:
        scan = st.session_state.last_scan
        st.image(scan["img"], caption="Zdjęcie do analizy", use_container_width=True)

        if st.session_state.need_time:
            # Tryb: brak godziny
            st.warning("🔔 Nie udało się odczytać godziny — uzupełnij ręcznie:")
            c1, c2, c3 = st.columns(3)
            c1.text_input("📦 Partia:", value=scan["batch"], disabled=True)
            c2.text_input("📅 Data:", value=scan["date"],  disabled=True)
            hint = scan.get("time_hint", datetime.now().strftime("%H:%M"))
            v_time = c3.text_input("🕒 Godzina (HH:MM):", value=hint,
                                   help="Wpisz godzinę z etykiety. Sekundy zostaną wyliczone automatycznie.")
            ca1, ca2 = st.columns(2)
            if ca1.button("✅ ZATWIERDŹ I DODAJ", type="primary", use_container_width=True):
                if validate_time_format(v_time):
                    db.add_job_from_ocr(scan['batch'], v_time)
                    beep_ok()
                    st.session_state.last_scan = None
                    st.session_state.need_time = False
                    st.rerun()
                else:
                    st.error("Niepoprawny format — wpisz HH:MM, np. 20:33")
            if ca2.button("🗑️ ODRZUĆ", use_container_width=True):
                st.session_state.last_scan = None
                st.session_state.need_time = False
                st.rerun()

        else:
            # Tryb: podejrzany czas — pelna weryfikacja
            if scan.get("warning"):
                st.warning(scan["warning"])
            st.markdown("### 📝 Weryfikacja danych")
            c1, c2, c3 = st.columns(3)
            v_batch = c1.text_input("📦 Numer Partii:", value=scan["batch"])
            v_date  = c2.text_input("📅 Data:",         value=scan["date"])
            v_time  = c3.text_input("🕒 Godzina:",      value=scan["time"])
            ca1, ca2 = st.columns(2)
            if ca1.button("✅ POTWIERDŹ I DODAJ DO KOLEJKI", type="primary", use_container_width=True):
                db.add_job_from_ocr(v_batch, v_time)
                beep_ok()
                st.session_state.last_scan = None; st.rerun()
            if ca2.button("🗑️ ODRZUĆ SKAN", use_container_width=True):
                st.session_state.last_scan = None; st.rerun()

# ================================================================== #
#  CENTRUM RPA                                                        #
# ================================================================== #

with col_ctrl:
    st.subheader("🕹️ Centrum RPA")
    c1, c2 = st.columns(2)
    if c1.button("▶️ START AUTO", type="primary", use_container_width=True):
        st.session_state.auto_mode = True; st.rerun()
    if c2.button("🛑 STOP", type="secondary", use_container_width=True):
        st.session_state.auto_mode = False; st.rerun()

    conn = sqlite3.connect(DB_PATH)
    next_job = conn.execute(
        "SELECT id, ocr_hhmm, calculated_hhmmss FROM jobs WHERE status='PENDING' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()

    if next_job:
        if st.button(f"🔥 DRUKUJ NASTĘPNĄ (ID {next_job[0]})", use_container_width=True):
            job_dict = {"id": next_job[0], "hhmm": next_job[1], "hhmmss": next_job[2]}
            update_job_status(job_dict['id'], 'PRINTING')
            if print_rpa_direct(job_dict, cfg):
                update_job_status(job_dict['id'], 'DONE')
                winsound.Beep(1000, 100); st.rerun()
    else:
        st.info("Brak paczek w kolejce.")

    st.divider()

    @st.fragment(run_every=3)
    def metrics_panel():
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT status FROM jobs", conn); conn.close()
        done_count = len(df[df['status'] == 'DONE'])
        m1, m2, m3 = st.columns(3)
        m1.metric("WYDRUKOWANO", done_count)
        m2.metric("W KOLEJCE",   len(df[df['status'] == 'PENDING']))
        cost = st.session_state.cost_total
        m3.metric("KOSZT", f"{cost:.3f} PLN")
    metrics_panel()

# ================================================================== #
#  OSTATNIE OPERACJE                                                  #
# ================================================================== #

st.divider()
st.subheader("📋 Ostatnie operacje")
conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT id, batch_id, ocr_hhmm, calculated_hhmmss, status, timestamp FROM jobs ORDER BY id DESC LIMIT 8"
).fetchall()
conn.close()

for r_id, batch, hhmm, hhmmss, status, ts in rows:
    with st.container():
        c_data, c_stat, c_btn = st.columns([3, 1, 1])
        icon = "✅" if status == "DONE" else ("⏳" if status == "PENDING" else "🖨️")
        ts_hms = ts[11:19] if ts and len(ts) >= 19 else "—"
        c_data.write(f"**ID {r_id}** `{ts_hms}` | {batch} | 🕒 **{hhmmss}**")
        c_stat.write(f"{icon} `{status}`")
        if c_btn.button("🖨️", key=f"re_{r_id}"):
            print_rpa_direct({"hhmm": hhmm, "hhmmss": hhmmss}, cfg)
