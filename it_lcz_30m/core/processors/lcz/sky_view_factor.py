# -*- coding: utf-8 -*-

import os
import numpy as np
from osgeo import gdal
from .base import LCZBaseProcessor

class SkyViewFactorProcessor(LCZBaseProcessor):
    def calculate_raster(self, log_callback=None, search_radius=100, num_sectors=16, canopy_opacity=0.7):
        """Calculates Sky View Factor (SVF) from the synthetic DSM using pure Python."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
        output_path = os.path.join(unified_dir, "svf_10m.tif")

        if os.path.exists(output_path):
            return True, "SVF già presente", output_path
        if not os.path.exists(dsm_path) or not os.path.exists(dtm_path):
            return False, "DSM o DTM mancante", None

        log_local(f"Calcolo SVF (Raggio: {search_radius}m, Settori: {num_sectors})...")
        
        dsm_ds = gdal.Open(dsm_path)
        dsm_band = dsm_ds.GetRasterBand(1)
        dsm_array = dsm_band.ReadAsArray().astype(np.float32)
        rows, cols = dsm_array.shape
        
        dtm_ds = gdal.Open(dtm_path)
        dtm_array = dtm_ds.GetRasterBand(1).ReadAsArray(buf_xsize=cols, buf_ysize=rows).astype(np.float32)
        
        geotransform = dsm_ds.GetGeoTransform()
        pixel_size = abs(geotransform[1])
        r_pix = int(search_radius / pixel_size)
        
        total_cos2_sum = np.zeros_like(dsm_array, dtype=np.float32)
        
        # Identify object types
        building_heights = dsm_array - dtm_array
        is_tree = (building_heights > 0.5) & (building_heights <= 2.0)
        
        # Sector definitions
        angles = np.linspace(0, 2 * np.pi, num_sectors, endpoint=False)
        log_local(f"Ottimizzazione vettoriale SVF ({num_sectors} settori)...")
        
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
                
                tan = (dsm_shifted - dsm_array) / dist
                tan[tree_shifted] *= canopy_opacity
                sector_max_tan = np.maximum(sector_max_tan, tan)
            
            total_cos2_sum += np.cos(np.arctan(np.maximum(0, sector_max_tan)))**2
            
        svf_array = total_cos2_sum / num_sectors
        svf_array[~valid_mask] = 1.0

        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32, options=['COMPRESS=DEFLATE'])
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(dsm_ds.GetProjection())
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(svf_array)
        out_ds = None
        
        return True, "Calcolo SVF completato", output_path

    def process(self, layer, target_path, log_callback=None):
        base_dir = self.dm.get_project_dir()
        svf_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "svf_10m.tif")
        return self._calc_zonal_mean(layer, target_path, svf_path, 'svf_mean', 'svf', log_callback)
