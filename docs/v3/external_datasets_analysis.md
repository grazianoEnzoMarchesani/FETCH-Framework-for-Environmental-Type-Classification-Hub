# Valutazione Dataset Esterni per LCZ Classificazione v3.0
## Report Onnicomprensivo

> **Data:** 31 Dicembre 2025  
> **Scopo:** Valutazione critica dell'integrazione di dataset autorevoli per migliorare la classificazione LCZ

---

## 1. Panoramica dei Dataset Proposti

| Dataset | Risoluzione | Formato | Accesso | Autorevolezza |
|---------|-------------|---------|---------|---------------|
| **AH4GUC** (Global Anthropogenic Heat) | ~1 km (30 arc-sec) | GeoTIFF | Figshare/Tokyo Tech | Alta (Nature Scientific Data) |
| **CORINE Land Cover 2018** | 100 m | Vector/Raster | REST/WMS EEA | Molto Alta (EEA ufficiale) |
| **Global LCZ Map (WUDAPT)** | 100 m | TMS Tiles | HTTP | Molto Alta (Demuzere et al. 2022) |

---

## 2. Dataset 1: AH4GUC (Global Anthropogenic Heat Flux)

### 2.1 Descrizione Tecnica

**Fonte:** Varquez et al. (2021), Nature Scientific Data  
**Metodologia:** Top-down energy balance (IEA consumption → spatial allocation)  
**Componenti:**
- Q_IA = Industrial & Agricultural heat
- Q_M = Metabolic heat
- Q_L = Heat loss (power generation)
- Q_VB = Commercial, residential, transport

**Dati disponibili:**
- 2010s (presente) e 2050s (futuro RCP8.5/SSP3)
- Valori orari rappresentativi mensili
- Unità: W/m² × 100,000 (integer)

### 2.2 Analisi Critica

#### Pregi
| Aspetto | Valutazione |
|---------|-------------|
| Copertura globale | ✓ Include qualsiasi location |
| Metodologia peer-reviewed | ✓ Nature Scientific Data |
| Temporal dynamics | ✓ Profili orari e stagionali |
| Proiezioni future | ✓ Utile per analisi climatiche |

#### Difetti
| Aspetto | Valutazione |
|---------|-------------|
| **Risoluzione ~1 km** | ✗ **Insufficiente per griglia 30m** |
| Smoothing regionale | ✗ Dettagli urbani persi |
| Anno 2010s | ⚠ Potenzialmente datato per alcune aree |
| Top-down bias | ⚠ Sovrastima aree residenziali, sottostima hotspot industriali |

### 2.3 Mapping con Parametro LCZ

```
LCZ Parameter: anthropogenic_heat (W/m²)
Stewart & Oke ranges:
  LCZ 10 (Heavy Industry): 300 - ∞
  LCZ 1 (Compact Highrise): 50 - 300
  LCZ 2/3 (Compact Mid/Low): 0 - 75
```

**Problema di scala:**  
A 1 km di risoluzione, il valore AH4GUC rappresenta la **media areale** di ~1,111 celle da 30m. Un hotspot industriale puntuale (che noi misuriamo via E-PRTR) viene "spalmato" su un'area enorme, perdendo significato per la classificazione LCZ 10.

### 2.4 Strategia di Integrazione Proposta

> [!IMPORTANT]
> **Non usare AH4GUC come input diretto alla classificazione**, ma come **strumento di validazione** per verificare che il nostro calcolo anthro_heat sia nell'ordine di grandezza corretto.

**Implementazione:**
```python
# Pseudo-code di validazione
ah4guc_cell = fetch_ah4guc_tile(cell_centroid)
local_calc = computed_anthro_heat  # Il nostro calcolo

discrepancy = abs(local_calc - ah4guc_cell) / max(local_calc, ah4guc_cell, 1)

if discrepancy > 0.5:
    flag_for_review(cell, "anthro_heat discrepancy with AH4GUC")
```

**Beneficio netto:** Identificare celle dove il nostro calcolo è anomalo rispetto al benchmark globale.

---

## 3. Dataset 2: CORINE Land Cover 2018

### 3.1 Descrizione Tecnica

**Fonte:** European Environment Agency (EEA)  
**Risoluzione:** 100 m (raster), ~25 ha MMU (vector)  
**Classi:** 44 classi gerarchiche (3 livelli)  
**Accesso:**
- REST: `https://image.discomap.eea.europa.eu/arcgis/rest/services/Corine/CLC2018_WM/MapServer`
- WMS: `https://image.discomap.eea.europa.eu/arcgis/services/Corine/CLC2018_WM/MapServer/WMSServer`

