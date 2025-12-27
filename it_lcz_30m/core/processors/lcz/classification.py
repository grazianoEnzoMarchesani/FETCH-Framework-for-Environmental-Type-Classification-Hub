# -*- coding: utf-8 -*-
"""
LCZ Final Classification Module

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


class LCZClassifier:
    """
    Classifies features into Local Climate Zones based on morphological parameters.
    Uses RMSEP (Root Mean Square Error Percentage) to find the best matching LCZ class.
    """
    
    # LCZ class definitions
    LCZ_CLASSES = {
        '1': 'Compact highrise', '2': 'Compact midrise', '3': 'Compact lowrise',
        '4': 'Open highrise', '5': 'Open midrise', '6': 'Open lowrise',
        '7': 'Lightweight lowrise', '8': 'Large lowrise', '9': 'Sparsely built',
        '10': 'Heavy industry', 'A': 'Dense trees', 'B': 'Scattered trees',
        'C': 'Bush, scrub', 'D': 'Low plants', 'E': 'Bare rock or paved',
        'F': 'Bare soil or sand', 'G': 'Water'
    }
    
    # LCZ parameter ranges from Stewart & Oke (2012)
    LCZ_PARAMETERS = {
        '1': {'sky_view_factor': (0.2, 0.4), 'aspect_ratio': (2, float('inf')), 'building_surface_fraction': (40, 60), 'impervious_surface_fraction': (40, 60), 'pervious_surface_fraction': (0, 10), 'height_roughness': (25, float('inf')), 'terrain_roughness': (8, 8), 'surface_admittance': (1500, 1800), 'surface_albedo': (0.1, 0.2), 'anthropogenic_heat': (50, 300)},
        '2': {'sky_view_factor': (0.3, 0.6), 'aspect_ratio': (0.75, 2), 'building_surface_fraction': (40, 70), 'impervious_surface_fraction': (30, 50), 'pervious_surface_fraction': (0, 20), 'height_roughness': (10, 25), 'terrain_roughness': (6, 7), 'surface_admittance': (1500, 2200), 'surface_albedo': (0.1, 0.2), 'anthropogenic_heat': (0, 75)},
        '3': {'sky_view_factor': (0.2, 0.6), 'aspect_ratio': (0.75, 1.5), 'building_surface_fraction': (40, 70), 'impervious_surface_fraction': (20, 50), 'pervious_surface_fraction': (0, 30), 'height_roughness': (3, 10), 'terrain_roughness': (6, 6), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.1, 0.2), 'anthropogenic_heat': (0, 75)},
        '4': {'sky_view_factor': (0.5, 0.7), 'aspect_ratio': (0.75, 1.25), 'building_surface_fraction': (20, 40), 'impervious_surface_fraction': (30, 40), 'pervious_surface_fraction': (30, 40), 'height_roughness': (25, float('inf')), 'terrain_roughness': (7, 8), 'surface_admittance': (1400, 1800), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 50)},
        '5': {'sky_view_factor': (0.5, 0.8), 'aspect_ratio': (0.3, 0.75), 'building_surface_fraction': (20, 40), 'impervious_surface_fraction': (30, 50), 'pervious_surface_fraction': (20, 40), 'height_roughness': (10, 25), 'terrain_roughness': (5, 6), 'surface_admittance': (1400, 2000), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 25)},
        '6': {'sky_view_factor': (0.6, 0.9), 'aspect_ratio': (0.3, 0.75), 'building_surface_fraction': (20, 40), 'impervious_surface_fraction': (20, 50), 'pervious_surface_fraction': (30, 60), 'height_roughness': (3, 10), 'terrain_roughness': (5, 6), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 25)},
        '7': {'sky_view_factor': (0.2, 0.5), 'aspect_ratio': (1, 2), 'building_surface_fraction': (60, 90), 'impervious_surface_fraction': (0, 20), 'pervious_surface_fraction': (0, 30), 'height_roughness': (2, 4), 'terrain_roughness': (4, 5), 'surface_admittance': (800, 1500), 'surface_albedo': (0.15, 0.35), 'anthropogenic_heat': (0, 35)},
        '8': {'sky_view_factor': (0.7, float('inf')), 'aspect_ratio': (0.1, 0.3), 'building_surface_fraction': (30, 50), 'impervious_surface_fraction': (40, 50), 'pervious_surface_fraction': (0, 20), 'height_roughness': (3, 10), 'terrain_roughness': (5, 5), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.15, 0.25), 'anthropogenic_heat': (0, 50)},
        '9': {'sky_view_factor': (0.8, 1), 'aspect_ratio': (0.1, 0.25), 'building_surface_fraction': (10, 20), 'impervious_surface_fraction': (0, 20), 'pervious_surface_fraction': (60, 80), 'height_roughness': (3, 10), 'terrain_roughness': (5, 6), 'surface_admittance': (1000, 1800), 'surface_albedo': (0.12, 0.25), 'anthropogenic_heat': (0, 10)},
        '10': {'sky_view_factor': (0.6, 0.9), 'aspect_ratio': (0.2, 0.5), 'building_surface_fraction': (20, 30), 'impervious_surface_fraction': (20, 40), 'pervious_surface_fraction': (40, 50), 'height_roughness': (5, 15), 'terrain_roughness': (5, 6), 'surface_admittance': (1000, 2500), 'surface_albedo': (0.12, 0.2), 'anthropogenic_heat': (300, float('inf'))},
        'A': {'sky_view_factor': (0, 0.4), 'aspect_ratio': (1, float('inf')), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (3, 30), 'terrain_roughness': (8, 8), 'surface_admittance': (1000, 1800), 'surface_albedo': (0.12, 0.2), 'anthropogenic_heat': (0, 0)},
        'B': {'sky_view_factor': (0.5, 0.8), 'aspect_ratio': (0.25, 0.75), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (3, 15), 'terrain_roughness': (5, 6), 'surface_admittance': (1200, 1800), 'surface_albedo': (0.15, 0.25), 'anthropogenic_heat': (0, 0)},
        'C': {'sky_view_factor': (0.7, 0.9), 'aspect_ratio': (0.25, 1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 2), 'terrain_roughness': (4, 5), 'surface_admittance': (700, 1500), 'surface_albedo': (0.15, 0.30), 'anthropogenic_heat': (0, 0)},
        'D': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 1), 'terrain_roughness': (3, 4), 'surface_admittance': (1200, 1600), 'surface_albedo': (0.15, 0.25), 'anthropogenic_heat': (0, 0)},
        'E': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (90, 100), 'pervious_surface_fraction': (0, 10), 'height_roughness': (0, 0.25), 'terrain_roughness': (1, 2), 'surface_admittance': (1200, 2500), 'surface_albedo': (0.15, 0.3), 'anthropogenic_heat': (0, 0)},
        'F': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 0.25), 'terrain_roughness': (1, 2), 'surface_admittance': (600, 1400), 'surface_albedo': (0.2, 0.35), 'anthropogenic_heat': (0, 0)},
        'G': {'sky_view_factor': (0.9, 1), 'aspect_ratio': (0, 0.1), 'building_surface_fraction': (0, 10), 'impervious_surface_fraction': (0, 10), 'pervious_surface_fraction': (90, 100), 'height_roughness': (0, 0.25), 'terrain_roughness': (1, 1), 'surface_admittance': (1500, 1500), 'surface_albedo': (0.02, 0.10), 'anthropogenic_heat': (0, 0)}
    }
    
    # Mapping from grid layer fields to LCZ parameter names
    FIELD_MAPPING = {
        'svf_mean': 'sky_view_factor',
        'aspect_ratio': 'aspect_ratio',
        'building_frac': 'building_surface_fraction',
        'impervious_frac': 'impervious_surface_fraction',
        'pervious_frac': 'pervious_surface_fraction',
        'z_h': 'height_roughness',
        'terrain_rough': 'terrain_roughness',
        'admittance': 'surface_admittance',
        'albedo': 'surface_albedo',
        'anthro_heat': 'anthropogenic_heat'
    }

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


class LCZClassificationProcessor:
    """
    Processor that applies LCZ classification to a grid layer.
    Includes ESA WorldCover-based correction for natural classes.
    """
    
    # ESA WorldCover class codes to LCZ natural class mapping
    ESA_TO_LCZ = {
        10: 'A',   # Tree cover → Dense trees (or B if low SVF)
        20: 'C',   # Shrubland → Bush, scrub
        30: 'D',   # Grassland → Low plants
        40: 'D',   # Cropland → Low plants
        50: None,  # Built-up → Keep RMSEP classification (1-10)
        60: 'F',   # Bare/sparse vegetation → Bare soil (check impervious for E)
        70: 'F',   # Snow and ice → Bare soil/sand
        80: 'G',   # Permanent water bodies → Water
        90: 'D',   # Herbaceous wetland → Low plants (near water)
        95: 'A',   # Mangroves → Dense trees
        100: 'D',  # Moss and lichen → Low plants
    }
    
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
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
        return landuse_path if os.path.exists(landuse_path) else None
    
    def _get_dominant_esa_class(self, geometry, raster_provider):
        """
        Get the dominant ESA class within a polygon geometry.
        Uses centroid sampling for speed - sufficient for grid cells.
        
        Args:
            geometry: QgsGeometry of the cell
            raster_provider: QgsRasterDataProvider (reused across features)
        """
        from qgis.core import QgsPointXY
        
        try:
            # Use centroid sampling - efficient for grid cells
            centroid = geometry.centroid().asPoint()
            
            # Sample the raster value at centroid
            value, success = raster_provider.sample(
                QgsPointXY(centroid.x(), centroid.y()), 1  # band 1
            )
            
            if success and value is not None:
                return int(value)
            return None
            
        except Exception as e:
            self.log(f"Errore nel campionamento ESA: {e}", Qgis.Warning)
            return None
    
    def _apply_esa_correction(self, lcz_class, esa_class, impervious_frac=None):
        """
        Apply correction to LCZ classification based on ESA WorldCover data.
        Only corrects natural classes (A-G) when there's a mismatch.
        """
        # If classified as built (1-10), don't override with ESA
        if lcz_class in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
            # But if ESA says it's water, that's a strong signal
            if esa_class == 80:
                return 'G'  # Override to water
            return lcz_class
        
        # If no ESA data or N/D, keep original
        if esa_class is None or lcz_class == 'N/D':
            return lcz_class
        
        # Get suggested LCZ from ESA
        suggested_lcz = self.ESA_TO_LCZ.get(esa_class)
        
        if suggested_lcz is None:
            # ESA class 50 (built-up) - keep RMSEP result
            return lcz_class
        
        # Special cases for correction
        if esa_class == 10:  # Tree cover
            # Could be A (dense) or B (scattered) based on SVF
            # Keep original if already A or B
            if lcz_class in ['A', 'B']:
                return lcz_class
            return 'A'  # Default to dense trees
        
        if esa_class == 60:  # Bare/sparse
            # Could be E (paved) or F (soil) based on impervious fraction
            if impervious_frac is not None and impervious_frac > 50:
                return 'E'
            return 'F'
        
        if esa_class == 80:  # Water
            return 'G'  # Always water
        
        # For other cases, use ESA suggestion if RMSEP gave a different natural class
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            return suggested_lcz
        
        return lcz_class
    
    def process(self, layer, log_callback=None):
        """
        Classify all features in the grid layer.
        Adds 'LCZ_Class' field with classification result.
        Applies ESA WorldCover correction for natural classes.
        Returns number of classified features.
        """
        import os
        from qgis.core import QgsRasterLayer
        
        def log_local(msg, level=Qgis.Info):
            if log_callback:
                log_callback(msg)
            self.log(msg, level)
        
        # Ensure output field exists with correct type (QString for LCZ codes like "3", "A", etc.)
        # IMPORTANT: Never delete existing fields to avoid schema corruption during editing
        field_name = 'lcz_class'
        idx = layer.fields().indexFromName(field_name)
        
        # Check if field exists
        if idx != -1:
            field = layer.fields().at(idx)
            # QMetaType.QString is type 10, QVariant.String is type 10
            is_string_type = field.type() == QMetaType.QString or field.type() == 10
            if not is_string_type:
                # Field exists with wrong type - use alternative field name instead of deleting
                log_local(f"Campo {field_name} esiste con tipo {field.typeName()} (non QString). Uso campo alternativo.", Qgis.Warning)
                field_name = 'LCZ_Type'  # Alternative field name
                idx = layer.fields().indexFromName(field_name)
        
        # Create field if it doesn't exist
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, QMetaType.QString, len=10)])
            layer.updateFields()
            idx = layer.fields().indexFromName(field_name)
            log_local(f"Campo {field_name} creato come QString")
        
        # Create RMSEP field (Double) for storing the RMSEP value
        rmsep_field_name = 'lcz_rmsep'
        rmsep_idx = layer.fields().indexFromName(rmsep_field_name)
        if rmsep_idx == -1:
            layer.dataProvider().addAttributes([QgsField(rmsep_field_name, QMetaType.Double)])
            layer.updateFields()
            rmsep_idx = layer.fields().indexFromName(rmsep_field_name)
            log_local(f"Campo {rmsep_field_name} creato come Double")
        
        # Create Perfect Matches field (Integer) for storing the number of perfect matches
        matches_field_name = 'lcz_matches'
        matches_idx = layer.fields().indexFromName(matches_field_name)
        if matches_idx == -1:
            layer.dataProvider().addAttributes([QgsField(matches_field_name, QMetaType.Int)])
            layer.updateFields()
            matches_idx = layer.fields().indexFromName(matches_field_name)
            log_local(f"Campo {matches_field_name} creato come Integer")
        
        # Create ESA correction flag field (String) for tracking if ESA WorldCover corrected the class
        esa_fix_field_name = 'lcz_esa_fix'
        esa_fix_idx = layer.fields().indexFromName(esa_fix_field_name)
        if esa_fix_idx == -1:
            layer.dataProvider().addAttributes([QgsField(esa_fix_field_name, QMetaType.QString, len=12)])
            layer.updateFields()
            esa_fix_idx = layer.fields().indexFromName(esa_fix_field_name)
            log_local(f"Campo {esa_fix_field_name} creato come QString")
        
        # Try to load ESA landuse raster for correction (load ONCE, reuse provider)
        landuse_path = self._get_landuse_raster_path()
        use_esa_correction = False
        landuse_provider = None
        
        if landuse_path and os.path.exists(landuse_path):
            landuse_raster = QgsRasterLayer(landuse_path, "esa_landuse")
            if landuse_raster.isValid():
                landuse_provider = landuse_raster.dataProvider()
                use_esa_correction = True
                log_local(f"Correzione ESA WorldCover attiva: {os.path.basename(landuse_path)}")
            else:
                log_local("Layer ESA non valido, correzione disabilitata", Qgis.Warning)
        else:
            log_local("Raster ESA WorldCover non trovato, classificazione senza correzione")
        
        log_local(f"Avvio classificazione LCZ per {layer.featureCount()} celle...")
        
        # Diagnostic: log available fields
        available_fields = [f.name() for f in layer.fields()]
        log_local(f"Campi disponibili nel layer: {available_fields}")
        
        # Check which expected fields exist
        expected_fields = list(LCZClassifier.FIELD_MAPPING.keys())
        missing = [f for f in expected_fields if f not in available_fields]
        found = [f for f in expected_fields if f in available_fields]
        log_local(f"Campi LCZ trovati: {found}")
        if missing:
            log_local(f"Campi LCZ mancanti: {missing}", Qgis.Warning)
        
        layer.startEditing()
        processed_count = 0
        corrected_count = 0
        error_count = 0
        null_count = 0  # Track features with all NULL params
        
        # Get impervious field index for E/F distinction
        impervious_idx = layer.fields().indexFromName('impervious_frac')
        
        # Diagnostic: check first feature's values
        first_feature_logged = False
        
        for feature in layer.getFeatures():
            feat_id = feature.id()
            
            # Extract parameters from feature fields
            parameters = {}
            for field_name_src, param_name in LCZClassifier.FIELD_MAPPING.items():
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
            
            # Log first feature's parameters for debugging
            if not first_feature_logged:
                param_summary = {k: v for k, v in parameters.items() if v is not None}
                if param_summary:
                    log_local(f"Prima feature - parametri trovati: {list(param_summary.keys())}")
                else:
                    log_local(f"Prima feature - NESSUN parametro valido trovato!", Qgis.Warning)
                first_feature_logged = True
            
            # Get impervious fraction for E/F correction
            impervious_frac = None
            if impervious_idx != -1:
                val = feature.attribute(impervious_idx)
                if val is not None and str(val) not in ('NULL', ''):
                    try:
                        impervious_frac = float(val)
                    except (ValueError, TypeError):
                        pass
            
            # Classify
            try:
                rmsep_value = None
                perfect_matches = 0
                esa_fix_status = '-'  # Default: no correction
                
                if any(v is not None for v in parameters.values()):
                    classifier = LCZClassifier(parameters)
                    result = classifier.classify()
                    lcz_class = result['lcz_class']
                    # Store RMSEP: None only if inf, otherwise store the actual value (including 0)
                    raw_rmsep = result['rmsep']
                    rmsep_value = None if (raw_rmsep == float('inf') or raw_rmsep != raw_rmsep) else float(raw_rmsep)
                    perfect_matches = result['perfect_matches']
                else:
                    lcz_class = 'N/D'
                    null_count += 1
                
                # Apply ESA correction for natural classes
                if use_esa_correction and lcz_class not in ['N/D', 'ERRORE']:
                    esa_class = self._get_dominant_esa_class(feature.geometry(), landuse_provider)
                    original_class = lcz_class
                    lcz_class = self._apply_esa_correction(lcz_class, esa_class, impervious_frac)
                    if lcz_class != original_class:
                        corrected_count += 1
                        # Show explicit transition: "original → new" (e.g., "C → D")
                        esa_fix_status = f"{original_class} → {lcz_class}"
                
                layer.changeAttributeValue(feat_id, idx, lcz_class)
                layer.changeAttributeValue(feat_id, rmsep_idx, rmsep_value)
                layer.changeAttributeValue(feat_id, matches_idx, perfect_matches)
                layer.changeAttributeValue(feat_id, esa_fix_idx, esa_fix_status)
                processed_count += 1
                
            except Exception as e:
                log_local(f"Errore classificazione feature {feat_id}: {e}", Qgis.Warning)
                layer.changeAttributeValue(feat_id, idx, 'ERRORE')
                layer.changeAttributeValue(feat_id, rmsep_idx, None)
                layer.changeAttributeValue(feat_id, matches_idx, None)
                layer.changeAttributeValue(feat_id, esa_fix_idx, 'ERRORE')
                error_count += 1
        
        layer.commitChanges()
        
        if use_esa_correction:
            log_local(f"Classificazione completata: {processed_count} celle, {corrected_count} corrette con ESA, {null_count} N/D, {error_count} errori")
        else:
            log_local(f"Classificazione completata: {processed_count} celle, {null_count} N/D (senza parametri), {error_count} errori")
        
        return processed_count

