# -*- coding: utf-8 -*-
"""
LCZ Final Classification Module - EXPERIMENTAL (v2.0)

Classifies each grid cell into a Local Climate Zone (LCZ) class based on 
calculated parameters using RMSEP (Root Mean Square Error Percentage) analysis.
Optimized sorting logic and RMSEP thresholds.
"""

import numpy as np
from qgis.core import QgsVectorLayer, QgsField, Qgis, QgsMessageLog, QgsGeometry, QgsSpatialIndex
from qgis.PyQt.QtCore import QMetaType
from collections import Counter

try:
    import statsmodels.tools.eval_measures as em
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

# Centralized constants
from ...constants import LCZMappings, FileNames, FolderNames, FieldNames


class LCZClassifierExperimental:
    """
    Classifies features into Local Climate Zones (Experimental v2.0).
    Uses RMSEP with improved sorting and thresholding.
    """
    
    # LCZ class definitions
    LCZ_CLASSES = LCZMappings.CLASSES
    LCZ_PARAMETERS = LCZMappings.PARAMETERS
    FIELD_MAPPING = LCZMappings.FIELD_TO_PARAM

    def __init__(self, parameters):
        self.parameters = {k: v for k, v in parameters.items() if v is not None}

    def _is_valid_for_class(self, lcz_class):
        building_fraction = self.parameters.get('building_surface_fraction')
        if building_fraction is None:
            return True
        
        threshold = 10
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            return building_fraction <= threshold
        else:
            return building_fraction > threshold

    def calculate_rmsep(self, lcz_class):
        params_definition = self.LCZ_PARAMETERS[lcz_class]
        if not self._is_valid_for_class(lcz_class):
            return float('inf'), 0, {}, len(self.parameters)

        valid_input_params = []
        target_class_values = []
        error_contributions = {}
        perfect_matches = 0
        available_params_count = len(self.parameters)

        for param_name, current_val in self.parameters.items():
            if param_name in params_definition:
                min_val, max_val = params_definition[param_name]
                if min_val <= current_val <= max_val:
                    perfect_matches += 1
                    error_contributions[param_name] = 0
                else:
                    target_val = min_val if max_val == float('inf') else (min_val + max_val) / 2
                    if target_val == 0:
                        error_contributions[param_name] = float('inf') if current_val != 0 else 0
                    else:
                        percentage_error = (current_val - target_val) / target_val
                        error_contributions[param_name] = percentage_error ** 2
                        valid_input_params.append(current_val)
                        target_class_values.append(target_val)

        if not valid_input_params:
            rmsep = 0 if perfect_matches > 0 else float('inf')
            if available_params_count == 0:
                rmsep = float('inf')
        else:
            valid_input_params = np.array(valid_input_params)
            target_class_values = np.array(target_class_values)
            try:
                non_zero_mask = target_class_values != 0
                if np.any(non_zero_mask) and HAS_STATSMODELS:
                    rmsep = em.rmspe(valid_input_params[non_zero_mask], target_class_values[non_zero_mask]) / 100
                elif np.any(non_zero_mask):
                    diff = (valid_input_params[non_zero_mask] - target_class_values[non_zero_mask]) / target_class_values[non_zero_mask]
                    rmsep = np.sqrt(np.mean(diff ** 2))
                else:
                    rmsep = float('inf')
            except Exception:
                rmsep = float('inf')

        return rmsep, perfect_matches, error_contributions, available_params_count

    def classify(self):
        """
        Classify into LCZ class using Balanced Score logic (v2.2).
        Weights statistical proximity (RMSEP) against parameter match count.
        """
        results = {}
        total_params_available = 0
        for lcz in self.LCZ_CLASSES.keys():
            rmsep, perfect_matches, error_contributions, available_params_count = self.calculate_rmsep(lcz)
            results[lcz] = {
                'rmsep': rmsep, 
                'perfect_matches': perfect_matches
            }
            if total_params_available == 0 and available_params_count > 0:
                total_params_available = available_params_count

        if total_params_available == 0:
            return {'lcz_class': 'N/D', 'rmsep': float('inf'), 'perfect_matches': 0, 'available_params': 0}

        # SORTING STRATEGY (v2.2 - Balanced Score):
        # We calculate a score where lower is better. 
        # Score = RMSEP - (Matches * Bonus)
        # Bonus = 0.15 (A 15% reduction in perceived error for each parameter that falls perfectly within the range)
        match_bonus = 0.15
        
        def calculate_score(vals):
            if vals['rmsep'] == float('inf'):
                return float('inf')
            return vals['rmsep'] - (vals['perfect_matches'] * match_bonus)

        sorted_results = sorted(
            results.items(),
            key=lambda item: calculate_score(item[1])
        )

        best_class_key, best_class_values = sorted_results[0]
        
        # Rigidity check (v2.2): threshold increased to 2.5 to allow more valid urban types.
        if best_class_values['rmsep'] == float('inf') or best_class_values['rmsep'] > 2.5:
            best_class_key = 'N/D'

        return {
            'lcz_class': best_class_key,
            'rmsep': best_class_values['rmsep'],
            'perfect_matches': best_class_values['perfect_matches'],
            'available_params': total_params_available
        }


