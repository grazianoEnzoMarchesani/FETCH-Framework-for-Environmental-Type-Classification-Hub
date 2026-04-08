# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - Help Content Repository

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
        "content": "Modello Digitale del Terreno (DTM) a 10m. Utilizzato per calcolare parametri morfologici del territorio.",
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
        "content": "Mappa globale di copertura del suolo a 10m. Utilizzata per definire le classi di uso del suolo.",
        "source": "European Space Agency (ESA)",
        "url": "https://esa-worldcover.org"
    },
    "osm": {
        "title": "OSM Roads (Vettoriale)",
        "content": "Rete stradale vettoriale da OpenStreetMap.",
        "source": "OpenStreetMap contributors",
        "url": "https://www.openstreetmap.org"
    },
    "copernicus": {
        "title": "Copernicus HRL (10m)",
        "content": "High Resolution Layer (HRL) Imperviousness. Misura la percentuale di sigillatura del suolo.",
        "source": "Copernicus Land Monitoring Service (CLMS)",
        "url": "https://land.copernicus.eu/pan-european/high-resolution-layers/imperviousness"
    }
}
