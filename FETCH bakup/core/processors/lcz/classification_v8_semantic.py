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

        # 1-bis. AUTHORITATIVE ESA RULES FOR NATURAL AREAS
        # When ESA indicates a specific land cover and BSF is negligible, 
        # we trust ESA over morphological matching.
        
        # Water (ESA 80) → LCZ G
        if esa_class == 80 and bsf < 10.0:
            tags = {
                "height": self.tagger.tag_height(district_data.get('z_h', 0)),
                "density": "N/A (Water body)",
                "surface": "Water body (ESA Authoritative)"
            }
            return 'G', 100.0, 100.0, "Identificazione autoritativa basata su ESA WorldCover (Acqua).", tags
        
        # Shrubland (ESA 20) → LCZ C (Bush, scrub)
        if esa_class == 20 and bsf < 10.0:
            tags = {
                "height": self.tagger.tag_height(district_data.get('z_h', 0)),
                "density": "N/A (Natural)",
                "surface": "Shrubland (ESA Authoritative)"
            }
            return 'C', 95.0, 100.0, "Identificazione autoritativa: Shrubland ESA → LCZ C (Bush, scrub).", tags
        
        # Grassland (ESA 30) → LCZ D (Low plants)
        if esa_class == 30 and bsf < 10.0:
            tags = {
                "height": self.tagger.tag_height(district_data.get('z_h', 0)),
                "density": "N/A (Natural)",
                "surface": "Grassland (ESA Authoritative)"
            }
            return 'D', 95.0, 100.0, "Identificazione autoritativa: Grassland ESA → LCZ D (Low plants).", tags
        
        # Cropland (ESA 40) → LCZ D (Low plants)
        if esa_class == 40 and bsf < 10.0:
            tags = {
                "height": self.tagger.tag_height(district_data.get('z_h', 0)),
                "density": "N/A (Natural)",
                "surface": "Cropland (ESA Authoritative)"
            }
            return 'D', 95.0, 100.0, "Identificazione autoritativa: Cropland ESA → LCZ D (Low plants).", tags
        
        # Bare/sparse vegetation (ESA 60) → LCZ F (Bare soil or sand)
        if esa_class == 60 and bsf < 10.0 and isf < 50.0:
            tags = {
                "height": self.tagger.tag_height(district_data.get('z_h', 0)),
                "density": "N/A (Natural)",
                "surface": "Bare/sparse (ESA Authoritative)"
            }
            return 'F', 95.0, 100.0, "Identificazione autoritativa: Bare/Sparse ESA → LCZ F.", tags

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
            
            # Determine if this is a natural class (A-G)
            is_natural_class = lcz_id in ['A', 'B', 'C', 'D', 'E', 'F', 'G']
            
            # Audit each of the 10 parameters
            svf_matched = False
            for p_key, (p_min, p_max) in ranges.items():
                # NATURAL CLASS RULE: Skip aspect_ratio for natural classes
                # (Cannot reliably calculate from 10m resolution canopy data)
                if is_natural_class and p_key == 'aspect_ratio':
                    continue
                    
                internal_key = next((k for k, v in self.param_mapping.items() if v == p_key), None)
                
                if internal_key and internal_key in district_data:
                    val = district_data[internal_key]
                    
                    if p_min <= val <= p_max:
                        matches += 1
                        # Track SVF match for natural classes bonus
                        if p_key == 'sky_view_factor':
                            svf_matched = True
                    else:
                        label = param_labels.get(p_key, p_key)
                        deviations.append(f"{label} ({val:.2f} vs {p_min}-{p_max})")
            
            # Adjust total params for natural classes (excluding aspect_ratio)
            total_params = len(ranges) - 1 if is_natural_class else len(ranges)
            score = (matches / total_params) * 100 if total_params > 0 else 0
            
            # NATURAL CLASS RULE: SVF is the primary discriminator
            # Give extra weight when SVF matches for natural classes
            if is_natural_class and svf_matched:
                score += 15  # SVF is crucial for distinguishing A vs B vs C vs D
            
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
            return "N/D", 0.0, 100.0, "Nessun match semantico valido (Veto attivi).", {}

        # 3. Decision
        best_id = max(scores, key=scores.get)
        
        # Calculate ambiguity (delta between top 2 scores)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ambiguity = sorted_scores[0][1] - sorted_scores[1][1] if len(sorted_scores) > 1 else 100.0
        
        # --- EXPERT RULE: LCZ 1 vs LCZ 10 Disambiguation ---
        # Both have high anthropogenic heat, but LCZ 10 heat comes from industries (E-PRTR),
        # while LCZ 1 heat comes from high population density in tall buildings.
        industry_heat = district_data.get('industry_heat', None)
        anthro_heat = district_data.get('anthro_heat', 0)
        z_h = district_data.get('z_h', 0)
        
        # Fallback: if industry_heat not available, use morphology only
        if industry_heat is None:
            industry_ratio = 0.0
        else:
            industry_ratio = industry_heat / anthro_heat if anthro_heat > 0 else 0
        
        if best_id in ['1', '10'] and anthro_heat > 0:
            # If industrial heat is dominant (>50% of total), prefer LCZ 10
            if industry_ratio > 0.5:
                if '10' in scores:
                    scores['10'] += 15  # Strong bonus for industrial dominance
                if '1' in scores:
                    scores['1'] -= 10  # Penalty for non-industrial high heat
                best_id = max(scores, key=scores.get)
            # If industrial heat is low but height is high, prefer LCZ 1
            elif industry_ratio < 0.2 and z_h >= 25.0:
                if '1' in scores:
                    scores['1'] += 10  # Bonus for high-rise residential/commercial
                if '10' in scores:
                    scores['10'] -= 5  # Penalty for mismatch
                best_id = max(scores, key=scores.get)
        
        # Basic tags for UI
        basic_tags = {
            "height": self.tagger.tag_height(district_data.get('z_h', 0)),
            "density": self.tagger.tag_density(district_data.get('bsf', 0)),
            "surface": self.tagger.tag_surface(isf, district_data.get('psf', 0), albedo, esa_class)
        }
        
        return best_id, min(100.0, scores[best_id]), ambiguity, explanations[best_id], basic_tags

