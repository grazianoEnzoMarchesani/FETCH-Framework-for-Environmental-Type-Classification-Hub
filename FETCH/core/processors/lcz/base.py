# -*- coding: utf-8 -*-

import os
import processing
from qgis.core import (
    QgsProject, Qgis, QgsMessageLog, QgsVectorLayer, 
    QgsField, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsGeometry, QgsFeatureRequest
)
from qgis.PyQt.QtCore import QVariant, QMetaType

class LCZBaseProcessor:
    def __init__(self, data_manager):
        self.dm = data_manager

    def _ensure_field(self, layer, field_name, field_type=QMetaType.Double):
        """Ensures a field exists in the layer, creating it if necessary."""
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            layer.dataProvider().addAttributes([QgsField(field_name, field_type)])
            layer.updateFields()
            idx = layer.fields().indexFromName(field_name)
        return idx

    def _sanitize_layer(self, layer):
        """
        Truncates strings in fields known to cause length overflow issues 
        (like lcz_esa_fix) to prevent Crashes during zonal statistics.
        """
        target_fields = ['lcz_esa_fix', 'lcz_vulnerability', 'lcz_class']
        field_indices = {}
        for f_name in target_fields:
            idx = layer.fields().indexFromName(f_name)
            if idx != -1:
                field_indices[idx] = layer.fields().at(idx).length()

        if not field_indices:
            return

        # Check if any feature actually needs sanitization to avoid empty commits
        needs_sanitization = False
        for feat in layer.getFeatures():
            for idx, max_len in field_indices.items():
                if max_len <= 0: continue
                val = feat.attribute(idx)
                if isinstance(val, str) and len(val) > max_len:
                    needs_sanitization = True
                    break
            if needs_sanitization: break

        if not needs_sanitization:
            return

        layer.startEditing()
        for feat in layer.getFeatures():
            for idx, max_len in field_indices.items():
                if max_len <= 0: continue # No limit
                val = feat.attribute(idx)
                if isinstance(val, str) and len(val) > max_len:
                    # Truncate to fit
                    layer.changeAttributeValue(feat.id(), idx, val[:max_len])
        
        if not layer.commitChanges():
            errs = layer.commitErrors()
            self.log(f"Sanitization failed: {', '.join(errs)}", Qgis.Warning)

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def _ensure_link_id(self, layer, sanitize=True):
        """Ensure the layer has a unique _link_id field for robust joining."""
        # Sanitization: Only if explicitly requested (usually first time)
        if sanitize:
            self._sanitize_layer(layer)
        
        idx = layer.fields().indexFromName('_link_id')
        if idx == -1:
            layer.startEditing()
            # Double check if someone added it since last check
            if layer.fields().indexFromName('_link_id') == -1:
                layer.dataProvider().addAttributes([QgsField('_link_id', QMetaType.Int)])
                layer.updateFields()
            
            idx = layer.fields().indexFromName('_link_id')
            for i, feat in enumerate(layer.getFeatures()):
                layer.changeAttributeValue(feat.id(), idx, i)
            
            if not layer.commitChanges():
                errs = layer.commitErrors()
                self.log(f"Failed to create _link_id: {', '.join(errs)}", Qgis.Warning)
        return idx

    def _calc_zonal_mean(self, layer, target_path, raster_path, field_name, prefix, log_callback=None):
        """Helper to calculate zonal mean for a specific raster."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        # Ensure destination field exists
        self._ensure_field(layer, field_name)

        if not os.path.exists(raster_path):
            log_local(f"Raster mancante: {os.path.basename(raster_path)}", Qgis.Warning)
            return 0
        
        # Ensure robust linking ID
        idx_link = self._ensure_link_id(layer)
        
        log_local(f"Calcolo statistiche zonali per {field_name}...")
        res = processing.run("native:zonalstatisticsfb", {
            'INPUT': layer, 'INPUT_RASTER': raster_path, 'COLUMN_PREFIX': f'_tmp_{prefix}_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        temp_layer = res['OUTPUT']
        idx_dst = layer.fields().indexFromName(field_name)
        idx_src = temp_layer.fields().indexFromName(f'_tmp_{prefix}_mean')
        idx_temp_link = temp_layer.fields().indexFromName('_link_id')
        
        if idx_src == -1:
            log_local(f"Errore: colonna temporanea _tmp_{prefix}_mean non trovata.", Qgis.Warning)
            return 0

        # Map back using _link_id
        val_map = {}
        for feat in temp_layer.getFeatures():
            link_id = feat.attribute(idx_temp_link)
            val = feat.attribute(idx_src)
            if link_id is not None and val is not None and str(val) != 'NULL':
                val_map[link_id] = val

        layer.startEditing()
        processed = 0
        for feat in layer.getFeatures():
            link_id = feat.attribute(idx_link)
            if link_id in val_map:
                try:
                    layer.changeAttributeValue(feat.id(), idx_dst, round(float(val_map[link_id]), 3))
                    processed += 1
                except: pass
        layer.commitChanges()
        return processed
