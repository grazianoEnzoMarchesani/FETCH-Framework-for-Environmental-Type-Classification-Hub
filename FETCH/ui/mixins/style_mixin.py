# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Style Management Mixin

Provides methods for QGIS layer styling operations.
"""

from qgis.core import (
    QgsGraduatedSymbolRenderer, QgsRendererRange, 
    QgsFillSymbol, QgsStyle, QgsClassificationQuantile, QgsClassificationJenks,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol,
    QgsMessageLog, Qgis, QgsFeatureRequest
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor
import random

from ..constants import PARAM_VISUALIZATION
from ...core.constants import LCZMappings


class StyleMixin:
    """Mixin providing layer styling functionality."""
    
    def update_param_indicators(self):
        """Update indicator button states based on data availability in grid."""
        grid_layer = self.find_valid_grid_layer()
        
        if not grid_layer:
            self.params_section.set_all_indicators_disabled()
            return
        
        for param_id, config in PARAM_VISUALIZATION.items():
            field_name = config['field']
            
            # Support both 'lcz_rmsep' and 'lcz_score' for the Error indicator
            if field_name == 'lcz_rmsep':
                # First check if lcz_rmsep has any data
                has_data = self._field_has_values(grid_layer, 'lcz_rmsep')
                if not has_data:
                    # If empty, try lcz_score
                    if grid_layer.fields().indexFromName('lcz_score') != -1:
                        has_data = self._field_has_values(grid_layer, 'lcz_score')
            else:
                has_data = self._field_has_values(grid_layer, field_name)
                
            self.params_section.set_indicator_enabled(param_id, has_data)

    def apply_param_style(self, field_name):
        """Apply graduated color style to the grid layer for the specified parameter."""
        grid_layer = self.find_valid_grid_layer()
        if not grid_layer:
            self.iface.messageBar().pushMessage("Errore", "Nessuna griglia trovata.", level=2)
            return
        config = PARAM_VISUALIZATION.get(field_name)
        if not config:
            self.iface.messageBar().pushMessage("Errore", f"Configurazione non trovata per {field_name}.", level=2)
            return
            
        target_field = config['field']
        # Fallback to lcz_score for Error indicator if lcz_rmsep is missing
        if target_field == 'lcz_rmsep' and grid_layer.fields().indexFromName('lcz_rmsep') == -1:
            if grid_layer.fields().indexFromName('lcz_score') != -1:
                target_field = 'lcz_score'
        
        field_idx = grid_layer.fields().indexFromName(target_field)
        if field_idx == -1:
            self.iface.messageBar().pushMessage("Errore", f"Campo {target_field} non trovato nella griglia.", level=2)
            return
        
        try:
            # Check if this is a categorized renderer (LCZ or Vulnerability)
            if config.get('renderer') == 'categorized':
                categories = []
                
                if target_field == 'lcz_class':
                    palette = LCZMappings.COLORS
                    # Standard LCZ order 1-10, A-G
                    ordered_keys = list(LCZMappings.CLASSES.keys()) + ['N/D']
                elif target_field == 'lcz_vulnerability':
                    palette = LCZMappings.VULNERABILITY_COLORS
                    ordered_keys = LCZMappings.VULNERABILITY_ORDER
                elif target_field == 'lcz_esa_fix':
                    # Dynamic categories for ESA Fix (transitions like "C → D")
                    palette = LCZMappings.COLORS
                    unique_values = grid_layer.uniqueValues(field_idx)
                    ordered_keys = sorted([str(v) for v in unique_values if v is not None])
                elif target_field == 'lcz_matches':
                    # Dynamic categories for Matches using Cividis ramp
                    unique_values = grid_layer.uniqueValues(field_idx)
                    ordered_keys = sorted([v for v in unique_values if v is not None])
                    
                    style = QgsStyle.defaultStyle()
                    ramp = style.colorRamp('Cividis')
                    if not ramp: ramp = style.colorRamp('Viridis')
                    
                    palette = {}
                    for v in ordered_keys:
                        try:
                            # Normalize 0-10 (assuming max 10 matches)
                            val_float = float(v)
                            norm_val = min(max(val_float / 10.0, 0.0), 1.0)
                            color = ramp.color(norm_val)
                            palette[v] = color.name()
                        except:
                            palette[v] = '#ff00ff'
                else:
                    self.iface.messageBar().pushMessage("Errore", f"Mappatura non definita per renderer categorizzato: {field_name}", level=2)
                    return

                for cat_value in ordered_keys:
                    color_hex = None
                    if target_field == 'lcz_esa_fix':
                        if cat_value == '-':
                            color_hex = '#bebebe' # Gray for no fix
                        elif ' → ' in cat_value:
                            target_lcz = cat_value.split(' → ')[-1]
                            color_hex = palette.get(target_lcz, '#ff00ff')
                        else:
                            color_hex = palette.get(cat_value, '#ff00ff')
                    else:
                        color_hex = palette.get(cat_value)
                    
                    if not color_hex:
                        continue
                    
                    symbol = QgsFillSymbol.createSimple({
                        'color': color_hex,
                        'outline_style': 'no'
                    })
                    
                    label = LCZMappings.CLASSES.get(cat_value, cat_value) if target_field == 'lcz_class' else cat_value
                    # ...
                    category = QgsRendererCategory(cat_value, symbol, str(label), True)
                    categories.append(category)
                
                renderer = QgsCategorizedSymbolRenderer(target_field, categories)
            
            else:
                # Graduated renderer (original logic)
                style = QgsStyle.defaultStyle()
                ramp_name = config.get('ramp', 'Spectral')
                color_ramp = style.colorRamp(ramp_name)
                
                if not color_ramp:
                    color_ramp = style.colorRamp('Spectral')
                
                if not color_ramp:
                    self.iface.messageBar().pushMessage("Errore", "Nessuna rampa colore disponibile.", level=2)
                    return
                
                # Collect valid values efficiently (no geometry, limited fields)
                request = QgsFeatureRequest()
                request.setFlags(QgsFeatureRequest.NoGeometry)
                request.setSubsetOfAttributes([field_idx])
                
                all_values = []
                for feat in grid_layer.getFeatures(request):
                    val = feat.attribute(field_idx)
                    if val is not None and str(val) not in ('NULL', ''):
                        try:
                            all_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                
                if not all_values:
                    self.iface.messageBar().pushMessage("Errore", f"Nessun valore valido nel campo {target_field}.", level=2)
                    return

                # Optimization: Limit values for Jenks algorithm (O(n^2) complexity)
                # 20k points is more than enough for representative breaks
                MAX_SAMPLES = 20000
                if len(all_values) > MAX_SAMPLES:
                    values = random.sample(all_values, MAX_SAMPLES)
                else:
                    values = all_values
                
                # Create classification (Jenks/Natural Breaks is better for skewed distributions)
                num_classes = 10
                classifier = QgsClassificationJenks()
                classes = classifier.classes(values, num_classes)
                
                # Build renderer ranges
                ranges = []
                for i, cls in enumerate(classes):
                    color = color_ramp.color(i / (len(classes) - 1) if len(classes) > 1 else 0.5)
                    symbol = QgsFillSymbol.createSimple({
                        'color': color.name(),
                        'outline_style': 'no'
                    })
                    label = f"{cls.lowerBound():.2f} - {cls.upperBound():.2f}"
                    range_item = QgsRendererRange(cls.lowerBound(), cls.upperBound(), symbol, label)
                    ranges.append(range_item)
                
                renderer = QgsGraduatedSymbolRenderer(target_field, ranges)

            # Apply renderer
            grid_layer.setRenderer(renderer)
            grid_layer.triggerRepaint()
            
            # --- Update Legend ---
            legend_items = []
            if config.get('renderer') == 'categorized':
                for cat in categories:
                    if cat.renderState():
                        legend_items.append((cat.symbol().color().name(), cat.label()))
            else:
                for rng in ranges:
                    if rng.renderState():
                        legend_items.append((rng.symbol().color().name(), rng.label()))
            
            if hasattr(self, 'canvas_legend'):
                # Format title: if it's longer than 25 chars, wrap it etc.
                title = config.get('label', field_name)
                self.canvas_legend.update_legend(title, legend_items)

            self.iface.messageBar().pushMessage(
                "FETCH", 
                f"Stile '{config['label']}' applicato alla griglia.", 
                level=3, duration=3
            )
            
            # --- Auto-Snapshot Feature ---
            # Automatically save a high-res snapshot to the project folder
            try:
                import os
                snapshot_dir = self.data_manager.get_snapshot_dir()
                if snapshot_dir:
                    # Create a clean filename from the label
                    clean_label = "".join([c if c.isalnum() else "_" for c in config.get('label', field_name)])
                    # Remove multiple underscores
                    while "__" in clean_label: clean_label = clean_label.replace("__", "_")
                    
                    filename = f"{clean_label}.png"
                    auto_path = os.path.join(snapshot_dir, filename)
                    
                    # Force Qt to process UI events (ensure legend is updated and cleaned)
                    # before taking the high-res snapshot
                    QCoreApplication.processEvents()
                    
                    # We call the dashboard's method
                    if hasattr(self, 'take_high_res_snapshot'):
                        self.take_high_res_snapshot(auto_path=auto_path)
            except Exception as e:
                QgsMessageLog.logMessage(f"Errore auto-snapshot: {str(e)}", "FETCH", Qgis.Warning)
                
        except Exception as e:
            import traceback
            QgsMessageLog.logMessage(f"Errore styling: {traceback.format_exc()}", "FETCH", Qgis.Critical)
            self.iface.messageBar().pushMessage("Errore", f"Impossibile applicare stile: {str(e)}", level=2)
