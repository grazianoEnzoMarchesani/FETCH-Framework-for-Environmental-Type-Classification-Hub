# -*- coding: utf-8 -*-
"""
CalibrationManager - Handles local urban morphology adaptation.
Learns from high-confidence samples to shift theoretical ranges.
"""

import json
import os
import numpy as np
from ...constants import LCZMappings

class CalibrationManager:
    def __init__(self, project_path=None):
        self.project_path = project_path
        self.calibration_data = {}
        
    def calculate_calibration(self, layer, confidence_threshold=0.8):
        """
        Analyze a classified layer and calculate local offsets for each LCZ class.
        """
        from qgis.core import QgsFeatureRequest
        
        # 1. Group parameters by class for high-confidence samples
        stats = {} # {lcz_id: {param_name: [values]}}
        
        fields = layer.fields()
        lcz_idx = fields.indexOf('lcz_class')
        conf_idx = fields.indexOf('lcz_confidence')
        
        if lcz_idx == -1 or conf_idx == -1:
            return False, "Layer non contiene i campi necessari (lcz_class, lcz_confidence)"
            
        # Param mapping from constants
        param_to_field = {v: k for k, v in LCZMappings.FIELD_TO_PARAM.items()}
        
        # Iterating over features
        for feat in layer.getFeatures(QgsFeatureRequest()):
            # Safe extraction of attributes (avoiding QVariant issues)
            raw_conf = feat.attribute(conf_idx)
            raw_lcz = feat.attribute(lcz_idx)
            
            # Handle NULL or None
            if raw_conf is None or str(raw_conf) == 'NULL': continue
            if raw_lcz is None or str(raw_lcz) == 'NULL': continue
            
            try:
                conf = float(raw_conf)
                lcz_id = str(raw_lcz)
            except (ValueError, TypeError):
                continue
            
            if conf < confidence_threshold or lcz_id == 'N/D':
                continue
                
            if lcz_id not in stats:
                stats[lcz_id] = {p: [] for p in LCZMappings.FIELD_TO_PARAM.values()}
                
            for param_name, field_name in param_to_field.items():
                val = feat.attribute(field_name)
                # Check for NULL
                if val is not None and str(val) != 'NULL':
                    try:
                        stats[lcz_id][param_name].append(float(val))
                    except (ValueError, TypeError):
                        continue
        
        # 2. Calculate Offsets
        new_calibration = {}
        for lcz_id, params in stats.items():
            lcz_offsets = {}
            # Get theoretical ranges
            theory = LCZMappings.PARAMETERS.get(lcz_id, {})
            
            for p_name, values in params.items():
                if not values or p_name not in theory:
                    continue
                    
                local_mean = np.mean(values)
                p_min, p_max = theory[p_name]
                
                # Theoretical center
                if p_max == float('inf'):
                    theory_center = p_min * 1.5 # Heuristic for open ranges
                else:
                    theory_center = (p_min + p_max) / 2.0
                
                # Calculate Offset: Local - Theory
                offset = local_mean - theory_center
                
                lcz_offsets[p_name] = {
                    'offset': float(offset),
                    'local_mean': float(local_mean),
                    'sample_count': len(values)
                }
            
            if lcz_offsets:
                new_calibration[lcz_id] = lcz_offsets
                
        self.calibration_data = new_calibration
        return True, new_calibration

    def get_overrides(self):
        """Returns a dict of offsets to be passed to classifiers."""
        overrides = {}
        for lcz_id, params in self.calibration_data.items():
            overrides[lcz_id] = {p: info['offset'] for p, info in params.items()}
        return overrides

    def save_to_project(self, folder_path):
        """Save calibration to knowledge_base folder."""
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            
        file_path = os.path.join(folder_path, "local_calibration.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.calibration_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Errore salvataggio calibrazione: {e}")
            return False

    def load_from_project(self, folder_path):
        """Load calibration from knowledge_base folder."""
        file_path = os.path.join(folder_path, "local_calibration.json")
        if not os.path.exists(file_path):
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.calibration_data = json.load(f)
            return True
        except Exception as e:
            print(f"Errore caricamento calibrazione: {e}")
            return False
