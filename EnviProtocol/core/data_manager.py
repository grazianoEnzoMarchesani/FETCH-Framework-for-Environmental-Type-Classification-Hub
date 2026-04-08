# -*- coding: utf-8 -*-

import os
from pathlib import Path
from qgis.core import QgsProject, QgsMessageLog, Qgis, QgsCoordinateReferenceSystem

# Centralized constants
from .constants import LayerNames, FileNames, FolderNames

# Import new specialized modules
from .downloaders.tinitaly import TinitalyDownloader
from .downloaders.tum import TUMDownloader
from .downloaders.eth import ETHDownloader
from .downloaders.esa import ESADownloader
from .downloaders.osm import OSMDownloader
from .downloaders.hrl import HRLDownloader
from .downloaders.tcd import TCDDownloader
from .utils import get_target_crs_for_extent, download_file_generic

class DataManager:
    """
    Orchestrator class for managing data download and processing.
    Delegates actual work to specialized downloader classes.
    """
    def __init__(self, iface):
        self.iface = iface
        
        # Initialize internal modules
        self.tinitaly = TinitalyDownloader(self)
        self.tum = TUMDownloader(self)
        self.eth = ETHDownloader(self)
        self.esa = ESADownloader(self)
        self.osm = OSMDownloader(self)
        self.hrl = HRLDownloader(self)
        self.tcd = TCDDownloader(self)
        
        # UI Compatibility Attributes
        self.tum_categories = ["LoD1"]

    def get_project_dir(self):
        project_path = QgsProject.instance().fileName()
        return os.path.dirname(project_path) if project_path else None

    def get_data_dir_name(self):
        """Returns the dynamic data folder name: EnviProtocol+ProjectName."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            return "enviprotocol_data" # Fallback if project not saved
        
        project_name = os.path.splitext(os.path.basename(project_path))[0]
        return f"EnviProtocol+{project_name}"


    def get_download_dir(self, subfolder):
        base_dir = self.get_project_dir()
        if not base_dir: return None
        target_dir = os.path.join(base_dir, self.get_data_dir_name(), subfolder)
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        return target_dir


    # --- Backward compatibility wrappers for Dashboard.py ---

    def calculate_tinitaly_tiles(self, extent, crs_auth_id):
        return self.tinitaly.calculate_tiles(extent, crs_auth_id)

    def download_tinitaly_tile(self, tile_name):
        return self.tinitaly.download_tile(tile_name)

    def download_tum_data(self, category="LoD1", aoi_geometry=None):
        return self.tum.download_data(category, aoi_geometry)

    def fetch_eth_canopy(self, extent, crs_auth_id):
        return self.eth.fetch_canopy(extent, crs_auth_id)

    def fetch_esa_worldcover(self, extent, crs_auth_id):
        return self.esa.fetch_worldcover(extent, crs_auth_id)

    def fetch_osm_roads(self, extent, crs_auth_id, log_callback=None):
        return self.osm.fetch_roads(extent, crs_auth_id, log_callback=log_callback)

    def fetch_copernicus_hrl(self, extent, crs_auth_id, log_callback=None):
        return self.hrl.fetch_imperviousness(extent, crs_auth_id, log_callback=log_callback)

    def fetch_tree_cover_density(self, extent, crs_auth_id, log_callback=None):
        """Fetches Copernicus Tree Cover Density 10m."""
        return self.tcd.fetch_tree_cover_density(extent, crs_auth_id, log_callback=log_callback)


    def get_target_crs_for_extent(self, extent, crs_auth_id):
        return get_target_crs_for_extent(extent, crs_auth_id)


