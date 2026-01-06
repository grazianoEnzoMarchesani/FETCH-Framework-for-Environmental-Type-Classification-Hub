# -*- coding: utf-8 -*-
"""
FETCH Plugin - Crystallize Maps Processor

Exports individual styled vector layers for each LCZ parameter.
Each layer contains only the relevant attribute column and is saved
with a QML style file for immediate styling in QGIS.
"""

import os
from qgis.core import (
    QgsVectorLayer, QgsVectorFileWriter, QgsField, QgsFields,
    QgsFeature, QgsWkbTypes, QgsProject, QgsCoordinateTransformContext,
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsFillSymbol,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsStyle, QgsClassificationJenks, QgsMessageLog, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..constants import FolderNames, LCZMappings

# Parameter configurations: (field_name, output_filename, display_label, ramp_or_palette, is_categorized)
CRYSTALLIZE_PARAMS = [
    ('svf_mean', 'svf_mean', 'Sky View Factor', 'Viridis', False),
    ('aspect_ratio', 'aspect_ratio', 'Aspect Ratio', 'Plasma', False),
    ('building_frac', 'building_frac', 'Building Fraction', 'Reds', False),
    ('impervious_frac', 'impervious_frac', 'Impervious Fraction', 'Greys', False),
    ('pervious_frac', 'pervious_frac', 'Pervious Fraction', 'Greens', False),
    ('z_h', 'z_h', 'Roughness Height', 'YlOrBr', False),
    ('terrain_rough', 'terrain_rough', 'Terrain Roughness', 'PuBu', False),
    ('admittance', 'admittance', 'Surface Admittance', 'OrRd', False),
    ('albedo', 'albedo', 'Surface Albedo', 'RdYlGn', False),
    ('anthro_heat', 'anthro_heat', 'Anthropogenic Heat', 'Inferno', False),
    ('lcz_class', 'lcz_class', 'LCZ Class', 'LCZ', True),
    ('lcz_vulnerability', 'lcz_vulnerability', 'Vulnerability', 'VULNERABILITY', True),
]


class CrystallizeMapsProcessor:
    """Exports styled vector layers for each LCZ parameter."""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        
    def process(self, grid_layer, log_callback=None):
        """
        Export all parameters as individual styled vector layers.
        
        Args:
            grid_layer: QgsVectorLayer - the LCZ grid with calculated parameters
            log_callback: Optional logging function
            
        Returns:
            tuple: (success, message, output_dir)
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "FETCH", Qgis.Info)
        
        if not grid_layer or not grid_layer.isValid():
            return False, "Layer griglia non valido.", None
            
        # Create output directory
        base_dir = self.dm.get_project_dir()
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), FolderNames.UNIFIED)
        output_dir = os.path.join(unified_dir, FolderNames.CRYSTALLIZED)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        log(f"📁 Cartella output: {output_dir}")
        
        exported_count = 0
        errors = []
        exported_layers = []  # Track exported layer paths and labels
        
        for field_name, filename, label, style_info, is_categorized in CRYSTALLIZE_PARAMS:
            # Check if field exists in source layer
            field_idx = grid_layer.fields().indexFromName(field_name)
            if field_idx == -1:
                log(f"⚠️ Campo '{field_name}' non trovato, saltato.")
                continue
                
            try:
                log(f"🔄 Esportando {label}...")
                output_path = os.path.join(output_dir, f"{filename}.gpkg")
                success = self._export_single_layer(
                    grid_layer, field_name, filename, label, 
                    style_info, is_categorized, output_dir
                )
                if success:
                    exported_count += 1
                    exported_layers.append((output_path, label))
                    log(f"✅ {label} esportato.")
                else:
                    errors.append(field_name)
            except Exception as e:
                log(f"❌ Errore esportando {label}: {str(e)}")
                errors.append(field_name)
        
        # Load layers into QGIS project group
        if exported_layers:
            self._load_layers_to_group(exported_layers, log)
                
        if errors:
            return True, f"Esportati {exported_count} layer, {len(errors)} errori.", output_dir
        return True, f"Esportati {exported_count} layer con successo.", output_dir
    
    def _load_layers_to_group(self, layer_paths, log):
        """Load exported layers into a QGIS layer group."""
        from qgis.core import QgsProject, QgsVectorLayer, QgsLayerTreeGroup
        
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        
        # Create or find the group
        group_name = "💎 Mappe Cristallizzate"
        group = root.findGroup(group_name)
        if group is None:
            group = root.insertGroup(0, group_name)
        else:
            # Clear existing layers in group
            for child in group.children():
                group.removeChildNode(child)
        
        log(f"📂 Caricamento layer nel gruppo '{group_name}'...")
        
        for layer_path, label in layer_paths:
            if os.path.exists(layer_path):
                layer = QgsVectorLayer(layer_path, label, "ogr")
                if layer.isValid():
                    # Load QML style if exists
                    qml_path = layer_path.replace('.gpkg', '.qml')
                    if os.path.exists(qml_path):
                        layer.loadNamedStyle(qml_path)
                    
                    # Add to project (not to legend root)
                    project.addMapLayer(layer, False)
                    # Add to group
                    group.addLayer(layer)
        
        # Collapse and position the group
        group.setExpanded(False)
        
    def _export_single_layer(self, source_layer, field_name, filename, label, 
                              style_info, is_categorized, output_dir):
        """Export a single parameter as a styled vector layer."""
        
        # Get source field
        source_fields = source_layer.fields()
        field_idx = source_fields.indexFromName(field_name)
        source_field = source_fields.at(field_idx)
        
        # Create output layer with single field
        output_path = os.path.join(output_dir, f"{filename}.gpkg")
        
        # Define fields for new layer
        new_fields = QgsFields()
        new_fields.append(QgsField(field_name, source_field.type(), source_field.typeName(),
                                    source_field.length(), source_field.precision()))
        
        # Get CRS and geometry type from source
        crs = source_layer.crs()
        geom_type = source_layer.wkbType()
        
        # Create writer options
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.driverName = "GPKG"
        save_options.fileEncoding = "UTF-8"
        
        # Create the output file
        writer = QgsVectorFileWriter.create(
            output_path, new_fields, geom_type, crs,
            QgsCoordinateTransformContext(), save_options
        )
        
        if writer.hasError() != QgsVectorFileWriter.NoError:
            return False
            
        # Copy features with only the target field
        for feature in source_layer.getFeatures():
            new_feat = QgsFeature()
            new_feat.setGeometry(feature.geometry())
            new_feat.setAttributes([feature.attribute(field_idx)])
            writer.addFeature(new_feat)
            
        del writer  # Flush and close
        
        # Load the exported layer temporarily to apply and save style
        temp_layer = QgsVectorLayer(output_path, filename, "ogr")
        if not temp_layer.isValid():
            return False
            
        # Create and apply renderer
        if is_categorized:
            renderer = self._create_categorized_renderer(temp_layer, field_name, style_info)
        else:
            renderer = self._create_graduated_renderer(temp_layer, field_name, style_info)
            
        if renderer:
            temp_layer.setRenderer(renderer)
            
            # Save as QML sidecar file
            qml_path = os.path.join(output_dir, f"{filename}.qml")
            temp_layer.saveNamedStyle(qml_path)
            
        return True
        
    def _create_graduated_renderer(self, layer, field_name, ramp_name):
        """Create a graduated symbol renderer using the specified color ramp."""
        field_idx = layer.fields().indexFromName(field_name)
        if field_idx == -1:
            return None
            
        style = QgsStyle.defaultStyle()
        color_ramp = style.colorRamp(ramp_name)
        if not color_ramp:
            color_ramp = style.colorRamp('Spectral')
        if not color_ramp:
            return None
            
        # Collect values
        values = []
        for feat in layer.getFeatures():
            val = feat.attribute(field_idx)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass
                    
        if not values:
            return None
            
        # Create Jenks classification
        num_classes = min(10, len(set(values)))
        if num_classes < 2:
            num_classes = 2
            
        classifier = QgsClassificationJenks()
        classes = classifier.classes(values, num_classes)
        
        # Build ranges
        ranges = []
        for i, cls in enumerate(classes):
            color = color_ramp.color(i / (len(classes) - 1) if len(classes) > 1 else 0.5)
            symbol = QgsFillSymbol.createSimple({
                'color': color.name(),
                'outline_style': 'no'
            })
            label = f"{cls.lowerBound():.2f} - {cls.upperBound():.2f}"
            ranges.append(QgsRendererRange(cls.lowerBound(), cls.upperBound(), symbol, label))
            
        return QgsGraduatedSymbolRenderer(field_name, ranges)
        
    def _create_categorized_renderer(self, layer, field_name, palette_type):
        """Create a categorized symbol renderer using LCZ or Vulnerability palette."""
        field_idx = layer.fields().indexFromName(field_name)
        if field_idx == -1:
            return None
            
        if palette_type == 'LCZ':
            palette = LCZMappings.COLORS
            label_map = LCZMappings.CLASSES
        elif palette_type == 'VULNERABILITY':
            palette = LCZMappings.VULNERABILITY_COLORS
            label_map = {v: v for v in LCZMappings.VULNERABILITY_ORDER}
        else:
            return None
            
        # Get unique values from layer
        unique_values = layer.uniqueValues(field_idx)
        
        categories = []
        for val in unique_values:
            if val is None:
                continue
            str_val = str(val)
            color_hex = palette.get(str_val, '#ff00ff')
            
            symbol = QgsFillSymbol.createSimple({
                'color': color_hex,
                'outline_style': 'no'
            })
            
            label = label_map.get(str_val, str_val)
            categories.append(QgsRendererCategory(val, symbol, str(label), True))
            
        return QgsCategorizedSymbolRenderer(field_name, categories)
