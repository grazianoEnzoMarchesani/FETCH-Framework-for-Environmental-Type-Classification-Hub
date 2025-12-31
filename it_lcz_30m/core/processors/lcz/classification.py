# -*- coding: utf-8 -*-
"""
LCZ Classification Dispatcher

Routes classification requests to Standard (Stable), Experimental (v2.0),
or Advanced (v3.0) processor.
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
        self.v3_proc = None
    
    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)
    
    def process(self, layer, log_callback=None, method='stable', apply_smoothing=True):
        """
        Dispatches processing to the selected method.
        
        Args:
            layer: QgsVectorLayer to classify
            log_callback: Function for UI logging
            method: 'stable', 'experimental', or 'v3' (advanced)
        """
        if method == 'stable' or method == 'standard':
            from .classification_standard import LCZClassificationProcessorStandard
            if not self.standard_proc:
                self.standard_proc = LCZClassificationProcessorStandard(self.dm)
            
            if log_callback:
                log_callback("⚠ Utilizzo classificatore STANDARD (Stable - Dec 29)...")
            
            return self.standard_proc.process(layer, log_callback, apply_smoothing=apply_smoothing)
            
        elif method == 'experimental':
            from .classification_experimental import LCZClassificationProcessorExperimental
            if not self.experimental_proc:
                self.experimental_proc = LCZClassificationProcessorExperimental(self.dm)
                
            if log_callback:
                log_callback("🧪 Avvio classificazione LCZ (Experimental - v2.0)...")
                
            return self.experimental_proc.process(layer, log_callback, apply_smoothing=apply_smoothing)
        
        elif method == 'v1.1' or method == 'weighted':
            from .classification_v1_1 import LCZClassificationProcessorV1_1
            if not hasattr(self, 'v1_1_proc') or not self.v1_1_proc:
                self.v1_1_proc = LCZClassificationProcessorV1_1(self.dm)
            
            if log_callback:
                log_callback("🧪 Avvio classificazione LCZ WEIGHTED CONTEXTUAL (v1.1)...")
            
            return self.v1_1_proc.process(layer, log_callback, apply_smoothing=apply_smoothing)

        elif method == 'v2.1' or method == 'weighted_experimental':
            from .classification_v2_1 import LCZClassificationProcessorV2_1
            if not hasattr(self, 'v2_1_proc') or not self.v2_1_proc:
                self.v2_1_proc = LCZClassificationProcessorV2_1(self.dm)
                
            if log_callback:
                log_callback("🧪 Avvio classificazione LCZ WEIGHTED EXPERIMENTAL (v2.1)...")
                
            return self.v2_1_proc.process(layer, log_callback, apply_smoothing=apply_smoothing)
            
        elif method == 'v3' or method == 'advanced':
            from .classification_v3 import LCZClassificationProcessorV3
            if not self.v3_proc:
                self.v3_proc = LCZClassificationProcessorV3(self.dm)
            
            if log_callback:
                log_callback("🚀 Avvio classificazione LCZ ADVANCED (v3.0)...")
            
            return self.v3_proc.process(layer, log_callback, apply_smoothing=apply_smoothing)
            
        else:
            if log_callback:
                log_callback(f"❌ Metodo di classificazione '{method}' non riconosciuto. Uso Standard.")
            return self.process(layer, log_callback, method='stable', apply_smoothing=apply_smoothing)

