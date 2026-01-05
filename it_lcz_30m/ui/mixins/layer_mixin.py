# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Layer Management Mixin

Provides methods for QGIS layer management operations.
"""

import os
from qgis.core import QgsProject, QgsRasterLayer


class LayerMixin:
    """Mixin providing layer management functionality."""
    
    def find_valid_grid_layer(self):
        """Find the current valid grid layer in the project."""
        data_dir = os.path.join(
            self.data_manager.get_project_dir() or "", 
            self.data_manager.get_data_dir_name()
        )
        
        grid_names = [
            "Griglia LCZ (30m) - Parametri", "Griglia LCZ (50m) - Parametri",
            "Griglia LCZ (100m) - Parametri", "Griglia LCZ (custom) - Parametri",
            "Griglia LCZ (30m)", "Griglia LCZ (50m)", "Griglia LCZ (100m)", "Griglia LCZ (custom)"
        ]
        
        for name in grid_names:
            layers = QgsProject.instance().mapLayersByName(name)
            for lyr in layers:
                if os.path.normpath(lyr.source()).startswith(os.path.normpath(data_dir)):
                    return lyr
        return None

    def _field_has_values(self, layer, field_name):
        """Check if at least one feature has a valid value in the specified field."""
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            return False
        
        # INCREASED LIMIT: Check up to 1000 features to handle sparse data (like industry)
        count = 0
        for feat in layer.getFeatures():
            val = feat.attribute(idx)
            # Accept any non-null, non-empty string or numeric value
            # Filter out strings like 'NULL', 'N/D', or empty
            str_val = str(val).strip().upper()
            if val is not None and str_val not in ('NULL', '', 'N/D', 'NAN'):
                # For numeric fields, check if they are != 0 if desired, 
                # but generically any content means "processed"
                return True
            count += 1
            if count > 1000:
                break
        return False

    def _load_raster_layer(self, path, layer_name):
        """Helper to load a raster layer into the QGIS project."""
        if not os.path.exists(path):
            return None
        # Remove existing layer with same name in project data dir
        data_dir = os.path.join(
            self.data_manager.get_project_dir() or "", 
            self.data_manager.get_data_dir_name()
        )
        for lyr in QgsProject.instance().mapLayersByName(layer_name):
            if os.path.normpath(lyr.source()).startswith(os.path.normpath(data_dir)):
                QgsProject.instance().removeMapLayer(lyr.id())
        # Add new layer
        layer = QgsRasterLayer(path, layer_name)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return layer
        return None

    def _has_valid_layer(self, name, data_dir):
        """Check if a valid layer with the given name exists in the data directory."""
        layers = QgsProject.instance().mapLayersByName(name)
        for lyr in layers:
            if os.path.normpath(lyr.source()).startswith(os.path.normpath(data_dir)):
                return True
        return False

    def get_data_dir(self):
        """Get the current project data directory path."""
        return os.path.join(
            self.data_manager.get_project_dir() or "", 
            self.data_manager.get_data_dir_name()
        )
