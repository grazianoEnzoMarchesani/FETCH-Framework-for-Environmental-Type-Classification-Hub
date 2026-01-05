# -*- coding: utf-8 -*-
"""
LCZ Classification Module - DISTRICT-BASED RANDOM FOREST (v7.0)

Implements a district-based classification approach:
1. Building clustering (HDBSCAN/Multidimensional)
2. Convex/Concave Hull generation for urban zones
3. Random Forest classification trained on Knowledge Base
4. Urban-Natural sequential integration
"""

import numpy as np
import os
from qgis.core import (QgsVectorLayer, QgsField, Qgis, QgsMessageLog, 
                       QgsFeature, QgsProject, QgsGeometry, QgsVectorFileWriter)
from qgis.PyQt.QtCore import QMetaType

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import csv

# Centralized constants
try:
    from ...constants import LCZMappings, FileNames, FolderNames, FieldNames
except ImportError:
    # Fallback for direct testing
    class LCZMappings: 
        CLASSES = {'1': 'C1', '2': 'C2'}
        PARAMETERS = {}
        FIELD_TO_PARAM = {'svf': 'sky_view_factor'}
    class FolderNames: KNOWLEDGE_BASE = "knowledge_base"
    class FieldNames: LCZ_CLASS = "lcz_class"

class LCZKnowledgeBaseLoaderV7:
    """Handles loading Knowledge Base samples from the project directory."""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.params_ordered = list(LCZMappings.FIELD_TO_PARAM.values())

    def get_kb_dir(self):
        """Returns the project's knowledge base directory."""
        if not self.dm: return None
        path = os.path.join(
            self.dm.get_project_dir(), 
            self.dm.get_data_dir_name(), 
            FolderNames.KNOWLEDGE_BASE
        )
        return path if os.path.exists(path) else None

    def load_all_samples(self):
        """Loads all samples from CSV files in the KB directory."""
        kb_dir = self.get_kb_dir()
        if not kb_dir:
            return pd.DataFrame()

        all_data = []
        for lcz_id in LCZMappings.CLASSES.keys():
            class_file = os.path.join(kb_dir, f"lcz_{lcz_id}.csv")
            if os.path.exists(class_file):
                try:
                    df = pd.read_csv(class_file)
                    df['lcz_id'] = lcz_id
                    all_data.append(df)
                except Exception:
                    continue
        
        if not all_data:
            return pd.DataFrame()
            
        return pd.concat(all_data, ignore_index=True)

class LCZClassifierRF:
    """Classifies clusters using Random Forest logic."""
    
    def __init__(self, parameters=None, knowledge_base_path=None):
        self.parameters = parameters or list(LCZMappings.FIELD_TO_PARAM.values())
        self.kb_path = knowledge_base_path
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.feature_importance = {}
        self.is_trained = False

    def _generate_synthetic_samples(self, n_per_class=50):
        """Generates synthetic samples based on Stewart & Oke archetypes."""
        synthetic_data = []
        for lcz_id, ranges in LCZMappings.PARAMETERS.items():
            for _ in range(n_per_class):
                sample = {'lcz_id': lcz_id}
                for p_name, (min_v, max_v) in ranges.items():
                    # Handle infinity
                    effective_max = max_v if max_v != float('inf') else min_v * 2
                    effective_min = min_v if min_v != float('-inf') else 0
                    
                    val = np.random.uniform(effective_min, effective_max)
                    sample[p_name] = val
                synthetic_data.append(sample)
        return pd.DataFrame(synthetic_data)

    def train_model(self, kb_df=None):
        """
        Trains the Random Forest model. 
        If kb_df is empty, uses synthetic data from archetypes.
        """
        # 1. Prepare Data
        if kb_df is None or kb_df.empty:
            train_df = self._generate_synthetic_samples()
        else:
            # Mix real data with some synthetic data to ensure all classes are represented
            synthetic_df = self._generate_synthetic_samples(n_per_class=20)
            train_df = pd.concat([kb_df, synthetic_df], ignore_index=True)

        # Ensure all required parameters are present
        X = train_df[self.parameters].fillna(train_df[self.parameters].mean())
        y = train_df['lcz_id']

        # 2. Train
        self.model.fit(X, y)
        self.is_trained = True

        # 3. Extract importance
        self.feature_importance = dict(zip(self.parameters, self.model.feature_importances_))
        return self.feature_importance

    def predict_cluster(self, cluster_features, class_subset=None):
        """
        Predicts LCZ for a given set of parameters.
        cluster_features: dict {param_name: value}
        class_subset: optional list of LCZ IDs to restrict prediction to
        """
        if not self.is_trained:
            return None, 0.0

        # Prepare input vector
        vec = []
        for p in self.parameters:
            vec.append(cluster_features.get(p, 0.0))
        
        X_test = pd.DataFrame([vec], columns=self.parameters)
        
        # If subset is provided, handle filtered prediction
        if class_subset:
            probs = self.model.predict_proba(X_test)[0]
            class_labels = self.model.classes_
            
            # Map labels to probabilities
            label_prob = dict(zip(class_labels, probs))
            
            # Filter for requested subset and pick best
            best_id = None
            best_prob = -1.0
            
            for lid in class_subset:
                if lid in label_prob:
                    if label_prob[lid] > best_prob:
                        best_prob = label_prob[lid]
                        best_id = lid
            
            # If nothing in subset found (unlikely), fallback to standard
            if best_id:
                return best_id, best_prob

        # Standard Prediction
        lcz_id = self.model.predict(X_test)[0]
        probs = self.model.predict_proba(X_test)[0]
        confidence = np.max(probs)
        
        return lcz_id, confidence

