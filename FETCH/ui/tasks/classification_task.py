# -*- coding: utf-8 -*-
"""
FETCH Classification Task

Background task for running final LCZ classification.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis
from ...core.exceptions import FetchError, FetchWarning, FetchCriticalError


class ClassificationTask(QgsTask):
    """Task for running final LCZ classification in the background."""
    
    def __init__(self, data_manager, grid_path, method='stable', apply_smoothing=True, is_training=False, veto_count=1, adaptive_calibration=False, profile='z-score', force_urban_esa=False):
        super().__init__("Classificazione LCZ Finale", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.grid_path = grid_path
        self.method = method
        self.apply_smoothing = apply_smoothing
        self.is_training = is_training
        self.veto_count = veto_count
        self.adaptive_calibration = adaptive_calibration
        self.profile = profile
        self.force_urban_esa = force_urban_esa
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg, level=Qgis.Info):
            QgsMessageLog.logMessage(msg, "FETCH", level)

        try:
            self.success, self.message, self.output_path = self.data_manager.run_lcz_classification(
                grid_path=self.grid_path,
                log_callback=task_log,
                method=self.method,
                apply_smoothing=self.apply_smoothing,
                is_training=self.is_training,
                veto_count=self.veto_count,
                adaptive_calibration=self.adaptive_calibration,
                profile=self.profile,
                force_urban_esa=self.force_urban_esa
            )
            return self.success
        except FetchWarning as w:
            task_log(f"⚠ Avviso: {w.user_message}", Qgis.Warning)
            return True
        except FetchCriticalError as e:
            self.message = e.user_message
            task_log(f"✗ Errore critico: {e.user_message}", Qgis.Critical)
            return False
        except FetchError as e:
            self.message = e.user_message
            task_log(f"✗ Errore: {e.user_message}", Qgis.Critical if not e.recoverable else Qgis.Warning)
            return e.recoverable
        except Exception as e:
            self.message = f"Errore imprevisto: {str(e)}"
            task_log(self.message, Qgis.Critical)
            return False
