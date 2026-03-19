import tkinter as tk
import json
import os

CONFIG_FILE = 'config_rpa.json'

class VisualPins:
    def __init__(self, root):
        self.root = root
        self.root.title("AOP Visual Calibration")
        
        # Ustawienia przezroczystości i braku ramek
        self.root.attributes("-alpha", 0.4) # Przezroczystość 40%
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg='black')
        
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg='black', cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Ładowanie obecnej konfiguracji
        self.config = self.load_config()
        
        # Tworzenie pinezek (1, 2, 3)
        self.pins = []
        self.create_pin(self.config["PUNKT_HHMMSS"], "1", "#e74c3c", "PUNKT_HHMMSS")
        self.create_pin(self.config["PUNKT_HH_MM"], "2", "#2ecc71", "PUNKT_HH_MM")
        self.create_pin(self.config["PUNKT_DRUKUJ"], "3", "#3498db", "PUNKT_DRUKUJ")

        # Instrukcja na ekranie
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2, 50,
            text="📍 PRZECIĄGNIJ KROPKI NAD POLA W ZEBRA DESIGNER. NACIŚNIJ 'S' ABY ZAPISAĆ I WYJŚĆ.",
            fill="white", font=("Arial", 16, "bold")
        )

        self.root.bind("<Key-s>", lambda e: self.save_and_exit())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        return {"PUNKT_HHMMSS": [100, 100], "PUNKT_HH_MM": [100, 150], "PUNKT_DRUKUJ": [100, 200]}

    def create_pin(self, pos, label, color, config_key):
        r = 15 # promień kropki
        x, y = pos
        tag = f"pin_{label}"
        
        # Kółko
        oval = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="white", width=2, tags=tag)
        # Numer
        text = self.canvas.create_text(x, y, text=label, fill="white", font=("Arial", 10, "bold"), tags=tag)
        
        # Bindowanie przeciągania
        self.canvas.tag_bind(tag, "<B1-Motion>", lambda e, t=tag, k=config_key: self.move_pin(e, t, k))

    def move_pin(self, event, tag, config_key):
        x, y = event.x, event.y
        r = 15
        # Aktualizacja pozycji na płótnie
        self.canvas.coords(tag, x-r, y-r, x+r, y+r) # Kółko (id 1 w grupie tagów)
        # Przesunięcie tekstu też (brzydkie ale działa - tekst to drugi element w grupie)
        items = self.canvas.find_withtag(tag)
        self.canvas.coords(items[1], x, y)
        
        # Aktualizacja w pamięci
        self.config[config_key] = [x, y]

    def save_and_exit(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VisualPins(root)
    root.mainloop()
