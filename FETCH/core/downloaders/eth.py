# -*- coding: utf-8 -*-

import os
import math
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, Qgis
)
from .base import BaseDownloader

class ETHDownloader(BaseDownloader):
    def __init__(self, data_manager):
        super().__init__(data_manager)
        self.base_url = "https://libdrive.ethz.ch/index.php/s/cO8or7iOe5dT2Rt/download?path=%2F3deg_cogs&files="

    def calculate_tiles(self, extent, crs_auth_id):
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        
        try:
            wgs84_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            self.log(f"Error transforming extent to WGS84: {e}", Qgis.Critical)
            return []

        tiles = []
        lat_min = math.floor(wgs84_extent.yMinimum() / 3) * 3
        lat_max = math.ceil(wgs84_extent.yMaximum() / 3) * 3
        lon_min = math.floor(wgs84_extent.xMinimum() / 3) * 3
        lon_max = math.ceil(wgs84_extent.xMaximum() / 3) * 3

        for lat in range(int(lat_min), int(lat_max), 3):
            for lon in range(int(lon_min), int(lon_max), 3):
                lat_str = f"N{str(abs(lat)).zfill(2)}" if lat >= 0 else f"S{str(abs(lat)).zfill(2)}"
                lon_str = f"E{str(abs(lon)).zfill(3)}" if lon >= 0 else f"W{str(abs(lon)).zfill(3)}"
                tile_name = f"ETH_GlobalCanopyHeight_10m_2020_{lat_str}{lon_str}_Map.tif"
                tiles.append(tile_name)
        return tiles

    def fetch_canopy(self, extent, crs_auth_id):
        self.log("Avvio acquisizione ETH Global Canopy Height...")
        download_dir = self.get_download_dir("eth_canopy")
        if not download_dir: return []

        tile_names = self.calculate_tiles(extent, crs_auth_id)
        results = []

        for tile_name in tile_names:
            save_path = os.path.join(download_dir, tile_name)
            if os.path.exists(save_path):
                results.append((tile_name, True, "Gia' presente"))
                continue

            url = f"{self.base_url}{tile_name}"
            success, msg = self._download_file(url, save_path)
            results.append((tile_name, success, msg))
            
            if success:
                self.log(f"ETH tile {tile_name} scaricata.")
            else:
                self.log(f"Errore download ETH tile {tile_name}: {msg}", Qgis.Warning)

        return results
