# Registro delle decisioni (second brain)

Una voce per decisione: cosa, perché, cosa implica. Le più recenti in alto.
Stato: `attiva` · `rimandata` · `superata` (indica da quale voce).

---

## 2026-10-16 · AOI da città italiane (confini ISTAT)
**Stato:** attiva

**Decisione:** accanto a "Layer" ed "Estensione mappa" c'è la modalità **Città (confini ISTAT)** (sezione 1). Si scrive `Comune (SIGLA); Comune (SIGLA)`; i confini vengono scaricati in automatico da ISTAT.
- Fonte: ISTAT, confini a fini statistici **2026, non generalizzati** (shapefile, ~98 MB, CC BY 4.0). Cache a livello di profilo QGIS (`FETCH_cache/istat/2026`), scaricata una sola volta e condivisa tra i progetti.
- Input: nome + sigla di provincia; errore chiaro se il nome è ambiguo, sconosciuto o con sigla sbagliata (con suggerimenti).
- Più città: area unita, un solo layer (`boundary_city_<hash>.gpkg` nella cartella FETCH+progetto), con una feature per comune.
- I download restano sul rettangolo (bbox) dei comuni; il **ritaglio avviene alla griglia**: restano le celle che intersecano i comuni, intere e quadrate (nessun taglio sul bordo).
- Il nome del file di griglia e del layer confini contiene un hash dei codici comune, così un'altra selezione non sovrascrive file già caricati in QGIS.
- Il ritaglio della griglia vale anche in modalità "Layer vettoriale" se l'AOI è un layer poligonale su disco (non un semplice rettangolo): l'estensione serve per i download, la forma per la griglia. Il nome del file griglia porta l'hash della geometria.
- La città caricata (layer + testo) è salvata nel progetto QGIS e ripristinata alla riapertura.

**Perché:** evitare di disegnare/catturare a mano un rettangolo e lavorare solo sulle città volute; ISTAT è la fonte ufficiale e riproducibile.

**Limiti noti:**
- I downloader saltano i file già presenti ("già presenti"): cambiando città nello stesso progetto si riusano i dati scaricati per la città precedente. Preesistente, ma più probabile con le città.
- La modalità "Usa layer esistente" della griglia (sezione 4) non viene ritagliata.
- Città molto distanti → bbox enorme (la UI avvisa oltre 80 km).

---

## 2026-10-16 · Compatibilità QGIS 4 / Qt6
**Stato:** rimandata

**Decisione:** per ora il plugin resta su QGIS 3.40+ (Qt5). La compatibilità con QGIS 4 (Qt6) si farà più avanti, dopo aver testato la 2.01 su 3.44.

**Perché:** QGIS 4 non è ancora installato sulla macchina di sviluppo, quindi non si può verificare. Meglio stabilizzare prima la 2.01.

**Da fare quando arriva il momento:**
- Usare enum con scope completo (es. `Qt.DockWidgetArea.RightDockWidgetArea` invece di `Qt.RightDockWidgetArea`). Una prima ricerca ne ha trovati circa 15 usi non qualificati in `FETCH/` (Qt.*Align*, `QMessageBox.Yes`, `QSizePolicy.*`, `QFrame.*`, `.exec_()` ecc.).
- Mantenere la compatibilità con 3.x: gli enum con scope completo funzionano anche in PyQt5.
- Aggiornare `qgisMinimumVersion` / aggiungere `supportsQt6=yes` in `metadata.txt` solo dopo il test reale.
- Verificare le dipendenze (`requirements.txt`) sul Python di QGIS 4.

---

## 2026-10-16 · Base di lavoro: la cartella `FETCH/` è la 2.01
**Stato:** attiva

**Decisione:** si lavora direttamente su `FETCH/` nel branch `FetchPlugin-clean`. Il contenuto è identico a `FETCH 2.01.zip`, considerata pre-release (alpha), già online ma non in primo piano.

**Note:** `metadata.txt` dice ancora `version=2.0.0`; da allineare a 2.01 quando si decide la numerazione.

---

## 2026-10-16 · Installazione di sviluppo in QGIS tramite link simbolico
**Stato:** attiva

**Decisione:** FETCH compare nella lista plugin di QGIS 3.44 con un link simbolico da `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/FETCH` a `FETCH/` della repo.

**Perché:** le modifiche al codice sono subito visibili in QGIS (con il ricarico del plugin), senza reinstallare gli zip.
