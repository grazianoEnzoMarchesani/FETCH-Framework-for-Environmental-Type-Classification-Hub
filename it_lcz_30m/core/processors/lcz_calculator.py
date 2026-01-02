# -*- coding: utf-8 -*-

import os
from qgis.core import (
    QgsProject, Qgis, QgsMessageLog, QgsVectorLayer, 
    QgsField
)
from qgis.PyQt.QtCore import QMetaType

# Import specialized modules
from .lcz.sky_view_factor import SkyViewFactorProcessor
from .lcz.surface_fractions import SurfaceFractionsProcessor
from .lcz.surface_albedo import SurfaceAlbedoProcessor
from .lcz.aspect_ratio import AspectRatioProcessor
from .lcz.roughness_height import RoughnessHeightProcessor
from .lcz.terrain_roughness import TerrainRoughnessProcessor
from .lcz.surface_admittance import SurfaceAdmittanceProcessor
from .lcz.anthropogenic_heat import AnthropogenicHeatProcessor
from .lcz.classification import LCZClassificationProcessor

class LCZCalculator:
    def __init__(self, data_manager):
        self.dm = data_manager
        
        # Initialize sub-processors
        self.svf_proc = SkyViewFactorProcessor(data_manager)
        self.fractions_proc = SurfaceFractionsProcessor(data_manager)
        self.albedo_proc = SurfaceAlbedoProcessor(data_manager)
        self.aspect_proc = AspectRatioProcessor(data_manager)
        self.roughness_proc = RoughnessHeightProcessor(data_manager)
        self.terrain_proc = TerrainRoughnessProcessor(data_manager)
        self.admittance_proc = SurfaceAdmittanceProcessor(data_manager)
        self.anthro_proc = AnthropogenicHeatProcessor(data_manager)
        self.classification_proc = LCZClassificationProcessor(data_manager)

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def calculate_svf(self, log_callback=None, search_radius=100, num_sectors=16, canopy_opacity=0.7, method='ground'):
        """Calculates Sky View Factor (SVF) raster - delegated to specialized module."""
        return self.svf_proc.calculate_raster(log_callback, search_radius, num_sectors, canopy_opacity, method=method, overwrite=True)

    def calculate_parameters(self, grid_path, parameter_id=None, log_callback=None):
        """Calculates LCZ parameters for each grid cell - delegated to specialized modules."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        PARAM_MAP = {
            'sky_view_factor': ('svf_mean', 'Sky View Factor'),
            'surface_fractions': (None, 'Surface Fractions (BSF/ISF/PSF)'),
            'surface_albedo': ('albedo', 'Surface Albedo'),
            'aspect_ratio': ('aspect_ratio', 'Aspect Ratio (H/W) & Roughness H (zH)'),
            'terrain_roughness_class': ('terrain_rough', 'Terrain Roughness Class'),
            'surface_admittance': ('admittance', 'Surface Admittance'),
            'anthropogenic_heat_output': ('anthro_heat', 'Anthropogenic Heat Output'),
        }

        if parameter_id and parameter_id not in PARAM_MAP:
             return False, f"Parametro {parameter_id} non supportato", None

        # Prepare working file
        target_path = grid_path
        if not grid_path.endswith("_lcz_params.gpkg"):
            target_path = grid_path.replace(".gpkg", "_lcz_params.gpkg")
            if not os.path.exists(target_path):
                import shutil
                shutil.copy2(grid_path, target_path)

        layer = QgsVectorLayer(target_path, "lcz_grid", "ogr")
        if not layer.isValid(): return False, "Griglia non valida", None
        
        # Ensure fields exist
        REQUIRED = [
            ('svf_mean', QMetaType.Double), 
            ('building_frac', QMetaType.Double), 
            ('impervious_frac', QMetaType.Double), 
            ('pervious_frac', QMetaType.Double), 
            ('albedo', QMetaType.Double),
            ('aspect_ratio', QMetaType.Double), 
            ('z_h', QMetaType.Double), 
            ('terrain_rough', QMetaType.Double), 
            ('admittance', QMetaType.Double),
            ('z0_value', QMetaType.Double),
            ('anthro_heat', QMetaType.Double)
        ]
        
        missing = [QgsField(name, dtype) for name, dtype in REQUIRED if layer.fields().indexFromName(name) == -1]
        if missing:
            layer.dataProvider().addAttributes(missing)
            layer.updateFields()

        processed = 0
        if parameter_id == 'sky_view_factor':
            # Check if legacy SVF should be used instead of ground SVF
            method = 'ground'
            if os.path.exists(os.path.join(self.dm.get_project_dir(), self.dm.get_data_dir_name(), "unified", "svf_legacy_10m.tif")):
                # If legacy exists but user is running LCZ classification, maybe we should ask?
                # For now, let's keep it consistent: process() in sky_view_factor.py will be updated to take method.
                pass
            processed = self.svf_proc.process(layer, target_path, log_callback)

        elif parameter_id == 'surface_albedo':
            processed = self.albedo_proc.process(layer, target_path, log_callback)

        elif parameter_id == 'surface_fractions':
            processed = self.fractions_proc.process(layer, target_path, log_callback)

        elif parameter_id == 'aspect_ratio':
            # Run Roughness Height first as it is a prerequisite for Aspect Ratio
            processed_zh = self.roughness_proc.process(layer, target_path, log_callback)
            processed_ar = self.aspect_proc.process(layer, log_callback)
            processed = processed_ar # Reporting AR processed count

        elif parameter_id == 'terrain_roughness_class':
            processed = self.terrain_proc.process(layer, log_callback)

        elif parameter_id == 'surface_admittance':
            processed = self.admittance_proc.process(layer, target_path, log_callback)

        elif parameter_id == 'anthropogenic_heat_output':
            processed = self.anthro_proc.process(layer, log_callback)

        return True, f"Calcolo completato ({processed} celle)", target_path

    def classify_lcz(self, grid_path, log_callback=None, method='stable', apply_smoothing=True, is_training=False):
        """Classifies grid cells into LCZ classes based on calculated parameters."""
        def log_local(msg, level=Qgis.Info):
            if log_callback: log_callback(msg)
            self.log(msg, level)

        # Use params file if exists, otherwise original grid
        target_path = grid_path
        if not grid_path.endswith("_lcz_params.gpkg"):
            params_path = grid_path.replace(".gpkg", "_lcz_params.gpkg")
            if os.path.exists(params_path):
                target_path = params_path

        layer = QgsVectorLayer(target_path, "lcz_grid", "ogr")
        if not layer.isValid():
            return False, "Griglia non valida", None

        log_local(f"Metodo di classificazione: {method} - Input: {target_path}")
        processed = self.classification_proc.process(
            layer, log_callback, method=method, apply_smoothing=apply_smoothing, is_training=is_training
        )

        return True, f"Classificazione completata ({processed} celle)", target_path
