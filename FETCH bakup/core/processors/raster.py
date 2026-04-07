# -*- coding: utf-8 -*-

import os
import glob
import numpy as np
import processing
from osgeo import gdal, ogr
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, Qgis, QgsMessageLog
)

class RasterProcessor:
    def __init__(self, data_manager):
        self.dm = data_manager

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def process_dataset(self, folder_path, config, output_path, target_crs, target_extent):
        """Process and merge raster files, then reproject and clip."""
        pattern = os.path.join(folder_path, config["pattern"])
        recursive = config.get("recursive", False)
        input_files = glob.glob(pattern, recursive=recursive)
        
        # Exclude cache folders
        input_files = [f for f in input_files if "cache" not in f]
        
        if not input_files:
            self.log(f"Nessun file trovato per pattern {config['pattern']} in {folder_path}")
            return False
        
        self.log(f"Trovati {len(input_files)} file raster da processare...")
        
        if len(input_files) > 1 and config.get("merge", False):
            temp_merged = output_path.replace(".tif", "_merged_temp.vrt")
            merge_params = {
                'INPUT': input_files,
                'RESOLUTION': 0, # Highest
                'SEPARATE': False,
                'PROJ_DIFFERENCE': False,
                'ADD_ALPHA': False,
                'OUTPUT': temp_merged
            }
            try:
                processing.run("gdal:buildvirtualraster", merge_params)
                input_for_warp = temp_merged
            except Exception as e:
                self.log(f"Errore VRT: {e}. Fallback su gdal:merge con compressione...")
                temp_merged = output_path.replace(".tif", "_merged_temp.tif")
                merge_params = {
                    'INPUT': input_files,
                    'PCT': False, 'SEPARATE': False, 'DATA_TYPE': 5, 
                    'OPTIONS': 'COMPRESS=DEFLATE|PREDICTOR=2|ZLEVEL=6',
                    'OUTPUT': temp_merged
                }
                processing.run("gdal:merge", merge_params)
                input_for_warp = temp_merged
        else:
            input_for_warp = input_files[0]
        
        warp_params = {
            'INPUT': input_for_warp,
            'TARGET_CRS': target_crs,
            'RESAMPLING': 0, # Nearest neighbor
            'OPTIONS': 'COMPRESS=DEFLATE|PREDICTOR=2|ZLEVEL=6',
            'TARGET_EXTENT': f"{target_extent.xMinimum()},{target_extent.xMaximum()},{target_extent.yMinimum()},{target_extent.yMaximum()}",
            'TARGET_EXTENT_CRS': target_crs,
            'MULTITHREADING': True,
            'OUTPUT': output_path
        }
        processing.run("gdal:warpreproject", warp_params)
        
        if len(input_files) > 1 and config.get("merge", False):
            if os.path.exists(temp_merged):
                try: os.remove(temp_merged)
                except: pass
        
        return os.path.exists(output_path)

    def create_synthetic_dsm(self, log_callback=None, overwrite=False):
        """Creates a synthetic DSM (Digital Surface Model) at 10m resolution."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        base_dir = self.dm.get_project_dir()
        if not base_dir: return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        if not os.path.exists(unified_dir):
            return False, "Cartella unified non trovata.", None
        
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
        canopy_path = os.path.join(unified_dir, "canopy_height_10m.tif")
        landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
        buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
        output_path = os.path.join(unified_dir, "dsm_10m.tif")
        
        if os.path.exists(output_path) and not overwrite:
            return True, "DSM già presente", output_path
        
        if not os.path.exists(dtm_path):
            return False, "DTM non trovato.", None
        
        log_local("Caricamento DTM di base...")
        dtm_ds = gdal.Open(dtm_path)
        if dtm_ds is None: return False, "Impossibile aprire DTM", None
        
        geotransform = dtm_ds.GetGeoTransform()
        projection = dtm_ds.GetProjection()
        x_size, y_size = dtm_ds.RasterXSize, dtm_ds.RasterYSize
        
        dtm_band = dtm_ds.GetRasterBand(1)
        dtm_array = dtm_band.ReadAsArray().astype(np.float32)
        
        # Identify NoData in DTM (common values: -9999, -32768, or metadata)
        nodata_val = dtm_band.GetNoDataValue()
        if nodata_val is None: nodata_val = -9999.0
        dtm_nodata_mask = (dtm_array == nodata_val) | (dtm_array < -1000)
        
        building_heights = np.zeros_like(dtm_array)
        tree_heights = np.zeros_like(dtm_array)
        valid_land_mask = np.ones_like(dtm_array)

        # Building Rasterization
        if os.path.exists(buildings_path):
            log_local("Rasterizzazione altezze edifici TUM...")
            temp_buildings_raster = os.path.join(unified_dir, "temp_buildings_height.tif")
            try:
                driver = gdal.GetDriverByName('GTiff')
                temp_ds = driver.Create(temp_buildings_raster, x_size, y_size, 1, gdal.GDT_Float32)
                temp_ds.SetGeoTransform(geotransform)
                temp_ds.SetProjection(projection)
                temp_band = temp_ds.GetRasterBand(1)
                temp_band.SetNoDataValue(0)
                temp_band.Fill(0)
                
                vector_ds = ogr.Open(buildings_path)
                if vector_ds:
                    layer = vector_ds.GetLayer()
                    height_attr = None
                    layer_defn = layer.GetLayerDefn()
                    for i in range(layer_defn.GetFieldCount()):
                        field_name = layer_defn.GetFieldDefn(i).GetName().lower()
                        if field_name in ['building_height', 'height', 'h', 'h_mean', 'height_mean']:
                            height_attr = layer_defn.GetFieldDefn(i).GetName()
                            break
                    
                    if height_attr:
                        gdal.RasterizeLayer(temp_ds, [1], layer, options=[f"ATTRIBUTE={height_attr}"])
                
                temp_ds = None 
                buildings_ds = gdal.Open(temp_buildings_raster)
                building_heights = buildings_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                buildings_ds = None
                if os.path.exists(temp_buildings_raster): os.remove(temp_buildings_raster)
            except Exception as e:
                log_local(f"Errore rasterizzazione edifici: {e}", Qgis.Warning)

        # Canopy Heights
        if os.path.exists(canopy_path):
            log_local("Integrazione altezze alberi ETH...")
            eth_ds = gdal.Open(canopy_path)
            if eth_ds:
                eth_band = eth_ds.GetRasterBand(1)
                # Use buf_xsize/buf_ysize to force alignment with DTM
                tree_heights = eth_band.ReadAsArray(
                    buf_xsize=x_size, buf_ysize=y_size
                ).astype(np.float32)
                
                # Handle ETH NoData (often 255, but check metadata)
                eth_nodata = eth_band.GetNoDataValue()
                if eth_nodata is None: eth_nodata = 255.0
                tree_heights[tree_heights == eth_nodata] = 0
                tree_heights[tree_heights > 200] = 0 # Safety for other NoData artifacts
                eth_ds = None

        # Land Use Masking
        if os.path.exists(landuse_path):
            log_local("Applicazione maschera Land Use (Acqua/Suolo nudo)...")
            lu_ds = gdal.Open(landuse_path)
            if lu_ds:
                # Use buf_xsize/buf_ysize to force alignment with DTM
                lu_array = lu_ds.GetRasterBand(1).ReadAsArray(
                    buf_xsize=x_size, buf_ysize=y_size
                )
                valid_land_mask[lu_array == 80] = 0 # Water
                valid_land_mask[lu_array == 60] = 0 # Bare soil
                lu_ds = None

        log_local("Calcolo DSM finale (DTM + MAX(Edifici, Alberi))...")
        # Combine objects and cap at a reasonable height (e.g., 100m for normal urban/forest)
        max_object_height = np.maximum(building_heights, tree_heights)
        max_object_height = np.clip(max_object_height, 0, 100.0)
        
        # Apply mask and handle DTM NoData
        dsm_array = dtm_array + (max_object_height * valid_land_mask)
        dsm_array[dtm_nodata_mask] = -9999.0
        
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(output_path, x_size, y_size, 1, gdal.GDT_Float32, options=['COMPRESS=DEFLATE'])
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(dsm_array)
        out_band.SetNoDataValue(-9999.0)
        out_ds = None
        
        return True, "DSM creato con successo", output_path
