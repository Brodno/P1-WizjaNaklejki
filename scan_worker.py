import cv2
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal


class ScanWorker(QThread):
    scan_done  = pyqtSignal(dict, object)  # result dict, PIL.Image
    scan_error = pyqtSignal(str)

    def __init__(self, vision, roi_frame, mode_str: str):
        super().__init__()
        self.vision    = vision
        self.roi_frame = roi_frame
        self.mode_str  = mode_str

    def run(self):
        try:
            img_pil = Image.fromarray(cv2.cvtColor(self.roi_frame, cv2.COLOR_BGR2RGB))

            if 'Gemini 3 Pro' in self.mode_str:
                res = self.vision.analyze_with_gemini3_pro(img_pil)
                if 'error' in res:
                    res = self.vision.analyze_with_haiku_4_5(img_pil)
                res['_cost'] = 0.008

            elif 'Gemini Flash' in self.mode_str:
                res = self.vision.analyze_with_gemini3_flash(img_pil)
                if 'error' in res:
                    res = self.vision.analyze_with_haiku_4_5(img_pil)
                res['_cost'] = 0.003

            elif 'Haiku' in self.mode_str:
                res = self.vision.analyze_with_haiku_4_5(img_pil)
                res['_cost'] = 0.004

            elif 'Sonnet' in self.mode_str:
                res = self.vision.analyze_with_sonnet_4_6(img_pil)
                res['_cost'] = 0.08

            else:
                res = self.vision.analyze_locally(self.roi_frame)
                res['_cost'] = 0.0

            self.scan_done.emit(res, img_pil)

        except Exception as e:
            self.scan_error.emit(str(e))