### 3.2 Classi Rilevanti per LCZ

| CORINE Code | Descrizione | LCZ Potenziale |
|-------------|-------------|----------------|
| **111** | Continuous urban fabric | 1, 2, 3 (densità alta) |
| **112** | Discontinuous urban fabric | 4, 5, 6 (densità media) |
| **121** | Industrial or commercial units | **8, 10** |
| **122** | Road and rail networks | E (impervious) |
| **131** | Mineral extraction sites | F, 10 |
| **141** | Green urban areas | B, D |
| **211-244** | Agricultural | D, C |
| **311-324** | Forest | A, B |
| **331** | Beaches, dunes, sands | F |
| **411-423** | Wetlands | D, G |
| **511-523** | Water bodies | **G** |

### 3.3 Analisi Critica

#### Pregi
| Aspetto | Valutazione |
|---------|-------------|
| Autorevolezza | ✓ Dataset ufficiale europeo |
| Semantica ricca | ✓ 44 classi interpretabili |
| Stabilità | ✓ Dataset maturo, ben documentato |
| Accesso API | ✓ REST e WMS nativi |

#### Difetti
| Aspetto | Valutazione |
|---------|-------------|
| **Risoluzione 100m** | ⚠ 3× più grossolana della nostra griglia |
| MMU 25 ha | ✗ Piccoli dettagli non catturati |
| Anno 2018 | ⚠ 7 anni vecchio |
| Generalizzazione | ⚠ "Industrial units" include tutto |

### 3.4 Confronto con ESA WorldCover

| Aspetto | ESA WorldCover (10m) | CORINE (100m) |
|---------|---------------------|---------------|
| Risoluzione | 10 m ✓ | 100 m ✗ |
| Aggiornamento | 2021 ✓ | 2018 ✗ |
| Classi | 11 (generiche) | 44 (dettaglio) |
| Industrial | ✗ Non distingue | ✓ Classe 121 |
| Accesso | Google Earth Engine | REST API EEA |

### 3.5 Strategia di Integrazione Proposta

> [!TIP]
> **Usare CORINE come supplemento a ESA WorldCover** per identificare celle con vocazione industriale (classe 121) e correggere la classificazione LCZ 8/10.

**Implementazione:**
```python
# Logica di correzione CORINE-aware
def apply_corine_correction(lcz_class, corine_class, anthro_heat):
    # Se CORINE dice "Industrial" (121) ma LCZ non è 8/10
    if corine_class == 121 and lcz_class not in ['8', '10']:
        if anthro_heat > 100:
            return '10'  # Heavy Industry
        else:
            return '8'   # Large Lowrise (warehouse/logistics)
    
    # Se CORINE dice "Urban fabric" ma ESA dice vegetation
    if corine_class in [111, 112] and lcz_class in ['A', 'B', 'C', 'D']:
        return lcz_class  # Trust morphology, might be park in city
    
    return lcz_class
```

**Beneficio netto:** Miglioramento discriminazione LCZ 10 nelle aree industriali certificate da CORINE.

---

## 4. Dataset 3: Global LCZ Map (WUDAPT/Demuzere 2022)

### 4.1 Descrizione Tecnica

**Fonte:** Demuzere, M., et al. (2022), ESSD  
**Metodologia:** Random Forest su Landsat/Sentinel + training globale  
**Risoluzione:** 100 m  
**Accuratezza riportata:** ~80% (OA), variabile per classe  
**Accesso:** TMS tiles  

```
Latest: https://lcz-generator.rub.de/tms/global-map-tiles/latest/{z}/{x}/{y}.png
```

### 4.2 Mapping Colori → Classi LCZ

I tile PNG usano lo schema colori Stewart & Oke standard:

| Colore RGB | LCZ Class |
|------------|-----------|
| #8c0000 | 1 - Compact Highrise |
| #cf0201 | 2 - Compact Midrise |
| #fe0100 | 3 - Compact Lowrise |
| #bd4d01 | 4 - Open Highrise |
| #ff6600 | 5 - Open Midrise |
| #ff9957 | 6 - Open Lowrise |
| #f9ef00 | 7 - Lightweight Lowrise |
| #bcbcbc | 8 - Large Lowrise |
| #fecca9 | 9 - Sparsely Built |
| #555555 | 10 - Heavy Industry |
| ... | (classi naturali) |