class LCZClassificationProcessorExperimental:
    """
    Processor that applies Experimental LCZ classification (v2.0).
    """
    ESA_TO_LCZ = LCZMappings.ESA_TO_LCZ
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)
    
    def _apply_esa_correction(self, lcz_class, esa_class, impervious_frac=None):
        """
        Applies logic to reconcile the morphological classifier with ESA WorldCover.
        Fixes cases where land is incorrectly classified as water ('G').
        """
        # 1. Base case: Built-up stays built-up unless ESA says water
        if lcz_class in [str(i) for i in range(1, 11)]:
            if esa_class == 80: 
                return 'G'
            return lcz_class
            
        if esa_class is None or lcz_class == 'N/D': 
            return lcz_class
            
        suggested = self.ESA_TO_LCZ.get(esa_class)
        
        # 2. Safety: If it's classified as water ('G') but ESA says it's land
        if lcz_class == 'G' and esa_class != 80:
            if esa_class == 50: # Built-up
                return '9' # Default to Sparsely Built if we thought it was open water
            return suggested if suggested else 'D' # Fallback to Low Plants for other land types
            
        # 3. Standardization strategy
        if suggested is None: 
            return lcz_class
            
        if esa_class == 10: # Trees
            return lcz_class if lcz_class in ['A', 'B'] else 'A'
            
        if esa_class == 60: # Bare
            return 'E' if (impervious_frac and impervious_frac > 50) else 'F'
            
        if esa_class == 80: # Water
            return 'G'
            
        # 4. Natural class overriding
        return suggested if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G'] else lcz_class

    def process(self, layer, log_callback=None, apply_smoothing=True, **kwargs):
        import os
        import processing
        from qgis.core import QgsRasterLayer

        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        # Basic field Setup
        field_name = 'lcz_class'
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, QMetaType.QString, len=10)])
            layer.updateFields()
            idx = layer.fields().lookupField(field_name)
        
        # Add other fields (Simplified for experimental view)
        for f, t, l in [('lcz_vulnerability', QMetaType.QString, 20), ('lcz_rmsep', QMetaType.Double, 0), ('lcz_matches', QMetaType.Int, 0), ('lcz_esa_fix', QMetaType.QString, 20)]:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
                layer.updateFields()

        # Zonal Stats for ESA (Experimental version uses the same logic)
        base_dir = self.dm.get_project_dir()
        landuse_path = os.path.join(base_dir, self.dm.get_data_dir_name(), FolderNames.UNIFIED, FileNames.LANDUSE)
        esa_lookup = {}
        if os.path.exists(landuse_path):
            log_local("⏳ Calcolo ESA (Experimental)...")
            res = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer, 'INPUT_RASTER': landuse_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'esa_', 'STATISTICS': [9], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            for feat in res['OUTPUT'].getFeatures():
                val = feat.attribute(res['OUTPUT'].fields().indexFromName('esa_majority'))
                if val is not None and str(val) not in ('NULL', ''):
                    esa_lookup[feat.id()] = int(float(val))

        layer.startEditing()
        imp_idx = layer.fields().indexFromName('impervious_frac')
        
        for feature in layer.getFeatures():
            fid = feature.id()
            params = {}
            for f_src, p_name in LCZClassifierExperimental.FIELD_MAPPING.items():
                v = feature.attribute(f_src)
                params[p_name] = float(v) if (v is not None and str(v) not in ('NULL', '')) else None
            
            try:
                if any(v is not None for v in params.values()):
                    res = LCZClassifierExperimental(params).classify()
                    lcz = res['lcz_class']
                    
                    if esa_lookup and lcz not in ['N/D', 'ERRORE']:
                        imp = float(feature.attribute(imp_idx)) if (imp_idx != -1 and feature.attribute(imp_idx) is not None) else None
                        lcz = self._apply_esa_correction(lcz, esa_lookup.get(fid), imp)
                    
                    raw_rmsep = res['rmsep']
                    rmsep_val = None if (raw_rmsep == float('inf') or raw_rmsep != raw_rmsep) else float(raw_rmsep)
                    
                    layer.changeAttributeValue(fid, idx, lcz)
                    layer.changeAttributeValue(fid, layer.fields().indexFromName('lcz_rmsep'), rmsep_val)
                    layer.changeAttributeValue(fid, layer.fields().indexFromName('lcz_matches'), res['perfect_matches'])
                    layer.changeAttributeValue(fid, layer.fields().indexFromName('lcz_vulnerability'), LCZMappings.VULNERABILITY_MAPPING.get(lcz, 'Unknown'))
            except: pass
            
        layer.commitChanges()
        
        # Apply smoothing if requested
        if apply_smoothing:
            if log_callback:
                log_callback("🧹 Applicazione smoothing spaziale (v2 - Regola 7/9)...")
            self._apply_spatial_smoothing(layer, log_callback)
            
        return layer.featureCount()

    def _apply_spatial_smoothing(self, layer, log_callback=None):
        """Unified smoothing for v2."""
        from collections import Counter
        idx_class = layer.fields().indexFromName('lcz_class')
        idx_vuln = layer.fields().indexFromName('lcz_vulnerability')
        if idx_class == -1: return
        
        spatial_index = QgsSpatialIndex(layer.getFeatures())
        feature_dict = {}
        for feat in layer.getFeatures():
            feature_dict[feat.id()] = {
                'lcz': feat.attribute(idx_class),
                'geom': QgsGeometry(feat.geometry())
            }
        
        smoothed = 0
        updates = {}
        MIN_NEIGHBOR_AGREEMENT = 7
        
        for fid, data in feature_dict.items():
            cell_lcz = data['lcz']
            if cell_lcz in ['N/D', 'ERRORE', None]: continue
            
            bbox = data['geom'].boundingBox()
            bbox.grow(max(bbox.width(), bbox.height()) * 1.5)
            candidates = spatial_index.intersects(bbox)
            
            neighbor_classes = []
            for cand_id in candidates:
                cand_data = feature_dict.get(cand_id)
                if cand_data:
                    l = cand_data['lcz']
                    if l not in ['N/D', 'ERRORE', None]:
                        neighbor_classes.append(l)
            
            if not neighbor_classes: continue
            counter = Counter(neighbor_classes)
            maj_class, maj_count = counter.most_common(1)[0]
            if cell_lcz != maj_class and maj_count >= MIN_NEIGHBOR_AGREEMENT:
                updates[fid] = maj_class
                smoothed += 1
        
        if updates:
            layer.startEditing()
            for fid, new_lcz in updates.items():
                layer.changeAttributeValue(fid, idx_class, new_lcz)
                if idx_vuln != -1:
                    layer.changeAttributeValue(fid, idx_vuln, 
                        LCZMappings.VULNERABILITY_MAPPING.get(new_lcz, 'Unknown'))
            layer.commitChanges()
            if log_callback:
                log_callback(f"✨ Smoothing completato: {smoothed} celle rettificate.")
