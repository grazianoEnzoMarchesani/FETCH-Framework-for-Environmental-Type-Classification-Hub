# -*- coding: utf-8 -*-
"""
LCZ Classification Module - SEMANTIC EXPERT ENGINE (v8.0)

Implements a rule-based semantic classification approach:
1. Context-First: Works on Districts (Clusters) to absorb local noise.
2. Fuzzy Tagging: Translates numerical values into semantic descriptors.
3. Archetype Matching: Compares district identity with Stewart & Oke standard.
4. XAI (Explainable AI): Provides textual justification for classification.
"""

import numpy as np
import os
from qgis.core import (QgsVectorLayer, QgsField, Qgis, QgsMessageLog, 
                       QgsFeature, QgsProject, QgsGeometry, QgsVectorFileWriter)
from qgis.PyQt.QtCore import QMetaType

# Centralized constants
try:
    from ...constants import LCZMappings, FieldNames, FileNames, FolderNames
except ImportError:
    class LCZMappings: 
        CLASSES = {}
        BUILT_CLASSES = []
        NATURAL_CLASSES = []
    class FieldNames: 
        LCZ_CLASS = "lcz_class"
        BUILDING_FRAC = "building_frac"
        ROUGHNESS_HEIGHT = "roughness_height"
        SVF = "sky_view_factor"
        IMPERVIOUS_FRAC = "impervious_frac"
        PERVIOUS_FRAC = "pervious_frac"

class LCZFuzzyTagger:
    """Translates numerical morphological data into semantic descriptors."""
    
    @staticmethod
    def tag_height(z_h):
        if z_h < 3.0: return "Single-story"
        if 3.0 <= z_h < 10.0: return "Low-rise (1-3 stories)"
        if 10.0 <= z_h < 25.0: return "Mid-rise (3-9 stories)"
        return "High-rise (> 9 stories)"

    @staticmethod
    def tag_density(bsf):
        # BSF is 0-100%
        if bsf < 10.0: return "Sparse"
        if 10.0 <= bsf < 40.0: return "Open arrangement"
        return "Dense mix"

    @staticmethod
    def tag_surface(isf, psf, albedo=0.15, esa_class=None):
        # ISF/PSF are 0-100%
        # SMOKING GUN: ESA LandUse is the most reliable for Water/Natural
        if esa_class == 80 or albedo < 0.06: return "Water body"
        if isf > 60.0: return "Mostly paved"
        if psf > 60.0: 
            if albedo > 0.25: return "Reflective vegetation/cropland"
            return "Abundance of pervious/vegetation"
        if isf < 20.0 and psf < 20.0: return "Bare soil or sand"
        return "Mixed surface"

