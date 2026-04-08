# -*- coding: utf-8 -*-


from qgis.core import QgsMessageLog, Qgis
from ..utils import download_file_generic

class BaseDownloader:
    def __init__(self, data_manager):
        self.dm = data_manager
        self.iface = data_manager.iface
        
    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "EnviProtocol", level)

    def _download_file(self, url, local_path, auth=None):
        """Delegates download to the unified SSL-aware downloader in utils."""
        return download_file_generic(url, local_path, auth)

    def get_download_dir(self, subfolder):
        return self.dm.get_download_dir(subfolder)
