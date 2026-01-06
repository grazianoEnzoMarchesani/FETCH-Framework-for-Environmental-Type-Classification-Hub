# -*- coding: utf-8 -*-
import os
from qgis.core import Qgis
from qgis.PyQt.QtCore import QVariant
from .base import LCZBaseProcessor

class SurfaceAdmittanceProcessor(LCZBaseProcessor):
    def process(self, layer, target_path, log_callback=None):
        """
        High-fidelity Surface Admittance calculation.
        Uses Oke (1987) coefficients and ESA WorldCover classes.
        Formula: μ = Σ(Fraction_i * Admittance_i) / 100
        """
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        # 1. Ensure building_frac exists (BSF)
        idx_bld = layer.fields().indexFromName('building_frac')
        if idx_bld == -1:
            log_local("Campo building_frac mancante. Avvio calcolo frazioni...")
            from .surface_fractions import SurfaceFractionsProcessor
            frac_proc = SurfaceFractionsProcessor(self.dm)
            frac_proc.process(layer, target_path, log_callback)
            idx_bld = layer.fields().indexFromName('building_frac')

        # 2. Get ESA WorldCover path
        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
        
        if not os.path.exists(landuse_path):
            log_local("Raster Land Use (ESA) mancante. Impossibile procedere con l'alta fedeltà.", Qgis.Warning)
            return 0

        # 3. Scientific Coefficients (μ) - J m⁻² s⁻¹ᐟ² K⁻¹
        # Sources: 
        # - Stewart & Oke (2012): "Local Climate Zones for Urban Temperature Studies"
        # - Oke (1987): "Boundary Layer Climates"
        # These values represent the thermal inertia of the materials.
        COEFFS = {
            'building': 1800,    # Stewart & Oke (2012): LCZ 1-3 range 1500-2500
            'h_50': 1800,        # Stewart & Oke (2012): Paved surfaces/LCZ E range 1200-2500
            'h_10': 1300,        # Stewart & Oke (2012): LCZ A-B range 1000-1800 (Trees)
            'h_30': 1300,        # Stewart & Oke (2012): LCZ D range 1200-1600 (Low plants)
            'h_40': 1300,        # Stewart & Oke (2012): LCZ D range (Cropland)
            'h_20': 1100,        # Stewart & Oke (2012): LCZ C range (Scrubland)
            'h_60': 600,         # Oke (1987): Dry bare soil ~600, Wet ~2000
            'h_80': 1500,        # Oke (1987): Water surfaces ~1500-1600
        }
        
        # 4. Run Zonal Histogram for detailed ESA classes
        log_local("Analisi dettagliata classi ESA WorldCover per Admittance...")
        import processing
        res = processing.run("native:zonalhistogram", {
            'INPUT_VECTOR': layer, 'INPUT_RASTER': landuse_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'h_', 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        temp_layer = res['OUTPUT']
        
        temp_layer = res['OUTPUT']
        
        idx_dst = self._ensure_field(layer, 'admittance')
        idx_link = layer.fields().indexFromName('_link_id')
        if idx_link == -1: idx_link = self._ensure_link_id(layer)
        
        idx_temp_link = temp_layer.fields().indexFromName('_link_id')
        
        def get_count(f, name):
            idx = f.fields().indexFromName(name)
            if idx == -1: return 0
            v = f.attribute(idx)
            return float(v) if v is not None and v != QVariant() else 0

        # Mapping data
        admittance_data = {}
        for feat in temp_layer.getFeatures():
            lk = feat.attribute(idx_temp_link)
            if lk is None: continue
            
            # Sum pixels for normalization
            counts = {c: get_count(feat, c) for c in COEFFS.keys() if c != 'building'}
            total_pixels = sum(counts.values())
            
            if total_pixels == 0: continue
            
            # Admittance of the non-building part (weighted by ESA classes)
            esa_weighted_sum = sum(counts[c] * COEFFS[c] for c in counts)
            esa_avg_mu = esa_weighted_sum / total_pixels
            
            admittance_data[lk] = esa_avg_mu

        # 5. Final combine with BSF
        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            lk = feat.attribute(idx_link)
            bsf = float(feat.attribute(idx_bld) or 0)
            
            esa_mu = admittance_data.get(lk, 1000) # Fallback to soil
            
            # Combine Buildings (BSF) and ESA Classes (100-BSF)
            final_mu = (bsf * COEFFS['building'] + (100.0 - bsf) * esa_mu) / 100.0
            
            layer.changeAttributeValue(feat.id(), idx_dst, round(final_mu, 2))
            processed += 1

        layer.commitChanges()
        return processed