### 4.3 Analisi Critica

#### Pregi
| Aspetto | Valutazione |
|---------|-------------|
| Stessa ontologia | ✓ Classi LCZ identiche alle nostre |
| Peer-reviewed | ✓ Nature ESSD |
| Copertura globale | ✓ Include Italia |
| Validazione robusta | ✓ Bootstrap + 150 FUA |

#### Difetti
| Aspetto | Valutazione |
|---------|-------------|
| **Risoluzione 100m** | ⚠ 3× la nostra griglia |
| Accuratezza ~80% | ⚠ 20% errore sistematico |
| Solo imagery | ⚠ Non usa dati morfologici diretti |
| Format PNG | ⚠ Richiede parsing colori |
| Generalizzazione | ⚠ Addestrato globalmente, bias locale |

### 4.4 Strategia di Integrazione Proposta

> [!IMPORTANT]
> **Non usare Global LCZ come input**, ma come **benchmark di validazione** e per **spatial smoothing**.

**Caso d'uso 1: Validazione**
```python
def validate_against_wudapt(our_lcz, wudapt_lcz):
    """Calcola metriche di accordo."""
    same_family = (our_lcz in BUILT_CLASSES) == (wudapt_lcz in BUILT_CLASSES)
    exact_match = our_lcz == wudapt_lcz
    return {
        'exact_agreement': exact_match,
        'family_agreement': same_family,
        'wudapt_reference': wudapt_lcz
    }
```

**Caso d'uso 2: Prior bayesiano per smoothing**
```python
def spatial_smoothing_with_prior(cell_lcz, neighbors_lcz, wudapt_lcz, confidence):
    """
    Se la nostra classificazione è isolata E discorda con WUDAPT,
    considera di allinearla al vicinato/riferimento.
    """
    neighbor_consensus = mode(neighbors_lcz)
    
    # Se siamo isolati E WUDAPT concorda con i vicini
    if cell_lcz != neighbor_consensus and wudapt_lcz == neighbor_consensus:
        if confidence < 0.7:  # Bassa confidenza nostra
            return neighbor_consensus  # Allinea
    
    return cell_lcz
```

**Beneficio netto:** Riduzione effetto salt-and-pepper usando WUDAPT come prior spaziale.

---

## 5. Sintesi Comparativa

### 5.1 Matrice Ruolo/Dataset

| Obiettivo | AH4GUC | CORINE | WUDAPT LCZ |
|-----------|--------|--------|------------|
| Input classificazione | ✗ No | ⚠ Limitato | ✗ No |
| Validazione | ✓ Sì (anthro_heat) | ⚠ Minore | ✓ Sì (classe LCZ) |
| Correzione LCZ 10 | ⚠ Indiretto | ✓ Sì (classe 121) | ⚠ Indiretto |
| Spatial smoothing | ✗ No | ✗ No | ✓ Sì (prior) |
| Discriminazione naturale | ✗ No | ✓ Sì | ✓ Sì |

### 5.2 Facilità di Integrazione Tecnica

| Dataset | Download | Parsing | Processing | Complessità |
|---------|----------|---------|------------|-------------|
| AH4GUC | ⚠ Manual FigShare | ✓ GeoTIFF nativo | ✓ Zonal stats | Media |
| CORINE | ✓ REST API | ✓ Vector/Raster | ✓ Spatial join | Bassa |
| WUDAPT | ⚠ TMS tiles | ⚠ PNG→LCZ parsing | ⚠ Tile stitching | Alta |

---

## 6. Raccomandazioni Operative per v3.0

### 6.1 Priorità di Integrazione

| Priorità | Dataset | Ruolo | Effort |
|----------|---------|-------|--------|
| **1** | CORINE 2018 | Correzione LCZ 8/10 industriale | Basso |
| **2** | WUDAPT Global | Benchmark validazione + prior | Medio |
| **3** | AH4GUC | Controllo ordine grandezza anthro_heat | Basso (una tantum) |

