# -*- coding: utf-8 -*-

"""
Data Fetcher for LCZ Mapping.
Handles API requests and caching of open datasets (Tinitaly, ESA WorldCover, etc.).
"""

import os
import requests
from typing import Optional, List
from qgis.core import QgsNetworkAccessManager, QgsMessageLog, Qgis

class DataFetcher:
    """
    Manages downloading and local caching of geospatial datasets.
    """

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def log(self, message: str, level: Qgis.MessageLevel = Qgis.Info):
        QgsMessageLog.logMessage(message, "IT-LCZ Data", level)

    def check_local_cache(self, filename: str) -> Optional[str]:
        """Checks if a file exists in the cache."""
        file_path = os.path.join(self.cache_dir, filename)
        if os.path.exists(file_path):
            self.log(f"Found {filename} in cache.")
            return file_path
        return None

    def download_file(self, url: str, filename: str) -> Optional[str]:
        """
        Downloads a file if it doesn't exist in cache.
        In a production environment, this would use QgsNetworkAccessManager for QGIS proxy support.
        """
        cached_path = self.check_local_cache(filename)
        if cached_path:
            return cached_path

        self.log(f"Downloading {filename} from {url}...")
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            target_path = os.path.join(self.cache_dir, filename)
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return target_path
        except Exception as e:
            self.log(f"Failed to download {filename}: {str(e)}", Qgis.Critical)
            return None

    def validate_dataset(self, file_path: str) -> bool:
        """
        Performs basic validation (e.g., file size, raster check).
        """
        if not file_path or not os.path.exists(file_path):
            return False
        # Add GDAL/QGIS check here to ensure it's a valid raster
        return True
