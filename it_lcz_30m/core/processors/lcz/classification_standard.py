# -*- coding: utf-8 -*-
"""
LCZ Final Classification Module - STANDARD (Stable - Dec 29)

Classifies each grid cell into a Local Climate Zone (LCZ) class based on 
calculated parameters using RMSEP (Root Mean Square Error Percentage) analysis.
Based on Stewart & Oke (2012) LCZ classification scheme.
"""

import numpy as np
from qgis.core import QgsVectorLayer, QgsField, Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QMetaType

try:
    import statsmodels.tools.eval_measures as em
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

# Centralized constants
from ...constants import LCZMappings, FileNames, FolderNames, FieldNames


class LCZClassifierStandard:
    """
    Classifies features into Local Climate Zones based on morphological parameters.
    Uses RMSEP (Root Mean Square Error Percentage) to find the best matching LCZ class.
    """
    
    # LCZ class definitions - reference centralized constants
    LCZ_CLASSES = LCZMappings.CLASSES
    
    # LCZ parameter ranges from Stewart & Oke (2012)
    LCZ_PARAMETERS = LCZMappings.PARAMETERS
    
    # Mapping from grid layer fields to LCZ parameter names
    FIELD_MAPPING = LCZMappings.FIELD_TO_PARAM

    def __init__(self, parameters):
        """
        Initialize classifier with a dict of {lcz_param_name: value}.
        None values are filtered out.
        """
        self.parameters = {k: v for k, v in parameters.items() if v is not None}

    def _is_valid_for_class(self, lcz_class):
        """
        Preliminary check if parameters are compatible with the LCZ class.
        Based on building_surface_fraction threshold.
        """
        building_fraction = self.parameters.get('building_surface_fraction')
        if building_fraction is None:
            return True  # Can't filter without this parameter
        
        threshold = 10
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            return building_fraction <= threshold
        else:
            return building_fraction > threshold

    def calculate_rmsep(self, lcz_class):
        """
        Calculate RMSEP for a given LCZ class.
        Returns (rmsep, perfect_matches, error_contributions, available_params_count).
        """
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
                    # Fallback without statsmodels
                    diff = (valid_input_params[non_zero_mask] - target_class_values[non_zero_mask]) / target_class_values[non_zero_mask]
                    rmsep = np.sqrt(np.mean(diff ** 2))
                else:
                    rmsep = float('inf')
            except Exception:
                rmsep = float('inf')

        return rmsep, perfect_matches, error_contributions, available_params_count

    def classify(self):
        """
        Classify into LCZ class by calculating RMSEP for all classes.
        Prioritizes perfect matches, then lowest RMSEP.
        Returns dict with 'lcz_class', 'rmsep', 'perfect_matches', 'available_params'.
        """
        results = {}
        total_params_available = 0

        for lcz in self.LCZ_CLASSES.keys():
            rmsep, perfect_matches, error_contributions, available_params_count = self.calculate_rmsep(lcz)
            results[lcz] = {
                'rmsep': rmsep,
                'perfect_matches': perfect_matches,
                'error_contributions': error_contributions
            }
            if total_params_available == 0 and available_params_count > 0:
                total_params_available = available_params_count

        if total_params_available == 0:
            return {'lcz_class': 'N/D', 'rmsep': float('inf'), 'perfect_matches': 0, 'available_params': 0}

        # Sort: max perfect matches first, then min RMSEP
        sorted_results = sorted(
            results.items(),
            key=lambda item: (
                -item[1]['perfect_matches'],
                float('inf') if item[1]['rmsep'] == float('inf') else item[1]['rmsep']
            )
        )

        best_class_key, best_class_values = sorted_results[0]

        if best_class_values['rmsep'] == float('inf') and best_class_values['perfect_matches'] == 0:
            best_class_key = 'N/D'

        return {
            'lcz_class': best_class_key,
            'rmsep': best_class_values['rmsep'],
            'perfect_matches': best_class_values['perfect_matches'],
            'available_params': total_params_available
        }

    @classmethod
    def get_lcz_description(cls, lcz_class):
        """Returns the description of an LCZ class."""
        return cls.LCZ_CLASSES.get(lcz_class, "Unknown class")


