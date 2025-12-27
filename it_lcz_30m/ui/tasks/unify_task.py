# -*- coding: utf-8 -*-
"""
FETCH Unify Task

Background task for unifying and clipping all downloaded data.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis


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
        def task_log(msg): 
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        try:
            self.success, self.message, self.output_paths = self.data_manager.unify_and_clip_data(
                self.extent, self.crs, log_callback=task_log
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False