class LCZClassificationProcessorV7:
    """Processor for District-Based Random Forest (v7.0)."""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.kb_loader = LCZKnowledgeBaseLoaderV7(data_manager)
        self.classifier = None

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(f"[LCZ v7] {msg}", "FETCH", level)

    def process(self, layer, log_callback=None, **kwargs):
        """
        Main execution flow for v7.
        """
        from ...geometry_utils import cluster_multidimensional, create_district_geometry

        def log_local(msg, level=Qgis.Info):
            msg_str = str(msg)
            # Always update status bar
            if log_callback: log_callback(msg_str)
            # Always log to persistent MessageLog (FETCH tab) for debugging
            self.log(msg_str, level)

        log_local("🧠 Preparazione motore Random Forest (v7.0)...")
        
        # 1. Load KB and Train
        kb_df = self.kb_loader.load_all_samples()
        field_to_param = LCZMappings.FIELD_TO_PARAM
        param_names = list(field_to_param.values()) # Internal names for RF
        
        self.classifier = LCZClassifierRF(parameters=param_names)
        importance = self.classifier.train_model(kb_df)
        
        log_local("📊 Feature Importance calcolata:")
        for p, imp in sorted(importance.items(), key=lambda x: x[1], reverse=True):
            log_local(f"   - {p}: {imp:.3f}")

        # 2. Identify features with buildings (Urban Seeds)
        log_local("🏙️ Identificazione semi urbani (soglia BSF >= 10%)...")
        urban_features = []
        all_features = list(layer.getFeatures())
        fields = [f.name() for f in layer.fields()]
        log_local(f"🔍 Scansione di {len(all_features)} celle totali... Campi trovati: {', '.join(fields[:5])}...")
        
        if FieldNames.BUILDING_FRAC not in fields:
            log_local(f"⚠️ ATTENZIONE: Campo '{FieldNames.BUILDING_FRAC}' non trovato nel layer!", Qgis.Warning)
        
        for feat in all_features:
            b_frac = feat.attribute(FieldNames.BUILDING_FRAC)
            try:
                val = float(b_frac) if b_frac is not None and str(b_frac) != 'NULL' else 0.0
                # Correcting threshold: Data is in 0-100 scale, so 10% is 10.0
                if val >= 10.0:
                    urban_features.append(feat)
            except (ValueError, TypeError):
                continue
        
        log_local(f"📍 Trovati {len(urban_features)} semi urbani con BSF >= 10%.")
        
        # Debug: range of BSF found
        if all_features:
            bsfs = []
            for f in all_features:
                b = f.attribute(FieldNames.BUILDING_FRAC)
                if b is not None and str(b) != 'NULL': bsfs.append(float(b))
            if bsfs:
                log_local(f"📊 Statistiche BSF: Min={min(bsfs):.3f}, Max={max(bsfs):.3f}, Media={sum(bsfs)/len(bsfs):.3f}")
        
        if not urban_features:
            log_local("ℹ️ Nessun edificio trovato. Classificazione v7 terminata.", Qgis.Warning)
            return 0

        # 3. Multidimensional Clustering (Refined: 45m Scale + Height Weight + BSF)
        log_local(f"🧩 Clustering di {len(urban_features)} celle (Scala: 45m, Parametri: Altezza, BSF)...")
        
        # we cluster on Position, Building Height and Building Fraction
        cluster_fields = [FieldNames.ROUGHNESS_HEIGHT, FieldNames.BUILDING_FRAC]
        
        # Weights: 
        # - Height: 3.5 (1 floor ~ 3m difference will likely trigger a cluster break)
        # - BSF: 1.5 (Density changes also help define district boundaries)
        cluster_weights = {
            FieldNames.ROUGHNESS_HEIGHT: 3.5,
            FieldNames.BUILDING_FRAC: 1.5
        }
        
        # eps=1.2 with 45m scaling means:
        # - Spatial radius: ~55m (tight connection)
        # - Height sensitivity: 3m floor is significant
        labels = cluster_multidimensional(
            urban_features, 
            cluster_fields, 
            eps=1.2, 
            min_samples=2,
            spatial_scale=45.0,
            weights=cluster_weights
        )
        
        # 4. Group by Cluster and Classify
        clusters = {}
        for i, label in enumerate(labels):
            if label == -1: continue # Noise
            if label not in clusters: clusters[label] = []
            clusters[label].append(urban_features[i])
            
        log_local(f"🏢 Trovati {len(clusters)} distretti urbani coerenti.")
        
        # 5. Classify Districts and Natural Areas
        layer.startEditing()
        processed_count = 0
        district_feature_ids = set()
        
        # Phase 1: Urban Districts (Unified Classification)
        for cid, features in clusters.items():
            cluster_data = {p: [] for p in param_names}
            for f in features:
                district_feature_ids.add(f.id())
                for f_name, p_name in field_to_param.items():
                    val = f.attribute(f_name)
                    if val is not None: cluster_data[p_name].append(float(val))
            
            mean_params = {p: (np.mean(vals) if vals else 0.0) for p, vals in cluster_data.items()}
            # District MUST be urban (1-10)
            built_ids = list(LCZMappings.BUILT_CLASSES)
            lcz_id, confidence = self.classifier.predict_cluster(mean_params, class_subset=built_ids)
            
            idx_class = layer.fields().lookupField(FieldNames.LCZ_CLASS)
            idx_conf = layer.fields().lookupField('lcz_confidence')
            idx_score = layer.fields().lookupField('lcz_score')
            
            if idx_class != -1:
                for f in features:
                    layer.changeAttributeValue(f.id(), idx_class, lcz_id)
                    if idx_conf != -1:
                        layer.changeAttributeValue(f.id(), idx_conf, float(confidence))
                    if idx_score != -1:
                        layer.changeAttributeValue(f.id(), idx_score, float(confidence))
            
            processed_count += len(features)

        # Phase 1.5: District Visualization (NEW)
        log_local("📐 Generazione layer vettoriale dei distretti (Hulls)...")
        district_path = os.path.join(self.dm.get_data_dir_path(), "distretti_lcz.gpkg")
        
        # Create memory layer for districts - Use MultiPolygon for robust compatibility
        district_layer = QgsVectorLayer("MultiPolygon?crs=" + layer.crs().authid(), "Distretti LCZ", "memory")
        district_layer.startEditing()
        district_layer.addAttribute(QgsField("cluster_id", QMetaType.Int))
        district_layer.addAttribute(QgsField("lcz_id", QMetaType.QString))
        district_layer.addAttribute(QgsField("confidence", QMetaType.Double))
        district_layer.updateFields()
        
        for cid, features in clusters.items():
            # Collect geometries for the district
            geoms = [f.geometry() for f in features if not f.geometry().isEmpty()]
            if not geoms: continue
            
            # Create robust, non-overlapping district geometry
            district_geom = create_district_geometry(geoms)
            
            if district_geom and not district_geom.isEmpty():
                # Force conversion to MultiPolygon to match layer type
                district_geom.convertToMultiType()
                feat = QgsFeature(district_layer.fields())
                feat.setGeometry(district_geom)
                
                # We need the prediction again or store it earlier
                cluster_data = {p: [] for p in param_names}
                for f in features:
                    for f_name, p_name in field_to_param.items():
                        val = f.attribute(f_name)
                        if val is not None: cluster_data[p_name].append(float(val))
                mean_params = {p: (np.mean(vals) if vals else 0.0) for p, vals in cluster_data.items()}
                
                # District visualization MUST also reflect the built id
                built_ids = list(LCZMappings.BUILT_CLASSES)
                lcz_id, confidence = self.classifier.predict_cluster(mean_params, class_subset=built_ids)
                
                feat.setAttributes([int(cid), str(lcz_id), float(confidence)])
                district_layer.addFeature(feat)

        district_layer.commitChanges()
        
        # Save and Load District Layer
        # Use modern writeAsVectorFormatV3 to avoid DeprecationWarning
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.driverName = "GPKG"
        save_options.fileEncoding = "UTF-8"
        
        QgsVectorFileWriter.writeAsVectorFormatV3(
            district_layer, 
            district_path, 
            layer.transformContext(), 
            save_options
        )
        final_dist_layer = QgsVectorLayer(district_path, "Distretti LCZ v7", "ogr")
        QgsProject.instance().addMapLayer(final_dist_layer)

        # Phase 2: Natural Areas (Individual Classification for non-district features)
        log_local("🌿 Classificazione aree naturali (fuori dai distretti)...")
        natural_count = 0
        for feat in layer.getFeatures():
            if feat.id() in district_feature_ids: continue
            
            f_params = {}
            for f_name, p_name in field_to_param.items():
                val = feat.attribute(f_name)
                f_params[p_name] = float(val) if val is not None else 0.0
                
            lcz_id, confidence = self.classifier.predict_cluster(f_params)
            
            idx_class = layer.fields().lookupField(FieldNames.LCZ_CLASS)
            idx_conf = layer.fields().lookupField('lcz_confidence')
            idx_score = layer.fields().lookupField('lcz_score')
            
            if idx_class != -1:
                layer.changeAttributeValue(feat.id(), idx_class, lcz_id)
                if idx_conf != -1:
                    layer.changeAttributeValue(feat.id(), idx_conf, float(confidence))
                if idx_score != -1:
                    layer.changeAttributeValue(feat.id(), idx_score, float(confidence))
            
            natural_count += 1

        layer.commitChanges()
        log_local(f"✅ Classificazione v7.0 completata: {processed_count} urban, {natural_count} natural.")
        
        return processed_count + natural_count
