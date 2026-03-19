import os, sys, re, time, sqlite3, winsound
os.environ['OPENCV_LOG_LEVEL'] = 'OFF'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

import cv2
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSlider, QCheckBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QLineEdit, QFrame, QScrollArea,
    QSizePolicy, QSplitter, QMessageBox, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, QSize, QProcess, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor

from config_manager import load_config
from db_manager import VisionPrintSystem
from vision_engine import AOPVision
from camera_thread import CameraThread
from scan_worker import ScanWorker

# ================================================================== #
#  STAŁE                                                             #
# ================================================================== #

DB_PATH = os.path.join(os.path.dirname(__file__), 'aop_production.db')
TIME_RE = re.compile(r'^(\d{1,2}):(\d{2})$')

# ================================================================== #
#  WALIDACJA (kopia z dashboard.py)                                  #
# ================================================================== #

def validate_field(val):
    if not val: return False
    return val.strip().upper() not in ('?', 'N/A', 'UNKNOWN', 'UNREADABLE', '', '00:00', 'NONE')

def validate_time_format(val):
    m = TIME_RE.match(str(val or ''))
    if not m: return False
    h, mn = int(m.group(1)), int(m.group(2))
    return 0 <= h <= 23 and 0 <= mn <= 59

def get_last_confirmed_times(n=5):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ocr_hhmm FROM jobs ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]

def is_time_plausible(time_str, tolerance_min=10):
    times = get_last_confirmed_times(5)
    if not times: return True, ""
    try:
        ocr_dt = datetime.strptime(time_str, "%H:%M")
    except:
        return False, f"Niepoprawny format: {time_str}"
    try:
        last_dt = datetime.strptime(times[0], "%H:%M")
    except:
        return True, ""
    diff = abs((ocr_dt - last_dt).total_seconds()) / 60
    if diff > 720: diff = 1440 - diff
    if diff > tolerance_min:
        return False, f"⚠️ {time_str} odbiega o {diff:.0f} min od ostatniego ({times[0]})"
    return True, ""

def ocr_status(res):
    batch = res.get('batch', '')
    date  = res.get('date',  '')
    t     = res.get('time',  '')
    if not validate_field(batch) or not validate_field(date):
        return 'error', "Brak numeru partii lub daty"
    if not validate_field(t) or not validate_time_format(t):
        times = get_last_confirmed_times(3)
        hint = times[0] if times else datetime.now().strftime("%H:%M")
        return 'brak_czasu', hint
    plausible, msg = is_time_plausible(t)
    if not plausible:
        return 'podejrzany', msg
    return 'ok', None

# ================================================================== #
#  DŹWIĘKI                                                           #
# ================================================================== #

def beep_ok():
    winsound.Beep(1200, 120); time.sleep(0.05); winsound.Beep(1500, 80)

def beep_warning():
    winsound.Beep(600, 300); time.sleep(0.05); winsound.Beep(400, 300)

def beep_manual():
    winsound.Beep(500, 500)

def beep_error():
    winsound.Beep(300, 800)

# ================================================================== #
#  HELPER — numpy → QPixmap                                          #
# ================================================================== #

def to_pixmap(bgr: np.ndarray, size: QSize = None) -> QPixmap:
    if bgr is None or bgr.size == 0:
        return QPixmap()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
    pm = QPixmap.fromImage(qimg)
    if size:
        pm = pm.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    return pm

# ================================================================== #
#  CIEMNY STYL                                                       #
# ================================================================== #

