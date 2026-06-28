#!/usr/bin/env python3
"""
fetch_10elotto.py
- Scarica l'ultima estrazione da estrazioni10elotto.it via scrape.do
- Retry automatico se i dati non sono ancora aggiornati
- Aggiorna ultima_estrazione.json
- Aggiunge la nuova riga in cima a storico_10elotto_serale.csv
"""

import json, re, sys, time, os
from datetime import date, datetime
import urllib.request, urllib.parse

import os
SCRAPE_DO_TOKEN = os.environ.get("SCRAPE_DO_TOKEN", "")
TARGET_URL      = "https://estrazioni10elotto.it/"
OUTPUT_JSON     = "ultima_estrazione.json"
OUTPUT_CSV      = "storico_10elotto_serale.csv"
MAX_RETRY       = 3        # tentativi massimi
RETRY_WAIT      = 300      # secondi tra un tentativo e l'altro (5 minuti)

MESI_IT = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
            "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
GIORNI_IT = {0:"Lunedì",1:"Martedì",2:"Mercoledì",3:"Giovedì",
             4:"Venerdì",5:"Sabato",6:"Domenica"}

# ─── Fetch ───────────────────────────────────────────────────────────────────

def fetch_html():
    encoded = urllib.parse.quote(TARGET_URL, safe="")
    url = f"https://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={encoded}&render=true"
    print(f"  → scrape.do chiamata a {TARGET_URL}")
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

# ─── Parse ───────────────────────────────────────────────────────────────────

def parse(html):
    testo = strip_tags(html)

    m_inizio = re.search(r"Estrazione\s+10eLotto\s+di\s+", testo, re.IGNORECASE)
    if not m_inizio:
        raise Exception("Intestazione estrazione non trovata")

    resto = testo[m_inizio.start():]
    m_fine = re.search(r"Estrazione\s+10eLotto\s+di\s+", resto[10:], re.IGNORECASE)
    blocco = resto[:m_fine.start() + 10] if m_fine else resto

    # Data
    m_data = re.search(
        r"(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+"
        r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
        r"agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
        blocco, re.IGNORECASE
    )
    if not m_data:
        raise Exception("Data non trovata nel blocco")

    giorno_n    = int(m_data.group(2))
    mese_str    = m_data.group(3).lower()
    mese_n      = MESI_IT[mese_str]
    anno_n      = int(m_data.group(4))
    data_obj    = date(anno_n, mese_n, giorno_n)
    giorno_nome = GIORNI_IT[data_obj.weekday()]
    data_leggibile = f"{giorno_nome} {giorno_n} {mese_str} {anno_n}"

    # Concorso
    m_conc = re.search(r"Concorso\s+n[°º.]\s*(\d+)/(\d{4})", blocco, re.IGNORECASE)
    concorso = int(m_conc.group(1)) if m_conc else 0

    # Parte numerica: inizia DOPO "Concorso n° NNN/AAAA"
    testo_dopo = blocco[m_conc.end():] if m_conc else blocco[m_data.end():]

    # Separa Extra
    testo_extra = ""
    m_ex = re.search(r"Extra\s+([\d\s]+?)(?:Segui|Numeri\s+ritard|$)",
                     testo_dopo, re.IGNORECASE | re.DOTALL)
    if m_ex:
        testo_extra  = m_ex.group(1)
        testo_numeri = testo_dopo[:m_ex.start()]
    else:
        testo_numeri = testo_dopo

    # Numero Oro / Doppio Oro
    numero_oro = None
    doppio_oro = None
    m_oro = re.search(r"Numero\s+Oro\s+(\d{1,2})", testo_numeri, re.IGNORECASE)
    if m_oro: numero_oro = int(m_oro.group(1))
    m_dop = re.search(r"Doppio\s+Oro\s+(\d{1,2})", testo_numeri, re.IGNORECASE)
    if m_dop: doppio_oro = int(m_dop.group(1))

    # 20 numeri (testo fino a "Numero Oro")
    testo_solo_20 = re.sub(r"(?:Numero\s+Oro|Doppio\s+Oro).*", "",
                           testo_numeri, flags=re.IGNORECASE | re.DOTALL)
    numeri = estrai_numeri(testo_solo_20, 20)

    if len(numeri) < 20:
        raise Exception(f"Trovati solo {len(numeri)} numeri su 20")

    if numero_oro is None: numero_oro = numeri[0]
    if doppio_oro is None: doppio_oro = numeri[1]

    extra = []
    if testo_extra:
        extra = [n for n in estrai_numeri(testo_extra, 15) if n not in numeri][:15]

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

# ─── CSV ─────────────────────────────────────────────────────────────────────

