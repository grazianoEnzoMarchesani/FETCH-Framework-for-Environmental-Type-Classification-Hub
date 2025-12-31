# -*- coding: utf-8 -*-
"""
LCZ Final Classification Module - WEIGHTED EXPERIMENTAL (v2.1)

Classifies each grid cell using the Experimental (v2.0) logic
(Balanced Score + Match Bonus) but applies a 3x3 spatial kernel (Weighted Contextual)
to input parameters before classification.
"""

from qgis.core import QgsField, Qgis, QgsMessageLog, QgsGeometry, QgsSpatialIndex
from qgis.PyQt.QtCore import QMetaType
from .classification_experimental import LCZClassifierExperimental, LCZClassificationProcessorExperimental

# Centralized constants
from ...constants import LCZMappings

class LCZClassificationProcessorV2_1(LCZClassificationProcessorExperimental):
    """
    Processor that applies Weighted Experimental LCZ classification (v2.1).
    Inherits from Experimental v2.0 to reuse logic and corrections.
    """
    
    def process(self, layer, log_callback=None, apply_smoothing=False):
        """
        Main processing logic for Weighted Experimental v2.1.
        """
        import os
        from qgis.core import QgsFeatureRequest
        
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)
            
        log_local("🧪 Avvio classificazione LCZ WEIGHTED EXPERIMENTAL (v2.1)...")
        if apply_smoothing:
             log_local("⚠ Nota: Lo smoothing post-classificazione è attivo (sconsigliato con v2.1).", Qgis.Warning)
        
        # 1. Field Setup (identical to experimental)
        field_name = 'lcz_class'
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, QMetaType.QString, len=10)])
            layer.updateFields()
            idx = layer.fields().lookupField(field_name)
            
        for f, t, l in [
            ('lcz_vulnerability', QMetaType.QString, 20),
            ('lcz_rmsep', QMetaType.Double, 0),
            ('lcz_matches', QMetaType.Int, 0),
            ('lcz_esa_fix', QMetaType.QString, 20)
        ]:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
                layer.updateFields()

        # 2. Build Spatial Index and Cache Parameters
        spatial_index = QgsSpatialIndex(layer.getFeatures())
        feature_data = {}
        all_features = list(layer.getFeatures())
        param_fields = LCZMappings.FIELD_TO_PARAM
        
        for feat in all_features:
            params = {}
            for field_name_src, param_name in param_fields.items():
                f_idx = layer.fields().indexFromName(field_name_src)
                if f_idx != -1:
                    val = feat.attribute(f_idx)
                    params[param_name] = float(val) if (val is not None and str(val) not in ('NULL', '')) else None
            
            feature_data[feat.id()] = {
                'params': params,
                'geom': QgsGeometry(feat.geometry())
            }

        # 3. ESA Correction Setup (Reusing Experimental process logic)
        from ...constants import FolderNames, FileNames
        base_dir = self.dm.get_project_dir()
        landuse_path = os.path.join(base_dir, self.dm.get_data_dir_name(), FolderNames.UNIFIED, FileNames.LANDUSE)
        esa_lookup = {}
        if os.path.exists(landuse_path):
            import processing
            res = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer, 'INPUT_RASTER': landuse_path, 'RASTER_BAND': 1, 'COLUMN_PREFIX': 'esa_', 'STATISTICS': [9], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            for feat in res['OUTPUT'].getFeatures():
                val = feat.attribute(res['OUTPUT'].fields().indexFromName('esa_majority'))
                if val is not None and str(val) not in ('NULL', ''):
                    esa_lookup[feat.id()] = int(float(val))

        # 4. Main Classification Loop with weighting
        layer.startEditing()
        processed_count = 0
        imp_idx = layer.fields().indexFromName('impervious_frac')
        idx_rmsep = layer.fields().lookupField('lcz_rmsep')
        idx_matches = layer.fields().lookupField('lcz_matches')
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')

        for fid, data in feature_data.items():
            center_params = data['params']
            if not any(v is not None for v in center_params.values()):
                continue
                
            # Weighting logic (Center 2, Neighbors 1)
            bbox = data['geom'].boundingBox()
            bbox.grow(max(bbox.width(), bbox.height()) * 1.5)
            candidate_ids = spatial_index.intersects(bbox)
            
            weighted_params = {}
            for p_name in center_params.keys():
                total_w = 0
                w_sum = 0
                c_val = center_params.get(p_name)
                if c_val is not None:
                    w_sum += c_val * 2
                    total_w += 2
                
                for n_id in candidate_ids:
                    if n_id == fid: continue
                    n_data = feature_data.get(n_id)
                    if n_data:
                        n_val = n_data['params'].get(p_name)
                        if n_val is not None:
                            w_sum += n_val * 1
                            total_w += 1
                
                weighted_params[p_name] = (w_sum / total_w) if total_w > 0 else None

            # Classify using Experimental v2.0 logic on Weighted Params
            try:
                res_classify = LCZClassifierExperimental(weighted_params).classify()
                lcz = res_classify['lcz_class']
                
                if esa_lookup and lcz not in ['N/D', 'ERRORE']:
                    feat_obj = layer.getFeature(fid)
                    imp = float(feat_obj.attribute(imp_idx)) if (imp_idx != -1 and feat_obj.attribute(imp_idx) is not None) else None
                    lcz = self._apply_esa_correction(lcz, esa_lookup.get(fid), imp)
                
                raw_rmsep = res_classify['rmsep']
                rmsep_val = None if (raw_rmsep == float('inf') or raw_rmsep != raw_rmsep) else float(raw_rmsep)
                
                layer.changeAttributeValue(fid, idx, lcz)
                layer.changeAttributeValue(fid, idx_rmsep, rmsep_val)
                layer.changeAttributeValue(fid, idx_matches, res_classify['perfect_matches'])
                layer.changeAttributeValue(fid, idx_vuln, LCZMappings.VULNERABILITY_MAPPING.get(lcz, 'Unknown'))
                processed_count += 1
            except Exception as e:
                self.log(f"Errore v2.1 feature {fid}: {e}", Qgis.Warning)

        layer.commitChanges()
        
        if apply_smoothing:
            log_local("🧹 Applicazione smoothing spaziale aggiuntivo...")
            self._apply_spatial_smoothing(layer, log_callback)
            
        return processed_count
