# -*- coding: utf-8 -*-
"""
LCZ Classification Module - MAHALANOBIS ADAPTIVE (v5.0)

Implements Mahalanobis distance classification with a persistent Knowledge Base.
Identifies "pure" samples matching Stewart & Oke (2012) ranges and uses 
them to calculate class-specific covariance matrices.

Key features:
- Persistent CSV-based training data (Knowledge Base)
- Adaptive Mahalanobis Distance (considers parameter correlations)
- Automatic collection of new high-quality samples from each run
- Fallback to Fuzzy Distance (v4.0) for classes with insufficient data
"""

import os
import csv
import numpy as np
from qgis.core import QgsVectorLayer, QgsField, Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QMetaType

from ...constants import LCZMappings, FileNames, FolderNames, FieldNames
from .classification_v4_fad import LCZClassifierFAD


class LCZKnowledgeBaseManager:
    """
    Handles persistence of LCZ training samples collected during runs.
    Uses one CSV file per LCZ class (e.g., lcz_1.csv, lcz_A.csv) for better transparency.
    """
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.params_ordered = list(LCZMappings.FIELD_TO_PARAM.values())

    @property
    def kb_dir(self):
        """Dynamic Knowledge Base directory path based on the current project."""
        path = os.path.join(
            self.dm.get_project_dir(), 
            self.dm.get_data_dir_name(), 
            FolderNames.KNOWLEDGE_BASE
        )
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except: pass
        return path

    def _get_class_file(self, lcz_id):
        """Returns path to the CSV file for a specific LCZ class."""
        return os.path.join(self.kb_dir, f"lcz_{lcz_id}.csv")

    def load_samples(self):
        """
        Loads samples from individual class CSV files.
        Returns: {lcz_id: [v_1, v_2, ...]} where v is a list of 10 parameters.
        """
        samples = {lcz_id: [] for lcz_id in LCZMappings.CLASSES.keys()}
        
        for lcz_id in samples.keys():
            class_file = self._get_class_file(lcz_id)
            if not os.path.exists(class_file):
                continue
                
            try:
                with open(class_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vec = []
                        for p in self.params_ordered:
                            val = row.get(p)
                            if val in (None, ''):
                                vec = None # Invalid sample
                                break
                            vec.append(float(val))
                        
                        if vec:
                            samples[lcz_id].append(vec)
            except Exception as e:
                QgsMessageLog.logMessage(f"KB Load Error ({lcz_id}): {e}", "FETCH", Qgis.Warning)
                
        return samples

    MAX_SAMPLES_PER_CLASS = 2000

    def append_samples(self, new_samples):
        """
        Appends new UNIQUE valid samples to their respective class files.
        Enforces a cap of MAX_SAMPLES_PER_CLASS to maintain performance.
        new_samples: list of dicts {'lcz_id': ID, 'param1': val, ...}
        """
        if not new_samples:
            return
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Group samples by lcz_id
        grouped = {}
        for s in new_samples:
            lcz_id = s.get('lcz_id')
            if lcz_id:
                if lcz_id not in grouped: grouped[lcz_id] = []
                grouped[lcz_id].append(s)
        
        header = self.params_ordered + ['source_run']
        
        total_added = 0
        for lcz_id, s_list in grouped.items():
            class_file = self._get_class_file(lcz_id)
            
            # Load existing samples to prevent duplicates and check cap
            existing_vectors = set()
            if os.path.exists(class_file):
                try:
                    with open(class_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Create a tuple of param values for hashing
                            v = tuple(round(float(row.get(p, 0.0)), 4) for p in self.params_ordered)
                            existing_vectors.add(v)
                except: pass

            # Check if we already reached the cap for this class
            if len(existing_vectors) >= self.MAX_SAMPLES_PER_CLASS:
                continue

            file_exists = os.path.exists(class_file)
            try:
                with open(class_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    if not file_exists:
                        writer.writeheader()
                    
                    for s in s_list:
                        if len(existing_vectors) >= self.MAX_SAMPLES_PER_CLASS:
                            break # Hard stop if limit reached during addition
                            
                        # Create tuple for duplicate check
                        v_new = tuple(round(float(s.get(p, 0.0)), 4) for p in self.params_ordered)
                        if v_new not in existing_vectors:
                            row = {p: s[p] for p in self.params_ordered}
                            row['source_run'] = timestamp
                            writer.writerow(row)
                            existing_vectors.add(v_new)
                            total_added += 1
                        
            except Exception as e:
                QgsMessageLog.logMessage(f"KB Save Error ({lcz_id}): {e}", "FETCH", Qgis.Warning)
        
        return total_added


class LCZClassifierMahalanobis:
    """
    Classifies features using Mahalanobis distance if enough training data exists.
    """
    
    MIN_SAMPLES_FOR_MAHALANOBIS = 15
    
    def __init__(self, parameters, knowledge_base_data=None):
        self.parameters = {k: v for k, v in parameters.items() if v is not None}
        self.kb_data = knowledge_base_data or {}
        self.params_ordered = list(LCZMappings.FIELD_TO_PARAM.values())
        
        # Prepare vector for current cell
        self.cell_vector = []
        for p in self.params_ordered:
            self.cell_vector.append(self.parameters.get(p, 0.0))
        self.cell_vector = np.array(self.cell_vector)

    def _calculate_mahalanobis_distance(self, x, samples):
        """
        Calculates Mahalanobis Distance using pseudo-inverse for robustness.
        """
        data = np.array(samples)
        mu = np.mean(data, axis=0)
        
        # Calculate covariance and add small regularization
        cov = np.cov(data, rowvar=False) + np.eye(len(self.params_ordered)) * 1e-4
        
        try:
            # Use pseudo-inverse for singular or near-singular matrices
            inv_cov = np.linalg.pinv(cov)
            diff = x - mu
            md2 = diff.T @ inv_cov @ diff
            return float(np.sqrt(max(0, md2)))
        except:
            return float('inf')

    def is_pure_sample(self):
        """
        Checks if the current cell perfectly matches all Stewart & Oke ranges.
        Returns the matching LCZ ID if pure, else None.
        """
        if len(self.parameters) < 10:
            return None
            
        for lcz_id, ranges in LCZMappings.PARAMETERS.items():
            matches_all = True
            for p_name, (min_v, max_v) in ranges.items():
                val = self.parameters.get(p_name)
                if val is None or not (min_v <= val <= max_v):
                    matches_all = False
                    break
            if matches_all:
                return lcz_id
        return None

    def classify(self):
        """
        Main classification strategy:
        1. Try Mahalanobis distance for classes with enough samples.
        2. Fallback to Fuzzy/RMSEP (v4_fad) for others or if MD fails.
        """
        # Run FAD as primary/fallback logic to get initial scores
        fad_result = LCZClassifierFAD(self.parameters).classify()
        
        # If FAD is already very confident (>0.9), stick with it or use it as proxy
        # But here we want to prioritize Mahalanobis if possible
        
        m_sims = {}
        distances_dict_raw = {}
        
        for lcz_id, samples in self.kb_data.items():
            if len(samples) >= self.MIN_SAMPLES_FOR_MAHALANOBIS:
                d = self._calculate_mahalanobis_distance(self.cell_vector, samples)
                if d != float('inf'):
                    distances_dict_raw[lcz_id] = d
                    # Convert distance to a similarity score [0, 1] for blending
                    # 1/(1+d) is a simple way to map [0, inf] to [1, 0]
                    m_sims[lcz_id] = 1.0 / (1.0 + d)
        
        # Blend FAD scores with Mahalanobis similarities
        final_scores = {}
        fad_scores = LCZClassifierFAD(self.parameters).calculate_scores()
        
        for lcz_id, f_score in fad_scores.items():
            m_sim = m_sims.get(lcz_id, 0.0)
            if m_sim > 0:
                # 60% theory (FAD), 40% local data (Mahalanobis)
                final_scores[lcz_id] = (f_score * 0.6) + (m_sim * 0.4)
            else:
                final_scores[lcz_id] = f_score
        
        # Preparation of raw distances for the result dictionary
        distances_raw = {k: round(v, 3) for k, v in distances_dict_raw.items()}
        
        if not final_scores:
            res = fad_result.copy()
            res['distances'] = distances_raw
            return res
            
        sorted_scores = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        best_id, best_score = sorted_scores[0]
        
        # Confidence logic
        if len(sorted_scores) > 1:
            margin = best_score - sorted_scores[1][1]
            confidence = (best_score * 0.7 + margin * 0.3)
        else:
            confidence = best_score

        # Rejection threshold (same as v4)
        if best_score < 0.25:
            return {
                'lcz_class': 'N/D', 
                'score': round(best_score, 3), 
                'confidence': round(confidence, 2),
                'distances': distances_raw
            }

        return {
            'lcz_class': best_id, 
            'score': round(best_score, 3), 
            'confidence': round(confidence, 2),
            'distances': distances_raw
        }


class LCZClassificationProcessorV5:
    """
    Orchestrates Adaptive Classification and Knowledge Base growth.
    """
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.kb_manager = LCZKnowledgeBaseManager(data_manager)

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def process(self, layer, log_callback=None, apply_smoothing=True, is_training=False):
        import time
        
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        log_local("🧠 Avvio classificazione MAHALANOBIS ADAPTIVE (v5.0)...")
        if is_training:
            log_local("📝 Modalità ADDESTRAMENTO attiva: i nuovi campioni puri verranno salvati.")
        
        # Load Knowledge Base
        kb_data = self.kb_manager.load_samples()
        sample_counts = {k: len(v) for k, v in kb_data.items() if len(v) > 0}
        if sample_counts:
            # Create a summary string like "F: 120, 6: 15, ..."
            summary = ", ".join([f"{k}: {v}" for k, v in sample_counts.items()])
            log_local(f"📊 Knowledge Base carica ({sum(sample_counts.values())} campioni): {summary}")
        else:
            log_local("ℹ Knowledge Base vuota. Inizializzazione con logica Fuzzy...")

        # --- Field Setup ---
        field_defs = [
            ('lcz_class', QMetaType.QString, 10),
            ('lcz_score', QMetaType.Double, 0),
            ('lcz_rmsep', QMetaType.Double, 0),
            ('lcz_confidence', QMetaType.Double, 0),
            ('lcz_vulnerability', QMetaType.QString, 20)
        ]
        
        # Add Distance fields definitions
        dist_fields = [f"dist_{l_id}" for l_id in LCZMappings.CLASSES.keys()]
        for df in dist_fields:
            field_defs.append((df, QMetaType.Double, 0))
            
        layer.startEditing()
        for f, t, l in field_defs:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
        layer.updateFields()
        
        idx_class = layer.fields().lookupField('lcz_class')
        idx_score = layer.fields().lookupField('lcz_score')
        idx_rmsep = layer.fields().lookupField('lcz_rmsep')
        idx_conf = layer.fields().lookupField('lcz_confidence')
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')
        
        # Mapping for distance field indices
        idx_distances = {l_id: layer.fields().lookupField(f"dist_{l_id}") for l_id in LCZMappings.CLASSES.keys()}

        # Detailed Logging before start
        ready_m = [k for k, v in sample_counts.items() if v >= LCZClassifierMahalanobis.MIN_SAMPLES_FOR_MAHALANOBIS]
        ready_f = [k for k in LCZMappings.CLASSES.keys() if k not in ready_m]
        
        if ready_m:
            log_local(f"✅ Classi ADATTIVE (Mahalanobis): {', '.join(ready_m)}")
        if ready_f:
            log_local(f"ℹ️ Classi TEORICHE (Fuzzy Fallback): {', '.join(ready_f)}")
        
        log_local("⚙️ Elaborazione celle in corso... (progressi nel log ogni 50.000 unità)")

        processed = 0
        total_count = layer.featureCount()
        new_pure_samples = []
        
        for feat in layer.getFeatures():
            params = {}
            for f_src, p_name in LCZMappings.FIELD_TO_PARAM.items():
                v = feat.attribute(f_src)
                params[p_name] = float(v) if (v is not None and str(v) not in ('NULL', '')) else None
            
            if any(v is not None for v in params.values()):
                classifier = LCZClassifierMahalanobis(params, kb_data)
                
                # Check for "pure" morphological samples to grow the KB
                if is_training:
                    pure_lcz = classifier.is_pure_sample()
                    if pure_lcz:
                        # Only add if haven't reached the cap for this run (optimization)
                        current_kb_count = len(kb_data.get(pure_lcz, []))
                        if current_kb_count < self.kb_manager.MAX_SAMPLES_PER_CLASS:
                            sample = {'lcz_id': pure_lcz}
                            sample.update({p: params.get(p, 0.0) for p in classifier.params_ordered})
                            new_pure_samples.append(sample)
                
                # Execute classification
                res = classifier.classify()
                lcz = res['lcz_class']
                
                layer.changeAttributeValue(feat.id(), idx_class, lcz)
                if idx_score != -1: layer.changeAttributeValue(feat.id(), idx_score, float(res.get('score', 0)))
                if idx_rmsep != -1: layer.changeAttributeValue(feat.id(), idx_rmsep, float(res.get('score', 0)))
                if idx_conf != -1: layer.changeAttributeValue(feat.id(), idx_conf, float(res.get('confidence', 0)))
                if idx_vuln != -1: layer.changeAttributeValue(feat.id(), idx_vuln, LCZMappings.VULNERABILITY_MAPPING.get(lcz, 'Unknown'))
                
                # Save individual Mahalanobis distances
                if 'distances' in res:
                    for l_id, d_val in res['distances'].items():
                        idx_d = idx_distances.get(l_id, -1)
                        if idx_d != -1:
                            layer.changeAttributeValue(feat.id(), idx_d, d_val)
                
                processed += 1
                
                # Periodic real-time update
                if processed % 50000 == 0:
                    perc = (processed / total_count) * 100
                    log_local(f"⏳ Avanzamento: {processed:,} / {total_count:,} celle ({perc:.1f}%)")
        
        layer.commitChanges()
        
        # Save new samples to KB
        if is_training and new_pure_samples:
            added = self.kb_manager.append_samples(new_pure_samples)
            if added > 0:
                log_local(f"✨ Aggiunti {added} nuovi campioni unici alla Knowledge Base.")
            else:
                log_local("ℹ Nessun nuovo campione unico trovato rispetto ai dati esistenti.")
            
        log_local(f"✓ Classificazione v5.0 completata: {processed} celle.")
        return processed
