# -*- coding: utf-8 -*-
"""
FETCH DSM Task

Background task for generating synthetic Digital Surface Model.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis
from ...core.exceptions import FetchError, FetchWarning, FetchCriticalError


class DSMTask(QgsTask):
    """Task for generating synthetic DSM in the background."""
    
    def __init__(self, data_manager):
        super().__init__("Generazione DSM FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg, level=Qgis.Info): 
            QgsMessageLog.logMessage(msg, "FETCH", level)
        
        try:
            self.success, self.message, self.output_path = self.data_manager.create_synthetic_dsm(
                log_callback=task_log, overwrite=True
            )
            return self.success
        except FetchWarning as w:
            task_log(f"⚠ Avviso: {w.user_message}", Qgis.Warning)
            # Non-blocking, continue
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
