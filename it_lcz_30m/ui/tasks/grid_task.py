# -*- coding: utf-8 -*-
"""
FETCH Grid Task

Background task for creating or applying LCZ grid.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis


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
        def task_log(msg): 
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
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
        except Exception as e:
            self.message = str(e)
            return False