STYLE = """
QMainWindow, QWidget       { background: #0d1117; color: #e0e0e0; font-family: 'Segoe UI'; font-size: 13px; }
QGroupBox                  { border: 1px solid #30363d; border-radius: 6px; margin-top: 10px; padding-top: 6px; }
QGroupBox::title           { subcontrol-origin: margin; left: 10px; color: #8b949e; font-size: 11px; }
QPushButton                { background: #21262d; border: 1px solid #30363d; border-radius: 5px; padding: 6px 14px; }
QPushButton:hover          { background: #30363d; }
QPushButton#btn_scan       { background: #1f6feb; font-size: 15px; font-weight: bold; padding: 10px; }
QPushButton#btn_scan:hover { background: #388bfd; }
QPushButton#btn_scan:disabled { background: #21262d; color: #484f58; }
QPushButton#btn_ok         { background: #238636; }
QPushButton#btn_ok:hover   { background: #2ea043; }
QPushButton#btn_rej        { background: #b91c1c; }
QPushButton#btn_rej:hover  { background: #dc2626; }
QPushButton#btn_print      { background: #7c3aed; }
QPushButton#btn_print:hover{ background: #8b5cf6; }
QLabel#lbl_cam             { background: #161b22; border: 2px solid #30363d; border-radius: 6px; }
QLabel#lbl_clock           { color: #8b949e; font-size: 20px; font-family: Consolas; }
QLabel#lbl_status          { padding: 5px; border-radius: 4px; background: #161b22; }
QComboBox                  { background: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 4px 8px; }
QComboBox::drop-down       { border: none; }
QLineEdit                  { background: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 4px 8px; }
QSlider::groove:horizontal { height: 4px; background: #30363d; border-radius: 2px; }
QSlider::handle:horizontal { background: #1f6feb; width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }
QTableWidget               { background: #0d1117; border: 1px solid #30363d; gridline-color: #21262d; }
QTableWidget::item         { padding: 3px 6px; }
QTableWidget::item:selected{ background: #1f6feb; }
QHeaderView::section       { background: #161b22; border: none; border-bottom: 1px solid #30363d; padding: 4px 6px; color: #8b949e; font-size: 11px; }
QScrollBar:vertical        { background: #0d1117; width: 8px; }
QScrollBar::handle:vertical{ background: #30363d; border-radius: 4px; min-height: 20px; }
QCheckBox                  { spacing: 6px; }
QCheckBox::indicator       { width: 16px; height: 16px; border: 1px solid #30363d; border-radius: 3px; background: #21262d; }
QCheckBox::indicator:checked { background: #1f6feb; border-color: #1f6feb; }
"""

# ================================================================== #
#  CAMERA VIEW — podgląd z ROI, zoom kółkiem, przeciągnij prostokąt #
# ================================================================== #

