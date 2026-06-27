#!/usr/bin/env python3
"""
fetch_10elotto.py - usa estrazioni10elotto.it che ha struttura HTML pulita
"""

import json, re, sys
from datetime import date, datetime
import urllib.request, urllib.parse

SCRAPE_DO_TOKEN = "a7c707c84d8345ef9c381ef4aecf5e59a3a24261872"
TARGET_URL      = "https://estrazioni10elotto.it/"
OUTPUT_FILE     = "ultima_estrazione.json"

MESI_IT  = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
             "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
GIORNI_IT = {0:"Lunedì",1:"Martedì",2:"Mercoledì",3:"Giovedì",4:"Venerdì",5:"Sabato",6:"Domenica"}

def fetch_html():
    encoded = urllib.parse.quote(TARGET_URL, safe="")
    url = f"https://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={encoded}&render=false"
    print(f"Chiamo scrape.do → {TARGET_URL}")
    req = urllib.request.Request(url, headers={"User-Agent": "TeneLotto/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
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
    # Cerca il primo blocco "Concorso n° NNN/AAAA"
    m = re.search(
        r"Concorso\s+n[°º.]\s*(\d+)/(\d{4})(.*?)(?=Concorso\s+n[°º.]|\Z)",
        html, re.DOTALL | re.IGNORECASE
    )
    if not m:
        raise Exception("Blocco concorso non trovato")

    num_concorso = int(m.group(1))
    anno = int(m.group(2))
    testo = strip_tags(m.group(3))
    print(f"Concorso n° {num_concorso}/{anno}")
    print(f"Testo: {testo[:400]}")

    # Data
    data_obj = None
    m_d = re.search(r"(\d{2})/(\d{2})/(\d{4})", testo)
    if m_d:
        try: data_obj = date(int(m_d.group(3)), int(m_d.group(2)), int(m_d.group(1)))
        except: pass
    if not data_obj:
        m_d2 = re.search(r"(\d{1,2})\s+(" + "|".join(MESI_IT.keys()) + r")\s+(\d{4})", testo, re.IGNORECASE)
        if m_d2:
            try: data_obj = date(int(m_d2.group(3)), MESI_IT[m_d2.group(2).lower()], int(m_d2.group(1)))
            except: pass
    if not data_obj:
        data_obj = date.today()
        print("⚠️  Data non trovata, uso oggi")

    g = GIORNI_IT[data_obj.weekday()]
    mese = list(MESI_IT.keys())[data_obj.month - 1]
    data_leggibile = f"{g} {data_obj.day} {mese} {data_obj.year}"
    print(f"Data: {data_leggibile}")

    # Separa sezione Extra
    testo_extra = ""
    m_ex = re.search(r"Extra\s*[·:\-]\s*(.*?)(?=Segui|Numero\s+pi|I\s+numeri\s+pi|$)", testo, re.DOTALL | re.IGNORECASE)
    if m_ex:
        testo_extra = m_ex.group(1)
        testo = testo[:m_ex.start()]

    # Numero Oro e Doppio Oro
    numero_oro = None
    doppio_oro = None
    m_oro = re.search(r"Numero\s+Oro\s*[·:\-]\s*(\d{1,2})", testo, re.IGNORECASE)
    if m_oro:
        numero_oro = int(m_oro.group(1))
    m_dop = re.search(r"Doppio\s+Oro\s*[·:\-]\s*(\d{1,2})", testo, re.IGNORECASE)
    if m_dop:
        doppio_oro = int(m_dop.group(1))

    # 20 numeri: rimuovi sezioni Oro/Doppio Oro prima di cercare
    testo_n = re.sub(r"(?:Numero\s+Oro|Doppio\s+Oro).*", "", testo, flags=re.IGNORECASE | re.DOTALL)
    numeri = estrai_numeri(testo_n, 20)
    print(f"Numeri ({len(numeri)}): {numeri}")

    if len(numeri) < 20:
        raise Exception(f"Trovati solo {len(numeri)} numeri su 20")

    if numero_oro is None: numero_oro = numeri[0]
    if doppio_oro is None: doppio_oro = numeri[1]

    extra = []
    if testo_extra:
        extra = [n for n in estrai_numeri(testo_extra, 15) if n not in numeri][:15]
    print(f"Numero Oro: {numero_oro} | Doppio Oro: {doppio_oro} | Extra ({len(extra)}): {extra}")

    return {
        "data":          data_obj.isoformat(),
        "data_testo":    data_leggibile,
        "concorso":      num_concorso,
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
        with open("debug_html.txt", "w") as f:
            f.write(html[:8000])
        print("Salvato debug_html.txt")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {OUTPUT_FILE} aggiornato — Concorso n° {dati['concorso']} del {dati['data_testo']}")

if __name__ == "__main__":
    main()
