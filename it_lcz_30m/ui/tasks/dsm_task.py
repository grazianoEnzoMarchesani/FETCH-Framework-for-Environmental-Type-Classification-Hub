# -*- coding: utf-8 -*-
"""
FETCH DSM Task

Background task for generating synthetic Digital Surface Model.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis


class DSMTask(QgsTask):
    """Task for generating synthetic DSM in the background."""
    
    def __init__(self, data_manager):
        super().__init__("Generazione DSM FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg): 
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        try:
            self.success, self.message, self.output_path = self.data_manager.create_synthetic_dsm(
                log_callback=task_log, overwrite=True
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False
