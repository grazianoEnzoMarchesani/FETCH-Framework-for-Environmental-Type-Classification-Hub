# -*- coding: utf-8 -*-
"""
Centralized Constants Module for EnviProtocol Plugin

Contains all hardcoded layer names, field names, file names,
and folder mappings used by the data acquisition engine.
"""


class LayerNames:
    """Display names for map layers loaded into QGIS."""
    
    # Unified data layers
    DTM = "DTM Tinitaly (10m)"
    BUILDINGS = "Edifici TUM LoD1"
    CANOPY = "Altezza Alberi ETH (10m)"
    LANDUSE = "Land Use ESA (10m)"
    ROADS = "Reti Stradali OSM"
    IMPERVIOUSNESS = "Impermeabilità Copernicus (10m)"
    TCD = "Tree Cover Density Copernicus (10m)"


class FileNames:
    """File names for unified/processed data outputs."""
    
    # Unified raster outputs
    DTM = "dtm_10m.tif"
    CANOPY = "canopy_height_10m.tif"
    LANDUSE = "landuse_10m.tif"
    IMPERVIOUSNESS = "imperviousness_10m.tif"
    TCD = "tcd_10m.tif"
    
    # ENVI-met Export outputs
    EM_SUB_AREA = "sub_area.gpkg"
    EM_SURFACES = "surfaces.gpkg"
    EM_VEGETATION = "vegetation.gpkg"
    EM_BUILDINGS = "buildings_prepared.gpkg"
    
    # Unified vector outputs
    BUILDINGS = "buildings_lod1.gpkg"
    ROADS = "roads.gpkg"


class FieldNames:
    """Field names used in unified layer attributes."""
    pass


class FolderNames:
    """Subfolder names for downloaded/processed data."""
    
    TINITALY = "tinitaly_tiles"
    TUM = "tum_lod1"
    ETH = "eth_canopy"
    ESA = "esa_worldcover"
    OSM = "osm_roads"
    HRL = "copernicus_hrl"
    SNAPSHOTS = "snapshots"
    ENVIMET = "envimet_export"


class ProjectHeaders:
    """Standard headers for ENVI-met layers."""
    ENVIMET = "Integrazione ENVI-met"


# Mapping from ESA WorldCover to placeholder ENVI_ID
# These are used to tag vector polygons during the "Prepare for ENVI-met" task.
ESA_ENVIMET_MAPPING = {
    10: "TRE_01",   # Trees
    20: "SHB_01",   # Shrubland
    30: "GRS_01",   # Grassland
    40: "CRP_01",   # Cropland
    50: "BLD_01",   # Built-up
    60: "SOI_01",   # Bare / sparse vegetation
    70: "ICE_01",   # Snow and Ice
    80: "WAT_01",   # Permanent water bodies
    90: "WET_01",   # Herbaceous wetland
    95: "MAN_01",   # Mangroves
    100: "MOS_01"   # Moss and lichen
}