from .base import LCZBaseProcessor

class LCZClassificationProcessorV8(LCZBaseProcessor):
    """Processor for Semantic Expert Engine (v8.0)."""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.matcher = LCZSemanticMatcher()

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(f"[LCZ v8 Semantic] {msg}", "FETCH", level)

    def process(self, layer, log_callback=None, force_urban_esa=False, **kwargs):
        """
        Main execution flow for v8.
        1. Context-First: Cluster features into districts (urban + natural).
        2. Perfectionist: Split districts with high internal variance on multiple params.
        3. Semantic Match: Classify districts using rules.
        """
        from ...geometry_utils import create_district_geometry, cluster_natural_areas, split_heterogeneous_clusters_multi
        
        # Sanitization: Ensure existing data doesn't violate field constraints
        self._sanitize_layer(layer)
        
        def log_local(msg, level=Qgis.Info):
            msg_str = str(msg)
            if log_callback: log_callback(msg_str)
            self.log(msg_str, level)

        log_local("📖 Avvio Motore Esperto Semantico (v8.0 Enhanced)...")

        # 1. Separate Urban vs Natural features
        urban_features = []
        natural_features = []
        
        for feat in layer.getFeatures():
            b_frac = feat.attribute(FieldNames.BUILDING_FRAC)
            try:
                val = float(b_frac) if b_frac is not None and str(b_frac) != 'NULL' else 0.0
                if val >= 10.0:
                    urban_features.append(feat)
                else:
                    natural_features.append(feat)
            except (ValueError, TypeError):
                natural_features.append(feat)
        
        log_local(f"🏙️ Celle urbane: {len(urban_features)}, 🌲 Celle naturali: {len(natural_features)}")
        
        if not urban_features and not natural_features:
            log_local("ℹ️ Nessuna cella trovata. Classificazione v8 terminata.", Qgis.Warning)
            return 0

        # 2. Urban Districts: BUILDING-BASED clustering
        urban_clusters = []
        unclustered_urban_cells = []  # Cells with buildings but not in any cluster
        
        if urban_features:
            log_local("🏗️ Clustering urbano basato sugli edifici...")
            
            # Load buildings layer
            buildings_path = os.path.join(self.dm.get_data_dir_path(), "unified", FileNames.BUILDINGS)
            
            if os.path.exists(buildings_path):
                from qgis.core import QgsVectorLayer, QgsSpatialIndex
                buildings_layer = QgsVectorLayer(buildings_path, "buildings", "ogr")
                
                if buildings_layer.isValid() and buildings_layer.featureCount() > 0:
                    log_local(f"📦 Edifici caricati: {buildings_layer.featureCount()}")
                    
                    # Check CRS and prepare transformation if needed
                    from qgis.core import QgsCoordinateTransform
                    transform = None
                    if buildings_layer.crs() != layer.crs():
                        transform = QgsCoordinateTransform(
                            buildings_layer.crs(), 
                            layer.crs(), 
                            QgsProject.instance()
                        )
                        log_local(f"🔄 Trasformazione CRS: {buildings_layer.crs().authid()} -> {layer.crs().authid()}")
                    
                    # 2a. Extract building centroids and heights for clustering
                    building_data = []
                    building_feats = list(buildings_layer.getFeatures())
                    
                    for bld in building_feats:
                        geom = bld.geometry()
                        if geom and not geom.isEmpty():
                            # Transform geometry to grid CRS if needed
                            if transform:
                                geom.transform(transform)
                            
                            centroid = geom.centroid().asPoint()
                            # Try to get height from building
                            height = 0
                            for h_field in ['height', 'z_h', 'H', 'z', 'h_mean']:
                                h_val = bld.attribute(h_field) if bld.fields().indexFromName(h_field) != -1 else None
                                if h_val is not None and str(h_val) not in ('NULL', ''):
                                    try:
                                        height = float(h_val)
                                        break
                                    except:
                                        pass
                            building_data.append({
                                'feat': bld,
                                'centroid': [centroid.x(), centroid.y()],
                                'height': height,
                                'geom': geom
                            })
                    
                    if building_data:
                        # 2b. Cluster buildings by proximity + height
                        import numpy as np
                        from sklearn.cluster import DBSCAN
                        
                        # Prepare clustering data: [x, y, height_scaled]
                        spatial_scale = 50.0  # Buildings within 50m can be same cluster
                        height_weight = 2.0   # Height difference matters
                        
                        cluster_input = []
                        for bd in building_data:
                            cluster_input.append([
                                bd['centroid'][0] / spatial_scale,
                                bd['centroid'][1] / spatial_scale,
                                bd['height'] / 10.0 * height_weight  # Normalize height
                            ])
                        
                        cluster_input = np.array(cluster_input)
                        
                        # DBSCAN with eps=0.7 for tighter clusters, min_samples=2 to avoid singletons
                        db = DBSCAN(eps=0.7, min_samples=2).fit(cluster_input)
                        building_labels = db.labels_
                        
                        # 2c. Group buildings by cluster
                        building_clusters = {}
                        for i, label in enumerate(building_labels):
                            if label not in building_clusters:
                                building_clusters[label] = []
                            building_clusters[label].append(building_data[i])
                        
                        log_local(f"🏘️ Cluster di edifici: {len(building_clusters)}")
                        
                        # 2d. For each building cluster, find intersecting grid cells
                        # Build spatial index for grid cells
                        cell_index = QgsSpatialIndex()
                        cell_lookup = {}
                        for uf in urban_features:
                            cell_index.addFeature(uf)
                            cell_lookup[uf.id()] = uf
                        
                        cells_assigned = set()
                        
                        for cluster_id, buildings in building_clusters.items():
                            # Union of all building geometries in this cluster
                            building_geoms = [b['geom'] for b in buildings]
                            cluster_footprint = QgsGeometry.unaryUnion(building_geoms)
                            
                            if cluster_footprint and not cluster_footprint.isEmpty():
                                # Buffer slightly to catch adjacent cells
                                buffered = cluster_footprint.buffer(15.0, 2)
                                
                                # Find grid cells intersecting this cluster
                                candidate_ids = cell_index.intersects(buffered.boundingBox())
                                cluster_cells = []
                                
                                for cid in candidate_ids:
                                    if cid in cells_assigned:
                                        continue
                                    cell = cell_lookup.get(cid)
                                    if cell and cell.geometry().intersects(buffered):
                                        cluster_cells.append(cell)
                                        cells_assigned.add(cid)
                                
                                if cluster_cells:
                                    urban_clusters.append(cluster_cells)
                        
                        # Cells with buildings but not assigned to any cluster
                        for uf in urban_features:
                            if uf.id() not in cells_assigned:
                                unclustered_urban_cells.append(uf)
                        
                        # --- SPLITTING: Break up heterogeneous districts ---
                        # Thresholds for splitting: if std deviation exceeds these, split
                        split_thresholds = {
                            FieldNames.ROUGHNESS_HEIGHT: 4.0,   # Height variance > 4m
                            FieldNames.BUILDING_FRAC: 15.0,     # BSF variance > 15%
                            FieldNames.SVF_MEAN: 0.15           # SVF variance > 0.15
                        }
                        
                        # Apply splitting to each cluster
                        split_clusters = []
                        for cluster_cells in urban_clusters:
                            if len(cluster_cells) < 5:
                                # Too small to split meaningfully
                                split_clusters.append(cluster_cells)
                                continue
                            
                            # Check heterogeneity and split if needed
                            sub_clusters = split_heterogeneous_clusters_multi(
                                cluster_cells,
                                labels=[0] * len(cluster_cells),  # All same label initially
                                params_thresholds=split_thresholds
                            )
                            split_clusters.extend(sub_clusters)
                        
                        original_count = len(urban_clusters)
                        urban_clusters = split_clusters
                        log_local(f"✂️ Splitting distretti: {original_count} → {len(urban_clusters)}")
                        
                        
                        log_local(f"🏢 Distretti urbani (da edifici): {len(urban_clusters)}")
                        log_local(f"📍 Celle urbane isolate: {len(unclustered_urban_cells)}")
                    else:
                        log_local("⚠️ Nessun dato edificio valido, fallback a clustering celle", Qgis.Warning)
                        urban_clusters = [[f] for f in urban_features]  # Each cell is its own district
                else:
                    log_local("⚠️ Layer edifici non valido, fallback a clustering celle", Qgis.Warning)
                    urban_clusters = [[f] for f in urban_features]
            else:
                log_local("⚠️ Layer edifici non trovato, fallback a clustering celle", Qgis.Warning)
                urban_clusters = [[f] for f in urban_features]

        # 4. Natural Districts: Canopy-based clustering
        natural_clusters = []
        if natural_features and len(natural_features) > 3:
            log_local("🌲 Clustering aree naturali (canopy + SVF)...")
            
            natural_labels = cluster_natural_areas(
                natural_features,
                canopy_field=FieldNames.ROUGHNESS_HEIGHT,
                min_cluster_size=3,
                spatial_scale=60.0
            )
            
            # Group by label
            natural_groups = {}
            for i, label in enumerate(natural_labels):
                if label == -1:
                    continue
                if label not in natural_groups:
                    natural_groups[label] = []
                natural_groups[label].append(natural_features[i])
            
            natural_clusters = list(natural_groups.values())
            log_local(f"🌳 Distretti naturali: {len(natural_clusters)}")
        
        # Combine all clusters with type flag: (features, is_natural)
        final_clusters = [(c, False) for c in urban_clusters] + [(c, True) for c in natural_clusters]
        log_local(f"📊 Totale distretti: {len(final_clusters)}")

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
            ('lcz_ambiguity', QMetaType.Double, 0),
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
            FieldNames.ANTHROPOGENIC_HEAT: 'anthro_heat',
            'industry_heat': 'industry_heat'  # NEW: For LCZ 1 vs 10 disambiguation
        }
        
        # ESA WorldCover Context (Majority sampling)
        # NOTE: Use geometry centroid as key, not feature ID (IDs differ between layers)
        esa_path = os.path.join(self.dm.get_data_dir_path(), FolderNames.UNIFIED, FileNames.LANDUSE)
        esa_lookup = {}  # Key: "x,y" centroid string -> Value: ESA class
        if os.path.exists(esa_path):
            log_local("⏳ Analisi ESA WorldCover per rinforzo semantico...")
            import processing
            res = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer, 'INPUT_RASTER': esa_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'esa_',
                'STATISTICS': [9], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            for feat in res['OUTPUT'].getFeatures():
                v = feat.attribute(res['OUTPUT'].fields().indexFromName('esa_majority'))
                if v is not None and str(v) not in ('NULL', ''):
                    # Use centroid as key (rounded to avoid floating point issues)
                    centroid = feat.geometry().centroid().asPoint()
                    key = f"{round(centroid.x(), 2)},{round(centroid.y(), 2)}"
                    esa_lookup[key] = int(float(v))
            log_local(f"🗺️ ESA lookup popolato: {len(esa_lookup)} celle")

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

        for features, is_natural_cluster in final_clusters:
            # Aggregate district parameters
            district_data = {}
            for f_name, p_key in field_to_param.items():
                # Check if field exists in layer (robustness for optional fields like industry_heat)
                if layer.fields().indexFromName(f_name) == -1:
                    continue
                vals = [float(f.attribute(f_name)) for f in features if f.attribute(f_name) is not None and str(f.attribute(f_name)) != 'NULL']
                district_data[p_key] = np.mean(vals) if vals else 0.0
            
            # Majority ESA for district (use centroid key)
            def get_esa_key(feat):
                c = feat.geometry().centroid().asPoint()
                return f"{round(c.x(), 2)},{round(c.y(), 2)}"
            
            luse_vals = [esa_lookup.get(get_esa_key(f)) for f in features if esa_lookup.get(get_esa_key(f)) is not None]
            dist_esa = max(set(luse_vals), key=luse_vals.count) if luse_vals else None

            # Determine class subset based on cluster type
            if force_urban_esa and dist_esa == 50:
                # User preference: Force urban (1-10) + Paved (E) for ESA Built-up
                subset_for_match = built_ids + ['E']
            elif is_natural_cluster:
                # Natural clusters: only natural classes
                subset_for_match = natural_ids
            else:
                # Urban clusters: check for urban voids
                district_ar = district_data.get('aspect_ratio', 0)
                if district_ar < 0.4:  # Near-zero aspect ratio = urban void
                    subset_for_match = built_ids + ['E', 'D']
                else:
                    subset_for_match = built_ids
            
            # Match district against archetypes
            lcz_id, score, ambiguity, explanation, tags = self.matcher.match(district_data, class_subset=subset_for_match, esa_class=dist_esa)

            # Match metrics
            esa_status = "Reinforced" if dist_esa and LCZMappings.ESA_TO_LCZ.get(dist_esa) == lcz_id else "-"
            matches_count = int((score / 100.0) * 10.0)
            vuln = LCZMappings.VULNERABILITY_MAPPING.get(lcz_id, 'Unknown')
            confidence = float(score / 100.0)
            rmsep_val = 1.0 - confidence

            for f in features:
                fid = f.id()
                district_feature_ids.add(fid)
                
                # --- PER-CELL ESA AUTHORITATIVE OVERRIDE ---
                # Each cell's ESA can override the district classification
                cell_esa_key = get_esa_key(f)
                cell_esa = esa_lookup.get(cell_esa_key)
                cell_bsf = f.attribute(FieldNames.BUILDING_FRAC)
                try:
                    cell_bsf = float(cell_bsf) if cell_bsf is not None and str(cell_bsf) != 'NULL' else 0.0
                except:
                    cell_bsf = 0.0
                
                # Apply authoritative ESA rules at cell level
                final_lcz = lcz_id
                final_score = score
                cell_esa_status = esa_status
                
                if cell_esa is not None and cell_bsf < 10.0:
                    # Shrubland (ESA 20) → LCZ C
                    if cell_esa == 20 and final_lcz not in ['C']:
                        final_lcz = 'C'
                        final_score = 95.0
                        cell_esa_status = "ESA Override: Shrubland → C"
                    # Grassland (ESA 30) → LCZ D
                    elif cell_esa == 30 and final_lcz not in ['D']:
                        final_lcz = 'D'
                        final_score = 95.0
                        cell_esa_status = "ESA Override: Grassland → D"
                    # Cropland (ESA 40) → LCZ D
                    elif cell_esa == 40 and final_lcz not in ['D']:
                        final_lcz = 'D'
                        final_score = 95.0
                        cell_esa_status = "ESA Override: Cropland → D"
                    # Bare/sparse (ESA 60) → LCZ F
                    elif cell_esa == 60 and final_lcz not in ['F']:
                        final_lcz = 'F'
                        final_score = 95.0
                        cell_esa_status = "ESA Override: Bare → F"
                    # Water (ESA 80) → LCZ G
                    elif cell_esa == 80 and final_lcz not in ['G']:
                        final_lcz = 'G'
                        final_score = 100.0
                        cell_esa_status = "ESA Override: Water → G"
                
                final_confidence = float(final_score / 100.0)
                final_rmsep = 1.0 - final_confidence
                final_vuln = LCZMappings.VULNERABILITY_MAPPING.get(final_lcz, 'Unknown')
                final_matches = int((final_score / 100.0) * 10.0)
                
                if idx_map[FieldNames.LCZ_CLASS] != -1: layer.changeAttributeValue(fid, idx_map[FieldNames.LCZ_CLASS], final_lcz)
                if idx_map['lcz_score'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_score'], float(final_score))
                if idx_map['lcz_confidence'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_confidence'], final_confidence)
                if idx_map['lcz_ambiguity'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_ambiguity'], float(ambiguity))
                if idx_map['lcz_rmsep'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep'], final_rmsep)
                if idx_map['lcz_rmsep_norm'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep_norm'], final_rmsep)
                if idx_map['lcz_matches'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_matches'], final_matches)
                if idx_map['lcz_vulnerability'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_vulnerability'], final_vuln)
                if idx_map['lcz_esa_fix'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_esa_fix'], cell_esa_status)
            
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
            
            # Diagnostic logging for first 50 districts to understand classification
            if processed_count < 500:
                z_h = district_data.get('z_h', 0)
                bsf = district_data.get('bsf', 0)
                svf = district_data.get('svf_mean', 0)
                log_local(f"📊 Distretto #{processed_count}: z_h={z_h:.1f}m, BSF={bsf:.0f}%, SVF={svf:.2f} → LCZ {lcz_id} ({score:.0f}%)")
            elif len(final_clusters) < 15 or processed_count % 500 == 0:
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
                # Check if field exists (robustness for optional fields like industry_heat)
                if layer.fields().indexFromName(f_name) == -1:
                    continue
                val = feat.attribute(f_name)
                f_data[p_key] = float(val) if val is not None and str(val) != 'NULL' else 0.0
            
            # DETERMINISTIC BOUNDARY: Urban vs Natural
            bsf_val = f_data.get('bsf', 0)
            ar_val = f_data.get('aspect_ratio', 0)
            is_urban_seed = bsf_val >= 10.0
            
            # Use centroid key for ESA lookup
            feat_centroid = feat.geometry().centroid().asPoint()
            feat_esa_key = f"{round(feat_centroid.x(), 2)},{round(feat_centroid.y(), 2)}"
            feat_esa = esa_lookup.get(feat_esa_key)
            
            # --- EXPERT RULE: Urban Void Detection ---
            # If BSF >= 10 but aspect_ratio near 0, it's an "urban void" (piazza, parking)
            # Include E/D classes in the matching subset
            if force_urban_esa and feat_esa == 50:
                subset = built_ids + ['E']
            elif is_urban_seed and ar_val < 0.1:
                subset = built_ids + ['E', 'D']  # Urban void: built + paved/low-plant
            elif is_urban_seed:
                subset = built_ids
            else:
                subset = natural_ids
            lcz_id, score, ambiguity, _, _ = self.matcher.match(f_data, class_subset=subset, esa_class=feat_esa)
            
            esa_status = "Reinforced" if feat_esa and LCZMappings.ESA_TO_LCZ.get(feat_esa) == lcz_id else "-"
            matches_count = int((score / 100.0) * 10.0)
            vuln = LCZMappings.VULNERABILITY_MAPPING.get(lcz_id, 'Unknown')
            confidence = float(score / 100.0)
            rmsep_val = 1.0 - confidence

            fid = feat.id()
            if idx_map[FieldNames.LCZ_CLASS] != -1: layer.changeAttributeValue(fid, idx_map[FieldNames.LCZ_CLASS], lcz_id)
            if idx_map['lcz_score'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_score'], float(score))
            if idx_map['lcz_confidence'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_confidence'], confidence)
            if idx_map['lcz_ambiguity'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_ambiguity'], float(ambiguity))
            if idx_map['lcz_rmsep'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep'], rmsep_val)
            if idx_map['lcz_rmsep_norm'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_rmsep_norm'], rmsep_val)
            if idx_map['lcz_matches'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_matches'], matches_count)
            if idx_map['lcz_vulnerability'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_vulnerability'], vuln)
            if idx_map['lcz_esa_fix'] != -1: layer.changeAttributeValue(fid, idx_map['lcz_esa_fix'], esa_status)
            
            remaining_count += 1

        layer.commitChanges()
        log_local(f"✅ Classificazione v8.0 completata: {processed_count} in distretti, {remaining_count} individuali.")
        return processed_count + remaining_count
