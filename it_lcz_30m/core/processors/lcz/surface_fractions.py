# -*- coding: utf-8 -*-

import os
from qgis.core import QgsVectorLayer, QgsCoordinateTransform, QgsProject, QgsFeatureRequest, QgsGeometry
from qgis.PyQt.QtCore import QVariant
import processing
from .base import LCZBaseProcessor

class SurfaceFractionsProcessor(LCZBaseProcessor):
    def process(self, layer, target_path, log_callback=None):
        """Calcolo Building, Impervious e Pervious Surface Fraction (BSF, ISF, PSF)."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        PERVIOUS = [10, 20, 30, 40, 60, 90, 95, 100]
        EXCLUDED = [70, 80]
        
        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
        landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
        hrl_path = os.path.join(unified_dir, "imperviousness_10m.tif")

        idx_link = self._ensure_link_id(layer)
        idx_bld = self._ensure_field(layer, 'building_frac')
        idx_imp = self._ensure_field(layer, 'impervious_frac')
        idx_per = self._ensure_field(layer, 'pervious_frac')
        
        # 1. BSF from vectors
        log_local("Fase 1: Calcolo Building Fraction dai vettori...")
        bsf_data = {}
        bld_layer = QgsVectorLayer(buildings_path, "bld", "ogr")
        if bld_layer.isValid():
            transform = None
            if bld_layer.crs() != layer.crs():
                log_local(f"Riproiezione edifici {bld_layer.crs().authid()} -> {layer.crs().authid()}")
                transform = QgsCoordinateTransform(bld_layer.crs(), layer.crs(), QgsProject.instance())
            
            found_bld = 0
            for feature in layer.getFeatures():
                geom = feature.geometry()
                cell_area = geom.area()
                b_area = 0.0
                query_geom = QgsGeometry(geom)
                if transform:
                    try:
                        inv_transform = QgsCoordinateTransform(layer.crs(), bld_layer.crs(), QgsProject.instance())
                        query_geom.transform(inv_transform)
                    except: pass
                
                request = QgsFeatureRequest().setFilterRect(query_geom.boundingBox())
                for bldg in bld_layer.getFeatures(request):
                    bldg_geom = bldg.geometry()
                    if transform: bldg_geom.transform(transform)
                    if bldg_geom.intersects(geom):
                        inter = bldg_geom.intersection(geom)
                        if inter: b_area += inter.area()
                
                if b_area > 0: found_bld += 1
                bsf_data[feature.attribute(idx_link)] = min(100.0, (b_area / cell_area) * 100)
            log_local(f"Edifici trovati in {found_bld} celle.")

        # 2. ISF/PSF calculation logic
        has_hrl = os.path.exists(hrl_path)
        hrl_data = {}
        esa_layer = None

        if has_hrl:
            log_local("Fase 2: Utilizzo Impermeabilità Alta Risoluzione (Copernicus HRL)...")
            res_hrl = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': hrl_path, 'COLUMN_PREFIX': '_hrl_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            idx_hrl_mean = res_hrl['OUTPUT'].fields().indexFromName('_hrl_mean')
            idx_temp_link = res_hrl['OUTPUT'].fields().indexFromName('_link_id')
            for f in res_hrl['OUTPUT'].getFeatures():
                lk = f.attribute(idx_temp_link)
                v = f.attribute(idx_hrl_mean)
                if lk is not None: hrl_data[lk] = float(v or 0)
        else:
            log_local("Fase 2: Analisi Land Cover (ESA WorldCover) - HRL non trovato...")
            res_esa = processing.run("native:zonalhistogram", {
                'INPUT_VECTOR': layer, 'INPUT_RASTER': landuse_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'h_', 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            esa_layer = res_esa['OUTPUT']

        def get_esa_val(f, name):
            idx = f.fields().indexFromName(name)
            if idx == -1: return 0
            v = f.attribute(idx)
            return float(v) if v is not None and v != QVariant() else 0

        layer.startEditing()
        processed = 0
        
        # We iterate over the original layer features to apply the results
        for feat in layer.getFeatures():
            lk = feat.attribute(idx_link)
            if lk is None: continue
            
            b_frac = bsf_data.get(lk, 0.0)
            imp_f = 0.0
            per_f = 100.0 - b_frac # Initial guess
            
            if has_hrl:
                hrl_val = hrl_data.get(lk, 0.0)
                # HRL logic: HRL includes buildings. ISF = HRL - BSF. PSF = 100 - HRL.
                # If HRL is 80 and Buildings is 30, then Impervious is 50 and Pervious is 20.
                imp_f = max(0, hrl_val - b_frac)
                per_f = max(0, 100.0 - hrl_val)
            elif esa_layer:
                # Fallback to ESA logic
                # Need to find the corresponding feature in esa_layer
                # (Optimization: could create a map before, but layer is usually small enough or we use link_id)
                request = QgsFeatureRequest().setFilterExpression(f"_link_id = {lk}")
                esa_feat = next(esa_layer.getFeatures(request), None)
                if esa_feat:
                    p_imp = get_esa_val(esa_feat, 'h_50')
                    p_per = sum(get_esa_val(esa_feat, f'h_{c}') for c in PERVIOUS)
                    p_exc = sum(get_esa_val(esa_feat, f'h_{c}') for c in EXCLUDED)
                    p_tot = p_imp + p_per + p_exc
                    if p_tot > 0:
                        esa_imp_f = (p_imp / p_tot) * 100
                        imp_f = max(0, esa_imp_f - b_frac)
                        per_f = max(0, 100.0 - b_frac - imp_f)
            
            # Normalization to ensure 100%
            total = b_frac + imp_f + per_f
            if total > 0:
                b_frac = (b_frac / total) * 100
                imp_f = (imp_f / total) * 100
                per_f = (per_f / total) * 100
            
            layer.changeAttributeValue(feat.id(), idx_bld, round(b_frac, 1))
            layer.changeAttributeValue(feat.id(), idx_imp, round(imp_f, 1))
            layer.changeAttributeValue(feat.id(), idx_per, round(per_f, 1))
            processed += 1
            
        layer.commitChanges()
        return processed
