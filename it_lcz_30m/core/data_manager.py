# -*- coding: utf-8 -*-

import os
import requests
import zipfile
import math
import ftplib
import io
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
        
        # TUM GBA Dataset Config (FTP Access)
        self.tum_host = "dataserv.ub.tum.de"
        self.tum_user = "m1782307"
        self.tum_pass = "m1782307"
        self.tum_categories = ["Height", "LoD1"]
        
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

    def calculate_tum_tiles(self, extent, crs_auth_id):
        """
        Calculates the 5x5 degree tiles for TUM GBA dataset.
        Format: {e/w}{lon_min}_{n/s}{lat_max}_{e/w}{lon_max}_{n/s}{lat_min}
        """
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84_crs, QgsProject.instance())
        
        try:
            wgs_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error transforming extent to WGS84: {e}", "IT-LCZ", Qgis.Critical)
            return []

        lon_min_full = math.floor(wgs_extent.xMinimum() / 5) * 5
        lon_max_full = math.ceil(wgs_extent.xMaximum() / 5) * 5
        lat_min_full = math.floor(wgs_extent.yMinimum() / 5) * 5
        lat_max_full = math.ceil(wgs_extent.yMaximum() / 5) * 5

        tiles = []
        for lon in range(lon_min_full, lon_max_full, 5):
            for lat in range(lat_min_full, lat_max_full, 5):
                l_min = self._fmt_coord(lon, is_lat=False)
                l_max = self._fmt_coord(lon + 5, is_lat=False)
                t_max = self._fmt_coord(lat + 5, is_lat=True)
                t_min = self._fmt_coord(lat, is_lat=True)
                
                tile_id = f"{l_min}_{t_max}_{l_max}_{t_min}"
                tiles.append(tile_id)
        return tiles

    def _fmt_coord(self, val, is_lat=False):
        prefix = ("n" if val >= 0 else "s") if is_lat else ("e" if val >= 0 else "w")
        abs_val = abs(val)
        digits = 2 if is_lat else 3
        return f"{prefix}{str(abs_val).zfill(digits)}"

    def download_tinitaly_tile(self, tile_name):
        QgsMessageLog.logMessage(f"Avvio elaborazione quadrante Tinitaly: {tile_name}", "IT-LCZ", Qgis.Info)
        download_dir = self.get_download_dir("tinitaly_tiles")
        if not download_dir: return False, "Project not saved"

        filename = f"{tile_name}_s10.zip"
        url = f"{self.base_url_tinitaly}{tile_name}_s10/{filename}"
        save_path = os.path.join(download_dir, filename)

        if os.path.exists(save_path):
            return True, f"Tile {tile_name} già presente"

        success, msg = self._download_file_generic(url, save_path)
        if success:
            try:
                with zipfile.ZipFile(save_path, 'r') as zip_ref:
                    zip_ref.extractall(download_dir)
                return True, f"Tile {tile_name} scaricata ed estratta"
            except Exception as e:
                return False, f"Errore estrazione: {e}"
        return False, msg

    def download_tum_data(self, target_tiles, category="Height", aoi_geometry=None):
        """
        Downloads TUM data. 
        - Height: via FTP (Crawler + Zip)
        - LoD1: via WFS (AOI-specific GeoJSON/GPKG, much faster)
        """
        QgsMessageLog.logMessage(f"Avvio acquisizione TUM {category}. AOI: {'Disponibile' if aoi_geometry else 'Mancante'}", "IT-LCZ", Qgis.Info)
        download_dir = self.get_download_dir(f"tum_{category.lower()}")
        if not download_dir: return []

        if category == "LoD1" and aoi_geometry:
            # Use WFS for LoD1 - it's much faster
            return self._download_tum_lod1_wfs(download_dir, aoi_geometry)

        # Fallback to FTP for Height or if no AOI provided
        results = []
        ftp = None
        try:
            ftp = ftplib.FTP(self.tum_host)
            ftp.login(self.tum_user, self.tum_pass)
            ftp.cwd(category)
            regions = ftp.nlst()
            
            for region in regions:
                try:
                    ftp.cwd(region)
                    files = ftp.nlst()
                    for file_name in files:
                        match = next((t for t in target_tiles if t in file_name), None)
                        if match:
                            save_path = os.path.join(download_dir, file_name)
                            
                            # Download if not exists
                            if not os.path.exists(save_path):
                                QgsMessageLog.logMessage(f"Download FTP: {file_name}", "IT-LCZ", Qgis.Info)
                                with open(save_path, 'wb') as f:
                                    ftp.retrbinary(f"RETR {file_name}", f.write)
                            
                            # Post-processing
                            success, msg = self._process_tum_file(save_path, category, aoi_geometry)
                            results.append((file_name, success, msg))
                            
                    ftp.cwd("..")
                except Exception as e:
                    QgsMessageLog.logMessage(f"Errore nella regione {region}: {e}", "IT-LCZ", Qgis.Warning)
                    try:
                        ftp.cwd("..")
                    except:
                        pass
                    continue
        except Exception as e:
            QgsMessageLog.logMessage(f"Errore FTP TUM: {e}", "IT-LCZ", Qgis.Critical)
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass

        return results

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
        QgsMessageLog.logMessage(f"Download WFS TUM LoD1 per AOI...", "IT-LCZ", Qgis.Info)
        
        success, msg = self._download_file_generic(wfs_url, save_path)
        if success:
            # Convert and process
            success, msg = self._process_tum_file(save_path, "LoD1", aoi_geometry)
            return [("tum_lod1_aoi.json", success, msg)]
        else:
            QgsMessageLog.logMessage(f"Download WFS fallito: {msg}", "IT-LCZ", Qgis.Critical)
            return [("tum_lod1_aoi.json", False, msg)]

    def _process_tum_file(self, file_path, category, aoi_geometry=None):
        """
        Handles unzipping for Height and conversion to GPKG for LoD1.
        Optionally clips to AOI for performance.
        """
        processed_file = file_path
        
        if category == "Height" and file_path.lower().endswith(".zip"):
            try:
                QgsMessageLog.logMessage(f"Estrazione {os.path.basename(file_path)}...", "IT-LCZ", Qgis.Info)
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(os.path.dirname(file_path))
                
                # Check what was extracted (usually a .tif)
                extracted_files = zip_ref.namelist()
                for f in extracted_files:
                    if f.lower().endswith(".tif"):
                        processed_file = os.path.join(os.path.dirname(file_path), f)
                        break
                
                os.remove(file_path) # Remove zip
            except Exception as e:
                return False, f"Errore estrazione: {e}"

        elif category == "LoD1" and file_path.lower().endswith(".geojson"):
            gpkg_path = file_path.replace(".geojson", ".gpkg")
            if not os.path.exists(gpkg_path):
                try:
                    QgsMessageLog.logMessage(f"Conversione {os.path.basename(file_path)} in GPKG...", "IT-LCZ", Qgis.Info)
                    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsCoordinateTransformContext
                    vlayer = QgsVectorLayer(file_path, "temp", "ogr")
                    if vlayer.isValid():
                        opts = QgsVectorFileWriter.SaveVectorOptions()
                        opts.driverName = "GPKG"
                        QgsVectorFileWriter.writeAsVectorFormatV3(vlayer, gpkg_path, QgsCoordinateTransformContext(), opts)
                        # os.remove(file_path) # Keep original for safety
                        processed_file = gpkg_path
                except Exception as e:
                    QgsMessageLog.logMessage(f"Errore conversione: {e}", "IT-LCZ", Qgis.Warning)

        # Optional: Clip to AOI
        if aoi_geometry and os.path.exists(processed_file):
            try:
                from qgis import processing
                from qgis.core import QgsVectorLayer, QgsFeature, QgsField
                from qgis.PyQt.QtCore import QVariant
                
                base, ext = os.path.splitext(processed_file)
                clipped_path = base + "_clipped" + ext
                if os.path.exists(clipped_path): 
                    return True, "Gia' ritagliato"
                
                QgsMessageLog.logMessage(f"Ritaglio {os.path.basename(processed_file)} su AOI...", "IT-LCZ", Qgis.Info)
                
                if category == "Height":
                    # Clip raster (GDAL: clip by extent)
                    ext_rect = aoi_geometry.boundingBox()
                    # Format: xmin, xmax, ymin, ymax
                    projwin = f"{ext_rect.xMinimum()},{ext_rect.xMaximum()},{ext_rect.yMinimum()},{ext_rect.yMaximum()}"
                    
                    processing.run("gdal:cliprasterbyextent", {
                        'INPUT': processed_file,
                        'PROJWIN': projwin,
                        'NODATA': None, 'OPTIONS': '', 'DATA_TYPE': 0, 'OUTPUT': clipped_path
                    })
                else:
                    # Clip vector (Native: clip expects a layer for OVERLAY)
                    # Create a temporary mem layer for the AOI
                    aoi_layer = QgsVectorLayer(f"Polygon?crs=EPSG:4326", "aoi_temp", "memory")
                    aoi_layer.startEditing()
                    f = QgsFeature()
                    f.setGeometry(aoi_geometry)
                    aoi_layer.addFeature(f)
                    aoi_layer.commitChanges()
                    
                    processing.run("native:clip", {
                        'INPUT': processed_file,
                        'OVERLAY': aoi_layer,
                        'OUTPUT': clipped_path
                    })
                
                return True, "Scaricato e ritagliato"
            except Exception as e:
                QgsMessageLog.logMessage(f"Errore ritaglio: {e}", "IT-LCZ", Qgis.Warning)

        return True, "Processato"

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
