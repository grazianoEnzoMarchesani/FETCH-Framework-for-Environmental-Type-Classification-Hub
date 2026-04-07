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
    
    def process(self, layer, log_callback=None, method='stable', apply_smoothing=True, is_training=False, veto_count=1, adaptive_calibration=False, profile='z-score', force_urban_esa=False):
        """
        Dispatches processing to the selected method.
        """
        # If adaptive calibration is requested, we do two passes
        calibration_overrides = None
        
        if adaptive_calibration:
            if log_callback: log_callback("🔄 [PASSAGGIO 1] Avvio classificazione per calibrazione locale...")
            # Disable training and smoothing for Pass 1 to get "pure" data faster
            self._execute_process(layer, None, method, apply_smoothing=False, is_training=False, veto_count=veto_count, profile=profile, force_urban_esa=force_urban_esa)
            
            if log_callback: log_callback("🔍 Analisi campioni ad alta confidenza per calibrazione...")
            from .calibration_manager import CalibrationManager
            cm = CalibrationManager()
            success, info = cm.calculate_calibration(layer)
            
            if success and info:
                calibration_overrides = cm.get_overrides()
                if log_callback:
                    count = sum([len(v) for v in info.values()])
                    log_callback(f"✅ Calibrazione completata su {count} parametri. Avvio PASSAGGIO 2...")
                    # Save for record
                    cm.save_to_project(self.dm.get_data_dir_path()) 
            else:
                if log_callback: log_callback("⚠ Calibrazione non riuscita (pochi campioni validi). Procedo con parametri standard.")

        # Final Pass (or only pass)
        return self._execute_process(layer, log_callback, method, apply_smoothing, is_training, veto_count, calibration_overrides, profile, force_urban_esa)

    def _execute_process(self, layer, log_callback, method, apply_smoothing, is_training, veto_count, calibration_overrides=None, profile='z-score', force_urban_esa=False):
        if method == 'stable' or method == 'standard':
            from .classification_standard import LCZClassificationProcessorStandard
            if not self.standard_proc:
                self.standard_proc = LCZClassificationProcessorStandard(self.dm)
            return self.standard_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, calibration_overrides=calibration_overrides)
            
        elif method == 'experimental':
            from .classification_experimental import LCZClassificationProcessorExperimental
            if not self.experimental_proc:
                self.experimental_proc = LCZClassificationProcessorExperimental(self.dm)
            return self.experimental_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, calibration_overrides=calibration_overrides)
        
        elif method == 'v1.1' or method == 'weighted':
            from .classification_v1_1 import LCZClassificationProcessorV1_1
            if not hasattr(self, 'v1_1_proc') or not self.v1_1_proc:
                self.v1_1_proc = LCZClassificationProcessorV1_1(self.dm)
            return self.v1_1_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, calibration_overrides=calibration_overrides)

        elif method == 'v2.1' or method == 'weighted_experimental':
            from .classification_v2_1 import LCZClassificationProcessorV2_1
            if not hasattr(self, 'v2_1_proc') or not self.v2_1_proc:
                self.v2_1_proc = LCZClassificationProcessorV2_1(self.dm)
            return self.v2_1_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, calibration_overrides=calibration_overrides)
            
        elif method == 'v3' or method == 'advanced':
            from .classification_v3 import LCZClassificationProcessorV3
            if not self.v3_proc:
                self.v3_proc = LCZClassificationProcessorV3(self.dm)
            return self.v3_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, calibration_overrides=calibration_overrides)
            
        elif method == 'v4' or method == 'fad':
            from .classification_v4_fad import LCZClassificationProcessorFAD
            if not hasattr(self, 'fad_proc') or not self.fad_proc:
                self.fad_proc = LCZClassificationProcessorFAD(self.dm)
            return self.fad_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, calibration_overrides=calibration_overrides)

        elif method == 'v5' or method == 'mahalanobis':
            from .classification_v5_mahalanobis import LCZClassificationProcessorV5
            if not hasattr(self, 'v5_proc') or not self.v5_proc:
                self.v5_proc = LCZClassificationProcessorV5(self.dm)
            return self.v5_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, is_training=is_training, calibration_overrides=calibration_overrides)
            
        elif method == 'v6' or method == 'wzdv':
            from .classification_v6_wzdv import LCZClassificationProcessorV6
            if not hasattr(self, 'v6_proc') or not self.v6_proc:
                self.v6_proc = LCZClassificationProcessorV6(self.dm)
            return self.v6_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, veto_count=veto_count, calibration_overrides=calibration_overrides, profile=profile)
            
        elif method == 'v7' or method == 'object':
            from .classification_v7_rf import LCZClassificationProcessorV7
            if not hasattr(self, 'v7_proc') or not self.v7_proc:
                self.v7_proc = LCZClassificationProcessorV7(self.dm)
            return self.v7_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, is_training=is_training, calibration_overrides=calibration_overrides)
            
        elif method == 'v8' or method == 'semantic':
            from .classification_v8_semantic import LCZClassificationProcessorV8
            if not hasattr(self, 'v8_proc') or not self.v8_proc:
                self.v8_proc = LCZClassificationProcessorV8(self.dm)
            return self.v8_proc.process(layer, log_callback, apply_smoothing=apply_smoothing, is_training=is_training, calibration_overrides=calibration_overrides, force_urban_esa=force_urban_esa)
            
        else:
            return self._execute_process(layer, log_callback, method='stable', apply_smoothing=apply_smoothing, is_training=False, veto_count=1)

