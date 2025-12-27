# -*- coding: utf-8 -*-

import os
import math
import processing
from qgis.core import (
    QgsRasterLayer, QgsFeatureRequest, Qgis,
    QgsProject, QgsGeometry, QgsField
)
from .base import LCZBaseProcessor

class RoughnessHeightProcessor(LCZBaseProcessor):
    def process(self, layer, target_path, log_callback=None):
        """
        Calcolo Geometric Mean Height of roughness elements (z_H).
        Segue standard Stewart & Oke (2012).
        """
        import traceback
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        try:
            base_dir = self.dm.get_project_dir()
            unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
            dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
            dtm_path = os.path.join(unified_dir, "dtm_10m.tif")

            if not os.path.exists(dsm_path) or not os.path.exists(dtm_path):
                log_local("DSM o DTM mancante", Qgis.Warning); return 0
            
            idx_link = self._ensure_link_id(layer)
            idx_zh = layer.fields().indexFromName('z_h')
            if idx_zh == -1:
                from qgis.core import QgsField
                from qgis.PyQt.QtCore import QVariant
                layer.dataProvider().addAttributes([QgsField('z_h', QVariant.Double)])
                layer.updateFields()
                idx_zh = layer.fields().indexFromName('z_h')

            # 1. Creiamo nDSM temporaneo (DSM - DTM)
            log_local("Fase 1: Analisi altezze differenziali (nDSM)...")
            
            # Use gdal:rastercalculator with Float32 (RTYPE 5)
            # A-B is height. We filter between 2.0 and 150.0 meters.
            res_ndsm = processing.run("gdal:rastercalculator", {
                'INPUT_A': dsm_path, 'BAND_A': 1,
                'INPUT_B': dtm_path, 'BAND_B': 1,
                'FORMULA': 'A - B',
                'RTYPE': 5,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            ndsm_path = res_ndsm['OUTPUT']

            # 2. Calcolo Media Geometrica (elementi validi: 2m < h < 150m)
            log_local("Fase 2: Calcolo Media Geometrica (esclusione outlier)...")
            
            # Formula robusta: 
            # log(A) solo se 2.0 < A < 150.0
            # Altrimenti restituiamo 0.0 (che log(1) farebbe 0, ma qui usiamo zero per la somma)
            # Nota: GDAL log è naturale (ln)
            res_log = processing.run("gdal:rastercalculator", {
                'INPUT_A': ndsm_path, 'BAND_A': 1,
                'FORMULA': 'log(numpy.where((A>2.0) & (A<150.0), A, 1.0))',
                'RTYPE': 5,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            log_ndsm_path = res_log['OUTPUT']

            # Estraiamo la somma dei log
            stats_sum = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': log_ndsm_path, 'COLUMN_PREFIX': '_logsum_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            # Contiamo i pixel validi (2m < h < 150m)
            res_mask = processing.run("gdal:rastercalculator", {
                'INPUT_A': ndsm_path, 'BAND_A': 1,
                'FORMULA': '(A>2.0) & (A<150.0)',
                'RTYPE': 5,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            mask_ndsm_path = res_mask['OUTPUT']
            
            stats_count = processing.run("native:zonalstatisticsfb", {
                'INPUT': stats_sum['OUTPUT'], 'INPUT_RASTER': mask_ndsm_path, 'COLUMN_PREFIX': '_cnt_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })

            temp_layer = stats_count['OUTPUT']
            idx_logsum = temp_layer.fields().indexFromName('_logsum_sum')
            idx_cnt = temp_layer.fields().indexFromName('_cnt_sum')
            idx_temp_link = temp_layer.fields().indexFromName('_link_id')

            zh_map = {}
            for feat in temp_layer.getFeatures():
                lk = feat.attribute(idx_temp_link)
                lsum = feat.attribute(idx_logsum)
                cnt = feat.attribute(idx_cnt)
                
                # Applichiamo la formula della media geometrica: exp(media(log))
                if lsum is not None and cnt is not None and cnt > 0:
                    try:
                        g_mean = math.exp(float(lsum) / float(cnt))
                        # Se il valore è assurdo (es. errore floating point), lo cappiamo a 150
                        zh_map[lk] = min(150.0, round(g_mean, 2))
                    except:
                        zh_map[lk] = 0.0
                else:
                    zh_map[lk] = 0.0

            layer.startEditing()
            processed = 0
            for feat in layer.getFeatures():
                lk = feat.attribute(idx_link)
                if lk in zh_map:
                    layer.changeAttributeValue(feat.id(), idx_zh, zh_map[lk])
                    processed += 1
            
            layer.commitChanges()
            log_local(f"Completato: {processed} celle aggiornate con Media Geometrica raffinata.")
            return processed

        except Exception as e:
            err = traceback.format_exc()
            log_local(f"Errore critico in zH: {str(e)}\n{err}", Qgis.Critical)
            return 0
