# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Help Content Repository

Contains all explanations for UI elements.
"""

HELP_PROJECT_SETUP = {
    "aoi_layer": {
        "title": "Layer Area di Studio (AOI)",
        "content": "Seleziona un layer vettoriale esistente nel progetto QGIS che definisce i confini della tua area di studio. Tutti i dati scaricati verranno ritagliati su questo confine.",
        "source": "Dato Utente (QGIS Layer)"
    },
    "capture_extent": {
        "title": "Cattura Estensione Mappa",
        "content": "Utilizza l'estensione attualmente visibile nella mappa di QGIS come area di studio. Il sistema creerà automaticamente un file 'boundary.gpkg' per garantire la compatibilità con i servizi di download OSM.",
        "source": "QGIS Canvas Extent"
    }
}

HELP_DATA_ACQUISITION = {
    "tinitaly": {
        "title": "Tinitaly (DTM 10m)",
        "content": "Modello Digitale del Terreno ad alta risoluzione (10m) per l'intero territorio italiano. Essenziale per calcolare le quote e le pendenze.",
        "source": "INGV (Tarquini et al.)"
    },
    "tum": {
        "title": "TUM (Edifici H 10m)",
        "content": "Dataset globale delle altezze degli edifici derivato da dati satellitari. Fornisce l'altezza media delle strutture per ogni cella.",
        "source": "Technical University of Munich"
    },
    "eth": {
        "title": "ETH (Alberi H 10m)",
        "content": "Mappa globale dell'altezza della vegetazione (Canopy Height Model). Usata per integrare la vegetazione nel DSM.",
        "source": "ETH Zurich (Lang et al.)"
    },
    "esa": {
        "title": "ESA WorldCover (Land Use)",
        "content": "Mappa globale della copertura del suolo a 10m con 11 classi (edificato, foresta, agricoltura, ecc.).",
        "source": "European Space Agency (ESA)"
    },
    "meta": {
        "title": "Meta HRSL (Popolazione)",
        "content": "High Resolution Settlement Layer. Fornisce stime sulla densità di popolazione, usate per calcolare il calore antropogenico.",
        "source": "Meta / CIESIN (Columbia University)"
    },
    "s2gm": {
        "title": "S2GM (Albedo Sentinel-2)",
        "content": "Mosaici stagionali Sentinel-2 per il calcolo dell'Albedo superficiale (riflettanza). Richiede account CDSE.",
        "source": "Sentinel-2 Global Mosaic Service"
    },
    "osm": {
        "title": "OSM Roads (Vettoriale)",
        "content": "Dati stradali da OpenStreetMap. Usati per determinare la larghezza dei canyon urbani e il traffico.",
        "source": "OpenStreetMap contributors"
    },
    "anas": {
        "title": "Traffic ANAS (Italia)",
        "content": "Dati sul traffico veicolare per le strade statali italiane, integrati per la stima del calore antropogenico.",
        "source": "Open Data ANAS"
    },
    "copernicus": {
        "title": "Copernicus HRL (10m)",
        "content": "High Resolution Layers per l'impermeabilità del suolo (Imperviousness), essenziale per il bilancio idrologico.",
        "source": "Copernicus Land Monitoring Service"
    },
    "industrial": {
        "title": "Industrial Points (E-PRTR)",
        "content": "Registro europeo delle emissioni e dei trasferimenti di sostanze inquinanti da siti industriali.",
        "source": "European Environment Agency"
    },
    "cdse_creds": {
        "title": "Credenziali CDSE",
        "content": "L'accesso a Copernicus Data Space Ecosystem è gratuito ma obbligatorio per scaricare i dati Sentinel-2 (Albedo).",
        "source": "Copernicus Data Space Ecosystem"
    },
    "remember": {
        "title": "Memorizzazione Sicura",
        "content": "Se attivo, le credenziali vengono salvate in modo criptato all'interno del gestore password nativo di QGIS (Auth Manager).",
        "source": "QGIS Security Framework"
    }
}

HELP_PROCESSING = {
    "unify": {
        "title": "Unificazione e Ritaglio",
        "content": "Questa fase uniforma tutti i dati scaricati (Vettoriali e Raster) verso un unico Sistema di Riferimento (UTM locale) e li ritaglia esattamente sull'Area di Studio (AOI).",
        "source": "FETCH Core Engine (GDAL/OGR)"
    },
    "dsm": {
        "title": "Generazione DSM",
        "content": "Crea un Modello Digitale delle Superfici (DSM) sintetico combinando il terreno (DTM), le altezze degli edifici (LOD1) e la copertura vegetale (Canopy Height Model).",
        "source": "Integrazione DTM + Edifici + Vegetazione"
    },
    "svf": {
        "title": "Sky View Factor (SVF)",
        "content": "Calcola la porzione di cielo visibile da ogni cella della griglia (30m). Fondamentale per stimare il raffreddamento notturno e il comfort termico.",
        "source": "Algoritmo ottimizzato NumPy (FETCH Engine)"
    }
}

HELP_PARAMETERS = {
    "sky_view_factor": {
        "title": "Sky View Factor (SVF)",
        "content": "Calcola la porzione di cielo visibile da ogni cella. Fondamentale per stimare il raffreddamento notturno.",
        "source": "FETCH Engine (NumPy Optimization)"
    },
    "aspect_ratio": {
        "title": "Aspect Ratio e Rugosità",
        "content": "Calcola il rapporto H/W (altezza canyon / larghezza) e l'altezza media degli elementi di rugosità (zH).",
        "source": "Dati Edifici LOD1 + OSM Roads"
    },
    "surface_fractions": {
        "title": "Frazioni di Copertura",
        "content": "Ripartizione della cella in: Frazione Edificata (BSF), Impermeabile (ISF) e Permeabile (PSF).",
        "source": "ESA WorldCover + Copernicus HRL"
    },
    "terrain_roughness_class": {
        "title": "Rugosità del Terreno (TRC)",
        "content": "Classificazione Davenport della rugosità superficiale basata sull'uso del suolo.",
        "source": "Land Use (ESA) + Mappatura Davenport"
    },
    "surface_admittance": {
        "title": "Ammettenza Termica",
        "content": "Capacità del suolo di trasmettere calore. Influenzata dal tipo di superficie.",
        "source": "Mappatura Letteratura (Stewart & Oke, 2012)"
    },
    "surface_albedo": {
        "title": "Albedo Superficiale",
        "content": "Percentuale di radiazione solare riflessa. Dipende dai materiali e dal colore delle superfici.",
        "source": "Sentinel-2 Global Mosaic (S2GM)"
    },
    "anthropogenic_heat_output": {
        "title": "Calore Antropogenico (QF)",
        "content": "Flusso di calore generato da traffico, riscaldamento e metabolismo umano.",
        "source": "Meta Population + ANAS Traffic"
    },
    "lcz_class": {
        "title": "Classe LCZ Finale",
        "content": "Risultato della classificazione statistica. Identifica la Local Climate Zone più probabile per ogni cella.",
        "source": "Algoritmo RMSEP (FETCH)"
    }
}