class LCZClassificationProcessorStandard:
    """
    Processor that applies LCZ classification to a grid layer (Standard Stable version).
    Includes ESA WorldCover-based correction for natural classes.
    """
    
    # ESA WorldCover class codes to LCZ natural class mapping - reference centralized constants
    ESA_TO_LCZ = LCZMappings.ESA_TO_LCZ
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)
    
    def _get_landuse_raster_path(self):
        """Find the ESA WorldCover raster in the unified folder."""
        import os
        base_dir = self.dm.get_project_dir()
        if not base_dir:
            return None
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), FolderNames.UNIFIED)
        landuse_path = os.path.join(unified_dir, FileNames.LANDUSE)
        return landuse_path if os.path.exists(landuse_path) else None
    
    def _compute_esa_majority_for_layer(self, layer, raster_path, log_callback=None):
        """
        Compute the majority (most frequent) ESA class for each cell in the grid layer.
        Uses QGIS native:zonalstatisticsfb algorithm for accurate zonal analysis.
        """
        import processing
        
        try:
            # Run zonal statistics with Majority statistic (code 9)
            result = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer,
                'INPUT_RASTER': raster_path,
                'RASTER_BAND': 1,
                'COLUMN_PREFIX': 'esa_',
                'STATISTICS': [9],  # 9 = Majority (most frequent value)
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            output_layer = result['OUTPUT']
            if log_callback:
                log_callback(f"Statistiche zonali ESA calcolate per {output_layer.featureCount()} celle")
            
            return output_layer
            
        except Exception as e:
            self.log(f"Errore nel calcolo statistiche zonali ESA: {e}", Qgis.Warning)
            if log_callback:
                log_callback(f"Errore statistiche zonali: {e}")
            return None
    
    def _get_dominant_esa_class(self, feature, esa_majority_idx):
        """Get dominant ESA class."""
        try:
            if esa_majority_idx == -1:
                return None
            value = feature.attribute(esa_majority_idx)
            if value is not None and str(value) not in ('NULL', ''):
                return int(float(value))
            return None
        except (ValueError, TypeError):
            return None
    
    def _apply_esa_correction(self, lcz_class, esa_class, impervious_frac=None):
        """Apply ESA correction."""
        if lcz_class in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
            if esa_class == 80:
                return 'G'
            return lcz_class
        
        if esa_class is None or lcz_class == 'N/D':
            return lcz_class
        
        suggested_lcz = self.ESA_TO_LCZ.get(esa_class)
        if suggested_lcz is None:
            return lcz_class
        
        if esa_class == 10:  # Tree cover
            if lcz_class in ['A', 'B']:
                return lcz_class
            return 'A'
        
        if esa_class == 60:  # Bare/sparse
            if impervious_frac is not None and impervious_frac > 50:
                return 'E'
            return 'F'
        
        if esa_class == 80:  # Water
            return 'G'
        
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            return suggested_lcz
        
        return lcz_class
    
    def process(self, layer, log_callback=None):
        """Main processing logic for Standard classification."""
        import os
        from qgis.core import QgsRasterLayer
        
        def log_local(msg, level=Qgis.Info):
            if log_callback:
                log_callback(msg)
            self.log(msg, level)
        
        field_name = 'lcz_class'
        idx = layer.fields().indexFromName(field_name)
        
        if idx != -1:
            field = layer.fields().at(idx)
            is_string_type = field.type() == QMetaType.QString or field.type() == 10
            if not is_string_type:
                field_name = 'LCZ_Type'
                idx = layer.fields().indexFromName(field_name)
        
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, QMetaType.QString, len=10)])
            layer.updateFields()
            idx = layer.fields().lookupField(field_name)
        
        vuln_field_name = 'lcz_vulnerability'
        vuln_idx = layer.fields().indexFromName(vuln_field_name)
        if vuln_idx == -1:
            layer.dataProvider().addAttributes([QgsField(vuln_field_name, QMetaType.QString, len=20)])
            layer.updateFields()
            vuln_idx = layer.fields().lookupField(vuln_field_name)
        
        rmsep_field_name = 'lcz_rmsep'
        rmsep_idx = layer.fields().indexFromName(rmsep_field_name)
        if rmsep_idx == -1:
            layer.dataProvider().addAttributes([QgsField(rmsep_field_name, QMetaType.Double)])
            layer.updateFields()
            rmsep_idx = layer.fields().indexFromName(rmsep_field_name)
        
        matches_field_name = 'lcz_matches'
        matches_idx = layer.fields().indexFromName(matches_field_name)
        if matches_idx == -1:
            layer.dataProvider().addAttributes([QgsField(matches_field_name, QMetaType.Int)])
            layer.updateFields()
            matches_idx = layer.fields().indexFromName(matches_field_name)
        
        esa_fix_field_name = 'lcz_esa_fix'
        esa_fix_idx = layer.fields().indexFromName(esa_fix_field_name)
        if esa_fix_idx == -1:
            layer.dataProvider().addAttributes([QgsField(esa_fix_field_name, QMetaType.QString, len=12)])
            layer.updateFields()
            esa_fix_idx = layer.fields().indexFromName(esa_fix_field_name)
        
        landuse_path = self._get_landuse_raster_path()
        use_esa_correction = False
        esa_majority_lookup = {}
        
        if landuse_path and os.path.exists(landuse_path):
            log_local("⏳ Calcolo statistiche zonali ESA WorldCover (standard)...")
            esa_layer = self._compute_esa_majority_for_layer(layer, landuse_path, log_local)
            if esa_layer:
                esa_majority_idx = esa_layer.fields().indexFromName('esa_majority')
                if esa_majority_idx != -1:
                    for feat in esa_layer.getFeatures():
                        val = feat.attribute(esa_majority_idx)
                        if val is not None and str(val) not in ('NULL', ''):
                            try:
                                esa_majority_lookup[feat.id()] = int(float(val))
                            except (ValueError, TypeError):
                                pass
                    use_esa_correction = len(esa_majority_lookup) > 0
        
        layer.startEditing()
        processed_count = 0
        corrected_count = 0
        null_count = 0
        
        impervious_idx = layer.fields().indexFromName('impervious_frac')
        
        for feature in layer.getFeatures():
            feat_id = feature.id()
            parameters = {}
            for field_name_src, param_name in LCZClassifierStandard.FIELD_MAPPING.items():
                field_idx = layer.fields().indexFromName(field_name_src)
                if field_idx != -1:
                    value = feature.attribute(field_idx)
                    if value is not None and str(value) not in ('NULL', ''):
                        try:
                            parameters[param_name] = float(value)
                        except (ValueError, TypeError):
                            parameters[param_name] = None
                    else:
                        parameters[param_name] = None
            
            impervious_frac = None
            if impervious_idx != -1:
                val = feature.attribute(impervious_idx)
                if val is not None and str(val) not in ('NULL', ''):
                    try: impervious_frac = float(val)
                    except: pass
            
            try:
                if any(v is not None for v in parameters.values()):
                    classifier = LCZClassifierStandard(parameters)
                    result = classifier.classify()
                    lcz_class = result['lcz_class']
                    raw_rmsep = result['rmsep']
                    rmsep_value = None if (raw_rmsep == float('inf') or raw_rmsep != raw_rmsep) else float(raw_rmsep)
                    perfect_matches = result['perfect_matches']
                    esa_fix_status = '-'
                    
                    if use_esa_correction and lcz_class not in ['N/D', 'ERRORE']:
                        esa_class = esa_majority_lookup.get(feat_id)
                        original_class = lcz_class
                        lcz_class = self._apply_esa_correction(lcz_class, esa_class, impervious_frac)
                        if lcz_class != original_class:
                            corrected_count += 1
                            esa_fix_status = f"{original_class} → {lcz_class}"
                    
                    vulnerability = LCZMappings.VULNERABILITY_MAPPING.get(lcz_class, 'Unknown/Other')
                    layer.changeAttributeValue(feat_id, idx, lcz_class)
                    layer.changeAttributeValue(feat_id, vuln_idx, vulnerability)
                    layer.changeAttributeValue(feat_id, rmsep_idx, rmsep_value)
                    layer.changeAttributeValue(feat_id, matches_idx, perfect_matches)
                    layer.changeAttributeValue(feat_id, esa_fix_idx, esa_fix_status)
                    processed_count += 1
                else:
                    null_count += 1
            except Exception as e:
                self.log(f"Errore feature {feat_id}: {e}", Qgis.Warning)
        
        layer.commitChanges()
        return processed_count
