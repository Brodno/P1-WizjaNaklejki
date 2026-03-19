import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import pandas as pd
import pyautogui
import time
import os
from datetime import datetime

# --- KONFIGURACJA ---
PUNKT_HHMMSS = (2453, 496)
PUNKT_HH_MM = (2404, 527)
PUNKT_DRUKUJ = (2181, 95)
DB_PATH = 'aop_production.db'

class AOPDashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📦 AOP Label Master - Pro Dashboard (Native)")
        self.root.geometry("1000x700")
        self.root.configure(bg="#2c3e50")
        
        self.create_widgets()
        self.refresh_data()

    def create_widgets(self):
        # Header
        header = tk.Label(self.root, text="AOP VISION & RPA DASHBOARD", font=("Arial", 24, "bold"), bg="#34495e", fg="white", pady=10)
        header.pack(fill=tk.X)

        # Statystyki
        stats_frame = tk.Frame(self.root, bg="#2c3e50", pady=20)
        stats_frame.pack()
        
        self.lbl_done = tk.Label(stats_frame, text="Wydrukowano: 0", font=("Arial", 16), bg="#27ae60", fg="white", padx=20, pady=10)
        self.lbl_done.pack(side=tk.LEFT, padx=10)
        
        self.lbl_pending = tk.Label(stats_frame, text="Oczekuje: 0", font=("Arial", 16), bg="#f39c12", fg="black", padx=20, pady=10)
        self.lbl_pending.pack(side=tk.LEFT, padx=10)

        # Sterowanie
        btn_frame = tk.Frame(self.root, bg="#2c3e50", pady=20)
        btn_frame.pack()
        
        tk.Button(btn_frame, text="🚀 WYDRUKUJ NASTĘPNY (KROKOWO)", font=("Arial", 14, "bold"), bg="#3498db", fg="white", padx=20, pady=15, command=self.print_next).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🔄 ODŚWIEŻ LISTĘ", font=("Arial", 12), bg="#95a5a6", command=self.refresh_data).pack(side=tk.LEFT, padx=5)

        # Tabela (Treeview)
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 10), rowheight=25)
        
        table_frame = tk.Frame(self.root)
        table_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        self.tree = ttk.Treeview(table_frame, columns=("ID", "Batch", "OCR Time", "Print Time", "Status"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Batch", text="Partia (Batch)")
        self.tree.heading("OCR Time", text="Czas z paczki")
        self.tree.heading("Print Time", text="Czas do druku")
        self.tree.heading("Status", text="Status")
        
        self.tree.column("ID", width=50)
        self.tree.column("Status", width=100)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_data(self):
        if not os.path.exists(DB_PATH): return
        
        # Czyścimy tabelę
        for item in self.tree.get_children(): self.tree.delete(item)
        
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT id, batch_id, ocr_hhmm, calculated_hhmmss, status FROM jobs ORDER BY id DESC", conn)
        
        done_count = len(df[df['status'] == 'DONE'])
        pending_count = len(df[df['status'] == 'PENDING'])
        
        self.lbl_done.config(text=f"Wydrukowano: {done_count}")
        self.lbl_pending.config(text=f"Oczekuje: {pending_count}")
        
        for _, row in df.iterrows():
            self.tree.insert("", tk.END, values=(row['id'], row['batch_id'], row['ocr_hhmm'], row['calculated_hhmmss'], row['status']))
        
        conn.close()
        # Auto-odświeżanie co 3 sekundy
        self.root.after(3000, self.refresh_data)

    def print_next(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, calculated_hhmmss, ocr_hhmm FROM jobs WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1")
        job = cursor.fetchone()
        
        if job:
            job_id, hhmmss, hhmm = job
            self.root.iconify() # Minimalizuj panel żeby nie zasłaniał
            time.sleep(0.5)
            
            try:
                # RPA AKCJA
                pyautogui.click(PUNKT_HHMMSS)
                time.sleep(0.1); pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
                pyautogui.typewrite(str(hhmmss))
                
                pyautogui.click(PUNKT_HH_MM)
                time.sleep(0.1); pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
                pyautogui.typewrite(str(hhmm))
                
                pyautogui.click(PUNKT_DRUKUJ)
                
                cursor.execute("UPDATE jobs SET status = 'DONE' WHERE id = ?", (job_id,))
                conn.commit()
                messagebox.showinfo("Sukces", f"Zadanie {job_id} wydrukowane!")
            except Exception as e:
                messagebox.showerror("Błąd", f"RPA ERROR: {e}")
            finally:
                self.root.deiconify() # Przywróć panel
        else:
            messagebox.showinfo("Koniec", "Brak zadań w kolejce!")
        
        conn.close()
        self.refresh_data()

if __name__ == "__main__":
    root = tk.Tk()
    app = AOPDashboardApp(root)
    root.mainloop()
