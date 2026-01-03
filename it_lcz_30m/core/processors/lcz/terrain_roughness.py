# -*- coding: utf-8 -*-

import os
import processing
from qgis.core import (
    QgsFeatureRequest, QgsVectorLayer, QgsCoordinateTransform, 
    QgsProject, QgsGeometry, QgsField, Qgis
)
from qgis.PyQt.QtCore import QVariant, QMetaType
from .base import LCZBaseProcessor

class TerrainRoughnessProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        idx_link = self._ensure_link_id(layer)
        idx_bld = layer.fields().indexFromName('building_frac')
        idx_zh = layer.fields().indexFromName('z_h')
        
        # Output fields
        idx_dst = self._ensure_field(layer, 'terrain_rough', QMetaType.Int) # Classification is Int
        idx_z0 = self._ensure_field(layer, 'z0_value', QMetaType.Double)

        # 1. Pre-fetch data if missing
        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
        canopy_path = os.path.join(unified_dir, "canopy_height_10m.tif")
        buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")

        # Check if fields are empty by looking at first few features
        is_zh_empty = True
        is_bsf_empty = True
        for feat in layer.getFeatures(QgsFeatureRequest().setLimit(50)):
            if feat.attribute(idx_zh) not in [None, QVariant()]: is_zh_empty = False
            if feat.attribute(idx_bld) not in [None, QVariant()]: is_bsf_empty = False
        
        fallback_zh = {}
        if is_zh_empty and os.path.exists(buildings_path) and os.path.exists(canopy_path):
            log_local("z_h vuoto, calcolo temporaneo da Edifici e Chiome...")
            from .roughness_height import RoughnessHeightProcessor
            # We can use the processor we just refactored
            proc = RoughnessHeightProcessor(self.dm)
            proc.process(layer, None, log_callback)
            
            # Re-fetch the newly calculated zh values
            idx_zh = layer.fields().indexFromName('z_h')
            for feat in layer.getFeatures():
                lk = feat.attribute(idx_link)
                val = feat.attribute(idx_zh)
                if val not in [None, QVariant()]:
                    fallback_zh[lk] = float(val)

        fallback_bsf = {}
        if is_bsf_empty and os.path.exists(buildings_path):
            log_local("building_frac vuoto, calcolo temporaneo dai vettori edifici...")
            bld_layer = QgsVectorLayer(buildings_path, "bld", "ogr")
            if bld_layer.isValid():
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
            log_local(f"Building fraction calcolato per {len(fallback_bsf)} celle.")

        # 1.3 Tree Fraction from Canopy Raster
        tree_frac_map = {}
        if os.path.exists(canopy_path):
            log_local("Calcolo frazione copertura alberi per rugosità...")
            try:
                res_mask = processing.run("gdal:rastercalculator", {
                    'INPUT_A': canopy_path, 'BAND_A': 1,
                    'FORMULA': 'A > 2.0',
                    'RTYPE': 1, # Byte
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                res_stats = processing.run("native:zonalstatisticsfb", {
                    'INPUT': layer, 'INPUT_RASTER': res_mask['OUTPUT'], 'COLUMN_PREFIX': '_tr_', 'STATISTICS': [0, 1], 'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                stats_layer = res_stats['OUTPUT']
                
                # Robust field lookup
                idx_sum = -1
                idx_cnt = -1
                for i, field in enumerate(stats_layer.fields()):
                    fname = field.name().lower()
                    if '_tr_' in fname:
                        if 'sum' in fname: idx_sum = i
                        elif 'count' in fname or 'cnt' in fname: idx_cnt = i
                
                idx_tmp_link = stats_layer.fields().indexFromName('_link_id')
                
                if idx_tmp_link != -1 and (idx_sum != -1 or idx_cnt != -1):
                    for f in stats_layer.getFeatures():
                        lk = f.attribute(idx_tmp_link)
                        s = f.attribute(idx_sum) if idx_sum != -1 else 0
                        c = f.attribute(idx_cnt) if idx_cnt != -1 else 1
                        if lk is not None:
                            tree_frac_map[lk] = (float(s or 0) / float(c or 1)) * 100 if c and c > 0 else 0
                else:
                    log_local("Campi statistiche zonali non trovati nell'output temporaneo.", Qgis.Warning)
            except Exception as e:
                log_local(f"Avviso: Errore nel calcolo tree_frac: {str(e)}", Qgis.Warning)

        # 2. Main Classification Logic
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
                tree_frac = float(tree_frac_map.get(lk, 0.0))
            except (ValueError, TypeError):
                bsf, zh, tree_frac = 0.0, 0.0, 0.0
            
            # Decisions based on Combined Fraction (Buildings + Trees)
            # This accounts for high-density trees (LCZ A) as much as high-density buildings
            comb_frac = bsf + tree_frac
            
            if zh < 3:
                if comb_frac < 10:   cls, z0 = 3, 0.03
                elif comb_frac < 20: cls, z0 = 4, 0.10
                elif comb_frac < 40: cls, z0 = 5, 0.25
                else:                cls, z0 = 6, 0.50
            elif zh < 10:
                if comb_frac < 10:   cls, z0 = 4, 0.10
                elif comb_frac < 20: cls, z0 = 5, 0.25
                elif comb_frac < 40: cls, z0 = 6, 0.50
                else:                cls, z0 = 7, 1.00
            elif zh < 25:
                if comb_frac < 10:   cls, z0 = 5, 0.25
                elif comb_frac < 20: cls, z0 = 6, 0.50
                elif comb_frac < 40: cls, z0 = 7, 1.00
                else:                cls, z0 = 8, 2.00
            else: # zh >= 25
                if comb_frac < 10:   cls, z0 = 6, 0.50
                elif comb_frac < 20: cls, z0 = 7, 1.00
                else:                cls, z0 = 8, 2.00

            # Fallback for very low values
            if zh < 0.5 and bsf < 1:
                cls, z0 = 2, 0.005

            layer.changeAttributeValue(feat.id(), idx_dst, cls)
            if idx_z0 != -1:
                layer.changeAttributeValue(feat.id(), idx_z0, z0)
            
            processed += 1

        layer.commitChanges()
        return processed
