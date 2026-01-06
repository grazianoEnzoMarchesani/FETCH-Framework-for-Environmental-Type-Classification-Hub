# -*- coding: utf-8 -*-
"""
LCZ Classification Module - FUZZY ARCHETYPE DISTANCE (v4.0)

Deterministic classification using Fuzzy Membership functions and 
weighted distance to morphological archetypes. Designed for complex 
urban territories (Italy-centric) with non-standard morphologies.

Key improvements:
- Gaussian/Sigmoid membership instead of binary ranges
- Weighted parameter influence
- Resilience to "out-of-range" parameters
- Higher resolution (30m) optimization
"""

import numpy as np
from qgis.core import QgsVectorLayer, QgsField, Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QMetaType

# Centralized constants
from ...constants import LCZMappings, FileNames, FolderNames, FieldNames


class LCZClassifierFAD:
    """
    Classifies features using Fuzzy-Archetype Distance logic.
    """
    
    LCZ_CLASSES = LCZMappings.CLASSES
    LCZ_PARAMETERS = LCZMappings.PARAMETERS
    FIELD_MAPPING = LCZMappings.FIELD_TO_PARAM
    
    # Weighting Strategy (Importance of each parameter)
    WEIGHTS = {
        'building_surface_fraction': 0.20,
        'height_roughness': 0.15,
        'pervious_surface_fraction': 0.15,
        'sky_view_factor': 0.12,
        'aspect_ratio': 0.10,
        'impervious_surface_fraction': 0.08,
        'surface_admittance': 0.07,
        'surface_albedo': 0.05,
        'terrain_roughness': 0.05,
        'anthropogenic_heat': 0.03
    }

    def __init__(self, parameters, calibration_overrides=None):
        """
        Args:
            parameters: dict with parameter names and values
            calibration_overrides: dict {lcz_id: {param_name: offset}}
        """
        self.parameters = {k: v for k, v in parameters.items() if v is not None}
        self.available_params_count = len(self.parameters)
        self.calibration_overrides = calibration_overrides or {}

    def _gaussian_membership(self, x, center, sigma):
        """
        Gaussian membership function: returns 1.0 at center, decays towards 0.
        """
        if sigma == 0: return 1.0 if x == center else 0.0
        return np.exp(-0.5 * ((x - center) / sigma) ** 2)

    def _sigmoid_membership(self, x, threshold, slope, direction='up'):
        """
        Sigmoid membership for open-ended parameters (e.g., Height).
        'up': 0 below threshold, 1 above.
        'down': 1 below threshold, 0 above.
        """
        if direction == 'up':
            return 1 / (1 + np.exp(-slope * (x - threshold)))
        else:
            return 1 / (1 + np.exp(slope * (x - threshold)))

    def calculate_scores(self):
        """
        Calculate fuzzy membership score for each LCZ class.
        returns: dict {lcz_class: total_score}
        """
        scores = {}
        
        # BSF Gate Logic: Separate Urban (1-10) from Natural (A-G)
        # Threshold: 10% Building Surface Fraction
        bsf = self.parameters.get('building_surface_fraction', 0)
        is_urban_area = bsf >= 10.0
        
        for lcz_id, ranges in self.LCZ_PARAMETERS.items():
            # Check if class matches the area type (Built vs Natural)
            is_built_class = lcz_id in LCZMappings.BUILT_CLASSES
            
            if is_urban_area and not is_built_class:
                continue # BSF >= 10% -> Only urban classes
            if not is_urban_area and is_built_class:
                continue # BSF < 10% -> Only natural classes

            class_score = 0
            total_weight = 0
            
            for param_name, (min_val, max_val) in ranges.items():
                if param_name not in self.parameters:
                    continue
                
                val = self.parameters[param_name]
                weight = self.WEIGHTS.get(param_name, 0.05)
                
                # Handle open-ended ranges
                if max_val == float('inf'):
                    # e.g., Height > 25m
                    mu = self._sigmoid_membership(val, min_val, slope=0.5 if param_name=='height_roughness' else 1.0)
                elif min_val == 0 and param_name == 'sky_view_factor' and lcz_id == 'A':
                     # Special case for Dense Trees SVF [0, 0.4]
                     mu = self._sigmoid_membership(val, 0.4, slope=-10, direction='down')
                else:
                    # shifted center logic
                    offset = self.calibration_overrides.get(lcz_id, {}).get(param_name, 0.0)
                    center = ((min_val + max_val) / 2) + offset
                    # sigma is set so that the boundary of the range has mu ~ 0.5
                    # 0.5 = exp(-0.5 * (width/2 / sigma)^2) -> sigma = width / (2 * sqrt(2 * ln(2)))
                    width = max(0.001, max_val - min_val)
                    sigma = width / 2.355 # approx FWHM logic
                    
                    # Increase tolerance for Italian context (15% wider sigma)
                    sigma *= 1.15
                    
                    mu = self._gaussian_membership(val, center, sigma)
                
                class_score += mu * weight
                total_weight += weight
            
            # Normalize score by weight sum
            scores[lcz_id] = class_score / total_weight if total_weight > 0 else 0
            
        return scores

    def classify(self):
        """
        Main classification entry point.
        """
        if self.available_params_count < 2:
            return {'lcz_class': 'N/D', 'score': 0, 'confidence': 0}

        scores = self.calculate_scores()
        
        # Filter for urban/natural logic if needed? 
        # (v3 uses building_surface_fraction > 10 for urban classes 1-10)
        bsf = self.parameters.get('building_surface_fraction', 0)
        
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_id, best_score = sorted_scores[0]
        
        # Confidence logic: difference between best and second best, or absolute score
        if len(sorted_scores) > 1:
            margin = best_score - sorted_scores[1][1]
            confidence = (best_score * 0.7 + margin * 0.3)
        else:
            confidence = best_score
            
        # Rejection threshold
        # Lowered from 0.4 to 0.25 to handle complex Italian territories
        if best_score < 0.25:
            return {'lcz_class': 'N/D', 'score': best_score, 'confidence': round(confidence, 2)}

        return {
            'lcz_class': best_id, 
            'score': round(best_score, 3), 
            'confidence': round(confidence, 2)
        }


