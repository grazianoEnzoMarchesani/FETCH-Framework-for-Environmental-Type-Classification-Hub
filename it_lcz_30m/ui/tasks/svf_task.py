# -*- coding: utf-8 -*-
"""
FETCH SVF Task

Background task for calculating Sky View Factor from DSM.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis


class SVFTask(QgsTask):
    """Task for calculating Sky View Factor in the background."""
    
    def __init__(self, data_manager):
        super().__init__("Calcolo SVF FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg): 
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        try:
            # Default params for SVF
            self.success, self.message, self.output_path = self.data_manager.calculate_svf(
                log_callback=task_log, search_radius=100, num_sectors=16
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False
