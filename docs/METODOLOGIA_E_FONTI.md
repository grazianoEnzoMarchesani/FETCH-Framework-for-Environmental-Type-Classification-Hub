# Report metodologico: acquisizione dati e framework analitico FETCH

## Contesto e riferimento scientifico

Il sistema FETCH (Framework for Environmental Type Classification Hub) implementa uno schema classificatorio basato sulle Local Climate Zones (LCZ) definite da Stewart e Oke nel 2012. Questo framework suddivide il territorio in 17 classi climatiche — 10 di matrice urbana e 7 di tipo naturale — ciascuna caratterizzata da intervalli specifici per dieci parametri morfometrici e termofisici. L'assegnazione della classe LCZ avviene attraverso un algoritmo di minimizzazione dell'errore quadratico medio percentuale (RMSEP), che confronta i valori calcolati per ogni cella della griglia con i profili standard di riferimento.

## Architettura delle fonti dati

L'acquisizione dei dati si articola su più registri e servizi eterogenei, integrati attraverso protocolli WFS, API REST e download diretto di asset raster.

### Dati altimetrici e morfologici

Il Modello Digitale del Terreno (DTM) proviene dal servizio [Tinitaly](https://tinitaly.pi.ingv.it/) dell'Istituto Nazionale di Geofisica e Vulcanologia (INGV), con risoluzione nativa di 10 metri. Le altezze degli edifici derivano dal dataset [Global Building Heights](https://mediatum.ub.tum.de/1782307) elaborato dalla Technical University of Munich (TUM), che integra osservazioni Sentinel-2 con misure lidar GEDI a copertura globale. L'altezza della canopia vegetale è estratta dalla [mappa globale](https://langnico.github.io/globalcanopyheight/) prodotta da ETH Zürich (Lang et al., 2022), anch'essa basata sulla fusione di dati GEDI e Sentinel-2.

### Copertura del suolo e proprietà superficiali

La classificazione land use impiega [ESA WorldCover](https://esa-worldcover.org), mappa globale a 10 metri che distingue undici classi di copertura. Questo dataset alimenta il calcolo delle frazioni di superficie (edificato, impermeabile, permeabile) e contribuisce alla stima dell'ammettenza termica attraverso coefficienti ponderati da letteratura (Stewart & Oke, 2012). Il grado di impermeabilizzazione è affinato mediante l'[High Resolution Layer Imperviousness](https://land.copernicus.eu/pan-european/high-resolution-layers/imperviousness) del Copernicus Land Monitoring Service. L'albedo superficiale è derivato dal Sentinel-2 Global Mosaic, accessibile tramite le API del [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) con autenticazione dedicata.

### Flussi antropogenici

La stima del calore antropogenico integra tre componenti distinte. La densità di popolazione ad alta risoluzione (30 metri) proviene da [Meta HRSL](https://registry.opendata.aws/dataforgood-fb-hrsl/) (High Resolution Settlement Layer) e consente la quantificazione del contributo metabolico. I flussi veicolari attingono ai [dati di traffico medio giornaliero](https://www.stradeanas.it/it/dati-di-traffico-medio) pubblicati da ANAS sul portale Open Data del Ministero delle Infrastrutture; in caso di indisponibilità del servizio, il sistema ricorre a una stima proxy basata sulla gerarchia stradale OpenStreetMap e coefficienti empirici (Hohenberger et al., 2025). Le sorgenti industriali puntuali sono localizzate attraverso il registro [E-PRTR](https://industry.eea.europa.eu/) (European Pollutant Release and Transfer Register) dell'Agenzia Europea per l'Ambiente.

### Infrastrutture viarie

La rete stradale vettoriale è acquisita via Overpass API da [OpenStreetMap](https://www.openstreetmap.org) e impiegata sia per il calcolo del calore da traffico sia per l'analisi morfometrica della rugosità aerodinamica.

## Tabella sinottica delle fonti

| Dataset | Provider | Risoluzione | Tipo | Repository |
|---------|----------|-------------|------|------------|
| DTM Tinitaly | INGV | 10m | Raster | [tinitaly.pi.ingv.it](https://tinitaly.pi.ingv.it/) |
| Global Building Heights | TUM | 10m | Raster | [mediatum.ub.tum.de](https://mediatum.ub.tum.de/1782307) |
| Global Canopy Height | ETH Zürich | 10m | Raster | [langnico.github.io](https://langnico.github.io/globalcanopyheight/) |
| WorldCover | ESA | 10m | Raster | [esa-worldcover.org](https://esa-worldcover.org) |
| HRL Imperviousness | Copernicus | 10m | Raster | [land.copernicus.eu](https://land.copernicus.eu/pan-european/high-resolution-layers/imperviousness) |
| Albedo S2GM | Copernicus | 10m | Raster | [dataspace.copernicus.eu](https://dataspace.copernicus.eu/) |
| HRSL Population | Meta | 30m | Raster | [registry.opendata.aws](https://registry.opendata.aws/dataforgood-fb-hrsl/) |
| Road Network | OpenStreetMap | — | Vettoriale | [openstreetmap.org](https://www.openstreetmap.org) |
| Traffic Data | ANAS/MIT | — | Vettoriale | [stradeanas.it](https://www.stradeanas.it/it/dati-di-traffico-medio) |
| Industrial Points | EEA E-PRTR | — | Vettoriale | [industry.eea.europa.eu](https://industry.eea.europa.eu/) |

## Pipeline di elaborazione

I dataset acquisiti subiscono una fase di normalizzazione spaziale: riproiezione nel sistema metrico UTM locale e ritaglio sull'area di indagine mediante operazioni GDAL/OGR. Il Modello Digitale di Superficie (DSM) sintetizza DTM, volumi edificati LOD1 e biomassa arborea in un unico raster continuo. Su questo prodotto l'algoritmo calcola lo Sky View Factor (SVF), indicatore geometrico del rilascio radiativo notturno. L'analisi morfometrica degli edifici restituisce l'Aspect Ratio (H/W) e l'altezza media degli elementi di rugosità (zH) attraverso Nearest Neighbor Analysis. La classificazione aerodinamica segue la matrice Davenport-Wieringa per l'assegnazione delle classi di Terrain Roughness.

La griglia di calcolo, generabile a risoluzioni di 30, 50 o 100 metri, raccoglie tutti i parametri derivati. L'algoritmo RMSEP confronta ciascuna cella con i 17 profili LCZ di riferimento, assegnando la classe che minimizza lo scarto complessivo. Una post-elaborazione basata sulle classi ESA WorldCover affina il risultato per le aree a dominante naturale.

## Riferimenti

Stewart, I.D. & Oke, T.R. (2012). Local Climate Zones for Urban Temperature Studies. *Bulletin of the American Meteorological Society*, 93(12), 1879-1900.

Lang, N., Jetz, W., Schindler, K., & Wegner, J.D. (2022). A high-resolution canopy height model of the Earth. *arXiv preprint arXiv:2204.08322*.

Hohenberger, C., et al. (2025). Traffic heat flux estimation from open street data. *In preparation*.
