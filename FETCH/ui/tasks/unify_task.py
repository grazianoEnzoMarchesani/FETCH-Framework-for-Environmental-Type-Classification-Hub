# -*- coding: utf-8 -*-
"""
FETCH Unify Task

Background task for unifying and clipping all downloaded data.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis
from ...core.exceptions import FetchError, FetchWarning, FetchCriticalError


class UnifyTask(QgsTask):
    """Task for unifying and clipping data in the background."""
    
    def __init__(self, data_manager, extent, crs):
        super().__init__("Unificazione Dati FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.extent = extent
        self.crs = crs
        self.success = False
        self.message = ""
        self.output_paths = []

    def run(self):
        def task_log(msg, level=Qgis.Info): 
            QgsMessageLog.logMessage(msg, "FETCH", level)
        
        try:
            self.success, self.message, self.output_paths = self.data_manager.unify_and_clip_data(
                self.extent, self.crs, log_callback=task_log
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
