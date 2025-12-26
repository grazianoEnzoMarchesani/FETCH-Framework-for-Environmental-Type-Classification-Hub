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

        # --- Componente Industriale (E-PRTR) ---
        ind_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "industry_points.gpkg")
        ind_counts = {}
        if os.path.exists(ind_path):
            log_local("Integrazione punti industriali E-PRTR...")
            res_ind = processing.run("native:countpointsinpolygon", {
                'POINTS': ind_path, 'POLYGONS': layer, 'FIELD': 'ind_count', 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            idx_ind = res_ind['OUTPUT'].fields().indexFromName('ind_count')
            idx_temp_link = res_ind['OUTPUT'].fields().indexFromName('_link_id')
            for f in res_ind['OUTPUT'].getFeatures():
                lk = f.attribute(idx_temp_link)
                v = f.attribute(idx_ind)
                if lk is not None: ind_counts[lk] = v

        # --- Componente Traffico Punti (ANAS) ---
        traffic_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "traffic_points.gpkg")
        traffic_volumes = {}
        if os.path.exists(traffic_path):
            log_local("Integrazione volumi di traffico ANAS...")
            # We use zonal statistics to sum traffic volumes in the cell (if any points fall inside)
            # Assuming the field name in ANAS data is 'tgma' or 'volume'
            res_traffic = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': traffic_path, 'COLUMN_PREFIX': '_tmp_traf_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            }) if traffic_path.endswith('.tif') else \
            processing.run("native:joinattributesbylocation", {
                'INPUT': layer, 'JOIN': traffic_path, 'PREDICATE': [0], 'SUMMARY_FIELDS': ['tgma'], 'SUMMARIES': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            idx_traf = res_traffic['OUTPUT'].fields().indexFromName('tgma_sum')
            idx_temp_link = res_traffic['OUTPUT'].fields().indexFromName('_link_id')
            for f in res_traffic['OUTPUT'].getFeatures():
                lk = f.attribute(idx_temp_link)
                v = f.attribute(idx_traf)
                if lk is not None: traffic_volumes[lk] = v

        layer.startEditing()
        processed = 0
        idx_link = self._ensure_link_id(layer)
        for feat in layer.getFeatures():
            lk = feat.attribute(idx_link)
            bsf = float(feat.attribute(idx_bld) or 0)
            isf = float(feat.attribute(idx_imp) or 0)
            
            # 1. Base Built Component (BSF/ISF or Population)
            pop_sum = float(pop_data.get(lk, 0) or 0)
            if pop_sum > 0:
                val_built = (pop_sum * 45) / 900.0 # Standard metabolic/domestic proxy
                val_built += (bsf * 0.4)
            else:
                val_built = (bsf * 0.7) + (isf * 0.1)
            
            # 2. Traffic Component (OSM Roads + ANAS)
            road_len = float(road_lengths.get(lk, 0) or 0)
            traffic_vol = float(traffic_volumes.get(lk, 0) or 0)
            
            # If we have real traffic volume, we use it to scale the heat
            # Base logic: if traffic_vol is high, we boost the emission factor
            traffic_multiplier = 1.0 + (traffic_vol / 50000.0) if traffic_vol > 0 else 1.0
            val_traffic = road_len * 0.08 * traffic_multiplier if road_len > 0 else 0
            
            # 3. Industrial Component (Point sources)
            ind_count = int(ind_counts.get(lk, 0) or 0)
            val_industry = ind_count * 50.0 # Extra heat per industrial site
            
            val = val_built + val_traffic + val_industry
            
            layer.changeAttributeValue(feat.id(), idx_dst, round(val, 2))
            processed += 1

        layer.commitChanges()
        return processed
