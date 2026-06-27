# lotto-serale-data

Repo di dati per l'app **10eLotto** — contiene l'ultima estrazione del 10eLotto Serale
aggiornata automaticamente da una GitHub Action dopo ogni estrazione.

---

## 📁 File

| File | Descrizione |
|------|-------------|
| `ultima_estrazione.json` | Ultima estrazione in formato JSON — letto dall'app Android |
| `fetch_10elotto.py` | Script Python che scarica i dati via scrape.do |
| `.github/workflows/aggiorna_10elotto.yml` | GitHub Action automatica |

---

## 🔧 Formato JSON

```json
{
  "data": "2026-06-25",
  "data_testo": "Giovedì 25 giugno 2026",
  "numeri": [2, 3, 5, 12, 16, 17, 19, 24, 27, 28, 42, 43, 49, 55, 58, 65, 69, 70, 84, 88],
  "numero_oro": 42,
  "doppio_oro": 24,
  "extra": [9, 21, 32, 38, 40, 44, 54, 60, 62, 72, 73, 75, 76, 85, 90],
  "aggiornato_il": "2026-06-25T18:10:00Z"
}
```

---

## ⏰ Quando si aggiorna

La Action parte automaticamente **10 minuti dopo ogni estrazione**:

| Giorno | Orario italiano | Cron UTC (estate CEST+2) |
|--------|----------------|--------------------------|
| Martedì | 20:10 | `10 18 * * 2` |
| Giovedì | 20:10 | `10 18 * * 4` |
| Venerdì | 20:10 | `10 18 * * 5` |
| Sabato | 20:10 | `10 18 * * 6` |

> ⚠️ In inverno (CET = UTC+1) aggiorna il cron a `10 19 * * 2,4,5,6`

---

## 🚀 Setup iniziale

### 1. Crea il repo su GitHub
- Nome: `lotto-serale-data`
- Visibilità: **Public** (necessario per raw.githubusercontent.com senza token)

### 2. Carica tutti i file
```bash
git init
git remote add origin https://github.com/ilCamillo/lotto-serale-data.git
git add .
git commit -m "Setup iniziale"
git branch -M main
git push -u origin main
```

### 3. Verifica che la Action funzioni
- Vai su **Actions → Aggiorna 10eLotto Serale → Run workflow**
- Clicca **Run workflow** (pulsante verde)
- Dopo ~20 secondi `ultima_estrazione.json` sarà aggiornato

### 4. URL che l'app Android legge
```
https://raw.githubusercontent.com/ilCamillo/lotto-serale-data/main/ultima_estrazione.json
```

---

## 🔑 Token scrape.do

Il token è incluso direttamente in `fetch_10elotto.py`.
Con il piano gratuito hai **1000 chiamate/mese** — le estrazioni
sono ~64/anno (4 a settimana × ~16 settimane/mese = ~16/mese),
quindi sei abbondantemente dentro il limite.
