# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Style Management Mixin

Provides methods for QGIS layer styling operations.
"""

from qgis.core import (
    QgsGraduatedSymbolRenderer, QgsRendererRange, 
    QgsFillSymbol, QgsStyle, QgsClassificationQuantile
)

from ..constants import PARAM_VISUALIZATION


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
            style = QgsStyle.defaultStyle()
            ramp_name = config['ramp']
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
            
            # Apply renderer
            renderer = QgsGraduatedSymbolRenderer(config['field'], ranges)
            grid_layer.setRenderer(renderer)
            grid_layer.triggerRepaint()
            
            self.iface.messageBar().pushMessage(
                "FETCH", 
                f"Stile '{config['label']}' (quantile) applicato alla griglia.", 
                level=3, duration=3
            )
            
        except Exception as e:
            self.iface.messageBar().pushMessage("Errore", f"Impossibile applicare stile: {str(e)}", level=2)
