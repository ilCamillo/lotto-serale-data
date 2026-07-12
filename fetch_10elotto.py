#!/usr/bin/env python3
"""
fetch_10elotto.py
- Controlla la data nel JSON locale (già committato nel repo)
- Se già aggiornato all'ultima estrazione attesa: esce senza chiamare scrape.do
- Se non aggiornato: scrapa estrazioni10elotto.it via scrape.do
- Retry automatico se il sito non è ancora aggiornato
"""

import json, re, sys, time, os, urllib.request, urllib.parse
from datetime import date, datetime, timezone, timedelta

SCRAPE_DO_TOKEN = os.environ.get("SCRAPE_DO_TOKEN", "")
TARGET_URL      = "https://estrazioni10elotto.it/"
OUTPUT_JSON     = "ultima_estrazione.json"
OUTPUT_CSV      = "storico_10elotto_serale.csv"
# Nessun retry interno: 1 sola chiamata per run.
# Se il sito non è aggiornato, la run esce senza salvare nulla.
# La run successiva (schedulata 20 min dopo) riproverà.

MESI_IT = {
    "gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
    "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12
}
GIORNI_IT = {
    0:"Lunedì",1:"Martedì",2:"Mercoledì",3:"Giovedì",
    4:"Venerdì",5:"Sabato",6:"Domenica"
}
# Giorni di estrazione: lunedì=0, martedì=1, giovedì=3, venerdì=4, sabato=5
GIORNI_ESTRAZIONE = {1, 3, 4, 5}
ORA_ESTRAZIONE    = 20  # le 20:00

# ─── Calcolo ora italiana ─────────────────────────────────────────────────────

def ora_italiana() -> datetime:
    """Restituisce il datetime corrente in ora italiana (gestisce ora legale)."""
    utc_now = datetime.now(timezone.utc)
    # Ora legale italiana (CEST): ultima domenica di marzo → ultima domenica di ottobre
    anno = utc_now.year
    # Calcola ultima domenica di marzo
    import calendar
    def ultima_domenica(anno, mese):
        ultimo_giorno = calendar.monthrange(anno, mese)[1]
        for g in range(ultimo_giorno, 0, -1):
            if datetime(anno, mese, g).weekday() == 6:
                return datetime(anno, mese, g, 1, 0, 0, tzinfo=timezone.utc)
        return None

    inizio_legale = ultima_domenica(anno, 3)   # ultima domenica marzo
    fine_legale   = ultima_domenica(anno, 10)  # ultima domenica ottobre

    if inizio_legale and fine_legale and inizio_legale <= utc_now < fine_legale:
        offset = timedelta(hours=2)  # CEST (ora legale)
    else:
        offset = timedelta(hours=1)  # CET (ora solare)

    return (utc_now + offset).replace(tzinfo=None)

def ultima_estrazione_attesa() -> date:
    """
    Calcola la data dell'ultima estrazione che dovrebbe già essere avvenuta
    usando l'ora italiana corretta (con ora legale).
    """
    now_it = ora_italiana()
    print(f"  Ora italiana corrente: {now_it.strftime('%Y-%m-%d %H:%M')}")

    for i in range(7):
        candidato = now_it - timedelta(days=i)
        if candidato.weekday() in GIORNI_ESTRAZIONE:
            # Se è oggi ma prima delle 20:05, salta a ieri
            if i == 0 and candidato.hour < ORA_ESTRAZIONE:
                continue
            return candidato.date()
    return now_it.date()

# ─── Lettura JSON locale ──────────────────────────────────────────────────────

def data_nel_json() -> date | None:
    if not os.path.exists(OUTPUT_JSON):
        return None
    try:
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            d = json.load(f)
        return date.fromisoformat(d["data"])
    except Exception:
        return None

# ─── Fetch HTML via scrape.do ────────────────────────────────────────────────

