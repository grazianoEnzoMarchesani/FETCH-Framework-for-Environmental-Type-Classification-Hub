# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Constants and Configuration

This module contains configuration constants for LCZ parameters 
and their visualization settings.
"""

# Mapping of parameters to their visualization settings
PARAM_VISUALIZATION = {
    'svf_mean': {'field': 'svf_mean', 'label': 'SVF', 'ramp': 'Viridis', 'min': 0, 'max': 1},
    'aspect_ratio': {'field': 'aspect_ratio', 'label': 'H/W', 'ramp': 'Plasma', 'min': 0, 'max': 3},
    'building_frac': {'field': 'building_frac', 'label': 'BSF', 'ramp': 'Reds', 'min': 0, 'max': 100},
    'impervious_frac': {'field': 'impervious_frac', 'label': 'ISF', 'ramp': 'Greys', 'min': 0, 'max': 100},
    'pervious_frac': {'field': 'pervious_frac', 'label': 'PSF', 'ramp': 'Greens', 'min': 0, 'max': 100},
    'z_h': {'field': 'z_h', 'label': 'zH', 'ramp': 'YlOrBr', 'min': 0, 'max': 50},
    'terrain_rough': {'field': 'terrain_rough', 'label': 'TRC', 'ramp': 'PuBu', 'min': 1, 'max': 8},
    'admittance': {'field': 'admittance', 'label': 'μ', 'ramp': 'OrRd', 'min': 500, 'max': 2500},
    'albedo': {'field': 'albedo', 'label': 'α', 'ramp': 'RdYlGn', 'min': 0, 'max': 0.5},
    'anthro_heat': {'field': 'anthro_heat', 'label': 'QF', 'ramp': 'Inferno', 'min': 0, 'max': 100},
}

# Data sources available for download
DATA_SOURCES = [
    "Tinitaly (DTM 10m)", "TUM (Edifici H 10m)",
    "ETH (Alberi H 10m)", "ESA WorldCover (Land Use)",
    "Meta HRSL (Popolazione)", "S2GM (Albedo Sentinel-2)",
    "OSM Roads (Vettoriale)", "Traffic ANAS (Italia)",
    "Copernicus HRL (10m)", "Industrial Points (E-PRTR)"
]

# LCZ Parameter definitions: (id, display_name, tooltip, output_fields)
PARAM_DEFINITIONS = [
    ('sky_view_factor', 'SVF Mean', 
     'Rapporto tra la porzione di volta celeste visibile dal suolo e una semisfera non ostruita.', 
     ['svf_mean']),
    ('aspect_ratio', 'Aspect Ratio', 
     'Rapporto medio altezza-larghezza dei canyon stradali (LCZ 1–7), spaziatura tra edifici (8–10) e alberi (A–G).', 
     ['aspect_ratio']),
    ('surface_fractions', 'Surface Frac.', 
     'Frazioni di copertura: edifici (BSF), superfici impermeabili (ISF) e permeabili (PSF).', 
     ['building_frac', 'impervious_frac', 'pervious_frac']),
    ('roughness_elements_height', 'Roughness H', 
     "Media geometrica dell'altezza degli edifici (LCZ 1–10) e degli elementi vegetali (LCZ A–F) [m].", 
     ['z_h']),
    ('terrain_roughness_class', 'Terrain Rough.', 
     'Classificazione della rugosità del terreno (Davenport et al., 2000) per contesti urbani e rurali.', 
     ['terrain_rough']),
    ('surface_admittance', 'S. Admittance', 
     'Capacità della superficie di assorbire o rilasciare calore [J m⁻² s⁻¹/² K⁻¹].', 
     ['admittance']),
    ('surface_albedo', 'S. Albedo', 
     'Rapporto tra la radiazione solare riflessa da una superficie e quella ricevuta.', 
     ['albedo']),
    ('anthropogenic_heat_output', 'Anthro. Heat', 
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
