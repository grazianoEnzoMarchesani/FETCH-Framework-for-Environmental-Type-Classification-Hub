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
import processing

class DataManager:
    def __init__(self, iface):
        self.iface = iface
        self.base_url_tinitaly = "https://tinitaly.pi.ingv.it/data_1.1/"
        self.base_url_eth = "https://libdrive.ethz.ch/index.php/s/cO8or7iOe5dT2Rt/download?path=%2F3deg_cogs&files="
        self.base_url_esa_worldcover = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
        self.url_meta_hrsl = "https://data.humdata.org/dataset/0eb77b21-06be-42c8-9245-2edaff79952f/resource/a5f709f2-9871-46ab-a573-a25b0a7615ca/download/ita_general_2020_geotiff.zip"
        
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

    def calculate_esa_worldcover_tiles(self, extent, crs_auth_id):
        """
        Calculates the required 3x3 degree tiles for ESA WorldCover 2021.
        Tiles are named like: ESA_WorldCover_10m_2021_v200_N45E009_Map.tif
        """
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        
        try:
            wgs84_extent = transform.transformBoundingBox(extent)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error transforming extent to WGS84 for ESA: {e}", "IT-LCZ", Qgis.Critical)
            return []

        tiles = []
        # ESA tiles are 3x3 degrees, anchored at multiples of 3
        lat_min = math.floor(wgs84_extent.yMinimum() / 3) * 3
        lat_max = math.ceil(wgs84_extent.yMaximum() / 3) * 3
        lon_min = math.floor(wgs84_extent.xMinimum() / 3) * 3
        lon_max = math.ceil(wgs84_extent.xMaximum() / 3) * 3

        for lat in range(int(lat_min), int(lat_max), 3):
            for lon in range(int(lon_min), int(lon_max), 3):
                lat_str = f"N{str(abs(lat)).zfill(2)}" if lat >= 0 else f"S{str(abs(lat)).zfill(2)}"
                lon_str = f"E{str(abs(lon)).zfill(3)}" if lon >= 0 else f"W{str(abs(lon)).zfill(3)}"
                tile_name = f"ESA_WorldCover_10m_2021_v200_{lat_str}{lon_str}_Map.tif"
                tiles.append(tile_name)
        
        return tiles

    def fetch_esa_worldcover(self, extent, crs_auth_id):
        """
        Orchestrates the calculation and download of ESA WorldCover tiles.
        """
        QgsMessageLog.logMessage("Avvio acquisizione ESA WorldCover (Land Use)...", "IT-LCZ", Qgis.Info)
        download_dir = self.get_download_dir("esa_worldcover")
        if not download_dir: return []

        tile_names = self.calculate_esa_worldcover_tiles(extent, crs_auth_id)
        results = []

        for tile_name in tile_names:
            save_path = os.path.join(download_dir, tile_name)
            if os.path.exists(save_path):
                results.append((tile_name, True, "Gia' presente"))
                continue

            url = f"{self.base_url_esa_worldcover}{tile_name}"
            success, msg = self._download_file_generic(url, save_path)
            results.append((tile_name, success, msg))
            
            if success:
                QgsMessageLog.logMessage(f"ESA WorldCover tile {tile_name} scaricata.", "IT-LCZ", Qgis.Info)
            else:
                QgsMessageLog.logMessage(f"Errore download ESA tile {tile_name}: {msg}", "IT-LCZ", Qgis.Warning)

        return results

    def fetch_meta_hrsl(self, extent, crs_auth_id):
        """
        Downloads, extracts and clips Meta HRSL Population data for the AOI.
        """
        QgsMessageLog.logMessage("Avvio acquisizione Meta HRSL (Popolazione)...", "IT-LCZ", Qgis.Info)
        
        # 1. Paths
        download_dir = self.get_download_dir("meta_hrsl")
        if not download_dir: return False, "Project not saved"
        
        cache_dir = os.path.join(download_dir, "cache")
        if not os.path.exists(cache_dir): os.makedirs(cache_dir)
        
        zip_path = os.path.join(cache_dir, "ita_population.zip")
        output_aoi = os.path.join(download_dir, "meta_hrsl_aoi.tif")
        
        if os.path.exists(output_aoi):
            return True, "Clipped population raster già presente"

        # 2. Download ZIP if not in cache
        if not os.path.exists(zip_path):
            QgsMessageLog.logMessage("Download del dataset nazionale Meta HRSL (~500MB)...", "IT-LCZ", Qgis.Info)
            success, msg = self._download_file_generic(self.url_meta_hrsl, zip_path)
            if not success: return False, f"Download fallito: {msg}"
        
        # 3. Extract to find the TIF
        tif_found = None
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Look for the .tif file inside
                for name in zip_ref.namelist():
                    if name.lower().endswith('.tif') and not name.startswith('__MACOSX'):
                        tif_found = os.path.join(cache_dir, name)
                        if not os.path.exists(tif_found):
                            QgsMessageLog.logMessage(f"Estrazione {name}...", "IT-LCZ", Qgis.Info)
                            zip_ref.extract(name, cache_dir)
                        break
        except Exception as e:
            return False, f"Errore estrazione ZIP: {e}"
        
        if not tif_found or not os.path.exists(tif_found):
            return False, "Nessun file TIF trovato nello ZIP della popolazione"

        # 4. Clip to AOI using QGIS Processing
        try:
            QgsMessageLog.logMessage(f"Ritaglio Meta HRSL sull'estensione AOI...", "IT-LCZ", Qgis.Info)
            
            # Convert extent to WGS84 for clipping (Meta data is usually 4326)
            source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
            wgs84_extent = transform.transformBoundingBox(extent)
            
            # Logic to handle existing oversized file
            if os.path.exists(output_aoi):
                if os.path.getsize(output_aoi) > 1024 * 1024 * 1024: # > 1GB
                    QgsMessageLog.logMessage("Rilevato file AOI sovradimensionato, procedo alla rimozione e ricalcolo...", "IT-LCZ", Qgis.Warning)
                    os.remove(output_aoi)

            params = {
                'INPUT': tif_found,
                'PROJWIN': wgs84_extent, # Pass the QgsRectangle object directly
                'OVERWM': 0,
                'RTYPE': 5, # Float32
                'OPTIONS': 'COMPRESS=DEFLATE -co PREDICTOR=2 -co ZLEVEL=9',
                'DATA_TYPE': 5,
                'EXTRA': '',
                'OUTPUT': output_aoi
            }
            
            processing.run("gdal:cliprasterbyextent", params)
            
            if os.path.exists(output_aoi):
                # CLEANUP: Remove the large extracted national TIF to save space
                try:
                    QgsMessageLog.logMessage("Pulizia cache: rimozione dataset nazionale esteso per risparmiare spazio.", "IT-LCZ", Qgis.Info)
                    os.remove(tif_found)
                except Exception as e:
                    QgsMessageLog.logMessage(f"Impossibile rimuovere file cache: {e}", "IT-LCZ", Qgis.Warning)
                
                return True, "Ritaglio popolazione completato con compressione"
            else:
                return False, "Errore durante il clipping GDAL: output non generato"
                
        except Exception as e:
            return False, f"Errore durante il clipping: {e}"

    def fetch_sentinel2_albedo(self, extent, crs_auth_id, username=None, password=None):
        """
        Downloads and processes Sentinel-2 imagery to calculate broadband albedo.
        Uses EODAG with Copernicus Data Space Ecosystem (CDSE).
        
        Args:
            extent: QgsRectangle of the AOI
            crs_auth_id: CRS authority ID (e.g., 'EPSG:4326')
            username: CDSE username (optional, falls back to env var)
            password: CDSE password (optional, falls back to env var)
        """
        QgsMessageLog.logMessage("Avvio acquisizione Sentinel-2 Albedo...", "IT-LCZ", Qgis.Info)
        
        # Get output directory
        output_dir = self.get_download_dir("sentinel2_albedo")
        if not output_dir:
            return False, "Project not saved"
        
        # Check if output already exists
        existing_files = [f for f in os.listdir(output_dir) if f.endswith('_albedo_10m.tif')]
        if existing_files:
            QgsMessageLog.logMessage(f"Albedo già presente: {existing_files[0]}", "IT-LCZ", Qgis.Info)
            return True, f"Albedo già presente: {existing_files[0]}"
        
        # Transform extent to WGS84 for Sentinel-2 search
        try:
            source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
            wgs84_extent = transform.transformBoundingBox(extent)
            
            bbox = (
                wgs84_extent.xMinimum(),
                wgs84_extent.yMinimum(),
                wgs84_extent.xMaximum(),
                wgs84_extent.yMaximum()
            )
        except Exception as e:
            return False, f"Errore trasformazione coordinate: {e}"
        
        # Import the sentinel2_albedo module
        try:
            from .sentinel2_albedo import fetch_albedo_for_aoi
        except ImportError as e:
            QgsMessageLog.logMessage(f"Errore import modulo sentinel2_albedo: {e}", "IT-LCZ", Qgis.Critical)
            return False, f"Modulo sentinel2_albedo non disponibile: {e}"
        
        # Define logging callback
        def log_callback(msg):
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        # Call the fetch function with credentials from UI
        success, message, output_path = fetch_albedo_for_aoi(
            bbox=bbox,
            output_dir=output_dir,
            username=username,
            password=password,
            log_callback=log_callback
        )
        
        if success:
            QgsMessageLog.logMessage(f"Sentinel-2 Albedo completato: {output_path}", "IT-LCZ", Qgis.Info)
        else:
            QgsMessageLog.logMessage(f"Sentinel-2 Albedo fallito: {message}", "IT-LCZ", Qgis.Warning)
        
        return success, message

    def get_utm_zone_for_extent(self, extent, crs_auth_id):
        """
        Determina la zona UTM corretta basata sul centroide dell'extent.
        Restituisce l'EPSG della zona UTM appropriata per l'Italia.
        """
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
        wgs84_extent = transform.transformBoundingBox(extent)
        
        # Calcola zona UTM dal centroide
        center_lon = (wgs84_extent.xMinimum() + wgs84_extent.xMaximum()) / 2
        zone = int((center_lon + 180) / 6) + 1
        
        # Per Italia, usa sempre emisfero nord (326XX)
        return f"EPSG:326{zone:02d}"

    def unify_and_clip_data(self, extent, crs_auth_id, log_callback=None):
        """
        Unifica tutti i dati scaricati in proiezione metrica (UTM) e ritaglia sull'AOI.
        I file originali rimangono intatti, i nuovi vengono salvati in unified/.
        
        Returns:
            tuple: (success, message, list of output paths)
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        # Get base directories
        base_dir = self.get_project_dir()
        if not base_dir:
            return False, "Progetto non salvato", []
        
        data_dir = os.path.join(base_dir, "it_lcz_data")
        if not os.path.exists(data_dir):
            return False, "Nessun dato scaricato trovato (cartella it_lcz_data non esiste)", []
        
        # Create unified output directory
        unified_dir = os.path.join(data_dir, "unified")
        if not os.path.exists(unified_dir):
            os.makedirs(unified_dir)
        
        # Determine target CRS (UTM zone based on AOI)
        target_crs_auth = self.get_utm_zone_for_extent(extent, crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem(target_crs_auth)
        log(f"Proiezione target: {target_crs_auth} ({target_crs.description()})")
        
        # Transform extent to target CRS for clipping
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        target_extent = transform.transformBoundingBox(extent)
        
        output_paths = []
        
        # Mapping of source folders to output names
        dataset_mapping = {
            "tinitaly_tiles": {"pattern": "*_s10.tif", "output_name": "dtm_10m.tif", "merge": True},
            "tum_lod1": {"pattern": "*.json", "output_name": "buildings_lod1.gpkg", "type": "vector"},
            "eth_canopy": {"pattern": "*.tif", "output_name": "canopy_height_10m.tif", "merge": True},
            "esa_worldcover": {"pattern": "*.tif", "output_name": "landuse_10m.tif", "merge": True},
            "meta_hrsl": {"pattern": "meta_hrsl_aoi.tif", "output_name": "population_30m.tif", "merge": False},
            "sentinel2_albedo": {"pattern": "*_albedo_10m.tif", "output_name": "albedo_10m.tif", "merge": False},
        }
        
        for folder_name, config in dataset_mapping.items():
            folder_path = os.path.join(data_dir, folder_name)
            if not os.path.exists(folder_path):
                log(f"Cartella {folder_name} non trovata, salto...")
                continue
            
            output_path = os.path.join(unified_dir, config["output_name"])
            
            # Skip if already processed
            if os.path.exists(output_path):
                log(f"{config['output_name']} già presente, salto...")
                output_paths.append(output_path)
                continue
            
            try:
                if config.get("type") == "vector":
                    # Process vector data (TUM buildings)
                    result = self._process_vector_data(folder_path, config, output_path, target_crs_auth, target_extent, log)
                else:
                    # Process raster data
                    result = self._process_raster_data(folder_path, config, output_path, target_crs_auth, target_extent, log)
                
                if result and os.path.exists(output_path):
                    output_paths.append(output_path)
                    log(f"✓ {config['output_name']} creato con successo")
                    
            except Exception as e:
                log(f"✗ Errore processando {folder_name}: {str(e)}")
        
        if output_paths:
            return True, f"Processati {len(output_paths)} dataset", output_paths
        else:
            return False, "Nessun dataset processato", []

    def _process_raster_data(self, folder_path, config, output_path, target_crs, target_extent, log):
        """Process and merge raster files, then reproject and clip."""
        import glob
        
        # Find all matching files
        pattern = os.path.join(folder_path, config["pattern"])
        input_files = glob.glob(pattern)
        
        # Exclude cache folders
        input_files = [f for f in input_files if "cache" not in f]
        
        if not input_files:
            log(f"Nessun file trovato per pattern {config['pattern']} in {folder_path}")
            return False
        
        log(f"Trovati {len(input_files)} file raster da processare...")
        
        # If multiple files and merge is True, merge first
        if len(input_files) > 1 and config.get("merge", False):
            # Merge rasters
            temp_merged = output_path.replace(".tif", "_merged_temp.tif")
            merge_params = {
                'INPUT': input_files,
                'PCT': False,
                'SEPARATE': False,
                'NODATA_INPUT': None,
                'NODATA_OUTPUT': None,
                'OPTIONS': '',
                'EXTRA': '',
                'DATA_TYPE': 5,  # Float32
                'OUTPUT': temp_merged
            }
            processing.run("gdal:merge", merge_params)
            input_for_warp = temp_merged
        else:
            input_for_warp = input_files[0]
        
        # Warp (reproject) and clip in one step
        warp_params = {
            'INPUT': input_for_warp,
            'SOURCE_CRS': None,  # Auto-detect
            'TARGET_CRS': target_crs,
            'RESAMPLING': 0,  # Nearest neighbor (good for categorical data like land use)
            'NODATA': None,
            'TARGET_RESOLUTION': None,
            'OPTIONS': 'COMPRESS=DEFLATE|PREDICTOR=2|ZLEVEL=6',
            'DATA_TYPE': 0,  # Use input type
            'TARGET_EXTENT': f"{target_extent.xMinimum()},{target_extent.xMaximum()},{target_extent.yMinimum()},{target_extent.yMaximum()}",
            'TARGET_EXTENT_CRS': target_crs,
            'MULTITHREADING': True,
            'EXTRA': '',
            'OUTPUT': output_path
        }
        processing.run("gdal:warpreproject", warp_params)
        
        # Cleanup temp merged file
        if len(input_files) > 1 and config.get("merge", False):
            temp_merged = output_path.replace(".tif", "_merged_temp.tif")
            if os.path.exists(temp_merged):
                try:
                    os.remove(temp_merged)
                except:
                    pass
        
        return os.path.exists(output_path)

    def _process_vector_data(self, folder_path, config, output_path, target_crs, target_extent, log):
        """Process vector data: reproject and clip to AOI."""
        import glob
        from qgis.core import QgsVectorLayer, QgsGeometry
        
        # Find input file
        pattern = os.path.join(folder_path, config["pattern"])
        input_files = glob.glob(pattern)
        
        if not input_files:
            log(f"Nessun file vettoriale trovato per pattern {config['pattern']}")
            return False
        
        input_file = input_files[0]
        log(f"Processamento vettoriale: {os.path.basename(input_file)}")
        
        # Create clip geometry from extent
        clip_geom = QgsGeometry.fromRect(target_extent)
        
        # Use a temporary file for reprojection
        temp_reprojected = output_path.replace(".gpkg", "_temp.gpkg")
        
        # Reproject
        reproject_params = {
            'INPUT': input_file,
            'TARGET_CRS': target_crs,
            'OPERATION': '',
            'OUTPUT': temp_reprojected
        }
        processing.run("native:reprojectlayer", reproject_params)
        
        # Clip - create a temporary layer from extent
        clip_params = {
            'INPUT': temp_reprojected,
            'OVERLAY': None,  # Use extent instead
            'OUTPUT': output_path
        }
        
        # Use clip by extent for vector
        clip_extent_params = {
            'INPUT': temp_reprojected,
            'EXTENT': f"{target_extent.xMinimum()},{target_extent.xMaximum()},{target_extent.yMinimum()},{target_extent.yMaximum()}",
            'CLIP': True,
            'OUTPUT': output_path
        }
        processing.run("native:extractbyextent", clip_extent_params)
        
        # Cleanup temp file
        if os.path.exists(temp_reprojected):
            try:
                os.remove(temp_reprojected)
            except:
                pass
        
        return os.path.exists(output_path)

    def load_unified_layers(self, log_callback=None):
        """
        Carica tutti i layer dalla cartella unified nel progetto QGIS.
        
        Returns:
            list: Lista dei layer caricati
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        base_dir = self.get_project_dir()
        if not base_dir:
            return []
        
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        if not os.path.exists(unified_dir):
            log("Cartella unified non trovata")
            return []
        
        from qgis.core import QgsRasterLayer, QgsVectorLayer
        
        loaded_layers = []
        
        # Layer names mapping for friendly display
        layer_names = {
            "dtm_10m.tif": "DTM Tinitaly (10m)",
            "buildings_lod1.gpkg": "Edifici TUM LoD1",
            "canopy_height_10m.tif": "Altezza Alberi ETH (10m)",
            "landuse_10m.tif": "Land Use ESA (10m)",
            "population_30m.tif": "Popolazione Meta HRSL",
            "albedo_10m.tif": "Albedo Sentinel-2 (10m)",
        }
        
        for filename, display_name in layer_names.items():
            filepath = os.path.join(unified_dir, filename)
            if not os.path.exists(filepath):
                continue
            
            # Check if already loaded
            existing = QgsProject.instance().mapLayersByName(display_name)
            if existing:
                log(f"Layer '{display_name}' già caricato")
                continue
            
            try:
                if filename.endswith('.tif'):
                    layer = QgsRasterLayer(filepath, display_name)
                elif filename.endswith('.gpkg'):
                    layer = QgsVectorLayer(filepath, display_name, "ogr")
                else:
                    continue
                
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    loaded_layers.append(layer)
                    log(f"✓ Caricato: {display_name}")
                else:
                    log(f"✗ Layer non valido: {display_name}")
                    
            except Exception as e:
                log(f"✗ Errore caricamento {display_name}: {str(e)}")
        
        return loaded_layers

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
