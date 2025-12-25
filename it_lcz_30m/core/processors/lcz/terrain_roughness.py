# -*- coding: utf-8 -*-

import os
import processing
from qgis.core import (
    QgsFeatureRequest, QgsVectorLayer, QgsCoordinateTransform, 
    QgsProject, QgsGeometry, QgsField
)
from qgis.PyQt.QtCore import QVariant
from .base import LCZBaseProcessor

class TerrainRoughnessProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        idx_bld = layer.fields().indexFromName('building_frac')
        idx_zh = layer.fields().indexFromName('z_h')
        idx_dst = layer.fields().indexFromName('terrain_rough')
        idx_z0 = layer.fields().indexFromName('z0_value')

        # 1. Pre-fetch data if missing
        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
        buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")

        # Check if fields are empty by looking at first few features
        is_zh_empty = True
        is_bsf_empty = True
        for feat in layer.getFeatures(QgsFeatureRequest().setLimit(50)):
            if feat.attribute(idx_zh) not in [None, QVariant()]: is_zh_empty = False
            if feat.attribute(idx_bld) not in [None, QVariant()]: is_bsf_empty = False
        
        fallback_zh = {}
        if is_zh_empty and os.path.exists(dsm_path) and os.path.exists(dtm_path):
            log_local("z_h vuoto, calcolo temporaneo da DSM/DTM...")
            # Use a simplified zonal mean logic for z_h
            import processing
            res_dsm = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': dsm_path, 'COLUMN_PREFIX': '_t_dsm_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            res_dtm = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': dtm_path, 'COLUMN_PREFIX': '_t_dtm_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            idx_link = self._ensure_link_id(layer)
            l_dsm = res_dsm['OUTPUT']
            l_dtm = res_dtm['OUTPUT']
            
            dsm_map = {f.attribute('_link_id'): f.attribute('_t_dsm_mean') for f in l_dsm.getFeatures()}
            dtm_map = {f.attribute('_link_id'): f.attribute('_t_dtm_mean') for f in l_dtm.getFeatures()}
            
            for lk in dsm_map:
                v_dsm = dsm_map[lk]
                v_dtm = dtm_map.get(lk)
                if v_dsm is not None and v_dtm is not None:
                    fallback_zh[lk] = max(0, float(v_dsm) - float(v_dtm))

        fallback_bsf = {}
        if is_bsf_empty and os.path.exists(buildings_path):
            log_local("building_frac vuoto, calcolo temporaneo dai vettori edifici...")
            bld_layer = QgsVectorLayer(buildings_path, "bld", "ogr")
            if bld_layer.isValid():
                idx_link = self._ensure_link_id(layer)
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    area = geom.area()
                    b_area = 0.0
                    request = QgsFeatureRequest().setFilterRect(geom.boundingBox())
                    for bldg in bld_layer.getFeatures(request):
                        if bldg.geometry().intersects(geom):
                            inter = bldg.geometry().intersection(geom)
                            if inter: b_area += inter.area()
                    fallback_bsf[feat.attribute(idx_link)] = (b_area / area) * 100

        # 2. Main Classification Logic
        idx_link = self._ensure_link_id(layer)
        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            lk = feat.attribute(idx_link)
            
            # Use existing attribute or fallback
            zh_val = feat.attribute(idx_zh)
            if zh_val in [None, QVariant()]: zh_val = fallback_zh.get(lk, 0.0)
            
            bsf_val = feat.attribute(idx_bld)
            if bsf_val in [None, QVariant()]: bsf_val = fallback_bsf.get(lk, 0.0)

            try:
                bsf = float(bsf_val)
                zh = float(zh_val)
            except (ValueError, TypeError):
                bsf, zh = 0.0, 0.0
            
            # Decision Matrix based on Stewart & Oke (2012) and Davenport-Wieringa
            if zh < 3:
                if bsf < 10:   cls, z0 = 3, 0.03
                elif bsf < 20: cls, z0 = 4, 0.10
                elif bsf < 40: cls, z0 = 5, 0.25
                else:          cls, z0 = 6, 0.50
            elif zh < 10:
                if bsf < 10:   cls, z0 = 4, 0.10
                elif bsf < 20: cls, z0 = 5, 0.25
                elif bsf < 40: cls, z0 = 6, 0.50
                else:          cls, z0 = 7, 1.00
            elif zh < 25:
                if bsf < 10:   cls, z0 = 5, 0.25
                elif bsf < 20: cls, z0 = 6, 0.50
                elif bsf < 40: cls, z0 = 7, 1.00
                else:          cls, z0 = 8, 2.00
            else: # zh >= 25
                if bsf < 10:   cls, z0 = 6, 0.50
                elif bsf < 20: cls, z0 = 7, 1.00
                else:          cls, z0 = 8, 2.00

            # Fallback for very low values
            if zh < 0.5 and bsf < 1:
                cls, z0 = 2, 0.005

            layer.changeAttributeValue(feat.id(), idx_dst, cls)
            if idx_z0 != -1:
                layer.changeAttributeValue(feat.id(), idx_z0, z0)
            
            processed += 1

        layer.commitChanges()
        return processed