class LCZSemanticMatcher:
    """
    Matches district data against all 10 morphological parameters (The 'Perito' mode).
    Provides detailed scoring and semantic justifications.
    """
    
    def __init__(self):
        self.tagger = LCZFuzzyTagger()
        # Direct access to the official standard ranges
        self.param_ranges = LCZMappings.PARAMETERS
        self.param_mapping = LCZMappings.FIELD_TO_PARAM

    def match(self, district_data, class_subset=None, esa_class=None):
        """
        Performs a full 10-parameter audit against standard archetypes.
        district_data: dict of mean parameters from the district.
        esa_class: Optional ESA landuse category to anchor the natural types.
        """
        scores = {}
        explanations = {}

        # 1. Preparation: Define subset of classes to check
        target_ids = list(self.param_ranges.keys())
        if class_subset:
            target_ids = [tid for tid in target_ids if tid in class_subset]

        isf = district_data.get('isf', 0)
        psf = district_data.get('psf', 0)
        bsf = district_data.get('bsf', 0)
        albedo = district_data.get('albedo', 0.15)

        # 1-bis. AUTHORITATIVE WATER (ESA 80)
        # If ESA says water and BSF is negligible, skip the loop and force G.
        if esa_class == 80 and bsf < 10.0:
            tags = {
                "height": self.tagger.tag_height(district_data.get('z_h', 0)),
                "density": "N/A (Water body)",
                "surface": "Water body (ESA Authoritative)"
            }
            return 'G', 100.0, "Identificazione autoritativa basata su ESA WorldCover (Acqua).", tags

        # 2. Match loop
        for lcz_id in target_ids:
            # --- PROFESSONAL VETOS (Perito Expert Rules) ---
            # Rule: LCZ G (Water) CANNOT have significant imperviousness
            if lcz_id == 'G' and isf > 20.0: continue
            
            # Rule: LCZ E (Paved) MUST have significant imperviousness
            if lcz_id == 'E' and isf < 40.0: continue

            # Rule: LCZ G (Water) MUST have low albedo (unless glinting, but range handles it)
            if lcz_id == 'G' and albedo > 0.20: continue 

            # Rule: Paved Surface Priority (User-suggested rule for Piazza Arringo fix)
            # If it's mostly paved (ISF > 90) and has few buildings (BSF < 10), 
            # veto natural classes that require high perviousness (A, B, C, D, F, G).
            bsf = district_data.get('bsf', 0)
            if isf > 90.0 and bsf < 10.0:
                if lcz_id in ['A', 'B', 'C', 'D', 'F', 'G']:
                    continue

            ranges = self.param_ranges[lcz_id]
            matches = 0
            deviations = []
            param_labels = LCZMappings.PARAM_LABELS
            
            # Audit each of the 10 parameters
            for p_key, (p_min, p_max) in ranges.items():
                internal_key = next((k for k, v in self.param_mapping.items() if v == p_key), None)
                
                if internal_key and internal_key in district_data:
                    val = district_data[internal_key]
                    
                    if p_min <= val <= p_max:
                        matches += 1
                    else:
                        label = param_labels.get(p_key, p_key)
                        deviations.append(f"{label} ({val:.2f} vs {p_min}-{p_max})")
            
            total_params = len(ranges)
            score = (matches / total_params) * 100
            
            # --- CONTEXTUAL ESA HINTS (Expert Reinforcement) ---
            # Nuanced bonuses based on land cover categories
            if esa_class:
                # 1. Matching Hint: If morphology and landuse agree on the broad type
                if LCZMappings.ESA_TO_LCZ.get(esa_class) == lcz_id:
                    score += 12 # Standard reinforcement bonus
                
                # 2. Category Hints: Bias towards natural types
                if esa_class == 10 and lcz_id in ['A', 'B']: # Tree cover
                    score += 10
                elif esa_class in [30, 40] and lcz_id == 'D': # Grassland / Cropland
                    score += 10
                elif esa_class == 60 and lcz_id == 'F': # Bare / Sparse
                    score += 10
                
                # 3. Urban Bias: If ESA sees Built-up but morphology found a Natural class
                # (Helps with parks or tree-lined streets in dense areas)
                elif esa_class == 50 and lcz_id in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                    score -= 10 # Soft penalty for natural classes in areas ESA designated as urban
            
            scores[lcz_id] = score
            
            if score >= 100:
                explanations[lcz_id] = "Match perfetto (confermato/rinforzato da ESA)."
            else:
                explanations[lcz_id] = f"{matches}/10 parametri OK. Divergenze: " + ", ".join(deviations[:2]) + ("..." if len(deviations) > 2 else "")

        if not scores:
            # Fallback for N/D
            return "N/D", 0.0, "Nessun match semantico valido (Veto attivi).", {}

        # 3. Decision
        best_id = max(scores, key=scores.get)
        
        # Basic tags for UI
        basic_tags = {
            "height": self.tagger.tag_height(district_data.get('z_h', 0)),
            "density": self.tagger.tag_density(district_data.get('bsf', 0)),
            "surface": self.tagger.tag_surface(isf, district_data.get('psf', 0), albedo, esa_class)
        }
        
        return best_id, min(100.0, scores[best_id]), explanations[best_id], basic_tags

from .base import LCZBaseProcessor

