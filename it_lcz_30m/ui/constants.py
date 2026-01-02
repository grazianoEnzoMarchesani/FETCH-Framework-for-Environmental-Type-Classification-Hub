# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Constants and Configuration

This module contains configuration constants for LCZ parameters 
and their visualization settings.
"""

# Mapping of parameters to their visualization settings
PARAM_VISUALIZATION = {
    'svf_mean': {'field': 'svf_mean', 'label': 'Sky View Factor', 'ramp': 'Viridis', 'min': 0, 'max': 1},
    'aspect_ratio': {'field': 'aspect_ratio', 'label': 'Aspect Ratio (H/W)', 'ramp': 'Plasma', 'min': 0, 'max': 3},
    'building_frac': {'field': 'building_frac', 'label': 'Frazione Edificata (BSF)', 'ramp': 'Reds', 'min': 0, 'max': 100},
    'impervious_frac': {'field': 'impervious_frac', 'label': 'Frazione Impermeabile (ISF)', 'ramp': 'Greys', 'min': 0, 'max': 100},
    'pervious_frac': {'field': 'pervious_frac', 'label': 'Frazione Permeabile (PSF)', 'ramp': 'Greens', 'min': 0, 'max': 100},
    'z_h': {'field': 'z_h', 'label': 'Altezza media elementi di rugosità (zH)', 'ramp': 'YlOrBr', 'min': 0, 'max': 50},
    'terrain_rough': {'field': 'terrain_rough', 'label': 'Rugosità del Terreno (TRC)', 'ramp': 'PuBu', 'min': 1, 'max': 8},
    'admittance': {'field': 'admittance', 'label': 'Ammettenza Termica Superficiale', 'ramp': 'OrRd', 'min': 500, 'max': 2500},
    'albedo': {'field': 'albedo', 'label': 'Albedo Superficiale', 'ramp': 'RdYlGn', 'min': 0, 'max': 0.5},
    'anthro_heat': {'field': 'anthro_heat', 'label': 'Calore Antropogenico (QF)', 'ramp': 'Inferno', 'min': 0, 'max': 100},
    'lcz_class': {'field': 'lcz_class', 'label': 'Classe Local Climate Zone', 'renderer': 'categorized'},
    'lcz_vulnerability': {'field': 'lcz_vulnerability', 'label': 'Vulnerabilità Climatica', 'renderer': 'categorized'},
    'lcz_rmsep': {'field': 'lcz_rmsep', 'label': 'Errore Statistico (RMSEP)', 'ramp': 'Magma', 'min': 0, 'max': 1},
    'lcz_score': {'field': 'lcz_score', 'label': 'Punteggio Corrispondenza (Score)', 'ramp': 'Viridis', 'min': 0, 'max': 1},
    'lcz_confidence': {'field': 'lcz_confidence', 'label': 'Grado di Confidenza', 'ramp': 'YlGn', 'min': 0, 'max': 1},
    'lcz_rmsep_norm': {'field': 'lcz_rmsep_norm', 'label': 'Errore Normalizzato (v3)', 'ramp': 'Magma', 'min': 0, 'max': 1},
    'lcz_matches': {'field': 'lcz_matches', 'label': 'Corrispondenze Trovate', 'renderer': 'categorized'},
    'lcz_esa_fix': {'field': 'lcz_esa_fix', 'label': 'Rettifica ESA', 'renderer': 'categorized'},
    'lcz_corine_fix': {'field': 'lcz_corine_fix', 'label': 'Rettifica CORINE', 'renderer': 'categorized'},
}

# Data sources available for download
DATA_SOURCES = [
    "Tinitaly (DTM 10m)", "TUM (Edifici H 10m)",
    "ETH (Alberi H 10m)", "ESA WorldCover (Land Use)",
    "Meta HRSL (Popolazione)", "S2GM (Albedo Sentinel-2)",
    "OSM Roads (Vettoriale)", "Traffic ANAS (Italia)",
    "Copernicus HRL (10m)", "Industrial Points (E-PRTR)",
    "CORINE Land Cover (EEA)"
]

# LCZ Parameter definitions: (id, display_name, tooltip, output_fields)
PARAM_DEFINITIONS = [
    ('sky_view_factor', 'Sky View Factor', 
     'Rapporto tra la porzione di volta celeste visibile dal suolo e una semisfera non ostruita.', 
     ['svf_mean']),
    ('aspect_ratio', 'Aspect Ratio e Rugosità', 
     'Calcola Aspect Ratio (H/W) e Roughness Height (zH - Altezza media elementi di rugosità).', 
     ['aspect_ratio', 'z_h']),
    ('surface_fractions', 'Frazioni di Copertura', 
     'Frazioni di copertura: edifici (BSF), superfici impermeabili (ISF) e permeabili (PSF).', 
     ['building_frac', 'impervious_frac', 'pervious_frac']),
    ('terrain_roughness_class', 'Rugosità del Terreno', 
     'Classificazione della rugosità del terreno (Davenport et al., 2000) per contesti urbani e rurali.', 
     ['terrain_rough']),
    ('surface_admittance', 'Ammettenza Termica', 
     'Capacità della superficie di assorbire o rilasciare calore [J m⁻² s⁻¹/² K⁻¹].', 
     ['admittance']),
    ('surface_albedo', 'Albedo Superficiale', 
     'Rapporto tra la radiazione solare riflessa da una superficie e quella ricevuta.', 
     ['albedo']),
    ('anthropogenic_heat_output', 'Calore Antropogenico', 
     'Densità media del flusso di calore annuo da combustione e attività umana [W m⁻²].', 
     ['anthro_heat'])
]

# Grid names used throughout the plugin
GRID_LAYER_NAMES = [
    "Griglia LCZ (30m)", "Griglia LCZ (50m)", "Griglia LCZ (100m)", 
    "Griglia LCZ (custom)", "Griglia LCZ (30m) - Parametri", 
    "Griglia LCZ (50m) - Parametri", "Griglia LCZ (100m) - Parametri", 
    "Griglia LCZ (custom) - Parametri"
]
