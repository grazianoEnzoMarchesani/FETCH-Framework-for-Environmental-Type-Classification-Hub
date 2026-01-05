# Report Tecnico: Classificatore LCZ v8 (Semantic Expert Engine)

Il classificatore **v8.0**, denominato **"Semantic Expert Engine"**, rappresenta un cambio di paradigma rispetto ai modelli puramente statistici o di Machine Learning (come il Random Forest della v7). Si basa su una logica "Expert System" che emula il processo decisionale di un perito esperto, utilizzando regole semantiche e una struttura a "distretti".

---

## 1. Filosofia del Motore Decisionale
A differenza dei classificatori standard che lavorano pixel-per-pixel, la v8 utilizza un approccio **Context-First**. Il sistema non cerca di indovinare la classe di ogni singolo punto in isolamento, ma analizza il contesto urbano circostante per assorbire il rumore locale e identificare pattern morfologici coerenti.

I pilastri della v8 sono:
1.  **Fuzzy Tagging**: Traduzione dei dati numerici in descrittori semantici (es. "Mid-rise", "Dense mix", "Mostly paved").
2.  **Archetype Matching**: Confronto tra l'identità del distretto e gli standard ufficiali di **Stewart & Oke (2012)**.
3.  **Logica Perfezionista**: Suddivisione automatica dei distretti eterogenei per garantire la purezza morfologica.
4.  **XAI (Explainable AI)**: Ogni scelta è giustificata da un'analisi testuale dei parametri che hanno portato alla decisione.

---

## 2. Il Ciclo di Classificazione (Step-by-Step)

Il processo avviene attraverso una sequenza di fasi logiche:

### Fase 1: Identificazione degli "Urban Seeds"
Il sistema isola inizialmente tutte le celle che hanno una frazione di edifici (**BSF**) $\ge 10.0\%$. Queste celle sono considerate il "cuore pulsante" dell'area urbana e fungono da base per la creazione dei distretti.

### Fase 2: Clustering Multidimensionale
Il motore raggruppa le celle non solo in base alla vicinanza spaziale, ma anche alla somiglianza morfologica. Viene utilizzato un algoritmo di clustering che pesa:
-   **Distanza Spaziale** (vicinanza fisica).
-   **Altezza degli Edifici ($z_h$)**: Peso 3.5 (Parametro critico).
-   **Densità Edificata (BSF)**: Peso 1.5.

### Fase 3: Il Controllo "Perfezionista" (Splitting)
Se un distretto appena creato presenta una varianza interna troppo elevata (es. edifici molto alti misti a edifici bassi), interviene il modulo **Perfectionist**. Questo divide il distretto in sotto-unità più pure, assicurando che ogni "Distretto Semantico" abbia una morfologia coerente (soglia di deviazione standard per l'altezza: $4.0m$).

### Fase 4: Audit Semantico (Mapping Stewart & Oke)
Per ogni distretto, viene eseguito un "Audit" completo su **10 parametri morfologici**:
1.  Sky View Factor (SVF)
2.  Aspect Ratio (H/W)
3.  Building Surface Fraction (BSF)
4.  Impervious Surface Fraction (ISF)
5.  Pervious Surface Fraction (PSF)
6.  Roughness Height ($z_h$)
7.  Terrain Roughness ($z_0$)
8.  Surface Admittance
9.  Surface Albedo
10. Anthropogenic Heat

**Logica di Veto**: Prima del calcolo del punteggio, vengono applicati dei **Veti Professionali**:
-   *Esempio*: Se un'area ha più del 20% di superficie impermeabile, non può essere classificata come LCZ G (Acqua).
-   *Esempio*: Se l'albedo è troppo alto ($>0.20$), viene esclusa la classe Acqua.

### Fase 5: Rinforzo Semantico ESA
Il sistema consulta i dati di riferimento di **ESA WorldCover**. Se la classe rilevata dall'archetipo coincide con la classe Land Use di ESA, il punteggio di confidenza riceve un **Bonus di Ancoraggio (+15%)**. Questo permette di risolvere ambiguità tra classi naturali simili.

---

## 3. Criteri di Scelta e Output
La classe finale assegnata è quella che ottiene il **Match Score** più elevato nel confronto con gli archetipi.

### Dati Prodotti per ogni Cella:
-   **LCZ Class**: Il codice della zona climatica locale.
-   **LCZ Matches**: Quanti dei 10 parametri ufficiali rientrano perfettamente nel range standard (es. "7/10").
-   **Confidence (Score)**: Percentuale di aderenza all'archetipo (0-100%).
-   **RMSEP**: Errore residuo (calcolato come $1.0 - Confidenza$).
-   **ESA Fix Status**: Indica se la classificazione è stata "Rinforzata" dai dati ESA.
-   **Vulnerability**: Livello di vulnerabilità UHI (es. "Very High" per LCZ 2/3/10).

---

## 4. Dati di Riferimento Utilizzati
-   **Morfologia**: Dati estratti da DTM, DSM, ed edifici LoD1 (BSF, H, SVF, etc.).
-   **Coprimuolto**: Copernicus Imperviousness (ISF) e Land Cover (PSF).
-   **Satellitare**: Albedo derivata da Sentinel-2.
-   **Expert Knowledge**: Il database interno dei parametri di Stewart & Oke integrato in `constants.py`.
-   **Validation**: ESA WorldCover (Contextual Anchor).

---

> [!NOTE]
> La v8 genera automaticamente un layer vettoriale aggiuntivo chiamato **"Distretti Semantici"**, che permette all'utente di visualizzare i confini delle macro-aree identificate dal motore e leggere la giustificazione testuale per ogni distretto.
