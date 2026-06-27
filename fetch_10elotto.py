#!/usr/bin/env python3
"""
fetch_10elotto.py - versione corretta
"""

import json, re, sys
from datetime import date, datetime
import urllib.request, urllib.parse

SCRAPE_DO_TOKEN = "a7c707c84d8345ef9c381ef4aecf5e59a3a24261872"
TARGET_URL      = "https://estrazioni10elotto.it/"
OUTPUT_FILE     = "ultima_estrazione.json"

MESI_IT = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
            "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
GIORNI_IT = {0:"Lunedì",1:"Martedì",2:"Mercoledì",3:"Giovedì",
             4:"Venerdì",5:"Sabato",6:"Domenica"}

def fetch_html():
    encoded = urllib.parse.quote(TARGET_URL, safe="")
    url = f"https://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={encoded}&render=true"
    print(f"Chiamo scrape.do → {TARGET_URL}")
    req = urllib.request.Request(url, headers={"User-Agent": "TeneLotto/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise Exception(f"HTTP {r.status}")
        return r.read().decode("utf-8", errors="replace")

def strip_tags(html):
    return re.sub(r"<[^>]+>", " ", html)

def estrai_numeri(testo, quanti):
    res = []
    for m in re.finditer(r"\b(\d{1,2})\b", testo):
        n = int(m.group(1))
        if 1 <= n <= 90 and n not in res:
            res.append(n)
        if len(res) == quanti:
            break
    return res

def parse(html):
    testo = strip_tags(html)

    # Trova il primo blocco estrazione
    m_inizio = re.search(r"Estrazione\s+10eLotto\s+di\s+", testo, re.IGNORECASE)
    if not m_inizio:
        raise Exception("Intestazione estrazione non trovata")

    resto = testo[m_inizio.start():]
    m_fine = re.search(r"Estrazione\s+10eLotto\s+di\s+", resto[10:], re.IGNORECASE)
    blocco = resto[:m_fine.start() + 10] if m_fine else resto
    print(f"Blocco: {blocco[:300]}")

    # --- Data: "Venerdì 26 Giugno 2026" ---
    m_data = re.search(
        r"(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+"
        r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
        r"agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
        blocco, re.IGNORECASE
    )
    if not m_data:
        raise Exception("Data non trovata nel blocco")

    giorno_n   = int(m_data.group(2))
    mese_str   = m_data.group(3).lower()
    mese_n     = MESI_IT[mese_str]
    anno_n     = int(m_data.group(4))
    data_obj   = date(anno_n, mese_n, giorno_n)
    giorno_nome = GIORNI_IT[data_obj.weekday()]
    data_leggibile = f"{giorno_nome} {giorno_n} {mese_str} {anno_n}"
    print(f"Data: {data_leggibile}")

    # --- Numero concorso ---
    m_conc = re.search(r"Concorso\s+n[°º.]\s*(\d+)/(\d{4})", blocco, re.IGNORECASE)
    concorso = int(m_conc.group(1)) if m_conc else 0
    print(f"Concorso n° {concorso}")

    # --- Isola la sezione numeri: da DOPO "Concorso n° NNN/AAAA" ---
    # In questo modo evitiamo di prendere il giorno, mese e anno della data
    # e il numero del concorso stesso
    if m_conc:
        testo_dopo_concorso = blocco[m_conc.end():]
    else:
        testo_dopo_concorso = blocco[m_data.end():]

    # --- Separa Extra ---
    testo_extra = ""
    m_ex = re.search(r"Extra\s+([\d\s]+?)(?:Segui|Numeri\s+ritard|$)",
                     testo_dopo_concorso, re.IGNORECASE | re.DOTALL)
    if m_ex:
        testo_extra = m_ex.group(1)
        testo_numeri = testo_dopo_concorso[:m_ex.start()]
    else:
        testo_numeri = testo_dopo_concorso

    # --- Numero Oro e Doppio Oro ---
    numero_oro = None
    doppio_oro = None
    m_oro = re.search(r"Numero\s+Oro\s+(\d{1,2})", testo_numeri, re.IGNORECASE)
    if m_oro:
        numero_oro = int(m_oro.group(1))
    m_dop = re.search(r"Doppio\s+Oro\s+(\d{1,2})", testo_numeri, re.IGNORECASE)
    if m_dop:
        doppio_oro = int(m_dop.group(1))

    # --- 20 numeri: testo da dopo il concorso fino a "Numero Oro" ---
    testo_solo_20 = re.sub(
        r"(?:Numero\s+Oro|Doppio\s+Oro).*", "",
        testo_numeri, flags=re.IGNORECASE | re.DOTALL
    )
    numeri = estrai_numeri(testo_solo_20, 20)
    print(f"Numeri ({len(numeri)}): {numeri}")

    if len(numeri) < 20:
        raise Exception(f"Trovati solo {len(numeri)} numeri su 20. Testo: {testo_solo_20[:200]}")

    if numero_oro is None: numero_oro = numeri[0]
    if doppio_oro is None: doppio_oro = numeri[1]
    print(f"Numero Oro: {numero_oro} | Doppio Oro: {doppio_oro}")

    # --- Extra ---
    extra = []
    if testo_extra:
        extra = [n for n in estrai_numeri(testo_extra, 15) if n not in numeri][:15]
    print(f"Extra ({len(extra)}): {extra}")

    return {
        "data":          data_obj.isoformat(),
        "data_testo":    data_leggibile,
        "concorso":      concorso,
        "numeri":        numeri,
        "numero_oro":    numero_oro,
        "doppio_oro":    doppio_oro,
        "extra":         extra,
        "aggiornato_il": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

def main():
    print(f"=== Fetch 10eLotto - {date.today()} ===\n")
    try:
        html = fetch_html()
        print(f"HTML: {len(html)} caratteri\n")
    except Exception as e:
        print(f"❌ Fetch fallito: {e}")
        sys.exit(1)

    try:
        dati = parse(html)
    except Exception as e:
        print(f"❌ Parsing fallito: {e}")
        with open("debug_html.txt", "w", encoding="utf-8") as f:
            f.write(strip_tags(html)[:8000])
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Concorso n° {dati['concorso']} - {dati['data_testo']}")
    print(f"   Numeri     : {dati['numeri']}")
    print(f"   Numero Oro : {dati['numero_oro']}")
    print(f"   Doppio Oro : {dati['doppio_oro']}")
    print(f"   Extra      : {dati['extra']}")

if __name__ == "__main__":
    main()
