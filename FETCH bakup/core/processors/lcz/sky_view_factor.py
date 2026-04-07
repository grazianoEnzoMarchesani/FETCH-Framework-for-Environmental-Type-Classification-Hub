# -*- coding: utf-8 -*-

import os
import numpy as np
from osgeo import gdal, ogr
from .base import LCZBaseProcessor

class SkyViewFactorProcessor(LCZBaseProcessor):
    def calculate_raster(self, log_callback=None, search_radius=100, num_sectors=16, canopy_opacity=0.7, method='ground', overwrite=False):
        """
        Calculates Sky View Factor (SVF).
        - 'ground': POV at DTM level (LCZ compliant). Buildings = 0.
        - 'legacy': POV at DSM level (Roof-top). Traditional calculation.
        """
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
        canopy_path = os.path.join(unified_dir, "canopy_height_10m.tif")
        
        # Output path depends on method
        mapping = {
            'ground': "svf_10m.tif",
            'ground_no_building': "svf_no_building_10m.tif",
            'legacy': "svf_legacy_10m.tif"
        }
        filename = mapping.get(method, "svf_10m.tif")
        output_path = os.path.join(unified_dir, filename)

        if os.path.exists(output_path) and not overwrite:
            return True, f"SVF ({method}) già presente", output_path
        if not os.path.exists(dsm_path) or not os.path.exists(dtm_path):
            return False, "DSM o DTM mancante", None

        log_local(f"Calcolo SVF {method.upper()} (R: {search_radius}m, S: {num_sectors})...")
        
        dsm_ds = gdal.Open(dsm_path)
        dsm_band = dsm_ds.GetRasterBand(1)
        dsm_array = dsm_band.ReadAsArray().astype(np.float32)
        rows, cols = dsm_array.shape
        
        dtm_ds = gdal.Open(dtm_path)
        dtm_array = dtm_ds.GetRasterBand(1).ReadAsArray(buf_xsize=cols, buf_ysize=rows).astype(np.float32)
        
        # Load canopy for high-accuracy transparency
        is_tree = np.zeros_like(dsm_array, dtype=bool)
        if os.path.exists(canopy_path):
            canopy_ds = gdal.Open(canopy_path)
            canopy_array = canopy_ds.GetRasterBand(1).ReadAsArray(buf_xsize=cols, buf_ysize=rows).astype(np.float32)
            is_tree = canopy_array > 0.5
            canopy_ds = None

        # Metadata for rasterization and shifting
        geotransform = dsm_ds.GetGeoTransform()
        pixel_size = abs(geotransform[1])
        r_pix = int(search_radius / pixel_size)

        # Identify building pixels for ground modes
        is_building = np.zeros_like(dsm_array, dtype=bool)
        buildings_vec_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
        
        if os.path.exists(buildings_vec_path):
            log_local("Utilizzo maschera vettoriale edifici per il calcolo...")
            try:
                # Rasterize building footprints
                mem_driver = gdal.GetDriverByName('MEM')
                mask_ds = mem_driver.Create('', cols, rows, 1, gdal.GDT_Byte)
                mask_ds.SetGeoTransform(geotransform)
                mask_ds.SetProjection(dsm_ds.GetProjection())
                
                vector_ds = ogr.Open(buildings_vec_path)
                if vector_ds:
                    v_layer = vector_ds.GetLayer()
                    if v_layer.GetFeatureCount() > 0:
                        gdal.RasterizeLayer(mask_ds, [1], v_layer, burn_values=[1])
                        is_building = mask_ds.GetRasterBand(1).ReadAsArray().astype(bool)
                        log_local(f"Identificati {np.sum(is_building)} pixel come edifici dal vettoriale.")
                    else:
                        log_local("Sorgente edifici vuota, fallback su altezza.")
                        total_height = dsm_array - dtm_array
                        is_building = (total_height > 0.5) & (~is_tree)
                else:
                    log_local("Impossibile aprire il vettoriale edifici, fallback su altezza.")
                    total_height = dsm_array - dtm_array
                    is_building = (total_height > 0.5) & (~is_tree)
                mask_ds = None
                vector_ds = None
            except Exception as e:
                 log_local(f"Errore maschera edifici: {e}. Fallback su altezza.")
                 total_height = dsm_array - dtm_array
                 is_building = (total_height > 0.5) & (~is_tree)
        else:
            log_local("Vettoriale edifici non trovato, fallback su altezza.")
            total_height = dsm_array - dtm_array
            is_building = (total_height > 0.5) & (~is_tree)
        
        total_cos2_sum = np.zeros_like(dsm_array, dtype=np.float32)
        angles = np.linspace(0, 2 * np.pi, num_sectors, endpoint=False)
        
        # Valid pixels mask
        valid_mask = (dsm_array > -100) & (~np.isnan(dsm_array))
        
        for s, angle in enumerate(angles):
            if log_callback: log_callback(f"Settore {s+1}/{num_sectors}...")
            
            sector_max_tan = np.zeros_like(dsm_array, dtype=np.float32)
            sin_a, cos_a = np.sin(angle), np.cos(angle)
            
            for d_idx in range(1, r_pix + 1):
                dist = d_idx * pixel_size
                dy, dx = int(round(-d_idx * cos_a)), int(round(d_idx * sin_a))
                if dy == 0 and dx == 0: continue
                
                dsm_shifted = np.full_like(dsm_array, -9999.0)
                tree_shifted = np.zeros_like(is_tree, dtype=bool)
                
                r1_s, r2_s = max(0, -dy), min(rows, rows - dy)
                c1_s, c2_s = max(0, -dx), min(cols, cols - dx)
                r1_o, r2_o = max(0, dy), min(rows, rows + dy)
                c1_o, c2_o = max(0, dx), min(cols, cols + dx)
                
                if r1_s < r2_s and c1_s < c2_s:
                    dsm_shifted[r1_s:r2_s, c1_s:c2_s] = dsm_array[r1_o:r2_o, c1_o:c2_o]
                    tree_shifted[r1_s:r2_s, c1_s:c2_s] = is_tree[r1_o:r2_o, c1_o:c2_o]
                
                # POV selection
                if method in ['ground', 'ground_no_building']:
                    # Observer is AT GROUND (dtm_array), obstacles are dsm_shifted
                    tan = (dsm_shifted - dtm_array) / dist
                else:
                    # Legacy: Observer is AT DSM top (dsm_array), obstacles are dsm_shifted
                    tan = (dsm_shifted - dsm_array) / dist
                
                tan[tree_shifted] *= canopy_opacity
                sector_max_tan = np.maximum(sector_max_tan, tan)
            
            total_cos2_sum += np.cos(np.arctan(np.maximum(0, sector_max_tan)))**2
            
        svf_array = total_cos2_sum / num_sectors
        
        if method == 'ground':
            # Set SVF to 0.0 for building footprints in ground mode
            svf_array[is_building] = 0.0
        elif method == 'ground_no_building':
            # Set SVF to NaN for building footprints
            log_local(f"Mascheramento {np.sum(is_building)} pixel edifici come NoData...")
            svf_array[is_building] = np.nan
            
        svf_array[~valid_mask] = 1.0

        driver = gdal.GetDriverByName('GTiff')
        # Create the specific output
        out_ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32, options=['COMPRESS=DEFLATE'])
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(dsm_ds.GetProjection())
        out_band = out_ds.GetRasterBand(1)
        
        # Set NoData value explicitly for NaN support if needed
        if method == 'ground_no_building':
             out_band.SetNoDataValue(-9999.0) # We'll use this for real NoData, and buildings as NaN or -9999
             # Actually, GDAL handles NaN if we write it, but better to use a standard NoData
             svf_array[np.isnan(svf_array)] = -9999.0
             out_band.SetNoDataValue(-9999.0)
        
        out_band.WriteArray(svf_array)
        out_ds = None
        
        # KEY UPDATE: Force update of the canonical 'svf_10m.tif' layer used by zonal stats
        # If the method is NOT ground (which already saves to svf_10m.tif), we overwrite svf_10m.tif
        canonical_path = os.path.join(unified_dir, "svf_10m.tif")
        if output_path != canonical_path:
             import shutil
             try:
                 shutil.copy2(output_path, canonical_path)
                 log_local(f"Aggiornato layer attivo 'svf_10m.tif' con i dati {method}")
             except Exception as e:
                 log_local(f"Errore aggiornamento layer attivo: {str(e)}")

        return True, f"Calcolo SVF {method} completato", output_path

    def process(self, layer, target_path, log_callback=None, method='ground'):
        base_dir = self.dm.get_project_dir()
        mapping = {
            'ground': "svf_10m.tif",
            'ground_no_building': "svf_no_building_10m.tif",
            'legacy': "svf_legacy_10m.tif"
        }
        filename = mapping.get(method, "svf_10m.tif")
        svf_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", filename)
        return self._calc_zonal_mean(layer, target_path, svf_path, 'svf_mean', 'svf', log_callback)

