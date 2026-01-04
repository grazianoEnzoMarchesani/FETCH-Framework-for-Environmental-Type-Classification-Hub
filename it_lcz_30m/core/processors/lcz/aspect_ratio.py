# -*- coding: utf-8 -*-

import os
import statistics
import traceback
from qgis.core import (
    Qgis, QgsProject, QgsSpatialIndex, QgsFeatureRequest, 
    QgsCoordinateTransform, QgsVectorLayer, QgsGeometry,
    QgsCoordinateReferenceSystem, NULL
)
from qgis.PyQt.QtCore import QMetaType
import processing
import math
from .base import LCZBaseProcessor

class AspectRatioProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        """
        Calcolo Aspect Ratio (H/W) tramite misurazione geometrica diretta.
        Risolto bug CRS: l'indice spaziale ora usa unità metriche coerenti.
        """
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        try:
            # 1. Setup Campi
            idx_link = self._ensure_link_id(layer)
            idx_ar = layer.fields().indexFromName('aspect_ratio')
            if idx_ar == -1:
                from qgis.core import QgsField
                layer.dataProvider().addAttributes([QgsField('aspect_ratio', QMetaType.Double)])
                layer.updateFields()
                idx_ar = layer.fields().indexFromName('aspect_ratio')

            idx_zh = layer.fields().indexFromName('z_h')
            # Cerchiamo building_frac solo come indicazione, non obbligatoria se z_h presente
            idx_bld = layer.fields().indexFromName('building_frac')
            
            # ATOMICITÀ: Controlliamo se z_h è effettivamente popolato
            is_zh_populated = False
            if idx_zh != -1:
                # Controlliamo un campione di feature per vedere se ci sono valori > 0
                for feat in layer.getFeatures(QgsFeatureRequest().setLimit(50)):
                    val = feat.attribute(idx_zh)
                    if val is not None and val != NULL and float(val) > 0:
                        is_zh_populated = True
                        break
            
            if idx_zh == -1 or not is_zh_populated:
                log_local("z_h (altezza media) mancante o non popolata. Calcolo automatico per atomicità...", Qgis.Info)
                from .roughness_height import RoughnessHeightProcessor
                RoughnessHeightProcessor(self.dm).process(layer, None, log_callback)
                # Ricarichiamo gli indici dei campi post-calcolo
                layer.updateFields()
                idx_zh = layer.fields().indexFromName('z_h')

            # 2. Reperimento Layer Edifici
            bld_layer = None
            for l in QgsProject.instance().mapLayers().values():
                if l.name() == "Edifici TUM LoD1":
                    bld_layer = l
                    break
            
            if not bld_layer:
                path = os.path.join(self.dm.get_project_dir(), self.dm.get_data_dir_name(), "unified", "buildings_lod1.gpkg")
                if os.path.exists(path):
                    bld_layer = QgsVectorLayer(path, "Edifici TUM LoD1", "ogr")
                    if bld_layer.isValid(): QgsProject.instance().addMapLayer(bld_layer)
            
            if not bld_layer or not bld_layer.isValid():
                log_local("Layer 'Edifici TUM LoD1' non trovato.", Qgis.Critical)
                return 0

            # 3. Preparazione CRS Metrico e Indice Spaziale
            # Forziamo tutto nel CRS della griglia (che è UTM/Metrico per il progetto FETCH)
            target_crs = layer.crs()
            if target_crs.isGeographic():
                target_crs = QgsCoordinateReferenceSystem("EPSG:32632") # Fallback safe

            bld_to_grid = QgsCoordinateTransform(bld_layer.crs(), target_crs, QgsProject.instance())
            grid_to_bld = QgsCoordinateTransform(layer.crs(), bld_layer.crs(), QgsProject.instance())

            log_local("Costruzione indice spaziale metrico per gli edifici...")
            # CRITICO: L'indice deve contenere geometrie già trasformate in metri
            spatial_index = QgsSpatialIndex()
            bld_geom_cache = {} # Cache per non ricalcolare trasformazioni
            
            count_bld = 0
            for b_feat in bld_layer.getFeatures():
                geom = b_feat.geometry()
                try: 
                    geom.transform(bld_to_grid)
                    # IMPORTANTE: Creiamo una copia della feature e impostiamo la geometria trasformata
                    # affinché l'indice contenga la posizione corretta nel CRS target.
                    b_feat.setGeometry(geom)
                    spatial_index.addFeature(b_feat)
                    bld_geom_cache[b_feat.id()] = QgsGeometry(geom)
                    count_bld += 1
                except: continue
            
            log_local(f"Indice creato con {count_bld} edifici.")

            # 4. Stima Spaziautra Alberi (Tree Spacing) via Raster
            log_local("Analisi copertura vegetale alta per stima spaziatura alberi...")
            tree_spacing_map = {}
            canopy_path = os.path.join(self.dm.get_project_dir(), self.dm.get_data_dir_name(), "unified", "canopy_height_10m.tif")
            
            if os.path.exists(canopy_path):
                try:
                    # Creiamo maschera binaria alberi (> 2m)
                    res_mask = processing.run("gdal:rastercalculator", {
                        'INPUT_A': canopy_path, 'BAND_A': 1,
                        'FORMULA': 'A > 2.0',
                        'RTYPE': 1, # Byte
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    mask_path = res_mask['OUTPUT']
                    
                    # Conteggio pixel totali e pixel alberi per cella
                    res_stats = processing.run("native:zonalstatisticsfb", {
                        'INPUT': layer, 
                        'INPUT_RASTER': mask_path, 
                        'COLUMN_PREFIX': '_tr_', 
                        'STATISTICS': [0, 1], # Count and Sum
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    
                    stats_layer = res_stats['OUTPUT']
                    idx_sum = stats_layer.fields().indexFromName('_tr_sum')
                    idx_cnt = stats_layer.fields().indexFromName('_tr_count')
                    idx_tmp_link = stats_layer.fields().indexFromName('_link_id')
                    
                    # D_tree: diametro medio chioma assunto (10m per LCZ A/B)
                    D_tree = 10.0
                    
                    for f in stats_layer.getFeatures():
                        lk = f.attribute(idx_tmp_link)
                        s = f.attribute(idx_sum) or 0
                        c = f.attribute(idx_cnt) or 1
                        
                        # Frazione copertura (0.0 - 1.0)
                        frac = float(s) / float(c) if c > 0 else 0
                        
                        if frac > 0.05: 
                            # Spaziatura centro-centro (Standard Stewart & Oke 2012):
                            # W = D / sqrt(F)
                            try:
                                w_tree = D_tree / math.sqrt(frac)
                                tree_spacing_map[lk] = max(2.0, w_tree)
                            except:
                                tree_spacing_map[lk] = 10.0
                        else:
                            tree_spacing_map[lk] = 200.0 # Spaziatura infinita (nessun albero)
                except Exception as ex:
                    log_local(f"Avviso: Errore nel calcolo spaziatura alberi: {str(ex)}", Qgis.Warning)

            # 5. Elaborazione Celle
            layer.startEditing()
            processed = 0
            count_valid_ar = 0
            total_spacings_found = 0
            
            log_local(f"Analisi spaziale su {layer.featureCount()} celle...")
            
            for feat in layer.getFeatures():
                zh = feat.attribute(idx_zh) or 0
                if float(zh) <= 0:
                    layer.changeAttributeValue(feat.id(), idx_ar, 0.0)
                    processed += 1
                    continue

                # Trova edifici nella cella (usando bounding box nel CRS edifici)
                cell_geom = feat.geometry()
                query_geom = QgsGeometry(cell_geom)
                try: query_geom.transform(grid_to_bld)
                except: pass
                
                request = QgsFeatureRequest().setFilterRect(query_geom.boundingBox())
                cell_buildings = list(bld_layer.getFeatures(request))
                
                cell_spacings = []
                for b_feat in cell_buildings:
                    # Recuperiamo la geometria metrica dalla cache
                    b_geom_metric = bld_geom_cache.get(b_feat.id())
                    if not b_geom_metric: continue
                    
                    # Cerca vicini nell'indice metrico
                    nearest_ids = spatial_index.nearestNeighbor(b_geom_metric, 11) # se stesso + 10
                    
                    min_dist = 999.0
                    for n_id in nearest_ids:
                        if n_id == b_feat.id(): continue
                        n_geom_metric = bld_geom_cache.get(n_id)
                        if not n_geom_metric: continue
                        
                        dist = b_geom_metric.distance(n_geom_metric)
                        if dist > 0.5 and dist < min_dist: # Soglia 0.5m per evitare errori di overlap
                            min_dist = dist
                    
                    if min_dist < 200.0: # Solo distanze urbane verosimili
                        # Applichiamo la soglia di 2m: se la fessura è < 2m, la consideriamo 2m
                        effective_dist = max(2.0, min_dist)
                        cell_spacings.append(effective_dist)
                
                # Calcolo Finale AR
                # 1. Spaziatura Edifici
                w_bld = 200.0
                if cell_spacings:
                    median_w = statistics.median(cell_spacings)
                    w_bld = max(2.0, median_w)
                
                # 2. Spaziatura Alberi
                lk = feat.attribute(idx_link)
                w_tree = tree_spacing_map.get(lk, 200.0)
                
                # 3. Spaziatura Integrata (la più densa vince)
                w_final = min(w_bld, w_tree)
                
                # AR = H / W
                if w_final < 200.0:
                    ar = float(zh) / w_final
                    count_valid_ar += 1
                    if cell_spacings: total_spacings_found += len(cell_spacings)
                else:
                    # Elementi isolati: AR molto basso
                    ar = float(zh) / 100.0 if float(zh) > 0 else 0.0
                
                layer.changeAttributeValue(feat.id(), idx_ar, round(min(10.0, ar), 2))
                processed += 1
                
            layer.commitChanges()
            log_local(f"Debug: Distanze misurate in totale: {total_spacings_found}")
            log_local(f"Debug: Celle con Aspect Ratio calcolato: {count_valid_ar}")
            log_local(f"Processo completato: {processed} celle.")
            return processed

        except Exception as e:
            log_local(f"Errore: {str(e)}\n{traceback.format_exc()}", Qgis.Critical)
            return 0
