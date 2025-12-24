# -*- coding: utf-8 -*-

import os
from qgis.core import Qgis
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
        pop_path = os.path.join(base_dir, "it_lcz_data", "unified", "population_10m.tif")

        # For Anthro Heat, try population zonal sum
        pop_data = {}
        if os.path.exists(pop_path):
            log_local("Integrazione dati popolazione per calcolo calore antropico...")
            res = processing.run("native:zonalstatisticsfb", {
                'INPUT': layer, 'INPUT_RASTER': pop_path, 'COLUMN_PREFIX': '_tmp_pop_', 'STATISTICS': [1], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            idx_pop = res['OUTPUT'].fields().indexFromName('_tmp_pop_sum')
            # Needs to map via _link_id or fid
            idx_link = self._ensure_link_id(layer)
            idx_temp_link = res['OUTPUT'].fields().indexFromName('_link_id')
            
            for f in res['OUTPUT'].getFeatures():
                lk = f.attribute(idx_temp_link)
                v = f.attribute(idx_pop)
                if lk is not None: pop_data[lk] = v

        layer.startEditing()
        processed = 0
        idx_link = self._ensure_link_id(layer)
        for feat in layer.getFeatures():
            lk = feat.attribute(idx_link)
            bsf = float(feat.attribute(idx_bld) or 0)
            isf = float(feat.attribute(idx_imp) or 0)
            
            pop_sum = float(pop_data.get(lk, 0) or 0)
            if pop_sum > 0:
                # Formula incorporating population density
                val = (pop_sum * 50) / 900.0 # Normalized by cell area proxy
                val += (bsf * 0.5)
            else:
                val = (bsf * 0.8) + (isf * 0.2)
            
            layer.changeAttributeValue(feat.id(), idx_dst, round(val, 2))
            processed += 1

        layer.commitChanges()
        return processed
