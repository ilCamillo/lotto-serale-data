#!/usr/bin/env python3
"""
fetch_10elotto.py - versione debug: salva sempre l'HTML per analisi
"""

import json, re, sys
from datetime import date, datetime
import urllib.request, urllib.parse

SCRAPE_DO_TOKEN = "a7c707c84d8345ef9c381ef4aecf5e59a3a24261872"
TARGET_URL      = "https://estrazioni10elotto.it/"
OUTPUT_FILE     = "ultima_estrazione.json"
DEBUG_FILE      = "debug_html.txt"

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

def main():
    print(f"=== Fetch 10eLotto - {date.today()} ===\n")

    # 1. Fetch HTML
    try:
        html = fetch_html()
        print(f"HTML ricevuto: {len(html)} caratteri\n")
    except Exception as e:
        print(f"❌ Fetch fallito: {e}")
        sys.exit(1)

    # 2. Salva sempre il debug (primi 10000 caratteri) — verrà committato
    testo_completo = strip_tags(html)
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        f.write("=== HTML GREZZO (primi 5000 car) ===\n")
        f.write(html[:5000])
        f.write("\n\n=== TESTO PULITO (primi 5000 car) ===\n")
        f.write(testo_completo[:5000])
    print(f"Debug salvato in {DEBUG_FILE}")

    # 3. Stampa il testo pulito per vedere la struttura nei log
    print("\n--- TESTO PULITO (primi 1000 car) ---")
    print(testo_completo[:1000])
    print("---\n")

    # 4. Prova diversi pattern per trovare i numeri
    # Pattern A: "Concorso n° NNN/AAAA"
    m = re.search(r"Concorso\s+n[°º.]\s*(\d+)/(\d{4})", html, re.IGNORECASE)
    if m:
        print(f"✅ Pattern A trovato: Concorso n° {m.group(1)}/{m.group(2)}")
    else:
        print("❌ Pattern A (Concorso n°) NON trovato")

    # Pattern B: "Estrazione n. NNN"
    m2 = re.search(r"[Ee]strazione\s+n[°º.]\s*(\d+)", html)
    if m2:
        print(f"✅ Pattern B trovato: Estrazione n. {m2.group(1)}")
    else:
        print("❌ Pattern B (Estrazione n.) NON trovato")

    # Pattern C: cerca sequenza di 20 numeri separati da spazi/punti/virgole
    m3 = re.search(r"(\d{1,2}(?:\s*[·,\s]\s*\d{1,2}){19,})", testo_completo)
    if m3:
        print(f"✅ Pattern C trovato: {m3.group(0)[:100]}")
    else:
        print("❌ Pattern C (sequenza 20 numeri) NON trovato")

    # Non esce con errore — il file debug verrà committato
    print("\n⚠️  Script terminato in modalità debug. Controlla debug_html.txt nel repo.")

if __name__ == "__main__":
    main()
