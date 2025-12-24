# -*- coding: utf-8 -*-

from .base import LCZBaseProcessor

class SurfaceAdmittanceProcessor(LCZBaseProcessor):
    def process(self, layer, log_callback=None):
        idx_bld = layer.fields().indexFromName('building_frac')
        idx_imp = layer.fields().indexFromName('impervious_frac')
        idx_per = layer.fields().indexFromName('pervious_frac')
        idx_dst = layer.fields().indexFromName('admittance')

        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            bsf = float(feat.attribute(idx_bld) or 0)
            isf = float(feat.attribute(idx_imp) or 0)
            psf = float(feat.attribute(idx_per) or 0)
            
            # Weighted average admittance
            val = (bsf * 2000 + isf * 1800 + psf * 1100) / 100.0
            
            layer.changeAttributeValue(feat.id(), idx_dst, round(val, 2))
            processed += 1

        layer.commitChanges()
        return processed