def data_ultima_nel_csv() -> date | None:
    """Legge la data della prima riga dati del CSV (= estrazione più recente)."""
    if not os.path.exists(OUTPUT_CSV):
        return None
    try:
        with open(OUTPUT_CSV, encoding="utf-8") as f:
            f.readline()  # salta header
            prima_riga = f.readline().strip()
        if not prima_riga:
            return None
        # Formato: "Venerdì 26 giugno 2026;..."
        parti_data = prima_riga.split(";")[0].strip().split()
        # parti_data = ["Venerdì", "26", "giugno", "2026"]
        giorno_n = int(parti_data[1])
        mese_n   = MESI_IT[parti_data[2].lower()]
        anno_n   = int(parti_data[3])
        return date(anno_n, mese_n, giorno_n)
    except Exception as e:
        print(f"  ⚠️  Errore lettura CSV: {e}")
        return None

def aggiungi_riga_csv(dati: dict):
    """Aggiunge la nuova estrazione in CIMA al CSV (dopo l'header)."""
    data_testo  = dati["data_testo"]           # "Venerdì 26 giugno 2026"
    numeri_str  = " ".join(str(n) for n in dati["numeri"])
    oro         = dati["numero_oro"]
    doppio      = dati["doppio_oro"]
    extra_str   = " ".join(str(n) for n in dati["extra"])
    nuova_riga  = f"{data_testo};{numeri_str};{oro};{doppio};{extra_str}\r\n"

    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, encoding="utf-8") as f:
            contenuto = f.read()
        # Inserisce dopo l'header
        lines = contenuto.splitlines(keepends=True)
        header = lines[0]
        resto  = "".join(lines[1:])
        nuovo  = header + nuova_riga + resto
    else:
        # CSV non esiste: crea con header
        header  = "Date;Numbers;Gold;DoubleGold;Extra\r\n"
        nuovo   = header + nuova_riga

    with open(OUTPUT_CSV, "w", encoding="utf-8") as f:
        f.write(nuovo)
    print(f"  ✅ CSV aggiornato: aggiunta riga '{data_testo}'")

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    oggi = date.today()
    print(f"=== Fetch 10eLotto Serale - {oggi} ===\n")

    # Controlla se il CSV è già aggiornato a oggi
    # (evita doppi aggiornamenti in caso di re-run manuale)
    data_csv = data_ultima_nel_csv()
    if data_csv and data_csv >= oggi:
        print(f"✅ CSV già aggiornato a {data_csv} — nessuna chiamata necessaria")
        sys.exit(0)

    dati = None
    for tentativo in range(1, MAX_RETRY + 1):
        print(f"--- Tentativo {tentativo}/{MAX_RETRY} ---")
        try:
            html  = fetch_html()
            dati  = parse(html)
            print(f"  Data trovata: {dati['data_testo']} ({dati['data']})")

            # Controlla se il sito è già aggiornato con l'estrazione di oggi
            if dati["data"] < oggi.isoformat():
                print(f"  ⚠️  Il sito riporta ancora {dati['data']} (atteso {oggi})")
                if tentativo < MAX_RETRY:
                    print(f"  ⏳ Attendo {RETRY_WAIT // 60} minuti prima di riprovare...")
                    time.sleep(RETRY_WAIT)
                    continue
                else:
                    print("  ⚠️  Esauriti i tentativi — salvo comunque i dati disponibili")
            else:
                print(f"  ✅ Dati aggiornati a oggi!")
            break

        except Exception as e:
            print(f"  ❌ Errore: {e}")
            if tentativo < MAX_RETRY:
                print(f"  ⏳ Riprovo tra {RETRY_WAIT // 60} minuti...")
                time.sleep(RETRY_WAIT)
            else:
                print("  ❌ Tutti i tentativi falliti")
                sys.exit(1)

    if dati is None:
        print("❌ Nessun dato ottenuto")
        sys.exit(1)

    # Salva JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {OUTPUT_JSON} aggiornato")

    # Aggiorna CSV solo se la data è nuova rispetto all'ultima nel file
    if data_csv is None or dati["data"] > data_csv.isoformat():
        aggiungi_riga_csv(dati)
    else:
        print(f"  CSV già contiene {dati['data']} — nessuna riga aggiunta")

    print(f"\n=== Risultato ===")
    print(f"  Concorso   : n° {dati['concorso']}")
    print(f"  Data       : {dati['data_testo']}")
    print(f"  Numeri     : {dati['numeri']}")
    print(f"  Numero Oro : {dati['numero_oro']}")
    print(f"  Doppio Oro : {dati['doppio_oro']}")
    print(f"  Extra      : {dati['extra']}")

if __name__ == "__main__":
    main()
