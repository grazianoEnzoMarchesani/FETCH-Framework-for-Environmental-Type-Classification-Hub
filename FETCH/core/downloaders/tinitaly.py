# -*- coding: utf-8 -*-

import os
import math
import zipfile
from qgis.core import (
    QgsProject, QgsRectangle, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, Qgis
)
from .base import BaseDownloader
from ..tinitaly_tiles import AVAILABLE_TILES, tile_name

class TinitalyDownloader(BaseDownloader):
    def __init__(self, data_manager):
        super().__init__(data_manager)
        self.base_url = "https://tinitaly.pi.ingv.it/data_1.1/"

    def calculate_tiles(self, extent, crs_auth_id):
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:32632")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        
        try:
            utm_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            self.log(f"Error transforming extent: {e}", Qgis.Critical)
            return []

        tiles, skipped = [], []
        x_min = math.floor(utm_extent.xMinimum() / 50000) * 50000
        x_max = math.ceil(utm_extent.xMaximum() / 50000) * 50000
        y_min = math.floor(utm_extent.yMinimum() / 50000) * 50000
        y_max = math.ceil(utm_extent.yMaximum() / 50000) * 50000

        for x in range(int(x_min), int(x_max), 50000):
            for y in range(int(y_min), int(y_max), 50000):
                name = tile_name(x, y)
                # Only tiles that really exist on the server (sea-only squares do not)
                if name in AVAILABLE_TILES:
                    tiles.append(name)
                else:
                    skipped.append(name or f"x={x}/y={y}")
        if skipped:
            self.log(f"Tinitaly: quadranti senza dati (mare o fuori Italia), non scaricati: {', '.join(skipped)}")
        if not tiles:
            self.log("Tinitaly: nessun quadrante DTM disponibile per l'area selezionata.", Qgis.Warning)
        return tiles

    def download_tile(self, tile_name):
        self.log(f"Avvio elaborazione quadrante Tinitaly: {tile_name}")
        download_dir = self.get_download_dir("tinitaly_tiles")
        if not download_dir: return False, "Project not saved"

        filename = f"{tile_name}_s10.zip"
        url = f"{self.base_url}{tile_name}_s10/{filename}"
        save_path = os.path.join(download_dir, filename)
        extracted_tif = os.path.join(download_dir, f"{tile_name}_s10.tif")

        if os.path.exists(extracted_tif):
            return True, f"Tile {tile_name} già presente (TIF)"

        if os.path.exists(save_path):
            self.log(f"ZIP {filename} già presente, avvio estrazione...")
            success, msg = True, "Gia' presente"
        else:
            success, msg = self._download_file(url, save_path)
            
        if success:
            try:
                with zipfile.ZipFile(save_path, 'r') as zip_ref:
                    zip_ref.extractall(download_dir)
                return True, f"Tile {tile_name} scaricata ed estratta"
            except Exception as e:
                return False, f"Errore estrazione: {e}"
        return False, msg
