# -*- coding: utf-8 -*-

from qgis.core import Qgis
from .base import LCZBaseProcessor

class AspectRatioProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        """Calcolo Aspect Ratio (H/W) using simplified building model."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        idx_bld = layer.fields().indexFromName('building_frac')
        idx_zh = layer.fields().indexFromName('z_h')
        idx_ar = layer.fields().indexFromName('aspect_ratio')
        
        if idx_bld == -1 or idx_zh == -1:
            log_local("BSF o z_H mancante. Calcolarli prima.", Qgis.Warning); return 0
            
        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            bsf = feat.attribute(idx_bld) or 0
            zh = feat.attribute(idx_zh) or 0
            
            bsf_dec = float(bsf) / 100.0 if bsf else 0
            if bsf_dec < 0.01: 
                ar = 0.0
            elif bsf_dec > 0.9:
                ar = 5.0
            else:
                # Aspect Ratio for urban canyon model
                ar = (float(zh) * bsf_dec) / (1.0 - bsf_dec)
            
            layer.changeAttributeValue(feat.id(), idx_ar, round(min(10.0, ar), 2))
            processed += 1
            
        layer.commitChanges()
        return processed
