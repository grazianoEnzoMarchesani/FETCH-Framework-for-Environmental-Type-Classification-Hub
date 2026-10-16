# -*- coding: utf-8 -*-
"""
FETCH Istat Task

Background task: download (first run only) and resolve ISTAT municipal boundaries.
"""

import os
from qgis.core import QgsTask, QgsMessageLog, Qgis
from ...core.exceptions import FetchError
from ...core.istat import IstatBoundaries


class IstatTask(QgsTask):
    """Resolves "Comune (SIGLA); ..." into a boundary GeoPackage inside the project data folder."""

    def __init__(self, text, data_dir):
        super().__init__("Confini città ISTAT", QgsTask.CanCancel)
        self.text = text
        self.data_dir = data_dir
        self.aoi_result = None
        self.message = ""

    def run(self):
        def task_log(msg, level=Qgis.Info):
            QgsMessageLog.logMessage(msg, "FETCH", level)

        try:
            os.makedirs(self.data_dir, exist_ok=True)
            self.aoi_result = IstatBoundaries(log=task_log).build_aoi(self.text, self.data_dir)
            task_log(f"Confini ISTAT: {', '.join(self.aoi_result['names'])}")
            return True
        except FetchError as e:
            self.message = e.user_message
            task_log(f"✗ {e.message}", Qgis.Warning)
            return False
        except Exception as e:
            self.message = f"Errore imprevisto: {e}"
            task_log(self.message, Qgis.Critical)
            return False
