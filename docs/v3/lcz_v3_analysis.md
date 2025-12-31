# Analisi Statistica Comparativa degli Algoritmi di Classificazione LCZ
## Verso la Versione 3.0

> **Autore:** Analisi condotta in qualità di statistico senior  
> **Data:** 31 Dicembre 2025  
> **Scopo:** Definire linee guida per la versione 3.0 dell'algoritmo di classificazione

---

## 1. Sintesi delle Due Metodologie

### 1.1 Classificatore Standard (Stable - Dec 29)

Il classificatore **Standard** implementa un approccio basato su RMSEP (Root Mean Square Error Percentage) con priorità lessicografica:

```
Ordinamento: max(perfect_matches) → min(RMSEP)
```

**Formula RMSEP:**
$$
RMSEP = \sqrt{\frac{1}{n}\sum_{i=1}^{n}\left(\frac{x_i - \mu_i}{\mu_i}\right)^2}
$$

dove $x_i$ è il valore osservato e $\mu_i$ è il valore target (centro dell'intervallo LCZ).

**Caratteristiche chiave:**
- Priorità assoluta ai "perfect matches" (parametri entro l'intervallo)
- Nessuna soglia di rigetto esplicita
- Correzione ESA WorldCover post-classificazione

---

### 1.2 Classificatore Sperimentale (v2.0)

Il classificatore **Sperimentale** introduce un approccio a **Balanced Score** che combina linearmente RMSEP e match count:

```
Score = RMSEP - (perfect_matches × 0.15)
```

**Caratteristiche chiave:**
- Bonus del 15% per ogni parametro in range
- Soglia di rigetto rigida: `RMSEP > 2.5 → N/D`
- Stesso calcolo RMSEP di base

---

## 2. Analisi Critica: Pregi e Difetti

### 2.1 Classificatore Standard

| Aspetto | Valutazione |
|---------|-------------|
| **Pregi** | |
| Stabilità | Comportamento deterministico e prevedibile |
| Interpretabilità | I "perfect matches" forniscono una metrica intuitiva |
| Conservatività | Evita classificazioni aggressive su dati incerti |
| **Difetti** | |
| Sensibilità ordinale | L'ordinamento lessicografico crea discontinuità |
| Assenza penalizzazione | Non penalizza outlier estremi se altri parametri matchano |
| Edge cases | Può assegnare classi con RMSEP molto alto se ha molti match |

> [!WARNING]
> **Criticità matematica:** L'ordinamento lessicografico `(max_matches, min_rmsep)` può portare a situazioni paradossali dove una classe con 5 match e RMSEP=3.0 vince su una classe con 4 match e RMSEP=0.1.

---

### 2.2 Classificatore Sperimentale

| Aspetto | Valutazione |
|---------|-------------|
| **Pregi** | |
| Bilanciamento | Lo score combinato evita discontinuità |
| Soglia di rigetto | RMSEP > 2.5 previene classificazioni assurde |
| Flessibilità | Il bonus match è tunabile |
| **Difetti** | |
| Arbitrarietà parametri | Il valore 0.15 e la soglia 2.5 non sono giustificati teoricamente |
| Scala non normalizzata | RMSEP e bonus operano su scale diverse |
| Rischio under-classification | La soglia rigida può generare troppi N/D in aree miste |

> [!IMPORTANT]
> **Problema del bonus additivo:** La formula `RMSEP - 0.15×matches` assume che ogni match "vale" un 15% di riduzione errore, ma matematicamente questo è corretto solo se RMSEP è normalizzato su [0,1]. In pratica, RMSEP può superare 1.0, rendendo il bonus insignificante.

---

## 3. Problema Specifico: LCZ 10 (Heavy Industry)

### 3.1 Definizione Parametrica (Stewart & Oke 2012)

| Parametro | Range LCZ 10 | Criticità |
|-----------|--------------|-----------|
| `sky_view_factor` | 0.6 - 0.9 | Sovrapposizione con LCZ 5, 6, 9 |
| `aspect_ratio` | 0.2 - 0.5 | Molto specifico |
| `building_surface_fraction` | 20 - 30% | **Basso per contesti industriali** |
| `impervious_surface_fraction` | 20 - 40% | Simile a LCZ 5, 6 |
| `pervious_surface_fraction` | 40 - 50% | **Controintuitivo** |
| `height_roughness` | 5 - 15m | Sovrapposizione multipla |
| `anthropogenic_heat` | **300 - ∞ W/m²** | **Unico discriminante forte** |

> [!CAUTION]
> **Diagnosi del problema LCZ 10:** Il parametro discriminante primario è `anthropogenic_heat ≥ 300 W/m²`. Se questo valore non viene raggiunto (dato mancante o sottostimato), la classe LCZ 10 diventa indistinguibile da LCZ 8 (Large Lowrise) o LCZ 6 (Open Lowrise).

### 3.2 Origine del Problema

L'algoritmo attuale calcola `anthropogenic_heat` come:

```python
val = val_built + val_traffic + val_industry
```

dove `val_industry = total_ind_heat_w / cell_area`

**Criticità identificate:**

1. **Scala dei pesi industriali:** I pesi per settore (es. 50 MW per "Energy sector") sono benchmark conservativi. Un impianto petrolchimico reale potrebbe emettere 100-500 MW di calore residuo.

2. **Campionamento E-PRTR:** L'API IED/E-PRTR restituisce solo **stabilimenti con obbligo di reporting** (soglia di emissione). Impianti artigianali o piccola industria non figurano.

3. **Distribuzione spaziale:** Il valore viene diviso per `cell_area`. Con celle di 30m (900 m²), un impianto da 50 MW produce ~55,555 W/m² — molto alto. Ma se l'impianto è a 50m dalla cella, il contributo crolla a **zero**.

---

## 4. Problema dell'Agnosticismo Spaziale

### 4.1 Diagnosi

Entrambi gli algoritmi classificano ogni cella **indipendentemente** dal contesto circostante. Questo crea tre problemi:

| Problema | Manifestazione |
|----------|----------------|
| **Salt & Pepper** | Celle isolate con classe diversa dal vicinato |
| **Bordi netti** | Transizioni brusche fra zone omogenee |
| **Sensibilità al rumore** | Un singolo edificio alto può creare una cella LCZ 1 isolata |

### 4.2 Base Teorica

Nella letteratura LCZ (Stewart & Oke, 2012), le zone sono definite su **scale di centinaia di metri**. La griglia a 30m cattura variabilità sub-LCZ che dovrebbe essere smoothata.

> [!NOTE]
> **Soluzione proposta per v3.0:** Introdurre un passo di **post-processing spaziale** che consideri il vicinato (kernel 3×3 o 5×5) per:
> - Smoothing bayesiano (prior = classe dominante nel vicinato)
> - Majority filter per eliminare celle isolate
> - Edge-aware smoothing per preservare transizioni genuine

---

## 5. Analisi Fonti Dati Industriali (E-PRTR)

### 5.1 Struttura Dati Scaricata

L'endpoint EEA restituisce:

```
https://air.discomap.eea.europa.eu/arcgis/rest/services/Air/IED_SiteMap/MapServer/0/query
```

**Campi chiave:**
- `eprtr_sectors` → Settore industriale
- Coordinate punto → Centroide stabilimento

### 5.2 Limitazioni

| Limitazione | Impatto |
|-------------|---------|
| Solo grandi impianti | Manca piccola/media industria |
| Centroide singolo | Grandi stabilimenti (km²) ridotti a un punto |
| Dati nominali | Nessun dato reale su emissioni termiche |
| Aggiornamento | Dataset può essere non aggiornato |

> [!WARNING]
> **Affidabilità dati industriali:** I pesi termici assegnati (SECTOR_WEIGHTS) sono **stime conservative** basate su letteratura (sEEnergies, Buhler 2018), non dati reali. Per un'area specifica, i valori potrebbero essere sottostimati del 50-200%.

---

## 6. Layer Disponibili per Miglioramento v3.0

| Layer | Potenziale Utilizzo v3.0 |
|-------|--------------------------|
| **DTM/DSM** | ✓ Già usati per SVF, z_h, Aspect Ratio |
| **Buildings LoD1** | ✓ Fondamentale per BSF, H/W, z_h |
| **Canopy Height** | ✓ Transparency SVF, ma potrebbe pesare nella classificazione naturale |
| **ESA WorldCover** | ✓ Correzione post-classificazione |
| **Population Meta** | ⚠ Usato solo per anthro_heat residenziale, potrebbe pesare direttamente |
| **Imperviousness HRL** | ✓ ISF già integrata |
| **Roads OSM** | ✓ Già integrata nel traffico, ma potrebbe servire per aspect_ratio (street width) |
| **Traffic ANAS** | ⚠ Solo punti interpolati, bassa copertura spaziale |
| **Industry E-PRTR** | ⚠ Da potenziare con decay spaziale e stime migliori |
| **Albedo Sentinel-2** | ⚠ Usato ma con scarso peso discriminante attualmente |

---

## 7. Raccomandazioni per v3.0

### 7.1 Modifiche all'Algoritmo di Classificazione

1. **Normalizzazione RMSEP:**
   $$RMSEP_{norm} = \frac{RMSEP}{\max(RMSEP_{feasible})}$$
   
2. **Weighted Score con confidenza:**
   ```
   Score = α·RMSEP_norm + β·(1 - match_ratio) + γ·uncertainty
   ```
   dove `uncertainty` dipende dalla completezza dei parametri

3. **Soglia adattiva:** Invece di `RMSEP > 2.5 → N/D`, usare:
   ```
   if RMSEP > μ_class + 2σ_class → N/D
   ```

### 7.2 Miglioramento LCZ 10

1. **Decay spaziale industriale:**
   ```python
   heat_contribution = sum(weight_i / (1 + distance_i/decay_radius))
   ```
   con `decay_radius ≈ 500m` per modellare diffusione termica

2. **Integrazione satellitare:** Usare anomalie termiche da Landsat Band 10 come proxy diretto

3. **Soglia discriminante:** Se `anthro_heat < 200` E `building_frac < 25%`, escludere LCZ 10 a priori

### 7.3 Contestualizzazione Spaziale

1. **Pre-classification smoothing:** Media mobile sui raster input
2. **Post-classification filtering:** Majority filter 3×3 con soglia 5/9
3. **Object-based override:** Se una cella è circondata da 8 celle identiche, assume quella classe

---

## 8. Conclusioni

L'algoritmo **Standard** è più robusto per analisi conservative ma soffre di discontinuità matematiche. L'algoritmo **Sperimentale** è più elegante ma introduce parametri arbitrari.

Per la **versione 3.0**, raccomando:

1. Mantenere la struttura RMSEP normalizzata
2. Introdurre **contestualizzazione spaziale** (kernel-based)
3. Potenziare il modulo **anthropogenic_heat** con decay spaziale
4. Aggiungere un **confidence score** alla classificazione

> [!IMPORTANT]
> Prima di modificare il codice, suggerisco di validare queste proposte su un caso studio (es. Bologna) confrontando i risultati con classificazioni LCZ manuali o WUDAPT di riferimento.
