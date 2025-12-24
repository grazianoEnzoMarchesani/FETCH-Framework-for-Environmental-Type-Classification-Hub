# -*- coding: utf-8 -*-

from .base import LCZBaseProcessor

class TerrainRoughnessProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        idx_bld = layer.fields().indexFromName('building_frac')
        idx_zh = layer.fields().indexFromName('z_h')
        idx_dst = layer.fields().indexFromName('terrain_rough')

        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            bsf = float(feat.attribute(idx_bld) or 0)
            zh = float(feat.attribute(idx_zh) or 0)
            
            val = 0
            if zh < 0.5: val = 2
            elif bsf < 10: val = 3
            elif bsf < 30: val = 4 if zh < 10 else 5
            elif bsf < 50: val = 6
            else: val = 7 if zh < 25 else 8
            
            layer.changeAttributeValue(feat.id(), idx_dst, round(val, 2))
            processed += 1

        layer.commitChanges()
        return processed