class CameraView(QWidget):
    roi_changed = pyqtSignal(dict)   # emituje nowy roi gdy użytkownik narysuje

    def __init__(self, roi_cfg: dict, parent=None):
        super().__init__(parent)
        self._pixmap     = None
        self._frame_size = (1920, 1080)
        self._roi        = roi_cfg.copy()
        self._zoom        = 1.0
        self._drawing     = False
        self._drag_start  = None
        self._drag_end    = None
        self._quality     = -1.0   # -1 = brak danych
        self._text_boxes  = []     # boxy tekstu w ROI

        self.setMinimumHeight(300)
        self.setFixedHeight(340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet("background:#161b22; border:2px solid #30363d; border-radius:6px;")

    def set_full_frame(self, frame_bgr: np.ndarray):
        self._frame_size = (frame_bgr.shape[1], frame_bgr.shape[0])
        rgb  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        self._pixmap = QPixmap.fromImage(
            QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888))
        self.update()

    def update_roi(self, roi_cfg: dict):
        self._roi = roi_cfg.copy()
        self.update()

    def set_quality(self, score: float, boxes: list):
        self._quality    = score
        self._text_boxes = boxes
        self.update()

    # ---------- RYSOWANIE ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap is None:
            painter.setPen(QColor('#8b949e'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Inicjalizacja kamery...")
            return

        # Skaluj klatkę do widgetu z zachowaniem proporcji i zoom
        fw, fh = self._frame_size
        ww, wh = self.width(), self.height()
        base_scale = min(ww / fw, wh / fh) * self._zoom
        disp_w = int(fw * base_scale)
        disp_h = int(fh * base_scale)
        ox = (ww - disp_w) // 2
        oy = (wh - disp_h) // 2

        pm = self._pixmap.scaled(disp_w, disp_h,
                                  Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(ox, oy, pm)

        # Zielony prostokąt ROI
        def to_widget(rx, ry, rw, rh):
            return (int(rx * base_scale) + ox,
                    int(ry * base_scale) + oy,
                    int(rw * base_scale),
                    int(rh * base_scale))

        rx, ry, rw, rh = to_widget(
            self._roi['roi_x'], self._roi['roi_y'],
            self._roi['roi_w'], self._roi['roi_h'])
        painter.setPen(QPen(QColor('#00ff88'), 2))
        painter.drawRect(rx, ry, rw, rh)
        painter.setPen(QColor('#00ff88'))
        painter.drawText(rx + 4, ry - 6, "ROI")

        # Żółty prostokąt podczas rysowania
        if self._drawing and self._drag_start and self._drag_end:
            x1, y1 = self._drag_start
            x2, y2 = self._drag_end
            painter.setPen(QPen(QColor('#ffdd00'), 2, Qt.PenStyle.DashLine))
            painter.drawRect(min(x1, x2), min(y1, y2),
                             abs(x2 - x1), abs(y2 - y1))

        # Boxy wykrytego tekstu (niebieskie, w obszarze ROI)
        if self._text_boxes:
            painter.setPen(QPen(QColor('#38bdf8'), 1))
            for (bx, by, bw, bh) in self._text_boxes:
                wx = int(bx * base_scale) + rx
                wy = int(by * base_scale) + ry
                wbw = int(bw * base_scale)
                wbh = int(bh * base_scale)
                painter.drawRect(wx, wy, wbw, wbh)

        # Wskaźnik jakości — kolorowy pasek i opis
        if self._quality >= 0:
            q = self._quality
            if q >= 0.45:
                color, label = '#22c55e', f'🟢 CZYTELNY  {q*100:.0f}%'
            elif q >= 0.20:
                color, label = '#f59e0b', f'🟡 SŁABY     {q*100:.0f}%'
            else:
                color, label = '#ef4444', f'🔴 NIECZYTELNY {q*100:.0f}%'

            # Pasek jakości pod prostokątem ROI
            bar_y = ry + rh + 6
            bar_w = rw
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#30363d'))
            painter.drawRect(rx, bar_y, bar_w, 6)
            painter.setBrush(QColor(color))
            painter.drawRect(rx, bar_y, int(bar_w * q), 6)

            # Napis
            painter.setPen(QColor(color))
            painter.drawText(rx, bar_y + 20, label)

            # Kolorowa ramka całego ROI
            painter.setPen(QPen(QColor(color), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rx, ry, rw, rh)

        # Info zoom
        painter.setPen(QColor('#8b949e'))
        painter.drawText(6, 16, f"zoom: {self._zoom:.1f}×  |  przeciągnij = nowe ROI  |  scroll = zoom")

    # ---------- MYSZ ----------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing    = True
            p = event.pos()
            self._drag_start = (p.x(), p.y())
            self._drag_end   = (p.x(), p.y())

    def mouseMoveEvent(self, event):
        if self._drawing:
            p = event.pos()
            self._drag_end = (p.x(), p.y())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            p = event.pos()
            self._drag_end = (p.x(), p.y())
            self._apply_drag_as_roi()
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self._zoom = min(4.0, self._zoom * 1.15)
        else:
            self._zoom = max(0.3, self._zoom / 1.15)
        self.update()

    # ---------- PRZELICZ ----------

    def _apply_drag_as_roi(self):
        if not self._drag_start or not self._drag_end or not self._pixmap:
            return
        x1, y1 = self._drag_start
        x2, y2 = self._drag_end
        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            return   # za mały prostokąt — ignoruj

        fw, fh = self._frame_size
        ww, wh = self.width(), self.height()
        base_scale = min(ww / fw, wh / fh) * self._zoom
        ox = (ww - int(fw * base_scale)) // 2
        oy = (wh - int(fh * base_scale)) // 2

        rx = max(0, int((min(x1, x2) - ox) / base_scale))
        ry = max(0, int((min(y1, y2) - oy) / base_scale))
        rw = max(20, int(abs(x2 - x1) / base_scale))
        rh = max(20, int(abs(y2 - y1) / base_scale))
        rw = min(rw, fw - rx)
        rh = min(rh, fh - ry)

        self._roi = {**self._roi, 'roi_x': rx, 'roi_y': ry, 'roi_w': rw, 'roi_h': rh}
        self.roi_changed.emit(self._roi)


# ================================================================== #
#  GŁÓWNE OKNO                                                       #
# ================================================================== #

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏭 AOP VISION MASTER v6.0 — PyQt6")
        self.setMinimumSize(1100, 680)
        self.resize(1400, 800)
        self.setStyleSheet(STYLE)

        self.cfg    = load_config()
        self.db     = VisionPrintSystem(DB_PATH)
        self.vision = AOPVision()

        self._scan_count    = 0
        self._cost_total    = 0.0
        self._last_roi      = None   # ostatnia klatka ROI z kamery
        self._scan_worker   = None
        self._roi_cfg       = self._load_roi_cfg()
        self._pending_img   = None   # PIL Image czekający na weryfikację (Shadow Learning)
        self._last_quality  = None   # ostatni wynik jakości OCR (0-1)

        # Timer odliczający sekundy podczas skanu
        self._scan_elapsed  = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._build_ui()
        self._start_camera()
        self._start_timers()

    # ------------------------------------------------------------------ #
    #  KONFIGURACJA                                                        #
    # ------------------------------------------------------------------ #

    def _load_roi_cfg(self) -> dict:
        import json
        p = os.path.join(os.path.dirname(__file__), 'config_camera.json')
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
        return {"cam_id": 1, "roi_x": 660, "roi_y": 440, "roi_w": 600, "roi_h": 200}

    # ------------------------------------------------------------------ #
    #  BUDOWANIE UI                                                        #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_left(), stretch=2)
        layout.addWidget(self._build_right(), stretch=1)

    # ---------- LEWY PANEL ----------

    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)

        # Zegar
        self.lbl_clock = QLabel(self._now())
        self.lbl_clock.setObjectName('lbl_clock')
        self.lbl_clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.lbl_clock)

        # Podgląd kamery z ROI
        self.cam_view = CameraView(self._roi_cfg)
        self.cam_view.roi_changed.connect(self._on_roi_changed)
        lay.addWidget(self.cam_view)

        # Historia 3 klatek
        lay.addWidget(self._build_history_panel())

        # Status auto-triggera
        self.lbl_status = QLabel("⭕ Auto-Trigger: wyłączony")
        self.lbl_status.setObjectName('lbl_status')
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_status)

        # Przycisk skan
        self.btn_scan = QPushButton("📸  SKANUJ PACZKĘ")
        self.btn_scan.setObjectName('btn_scan')
        self.btn_scan.setMinimumHeight(50)
        self.btn_scan.clicked.connect(self._on_scan_clicked)
        lay.addWidget(self.btn_scan)

        # Panel weryfikacji (ukryty)
        self.verify_panel = self._build_verify_panel()
        self.verify_panel.hide()
        lay.addWidget(self.verify_panel)

        return w

    def _build_history_panel(self) -> QGroupBox:
        grp = QGroupBox("Ostatnie 3 klatki ROI")
        lay = QHBoxLayout(grp)
        self._hist_imgs  = []
        self._hist_diffs = []
        labels = ["najstarsza", "środkowa", "bieżąca"]
        for i in range(3):
            col = QVBoxLayout()
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setMinimumHeight(80)
            img_lbl.setStyleSheet("background:#161b22; border:1px solid #30363d; border-radius:4px;")
            diff_lbl = QLabel(f"— ({labels[i]})")
            diff_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            diff_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
            col.addWidget(img_lbl)
            col.addWidget(diff_lbl)
            lay.addLayout(col)
            self._hist_imgs.append(img_lbl)
            self._hist_diffs.append(diff_lbl)
        return grp

    def _build_verify_panel(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet("QFrame{background:#161b22; border:1px solid #d29922; border-radius:6px; padding:6px;}")
        lay = QVBoxLayout(f)

        self.lbl_verify_msg = QLabel("🔔 Uzupełnij dane")
        self.lbl_verify_msg.setStyleSheet("font-weight:bold; color:#d29922; font-size:14px;")
        lay.addWidget(self.lbl_verify_msg)

        fields = QHBoxLayout()
        self.edit_batch = QLineEdit(); self.edit_batch.setPlaceholderText("Partia")
        self.edit_date  = QLineEdit(); self.edit_date.setPlaceholderText("Data DD/MM/YYYY")
        self.edit_time  = QLineEdit(); self.edit_time.setPlaceholderText("HH:MM")
        for lbl_txt, edit in [("Partia:", self.edit_batch), ("Data:", self.edit_date), ("Godzina:", self.edit_time)]:
            fields.addWidget(QLabel(lbl_txt))
            fields.addWidget(edit)
        lay.addLayout(fields)

        btns = QHBoxLayout()
        btn_ok  = QPushButton("✅ ZATWIERDŹ I DODAJ"); btn_ok.setObjectName('btn_ok')
        btn_rej = QPushButton("🗑️ ODRZUĆ");           btn_rej.setObjectName('btn_rej')
        btn_ok.clicked.connect(self._on_verify_ok)
        btn_rej.clicked.connect(self._on_verify_reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_rej)
        lay.addLayout(btns)
        return f

    # ---------- PRAWY PANEL ----------

    def _build_right(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        scroll.setMaximumWidth(380)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setSpacing(8)

        lay.addWidget(self._build_settings())
        lay.addWidget(self._build_rpa())
        lay.addWidget(self._build_metrics())
        lay.addWidget(self._build_table())
        lay.addStretch()

        scroll.setWidget(inner)
        return scroll

    def _build_settings(self) -> QGroupBox:
        grp = QGroupBox("⚙️ Ustawienia")
        lay = QVBoxLayout(grp)

        btn_cfg = QPushButton("🖥️ KONFIGURATOR ROI (osobne okno)")
        btn_cfg.clicked.connect(self._open_konfigurator)
        lay.addWidget(btn_cfg)

        lay.addWidget(QLabel("Silnik OCR:"))
        self.combo_engine = QComboBox()
        self.combo_engine.addItems([
            "Gemini 3 Pro  🎯 (~14s najdokładniejszy)",
            "Gemini Flash  ⚡ (~3s szybki)",
            "Haiku 4.5     🚀 (~2s najszybszy)",
            "Claude Sonnet 🎭 (~6s dokładny)",
            "Lokalny       🔒 (offline)",
        ])
        self.combo_engine.setCurrentIndex(0)
        lay.addWidget(self.combo_engine)

        # Auto-trigger toggle
        self.chk_auto = QCheckBox("🔄  AUTO-TRIGGER")
        self.chk_auto.setStyleSheet("font-weight:bold; font-size:14px; color:#3fb950; padding:4px 0;")
        self.chk_auto.stateChanged.connect(self._on_auto_toggle)
        lay.addWidget(self.chk_auto)

        # Panel sliderów (ukryty gdy AT wyłączony)
        self.at_panel = QWidget()
        at_lay = QVBoxLayout(self.at_panel)
        at_lay.setContentsMargins(0, 0, 0, 0)
        at_lay.setSpacing(4)

        self._sl_motion    = self._slider_row(at_lay, "Czułość ruchu (wjazd):",    5,  50, 15)
        self._sl_stability = self._slider_row(at_lay, "Próg stabilności (stój):",  1,  20,  5)
        self._sl_frames    = self._slider_row(at_lay, "Klatek stabilnych:",         1,   5,  2)
        self._sl_cooldown  = self._slider_row(at_lay, "Cooldown po skanie (s):",   3,  15,  5)

        lay.addWidget(self.at_panel)
        self.at_panel.hide()
        return grp

    def _slider_row(self, parent_lay, label: str, min_v, max_v, default) -> QSlider:
        lbl = QLabel(label)
        lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        parent_lay.addWidget(lbl)

        row = QHBoxLayout()
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(min_v, max_v)
        sl.setValue(default)
        val_lbl = QLabel(str(default))
        val_lbl.setFixedWidth(28)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        sl.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
        sl.valueChanged.connect(self._sync_trigger_params)
        row.addWidget(sl)
        row.addWidget(val_lbl)
        parent_lay.addLayout(row)
        return sl

    def _build_rpa(self) -> QGroupBox:
        grp = QGroupBox("🕹️ Centrum RPA")
        lay = QVBoxLayout(grp)

        row = QHBoxLayout()
        btn_start = QPushButton("▶️ START AUTO")
        btn_stop  = QPushButton("■ STOP")
        row.addWidget(btn_start)
        row.addWidget(btn_stop)
        lay.addLayout(row)

        self.btn_print = QPushButton("🔥 DRUKUJ NASTĘPNĄ")
        self.btn_print.setObjectName('btn_print')
        self.btn_print.clicked.connect(self._on_print)
        lay.addWidget(self.btn_print)

        return grp

    def _build_metrics(self) -> QGroupBox:
        grp = QGroupBox("📊 Sesja")
        lay = QHBoxLayout(grp)

        self._m_done    = self._metric(lay, "WYDRUK.", "0")
        self._m_pending = self._metric(lay, "KOLEJKA", "0")
        self._m_cost    = self._metric(lay, "KOSZT",   "0.000")
        self._m_scans   = self._metric(lay, "SKANÓW",  "0")
        return grp

    def _metric(self, parent_lay, title: str, value: str) -> QLabel:
        col = QVBoxLayout()
        t = QLabel(title); t.setStyleSheet("color:#8b949e; font-size:10px;"); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v = QLabel(value); v.setStyleSheet("font-size:15px; font-weight:bold;"); v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(t); col.addWidget(v)
        parent_lay.addLayout(col)
        return v

    def _build_table(self) -> QGroupBox:
        grp = QGroupBox("📋 Ostatnie operacje")
        lay = QVBoxLayout(grp)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Czas", "Partia", "HHMMSS", "Status"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 65)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 60)
        lay.addWidget(self.table)

        # Log zdarzeń
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(100)
        self.log_box.setStyleSheet(
            "background:#0d1117; color:#8b949e; font-family:Consolas; font-size:11px; border:1px solid #30363d;")
        self.log_box.setPlaceholderText("Log zdarzeń...")
        lay.addWidget(self.log_box)

        return grp

    # ------------------------------------------------------------------ #
    #  URUCHOMIENIE                                                        #
    # ------------------------------------------------------------------ #

    def _start_camera(self):
        self.cam = CameraThread(self._roi_cfg)
        self.cam.full_frame_ready.connect(self.cam_view.set_full_frame)
        self.cam.frame_ready.connect(self._on_frame)
        self.cam.history_update.connect(self._on_history)
        self.cam.status_update.connect(self._on_status)
        self.cam.trigger_fired.connect(self._on_trigger)
        self.cam.quality_update.connect(self.cam_view.set_quality)
        self.cam.quality_update.connect(self._on_quality)
        self.cam.start()

    def _start_timers(self):
        QTimer(self, timeout=lambda: self.lbl_clock.setText(self._now()), interval=1000).start()
        QTimer(self, timeout=self._refresh_table, interval=3000).start()
        self._refresh_table()

    # ------------------------------------------------------------------ #
    #  SLOTY — KAMERA                                                      #
    # ------------------------------------------------------------------ #

    @pyqtSlot(object)
    def _on_frame(self, roi_bgr):
        self._last_roi = roi_bgr

    @pyqtSlot(list)
    def _on_history(self, history):
        # history: lista dict {frame: ndarray, diff: float}, max 3 elementy
        stability = self._sl_stability.value()
        motion    = self._sl_motion.value()
        padded    = ([None] * (3 - len(history))) + history
        labels    = ["najstarsza", "środkowa", "bieżąca"]

        for i, entry in enumerate(padded):
            if entry is None:
                self._hist_imgs[i].clear()
                self._hist_diffs[i].setText(f"— ({labels[i]})")
            else:
                pm = to_pixmap(entry['frame'], QSize(220, 90))
                self._hist_imgs[i].setPixmap(pm)
                d = entry['diff']
                if d == 0:         icon = "🟡"
                elif d < stability: icon = "🟢"
                elif d < motion:    icon = "🟠"
                else:               icon = "🔴"
                self._hist_diffs[i].setText(f"{icon} diff={d:.1f}  ({labels[i]})")

    @pyqtSlot(str, str, float)
    def _on_status(self, state, msg, diff):
        self.lbl_status.setText(msg)

    @pyqtSlot(object)
    def _on_trigger(self, roi_frame):
        self._run_scan(roi_frame)

    # ------------------------------------------------------------------ #
    #  SLOTY — SKAN                                                        #
    # ------------------------------------------------------------------ #

    def _on_scan_clicked(self):
        if self._last_roi is None:
            self.lbl_status.setText("⚠️ Brak klatki z kamery")
            return
        self._run_scan(self._last_roi.copy())

    def _tick_elapsed(self):
        self._scan_elapsed += 1
        self.btn_scan.setText(f"⏳  Analizuję... {self._scan_elapsed}s")

    def _run_scan(self, roi_frame):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self._scan_elapsed = 0
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("⏳  Analizuję... 0s")
        self._elapsed_timer.start()
        mode = self.combo_engine.currentText()
        self._log(f"Skan START — silnik: {mode.split()[0]}")
        self._scan_worker = ScanWorker(self.vision, roi_frame, mode)
        self._scan_worker.scan_done.connect(self._on_scan_done)
        self._scan_worker.scan_error.connect(self._on_scan_error)
        self._scan_worker.start()

    @pyqtSlot(dict, object)
    def _on_scan_done(self, res, img_pil):
        self._elapsed_timer.stop()
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText(f"📸  SKANUJ PACZKĘ  ({self._scan_elapsed}s)")
        self._scan_count  += 1
        self._cost_total  += res.get('_cost', 0.0)
        self._update_metrics()

        if 'error' in res:
            beep_error()
            msg = res['error']
            self._log(f"❌ API ERROR: {msg}")
            self.lbl_status.setText(f"❌ API Error: {msg}")
            QMessageBox.critical(self, "Błąd API", f"Skan nie powiódł się:\n\n{msg}")
            return

        batch = res.get('batch') or ''
        date  = res.get('date')  or ''
        t     = res.get('time')  or ''
        self._log(f"OCR: batch='{batch}'  date='{date}'  time='{t}'")

        status, detail = ocr_status(res)

        if status == 'ok':
            beep_ok()
            self.db.add_job_from_ocr(batch, t)
            self.db.save_training_sample(img_pil, batch, t, self._last_quality)
            self.lbl_status.setText(f"✅ AUTO-ZAPISANO: {batch} | {date} | {t}")
            self._log(f"✅ ZAPISANO: {batch} | {t} | jakość: {self._last_quality*100:.0f}%" if self._last_quality else f"✅ ZAPISANO: {batch} | {t}")
            self._refresh_table()

        elif status == 'brak_czasu':
            beep_manual()
            self._pending_img = img_pil
            self._log(f"🔔 Brak godziny — weryfikacja (hint: {detail})")
            self._show_verify(res, detail, need_time=True)

        elif status == 'podejrzany':
            beep_warning()
            self._pending_img = img_pil
            self._log(f"⚠️ Podejrzany czas: {detail}")
            self._show_verify(res, detail, need_time=False)

        else:
            # OCR nie dał rady — pokaż panel ręcznej korekty z tym co odczytano
            beep_manual()
            self._pending_img = img_pil
            self._log(f"🔔 Słaby odczyt — otwiera weryfikację ręczną")
            self._show_verify(res, '', need_time=False)

    @pyqtSlot(str)
    def _on_scan_error(self, msg):
        self._elapsed_timer.stop()
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("📸  SKANUJ PACZKĘ")
        beep_error()
        self._log(f"❌ WYJĄTEK: {msg}")
        self.lbl_status.setText(f"❌ Błąd: {msg}")
        QMessageBox.critical(self, "Błąd skanera", msg)

    # ------------------------------------------------------------------ #
    #  WERYFIKACJA                                                         #
    # ------------------------------------------------------------------ #

    def _show_verify(self, res, detail, need_time: bool):
        self.edit_batch.setText(res.get('batch') or '')
        self.edit_date.setText(res.get('date') or '')
        if need_time:
            self.edit_time.setText(detail or datetime.now().strftime("%H:%M"))
            self.lbl_verify_msg.setText(f"🔔 Brak godziny — uzupełnij (podpowiedź: {detail})")
            self.edit_batch.setReadOnly(True)
            self.edit_date.setReadOnly(True)
            self.edit_time.setReadOnly(False)
        else:
            self.edit_time.setText(res.get('time', ''))
            self.lbl_verify_msg.setText(f"⚠️ {detail}")
            self.edit_batch.setReadOnly(False)
            self.edit_date.setReadOnly(False)
            self.edit_time.setReadOnly(False)
        self.verify_panel.show()

    def _on_verify_ok(self):
        t     = self.edit_time.text().strip()
        batch = self.edit_batch.text().strip()
        if not validate_time_format(t):
            self.lbl_verify_msg.setText("❌ Niepoprawny format — wpisz HH:MM, np. 20:33")
            return
        self.db.add_job_from_ocr(batch, t)
        # Shadow Learning — zapisz próbkę z poprawionymi danymi
        if self._pending_img is not None:
            self.db.save_training_sample(self._pending_img, batch, t, self._last_quality)
            self._pending_img = None
        beep_ok()
        self.verify_panel.hide()
        self.lbl_status.setText(f"✅ Dodano ręcznie: {batch} | {t}")
        self._refresh_table()

    def _on_verify_reject(self):
        self.verify_panel.hide()
        self.lbl_status.setText("🗑️ Skan odrzucony")

    # ------------------------------------------------------------------ #
    #  AUTO-TRIGGER — ustawienia                                           #
    # ------------------------------------------------------------------ #

    def _open_konfigurator(self):
        script = os.path.join(os.path.dirname(__file__), "camera_monitor.py")
        if not os.path.exists(script):
            QMessageBox.warning(self, "Brak pliku", f"Nie znaleziono:\n{script}")
            return

        # Zatrzymaj kamerę — konfigurator potrzebuje wyłącznego dostępu
        self.cam.stop()
        self.lbl_cam.setText("⏸️ Kamera zatrzymana — konfigurator otwarty")
        self._log("⏸️ Kamera zatrzymana")

        # Uruchom konfigurator przez QProcess
        self._cfg_process = QProcess(self)
        self._cfg_process.finished.connect(self._on_konfigurator_closed)
        self._cfg_process.start(sys.executable, [script])
        self._log("🖥️ Konfigurator ROI otwarty")

    def _on_konfigurator_closed(self):
        self._log("✅ Konfigurator zamknięty — wznawiám kamerę")
        # Przeładuj config (operator mógł zmienić ROI)
        self._roi_cfg = self._load_roi_cfg()
        self._start_camera()

    @pyqtSlot(float, list)
    def _on_quality(self, score: float, boxes: list):
        self._last_quality = score

    def _on_roi_changed(self, roi: dict):
        import json
        self._roi_cfg.update(roi)
        self.cam.update_roi(self._roi_cfg)
        self.cam_view.update_roi(self._roi_cfg)
        p = os.path.join(os.path.dirname(__file__), 'config_camera.json')
        with open(p, 'w') as f:
            json.dump(self._roi_cfg, f)
        self._log(f"📐 ROI: x={roi['roi_x']} y={roi['roi_y']} w={roi['roi_w']} h={roi['roi_h']}")

    def _on_auto_toggle(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.at_panel.setVisible(enabled)
        self.cam.auto_trigger = enabled
        if not enabled:
            self.lbl_status.setText("⭕ Auto-Trigger: wyłączony")

    def _sync_trigger_params(self):
        if hasattr(self, 'cam'):
            self.cam.motion_threshold     = self._sl_motion.value()
            self.cam.stability_threshold  = self._sl_stability.value()
            self.cam.stable_frames_needed = self._sl_frames.value()
            self.cam.cooldown_sec         = self._sl_cooldown.value()

    # ------------------------------------------------------------------ #
    #  RPA                                                                 #
    # ------------------------------------------------------------------ #

    def _on_print(self):
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT id, ocr_hhmm, calculated_hhmmss FROM jobs WHERE status='PENDING' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        conn.close()
        if not row:
            self.lbl_status.setText("ℹ️ Brak paczek w kolejce")
            return
        import pyautogui
        job_id, hhmm, hhmmss = row
        self._set_job_status(job_id, 'PRINTING')
        try:
            ox, oy = pyautogui.position()
            pyautogui.click(self.cfg["PUNKT_HHMMSS"][0], self.cfg["PUNKT_HHMMSS"][1])
            pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
            pyautogui.typewrite(str(hhmmss), interval=0.01)
            pyautogui.click(self.cfg["PUNKT_HH_MM"][0], self.cfg["PUNKT_HH_MM"][1])
            pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
            pyautogui.typewrite(str(hhmm), interval=0.01)
            pyautogui.click(self.cfg["PUNKT_DRUKUJ"][0], self.cfg["PUNKT_DRUKUJ"][1])
            pyautogui.moveTo(ox, oy, duration=0.2)
            self._set_job_status(job_id, 'DONE')
            winsound.Beep(1000, 100)
            self.lbl_status.setText(f"🖨️ Wydrukowano ID {job_id}")
        except Exception as e:
            self.lbl_status.setText(f"❌ RPA błąd: {e}")
        self._refresh_table()

    def _set_job_status(self, job_id, status):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        conn.commit(); conn.close()

    # ------------------------------------------------------------------ #
    #  ODŚWIEŻANIE                                                         #
    # ------------------------------------------------------------------ #

    def _refresh_table(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT id, batch_id, ocr_hhmm, calculated_hhmmss, status, "
            "datetime(timestamp, 'localtime') FROM jobs ORDER BY id DESC LIMIT 8"
        ).fetchall()
        done    = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='DONE'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='PENDING'").fetchone()[0]
        conn.close()

        icons = {"DONE": "✅", "PENDING": "⏳", "PRINTING": "🖨️"}
        self.table.setRowCount(len(rows))
        for i, (r_id, batch, hhmm, hhmmss, status, ts) in enumerate(rows):
            ts_str = ts[11:19] if ts and len(ts) >= 19 else "—"
            self.table.setItem(i, 0, QTableWidgetItem(str(r_id)))
            self.table.setItem(i, 1, QTableWidgetItem(ts_str))
            self.table.setItem(i, 2, QTableWidgetItem(batch or ""))
            self.table.setItem(i, 3, QTableWidgetItem(hhmmss or ""))
            self.table.setItem(i, 4, QTableWidgetItem(f"{icons.get(status,'')} {status}"))

        self._m_done.setText(str(done))
        self._m_pending.setText(str(pending))
        self._update_metrics()

    def _update_metrics(self):
        self._m_cost.setText(f"{self._cost_total:.3f}")
        self._m_scans.setText(str(self._scan_count))

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{ts}] {msg}")

    def _now(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    # ------------------------------------------------------------------ #
    #  ZAMKNIĘCIE                                                          #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        self.cam.stop()
        event.accept()


# ================================================================== #
#  ENTRY POINT                                                        #
# ================================================================== #

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