def fetch_html() -> str:
    if not SCRAPE_DO_TOKEN:
        raise Exception("SCRAPE_DO_TOKEN mancante nei GitHub Secrets")
    encoded = urllib.parse.quote(TARGET_URL, safe="")
    url = f"https://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={encoded}&render=true"
    print(f"  → scrape.do: {TARGET_URL}")
    req = urllib.request.Request(url, headers={"User-Agent": "TeneLotto/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise Exception(f"HTTP {r.status}")
        return r.read().decode("utf-8", errors="replace")

# ─── Parsing HTML ─────────────────────────────────────────────────────────────

def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)

def estrai_numeri(testo: str, quanti: int) -> list:
    res = []
    for m in re.finditer(r"\b(\d{1,2})\b", testo):
        n = int(m.group(1))
        if 1 <= n <= 90 and n not in res:
            res.append(n)
        if len(res) == quanti:
            break
    return res

def parse(html: str) -> dict:
    testo = strip_tags(html)

    m_inizio = re.search(r"Estrazione\s+10eLotto\s+di\s+", testo, re.IGNORECASE)
    if not m_inizio:
        raise Exception("Intestazione estrazione non trovata")

    resto  = testo[m_inizio.start():]
    m_fine = re.search(r"Estrazione\s+10eLotto\s+di\s+", resto[10:], re.IGNORECASE)
    blocco = resto[:m_fine.start() + 10] if m_fine else resto

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
    anno_n      = int(m_data.group(4))
    data_obj    = date(anno_n, MESI_IT[mese_str], giorno_n)
    giorno_nome = GIORNI_IT[data_obj.weekday()]
    data_leggibile = f"{giorno_nome} {giorno_n} {mese_str} {anno_n}"

    m_conc   = re.search(r"Concorso\s+n[°º.]\s*(\d+)/(\d{4})", blocco, re.IGNORECASE)
    concorso = int(m_conc.group(1)) if m_conc else 0
    testo_dopo = blocco[m_conc.end():] if m_conc else blocco[m_data.end():]

    testo_extra = ""
    m_ex = re.search(r"Extra\s+([\d\s]+?)(?:Segui|Numeri\s+ritard|$)",
                     testo_dopo, re.IGNORECASE | re.DOTALL)
    if m_ex:
        testo_extra  = m_ex.group(1)
        testo_numeri = testo_dopo[:m_ex.start()]
    else:
        testo_numeri = testo_dopo

    numero_oro, doppio_oro = None, None
    m_oro = re.search(r"Numero\s+Oro\s+(\d{1,2})", testo_numeri, re.IGNORECASE)
    if m_oro: numero_oro = int(m_oro.group(1))
    m_dop = re.search(r"Doppio\s+Oro\s+(\d{1,2})", testo_numeri, re.IGNORECASE)
    if m_dop: doppio_oro = int(m_dop.group(1))

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

# ─── Aggiornamento CSV ────────────────────────────────────────────────────────

def aggiungi_riga_csv(dati: dict):
    numeri_str = " ".join(str(n) for n in dati["numeri"])
    extra_str  = " ".join(str(n) for n in dati["extra"])
    nuova_riga = (f"{dati['data_testo']};{numeri_str};"
                  f"{dati['numero_oro']};{dati['doppio_oro']};{extra_str}\r\n")

    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, encoding="utf-8") as f:
            contenuto = f.read()
        lines  = contenuto.splitlines(keepends=True)
        header = lines[0]
        resto  = "".join(lines[1:])
        nuovo  = header + nuova_riga + resto
    else:
        nuovo = f"Date;Numbers;Gold;DoubleGold;Extra\r\n{nuova_riga}"

    with open(OUTPUT_CSV, "w", encoding="utf-8") as f:
        f.write(nuovo)
    print(f"  ✅ CSV aggiornato con '{dati['data_testo']}'")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== Fetch 10eLotto — {now_utc} ===")

    attesa = ultima_estrazione_attesa()
    print(f"Ultima estrazione attesa : {attesa}")

    # Controlla se il JSON è già aggiornato → esce senza chiamare scrape.do
    data_json = data_nel_json()
    print(f"Data nel JSON attuale    : {data_json}")

    if data_json and data_json >= attesa:
        print(f"✅ JSON già aggiornato a {data_json} — nessuna chiamata a scrape.do")
        sys.exit(0)

    print(f"⚠️  Aggiornamento necessario — 1 chiamata a scrape.do...")

    # UNA SOLA chiamata per run — nessun retry interno
    # Se il sito non è ancora aggiornato, esce senza salvare nulla
    # La prossima run schedulata (tra 20 min) riproverà automaticamente
    try:
        html = fetch_html()
        dati = parse(html)
        data_sito = date.fromisoformat(dati["data"])
        print(f"  Data trovata sul sito: {dati['data_testo']}")

        if data_sito < attesa:
            print(f"  ⚠️  Sito fermo a {dati['data']} (attesa {attesa})")
            print(f"  ⏭️  Nessun salvataggio — la prossima run riproverà tra 20 min")
            sys.exit(0)

        print(f"  ✅ Sito aggiornato!")

    except Exception as e:
        print(f"  ❌ Errore scraping: {e}")
        sys.exit(1)

    # Salva JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {OUTPUT_JSON} aggiornato")

    # Aggiorna CSV solo se la data è nuova
    if data_json is None or dati["data"] > data_json.isoformat():
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
