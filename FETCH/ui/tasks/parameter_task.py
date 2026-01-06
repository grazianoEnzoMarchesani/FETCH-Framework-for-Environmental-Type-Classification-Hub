# -*- coding: utf-8 -*-
"""
FETCH LCZ Parameter Task

Background task for calculating individual LCZ parameters.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis
from ...core.exceptions import FetchError, FetchWarning, FetchCriticalError


class LCZParameterTask(QgsTask):
    """Task for running LCZ parameter calculation in the background."""
    
    def __init__(self, data_manager, grid_path, parameter_id):
        super().__init__(f"Calcolo LCZ: {parameter_id}", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.grid_path = grid_path
        self.parameter_id = parameter_id
        self.success = False
        self.message = ""
        self.output_path = ""
        self.log_msgs = []

    def run(self):
        def task_log(msg, level=Qgis.Info):
            self.log_msgs.append(msg)
            QgsMessageLog.logMessage(msg, "FETCH", level)

        try:
            self.success, self.message, self.output_path = self.data_manager.calculate_lcz_parameters(
                grid_path=self.grid_path,
                parameter_id=self.parameter_id,
                log_callback=task_log
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
