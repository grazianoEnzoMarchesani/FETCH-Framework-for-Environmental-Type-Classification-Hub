# -*- coding: utf-8 -*-
"""
FETCH Grid Task

Background task for creating or applying LCZ grid.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis
from ...core.exceptions import FetchError, FetchWarning, FetchCriticalError


class GridTask(QgsTask):
    """Task for creating the LCZ grid in the background."""
    
    def __init__(self, data_manager, extent, crs, cell_size=None, existing_layer=None):
        super().__init__("Creazione Griglia FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.extent = extent
        self.crs = crs
        self.cell_size = cell_size
        self.existing_layer = existing_layer
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg, level=Qgis.Info): 
            QgsMessageLog.logMessage(msg, "FETCH", level)
        
        try:
            if self.cell_size:
                self.success, self.message, self.output_path = self.data_manager.create_lcz_grid(
                    self.extent, self.crs, cell_size=self.cell_size, log_callback=task_log
                )
            elif self.existing_layer:
                self.success, self.message, self.output_path = self.data_manager.use_existing_grid(
                    self.existing_layer, self.extent, self.crs, log_callback=task_log
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
