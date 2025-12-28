# -*- coding: utf-8 -*-
"""
Centralized Constants Module for FETCH Plugin

Contains all hardcoded layer names, field names, file names,
and LCZ mappings extracted from data_manager.py, classification.py,
and dashboard.py.

Reference: Stewart, I.D., & Oke, T.R. (2012). Local Climate Zones for Urban 
Temperature Studies. Bulletin of the American Meteorological Society, 93(12), 1879-1900.
"""


class LayerNames:
    """Display names for map layers loaded into QGIS."""
    
    # Unified data layers (from data_manager.py load_unified_layers)
    DTM = "DTM Tinitaly (10m)"
    BUILDINGS = "Edifici TUM LoD1"
    CANOPY = "Altezza Alberi ETH (10m)"
    LANDUSE = "Land Use ESA (10m)"
    POPULATION = "Popolazione Meta HRSL"
    ALBEDO = "Albedo Sentinel-2 (10m)"
    ROADS = "Reti Stradali OSM"
    TRAFFIC = "Punti Traffico ANAS"
    IMPERVIOUSNESS = "Impermeabilità Copernicus (10m)"
    INDUSTRY = "Punti Industriali E-PRTR"
    
    # Processing layers (from dashboard.py)
    DSM = "DSM Sintetico (10m)"
    SVF = "Sky View Factor (10m)"
    
    # Grid layer name templates
    GRID_TEMPLATE = "Griglia LCZ ({size}m)"
    GRID_CUSTOM = "Griglia LCZ (custom)"
    GRID_PARAMS_SUFFIX = " - Parametri"
    
    @classmethod
    def grid_name(cls, cell_size):
        """Generate grid layer name for a given cell size."""
        return cls.GRID_TEMPLATE.format(size=cell_size)
    
    @classmethod
    def grid_params_name(cls, cell_size):
        """Generate grid layer name with parameters suffix."""
        return cls.grid_name(cell_size) + cls.GRID_PARAMS_SUFFIX


class FileNames:
    """File names for unified/processed data outputs."""
    
    # Unified raster outputs
    DTM = "dtm_10m.tif"
    CANOPY = "canopy_height_10m.tif"
    LANDUSE = "landuse_10m.tif"
    POPULATION = "population_10m.tif"
    ALBEDO = "albedo_10m.tif"
    IMPERVIOUSNESS = "imperviousness_10m.tif"
    
    # Unified vector outputs
    BUILDINGS = "buildings_lod1.gpkg"
    ROADS = "roads.gpkg"
    TRAFFIC = "traffic_points.gpkg"
    INDUSTRY = "industry_points.gpkg"
    
    # Processing outputs
    DSM = "dsm_10m.tif"
    SVF = "svf_10m.tif"
    GRID = "griglia_lcz.gpkg"


class FieldNames:
    """Field names used in grid layer attributes."""
    
    # LCZ parameter fields (output by processors)
    SVF_MEAN = "svf_mean"
    ASPECT_RATIO = "aspect_ratio"
    BUILDING_FRAC = "building_frac"
    IMPERVIOUS_FRAC = "impervious_frac"
    PERVIOUS_FRAC = "pervious_frac"
    ROUGHNESS_HEIGHT = "z_h"
    TERRAIN_ROUGHNESS = "terrain_rough"
    ADMITTANCE = "admittance"
    ALBEDO = "albedo"
    ANTHROPOGENIC_HEAT = "anthro_heat"
    
    # Classification output fields
    LCZ_CLASS = "lcz_class"
    LCZ_RMSEP = "lcz_rmsep"
    LCZ_MATCHES = "lcz_matches"
    LCZ_ESA_FIX = "lcz_esa_fix"
    LCZ_TYPE_ALT = "LCZ_Type"  # Alternative field name if lcz_class exists with wrong type


class FolderNames:
    """Subfolder names for downloaded/processed data."""
    
    TINITALY = "tinitaly_tiles"
    TUM = "tum_lod1"
    ETH = "eth_canopy"
    ESA = "esa_worldcover"
    META = "meta_hrsl"
    SENTINEL = "sentinel2_albedo"
    OSM = "osm_roads"
    ANAS = "anas_traffic"
    HRL = "copernicus_hrl"
    INDUSTRY = "eprtr_industry"
    UNIFIED = "unified"


