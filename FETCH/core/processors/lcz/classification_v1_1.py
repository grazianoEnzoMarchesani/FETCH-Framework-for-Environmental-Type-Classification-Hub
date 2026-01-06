# -*- coding: utf-8 -*-
"""
LCZ Final Classification Module - WEIGHTED CONTEXTUAL (v1.1)

Classifies each grid cell into an LCZ class but considers the neighborhood
by weighting the central cell's parameters (2/10) and its 8 neighbors (1/10 each).
This acts as a "physical smoothing" of parameters before classification.
"""

import numpy as np
from qgis.core import QgsField, Qgis, QgsMessageLog, QgsGeometry, QgsSpatialIndex
from qgis.PyQt.QtCore import QMetaType
from .classification_standard import LCZClassifierStandard, LCZClassificationProcessorStandard

# Centralized constants
from ...constants import LCZMappings, FolderNames, FileNames

class LCZClassificationProcessorV1_1(LCZClassificationProcessorStandard):
    """
    Processor that applies Weighted Contextual LCZ classification (v1.1).
    Inherits from Standard processor to reuse LandCover correction logic.
    """
    
    def process(self, layer, log_callback=None, apply_smoothing=False, **kwargs):
        """
        Main processing logic for Weighted v1.1 classification.
        Note: apply_smoothing defaults to False for this version as requested.
        """
        import os
        from qgis.core import QgsFeatureRequest
        
        def log_local(msg, level=Qgis.Info):
            if log_callback:
                log_callback(msg)
            self.log(msg, level)
            
        log_local("🧪 Avvio classificazione LCZ WEIGHTED CONTEXTUAL (v1.1)...")
        if apply_smoothing:
             log_local("⚠ Nota: Lo smoothing post-classificazione è attivo (sconsigliato con v1.1).", Qgis.Warning)
        
        # 1. Field Setup (identical to standard)
        field_name = 'lcz_class'
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, QMetaType.QString, len=10)])
            layer.updateFields()
            idx = layer.fields().lookupField(field_name)
            
        # Add auxiliary fields
        for f, t, l in [
            ('lcz_vulnerability', QMetaType.QString, 20),
            ('lcz_rmsep', QMetaType.Double, 0),
            ('lcz_matches', QMetaType.Int, 0),
            ('lcz_esa_fix', QMetaType.QString, 50)
        ]:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
                layer.updateFields()

        # 2. Build Spatial Index and Cache Parameters
        log_local("⏳ Analisi vicinato e calcolo medie pesate...")
        spatial_index = QgsSpatialIndex(layer.getFeatures())
        
        # Cache all feature parameters and geometry
        feature_data = {}
        all_features = list(layer.getFeatures())
        param_fields = LCZMappings.FIELD_TO_PARAM # {field: param_name}
        
        for feat in all_features:
            params = {}
            for field_name_src, param_name in param_fields.items():
                f_idx = layer.fields().indexFromName(field_name_src)
                if f_idx != -1:
                    val = feat.attribute(f_idx)
                    params[param_name] = float(val) if (val is not None and str(val) not in ('NULL', '')) else None
            
            feature_data[feat.id()] = {
                'params': params,
                'geom': QgsGeometry(feat.geometry())
            }

        # 3. ESA Correction Setup
        landuse_path = self._get_landuse_raster_path()
        use_esa_correction = False
        esa_majority_lookup = {}
        if landuse_path and os.path.exists(landuse_path):
            esa_layer = self._compute_esa_majority_for_layer(layer, landuse_path, log_local)
            if esa_layer:
                esa_maj_idx = esa_layer.fields().indexFromName('esa_majority')
                if esa_maj_idx != -1:
                    for feat in esa_layer.getFeatures():
                        val = feat.attribute(esa_maj_idx)
                        if val is not None and str(val) not in ('NULL', ''):
                            try: esa_majority_lookup[feat.id()] = int(float(val))
                            except: pass
                    use_esa_correction = len(esa_majority_lookup) > 0

        # 4. Main Classification Loop with weighting
        layer.startEditing()
        processed_count = 0
        corrected_count = 0
        
        imp_idx = layer.fields().indexFromName('impervious_frac')
        
        # Get field indices for faster access
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')
        idx_rmsep = layer.fields().lookupField('lcz_rmsep')
        idx_matches = layer.fields().lookupField('lcz_matches')
        idx_esa_fix = layer.fields().lookupField('lcz_esa_fix')

        for fid, data in feature_data.items():
            center_params = data['params']
            if not any(v is not None for v in center_params.values()):
                continue
                
            # Find neighbors for 3x3 kernel
            bbox = data['geom'].boundingBox()
            bbox.grow(max(bbox.width(), bbox.height()) * 1.5)
            candidate_ids = spatial_index.intersects(bbox)
            
            # Calculate Weighted Parameters
            weighted_params = {}
            for param_name in center_params.keys():
                # Weights: Center = 2, Neighbors = 1
                total_weight = 0
                weighted_sum = 0
                
                # Check center weight
                c_val = center_params.get(param_name)
                if c_val is not None:
                    weighted_sum += c_val * 2
                    total_weight += 2
                
                # Check neighbors
                for n_id in candidate_ids:
                    if n_id == fid: continue
                    n_data = feature_data.get(n_id)
                    if n_data:
                        n_val = n_data['params'].get(param_name)
                        if n_val is not None:
                            weighted_sum += n_val * 1
                            total_weight += 1
                
                if total_weight > 0:
                    weighted_params[param_name] = weighted_sum / total_weight
                else:
                    weighted_params[param_name] = None

            # Classify using Weighted Parameters
            try:
                classifier = LCZClassifierStandard(weighted_params)
                result = classifier.classify()
                lcz_class = result['lcz_class']
                raw_rmsep = result['rmsep']
                rmsep_value = None if (raw_rmsep == float('inf') or raw_rmsep != raw_rmsep) else float(raw_rmsep)
                perfect_matches = result['perfect_matches']
                esa_fix_status = '-'
                
                if use_esa_correction and lcz_class not in ['N/D', 'ERRORE']:
                    esa_class = esa_majority_lookup.get(fid)
                    # We use the original impervious_frac of the CELL for SAFEST correction
                    imp_val = all_features[processed_count].attribute(imp_idx) # Actually need the feature by fid
                    # Let's find the feature in the list (or fetch it)
                    feat_obj = layer.getFeature(fid)
                    imp_frac = float(feat_obj.attribute(imp_idx)) if (imp_idx != -1 and feat_obj.attribute(imp_idx) is not None) else None
                    
                    original_class = lcz_class
                    lcz_class = self._apply_esa_correction(lcz_class, esa_class, imp_frac)
                    if lcz_class != original_class:
                        corrected_count += 1
                        esa_fix_status = f"{original_class} → {lcz_class}"
                
                vulnerability = LCZMappings.VULNERABILITY_MAPPING.get(lcz_class, 'Unknown/Other')
                
                layer.changeAttributeValue(fid, idx, lcz_class)
                layer.changeAttributeValue(fid, idx_vuln, vulnerability)
                layer.changeAttributeValue(fid, idx_rmsep, rmsep_value)
                layer.changeAttributeValue(fid, idx_matches, perfect_matches)
                layer.changeAttributeValue(fid, idx_esa_fix, esa_fix_status)
                processed_count += 1
                
            except Exception as e:
                self.log(f"Errore feature {fid}: {e}", Qgis.Warning)

        layer.commitChanges()
        
        # 5. Optional Smoothing (Not recommended but available)
        if apply_smoothing:
            log_local("🧹 Applicazione smoothing spaziale aggiuntivo...")
            self._apply_spatial_smoothing(layer, log_callback)
            
        return processed_count
