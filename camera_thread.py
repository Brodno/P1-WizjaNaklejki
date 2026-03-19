import os
os.environ['OPENCV_LOG_LEVEL'] = 'OFF'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

import cv2
import numpy as np
import time
from PyQt6.QtCore import QThread, pyqtSignal


class CameraThread(QThread):
    # Sygnały do MainWindow
    frame_ready      = pyqtSignal(object)        # np.ndarray BGR — ROI do skanowania
    full_frame_ready = pyqtSignal(object)        # np.ndarray BGR — pełna klatka do podglądu
    history_update   = pyqtSignal(list)          # lista dict: [{frame, diff}, ...]
    trigger_fired    = pyqtSignal(object)        # np.ndarray BGR — ROI gdy auto-trigger
    status_update    = pyqtSignal(str, str, float)  # state, message, diff
    quality_update   = pyqtSignal(float, list)   # score 0-1, lista boxów (x,y,w,h) w ROI

    def __init__(self, roi_cfg: dict):
        super().__init__()
        self._roi_cfg = roi_cfg
        self._running = False

        # Parametry auto-triggera (MainWindow ustawia przez property)
        self.auto_trigger         = False
        self.motion_threshold     = 15.0
        self.stability_threshold  = 5.0
        self.stable_frames_needed = 2
        self.cooldown_sec         = 5

        # Stan wewnętrzny maszyny stanowej
        self._state          = 'waiting_motion'
        self._stable_count   = 0
        self._prev_gray      = None
        self._cooldown_until = 0.0
        self._history        = []   # lista dict: {frame: ndarray BGR, diff: float}
        self._last_quality   = 0.0  # ostatni wynik jakości — gating triggera

        self.QUALITY_MIN     = 0.45  # próg "zielony" — poniżej nie strzelamy

    # ------------------------------------------------------------------ #
    #  Główna pętla wątku                                                  #
    # ------------------------------------------------------------------ #

    def update_roi(self, roi_cfg: dict):
        self._roi_cfg = roi_cfg

    def stop(self):
        self._running = False
        self.wait(3000)

    def run(self):
        self._running = True
        cam_id = self._roi_cfg.get('cam_id', 0)

        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        trigger_tick = 0

        while self._running:
            ret, frame = cap.read()
            if not ret or frame is None:
                self.status_update.emit('error', '⚠️ Brak sygnału kamery', 0.0)
                time.sleep(0.5)
                continue

            self.full_frame_ready.emit(frame.copy())

            roi = self._crop_roi(frame)
            if roi is not None and roi.size > 0:
                self.frame_ready.emit(roi.copy())

                # Auto-trigger sprawdzamy co ~1s (co 10 klatek przy 10fps)
                trigger_tick += 1
                if trigger_tick >= 10:
                    trigger_tick = 0
                    score, boxes = self._assess_quality(roi)
                    self._last_quality = score
                    self.quality_update.emit(score, boxes)
                    self._process_trigger(roi)

            time.sleep(0.1)   # ~10fps — wystarczy na podgląd live

        cap.release()

    # ------------------------------------------------------------------ #
    #  Maszyna stanowa auto-triggera                                       #
    # ------------------------------------------------------------------ #

    def _process_trigger(self, roi: np.ndarray):
        if not self.auto_trigger:
            self.status_update.emit('idle', '⭕ Auto-Trigger: wyłączony', 0.0)
            return

        now = time.time()

        # --- COOLDOWN ---
        if self._state == 'cooldown':
            remaining = self._cooldown_until - now
            if remaining > 0:
                self.status_update.emit('cooldown', f'⏳ Cooldown: {remaining:.0f}s', 0.0)
                return
            else:
                self._state        = 'waiting_motion'
                self._stable_count = 0
                self._prev_gray    = None
                self._history      = []

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # --- Oblicz diff ---
        diff = 0.0
        if self._prev_gray is not None:
            if self._prev_gray.shape != roi_gray.shape:
                self._prev_gray = cv2.resize(
                    self._prev_gray, (roi_gray.shape[1], roi_gray.shape[0]))
            diff = float(cv2.absdiff(roi_gray, self._prev_gray).mean())

        # --- Aktualizuj historię 3 klatek ---
        self._history.append({'frame': roi.copy(), 'diff': diff})
        if len(self._history) > 3:
            self._history = self._history[-3:]
        self.history_update.emit(list(self._history))

        # --- WAITING_MOTION ---
        if self._state == 'waiting_motion':
            self.status_update.emit('waiting', '⏸️ Czeka na paczkę...', diff)
            if diff > self.motion_threshold and self._prev_gray is not None:
                self._state        = 'waiting_stability'
                self._stable_count = 0

        # --- WAITING_STABILITY ---
        elif self._state == 'waiting_stability':
            if diff < self.stability_threshold:
                self._stable_count += 1
                msg = f'🔄 Stabilizacja: {self._stable_count}/{self.stable_frames_needed}'
                self.status_update.emit('stabilizing', msg, diff)
                if self._stable_count >= self.stable_frames_needed:
                    if self._last_quality < self.QUALITY_MIN:
                        # Jakość za niska — czekaj dalej, nie strzelaj
                        self.status_update.emit(
                            'stabilizing',
                            f'🔴 Czekam na czytelność... ({self._last_quality*100:.0f}% < {self.QUALITY_MIN*100:.0f}%)',
                            0.0)
                    else:
                        # === TRIGGER ===
                        self._state          = 'cooldown'
                        self._cooldown_until = now + self.cooldown_sec
                        self._stable_count   = 0
                        self.trigger_fired.emit(roi.copy())
            else:
                self._stable_count = 0
                self.status_update.emit('moving', f'🔴 Paczka jedzie... diff={diff:.1f}', diff)

        self._prev_gray = roi_gray

    # ------------------------------------------------------------------ #
    #  Helper                                                              #
    # ------------------------------------------------------------------ #

    def _assess_quality(self, roi: np.ndarray):
        """Zwraca (score 0-1, lista boxów tekstu w ROI).
        Szybkie — tylko OpenCV, bez modelu AI."""
        if roi is None or roi.size == 0:
            return 0.0, []

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Ostrość: wariancja Laplaciana — progi dostosowane do etykiet przemysłowych
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, sharpness / 80.0)   # było 300 — za wysokie

        # Kontrast lokalny — etykiety mają niższy globalny kontrast
        contrast_score = min(1.0, float(gray.std()) / 25.0)  # było 60

        # Gęstość krawędzi Canny — wyraźne litery = dużo krawędzi
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(edges.mean()) / 15.0   # 15 = próg dla czytelnego tekstu
        edge_score = min(1.0, edge_density)

        score = (sharpness_score * 0.4 + contrast_score * 0.3 + edge_score * 0.3)

        # Lokalizacja tekstu: MSER na szarej klatce (najlepszy dla drukowanego tekstu)
        h_roi, w_roi = gray.shape
        boxes = []
        try:
            mser = cv2.MSER_create(_min_area=30, _max_area=3000)
            regions, _ = mser.detectRegions(gray)
            raw_boxes = [cv2.boundingRect(r.reshape(-1, 1, 2)) for r in regions]

            for x, y, w, h in raw_boxes:
                if w < 5 or h < 5:
                    continue
                aspect = w / max(h, 1)
                # Proporcje litery/cyfry: wąskie pionowe lub kwadratowe
                if 0.2 < aspect < 4.0 and h < h_roi * 0.6:
                    boxes.append((x, y, w, h))

            # Ogranicz do max 40 boxów (najpierw większe)
            boxes = sorted(boxes, key=lambda b: b[2]*b[3], reverse=True)[:40]
        except Exception:
            pass

        return score, boxes

    def _crop_roi(self, frame: np.ndarray):
        fh, fw = frame.shape[:2]
        rx = min(self._roi_cfg['roi_x'], fw - 1)
        ry = min(self._roi_cfg['roi_y'], fh - 1)
        rw = min(self._roi_cfg['roi_w'], fw - rx)
        rh = min(self._roi_cfg['roi_h'], fh - ry)
        if rw <= 0 or rh <= 0:
            return None
        return frame[ry:ry+rh, rx:rx+rw]
