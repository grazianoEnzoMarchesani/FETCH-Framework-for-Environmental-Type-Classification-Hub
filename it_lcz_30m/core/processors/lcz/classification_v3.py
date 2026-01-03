# -*- coding: utf-8 -*-
"""
LCZ Final Classification Module - ADVANCED (v3.0)

Classifies each grid cell into a Local Climate Zone (LCZ) class based on 
calculated parameters using Normalized RMSEP analysis with adaptive thresholding.

Key improvements over v2.0:
- Normalized RMSEP on [0,1] scale for consistent scoring
- Adaptive rejection threshold based on parameter distribution
- Confidence score output for transparency
- Prepared for CORINE integration (Step 3) and spatial smoothing (Step 4)
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


class LCZClassifierV3:
    """
    Classifies features into Local Climate Zones (Advanced v3.0).
    Uses Normalized RMSEP with adaptive thresholding and confidence scoring.
    """
    
    LCZ_CLASSES = LCZMappings.CLASSES
    LCZ_PARAMETERS = LCZMappings.PARAMETERS
    FIELD_MAPPING = LCZMappings.FIELD_TO_PARAM
    
    # Maximum feasible RMSEP for normalization (empirically derived)
    MAX_FEASIBLE_RMSEP = 3.0

    def __init__(self, parameters):
        self.parameters = {k: v for k, v in parameters.items() if v is not None}
        self.available_params_count = len(self.parameters)

    def _is_valid_for_class(self, lcz_class):
        """Preliminary check based on building_surface_fraction threshold."""
        building_fraction = self.parameters.get('building_surface_fraction')
        if building_fraction is None:
            return True
        
        threshold = 10
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            return building_fraction <= threshold
        else:
            return building_fraction > threshold

    def calculate_rmsep(self, lcz_class):
        """
        Calculate RMSEP for a given LCZ class.
        Returns (rmsep, perfect_matches, error_contributions).
        """
        params_definition = self.LCZ_PARAMETERS[lcz_class]
        
        if not self._is_valid_for_class(lcz_class):
            return float('inf'), 0, {}

        valid_input_params = []
        target_class_values = []
        error_contributions = {}
        perfect_matches = 0

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

        return rmsep, perfect_matches, error_contributions

    def classify(self):
        """
        Classify into LCZ class using Normalized RMSEP with Confidence Score (v3.0).
        
        Key differences from v2.0:
        - RMSEP normalized to [0,1] scale
        - Score combines normalized RMSEP and match ratio
        - Adaptive threshold based on parameter coverage
        - Outputs confidence score
        
        Returns dict with 'lcz_class', 'rmsep', 'rmsep_norm', 'perfect_matches', 
                         'available_params', 'confidence'.
        """
        if self.available_params_count == 0:
            return {
                'lcz_class': 'N/D', 
                'rmsep': float('inf'), 
                'rmsep_norm': 1.0,
                'perfect_matches': 0, 
                'available_params': 0,
                'confidence': 0.0
            }

        results = {}
        for lcz in self.LCZ_CLASSES.keys():
            rmsep, perfect_matches, error_contributions = self.calculate_rmsep(lcz)
            
            # Normalize RMSEP to [0, 1]
            if rmsep == float('inf'):
                rmsep_norm = 1.0
            else:
                rmsep_norm = min(1.0, rmsep / self.MAX_FEASIBLE_RMSEP)
            
            # Match ratio: proportion of parameters that fall within LCZ range
            match_ratio = perfect_matches / max(1, self.available_params_count)
            
            # Combined score (lower is better):
            # - 60% weight on normalized RMSEP (statistical distance)
            # - 40% weight on inverse match ratio (categorical fit)
            score = 0.6 * rmsep_norm + 0.4 * (1 - match_ratio)
            
            results[lcz] = {
                'rmsep': rmsep,
                'rmsep_norm': rmsep_norm,
                'perfect_matches': perfect_matches,
                'match_ratio': match_ratio,
                'score': score
            }

        # Sort by combined score (lower is better)
        sorted_results = sorted(
            results.items(),
            key=lambda item: item[1]['score']
        )

        best_class_key, best_class_values = sorted_results[0]
        
        # Adaptive rejection threshold:
        # - With fewer parameters, we need higher confidence for a valid classification
        # - Base threshold: 0.7 (reject if score > 0.7)
        # - Adjusted by parameter coverage
        param_coverage = self.available_params_count / 10  # 10 is max parameters
        adaptive_threshold = 0.75 - (0.1 * (1 - param_coverage))  # Range: 0.65-0.75
        
        # Reject if best score exceeds adaptive threshold
        if best_class_values['score'] > adaptive_threshold:
            best_class_key = 'N/D'
            confidence = 0.0
        else:
            # Confidence: inverse of score, scaled to [0, 1]
            # High score → low confidence, low score → high confidence
            confidence = 1.0 - (best_class_values['score'] / adaptive_threshold)
            confidence = max(0.0, min(1.0, confidence))

        return {
            'lcz_class': best_class_key,
            'rmsep': best_class_values['rmsep'],
            'rmsep_norm': best_class_values['rmsep_norm'],
            'perfect_matches': best_class_values['perfect_matches'],
            'available_params': self.available_params_count,
            'confidence': round(confidence, 2)
        }


class LCZClassificationProcessorV3:
    """
    Processor that applies Advanced LCZ classification (v3.0).
    
    Key features:
    - ESA WorldCover correction for natural classes
    - CORINE Land Cover correction for industrial areas (class 121 → LCZ 10/8)
    - Prepared for spatial smoothing (Step 4)
    """
    ESA_TO_LCZ = LCZMappings.ESA_TO_LCZ
    CORINE_TO_LCZ = LCZMappings.CORINE_TO_LCZ
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)
    
    def _apply_esa_correction(self, lcz_class, esa_class, impervious_frac=None):
        """
        Applies logic to reconcile the morphological classifier with ESA WorldCover.
        Same logic as Standard/Experimental for consistency.
        """
        if lcz_class in [str(i) for i in range(1, 11)]:
            if esa_class == 80: 
                return 'G'
            return lcz_class
            
        if esa_class is None or lcz_class == 'N/D': 
            return lcz_class
            
        suggested = self.ESA_TO_LCZ.get(esa_class)
        
        if lcz_class == 'G' and esa_class != 80:
            if esa_class == 50:
                return '9'
            return suggested if suggested else 'D'
            
        if suggested is None: 
            return lcz_class
            
        if esa_class == 10:
            return lcz_class if lcz_class in ['A', 'B'] else 'A'
            
        if esa_class == 60:
            return 'E' if (impervious_frac and impervious_frac > 50) else 'F'
            
        if esa_class == 80:
            return 'G'
            
        return suggested if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G'] else lcz_class

    def _apply_corine_correction(self, lcz_class, corine_code, anthropogenic_heat=None):
        """
        Applies CORINE Land Cover correction for industrial areas (v3.0 exclusive).
        
        Key logic:
        - If CORINE says "Industrial/commercial" (121) but LCZ is not 8/10,
          correct based on anthropogenic heat level.
        - If anthro_heat > 100 W/m² → LCZ 10 (Heavy Industry)
        - Otherwise → LCZ 8 (Large Lowrise - warehouses/logistics)
        
        Args:
            lcz_class: Current LCZ classification from RMSEP
            corine_code: CORINE Land Cover class code (e.g., 121, 112, 311)
            anthropogenic_heat: Calculated anthropogenic heat in W/m²
            
        Returns:
            Corrected LCZ class
        """
        if corine_code is None or lcz_class == 'N/D':
            return lcz_class
        
        # Convert to integer if string
        try:
            corine_int = int(corine_code)
        except (ValueError, TypeError):
            return lcz_class
        
        # CORINE 121 = Industrial or commercial units
        if corine_int == 121:
            # If already classified as industrial (8 or 10), keep it
            if lcz_class in ['8', '10']:
                return lcz_class
            
            # Otherwise, force industrial classification based on heat
            if anthropogenic_heat is not None and anthropogenic_heat > 100:
                return '10'  # Heavy Industry
            else:
                return '8'   # Large Lowrise (warehouses, logistics)
        
        # CORINE water classes (5xx) → force Water if misclassified
        if corine_int >= 511 and corine_int <= 523:
            if lcz_class != 'G':
                return 'G'
        
        # For other CORINE classes, don't override RMSEP classification
        # (ESA WorldCover already handles natural classes)
        return lcz_class

    def _load_corine_lookup(self, layer, log_callback=None):
        """
        Loads CORINE Land Cover data and creates a lookup by feature ID.
        Returns dict {feature_id: corine_code}
        """
        import os
        import json
        from qgis.core import (QgsVectorLayer, QgsProject, QgsCoordinateReferenceSystem,
                               QgsCoordinateTransform, QgsGeometry, QgsSpatialIndex,
                               QgsFeatureRequest)
        
        def log(msg):
            if log_callback: log_callback(msg)
        
        corine_lookup = {}
        base_dir = self.dm.get_project_dir()
        corine_path = os.path.join(base_dir, self.dm.get_data_dir_name(), 
                                    FolderNames.UNIFIED, FileNames.CORINE)
        
        if not os.path.exists(corine_path):
            log("⚠ Dati CORINE non trovati, correzione industriale saltata.")
            return corine_lookup
        
        # Load CORINE as vector layer
        corine_layer = QgsVectorLayer(corine_path, "corine_temp", "ogr")
        if not corine_layer.isValid():
            log("⚠ Layer CORINE non valido, correzione industriale saltata.")
            return corine_lookup
        
        corine_features = list(corine_layer.getFeatures())
        if not corine_features:
            log("⚠ Layer CORINE vuoto, correzione industriale saltata.")
            return corine_lookup
        
        log(f"📍 Caricati {len(corine_features)} poligoni CORINE")
        
        # Build spatial index for CORINE
        corine_index = QgsSpatialIndex()
        corine_dict = {}
        for feat in corine_features:
            corine_index.addFeature(feat)
            corine_dict[feat.id()] = feat
        
        # CRS transformation if needed
        grid_crs = layer.crs()
        corine_crs = corine_layer.crs()
        need_transform = grid_crs != corine_crs
        
        if need_transform:
            transform = QgsCoordinateTransform(grid_crs, corine_crs, QgsProject.instance())
        
        # For each grid cell, find intersecting CORINE polygon
        for grid_feat in layer.getFeatures():
            grid_geom = grid_feat.geometry()
            
            if need_transform:
                grid_geom_transformed = QgsGeometry(grid_geom)
                grid_geom_transformed.transform(transform)
            else:
                grid_geom_transformed = grid_geom
            
            # Query spatial index
            candidates = corine_index.intersects(grid_geom_transformed.boundingBox())
            
            best_code = None
            max_area = 0
            
            for cand_id in candidates:
                corine_feat = corine_dict[cand_id]
                corine_geom = corine_feat.geometry()
                
                if grid_geom_transformed.intersects(corine_geom):
                    intersection = grid_geom_transformed.intersection(corine_geom)
                    area = intersection.area()
                    
                    if area > max_area:
                        max_area = area
                        # Try different field names for CORINE code
                        code = corine_feat.attribute('Code_18')
                        if code is None:
                            code = corine_feat.attribute('CLC_CODE')
                        if code is None:
                            code = corine_feat.attribute('code_18')
                        best_code = code
            
            if best_code is not None:
                corine_lookup[grid_feat.id()] = best_code
        
        industrial_count = sum(1 for c in corine_lookup.values() if str(c).startswith('121'))
        if industrial_count > 0:
            log(f"  └ {industrial_count} celle in aree industriali CORINE (121)")
        
        return corine_lookup

    def process(self, layer, log_callback=None, apply_smoothing=True, **kwargs):
        """Main processing logic for Advanced v3.0 classification."""
        import os
        import processing
        from qgis.core import QgsRasterLayer

        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        log_local("🚀 Avvio classificazione LCZ ADVANCED (v3.0)...")

        # --- Field Setup ---
        field_name = 'lcz_class'
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, QMetaType.QString, len=10)])
            layer.updateFields()
            idx = layer.fields().lookupField(field_name)
        
        # Add all output fields
        field_defs = [
            ('lcz_vulnerability', QMetaType.QString, 20),
            ('lcz_rmsep', QMetaType.Double, 0),
            ('lcz_rmsep_norm', QMetaType.Double, 0),  # NEW in v3.0
            ('lcz_matches', QMetaType.Int, 0),
            ('lcz_confidence', QMetaType.Double, 0),  # NEW in v3.0
            ('lcz_esa_fix', QMetaType.QString, 20),
            ('lcz_corine_fix', QMetaType.QString, 20)  # NEW in v3.0
        ]
        for f, t, l in field_defs:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
                layer.updateFields()

        base_dir = self.dm.get_project_dir()

        # --- ESA Zonal Stats ---
        landuse_path = os.path.join(base_dir, self.dm.get_data_dir_name(), FolderNames.UNIFIED, FileNames.LANDUSE)
        esa_lookup = {}
        
        if os.path.exists(landuse_path):
            log_local("⏳ Calcolo ESA WorldCover...")
            res = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer, 
                'INPUT_RASTER': landuse_path, 
                'RASTER_BAND': 1, 
                'COLUMN_PREFIX': 'esa_', 
                'STATISTICS': [9],  # Majority
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            for feat in res['OUTPUT'].getFeatures():
                val = feat.attribute(res['OUTPUT'].fields().indexFromName('esa_majority'))
                if val is not None and str(val) not in ('NULL', ''):
                    esa_lookup[feat.id()] = int(float(val))

        # --- CORINE Lookup (NEW in v3.0) ---
        log_local("⏳ Caricamento CORINE Land Cover...")
        corine_lookup = self._load_corine_lookup(layer, log_local)

        # --- Main Classification Loop ---
        layer.startEditing()
        imp_idx = layer.fields().indexFromName('impervious_frac')
        anthro_idx = layer.fields().indexFromName('anthro_heat')
        processed = 0
        corrected_esa = 0
        corrected_corine = 0
        
        # Get field indices (using lookupField for robustness)
        idx_class = layer.fields().lookupField('lcz_class')
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')
        idx_rmsep = layer.fields().lookupField('lcz_rmsep')
        idx_rmsep_norm = layer.fields().lookupField('lcz_rmsep_norm')
        idx_matches = layer.fields().lookupField('lcz_matches')
        idx_conf = layer.fields().lookupField('lcz_confidence')
        idx_esa_fix = layer.fields().lookupField('lcz_esa_fix')
        idx_corine_fix = layer.fields().lookupField('lcz_corine_fix')
        
        # Safety check: if fields still not found, refresh once more
        if any(i == -1 for i in [idx_rmsep_norm, idx_conf]):
            log_local("⚠ Campi non trovati, forzo refresh campi layer...")
            layer.updateFields()
            idx_rmsep_norm = layer.fields().lookupField('lcz_rmsep_norm')
            idx_conf = layer.fields().lookupField('lcz_confidence')
            idx_class = layer.fields().lookupField('lcz_class')
            idx_vuln = layer.fields().lookupField('lcz_vulnerability')
            idx_rmsep = layer.fields().lookupField('lcz_rmsep')
            idx_matches = layer.fields().lookupField('lcz_matches')
            idx_esa_fix = layer.fields().lookupField('lcz_esa_fix')
            idx_corine_fix = layer.fields().lookupField('lcz_corine_fix')

        log_local(f"🔍 Debug Indici: class={idx_class}, rmsep_norm={idx_rmsep_norm}, conf={idx_conf}")

        for feature in layer.getFeatures():
            fid = feature.id()
            
            # Extract parameters
            params = {}
            for f_src, p_name in LCZClassifierV3.FIELD_MAPPING.items():
                v = feature.attribute(f_src)
                params[p_name] = float(v) if (v is not None and str(v) not in ('NULL', '')) else None
            
            try:
                if any(v is not None for v in params.values()):
                    # Run v3.0 classifier
                    result = LCZClassifierV3(params).classify()
                    lcz = result['lcz_class']
                    esa_fix_status = '-'
                    corine_fix_status = '-'
                    
                    # Get anthropogenic heat for CORINE correction
                    anthro_heat = None
                    if anthro_idx != -1:
                        anthro_val = feature.attribute(anthro_idx)
                        if anthro_val is not None and str(anthro_val) not in ('NULL', ''):
                            anthro_heat = float(anthro_val)
                    
                    # Step 1: Apply ESA correction (for natural classes)
                    if esa_lookup and lcz not in ['N/D', 'ERRORE']:
                        imp = float(feature.attribute(imp_idx)) if (imp_idx != -1 and feature.attribute(imp_idx) is not None) else None
                        original_lcz = lcz
                        lcz = self._apply_esa_correction(lcz, esa_lookup.get(fid), imp)
                        if lcz != original_lcz:
                            corrected_esa += 1
                            esa_fix_status = f"{original_lcz} → {lcz}"
                    
                    # Step 2: Apply CORINE correction (for industrial areas - NEW in v3.0)
                    if corine_lookup and lcz not in ['N/D', 'ERRORE']:
                        original_lcz_corine = lcz
                        lcz = self._apply_corine_correction(lcz, corine_lookup.get(fid), anthro_heat)
                        if lcz != original_lcz_corine:
                            corrected_corine += 1
                            corine_fix_status = f"{original_lcz_corine} → {lcz}"
                    
                    # Handle RMSEP values
                    raw_rmsep = result['rmsep']
                    rmsep_val = None if (raw_rmsep == float('inf') or raw_rmsep != raw_rmsep) else float(raw_rmsep)
                    rmsep_norm_val = result['rmsep_norm']
                    
                    # Write attributes (only if indices are valid)
                    if idx_class != -1: layer.changeAttributeValue(fid, idx_class, lcz)
                    if idx_rmsep != -1: layer.changeAttributeValue(fid, idx_rmsep, rmsep_val)
                    if idx_rmsep_norm != -1: layer.changeAttributeValue(fid, idx_rmsep_norm, rmsep_norm_val)
                    if idx_matches != -1: layer.changeAttributeValue(fid, idx_matches, result['perfect_matches'])
                    if idx_conf != -1: layer.changeAttributeValue(fid, idx_conf, result['confidence'])
                    if idx_vuln != -1: layer.changeAttributeValue(fid, idx_vuln, LCZMappings.VULNERABILITY_MAPPING.get(lcz, 'Unknown'))
                    if idx_esa_fix != -1: layer.changeAttributeValue(fid, idx_esa_fix, esa_fix_status)
                    if idx_corine_fix != -1: layer.changeAttributeValue(fid, idx_corine_fix, corine_fix_status)
                    
                    processed += 1
            except Exception as e:
                self.log(f"Errore feature {fid}: {e}", Qgis.Warning)
        
        layer.commitChanges()
        
        log_local(f"✓ Classificazione v3.0 completata: {processed} celle")
        if corrected_esa > 0:
            log_local(f"  └ {corrected_esa} celle corrette con ESA WorldCover")
        if corrected_corine > 0:
            log_local(f"  └ {corrected_corine} celle corrette con CORINE (121 → LCZ 8/10)")
        
        # Step 3: Apply spatial smoothing (majority filter - NEW in v3.0)
        if apply_smoothing:
            log_local("⏳ Applicazione smoothing spaziale (v3 Gentile - Regola 7/9)...")
            smoothed_count = self._apply_spatial_smoothing(layer, log_local)
            if smoothed_count > 0:
                log_local(f"  └ {smoothed_count} celle allineate al vicinato")
        else:
            log_local("ℹ Smoothing spaziale disabilitato dall'utente.")
        
        return processed

    def _apply_spatial_smoothing(self, layer, log_callback=None):
        """
        Applies spatial smoothing using a majority filter to reduce salt-and-pepper noise.
        
        Logic:
        - For each cell, find neighbors in a 3x3 kernel (8 neighbors + self)
        - If the cell's class differs from the majority of neighbors AND
          the cell has low confidence (< 0.5), align to neighborhood consensus
        - Preserves high-confidence cells even if isolated
        
        Args:
            layer: QgsVectorLayer with lcz_class field
            log_callback: Optional function for logging
            
        Returns:
            Number of cells smoothed
        """
        from collections import Counter
        from qgis.core import QgsSpatialIndex, QgsFeatureRequest, QgsGeometry
        
        def log(msg):
            if log_callback: log_callback(msg)
        
        idx_class = layer.fields().indexFromName('lcz_class')
        idx_conf = layer.fields().indexFromName('lcz_confidence')
        idx_vuln = layer.fields().indexFromName('lcz_vulnerability')
        
        if idx_class == -1:
            return 0
        
        # Build spatial index
        spatial_index = QgsSpatialIndex()
        feature_dict = {}
        
        for feat in layer.getFeatures():
            spatial_index.addFeature(feat)
            feature_dict[feat.id()] = {
                'lcz': feat.attribute(idx_class),
                'conf': feat.attribute(idx_conf) if idx_conf != -1 else 1.0,
                'geom': QgsGeometry(feat.geometry())
            }
        
        # Calculate neighborhood for each cell
        smoothed = 0
        updates = {}  # Store updates to apply in batch
        
        # Confidence threshold for smoothing (only smooth very low-confidence cells)
        # Reduced from 0.5 to 0.3 to be less aggressive
        CONFIDENCE_THRESHOLD = 0.3
        
        # Minimum neighbor agreement for smoothing (7 out of 9 = strong consensus)
        # Increased from 5 to 7 to preserve local micro-details
        MIN_NEIGHBOR_AGREEMENT = 7
        
        for fid, data in feature_dict.items():
            cell_lcz = data['lcz']
            cell_conf = data['conf'] if data['conf'] is not None else 0.5
            cell_geom = data['geom']
            
            # Skip N/D or high-confidence cells
            if cell_lcz in ['N/D', 'ERRORE', None]:
                continue
            if cell_conf >= CONFIDENCE_THRESHOLD:
                continue
            
            # Get bounding box expanded by cell size (approximate 3x3 kernel)
            bbox = cell_geom.boundingBox()
            # Expand by 1.5x cell width/height to capture neighbors
            expansion = max(bbox.width(), bbox.height()) * 1.5
            bbox.grow(expansion)
            
            # Query spatial index for candidates
            candidates = spatial_index.intersects(bbox)
            
            # Count neighbor classes
            neighbor_classes = []
            for cand_id in candidates:
                if cand_id == fid:  # Include self in vote
                    neighbor_classes.append(cell_lcz)
                else:
                    cand_data = feature_dict.get(cand_id)
                    if cand_data:
                        cand_lcz = cand_data['lcz']
                        if cand_lcz not in ['N/D', 'ERRORE', None]:
                            neighbor_classes.append(cand_lcz)
            
            if not neighbor_classes:
                continue
            
            # Find majority class
            counter = Counter(neighbor_classes)
            majority_class, majority_count = counter.most_common(1)[0]
            
            # Only smooth if:
            # 1. Cell differs from majority
            # 2. Majority has enough support (>= MIN_NEIGHBOR_AGREEMENT)
            if cell_lcz != majority_class and majority_count >= MIN_NEIGHBOR_AGREEMENT:
                updates[fid] = majority_class
                smoothed += 1
        
        # Apply updates in batch
        if updates:
            layer.startEditing()
            for fid, new_lcz in updates.items():
                layer.changeAttributeValue(fid, idx_class, new_lcz)
                layer.changeAttributeValue(fid, idx_vuln, 
                    LCZMappings.VULNERABILITY_MAPPING.get(new_lcz, 'Unknown'))
            layer.commitChanges()
        
        return smoothed
