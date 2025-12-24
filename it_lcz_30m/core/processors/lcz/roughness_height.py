# -*- coding: utf-8 -*-

import os
from qgis.core import Qgis
import processing
from .base import LCZBaseProcessor

class RoughnessHeightProcessor(LCZBaseProcessor):
    def process(self, layer, target_path, log_callback=None):
        """Calcolo geometric mean height of roughness elements (z_H)."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")

        if not os.path.exists(dsm_path) or not os.path.exists(dtm_path):
            log_local("DSM o DTM mancante", Qgis.Warning); return 0
        
        idx_link = self._ensure_link_id(layer)
        
        # We need Mean(DSM) - Mean(DTM) for each cell
        log_local("Fase 1: Analisi DTM...")
        self._calc_zonal_mean(layer, target_path, dtm_path, 'z_h', 'dtm', log_callback) # Temporarily store DTM mean in z_h
        
        log_local("Fase 2: Analisi DSM...")
        res = processing.run("native:zonalstatisticsfb", {
            'INPUT': layer, 'INPUT_RASTER': dsm_path, 'COLUMN_PREFIX': '_tmp_dsm_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        temp_layer = res['OUTPUT']
        idx_dst = layer.fields().indexFromName('z_h')
        idx_dsm = temp_layer.fields().indexFromName('_tmp_dsm_mean')
        idx_temp_link = temp_layer.fields().indexFromName('_link_id')
        
        dsm_map = {}
        for feat in temp_layer.getFeatures():
            lk = feat.attribute(idx_temp_link)
            val = feat.attribute(idx_dsm)
            if lk is not None and val is not None: dsm_map[lk] = val

        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            fid = feat.id()
            lk = feat.attribute(idx_link)
            if lk not in dsm_map: continue
            
            dtm_mean = feat.attribute('z_h')
            dsm_mean = dsm_map[lk]
            
            if dtm_mean is not None and dsm_mean is not None:
                try:
                    z_h = max(0, float(dsm_mean) - float(dtm_mean))
                    layer.changeAttributeValue(fid, idx_dst, round(z_h, 2))
                    processed += 1
                except: pass
        
        layer.commitChanges()
        return processed
