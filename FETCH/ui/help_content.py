# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Help Content Repository

Contains all explanations for UI elements.
"""

HELP_PROJECT_SETUP = {
    "aoi_layer": {
        "title": "Layer Area di Studio (AOI)",
        "content": "Perimetro geometrico dell'ambito di indagine (Area of Interest). Questo vettore funge da maschera di ritaglio per la normalizzazione spaziale di tutti i dataset spettrali e morfologici acquisiti.",
        "source": "Dato Utente (QGIS Layer)"
    },
    "capture_extent": {
        "title": "Cattura Estensione Mappa",
        "content": "Definisce l'area di studio acquisendo le coordinate correnti della mappa (Canvas Extent). Il sistema genera contestualmente un layer vettoriale ausiliario ('boundary.gpkg') necessario per l'interrogazione dei servizi WFS/API esterni.",
        "source": "QGIS Canvas Extent"
    }
}

HELP_DATA_ACQUISITION = {
    "tinitaly": {
        "title": "Tinitaly (DTM 10m)",
        "content": "Modello Digitale del Terreno (DTM) a 10m. Utilizzato per calcolare parametri morfologici come la pendenza e l'Sky View Factor (SVF).",
        "source": "Istituto Nazionale di Geofisica e Vulcanologia (INGV)",
        "url": "https://tinitaly.pi.ingv.it/"
    },
    "tum": {
        "title": "TUM (Edifici H 10m)",
        "content": "Altezze degli edifici a livello globale (Global Building Heights). Derivato da dati Sentinel-2 e altezze GEDI. Risoluzione 10m.",
        "source": "Technical University of Munich (TUM)",
        "url": "https://mediatum.ub.tum.de/1782307"
    },
    "eth": {
        "title": "ETH (Alberi H 10m)",
        "content": "Mappa globale dell'altezza della canopia vegetale (Global Canopy Height). Basata su dati GEDI e Sentinel-2. Risoluzione 10m.",
        "source": "ETH Zürich / Lang et al. (2022)",
        "url": "https://langnico.github.io/globalcanopyheight/"
    },
    "esa": {
        "title": "ESA WorldCover (Land Use)",
        "content": "Mappa globale di copertura del suolo a 10m. Utilizzata per definire le frazioni di superficie (Paved, Vegetated, Water, Soil) e l'ammettenza termica.",
        "source": "European Space Agency (ESA)",
        "url": "https://esa-worldcover.org"
    },
    "meta": {
        "title": "Meta HRSL (Popolazione)",
        "content": "Mappe di densità di popolazione ad alta risoluzione (30m). Utilizzate per stimare il calore antropogenico metabolico e residenziale.",
        "source": "Meta High Resolution Settlement Layer (HRSL)",
        "url": "https://registry.opendata.aws/dataforgood-fb-hrsl/"
    },
    "s2gm": {
        "title": "S2GM (Albedo Sentinel-2)",
        "content": "Mosaico globale Sentinel-2 per il calcolo dell'Albedo superficiale a banda larga. Richiede credenziali Copernicus Data Space Ecosystem (CDSE).",
        "source": "Sentinel-2 Global Mosaic (S2GM)",
        "url": "https://dataspace.copernicus.eu/"
    },
    "osm": {
        "title": "OSM Roads (Vettoriale)",
        "content": "Rete stradale vettoriale da OpenStreetMap. Utilizzata per stimare il calore antropogenico da traffico (lunghezza strade e gerarchia).",
        "source": "OpenStreetMap contributors",
        "url": "https://www.openstreetmap.org"
    },
    "anas": {
        "title": "Traffic ANAS (o Proxy OSM)",
        "content": "Flussi di traffico reale (Open Data MIT/ANAS). In caso di indisponibilità del servizio, il sistema genera una stima basata sulla gerarchia stradale OSM e coefficienti di letteratura (Hohenberger et al., 2025).",
        "source": "ANAS Open Data / OSM Proxy w/ Lit. Benchmarks",
        "url": "https://www.stradeanas.it/it/dati-di-traffico-medio"
    },
    "copernicus": {
        "title": "Copernicus HRL (10m)",
        "content": "High Resolution Layer (HRL) Imperviousness. Misura la percentuale di sigillatura del suolo. Fondamentale per il calcolo della Frazione Impermeabile.",
        "source": "Copernicus Land Monitoring Service (CLMS)",
        "url": "https://land.copernicus.eu/pan-european/high-resolution-layers/imperviousness"
    },
    "industry": {
        "title": "Industrial Points (E-PRTR)",
        "content": "Registro europeo delle emissioni e dei trasferimenti di sostanze inquinanti. Localizza i grandi impianti industriali per il calore antropogenico.",
        "source": "European Environment Agency (EEA)",
        "url": "https://industry.eea.europa.eu/"
    },
    "cdse_creds": {
        "title": "Credenziali CDSE",
        "content": "Credenziali di accesso per l'ecosistema dati Copernicus. L'autenticazione è un requisito tecnico mandatorio per l'interrogazione delle API Sentinel-2 (Albedo Layer).",
        "source": "Copernicus Data Space Ecosystem"
    },
    "remember": {
        "title": "Memorizzazione Sicura",
        "content": "Abilita la persistenza delle credenziali nel gestore sicuro di QGIS (QgsAuthManager). I dati sensibili vengono crittografati nel database locale di autenticazione e non esposti in chiaro.",
        "source": "QGIS Security Framework"
    }
}

HELP_PROCESSING = {
    "unify": {
        "title": "Unificazione e Ritaglio",
        "content": "Processo di normalizzazione spaziale. I dataset eterogenei vengono riproiettati nel sistema di riferimento metrico locale (UTM) e ritagliati sull'AOI per garantire la congruenza geometrica delle analisi successive.",
        "source": "FETCH Core Engine (GDAL/OGR)"
    },
    "dsm": {
        "title": "Generazione DSM",
        "content": "Sintesi del Modello Digitale di Superficie (DSM). L'algoritmo fonde l'orografia (DTM), i volumi edificati (LOD1) e la biomassa arborea (CHM) in un unico raster morfologico continuo.",
        "source": "Integrazione DTM + Edifici + Vegetazione"
    },
    "svf": {
        "title": "Sky View Factor (SVF)",
        "content": "Analisi del Fattore di Vista del Cielo (Sky View Factor). L'algoritmo calcola per ogni cella la porzione di volta celeste visibile, indicatore determinante per il rilascio termico radiativo notturno e l'effetto canyon.",
        "source": "Algoritmo ottimizzato NumPy (FETCH Engine)"
    }
}

HELP_GRID_DEFINITION = {
    "automatic_grid": {
        "title": "Generazione Automatica Griglia",
        "content": "Generazione procedurale della maglia vettoriale (Vector Grid) sull'estensione dell'area di studio. La risoluzione spaziale (30m, 50m, 100m) deve essere congruente con la scala dei processi microclimatici oggetto di analisi.",
        "source": "Algoritmo QGIS 'Create Grid'"
    },
    "existing_layer": {
        "title": "Utilizzo Layer Esistente",
        "content": "Impiego di una griglia di calcolo preesistente (formato Poligonale). Utile per garantire la continuità spaziale con studi pregressi o per l'utilizzo di partizioni territoriali non standard (es. isolati censuari).",
        "source": "Dato Utente (Polygon Layer)"
    }
}

HELP_PARAMETERS = {
    "sky_view_factor": {
        "title": "Sky View Factor (SVF)",
        "content": "Indice adimensionale (0-1) della geometria urbana. Valori bassi indicano canyon stretti e ridotto raffreddamento radiativo; valori alti denotano spazi aperti.",
        "source": "FETCH Engine (NumPy Optimization)"
    },
    "aspect_ratio": {
        "title": "Aspect Ratio e Rugosità",
        "content": "Rapporto dimensionale H/W (Height-to-Width) dei canyon urbani e altezza media degli elementi di rugosità (zH). Calcolato analizzando la geometria e la spaziatura media degli edifici (Nearest Neighbor Analysis).",
        "source": "Morphometric Analysis (Dati Edifici LOD1)"
    },
    "surface_fractions": {
        "title": "Frazioni di Copertura",
        "content": "Scomposizione frazionaria della copertura del suolo. Quantifica le percentuali di edificato (BSF), superfici impermeabili (ISF) e permeabili (PSF) guidando la classificazione LCZ.",
        "source": "ESA WorldCover + Copernicus HRL"
    },
    "terrain_roughness_class": {
        "title": "Rugosità del Terreno (TRC)",
        "content": "Classificazione aerodinamica (Lunghezza di Rugosità z0) secondo le categorie Davenport-Wieringa. Calcolata matricialmente in funzione dell'altezza degli elementi (zH) e della densità del costruito.",
        "source": "Analisi Morfometrica (Davenport Matrix)"
    },
    "surface_admittance": {
        "title": "Ammettenza Termica",
        "content": "Media ponderata dell'ammettenza termica dei materiali (Building, Paved, Soil, Vegetated). Calcolata combinando la Frazione Edificata e le classi ESA WorldCover con coefficienti da letteratura.",
        "source": "ESA WorldCover + Coeff. Stewart & Oke"
    },
    "surface_albedo": {
        "title": "Albedo Superficiale",
        "content": "Coefficiente di riflessione della radiazione solare (shortwave). Determina la quantità di energia assorbita dalle superfici urbane e contribuisce al bilancio energetico locale.",
        "source": "Sentinel-2 Global Mosaic (S2GM)"
    },
    "anthropogenic_heat_output": {
        "title": "Calore Antropogenico (QF)",
        "content": "Densità del flusso di calore antropogenico (QF). Somma dei contributi metabolici (Popolazione), traffico (OSM+ANAS) e sorgenti industriali puntuali (E-PRTR). Include stime per il riscaldamento/raffrescamento edifici.",
        "source": "Meta Pop. + ANAS Traffic + E-PRTR Industry"
    },
    "lcz_class": {
        "title": "Classe LCZ Finale",
        "content": "Classificazione LCZ risultante dall'analisi statistica (RMSEP). Assegna la zona climatica locale più probabile minimizzando l'errore rispetto ai profili standard (Stewart & Oke, 2012). Per approfondimenti sul framework e metodologia: DOI 10.2495/SC250031.",
        "source": "Algoritmo RMSEP (FETCH)"
    }
}
