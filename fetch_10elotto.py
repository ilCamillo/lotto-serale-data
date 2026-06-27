#!/usr/bin/env python3
"""
fetch_10elotto.py
Scarica l'ultima estrazione del 10eLotto Serale da estrazionedellotto.it
tramite scrape.do e salva il risultato in ultima_estrazione.json

Viene eseguito dalla GitHub Action dopo ogni estrazione.
"""

import json
import re
import sys
from datetime import date, datetime
import urllib.request
import urllib.parse
import html

# ─── CONFIGURAZIONE ─────────────────────────────────────────────────────────
SCRAPE_DO_TOKEN = "a7c707c84d8345ef9c381ef4aecf5e59a3a24261872"
TARGET_URL      = "https://www.estrazionedellotto.it/10elotto/ultime-estrazioni-10elotto"
OUTPUT_FILE     = "ultima_estrazione.json"
# ────────────────────────────────────────────────────────────────────────────

MESI_IT = {
    "gennaio":1,"febbraio":2,"marzo":3,"aprile":4,
    "maggio":5,"giugno":6,"luglio":7,"agosto":8,
    "settembre":9,"ottobre":10,"novembre":11,"dicembre":12
}

GIORNI_IT = {
    0:"Lunedì",1:"Martedì",2:"Mercoledì",3:"Giovedì",
    4:"Venerdì",5:"Sabato",6:"Domenica"
}

def fetch_html(url: str) -> str:
    """Scarica la pagina tramite scrape.do."""
    encoded = urllib.parse.quote(url, safe="")
    api_url = f"https://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={encoded}&render=false"
    print(f"Chiamata scrape.do → {url}")
    req = urllib.request.Request(api_url, headers={"User-Agent": "TeneLotto-Action/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise Exception(f"HTTP {r.status}")
        return r.read().decode("utf-8", errors="replace")

def pulisci(testo: str) -> str:
    """Rimuove tag HTML e decodifica entità."""
    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = html.unescape(testo)
    return re.sub(r"\s+", " ", testo).strip()

def estrai_numeri(testo: str, quanti: int) -> list[int]:
    """Estrae fino a `quanti` numeri interi da 1 a 90 da una stringa."""
    trovati = []
    for m in re.finditer(r"\b(\d{1,2})\b", testo):
        n = int(m.group(1))
        if 1 <= n <= 90 and n not in trovati:
            trovati.append(n)
        if len(trovati) == quanti:
            break
    return trovati

def parse_data(testo: str) -> tuple[date | None, str]:
    """Cerca una data italiana nel testo e restituisce (date, testo_leggibile)."""
    pattern = re.compile(
        r"(\d{1,2})\s*/?\s*(gennaio|febbraio|marzo|aprile|maggio|giugno|"
        r"luglio|agosto|settembre|ottobre|novembre|dicembre)\s*/?\s*(\d{4})",
        re.IGNORECASE
    )
    m = pattern.search(testo)
    if m:
        g = int(m.group(1))
        mese_num = MESI_IT[m.group(2).lower()]
        a = int(m.group(3))
        try:
            d = date(a, mese_num, g)
            giorno_nome = GIORNI_IT[d.weekday()]
            mese_nome = m.group(2).lower()
            return d, f"{giorno_nome} {g} {mese_nome} {a}"
        except ValueError:
            pass

    # Fallback: formato DD/MM/YYYY
    m2 = re.search(r"(\d{2})/(\d{2})/(\d{4})", testo)
    if m2:
        try:
            d = date(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)))
            giorno_nome = GIORNI_IT[d.weekday()]
            mese_nome = list(MESI_IT.keys())[d.month - 1]
            return d, f"{giorno_nome} {d.day} {mese_nome} {d.year}"
        except ValueError:
            pass

    return None, ""

