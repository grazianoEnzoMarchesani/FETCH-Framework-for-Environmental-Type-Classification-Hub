# -*- coding: utf-8 -*-
"""
LCZ Classification Dispatcher

Routes classification requests to either the Standard (Stable) or 
Experimental (v2.0) processor.
"""

from qgis.core import Qgis, QgsMessageLog

class LCZClassificationProcessor:
    """
    Main dispatcher for LCZ classification.
    """
    
    def __init__(self, data_manager):
        self.dm = data_manager
        self.standard_proc = None
        self.experimental_proc = None
    
    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)
    
    def process(self, layer, log_callback=None, method='stable'):
        """
        Dispatches processing to the selected method.
        
        Args:
            layer: QgsVectorLayer to classify
            log_callback: Function for UI logging
            method: 'stable' (Dec 29) or 'experimental' (v2.0)
        """
        if method == 'stable' or method == 'standard':
            from .classification_standard import LCZClassificationProcessorStandard
            if not self.standard_proc:
                self.standard_proc = LCZClassificationProcessorStandard(self.dm)
            
            if log_callback:
                log_callback("⚠ Utilizzo classificatore STANDARD (Stable - Dec 29)...")
            
            return self.standard_proc.process(layer, log_callback)
            
        elif method == 'experimental':
            from .classification_experimental import LCZClassificationProcessorExperimental
            if not self.experimental_proc:
                self.experimental_proc = LCZClassificationProcessorExperimental(self.dm)
                
            if log_callback:
                log_callback("🧪 Avvio classificazione LCZ (Experimental - v2.0)...")
                
            return self.experimental_proc.process(layer, log_callback)
            
        else:
            if log_callback:
                log_callback(f"❌ Metodo di classificazione '{method}' non riconosciuto. Uso Standard.")
            return self.process(layer, log_callback, method='stable')
