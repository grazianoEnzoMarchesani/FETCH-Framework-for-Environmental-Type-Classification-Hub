# -*- coding: utf-8 -*-
"""
FETCH LCZ Parameter Task

Background task for calculating individual LCZ parameters.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis


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
        def task_log(msg):
            self.log_msgs.append(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)

        try:
            self.success, self.message, self.output_path = self.data_manager.calculate_lcz_parameters(
                grid_path=self.grid_path,
                parameter_id=self.parameter_id,
                log_callback=task_log
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False