class LCZClassificationProcessorFAD:
    """
    Processor applying the FAD methodology.
    """
    
    def __init__(self, data_manager):
        self.dm = data_manager

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def process(self, layer, log_callback=None, apply_smoothing=False, calibration_overrides=None):
        """
        apply_smoothing: False by default as FAD is contextually resilient.
        """
        import os
        import processing
        
        def log_local(msg, level=Qgis.Info):
            if log_callback:
                log_callback(msg, level)
            else:
                self.log(msg, level)

        log_local("🧪 Avvio classificazione FAD (Fuzzy-Archetype Distance v4.0)...")

        # --- Field Setup ---
        field_defs = [
            ('lcz_class', QMetaType.QString, 10),
            ('lcz_score', QMetaType.Double, 0),
            ('lcz_confidence', QMetaType.Double, 0),
            ('lcz_vulnerability', QMetaType.QString, 20)
        ]
        
        layer.startEditing()
        for f, t, l in field_defs:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
        layer.updateFields()
        
        idx_class = layer.fields().lookupField('lcz_class')
        idx_score = layer.fields().lookupField('lcz_score')
        idx_conf = layer.fields().lookupField('lcz_confidence')
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')

        processed = 0
        for feat in layer.getFeatures():
            params = {}
            for f_src, p_name in LCZMappings.FIELD_TO_PARAM.items():
                v = feat.attribute(f_src)
                params[p_name] = float(v) if (v is not None and str(v) not in ('NULL', '')) else None
            
            if any(v is not None for v in params.values()):
                res = LCZClassifierFAD(params, calibration_overrides=calibration_overrides).classify()
                lcz = res['lcz_class']
                
                layer.changeAttributeValue(feat.id(), idx_class, lcz)
                layer.changeAttributeValue(feat.id(), idx_score, res.get('score', 0))
                layer.changeAttributeValue(feat.id(), idx_conf, res.get('confidence', 0))
                layer.changeAttributeValue(feat.id(), idx_vuln, LCZMappings.VULNERABILITY_MAPPING.get(lcz, 'Unknown'))
                processed += 1
        
        layer.commitChanges()
        log_local(f"✓ Classificazione FAD completata: {processed} celle.")
        return processed