class LCZClassificationProcessorV8(LCZBaseProcessor):
    """Processor for Semantic Expert Engine (v8.0)."""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.matcher = LCZSemanticMatcher()

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(f"[LCZ v8 Semantic] {msg}", "FETCH", level)

    def process(self, layer, log_callback=None, **kwargs):
        """
        Main execution flow for v8.
        1. Context-First: Cluster features into districts.
        2. Perfectionist: Split districts with high internal variance.
        3. Semantic Match: Classify districts using rules.
        """
        from ...geometry_utils import cluster_multidimensional, create_district_geometry
        
        # Sanitization: Ensure existing data doesn't violate field constraints
        self._sanitize_layer(layer)
        
        def log_local(msg, level=Qgis.Info):
            msg_str = str(msg)
            if log_callback: log_callback(msg_str)
            self.log(msg_str, level)

        log_local("📖 Avvio Motore Esperto Semantico (v8.0)...")

        # 1. Identify Urban Seeds (BSF >= 10.0)
        urban_features = []
        for feat in layer.getFeatures():
            b_frac = feat.attribute(FieldNames.BUILDING_FRAC)
            try:
                val = float(b_frac) if b_frac is not None and str(b_frac) != 'NULL' else 0.0
                if val >= 10.0: urban_features.append(feat)
            except (ValueError, TypeError): continue
        
        if not urban_features:
            log_local("ℹ️ Nessun edificio trovato. Classificazione v8 terminata.", Qgis.Warning)
            return 0

        # 2. Initial Multidimensional Clustering (Spatial + Height + BSF)
        log_local("🧩 Clustering spaziale e morfologico iniziale...")
        cluster_fields = [FieldNames.ROUGHNESS_HEIGHT, FieldNames.BUILDING_FRAC]
        cluster_weights = {FieldNames.ROUGHNESS_HEIGHT: 3.5, FieldNames.BUILDING_FRAC: 1.5}
        
        labels = cluster_multidimensional(
            urban_features, cluster_fields, eps=1.2, min_samples=2,
            spatial_scale=45.0, weights=cluster_weights
        )
        
        # 3. The Perfectionist: Auto-Splitting check
        log_local("⚖️ Controllo Purezza Morfologica (Logica Perfezionista)...")
        from ...geometry_utils import split_heterogeneous_clusters
        final_clusters = split_heterogeneous_clusters(
            urban_features, labels, FieldNames.ROUGHNESS_HEIGHT, std_threshold=4.0
        )

        log_local(f"🏢 Analisi di {len(final_clusters)} distretti puri.")

        # 4. Semantic Matching & Classification
        layer.startEditing()
        processed_count = 0
        district_feature_ids = set()
        
        # Field Setup (Ensure all UI indicators work)
        field_defs = [
            (FieldNames.LCZ_CLASS, QMetaType.QString, 10),
            ('lcz_matches', QMetaType.Int, 0),
            ('lcz_score', QMetaType.Double, 0),
            ('lcz_confidence', QMetaType.Double, 0),
            ('lcz_rmsep', QMetaType.Double, 0),
            ('lcz_rmsep_norm', QMetaType.Double, 0),
            ('lcz_vulnerability', QMetaType.QString, 25),
            ('lcz_esa_fix', QMetaType.QString, 50)
        ]
        
        for f_name, f_type, f_len in field_defs:
            if layer.fields().indexFromName(f_name) == -1:
                layer.dataProvider().addAttributes([QgsField(f_name, f_type, len=f_len)])
        layer.updateFields()
        
        idx_map = {f[0]: layer.fields().lookupField(f[0]) for f in field_defs}
        
        field_to_param = {
            FieldNames.SVF_MEAN: 'svf_mean',
            FieldNames.ASPECT_RATIO: 'aspect_ratio',
            FieldNames.BUILDING_FRAC: 'bsf',
            FieldNames.IMPERVIOUS_FRAC: 'isf',
            FieldNames.PERVIOUS_FRAC: 'psf',
            FieldNames.ROUGHNESS_HEIGHT: 'z_h',
            FieldNames.TERRAIN_ROUGHNESS: 'terrain_rough',
            FieldNames.ADMITTANCE: 'admittance',
            FieldNames.ALBEDO: 'albedo',
            FieldNames.ANTHROPOGENIC_HEAT: 'anthro_heat'
        }
        
        # ESA WorldCover Context (Majority sampling)
        esa_path = os.path.join(self.dm.get_data_dir_path(), FolderNames.UNIFIED, FileNames.LANDUSE)
        esa_lookup = {}
        if os.path.exists(esa_path):
            log_local("⏳ Analisi ESA WorldCover per rinforzo semantico...")
            import processing
            res = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer, 'INPUT_RASTER': esa_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'esa_',
                'STATISTICS': [9], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            for feat in res['OUTPUT'].getFeatures():
                v = feat.attribute(res['OUTPUT'].fields().indexFromName('esa_majority'))
                if v is not None and str(v) not in ('NULL', ''): esa_lookup[feat.id()] = int(float(v))

        # Built-in context
        built_ids = [str(x) for x in range(1, 11)]
        natural_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

        # Setup District Vector Layer for visualization
        log_local("📐 Preparazione layer vettoriale dei distretti semantici...")
        district_path = os.path.join(self.dm.get_data_dir_path(), "distretti_lcz_v8.gpkg")
        district_layer = QgsVectorLayer("MultiPolygon?crs=" + layer.crs().authid(), "Distretti LCZ v8", "memory")
        district_layer.startEditing()
        district_layer.addAttribute(QgsField("cluster_id", QMetaType.Int))
        district_layer.addAttribute(QgsField("lcz_id", QMetaType.QString))
        district_layer.addAttribute(QgsField("score", QMetaType.Double))
        district_layer.addAttribute(QgsField("explanation", QMetaType.QString))
        district_layer.updateFields()

        for features in final_clusters:
            # Aggregate district parameters
            district_data = {}
            for f_name, p_key in field_to_param.items():
                vals = [float(f.attribute(f_name)) for f in features if f.attribute(f_name) is not None and str(f.attribute(f_name)) != 'NULL']
                district_data[p_key] = np.mean(vals) if vals else 0.0
            
            # Majority ESA for district
            luse_vals = [esa_lookup.get(f.id()) for f in features if esa_lookup.get(f.id()) is not None]
            dist_esa = max(set(luse_vals), key=luse_vals.count) if luse_vals else None

            # Match district against archetypes (restricted to built classes)
            lcz_id, score, explanation, tags = self.matcher.match(district_data, class_subset=built_ids, esa_class=dist_esa)

            # Match metrics
            esa_status = "Reinforced" if dist_esa and LCZMappings.ESA_TO_LCZ.get(dist_esa) == lcz_id else "-"
            matches_count = int((score / 100.0) * 10.0)
            vuln = LCZMappings.VULNERABILITY_MAPPING.get(lcz_id, 'Unknown')
            confidence = float(score / 100.0)
            rmsep_val = 1.0 - confidence

            for f in features:
                fid = f.id()
                district_feature_ids.add(fid)
                if idx_map[FieldNames.LCZ_CLASS] != -1: layer.changeAttributeValue(fid, idx_map[FieldNames.LCZ_CLASS], lcz_id)
                if idx_map['lcz_score'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_score'], float(score))
                if idx_map['lcz_confidence'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_confidence'], confidence)
                if idx_map['lcz_rmsep'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep'], rmsep_val)
                if idx_map['lcz_rmsep_norm'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep_norm'], rmsep_val)
                if idx_map['lcz_matches'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_matches'], matches_count)
                if idx_map['lcz_vulnerability'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_vulnerability'], vuln)
                if idx_map['lcz_esa_fix'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_esa_fix'], esa_status)
            
            # Add to district vector layer
            geoms = [f.geometry() for f in features if not f.geometry().isEmpty()]
            if geoms:
                district_geom = create_district_geometry(geoms)
                if district_geom and not district_geom.isEmpty():
                    district_geom.convertToMultiType()
                    feat = QgsFeature(district_layer.fields())
                    feat.setGeometry(district_geom)
                    feat.setAttributes([processed_count, str(lcz_id), float(score), explanation])
                    district_layer.addFeature(feat)

            processed_count += len(features)
            if len(final_clusters) < 15 or processed_count % 100 == 0:
                log_local(f"🔍 Distretto -> LCZ {lcz_id} ({score:.0f}%). {explanation}")

        district_layer.commitChanges()
        
        # Save District layer to GPKG
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.driverName = "GPKG"
        save_options.fileEncoding = "UTF-8"
        QgsVectorFileWriter.writeAsVectorFormatV3(district_layer, district_path, layer.transformContext(), save_options)
        
        # Load into Project
        final_dist_layer = QgsVectorLayer(district_path, "Distretti Semantici LCZ v8.0", "ogr")
        QgsProject.instance().addMapLayer(final_dist_layer)

        # 5. Remaining Cells (Natural or Isolated Built)
        log_local("🌱 Completamento classificazione aree rimanenti...")
        remaining_count = 0
        for feat in layer.getFeatures():
            if feat.id() in district_feature_ids: continue
            
            f_data = {}
            for f_name, p_key in field_to_param.items():
                val = feat.attribute(f_name)
                f_data[p_key] = float(val) if val is not None and str(val) != 'NULL' else 0.0
            
            # DETERMINISTIC BOUNDARY: If BSF >= 10.0, it's urban (built), even if isolated.
            is_urban_seed = f_data.get('bsf', 0) >= 10.0
            subset = built_ids if is_urban_seed else natural_ids
            
            feat_esa = esa_lookup.get(feat.id())
            lcz_id, score, _, _ = self.matcher.match(f_data, class_subset=subset, esa_class=feat_esa)
            
            esa_status = "Reinforced" if feat_esa and LCZMappings.ESA_TO_LCZ.get(feat_esa) == lcz_id else "-"
            matches_count = int((score / 100.0) * 10.0)
            vuln = LCZMappings.VULNERABILITY_MAPPING.get(lcz_id, 'Unknown')
            confidence = float(score / 100.0)
            rmsep_val = 1.0 - confidence

            fid = feat.id()
            if idx_map[FieldNames.LCZ_CLASS] != -1: layer.changeAttributeValue(fid, idx_map[FieldNames.LCZ_CLASS], lcz_id)
            if idx_map['lcz_score'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_score'], float(score))
            if idx_map['lcz_confidence'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_confidence'], confidence)
            if idx_map['lcz_rmsep'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep'], rmsep_val)
            if idx_map['lcz_rmsep_norm'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep_norm'], rmsep_val)
            if idx_map['lcz_matches'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_matches'], matches_count)
            if idx_map['lcz_vulnerability'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_vulnerability'], vuln)
            if idx_map['lcz_esa_fix'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_esa_fix'], esa_status)
            
            remaining_count += 1

        layer.commitChanges()
        log_local(f"✅ Classificazione v8.0 completata: {processed_count} in distretti, {remaining_count} individuali.")
        return processed_count + remaining_count
