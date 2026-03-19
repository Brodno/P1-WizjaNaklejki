import os

def generate_lavazza_label():
    # --- KONFIGURACJA DANYCH (Tutaj edytuj treść) ---
    
    # 1. Dane boczne (pionowe)
    company_text = "Luigi Lavazza S.p.A. - Via Bologna, 32 - 10152 Torino - Italia."
    product_desc = "FARD. 20 PC. QUALITA' ROSSA INT 1 250 M GROUND COFFEE"
    
    # 2. Główny blok (lewa góra)
    big_number = "03598"
    packs_text = "20 PACKS"
    weight_text = "OF e 250 g"
    batch_label = "BATCH NO."
    batch_value = "AH30GA"
    
    # 3. Prawa góra (EAN i daty)
    ean_number = "8000070135987" # Musi mieć 13 cyfr (lub 12 + cyfra kontrolna liczona automatycznie)
    
    best_before_label = "BEST BEFORE"
    best_before_date = "30/06/2027"
    
    prod_date_label = "DATE OF PRODUCTION"
    prod_date_value = "30/07/2025 19:05"
    
    # 4. Kody kreskowe GS1-128 (Dolne)
    # ZPL używa formatu >8 dla FNC1. 
    # Uwaga: Nawiasy () w kodzie kreskowym nie są kodowane, są tylko w opisie tekstowym.
    # Wartości w kodzie ZPL muszą być "czyste", poprzedzone >8 (FNC1) tam gdzie trzeba.
    
    # KOD 1 (Górny z dolnych)
    # (91)0359811302 (11)250730 (93)190509
    # Strukturę GS1 trzeba złożyć ostrożnie. >8 na początku to start GS1-128.
    # >8 przed każdym AI (zależnie od specyfikacji, zwykle FNC1 jest separatorem dla pól o zmiennej długości)
    # 91 (Internal) - zmienna długość? Zakładamy że tu kończy się na stałej.
    # Dla uproszczenia w tym generatorze używamy Code 128 Mode C/B (automatyczny w ZPL ^BC)
    # Sekwencja ZPL dla GS1 to często: >8 (FNC1) AI Dane >8 AI Dane...
    
    # Human readable text pod kodem
    gs1_top_text = "(91)0359811302(11)250730(93)190509"
    # Dane do zakodowania: >8910359811302>811250730>893190509
    gs1_top_data = ">8910359811302>811250730>893190509"
    
    # KOD 2 (Dolny)
    # (01)08000070135987 (15)270630 (10)AH30GA
    gs1_bottom_text = "(01)08000070135987(15)270630(10)AH30GA"
    gs1_bottom_data = ">80108000070135987>815270630>810AH30GA"

    # --- KONIEC KONFIGURACJI ---

    # Wymiary: 120mm x 90mm
    # Przy 203 DPI: 1 mm = 8 dots.
    # Width = 960 dots, Height = 720 dots.
    
    zpl = f"""
^XA
^PW960
^LL720
^UTF8

// --- PIONOWE TEKSTY Z LEWEJ ---
// ^A0R - czcionka obrócona o 90 stopni (R - Rotated)
// Współrzędne X,Y to punkt początkowy.
^FO20,50^A0R,24,24^FD{company_text}^FS
^FO50,50^A0R,24,24^FD{product_desc}^FS

// --- GŁÓWNY BLOK LEWY ---
// Duży numer 03598
^FO130,50^A0N,90,80^FD{big_number}^FS

// 20 PACKS
^FO130,140^A0N,30,30^FD{packs_text}^FS

// OF e 250 g
^FO130,180^A0N,30,30^FD{weight_text}^FS

// BATCH NO.
^FO130,225^A0N,20,20^FD{batch_label}^FS

// AH30GA (Numer partii - pogrubiony/duży)
^FO130,250^A0N,50,50^FD{batch_value}^FS

// --- PRAWA STRONA (EAN + DATY) ---

// Kod EAN-13
// ^BEN, wysokość, drukuj cyfry(Y), nad kodem(N)
^FO550,50^BEN,100,Y,N
^FD{ean_number}^FS

// Daty pod kodem EAN
^FO520,200^A0N,25,25^FD{best_before_label}^FS
// Data pogrubiona (można symulować przez lekkie przesunięcie i nadruk lub inną czcionkę, tu standard)
^FO720,200^A0N,25,25^FD{best_before_date}^FS

^FO450,235^A0N,25,25^FD{prod_date_label}^FS
^FO720,235^A0N,25,25^FD{prod_date_value}^FS


// --- DOLNE KODY KRESKOWE (GS1-128) ---
// ^BC - Code 128
// Parametry: orientacja, wysokość, drukuj tekst(N - bo drukujemy własny), ...
// Używamy ^FD>8...^FS aby włączyć tryb GS1 (FNC1)

// KOD 1 (Górny)
^FO110,300^BCN,80,N,N,N
^FD{gs1_top_data}^FS
// Tekst pod kodem 1 (wyśrodkowany 'na oko' lub dopasowany)
^FO110,390^A0N,25,25^FD{gs1_top_text}^FS

// KOD 2 (Dolny)
^FO110,430^BCN,80,N,N,N
^FD{gs1_bottom_data}^FS
// Tekst pod kodem 2
^FO110,520^A0N,25,25^FD{gs1_bottom_text}^FS

^XZ
"""
    return zpl

if __name__ == "__main__":
    zpl_code = generate_lavazza_label()
    
    filename = "etykieta_lavazza.zpl"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(zpl_code)
        
    print(f"Wygenerowano plik: {filepath}")
    print("Otwórz plik w notatniku, skopiuj treść i wklej na http://labelary.com/viewer.html")
    print("Ustaw na stronie Labelary rozmiar etykiety na: 4x3 cale (lub custom 120x90mm) aby zobaczyć poprawny podgląd.")