### 6.2 Architettura Proposta

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT PRIMARI (10m)                     │
│  DTM, DSM, Buildings, Canopy, ESA WorldCover, HRL, Albedo  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CALCOLO PARAMETRI (30m grid)                  │
│  SVF, BSF, ISF, PSF, z_h, H/W, Anthro Heat, ...            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           CLASSIFICAZIONE RMSEP BASE                       │
│  ───────────────────────────────────────────────────────── │
│  + Correzione ESA WorldCover (naturali)                    │
│  + [NEW] Correzione CORINE (industriali classe 121)        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         POST-PROCESSING SPAZIALE [NEW]                     │
│  ───────────────────────────────────────────────────────── │
│  + Majority filter 3×3                                      │
│  + [NEW] Prior bayesiano con WUDAPT Global                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              OUTPUT + VALIDATION REPORT                    │
│  ───────────────────────────────────────────────────────── │
│  + Metriche accordo con WUDAPT                             │
│  + [NEW] Flag discrepanza anthro_heat vs AH4GUC            │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Pipeline di Download

```python
# Proposta di nuovi downloader
class CorineDownloader:
    rest_url = "https://image.discomap.eea.europa.eu/arcgis/rest/services/Corine/CLC2018_WM/MapServer/0/query"
    
    def fetch(self, extent) -> GeoJSON:
        # Query vector layer via REST
        params = {
            'where': '1=1',
            'geometry': extent_to_envelope(extent),
            'geometryType': 'esriGeometryEnvelope',
            'inSR': '4326',
            'outFields': 'Code_18,CLC_CODE',  # Codice CORINE
            'returnGeometry': 'true',
            'f': 'geojson'
        }
        return requests.get(self.rest_url, params=params).json()

class WudaptTileDownloader:
    tms_url = "https://lcz-generator.rub.de/tms/global-map-tiles/latest/{z}/{x}/{y}.png"
    
    def fetch_tile(self, z, x, y) -> np.array:
        # Download PNG e converti in matrice di classi LCZ
        img = imageio.imread(self.tms_url.format(z=z, x=x, y=y))
        return rgb_to_lcz_class(img, LCZ_COLOR_MAP)
```

---

## 7. Rischi e Mitigazioni

### 7.1 Rischi Identificati

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| CORINE non copre l'area | Bassa (EU) | Alto | Fallback a solo ESA |
| Tile WUDAPT non disponibile | Media | Medio | Graceful degradation |
| Parsing colori PNG errato | Alta | Alto | Validazione su subset noto |
| Latenza API durante elaborazione | Media | Medio | Download bulk pre-processing |
| Disallineamento temporale | Media | Medio | Documentare anno riferimento |

### 7.2 Test di Validazione

Prima dell'integrazione in produzione:

1. **Test Bologna:** Scaricare tutti e 3 i dataset sull'area test, verificare copertura e qualità
2. **Test Accuracy:** Confrontare classificazione v2 vs v3 su 50 punti campione manuali
3. **Test Performance:** Misurare overhead in termini di tempo elaborazione

---

## 8. Conclusioni

### 8.1 Valutazione Onesta

| Dataset | Utilità Reale | Complessità | Raccomandazione |
|---------|---------------|-------------|-----------------|
| **AH4GUC** | Bassa (validazione) | Bassa | ⚠ Opzionale, da scaricare una tantum |
| **CORINE** | **Media-Alta** | Bassa | ✓ **Integrare** per LCZ 8/10 |
| **WUDAPT** | Media | Media | ⚠ Integrare per validazione e smoothing |

### 8.2 Impatto Atteso su Problemi Identificati

| Problema | Soluzione Proposta | Dataset Chiave |
|----------|-------------------|----------------|
| LCZ 10 mal classificato | Correzione CORINE classe 121 | CORINE |
| Agnosticismo spaziale | Prior bayesiano + majority filter | WUDAPT |
| Anthro_heat sottostimato | Flag discrepanza (non correzione) | AH4GUC |

> [!CAUTION]
> **Nessuno di questi dataset può sostituire i dati ad alta risoluzione locali** (Buildings LoD1, DSM, HRL). Il loro valore è di **complemento e validazione**, non di input primario.

---

## 9. Note Finali

La risoluzione di ~100m di CORINE e WUDAPT significa che ogni loro pixel contiene **~11 celle** della nostra griglia 30m. Questo implica:

- **Non possono aggiungere dettaglio**, solo contesto regionale
- **Sono utili per bias correction**, non per classificazione primaria
- **Il consenso con questi dataset aumenta la confidenza**, ma il disaccordo non invalida automaticamente la nostra classificazione

L'approccio più saggio è trattarli come **prior gentili** che influenzano marginalmente la decisione, non come ground truth.
