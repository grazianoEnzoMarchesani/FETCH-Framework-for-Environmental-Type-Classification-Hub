# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Style Management Mixin

Provides methods for QGIS layer styling operations.
"""

from qgis.core import (
    QgsGraduatedSymbolRenderer, QgsRendererRange, 
    QgsFillSymbol, QgsStyle, QgsClassificationQuantile,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol,
    QgsMessageLog, Qgis
)
from qgis.PyQt.QtGui import QColor

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
        
        field_idx = grid_layer.fields().indexFromName(config['field'])
        if field_idx == -1:
            self.iface.messageBar().pushMessage("Errore", f"Campo {config['field']} non trovato nella griglia.", level=2)
            return
        
        try:
            # Check if this is a categorized renderer (LCZ or Vulnerability)
            if config.get('renderer') == 'categorized':
                categories = []
                
                if config['field'] == 'lcz_class':
                    palette = LCZMappings.COLORS
                    # Standard LCZ order 1-10, A-G
                    ordered_keys = list(LCZMappings.CLASSES.keys()) + ['N/D']
                elif config['field'] == 'lcz_vulnerability':
                    palette = LCZMappings.VULNERABILITY_COLORS
                    ordered_keys = LCZMappings.VULNERABILITY_ORDER
                elif config['field'] == 'lcz_esa_fix':
                    # Dynamic categories for ESA Fix (transitions like "C → D")
                    palette = LCZMappings.COLORS
                    unique_values = grid_layer.uniqueValues(field_idx)
                    ordered_keys = sorted([str(v) for v in unique_values if v is not None])
                elif config['field'] == 'lcz_matches':
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
                            palette[v] = '#bebebe'
                else:
                    self.iface.messageBar().pushMessage("Errore", f"Mappatura non definita per renderer categorizzato: {field_name}", level=2)
                    return

                for cat_value in ordered_keys:
                    color_hex = None
                    if config['field'] == 'lcz_esa_fix':
                        if cat_value == '-':
                            color_hex = '#bebebe' # Gray for no fix
                        elif ' → ' in cat_value:
                            target_lcz = cat_value.split(' → ')[-1]
                            color_hex = palette.get(target_lcz, '#bebebe')
                        else:
                            color_hex = palette.get(cat_value, '#bebebe')
                    else:
                        color_hex = palette.get(cat_value)
                    
                    if not color_hex:
                        continue
                    
                    symbol = QgsFillSymbol.createSimple({
                        'color': color_hex,
                        'outline_style': 'no'
                    })
                    
                    label = LCZMappings.CLASSES.get(cat_value, cat_value) if config['field'] == 'lcz_class' else cat_value
                    # Check if cat_value is int for RendererCategory?
                    # The issue was label type. Argument 3 is label (string).
                    # But also QgsRendererCategory takes (value, symbol, label, render). 
                    # If value is integer, we might need to cast it?
                    # Actually, if the field is Integer, value should be int or str?
                    # Usually QVariant accepts int. The error said "argument 3 has unexpected type 'int'". 
                    # Argument 3 is label. So we MUST cast label to string.
                    category = QgsRendererCategory(cat_value, symbol, str(label), True)
                    categories.append(category)
                
                renderer = QgsCategorizedSymbolRenderer(config['field'], categories)
            
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
                
                # Collect valid values
                values = []
                for feat in grid_layer.getFeatures():
                    val = feat.attribute(field_idx)
                    if val is not None and str(val) not in ('NULL', ''):
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                
                if not values:
                    self.iface.messageBar().pushMessage("Errore", f"Nessun valore valido nel campo {config['field']}.", level=2)
                    return
                
                # Create quantile classification
                num_classes = 10
                classifier = QgsClassificationQuantile()
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
                
                renderer = QgsGraduatedSymbolRenderer(config['field'], ranges)

            # Apply renderer
            grid_layer.setRenderer(renderer)
            grid_layer.triggerRepaint()
            
            self.iface.messageBar().pushMessage(
                "FETCH", 
                f"Stile '{config['label']}' applicato alla griglia.", 
                level=3, duration=3
            )
            
        except Exception as e:
            import traceback
            QgsMessageLog.logMessage(f"Errore styling: {traceback.format_exc()}", "FETCH", Qgis.Critical)
            self.iface.messageBar().pushMessage("Errore", f"Impossibile applicare stile: {str(e)}", level=2)
