# -*- coding: utf-8 -*-

import os
import json
from qgis.core import (
    Qgis, QgsVectorLayer, QgsProject, QgsFeatureRequest, 
    QgsCoordinateTransform, QgsGeometry
)
from qgis.PyQt.QtCore import QMetaType
import processing
from .base import LCZBaseProcessor

class AnthropogenicHeatProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        """Calculates parameters based on lookups or population data."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        # Critical: Ensure _link_id exists BEFORE any other operation
        # This prevents crashes in helper methods like _ensure_fractions
        idx_link = self._ensure_link_id(layer)

        # Ensure input fields exist (Fix for KeyError: -1)
        idx_bld = self._ensure_field(layer, 'building_frac')
        idx_imp = self._ensure_field(layer, 'impervious_frac')
        
        # Ensure output field exists (Fix for independent run)
        idx_dst = self._ensure_field(layer, 'anthro_heat')

        # Ensure we have the necessary Morphological Fractions (Atomicity)
        bsf_dynamic, isf_dynamic = self._ensure_fractions(layer, log_callback)

        if -1 in [idx_bld, idx_imp, idx_dst]:
            log_local("ERRORE: Campi building_frac, impervious_frac o anthro_heat non trovati nel layer.", Qgis.Critical)
            return 0

        base_dir = self.dm.get_project_dir()
        pop_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "population_10m.tif")

        # For Anthro Heat, try population zonal sum
        pop_data = {}
        if os.path.exists(pop_path):
            log_local("Integrazione dati popolazione per calcolo calore antropico...")
            res_pop = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': pop_path, 'COLUMN_PREFIX': '_tmp_pop_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            idx_pop = res_pop['OUTPUT'].fields().indexFromName('_tmp_pop_sum')
            idx_link = self._ensure_link_id(layer)
            idx_temp_link = res_pop['OUTPUT'].fields().indexFromName('_link_id')
            for f in res_pop['OUTPUT'].getFeatures():
                lk = f.attribute(idx_temp_link)
                v = f.attribute(idx_pop)
                if lk is not None: pop_data[lk] = v

        # --- Componente Traffico (Strade OSM) ---
        road_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "roads.gpkg")
        road_lengths = {}
        if os.path.exists(road_path):
            log_local("Integrazione reti stradali per calcolo traffico...")
            res_roads = processing.run("native:sumlinelengths", {
                'LINES': road_path, 'POLYGONS': layer, 'LEN_FIELD': 'road_len', 'COUNT_FIELD': 'road_count', 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            idx_len = res_roads['OUTPUT'].fields().indexFromName('road_len')
            idx_temp_link = res_roads['OUTPUT'].fields().indexFromName('_link_id')
            for f in res_roads['OUTPUT'].getFeatures():
                lk = f.attribute(idx_temp_link)
                v = f.attribute(idx_len)
                if lk is not None: road_lengths[lk] = v

        # --- Componente Industriale (E-PRTR/IED) ---
        ind_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "industry_points.gpkg")
        ind_weights = {}
        if os.path.exists(ind_path):
            log_local("Integrazione punti industriali per settore (E-PRTR/IED)...")
            
            # 1. Define Sector Map (Watts per site - Conservative benchmarks)
            # SCIENTIFIC BASIS: 
            # Benchmarks adapted from the sEEnergies Project (D5.1 Report) 
            # and Buhler et al. (2018) "Estimation of excess heat potentials".
            # Values represent the estimated total thermal waste (Watts) per facility.
            SECTOR_WEIGHTS = {
                'Energy sector': 50000000,                       # 50 MW (Refineries, Power Plants)
                'Production and processing of metals': 30000000, # 30 MW (Steel mills, Foundries)
                'Mineral industry': 15000000,                    # 15 MW (Cement, Glass, Ceramics)
                'Chemical industry': 20000000,                   # 20 MW (Petrochemicals, Pharma)
                'Waste and waste water management': 2000000,    # 2 MW
                'Paper and wood production': 5000000,            # 5 MW
                'Food and beverage': 2000000,                    # 2 MW
                'Other': 1000000                                 # 1 MW (Default proxy)
            }

            # 2. Assign weight to each point based on sector
            ind_layer = QgsVectorLayer(ind_path, "industry", "ogr")
            if ind_layer.isValid():
                ind_layer.startEditing()
                if ind_layer.fields().indexFromName('heat_weight') == -1:
                    from qgis.core import QgsField
                    # Fixed DeprecationWarning: use the standardized (name, type) constructor
                    ind_layer.dataProvider().addAttributes([QgsField("heat_weight", QMetaType.Double)])
                    ind_layer.updateFields()
                
                idx_sector = ind_layer.fields().indexFromName('eprtr_sectors')
                if idx_sector == -1: idx_sector = ind_layer.fields().indexFromName('sector')
                
                idx_site_id = ind_layer.fields().indexFromName('InspireSiteId')
                if idx_site_id == -1: idx_site_id = ind_layer.fields().indexFromName('siteId')
                if idx_site_id == -1: idx_site_id = ind_layer.fields().indexFromName('facilityId')
                
                idx_year = ind_layer.fields().indexFromName('Site_reporting_year')
                if idx_year == -1: idx_year = ind_layer.fields().indexFromName('year')
                
                idx_weight = ind_layer.fields().indexFromName('heat_weight')
                
                # 3. De-duplicate: Keep only the most recent report per site
                site_best_reports = {} # {site_id: (feat_id, year, weight)}
                
                if idx_sector != -1 and idx_weight != -1:
                    for f in ind_layer.getFeatures():
                        # Determine weight
                        sector_str = str(f.attribute(idx_sector) or "Other")
                        weight = SECTOR_WEIGHTS.get('Other')
                        for key, val in SECTOR_WEIGHTS.items():
                            if key.lower() in sector_str.lower():
                                weight = val
                                break
                        
                        ind_layer.changeAttributeValue(f.id(), idx_weight, weight)
                        
                        # De-duplication key
                        site_id = str(f.attribute(idx_site_id)) if idx_site_id != -1 else None
                        if not site_id or site_id == 'NULL':
                             # Fallback to site name + first 2 decimals of coords
                             name = str(f.attribute('siteName') or "Anon")
                             geom = f.geometry().asPoint()
                             site_id = f"{name}_{round(geom.x(),2)}_{round(geom.y(),2)}"
                        
                        year = 0
                        try: year = int(f.attribute(idx_year) or 0)
                        except: pass
                        
                        if site_id not in site_best_reports or year > site_best_reports[site_id][1]:
                            site_best_reports[site_id] = (f.id(), year, weight)
                
                ind_layer.commitChanges()

                # 4. Sum weights per grid cell (Updated: 150m influence radius redistributed to buildings)
                log_local(f"De-duplicati punti industriali: {len(site_best_reports)} siti unici rilevati.")
                log_local("Ridistribuzione calore industriale agli edifici nel raggio di 150m...")
                
                # We need to intersect 150m buffers of the BEST points with the grid cells
                best_feature_ids = [v[0] for v in site_best_reports.values()]
                
                transform_ind = QgsCoordinateTransform(ind_layer.crs(), layer.crs(), QgsProject.instance()) if ind_layer.crs() != layer.crs() else None
                
                # Iterate only de-duplicated features
                for feat_id in best_feature_ids:
                    ind_feat = ind_layer.getFeature(feat_id)
                    weight = float(ind_feat.attribute(idx_weight) or 0)
                    if weight <= 0: continue
                    
                    point_geom = ind_feat.geometry()
                    if transform_ind: point_geom.transform(transform_ind)
                    
                    # 150m buffer in project units (assuming meters)
                    buffer_geom = point_geom.buffer(150.0, 8)
                    
                    # Find all intersecting grid cells
                    affected_cells = []
                    total_b_area_in_range = 0.0
                    
                    request = QgsFeatureRequest().setFilterRect(buffer_geom.boundingBox())
                    for cell_feat in layer.getFeatures(request):
                        cell_geom = cell_feat.geometry()
                        if cell_geom.intersects(buffer_geom):
                            lk = cell_feat.attribute(idx_link)
                            
                            # Get BSF for this cell (dynamic or from layer)
                            bsf = float(cell_feat.attribute(idx_bld) or 0)
                            if bsf == 0 and lk in bsf_dynamic: bsf = bsf_dynamic[lk]
                            
                            cell_area = cell_geom.area()
                            b_area = (bsf / 100.0) * cell_area
                            
                            # Calculate intersection area to weight the influence? 
                            # User said "influence all buildings in 150m", 
                            # so we distribute total weight among all buildings found in that radius.
                            intersection = cell_geom.intersection(buffer_geom)
                            if intersection:
                                # We only count building area that is actually inside the buffer
                                # Approximation: BSF * intersection area
                                active_b_area = (bsf / 100.0) * intersection.area()
                                if active_b_area > 0:
                                    affected_cells.append({
                                        'link': lk,
                                        'b_area': active_b_area
                                    })
                                    total_b_area_in_range += active_b_area
                    
                    # Step B: Distribute weight
                    if total_b_area_in_range > 0:
                        for item in affected_cells:
                            share = (item['b_area'] / total_b_area_in_range) * weight
                            ind_weights[item['link']] = ind_weights.get(item['link'], 0.0) + share
                    else:
                        # Fallback: if no buildings in 150m, assign to the cell containing the point
                        res_cell = layer.getFeatures(QgsFeatureRequest().setFilterRect(point_geom.boundingBox()))
                        for c in res_cell:
                            if c.geometry().contains(point_geom):
                                lk = c.attribute(idx_link)
                                ind_weights[lk] = ind_weights.get(lk, 0.0) + weight
                                break

        # --- Componente Traffico Punti (ANAS / Proxy) ---
        traffic_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "traffic_points.gpkg")
        traffic_volumes = {}
        if os.path.exists(traffic_path):
            log_local("Integrazione volumi di traffico (ANAS/OSM Proxy)...")
            try:
                # CRITICO: Usiamo MEAN invece di SUM per evitare multi-counting (fungo nucleare stradale)
                res_traffic = processing.run("native:joinattributesbylocation", {
                    'INPUT': layer, 'JOIN': traffic_path, 'PREDICATE': [0], # Intersects
                    'SUMMARY_FIELDS': ['tgma'], 'SUMMARIES': [2], # 2 = MEAN
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                
                out_fields = res_traffic['OUTPUT'].fields()
                idx_traf = out_fields.indexFromName('tgma_mean')
                if idx_traf == -1: idx_traf = out_fields.indexFromName('tgma')
                
                idx_temp_link = out_fields.indexFromName('_link_id')
                
                if idx_traf != -1 and idx_temp_link != -1:
                    for f in res_traffic['OUTPUT'].getFeatures():
                        lk = f.attribute(idx_temp_link)
                        v = f.attribute(idx_traf)
                        if lk is not None: traffic_volumes[lk] = v
                else:
                    log_local(f"AVVISO: Join traffico incompleto. Index: {idx_traf}", Qgis.Warning)
            except Exception as ex:
                log_local(f"Errore join traffico: {str(ex)}", Qgis.Warning)

        # --- Componente Traffico Geometria (OSM Class Weights) ---
        # If ANAS is missing, we use the road class to weight the heat
        road_type_weights = {} # {link_id: max_multiplier}
        if os.path.exists(road_path):
            log_local("Analisi classi stradali OSM per pesatura calore...")
            r_layer = QgsVectorLayer(road_path, "roads", "ogr")
            if r_layer.isValid():
                # Map specific highway types to multipliers
                # Values adapted from Sailor (2011) and urban morphology proxies
                TYPE_MULTIPLIERS = {
                    'motorway': 4.0, 'trunk': 3.5,
                    'primary': 2.5, 'secondary': 1.8,
                    'tertiary': 1.2, 'residential': 0.8,
                    'service': 0.5, 'unclassified': 0.7
                }
                
                idx_h = r_layer.fields().indexFromName('highway')
                if idx_h == -1: idx_h = r_layer.fields().indexFromName('highway_type')
                
                if idx_h != -1:
                    # Spatial Join to find roads in cells
                    for feat in layer.getFeatures():
                        lk = feat.attribute(idx_link)
                        geom = feat.geometry()
                        # Request roads in this bounding box
                        request = QgsFeatureRequest().setFilterRect(geom.boundingBox())
                        max_m = 1.0
                        for road in r_layer.getFeatures(request):
                            if road.geometry().intersects(geom):
                                h_type = str(road.attribute(idx_h) or "").lower()
                                m = 1.0
                                for k, v in TYPE_MULTIPLIERS.items():
                                    if k in h_type:
                                        m = v; break
                                if m > max_m: max_m = m
                        road_type_weights[lk] = max_m

        # Prepare main loop
        layer.startEditing()
        processed = 0
        idx_link = self._ensure_link_id(layer, sanitize=False)
        
        # Final field verification before main loop
        if idx_link == -1:
            log_local("ERRORE: Impossibile creare o trovare _link_id nel layer di destinazione.", Qgis.Critical)
            return 0

        # Check for degree-based CRS (potential buffer explosion)
        is_degree = layer.crs().isGeographic()
        if is_degree:
            log_local("AVVERTENZA: Il layer è in gradi (WGS84). I calcoli di calore antropogenico potrebbero essere imprecisi.", Qgis.Warning)

        try:
            log_local(f"Inizio ciclo di calcolo su {layer.featureCount()} celle...")
            for feat in layer.getFeatures():
                lk = feat.attribute(idx_link)
                
                # Check if we use existing attributes or dynamic ones
                attr_bld = feat.attribute(idx_bld)
                attr_imp = feat.attribute(idx_imp)
                
                bsf = float(attr_bld or 0)
                isf = float(attr_imp or 0)
                
                # If layer values are 0/NULL but we have dynamic values, use them
                if bsf == 0 and lk in bsf_dynamic: bsf = bsf_dynamic[lk]
                if isf == 0 and lk in isf_dynamic: isf = isf_dynamic[lk]
                
                # 1. Base Built Component (BSF/ISF or Population)
                pop_sum = float(pop_data.get(lk, 0) or 0)
                if pop_sum > 0:
                    # Metabolic + Domestic Heat Proxy
                    # ~45W per person metabolics + ~50W domestic scaled by density
                    val_built = (pop_sum * 45) / 900.0 
                    val_built += (bsf * 0.4)
                else:
                    # Morphological proxy if population raster is missing
                    val_built = (bsf * 0.7) + (isf * 0.1)
                
                # 2. Traffic Component
                road_len = float(road_lengths.get(lk, 0) or 0)
                traffic_vol = float(traffic_volumes.get(lk, 0) or 0)
                road_m = float(road_type_weights.get(lk, 1.0) or 1.0)
                
                traffic_vol_m = (traffic_vol / 50000.0) if traffic_vol > 0 else 0.0
                final_traffic_m = max(road_m, (1.0 + traffic_vol_m))
                val_traffic = (road_len * 0.08) * final_traffic_m if road_len > 0 else 0
                
                # 3. Industrial Component
                val_industry = 0
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    cell_area = geom.area() or 10000.0
                    total_ind_heat_w = float(ind_weights.get(lk, 0) or 0)
                    if total_ind_heat_w > 0:
                        val_industry = total_ind_heat_w / cell_area
                        # PHYSICAL CAP: Localized hotspots cap
                        val_industry = min(val_industry, 1500.0)
                
                # Total Heat (W/m2)
                val = float(val_built or 0) + float(val_traffic or 0) + float(val_industry or 0)
                
                if idx_dst != -1:
                    layer.changeAttributeValue(feat.id(), idx_dst, round(val, 2))
                
                processed += 1
                if processed % 1000 == 0:
                    log_local(f"Processate {processed} celle...")

            # Move commit inside try to report exact errors
            if not layer.commitChanges():
                errs = layer.commitErrors()
                log_local(f"ERRORE COMMIT: {', '.join(errs)}", Qgis.Critical)
                layer.rollBack()
                return 0

        except Exception as e_loop:
            import traceback
            log_local(f"Errore imprevisto durante il calcolo: {str(e_loop)}", Qgis.Critical)
            log_local(traceback.format_exc(), Qgis.Critical)
            layer.rollBack()
            return 0
            
        log_local(f"Calcolo calore antropogenico completato: {processed} celle aggiornate.")
        return processed

    def _ensure_fractions(self, layer, log_callback=None):
        """Checks if BSF/ISF are present; if not, calculates them on-the-fly."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        idx_bld = self._ensure_field(layer, 'building_frac')
        idx_imp = self._ensure_field(layer, 'impervious_frac')
        # Robustly get link id - Avoid redundant sanitization here as it was done in process()
        idx_link = self._ensure_link_id(layer, sanitize=False)

        # Sample check: are values mostly zeros/NULL?
        needs_bld = True
        needs_imp = True
        for f in layer.getFeatures(QgsFeatureRequest().setLimit(10)):
            if f.attribute(idx_bld) is not None and float(f.attribute(idx_bld) or 0) > 0: needs_bld = False
            if f.attribute(idx_imp) is not None and float(f.attribute(idx_imp) or 0) > 0: needs_imp = False
        
        bsf_map = {}
        isf_map = {}

        if not (needs_bld or needs_imp):
            return bsf_map, isf_map

        log_local("⏳ BSF/ISF mancanti nel layer. Avvio calcolo dinamico (potrebbe richiedere più tempo)...")
        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        
        # 1. Building Fraction (BSF)
        if needs_bld:
            bld_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
            if os.path.exists(bld_path):
                log_local("⏳ Calcolo Building Surface Fraction (BSF) dai footprint edifici...")
                bld_layer = QgsVectorLayer(bld_path, "bld", "ogr")
                if bld_layer.isValid():
                    transform = QgsCoordinateTransform(bld_layer.crs(), layer.crs(), QgsProject.instance()) if bld_layer.crs() != layer.crs() else None
                    for feat in layer.getFeatures():
                        geom = feat.geometry()
                        cell_area = geom.area()
                        b_area = 0.0
                        request_geom = QgsGeometry(geom)
                        if transform:
                            inv = QgsCoordinateTransform(layer.crs(), bld_layer.crs(), QgsProject.instance())
                            request_geom.transform(inv)
                        
                        request = QgsFeatureRequest().setFilterRect(request_geom.boundingBox())
                        for bldg in bld_layer.getFeatures(request):
                            bg = bldg.geometry()
                            if transform: bg.transform(transform)
                            if bg.intersects(geom):
                                inter = bg.intersection(geom)
                                if inter: b_area += inter.area()
                        bsf_map[feat.attribute(idx_link)] = min(100.0, (b_area / cell_area) * 100)
                log_local(f"✓ BSF calcolato dinamicamente per {len(bsf_map)} celle")

        # 2. Impervious Fraction (ISF) - Using HRL
        if needs_imp:
            hrl_path = os.path.join(unified_dir, "imperviousness_10m.tif")
            if os.path.exists(hrl_path):
                log_local("⏳ Calcolo Impervious Surface Fraction (ISF) da raster impermeabilità...")
                res_hrl = processing.run("native:zonalstatisticsfb", {
                    'INPUT': layer, 'INPUT_RASTER': hrl_path, 'COLUMN_PREFIX': '_dyn_hrl_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                idx_hrl = res_hrl['OUTPUT'].fields().indexFromName('_dyn_hrl_mean')
                idx_temp_link = res_hrl['OUTPUT'].fields().indexFromName('_link_id')
                for f in res_hrl['OUTPUT'].getFeatures():
                    lk = f.attribute(idx_temp_link)
                    raw_hrl = float(f.attribute(idx_hrl) or 0)
                    b_f = bsf_map.get(lk, 0.0)
                    # HRL includes buildings, so ISF = HRL - BSF (Avoid double counting)
                    isf_map[lk] = max(0, raw_hrl - b_f)
                log_local(f"✓ ISF calcolato dinamicamente per {len(isf_map)} celle")

        return bsf_map, isf_map