class LCZMappings:
    """LCZ classification reference data from Stewart & Oke (2012)."""
    
    # LCZ class codes to descriptions
    CLASSES = {
        '1': 'Compact highrise', '2': 'Compact midrise', '3': 'Compact lowrise',
        '4': 'Open highrise', '5': 'Open midrise', '6': 'Open lowrise',
        '7': 'Lightweight lowrise', '8': 'Large lowrise', '9': 'Sparsely built',
        '10': 'Heavy industry', 'A': 'Dense trees', 'B': 'Scattered trees',
        'C': 'Bush, scrub', 'D': 'Low plants', 'E': 'Bare rock or paved',
        'F': 'Bare soil or sand', 'G': 'Water'
    }
    
    # Natural classes (land cover types)
    NATURAL_CLASSES = {'A', 'B', 'C', 'D', 'E', 'F', 'G'}
    
    # Urban/Built classes
    BUILT_CLASSES = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '10'}
    
    # LCZ parameter ranges from Stewart & Oke (2012)
    # Format: {param: (min, max)} where float('inf') indicates no upper/lower bound
    PARAMETERS = {
        '1': {'sky_view_factor': (0.2, 0.4), 'aspect_ratio': (2, float('inf')), 'building_surface_fraction': (40, 60), 'impervious_surface_fraction': (40, 60), 'pervious_surface_fraction': (0, 10), 'height_roughness': (25, float('inf')), 'terrain_roughness': (8, 8), 'surface_admittance': (1500, 1800), 'surface_albedo': (0.1, 0.2), 'anthropogenic_heat': (50, 300)},
        '2': {'sky_view_factor': (0.3, 0.6), 'aspect_ratio': (0.75, 2), 'building_surface_fraction': (40, 70), 'impervious_surface_fraction': (30, 50), 'pervious_surface_fraction': (0, 20), 'height_roughness': (10, 25), 'terrain_roughness': (6, 7), 'surface_admittance': (1500, 2200), 'surface_albedo': (0.1, 0.2), 'anthropogenic_heat': (0, 75)},
        '3': {'sky_view_factor': (0.2, 0.6), 'aspect_ratio': (0.75, 1.5), 'building_surface_fraction': (40, 70), 'impervious_surface_fraction': (20, 50), 'pervious_surface_fraction': (0, 30), 'height_roughness': (3, 10), 'terrain_roughness': (6, 6), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.1, 0.2), 'anthropogenic_heat': (0, 75)},
        '4': {'sky_view_factor': (0.5, 0.7), 'aspect_ratio': (0.75, 1.25), 'building_surface_fraction': (20, 40), 'impervious_surface_fraction': (30, 40), 'pervious_surface_fraction': (30, 40), 'height_roughness': (25, float('inf')), 'terrain_roughness': (7, 8), 'surface_admittance': (1400, 1800), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 50)},
        '5': {'sky_view_factor': (0.5, 0.8), 'aspect_ratio': (0.3, 0.75), 'building_surface_fraction': (20, 40), 'impervious_surface_fraction': (30, 50), 'pervious_surface_fraction': (20, 40), 'height_roughness': (10, 25), 'terrain_roughness': (5, 6), 'surface_admittance': (1400, 2000), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 25)},
        '6': {'sky_view_factor': (0.6, 0.9), 'aspect_ratio': (0.3, 0.75), 'building_surface_fraction': (20, 40), 'impervious_surface_fraction': (20, 50), 'pervious_surface_fraction': (30, 60), 'height_roughness': (3, 10), 'terrain_roughness': (5, 6), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 25)},
        '7': {'sky_view_factor': (0.2, 0.5), 'aspect_ratio': (1, 2), 'building_surface_fraction': (60, 90), 'impervious_surface_fraction': (0, 20), 'pervious_surface_fraction': (0, 30), 'height_roughness': (2, 4), 'terrain_roughness': (4, 5), 'surface_admittance': (800, 1500), 'surface_albedo': (0.15, 0.35), 'anthropogenic_heat': (0, 35)},
        '8': {'sky_view_factor': (0.7, float('inf')), 'aspect_ratio': (0.1, 0.3), 'building_surface_fraction': (30, 50), 'impervious_surface_fraction': (40, 50), 'pervious_surface_fraction': (0, 20), 'height_roughness': (3, 10), 'terrain_roughness': (5, 5), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.15, 0.25), 'anthropogenic_heat': (0, 50)},
        '9': {'sky_view_factor': (0.8, 1), 'aspect_ratio': (0.1, 0.25), 'building_surface_fraction': (10, 20), 'impervious_surface_fraction': (0, 20), 'pervious_surface_fraction': (60, 80), 'height_roughness': (3, 10), 'terrain_roughness': (5, 6), 'surface_admittance': (1000, 1800), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 10)},
        '10': {'sky_view_factor': (0.6, 0.9), 'aspect_ratio': (0.2, 0.5), 'building_surface_fraction': (20, 30), 'impervious_surface_fraction': (20, 40), 'pervious_surface_fraction': (40, 50), 'height_roughness': (5, 15), 'terrain_roughness': (5, 6), 'surface_admittance': (1000, 2500), 'surface_albedo': (0.12, 0.2), 'anthropogenic_heat': (300, float('inf'))},
        'A': {'sky_view_factor': (0, 0.4), 'aspect_ratio': (1, float('inf')), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (3, 30), 'terrain_roughness': (8, 8), 'surface_admittance': (1000, 1800), 'surface_albedo': (0.12, 0.2), 'anthropogenic_heat': (0, 0)},
        'B': {'sky_view_factor': (0.5, 0.8), 'aspect_ratio': (0.25, 0.75), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (3, 15), 'terrain_roughness': (5, 6), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.15, 0.25), 'anthropogenic_heat': (0, 0)},
        'C': {'sky_view_factor': (0.7, 0.9), 'aspect_ratio': (0.25, 1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 2), 'terrain_roughness': (4, 5), 'surface_admittance': (700, 1500), 'surface_albedo': (0.15, 0.30), 'anthropogenic_heat': (0, 0)},
        'D': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 1), 'terrain_roughness': (3, 4), 'surface_admittance': (1200, 1600), 'surface_albedo': (0.15, 0.25), 'anthropogenic_heat': (0, 0)},
        'E': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (90, 100), 'pervious_surface_fraction': (0, 10), 'height_roughness': (0, 0.25), 'terrain_roughness': (1, 2), 'surface_admittance': (1200, 2500), 'surface_albedo': (0.15, 0.3), 'anthropogenic_heat': (0, 0)},
        'F': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 0.25), 'terrain_roughness': (1, 2), 'surface_admittance': (600, 1400), 'surface_albedo': (0.2, 0.35), 'anthropogenic_heat': (0, 0)},
        'G': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 0.25), 'terrain_roughness': (1, 1), 'surface_admittance': (1500, 1500), 'surface_albedo': (0.02, 0.10), 'anthropogenic_heat': (0, 0)}
    }
    
    # Mapping from grid field names to LCZ parameter names
    FIELD_TO_PARAM = {
        'svf_mean': 'sky_view_factor',
        'aspect_ratio': 'aspect_ratio',
        'building_frac': 'building_surface_fraction',
        'impervious_frac': 'impervious_surface_fraction',
        'pervious_frac': 'pervious_surface_fraction',
        'z_h': 'height_roughness',
        'terrain_rough': 'terrain_roughness',
        'admittance': 'surface_admittance',
        'albedo': 'surface_albedo',
        'anthro_heat': 'anthropogenic_heat'
    }
    
    # LCZ color palette (Stewart & Oke 2012 / WUDAPT standard)
    COLORS = {
        '1': '#8c0000', '2': '#cf0201', '3': '#fe0100', '4': '#bd4d01',
        '5': '#ff6600', '6': '#ff9957', '7': '#f9ef00', '8': '#bcbcbc',
        '9': '#fecca9', '10': '#555555', 'A': '#016901', 'B': '#06aa02',
        'C': '#638526', 'D': '#badb7a', 'E': '#000000', 'F': '#fbf5ad',
        'G': '#6a6afe', 'N/D': '#bebebe'
    }

    # LCZ class to UHI Vulnerability mapping (based on user's schema)
    # Changed from "Risk" to "Vulnerability" as per user request
    VULNERABILITY_MAPPING = {
        '2': 'Very High', '3': 'Very High', '10': 'Very High', '8': 'High',
        '1': 'High', '7': 'High', '5': 'Medium', '4': 'Medium', '6': 'Medium-Low',
        'E': 'Low-Medium', '9': 'Low', 'B': 'Low', 'C': 'Low', 'A': 'Very Low',
        'G': 'Very Low', 'D': 'Very Low', 'F': 'Very Low', 'N/D': 'Unknown/Other'
    }

    # UHI Vulnerability color palette
    VULNERABILITY_COLORS = {
        'Very High': '#ff5150',
        'High': '#e97131',
        'Medium': '#f6c6ac',
        'Medium-Low': '#fae2d6',
        'Low-Medium': '#d9f2d0',
        'Low': '#c0f0c8',
        'Very Low': '#c1e4f5',
        'Unknown/Other': '#bebebe'
    }
    
    # Desired order for vulnerability legend
    VULNERABILITY_ORDER = [
        'Very High', 'High', 'Medium', 'Medium-Low',
        'Low-Medium', 'Low', 'Very Low', 'Unknown/Other'
    ]

    # ESA WorldCover class codes to LCZ natural class mapping
    ESA_TO_LCZ = {
        10: 'A',   # Tree cover → Dense trees (or B if low SVF)
        20: 'C',   # Shrubland → Bush, scrub
        30: 'D',   # Grassland → Low plants
        40: 'D',   # Cropland → Low plants
        50: None,  # Built-up → Keep RMSEP classification (1-10)
        60: 'F',   # Bare/sparse vegetation → Bare soil (check impervious for E)
        70: 'F',   # Snow and ice → Bare soil/sand
        80: 'G',   # Permanent water bodies → Water
        90: 'D',   # Herbaceous wetland → Low plants (near water)
        95: 'A',   # Mangroves → Dense trees
        100: 'D',  # Moss and lichen → Low plants
    }
    
    @classmethod
    def get_description(cls, lcz_class):
        """Returns the description of an LCZ class."""
        return cls.CLASSES.get(lcz_class, "Unknown class")
    
    @classmethod
    def is_natural(cls, lcz_class):
        """Check if an LCZ class is a natural/land cover type."""
        return lcz_class in cls.NATURAL_CLASSES
    
    @classmethod
    def is_built(cls, lcz_class):
        """Check if an LCZ class is an urban/built type."""
        return lcz_class in cls.BUILT_CLASSES
