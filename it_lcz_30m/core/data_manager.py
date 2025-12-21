# -*- coding: utf-8 -*-

import os
import requests
import zipfile
import math
import re
from urllib.parse import urljoin
from qgis.core import (
    QgsProject, QgsRectangle, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, QgsMessageLog, Qgis
)

class DataManager:
    def __init__(self, iface):
        self.iface = iface
        self.base_url_tinitaly = "https://tinitaly.pi.ingv.it/data_1.1/"
        self.base_url_eth = "https://libdrive.ethz.ch/index.php/s/cO8or7iOe5dT2Rt/download?path=%2F3deg_cogs&files="
        
        self.tum_categories = ["LoD1"]
        
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
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:32632")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        
        try:
            utm_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error transforming extent: {e}", "IT-LCZ", Qgis.Critical)
            return []

        tiles = []
        x_min = math.floor(utm_extent.xMinimum() / 50000) * 50000
        x_max = math.ceil(utm_extent.xMaximum() / 50000) * 50000
        y_min = math.floor(utm_extent.yMinimum() / 50000) * 50000
        y_max = math.ceil(utm_extent.yMaximum() / 50000) * 50000

        for x in range(int(x_min), int(x_max), 50000):
            for y in range(int(y_min), int(y_max), 50000):
                nnn = int(y / 10000)
                ee = int(x / 10000)
                tile_name = f"w{str(nnn).zfill(3)}{str(ee).zfill(2)}"
                tiles.append(tile_name)
        return tiles


    def download_tinitaly_tile(self, tile_name):
        QgsMessageLog.logMessage(f"Avvio elaborazione quadrante Tinitaly: {tile_name}", "IT-LCZ", Qgis.Info)
        download_dir = self.get_download_dir("tinitaly_tiles")
        if not download_dir: return False, "Project not saved"

        filename = f"{tile_name}_s10.zip"
        url = f"{self.base_url_tinitaly}{tile_name}_s10/{filename}"
        save_path = os.path.join(download_dir, filename)
        extracted_tif = os.path.join(download_dir, f"{tile_name}_s10.tif")

        if os.path.exists(extracted_tif):
            return True, f"Tile {tile_name} già presente (TIF)"

        if os.path.exists(save_path):
            QgsMessageLog.logMessage(f"ZIP {filename} già presente, avvio estrazione...", "IT-LCZ", Qgis.Info)
            # Skip download, proceed to extraction logic below
            success, msg = True, "Gia' presente"
        else:
            success, msg = self._download_file_generic(url, save_path)
        if success:
            try:
                with zipfile.ZipFile(save_path, 'r') as zip_ref:
                    zip_ref.extractall(download_dir)
                return True, f"Tile {tile_name} scaricata ed estratta"
            except Exception as e:
                return False, f"Errore estrazione: {e}"
        return False, msg

    def download_tum_data(self, category="LoD1", aoi_geometry=None):
        """
        Downloads TUM data via WFS (AOI-specific GeoJSON, much faster).
        """
        QgsMessageLog.logMessage(f"Avvio acquisizione TUM {category}. AOI: {'Disponibile' if aoi_geometry else 'Mancante'}", "IT-LCZ", Qgis.Info)
        download_dir = self.get_download_dir(f"tum_{category.lower()}")
        if not download_dir: return []

        if category == "LoD1" and aoi_geometry:
            return self._download_tum_lod1_wfs(download_dir, aoi_geometry)

        QgsMessageLog.logMessage(f"Categoria {category} non supportata o AOI mancante.", "IT-LCZ", Qgis.Warning)
        return []

    def _download_tum_lod1_wfs(self, download_dir, aoi_geometry):
        """
        Downloads LoD1 building footprints via WFS for the specific AOI.
        """
        extent = aoi_geometry.boundingBox()
        # BBOX format: minx, miny, maxx, maxy
        bbox_str = f"{extent.xMinimum()},{extent.yMinimum()},{extent.xMaximum()},{extent.yMaximum()}"
        
        wfs_url = (
            "https://tubvsig-so2sat-vm1.srv.mwn.de/geoserver/ows?"
            "service=WFS&version=1.1.0&request=GetFeature&"
            "typeName=global3D:lod1_global&outputFormat=application/json&"
            f"srsName=EPSG:4326&bbox={bbox_str},EPSG:4326"
        )
        
        save_path = os.path.join(download_dir, "tum_lod1_aoi.json")

        if os.path.exists(save_path):
            QgsMessageLog.logMessage(f"LoD1 AOI già presente (JSON). Salto.", "IT-LCZ", Qgis.Info)
            return [("tum_lod1_aoi.json", True, "Gia' presente")]

        QgsMessageLog.logMessage(f"Download WFS TUM LoD1 per AOI...", "IT-LCZ", Qgis.Info)
        
        success, msg = self._download_file_generic(wfs_url, save_path)
        if success:
            return [("tum_lod1_aoi.json", True, "Download completato")]
        else:
            QgsMessageLog.logMessage(f"Download WFS fallito: {msg}", "IT-LCZ", Qgis.Critical)
            return [("tum_lod1_aoi.json", False, msg)]


    def calculate_eth_tiles(self, extent, crs_auth_id):
        """
        Calculates the required 3x3 degree tiles for ETH Global Canopy Height.
        Tiles are named like: ETH_GlobalCanopyHeight_10m_2020_N45E009_Map.tif
        """
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        
        try:
            wgs84_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error transforming extent to WGS84: {e}", "IT-LCZ", Qgis.Critical)
            return []

        tiles = []
        # ETH tiles are 3x3 degrees, anchored at multiples of 3
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

    def fetch_eth_canopy(self, extent, crs_auth_id):
        """
        Orchestrates the calculation and download of ETH tiles.
        """
        QgsMessageLog.logMessage("Avvio acquisizione ETH Global Canopy Height...", "IT-LCZ", Qgis.Info)
        download_dir = self.get_download_dir("eth_canopy")
        if not download_dir: return []

        tile_names = self.calculate_eth_tiles(extent, crs_auth_id)
        results = []

        for tile_name in tile_names:
            save_path = os.path.join(download_dir, tile_name)
            if os.path.exists(save_path):
                results.append((tile_name, True, "Gia' presente"))
                continue

            url = f"{self.base_url_eth}{tile_name}"
            success, msg = self._download_file_generic(url, save_path)
            results.append((tile_name, success, msg))
            
            if success:
                QgsMessageLog.logMessage(f"ETH tile {tile_name} scaricata.", "IT-LCZ", Qgis.Info)
            else:
                QgsMessageLog.logMessage(f"Errore download ETH tile {tile_name}: {msg}", "IT-LCZ", Qgis.Warning)

        return results


    def _get_links_from_page(self, url):
        try:
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()
            links = re.findall(r'href=[\'"]?([^\'" >]+)', response.text, re.IGNORECASE)
            valid_items = []
            for link in links:
                if link in ['../', './', '/'] or link.startswith('?'): continue
                full_url = urljoin(url, link)
                name = link.rstrip('/')
                valid_items.append((name, full_url))
            return valid_items
        except Exception as e:
            QgsMessageLog.logMessage(f"Errore scansione directory {url}: {e}", "IT-LCZ", Qgis.Critical)
            return []

    def _download_file_generic(self, url, local_path, auth=None):
        if os.path.exists(local_path):
            return True, "File già presente"
        try:
            with requests.get(url, stream=True, auth=auth, timeout=120, verify=False) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True, "Download completato"
        except Exception as e:
            if os.path.exists(local_path): os.remove(local_path)
            return False, str(e)
