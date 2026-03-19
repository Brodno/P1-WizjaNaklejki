import tkinter as tk
from tkinter import messagebox, filedialog
import requests
import io
from PIL import Image, ImageTk
import os
import re

# Próba importu OCR
try:
    import pytesseract
    # Domyślna ścieżka w Windows - sprawdź czy masz tu zainstalowany Tesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

class LavazzaLabelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AOP - Lavazza Label Pro v2 (OCR + Kalibracja)")
        self.root.geometry("1200x800")

        # --- KONFIGURACJA DANYCH DOMYŚLNYCH ---
        self.fields = {
            'big_id': '03598',
            'packs': '20 PACKS',
            'weight': '250 g',
            'batch': 'AH30GA',
            'ean': '8000070135987',
            'date_bb': '30/06/2027',
            'date_prod': '30/07/2025 19:05',
            'gs1_top': '(91)0359811302(11)250730(93)190509',
            'gs1_bot': '(01)08000070135987(15)270630(10)AH30GA'
        }
        
        self.entries = {}
        self.create_widgets()

    def create_widgets(self):
        # Panel boczny na dane
        left_panel = tk.Frame(self.root, width=400, padx=10, pady=10)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)

        # Sekcja OCR
        ocr_frame = tk.LabelFrame(left_panel, text="Automatyzacja", padx=5, pady=5)
        ocr_frame.pack(fill=tk.X, pady=10)
        
        btn_text = "WCZYTAJ DANE ZE ZDJĘCIA 📸" if HAS_OCR else "BRAK TESSERACT OCR"
        state = tk.NORMAL if HAS_OCR else tk.DISABLED
        tk.Button(ocr_frame, text=btn_text, command=self.load_from_image, bg="#ff9800", fg="white", state=state).pack(fill=tk.X)
        if not HAS_OCR:
            tk.Label(ocr_frame, text="Zainstaluj Tesseract-OCR i bibliotekę pytesseract", fg="red", font=("Arial", 8)).pack()

        # Sekcja Pól
        tk.Label(left_panel, text="DANE DO EDYCJI", font=("Arial", 12, "bold")).pack(pady=10)

        for key, value in self.fields.items():
            frame = tk.Frame(left_panel)
            frame.pack(fill=tk.X, pady=2)
            lbl = key.replace('_', ' ').upper()
            tk.Label(frame, text=lbl, width=15, anchor='w', font=("Arial", 9)).pack(side=tk.LEFT)
            entry = tk.Entry(frame)
            entry.insert(0, value)
            entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
            self.entries[key] = entry

        # Przyciski akcji
        tk.Button(left_panel, text="ODŚWIEŻ PODGLĄD", command=self.update_preview, bg="#4CAF50", fg="white", height=2).pack(fill=tk.X, pady=20)
        tk.Button(left_panel, text="ZAPISZ PLIK .ZPL", command=self.save_zpl, bg="#2196F3", fg="white").pack(fill=tk.X, pady=5)
        
        # Panel prawy na podgląd
        right_panel = tk.Frame(self.root, bg="#dddddd")
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.preview_label = tk.Label(right_panel, text="Tutaj pojawi się etykieta", bg="white")
        self.preview_label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

    def load_from_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Obrazy", "*.jpg *.jpeg *.png")])
        if not file_path:
            return

        try:
            # Wczytanie obrazu
            img = Image.open(file_path)
            
            # OCR - czytanie tekstu
            text = pytesseract.image_to_string(img)
            print("--- Odczytany tekst ---")
            print(text)
            print("-----------------------")
            
            # Proste parsowanie (Regex) - szukamy wzorców
            
            # 1. Znajdź kod EAN (13 cyfr zaczynające się od 8)
            ean_match = re.search(r'8\d{12}', text.replace(" ", ""))
            if ean_match:
                self.entries['ean'].delete(0, tk.END)
                self.entries['ean'].insert(0, ean_match.group(0))

            # 2. Znajdź Daty (format DD/MM/YYYY)
            dates = re.findall(r'\d{2}/\d{2}/\d{4}', text)
            if len(dates) >= 1:
                self.entries['date_bb'].delete(0, tk.END)
                self.entries['date_bb'].insert(0, dates[0])
            if len(dates) >= 2:
                # Często data produkcji jest druga lub ma obok godzinę
                prod_match = re.search(r'(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})?', text)
                # To wymaga lepszego dopasowania w zależności od układu tekstu z OCR
                # Tutaj proste przypisanie drugiej znalezionej daty
                self.entries['date_prod'].delete(0, tk.END)
                self.entries['date_prod'].insert(0, dates[1] + " 19:05") # Godzinę często trudno złapać, wstawiam placeholder

            # 3. Batch No (szukamy słowa BATCH i bierzemy to co po nim)
            batch_match = re.search(r'BATCH\s*NO\\.?\s*([A-Z0-9]+)', text, re.IGNORECASE)
            if batch_match:
                self.entries['batch'].delete(0, tk.END)
                self.entries['batch'].insert(0, batch_match.group(1))

            # 4. Duży numer ID (np. 03598) - zazwyczaj 5 cyfr na początku lub osobno
            id_match = re.search(r'\b\d{5}\b', text)
            if id_match:
                self.entries['big_id'].delete(0, tk.END)
                self.entries['big_id'].insert(0, id_match.group(0))
                
            messagebox.showinfo("OCR Zakończony", "Dane zostały uzupełnione. Sprawdź poprawność.")
            self.update_preview()

        except Exception as e:
            messagebox.showerror("Błąd OCR", f"Nie udało się odczytać tekstu: {e}\nUpewnij się, że Tesseract jest zainstalowany.")

    def get_zpl_code(self):
        d = {k: v.get() for k, v in self.entries.items()}
        
        # Formatowanie danych GS1
        gs1_top_raw = ">8" + d['gs1_top'].replace('(', '').replace(')', '')
        gs1_bot_raw = ">8" + d['gs1_bot'].replace('(', '').replace(')', '')

        # --- ZAAWANSOWANY LAYOUT ZPL ---
        # Poprawione pozycje na podstawie zdjęcia "Zrzut ekranu"
        # 120mm x 90mm @ 203dpi = 960 x 720 dots
        
        zpl = f"""^XA
^PW960^LL720^UTF8

// PIONOWY TEKST (LEWA KRAWĘDŹ)
^FO10,20^A0R,24,24^FDLuigi Lavazza S.p.A. - Via Bologna, 32 - 10152 Torino - Italia.^FS
^FO35,20^A0R,24,24^FDFARD. 20 PC. QUALITA' ROSSA INT 1 250 M GROUND COFFEE^FS

// GŁÓWNY BLOK
// 03598 - Pogrubiony (podwójny druk) i duży
^FO120,40^A0N,105,95^FD{d['big_id']}^FS
^FO122,40^A0N,105,95^FD{d['big_id']}^FS

// 20 PACKS
^FO120,140^A0N,32,32^FD{d['packs']}^FS
^FO121,140^A0N,32,32^FD{d['packs']}^FS

// OF e 250 g
^FO120,185^A0N,32,32^FDOF e {d['weight']}^FS
^FO121,185^A0N,32,32^FDOF e {d['weight']}^FS

// BATCH NO.
^FO120,235^A0N,22,22^FDBATCH NO.^FS

// KOD PARTII (AH30GA) - Bardzo wyraźny
^FO120,260^A0N,55,55^FD{d['batch']}^FS
^FO122,260^A0N,55,55^FD{d['batch']}^FS

// PRAWA STRONA
// EAN-13 - Przesunięty bardziej w prawo i do góry
^FO580,40^BEN,100,Y,N^FD{d['ean']}^FS

// Daty - Wyrównane do prawej krawędzi bloku dat
// Etykiety dat
^FO500,200^A0N,24,24^FDBEST BEFORE^FS
^FO400,240^A0N,24,24^FDDATE OF PRODUCTION^FS

// Wartości dat (pogrubione)
^FO730,200^A0N,28,28^FD{d['date_bb']}^FS
^FO731,200^A0N,28,28^FD{d['date_bb']}^FS

^FO730,240^A0N,28,28^FD{d['date_prod']}^FS
^FO731,240^A0N,28,28^FD{d['date_prod']}^FS

// DOLNE KODY KRESKOWE (GS1-128)
// Zagęszczone (BY2)
^BY2,3,80

// KOD 1
^FO80,310^BCN,80,N,N,N^FD{gs1_top_raw}^FS
^FO100,400^A0N,24,24^FD{d['gs1_top']}^FS

// KOD 2
^FO80,440^BCN,80,N,N,N^FD{gs1_bot_raw}^FS
^FO130,530^A0N,24,24^FD{d['gs1_bot']}^FS

^XZ"""
        return zpl

    def update_preview(self):
        zpl = self.get_zpl_code()
        # API Labelary
        url = "http://api.labelary.com/v1/printers/8dpmm/labels/120x90/0/"
        
        try:
            # Dodajemy nagłówek, żeby API wiedziało że chcemy obrazek
            files = {'file': zpl}
            response = requests.post(url, data=zpl) 
            
            if response.status_code == 200:
                image_data = response.content
                image = Image.open(io.BytesIO(image_data))
                # Skalowanie do okna
                image.thumbnail((800, 600))
                self.tk_image = ImageTk.PhotoImage(image)
                self.preview_label.config(image=self.tk_image, text="")
            else:
                self.preview_label.config(text=f"Błąd API: {response.status_code}", image="")
        except Exception as e:
            self.preview_label.config(text=f"Błąd połączenia: {e}", image="")

    def save_zpl(self):
        zpl = self.get_zpl_code()
        filename = f"etykieta_{self.entries['batch'].get()}.zpl"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(zpl)
        messagebox.showinfo("Zapisano", f"Plik gotowy: {filename}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LavazzaLabelApp(root)
    root.mainloop()