def parse_10elotto(html_content: str) -> dict:
    """
    Estrae i dati del 10eLotto dall'HTML.
    La pagina ha una struttura con blocchi per ogni estrazione;
    prendiamo il primo (= più recente).
    """

    # Cerca il primo blocco estrazione
    # La pagina usa tipicamente <article>, <section> o <div> con classe relativa all'estrazione
    # Proviamo a trovare il primo blocco significativo che contenga "20 numeri" o simile

    # Strategia 1: cerca tag <article> o <div class="...draw...">
    blocco = None
    for pattern in [
        r'<article[^>]*>(.*?)</article>',
        r'<section[^>]*class="[^"]*draw[^"]*"[^>]*>(.*?)</section>',
        r'<div[^>]*class="[^"]*estrazione[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*lotto[^"]*"[^>]*>(.*?)</div>',
        r'<table[^>]*>(.*?)</table>',
    ]:
        m = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if m:
            testo_blocco = pulisci(m.group(1))
            numeri = estrai_numeri(testo_blocco, 20)
            if len(numeri) >= 15:
                blocco = testo_blocco
                print(f"Blocco trovato con pattern: {pattern[:40]}...")
                break

    if blocco is None:
        # Strategia 2: prendi tutto il testo e cerca la sequenza di 20 numeri
        print("Nessun blocco specifico trovato, cerco nel testo completo...")
        blocco = pulisci(html_content)

    # Estrai data
    data_obj, data_leggibile = parse_data(blocco)
    if data_obj is None:
        data_obj = date.today()
        g = GIORNI_IT[data_obj.weekday()]
        mese = list(MESI_IT.keys())[data_obj.month - 1]
        data_leggibile = f"{g} {data_obj.day} {mese} {data_obj.year}"
        print(f"⚠️  Data non trovata nell'HTML, uso oggi: {data_leggibile}")
    else:
        print(f"✅ Data trovata: {data_leggibile}")

    # Estrai i 20 numeri vincenti
    numeri = estrai_numeri(blocco, 20)
    print(f"✅ Numeri trovati: {len(numeri)} → {numeri}")

    if len(numeri) < 20:
        raise Exception(f"Trovati solo {len(numeri)} numeri su 20 attesi")

    # Numero Oro: il primo estratto
    # Doppio Oro: il secondo
    # Cerchiamo testo "Numero Oro" / "Doppio Oro" / "Gold" / "DoubleGold"
    numero_oro  = numeri[0]
    doppio_oro  = numeri[1]

    for pattern_oro in [r"(?:numero\s*oro|gold)[^0-9]*(\d{1,2})", r"oro[^0-9]*(\d{1,2})"]:
        m = re.search(pattern_oro, blocco, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 90:
                numero_oro = n
                print(f"✅ Numero Oro trovato: {numero_oro}")
                break

    for pattern_doppio in [r"(?:doppio\s*oro|double\s*gold)[^0-9]*(\d{1,2})", r"doppio[^0-9]*(\d{1,2})"]:
        m = re.search(pattern_doppio, blocco, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 90 and n != numero_oro:
                doppio_oro = n
                print(f"✅ Doppio Oro trovato: {doppio_oro}")
                break

    # Numeri Extra (15 numeri aggiuntivi)
    extra = []
    for pattern_extra in [r"(?:extra|numeri\s*extra)[^0-9]*((?:\d{1,2}\s*){5,15})", r"extra[^<]*"]:
        m = re.search(pattern_extra, blocco, re.IGNORECASE)
        if m:
            extra = estrai_numeri(m.group(0), 15)
            extra = [n for n in extra if n not in numeri][:15]
            if len(extra) >= 5:
                print(f"✅ Extra trovati: {len(extra)} → {extra}")
                break

    return {
        "data":          data_obj.isoformat(),         # "2026-06-25"
        "data_testo":    data_leggibile,                # "Mercoledì 25 giugno 2026"
        "numeri":        numeri,                        # [2, 5, 8, ...]
        "numero_oro":    numero_oro,
        "doppio_oro":    doppio_oro,
        "extra":         extra,
        "aggiornato_il": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

def main():
    print(f"=== Fetch 10eLotto Serale - {date.today()} ===\n")

    try:
        html_content = fetch_html(TARGET_URL)
        print(f"HTML ricevuto: {len(html_content)} caratteri\n")
    except Exception as e:
        print(f"❌ Errore fetch: {e}")
        sys.exit(1)

    try:
        dati = parse_10elotto(html_content)
    except Exception as e:
        print(f"❌ Errore parsing: {e}")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Salvato {OUTPUT_FILE}")
    print(f"   Data        : {dati['data_testo']}")
    print(f"   Numeri      : {dati['numeri']}")
    print(f"   Numero Oro  : {dati['numero_oro']}")
    print(f"   Doppio Oro  : {dati['doppio_oro']}")
    print(f"   Extra ({len(dati['extra'])}): {dati['extra']}")

if __name__ == "__main__":
    main()
