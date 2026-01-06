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

            # 4. Stima Spaziatura Alberi (Tree Spacing) via Tree Cover Density o Fallback
            log_local("Analisi copertura vegetale per stima spaziatura alberi...")
            tree_spacing_map = {}
            
            # D_tree: diametro medio chioma assunto (10m per LCZ A/B)
            D_tree = 10.0
            
            # PRIORITY 1: Use Copernicus Tree Cover Density (TCD) if available
            tcd_path = os.path.join(self.dm.get_project_dir(), self.dm.get_data_dir_name(), "copernicus_hrl", "tcd_10m.tif")
            canopy_path = os.path.join(self.dm.get_project_dir(), self.dm.get_data_dir_name(), "unified", "canopy_height_10m.tif")
            
            if os.path.exists(tcd_path):
                try:
                    log_local("📊 Utilizzo Tree Cover Density (TCD) per spaziatura alberi...")
                    res_tcd_stats = processing.run("native:zonalstatisticsfb", {
                        'INPUT': layer,
                        'INPUT_RASTER': tcd_path,
                        'COLUMN_PREFIX': '_tcd_',
                        'STATISTICS': [2],  # Mean
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    
                    tcd_layer = res_tcd_stats['OUTPUT']
                    idx_tcd_mean = tcd_layer.fields().indexFromName('_tcd_mean')
                    idx_tcd_link = tcd_layer.fields().indexFromName('_link_id')
                    
                    for f in tcd_layer.getFeatures():
                        lk = f.attribute(idx_tcd_link)
                        tcd_mean = f.attribute(idx_tcd_mean) or 0
                        
                        if tcd_mean > 5:  # Soglia minima copertura (5%)
                            # Formula Stewart & Oke: W = D_tree / sqrt(TCD/100)
                            # TCD è già in percentuale (0-100)
                            try:
                                w_tree = D_tree / math.sqrt(tcd_mean / 100.0)
                                tree_spacing_map[lk] = max(2.0, w_tree)
                            except:
                                tree_spacing_map[lk] = 10.0
                        else:
                            tree_spacing_map[lk] = 200.0  # Spaziatura infinita (nessun albero)
                    
                    log_local(f"✓ TCD: spaziatura calcolata per {len([v for v in tree_spacing_map.values() if v < 200])} celle con alberi.")
                except Exception as ex:
                    log_local(f"Avviso: Errore TCD, fallback a metodo canopy mask: {str(ex)}", Qgis.Warning)
                    tree_spacing_map = {}  # Reset to trigger fallback
            
            # PRIORITY 2: Fallback to canopy height binary mask (original method)
            if not tree_spacing_map and os.path.exists(canopy_path):
                try:
                    log_local("Fallback: utilizzo maschera binaria canopy height...")
                    # Creiamo maschera binaria alberi (> 2m)
                    res_mask = processing.run("gdal:rastercalculator", {
                        'INPUT_A': canopy_path, 'BAND_A': 1,
                        'FORMULA': 'A > 2.0',
                        'RTYPE': 1,  # Byte
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    mask_path = res_mask['OUTPUT']
                    
                    # Conteggio pixel totali e pixel alberi per cella
                    res_stats = processing.run("native:zonalstatisticsfb", {
                        'INPUT': layer, 
                        'INPUT_RASTER': mask_path, 
                        'COLUMN_PREFIX': '_tr_', 
                        'STATISTICS': [0, 1],  # Count and Sum
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    
                    stats_layer = res_stats['OUTPUT']
                    idx_sum = stats_layer.fields().indexFromName('_tr_sum')
                    idx_cnt = stats_layer.fields().indexFromName('_tr_count')
                    idx_tmp_link = stats_layer.fields().indexFromName('_link_id')
                    
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
                            tree_spacing_map[lk] = 200.0  # Spaziatura infinita (nessun albero)
                except Exception as ex:
                    log_local(f"Avviso: Errore nel calcolo spaziatura alberi: {str(ex)}", Qgis.Warning)

            # 4b. Calcolo Altezza Media Canopy per Cella (per AR vegetazionale)
            log_local("Calcolo altezza media vegetazione per aree naturali...")
            canopy_height_map = {}
            if os.path.exists(canopy_path):
                try:
                    res_canopy_stats = processing.run("native:zonalstatisticsfb", {
                        'INPUT': layer,
                        'INPUT_RASTER': canopy_path,
                        'COLUMN_PREFIX': '_ch_',
                        'STATISTICS': [2],  # Mean
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    canopy_stats_layer = res_canopy_stats['OUTPUT']
                    idx_ch_mean = canopy_stats_layer.fields().indexFromName('_ch_mean')
                    idx_ch_link = canopy_stats_layer.fields().indexFromName('_link_id')
                    
                    for f in canopy_stats_layer.getFeatures():
                        lk = f.attribute(idx_ch_link)
                        ch_mean = f.attribute(idx_ch_mean)
                        if ch_mean is not None and str(ch_mean) not in ('NULL', ''):
                            canopy_height_map[lk] = float(ch_mean)
                        else:
                            canopy_height_map[lk] = 0.0
                except Exception as ex:
                    log_local(f"Avviso: Errore nel calcolo altezza canopy: {str(ex)}", Qgis.Warning)

            # 5. Elaborazione Celle
            layer.startEditing()
            processed = 0
            count_valid_ar = 0
            total_spacings_found = 0
            
            log_local(f"Analisi spaziale su {layer.featureCount()} celle...")
            
            for feat in layer.getFeatures():
                zh = feat.attribute(idx_zh) or 0
                lk = feat.attribute(idx_link)
                
                if float(zh) <= 0:
                    # NUOVO: Per aree senza edifici, calcoliamo AR vegetazionale
                    # usando altezza canopy e spaziatura alberi
                    w_tree = tree_spacing_map.get(lk, 200.0)
                    canopy_h = canopy_height_map.get(lk, 0.0)
                    
                    if canopy_h > 0.5 and w_tree < 200.0:
                        # AR vegetazionale = Altezza alberi / Spaziatura
                        # Permette di distinguere:
                        # - LCZ A (boschi densi): AR > 1 (alberi alti e ravvicinati)
                        # - LCZ B (alberi sparsi): AR 0.25-0.75
                        # - LCZ C (arbusti): AR 0.25-1.0
                        ar = canopy_h / w_tree
                    else:
                        # LCZ D, E, F, G: superfici piatte (AR < 0.1)
                        ar = 0.0
                    
                    layer.changeAttributeValue(feat.id(), idx_ar, round(min(10.0, ar), 2))
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
                    
                    # NUOVO: Raccogliamo TUTTE le distanze ai vicini, non solo la minima
                    # Questo evita che edifici isolati con 1 vicino attaccato abbiano AR altissimo
                    neighbor_distances = []
                    for n_id in nearest_ids:
                        if n_id == b_feat.id(): continue
                        n_geom_metric = bld_geom_cache.get(n_id)
                        if not n_geom_metric: continue
                        
                        dist = b_geom_metric.distance(n_geom_metric)
                        if dist > 0.5 and dist < 100.0:  # Range urbano realistico: 0.5m - 100m
                            neighbor_distances.append(max(2.0, dist))
                    
                    # Usa la MEDIA delle distanze ai vicini (più rappresentativa della distanza minima)
                    if neighbor_distances:
                        avg_dist = sum(neighbor_distances) / len(neighbor_distances)
                        cell_spacings.append(avg_dist)
                
                # Calcolo Finale AR
                # 1. Spaziatura Edifici - usa la mediana delle spaziature medie per cella
                w_bld = 200.0
                if cell_spacings:
                    median_w = statistics.median(cell_spacings)
                    # Imponiamo un minimo di 5m per evitare AR esagerati (edifici attaccati)
                    w_bld = max(5.0, median_w)
                
                # 2. Spaziatura Alberi (lk già definito all'inizio del loop)
                w_tree = tree_spacing_map.get(lk, 200.0)
                
                # 3. Spaziatura per AR: In aree URBANE (con edifici), usa SOLO w_bld
                # La logica precedente (min(w_bld, w_tree)) gonfiava AR quando c'erano alberi
                # tra gli edifici. Per le aree urbane, l'AR è H_edificio/W_tra_edifici.
                if cell_spacings:
                    # Abbiamo edifici → usa spaziatura edifici
                    w_final = w_bld
                else:
                    # Nessun edificio trovato nella cella → fallback a tree spacing
                    w_final = w_tree
                
                # AR = H / W
                if w_final < 200.0:
                    ar = float(zh) / w_final
                    # CAP: Aspect ratio massimo realistico per aree urbane = 3.0
                    # (corrisponde a canyon stretto: edifici 15m alti, strada 5m larga)
                    ar = min(3.0, ar)
                    count_valid_ar += 1
                    if cell_spacings: total_spacings_found += len(cell_spacings)
                else:
                    # Elementi isolati: AR molto basso
                    ar = float(zh) / 100.0 if float(zh) > 0 else 0.0
                
                layer.changeAttributeValue(feat.id(), idx_ar, round(ar, 2))
                processed += 1
                
            # Diagnostic: how many used building spacing vs tree spacing
            log_local(f"Debug: Celle urbane processate: {count_valid_ar} (con distanze edifici: {total_spacings_found})")
            layer.commitChanges()
            log_local(f"Debug: Distanze misurate in totale: {total_spacings_found}")
            log_local(f"Debug: Celle con Aspect Ratio calcolato: {count_valid_ar}")
            log_local(f"Processo completato: {processed} celle.")
            return processed

        except Exception as e:
            log_local(f"Errore: {str(e)}\n{traceback.format_exc()}", Qgis.Critical)
            return 0
