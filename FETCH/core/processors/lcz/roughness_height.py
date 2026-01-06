# -*- coding: utf-8 -*-

import os
import math
import processing
from qgis.core import (
    QgsRasterLayer, QgsFeatureRequest, Qgis,
    QgsProject, QgsGeometry, QgsField
)
from qgis.PyQt.QtCore import QMetaType
from .base import LCZBaseProcessor

class RoughnessHeightProcessor(LCZBaseProcessor):
    def process(self, layer, target_path, log_callback=None):
        """
        Calcolo Geometric Mean Height of roughness elements (z_H).
        Usa direttamente il layer vettoriale edifici e il raster chiome.
        """
        import traceback
        import numpy as np
        from osgeo import gdal, ogr
        
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        try:
            base_dir = self.dm.get_project_dir()
            unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
            canopy_path = os.path.join(unified_dir, "canopy_height_10m.tif")
            buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
            dtm_path = os.path.join(unified_dir, "dtm_10m.tif")

            if not os.path.exists(canopy_path) and not os.path.exists(buildings_path):
                log_local("Né il raster chiome né il vettoriale edifici sono presenti.", Qgis.Warning)
                return 0
            
            idx_link = self._ensure_link_id(layer)
            idx_zh = self._ensure_field(layer, 'z_h', QMetaType.Double)

            # 1. Creazione Raster Altezze Combinato (Temporary)
            log_local("Fase 1: Creazione mappa altezze (Edifici + Chiome)...")
            
            # Usiamo il DTM come riferimento per estensione e risoluzione
            dtm_ds = gdal.Open(dtm_path)
            if not dtm_ds:
                log_local("DTM non trovato per riferimento spaziale.", Qgis.Critical)
                return 0
                
            x_size, y_size = dtm_ds.RasterXSize, dtm_ds.RasterYSize
            geotransform = dtm_ds.GetGeoTransform()
            projection = dtm_ds.GetProjection()
            dtm_ds = None

            temp_heights_raster = os.path.join(unified_dir, "temp_roughness_height_map.tif")
            driver = gdal.GetDriverByName('GTiff')
            out_ds = driver.Create(temp_heights_raster, x_size, y_size, 1, gdal.GDT_Float32)
            out_ds.SetGeoTransform(geotransform)
            out_ds.SetProjection(projection)
            out_band = out_ds.GetRasterBand(1)
            out_band.Fill(0)

            # A. Rasterizzazione Edifici
            if os.path.exists(buildings_path):
                vector_ds = ogr.Open(buildings_path)
                if vector_ds:
                    v_layer = vector_ds.GetLayer()
                    # Cerca il campo altezza
                    h_attr = None
                    defn = v_layer.GetLayerDefn()
                    for i in range(defn.GetFieldCount()):
                        fn = defn.GetFieldDefn(i).GetName().lower()
                        if fn in ['building_height', 'height', 'h', 'h_mean', 'height_mean', 'quota_e_m']:
                            h_attr = defn.GetFieldDefn(i).GetName()
                            break
                    
                    if h_attr:
                        log_local(f"Rasterizzazione edifici usando campo: {h_attr}")
                        gdal.RasterizeLayer(out_ds, [1], v_layer, options=[f"ATTRIBUTE={h_attr}"])
                vector_ds = None

            # B. Integrazione Chiome (Prendiamo il MAX)
            temp_heights = out_band.ReadAsArray().astype(np.float32)
            if os.path.exists(canopy_path):
                log_local("Integrazione altezze chiome ETH...")
                c_ds = gdal.Open(canopy_path)
                if c_ds:
                    c_band = c_ds.GetRasterBand(1)
                    c_heights = c_band.ReadAsArray(buf_xsize=x_size, buf_ysize=y_size).astype(np.float32)
                    # Gestione NoData chiome
                    c_nodata = c_band.GetNoDataValue() or 255.0
                    c_heights[c_heights >= c_nodata] = 0
                    temp_heights = np.maximum(temp_heights, c_heights)
                    c_ds = None
            
            # Scriviamo il raster combinato
            out_band.WriteArray(temp_heights)
            out_ds = None 

            # 2. Calcolo Media Geometrica (elementi validi: h > 2m)
            log_local("Fase 2: Calcolo Media Geometrica (z_H)...")
            
            # Trasformiamo in LOG per la media geometrica
            res_log = processing.run("gdal:rastercalculator", {
                'INPUT_A': temp_heights_raster, 'BAND_A': 1,
                'FORMULA': 'log(numpy.where((A>2.0) & (A<150.0), A, 1.0))',
                'RTYPE': 5,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            # Somma log e Conteggio pixel validi
            stats_sum = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': res_log['OUTPUT'], 'COLUMN_PREFIX': '_logsum_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            res_mask = processing.run("gdal:rastercalculator", {
                'INPUT_A': temp_heights_raster, 'BAND_A': 1,
                'FORMULA': '(A>2.0) & (A<150.0)',
                'RTYPE': 5,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            stats_count = processing.run("native:zonalstatisticsfb", {
                'INPUT': stats_sum['OUTPUT'], 'INPUT_RASTER': res_mask['OUTPUT'], 'COLUMN_PREFIX': '_cnt_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })

            temp_layer = stats_count['OUTPUT']
            idx_logsum = temp_layer.fields().indexFromName('_logsum_sum')
            idx_cnt = temp_layer.fields().indexFromName('_cnt_sum')
            idx_tmp_link = temp_layer.fields().indexFromName('_link_id')

            zh_map = {}
            for feat in temp_layer.getFeatures():
                lk = feat.attribute(idx_tmp_link)
                lsum = feat.attribute(idx_logsum) or 0
                cnt = feat.attribute(idx_cnt) or 0
                
                if cnt > 0:
                    try:
                        g_mean = math.exp(float(lsum) / float(cnt))
                        zh_map[lk] = min(150.0, round(g_mean, 2))
                    except: zh_map[lk] = 0.0
                else: zh_map[lk] = 0.0

            layer.startEditing()
            processed = 0
            for feat in layer.getFeatures():
                lk = feat.attribute(idx_link)
                if lk in zh_map:
                    layer.changeAttributeValue(feat.id(), idx_zh, zh_map[lk])
                    processed += 1
            
            layer.commitChanges()
            if os.path.exists(temp_heights_raster): os.remove(temp_heights_raster)
            
            log_local(f"Completato: {processed} celle aggiornate con z_H basato su Edifici e Chiome.")
            return processed

        except Exception as e:
            err = traceback.format_exc()
            log_local(f"Errore critico in zH: {str(e)}\n{err}", Qgis.Critical)
            return 0
