# -*- coding: utf-8 -*-

import os
import json
from qgis.core import Qgis, QgsVectorLayer, QgsProject
import processing
from .base import LCZBaseProcessor

class AnthropogenicHeatProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        """Calculates parameters based on lookups or population data."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        idx_bld = layer.fields().indexFromName('building_frac')
        idx_imp = layer.fields().indexFromName('impervious_frac')
        idx_dst = layer.fields().indexFromName('anthro_heat')

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
                    from qgis.PyQt.QtCore import QVariant
                    # Fixed DeprecationWarning: use the standardized (name, type) constructor
                    ind_layer.dataProvider().addAttributes([QgsField("heat_weight", QVariant.Double)])
                    ind_layer.updateFields()
                
                idx_sector = ind_layer.fields().indexFromName('eprtr_sectors')
                if idx_sector == -1:
                    # Fallback check for alternate names or case-sensitivity
                    idx_sector = ind_layer.fields().indexFromName('sector')
                
                idx_weight = ind_layer.fields().indexFromName('heat_weight')
                
                if idx_sector != -1 and idx_weight != -1:
                    for f in ind_layer.getFeatures():
                        sector_str = str(f.attribute(idx_sector) or "Other")
                        # Match first part of sector string
                        weight = SECTOR_WEIGHTS.get('Other')
                        for key, val in SECTOR_WEIGHTS.items():
                            if key.lower() in sector_str.lower():
                                weight = val
                                break
                        ind_layer.changeAttributeValue(f.id(), idx_weight, weight)
                ind_layer.commitChanges()

                # 3. Sum weights per grid cell
                res_ind = processing.run("native:joinattributesbylocation", {
                    'INPUT': layer, 'JOIN': ind_layer, 'PREDICATE': [0], # Intersects
                    'SUMMARY_FIELDS': ['heat_weight'], 'SUMMARIES': [1], # Sum
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                
                # Check for standard summary field names
                out_fields = res_ind['OUTPUT'].fields()
                idx_ind_sum = out_fields.indexFromName('heat_weight_sum')
                if idx_ind_sum == -1:
                    # Some versions might use a different separator or just the field name
                    idx_ind_sum = out_fields.indexFromName('heat_weight')
                
                idx_temp_link = out_fields.indexFromName('_link_id')
                
                if idx_ind_sum != -1 and idx_temp_link != -1:
                    for f in res_ind['OUTPUT'].getFeatures():
                        lk = f.attribute(idx_temp_link)
                        v = f.attribute(idx_ind_sum)
                        if lk is not None: ind_weights[lk] = v
                else:
                    log_local(f"AVVISO: Join industriale incompleto. Sum index: {idx_ind_sum}, Link index: {idx_temp_link}", Qgis.Warning)

        # --- Componente Traffico Punti (ANAS) ---
        traffic_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "traffic_points.gpkg")
        traffic_volumes = {}
        if os.path.exists(traffic_path):
            log_local("Integrazione volumi di traffico ANAS...")
            try:
                # We use zonal statistics to sum traffic volumes in the cell (if any points fall inside)
                res_traffic = processing.run("native:joinattributesbylocation", {
                    'INPUT': layer, 'JOIN': traffic_path, 'PREDICATE': [0], 'SUMMARY_FIELDS': ['tgma'], 'SUMMARIES': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                
                out_fields = res_traffic['OUTPUT'].fields()
                idx_traf = out_fields.indexFromName('tgma_sum')
                if idx_traf == -1:
                    idx_traf = out_fields.indexFromName('tgma') # Fallback
                
                idx_temp_link = out_fields.indexFromName('_link_id')
                
                if idx_traf != -1 and idx_temp_link != -1:
                    for f in res_traffic['OUTPUT'].getFeatures():
                        lk = f.attribute(idx_temp_link)
                        v = f.attribute(idx_traf)
                        if lk is not None: traffic_volumes[lk] = v
                else:
                    log_local(f"AVVISO: Join traffico ANAS incompleto. Traf index: {idx_traf}, Link index: {idx_temp_link}", Qgis.Warning)
            except Exception as ex:
                log_local(f"Errore join traffico ANAS: {str(ex)}", Qgis.Warning)

        layer.startEditing()
        processed = 0
        idx_link = self._ensure_link_id(layer)
        
        # Final field verification before main loop
        if idx_link == -1:
            log_local("ERRORE: Impossibile creare o trovare _link_id nel layer di destinazione.", Qgis.Critical)
            return 0

        try:
            for feat in layer.getFeatures():
                lk = feat.attribute(idx_link)
                bsf = float(feat.attribute(idx_bld) or 0)
                isf = float(feat.attribute(idx_imp) or 0)
                
                # 1. Base Built Component (BSF/ISF or Population)
                # Metabolic + Domestic Heat Proxy
                # Based on Stewart & Oke (2012) ranges for built LCZs.
                pop_sum = float(pop_data.get(lk, 0) or 0)
                if pop_sum > 0:
                    # ~45W per person metabolics + ~50W domestic scaled by density
                    val_built = (pop_sum * 45) / 900.0 
                    val_built += (bsf * 0.4)
                else:
                    # Morphological proxy if population raster is missing
                    val_built = (bsf * 0.7) + (isf * 0.1)
                
                # 2. Traffic Component (OSM Roads + ANAS)
                # Based on Hohenberger et al. (2025) and Kühbacher et al. (2025) proxies.
                road_len = float(road_lengths.get(lk, 0) or 0)
                traffic_vol = float(traffic_volumes.get(lk, 0) or 0)
                
                # traffic_vol is the AADT scaled field 'tgma'
                # 50,000 AADT is used as a normalization factor for the multiplier
                traffic_multiplier = 1.0 + (traffic_vol / 50000.0) if traffic_vol > 0 else 1.0
                val_traffic = road_len * 0.08 * traffic_multiplier if road_len > 0 else 0
                
                # 3. Industrial Component (Point sources)
                # Summed heat (W) / Cell Area (m^2)
                # Scientific reference: Buhler et al. (2018) mapping method.
                cell_area = feat.geometry().area() or 10000.0
                total_ind_heat_w = float(ind_weights.get(lk, 0) or 0)
                val_industry = total_ind_heat_w / cell_area if total_ind_heat_w > 0 else 0
                
                # PHYSICAL CAP: Ensure cell average doesn't exceed 1500 W/m2 
                # to prevent instability in climatic models while allowing for heavy hotspots.
                # Localized industrial hotspots can reach 500-1000 W/m2 (Sailor, 2011).
                val_industry = min(val_industry, 1500.0)
                
                val = val_built + val_traffic + val_industry
                
                layer.changeAttributeValue(feat.id(), idx_dst, round(val, 2))
                processed += 1
        except Exception as e_loop:
            import traceback
            log_local(f"Errore critico durante il ciclo di calcolo: {str(e_loop)}", Qgis.Critical)
            log_local(traceback.format_exc(), Qgis.Critical)
            layer.rollBack()
            return processed

        layer.commitChanges()
        return processed
