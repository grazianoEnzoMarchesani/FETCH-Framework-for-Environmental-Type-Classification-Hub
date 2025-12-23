# -*- coding: utf-8 -*-

import os
import numpy as np
import processing
from osgeo import gdal
from qgis.core import (
    QgsProject, Qgis, QgsMessageLog, QgsVectorLayer, 
    QgsField, QgsCoordinateReferenceSystem, QgsCoordinateTransform
)
from qgis.PyQt.QtCore import QVariant

class LCZCalculator:
    def __init__(self, data_manager):
        self.dm = data_manager

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "IT-LCZ", level)

    def calculate_svf(self, log_callback=None, search_radius=100, num_sectors=16, canopy_opacity=0.7):
        """Calculates Sky View Factor (SVF) from the synthetic DSM using pure Python."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
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
        # Force DTM to match DSM dimensions (safer than direct ReadAsArray)
        dtm_array = dtm_ds.GetRasterBand(1).ReadAsArray(buf_xsize=cols, buf_ysize=rows).astype(np.float32)
        
        geotransform = dsm_ds.GetGeoTransform()
        pixel_size = abs(geotransform[1])
        r_pix = int(search_radius / pixel_size)
        
        rows, cols = dsm_array.shape
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

    def calculate_parameters(self, grid_path, parameter_id=None, log_callback=None):
        """Calcola i parametri LCZ per ogni cella della griglia."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        PARAM_MAP = {
            'sky_view_factor': ('svf_mean', 'Sky View Factor'),
            'surface_fractions': (None, 'Surface Fractions (BSF/ISF/PSF)'),
            'surface_albedo': ('albedo', 'Surface Albedo'),
            'aspect_ratio': ('aspect_ratio', 'Building Aspect Ratio (H/W)'),
            'roughness_elements_height': ('z_h', 'Geometric Mean Height (z_H)'),
            'terrain_roughness_class': ('terrain_rough', 'Terrain Roughness Class'),
            'surface_admittance': ('admittance', 'Surface Admittance'),
            'anthropogenic_heat_output': ('anthro_heat', 'Anthropogenic Heat Output'),
        }

        if parameter_id and parameter_id not in PARAM_MAP:
             return False, f"Parametro {parameter_id} non supportato", None

        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        
        # Open working file
        target_path = grid_path
        if not grid_path.endswith("_lcz_params.gpkg"):
            target_path = grid_path.replace(".gpkg", "_lcz_params.gpkg")
            if not os.path.exists(target_path):
                import shutil
                shutil.copy2(grid_path, target_path)

        layer = QgsVectorLayer(target_path, "lcz_grid", "ogr")
        if not layer.isValid(): return False, "Griglia non valida", None
        
        # Ensure fields
        REQUIRED = [
            'svf_mean', 'building_frac', 'impervious_frac', 'pervious_frac', 'albedo',
            'aspect_ratio', 'z_h', 'terrain_rough', 'admittance', 'anthro_heat'
        ]
        missing = [QgsField(f, QVariant.Double) for f in REQUIRED if layer.fields().indexFromName(f) == -1]
        if missing:
            layer.dataProvider().addAttributes(missing)
            layer.updateFields()

        processed = 0
        if parameter_id == 'sky_view_factor':
            svf_path = os.path.join(unified_dir, "svf_10m.tif")
            processed = self._calc_zonal_mean(layer, target_path, svf_path, 'svf_mean', 'svf', log_local)

        elif parameter_id == 'surface_albedo':
            albedo_path = os.path.join(unified_dir, "albedo_10m.tif")
            processed = self._calc_zonal_mean(layer, target_path, albedo_path, 'albedo', 'alb', log_local)

        elif parameter_id == 'surface_fractions':
            buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
            landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
            processed = self._calc_fractions(layer, target_path, buildings_path, landuse_path, log_local)

        elif parameter_id == 'roughness_elements_height':
            dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
            dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
            processed = self._calc_roughness_height(layer, target_path, dsm_path, dtm_path, log_local)

        elif parameter_id == 'aspect_ratio':
            processed = self._calc_aspect_ratio(layer, log_local)

        elif parameter_id in ['terrain_roughness_class', 'surface_admittance', 'anthropogenic_heat_output']:
            pop_path = os.path.join(unified_dir, "population_10m.tif")
            processed = self._calc_secondary_params(layer, parameter_id, pop_path, log_local)

        return True, f"Calcolo completato ({processed} celle)", target_path

    def _calc_zonal_mean(self, layer, target_path, raster_path, field_name, prefix, log):
        """Helper to calculate zonal mean for a specific raster."""
        if not os.path.exists(raster_path):
            log(f"Raster mancante: {os.path.basename(raster_path)}", Qgis.Warning)
            return 0
        
        log(f"Calcolo statistiche zonali per {field_name}...")
        res = processing.run("native:zonalstatisticsfb", {
            'INPUT': target_path, 'INPUT_RASTER': raster_path, 'COLUMN_PREFIX': f'_tmp_{prefix}_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        temp_layer = res['OUTPUT']
        idx_dst = layer.fields().indexFromName(field_name)
        idx_src = temp_layer.fields().indexFromName(f'_tmp_{prefix}_mean') # Added missing underscore after {prefix}
        
        if idx_src == -1:
            log(f"Errore: colonna temporanea _tmp_{prefix}_mean non trovata.", Qgis.Warning)
            return 0

        layer.startEditing()
        processed = 0
        for feat in temp_layer.getFeatures():
            val = feat.attribute(idx_src)
            if val is not None and str(val) != 'NULL':
                try:
                    layer.changeAttributeValue(feat.id(), idx_dst, round(float(val), 3))
                    processed += 1
                except: pass
        layer.commitChanges()
        return processed

    def _calc_roughness_height(self, layer, target_path, dsm_path, dtm_path, log):
        """Calcolo geometric mean height of roughness elements (z_H)."""
        if not os.path.exists(dsm_path) or not os.path.exists(dtm_path):
            log("DSM o DTM mancante", Qgis.Warning); return 0
        
        # We need Mean(DSM) - Mean(DTM) for each cell
        log("Fase 1: Analisi DTM...")
        self._calc_zonal_mean(layer, target_path, dtm_path, 'z_h', 'dtm', log) # Temporarily store DTM mean in z_h
        
        log("Fase 2: Analisi DSM...")
        res = processing.run("native:zonalstatisticsfb", {
            'INPUT': target_path, 'INPUT_RASTER': dsm_path, 'COLUMN_PREFIX': '_tmp_dsm_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        temp_layer = res['OUTPUT']
        idx_dst = layer.fields().indexFromName('z_h')
        idx_dsm = temp_layer.fields().indexFromName('_tmp_dsm_mean')
        
        layer.startEditing()
        processed = 0
        for feat in temp_layer.getFeatures():
            fid = feat.id()
            dtm_mean = layer.getFeature(fid).attribute('z_h')
            dsm_mean = feat.attribute(idx_dsm)
            
            if dtm_mean is not None and dsm_mean is not None:
                try:
                    z_h = max(0, float(dsm_mean) - float(dtm_mean))
                    layer.changeAttributeValue(fid, idx_dst, round(z_h, 2))
                    processed += 1
                except: pass
        
        layer.commitChanges()
        return processed

    def _calc_aspect_ratio(self, layer, log):
        """Calcolo Aspect Ratio (H/W) using simplified building model."""
        idx_bld = layer.fields().indexFromName('building_frac')
        idx_zh = layer.fields().indexFromName('z_h')
        idx_ar = layer.fields().indexFromName('aspect_ratio')
        
        if idx_bld == -1 or idx_zh == -1:
            log("BSF o z_H mancante. Calcolarli prima.", Qgis.Warning); return 0
            
        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            bsf = feat.attribute(idx_bld) or 0
            zh = feat.attribute(idx_zh) or 0
            
            bsf_dec = float(bsf) / 100.0 if bsf else 0
            if bsf_dec < 0.01: 
                ar = 0.0
            elif bsf_dec > 0.9:
                ar = 5.0
            else:
                ar = (float(zh) * bsf_dec) / (1.0 - bsf_dec)
            
            layer.changeAttributeValue(feat.id(), idx_ar, round(min(10.0, ar), 2))
            processed += 1
            
        layer.commitChanges()
        return processed

    def _calc_secondary_params(self, layer, parameter_id, pop_path, log):
        """Calculates parameters based on lookups or population data."""
        idx_bld = layer.fields().indexFromName('building_frac')
        idx_imp = layer.fields().indexFromName('impervious_frac')
        idx_per = layer.fields().indexFromName('pervious_frac')
        idx_zh = layer.fields().indexFromName('z_h')
        
        idx_dst = layer.fields().indexFromName({
            'terrain_roughness_class': 'terrain_rough',
            'surface_admittance': 'admittance',
            'anthropogenic_heat_output': 'anthro_heat'
        }[parameter_id])

        # For Anthro Heat, try population zonal sum
        if parameter_id == 'anthropogenic_heat_output' and os.path.exists(pop_path):
            log("Integrazione dati popolazione per calcolo calore antropico...")
            res = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer.source(), 'INPUT_RASTER': pop_path, 'COLUMN_PREFIX': '_tmp_pop_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            pop_data = {f.id(): f.attribute('_tmp_pop_sum') for f in res['OUTPUT'].getFeatures()}
        else:
            pop_data = {}

        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            fid = feat.id()
            bsf = float(feat.attribute(idx_bld) or 0)
            isf = float(feat.attribute(idx_imp) or 0)
            psf = float(feat.attribute(idx_per) or 0)
            zh = float(feat.attribute(idx_zh) or 0)
            
            val = 0
            if parameter_id == 'terrain_roughness_class':
                if zh < 0.5: val = 2
                elif bsf < 10: val = 3
                elif bsf < 30: val = 4 if zh < 10 else 5
                elif bsf < 50: val = 6
                else: val = 7 if zh < 25 else 8
            
            elif parameter_id == 'surface_admittance':
                val = (bsf * 2000 + isf * 1800 + psf * 1100) / 100.0
            
            elif parameter_id == 'anthropogenic_heat_output':
                pop_density = float(pop_data.get(fid, 0) or 0)
                if pop_density:
                    val = (pop_density * 50) / 900.0
                    val += (bsf * 0.5)
                else:
                    val = (bsf * 0.8) + (isf * 0.2)
            
            layer.changeAttributeValue(fid, idx_dst, round(val, 2))
            processed += 1

        layer.commitChanges()
        return processed

    def _calc_fractions(self, layer, target_path, buildings_path, landuse_path, log):
        """Calcolo Building, Impervious e Pervious Surface Fraction (BSF, ISF, PSF)."""
        PERVIOUS = [10, 20, 30, 40, 60, 90, 95, 100]
        EXCLUDED = [70, 80]
        
        # 1. BSF from vectors
        log("Fase 1: Calcolo Building Fraction dai vettori...")
        bsf_data = {}
        bld_layer = QgsVectorLayer(buildings_path, "bld", "ogr")
        if bld_layer.isValid():
            from qgis.core import QgsFeatureRequest
            for feature in layer.getFeatures():
                geom = feature.geometry()
                cell_area = geom.area()
                b_area = 0.0
                for bldg in bld_layer.getFeatures(QgsFeatureRequest().setFilterRect(geom.boundingBox())):
                    if bldg.geometry().intersects(geom):
                        inter = bldg.geometry().intersection(geom)
                        if inter: b_area += inter.area()
                bsf_data[feature.id()] = min(100.0, (b_area / cell_area) * 100)
        
        # 2. ISF/PSF from Zonal Histogram
        log("Fase 2: Analisi Land Cover (ESA WorldCover)...")
        res = processing.run("native:zonalhistogram", {
            'INPUT_VECTOR': target_path, 'INPUT_RASTER': landuse_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'h_', 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        temp_layer = res['OUTPUT']
        
        idx_imp = layer.fields().indexFromName('impervious_frac')
        idx_per = layer.fields().indexFromName('pervious_frac')
        idx_bld = layer.fields().indexFromName('building_frac')
        
        def get_val(f, name):
            idx = f.fields().indexFromName(name)
            if idx == -1: return 0
            v = f.attribute(idx)
            return float(v) if v is not None and v != QVariant() else 0

        layer.startEditing()
        processed = 0
        for feat in temp_layer.getFeatures():
            fid = feat.id()
            p_imp = get_val(feat, 'h_50')
            p_per = sum(get_val(feat, f'h_{c}') for c in PERVIOUS)
            p_exc = sum(get_val(feat, f'h_{c}') for c in EXCLUDED)
            p_tot = p_imp + p_per + p_exc
            
            b_frac = bsf_data.get(fid, 0.0)
            imp_f, per_f = 0.0, 100.0 - b_frac
            
            if p_tot > 0:
                esa_imp_f = (p_imp / p_tot) * 100
                imp_f = max(0, esa_imp_f - b_frac)
                per_f = max(0, 100.0 - b_frac - imp_f)
            
            total = b_frac + imp_f + per_f
            if total > 0:
                b_frac = (b_frac / total) * 100
                imp_f = (imp_f / total) * 100
                per_f = (per_f / total) * 100
            
            layer.changeAttributeValue(fid, idx_bld, round(b_frac, 1))
            layer.changeAttributeValue(fid, idx_imp, round(imp_f, 1))
            layer.changeAttributeValue(fid, idx_per, round(per_f, 1))
            processed += 1
            
        layer.commitChanges()
        return processed
