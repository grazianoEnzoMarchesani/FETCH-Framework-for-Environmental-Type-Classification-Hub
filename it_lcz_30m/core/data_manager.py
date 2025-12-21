# -*- coding: utf-8 -*-

import os
import requests
import zipfile
import math
from qgis.core import (
    QgsProject, QgsRectangle, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, QgsMessageLog, Qgis
)

class DataManager:
    def __init__(self, iface):
        self.iface = iface
        self.base_url_tinitaly = "https://tinitaly.pi.ingv.it/data_1.1/"
        
    def get_project_dir(self):
        project_path = QgsProject.instance().fileName()
        if not project_path:
            return None
        return os.path.dirname(project_path)

    def get_download_dir(self, subfolder="tinitaly_tiles"):
        base_dir = self.get_project_dir()
        if not base_dir:
            return None
        
        target_dir = os.path.join(base_dir, "it_lcz_data", subfolder)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        return target_dir

    def calculate_tinitaly_tiles(self, extent, crs_auth_id):
        """
        Calculates the list of Tinitaly tiles (50x50km) overlapping the extent.
        Uses UTM Zone 32N (EPSG:32632) as the reference grid.
        """
        # 1. Transform extent to UTM 32N
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:32632")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        
        try:
            utm_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error transforming extent: {e}", "IT-LCZ", Qgis.Critical)
            return []

        # 2. Iterate over 50km grid
        tiles = []
        x_min = math.floor(utm_extent.xMinimum() / 50000) * 50000
        x_max = math.ceil(utm_extent.xMaximum() / 50000) * 50000
        y_min = math.floor(utm_extent.yMinimum() / 50000) * 50000
        y_max = math.ceil(utm_extent.yMaximum() / 50000) * 50000

        # Step is 50,000 meters
        for x in range(int(x_min), int(x_max), 50000):
            for y in range(int(y_min), int(y_max), 50000):
                # NNN = Northing in tens of km
                nnn = int(y / 10000)
                # EE = Easting in tens of km
                ee = int(x / 10000)
                
                # Naming: w + NNN(3 digits) + EE(2 digits)
                tile_name = f"w{str(nnn).zfill(3)}{str(ee).zfill(2)}"
                tiles.append(tile_name)
        
        return tiles

    def download_tinitaly_tile(self, tile_name):
        """
        Downloads and unzips a single Tinitaly tile.
        """
        QgsMessageLog.logMessage(f"Avvio elaborazione quadrante: {tile_name}", "IT-LCZ", Qgis.Info)
        
        download_dir = self.get_download_dir("tinitaly_tiles")
        if not download_dir:
            QgsMessageLog.logMessage("Errore: Impossibile trovare la cartella di download. Il progetto è salvato?", "IT-LCZ", Qgis.Critical)
            return False, "Project not saved"

        # URL Pattern: https://tinitaly.pi.ingv.it/data_1.1/[tile]_s10/[tile]_s10.zip
        filename = f"{tile_name}_s10.zip"
        url = f"{self.base_url_tinitaly}{tile_name}_s10/{filename}"
        save_path = os.path.join(download_dir, filename)

        QgsMessageLog.logMessage(f"URL: {url}", "IT-LCZ", Qgis.Info)
        QgsMessageLog.logMessage(f"Destinazione: {save_path}", "IT-LCZ", Qgis.Info)

        if os.path.exists(save_path):
            QgsMessageLog.logMessage(f"Quadrante {tile_name} già presente localmente.", "IT-LCZ", Qgis.Info)
            return True, f"Tile {tile_name} found locally"

        try:
            QgsMessageLog.logMessage(f"Downloading {tile_name} (SSL verification disabled)...", "IT-LCZ", Qgis.Warning)
            # Use verify=False to bypass local SSL certificate issues common in some environments
            response = requests.get(url, stream=True, timeout=60, verify=False)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                QgsMessageLog.logMessage(f"Download completato: {tile_name}. Estrazione zip...", "IT-LCZ", Qgis.Info)
                
                # Unzip
                with zipfile.ZipFile(save_path, 'r') as zip_ref:
                    zip_ref.extractall(download_dir)
                
                QgsMessageLog.logMessage(f"Estrazione completata per {tile_name}.", "IT-LCZ", Qgis.Success)
                return True, f"Tile {tile_name} downloaded and extracted"
            else:
                QgsMessageLog.logMessage(f"Errore HTTP {response.status_code} per {tile_name}. Verificare l'URL.", "IT-LCZ", Qgis.Critical)
                return False, f"HTTP Error {response.status_code}"
        except Exception as e:
            QgsMessageLog.logMessage(f"Eccezione durante il download di {tile_name}: {str(e)}", "IT-LCZ", Qgis.Critical)
            return False, str(e)
