# -*- coding: utf-8 -*-
"""
FETCH Classification Task

Background task for running final LCZ classification.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis


class ClassificationTask(QgsTask):
    """Task for running final LCZ classification in the background."""
    
    def __init__(self, data_manager, grid_path):
        super().__init__("Classificazione LCZ Finale", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.grid_path = grid_path
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg):
            QgsMessageLog.logMessage(msg, "FETCH", Qgis.Info)

        try:
            self.success, self.message, self.output_path = self.data_manager.run_lcz_classification(
                grid_path=self.grid_path,
                log_callback=task_log
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False
