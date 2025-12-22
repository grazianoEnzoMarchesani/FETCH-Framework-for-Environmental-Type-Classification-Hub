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
            "tinitaly_tiles": {"pattern": "**/*_s10.tif", "output_name": "dtm_10m.tif", "merge": True, "recursive": True},
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
        
        # Find all matching files (recursive if needed for nested structures)
        pattern = os.path.join(folder_path, config["pattern"])
        recursive = config.get("recursive", False)
        input_files = glob.glob(pattern, recursive=recursive)
        
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

    def create_synthetic_dsm(self, log_callback=None, overwrite=False):
        """
        Creates a synthetic DSM (Digital Surface Model) at 10m resolution.
        
        Formula: DSM = DTM + MAX(H_Buildings, H_Trees)
        The tallest element (building or tree) determines the surface height per pixel.
        Filter: Uses ESA WorldCover to mask water (80) and bare soil (60) areas.
        
        Args:
            log_callback: Optional callback for logging messages
            overwrite: If True, regenerate DSM even if it already exists
        
        Returns:
            tuple: (success, message, output_path)
        """
        import numpy as np
        from osgeo import gdal, ogr
        
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        # Get paths
        base_dir = self.get_project_dir()
        if not base_dir:
            return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        if not os.path.exists(unified_dir):
            return False, "Cartella unified non trovata. Esegui prima 'Unifica e Ritaglia Dati'.", None
        
        # Check required files
        dtm_path = os.path.join(unified_dir, "dtm_10m.tif")
        canopy_path = os.path.join(unified_dir, "canopy_height_10m.tif")
        landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
        buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
        output_path = os.path.join(unified_dir, "dsm_10m.tif")
        
        # Check if already exists (skip if overwrite requested)
        if os.path.exists(output_path):
            if not overwrite:
                return True, "DSM già presente (usa overwrite=True per rigenerare)", output_path
            else:
                log("Rimozione DSM esistente per rigenerazione...")
                os.remove(output_path)
        
        if not os.path.exists(dtm_path):
            return False, "DTM non trovato. Scarica prima i dati Tinitaly.", None
        
        log("Caricamento DTM di base...")
        dtm_ds = gdal.Open(dtm_path)
        if dtm_ds is None:
            return False, "Impossibile aprire DTM", None
        
        # Get raster properties from DTM (reference)
        geotransform = dtm_ds.GetGeoTransform()
        projection = dtm_ds.GetProjection()
        x_size = dtm_ds.RasterXSize
        y_size = dtm_ds.RasterYSize
        
        dtm_band = dtm_ds.GetRasterBand(1)
        dtm_nodata = dtm_band.GetNoDataValue()
        dtm_array = dtm_band.ReadAsArray().astype(np.float32)
        
        # Initialize height arrays
        building_heights = np.zeros_like(dtm_array)
        tree_heights = np.zeros_like(dtm_array)
        mask = np.ones_like(dtm_array)  # Default: all valid
        
        # 1. Rasterize buildings if available
        if os.path.exists(buildings_path):
            log("Rasterizzazione altezze edifici TUM...")
            temp_buildings_raster = os.path.join(unified_dir, "temp_buildings_height.tif")
            
            try:
                # Create temp raster for buildings
                driver = gdal.GetDriverByName('GTiff')
                temp_ds = driver.Create(temp_buildings_raster, x_size, y_size, 1, gdal.GDT_Float32)
                temp_ds.SetGeoTransform(geotransform)
                temp_ds.SetProjection(projection)
                temp_band = temp_ds.GetRasterBand(1)
                temp_band.SetNoDataValue(0)
                temp_band.Fill(0)
                
                # Open vector layer
                vector_ds = ogr.Open(buildings_path)
                if vector_ds:
                    layer = vector_ds.GetLayer()
                    
                    # Find height attribute (try common names)
                    height_attr = None
                    layer_defn = layer.GetLayerDefn()
                    for i in range(layer_defn.GetFieldCount()):
                        field_name = layer_defn.GetFieldDefn(i).GetName().lower()
                        if field_name in ['building_height', 'height', 'h', 'h_mean', 'height_mean']:
                            height_attr = layer_defn.GetFieldDefn(i).GetName()
                            break
                    
                    if height_attr:
                        log(f"  Usando attributo: {height_attr}")
                        gdal.RasterizeLayer(temp_ds, [1], layer, options=[f"ATTRIBUTE={height_attr}"])
                    else:
                        log("  Attributo altezza non trovato, uso valore fisso 10m")
                        gdal.RasterizeLayer(temp_ds, [1], layer, burn_values=[10])
                    
                    vector_ds = None
                
                temp_ds.FlushCache()
                building_heights = temp_band.ReadAsArray().astype(np.float32)
                temp_ds = None
                
                # Cleanup temp file
                if os.path.exists(temp_buildings_raster):
                    os.remove(temp_buildings_raster)
                    
                log(f"  Edifici rasterizzati. Max altezza: {np.nanmax(building_heights):.1f}m")
                
            except Exception as e:
                log(f"  Errore rasterizzazione edifici: {e}")
        else:
            log("Layer edifici non disponibile, proseguo senza altezze edifici.")
        
        # 2. Load tree heights if available
        if os.path.exists(canopy_path):
            log("Caricamento altezze vegetazione ETH...")
            canopy_ds = gdal.Open(canopy_path)
            if canopy_ds:
                # Get NoData value from the raster
                canopy_band = canopy_ds.GetRasterBand(1)
                canopy_nodata = canopy_band.GetNoDataValue()
                
                # Resample to match DTM if needed
                canopy_array = canopy_band.ReadAsArray()
                if canopy_array.shape == dtm_array.shape:
                    tree_heights = canopy_array.astype(np.float32)
                else:
                    log(f"  Dimensioni non corrispondenti (canopy: {canopy_array.shape}, dtm: {dtm_array.shape})")
                    # Use GDAL warp to resample
                    temp_resampled = os.path.join(unified_dir, "temp_canopy_resampled.tif")
                    warp_options = gdal.WarpOptions(
                        width=x_size, height=y_size,
                        outputBounds=(geotransform[0], 
                                     geotransform[3] + y_size * geotransform[5],
                                     geotransform[0] + x_size * geotransform[1],
                                     geotransform[3]),
                        resampleAlg=gdal.GRA_Bilinear
                    )
                    gdal.Warp(temp_resampled, canopy_ds, options=warp_options)
                    resampled_ds = gdal.Open(temp_resampled)
                    if resampled_ds:
                        tree_heights = resampled_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                        resampled_ds = None
                    if os.path.exists(temp_resampled):
                        os.remove(temp_resampled)
                
                # CRITICAL: Handle NoData values (often 255 in 8-bit rasters)
                # ETH Canopy Height uses 255 as NoData
                tree_heights = np.nan_to_num(tree_heights, nan=0, posinf=0, neginf=0)
                if canopy_nodata is not None:
                    tree_heights[tree_heights == canopy_nodata] = 0
                    log(f"  Filtrato NoData: {canopy_nodata}")
                # Always filter 255 as it's the common NoData for 8-bit rasters
                tree_heights[tree_heights == 255] = 0
                # Also filter unreasonable values (tallest trees are ~60m)
                tree_heights[tree_heights > 60] = 0
                
                log(f"  Altezza max vegetazione (dopo filtro): {np.max(tree_heights):.1f}m")
                canopy_ds = None
        else:
            log("Dati vegetazione ETH non disponibili.")
        
        # 3. Create mask from ESA WorldCover
        if os.path.exists(landuse_path):
            log("Creazione maschera da ESA WorldCover...")
            landuse_ds = gdal.Open(landuse_path)
            if landuse_ds:
                landuse_array = landuse_ds.GetRasterBand(1).ReadAsArray()
                
                # Handle dimension mismatch
                if landuse_array.shape != dtm_array.shape:
                    log(f"  Resampling land use da {landuse_array.shape} a {dtm_array.shape}")
                    temp_resampled = os.path.join(unified_dir, "temp_landuse_resampled.tif")
                    warp_options = gdal.WarpOptions(
                        width=x_size, height=y_size,
                        outputBounds=(geotransform[0], 
                                     geotransform[3] + y_size * geotransform[5],
                                     geotransform[0] + x_size * geotransform[1],
                                     geotransform[3]),
                        resampleAlg=gdal.GRA_NearestNeighbour
                    )
                    gdal.Warp(temp_resampled, landuse_ds, options=warp_options)
                    resampled_ds = gdal.Open(temp_resampled)
                    if resampled_ds:
                        landuse_array = resampled_ds.GetRasterBand(1).ReadAsArray()
                        resampled_ds = None
                    if os.path.exists(temp_resampled):
                        os.remove(temp_resampled)
                
                # ESA WorldCover classes to mask (set height to 0)
                # 60 = Bare / sparse vegetation
                # 80 = Permanent water bodies
                mask = np.ones_like(dtm_array)
                mask[landuse_array == 60] = 0  # Bare soil
                mask[landuse_array == 80] = 0  # Water
                
                water_pixels = np.sum(landuse_array == 80)
                bare_pixels = np.sum(landuse_array == 60)
                log(f"  Filtrati {water_pixels} pixel acqua, {bare_pixels} pixel suolo nudo")
                
                landuse_ds = None
        else:
            log("Land use ESA non disponibile, nessun filtro applicato.")
        
        # 4. Calculate DSM
        log("Calcolo DSM sintetico...")
        
        # Apply mask to heights (zero out heights in water/bare areas)
        building_heights_filtered = building_heights * mask
        tree_heights_filtered = tree_heights * mask
        
        # Handle nodata in DTM
        if dtm_nodata is not None:
            valid_dtm = dtm_array != dtm_nodata
        else:
            valid_dtm = ~np.isnan(dtm_array)
        
        # DIAGNOSTIC: Log value ranges for debugging
        log(f"=== DIAGNOSTICA VALORI ===")
        dtm_valid = dtm_array[valid_dtm]
        log(f"  DTM: min={np.min(dtm_valid):.1f}m, max={np.max(dtm_valid):.1f}m, mean={np.mean(dtm_valid):.1f}m")
        
        bh_valid = building_heights_filtered[building_heights_filtered > 0]
        if len(bh_valid) > 0:
            log(f"  Buildings: min={np.min(bh_valid):.1f}m, max={np.max(bh_valid):.1f}m, mean={np.mean(bh_valid):.1f}m, count={len(bh_valid)}")
        else:
            log(f"  Buildings: nessun valore > 0")
        
        th_valid = tree_heights_filtered[tree_heights_filtered > 0]
        if len(th_valid) > 0:
            log(f"  Trees: min={np.min(th_valid):.1f}m, max={np.max(th_valid):.1f}m, mean={np.mean(th_valid):.1f}m, count={len(th_valid)}")
        else:
            log(f"  Trees: nessun valore > 0")
        
        # VALIDATION: Cap unreasonable heights
        # Max building height in Italy is ~200m (Unicredit Tower), most are < 50m
        # Max tree height is ~50m (Sequoia), most are < 30m
        MAX_BUILDING_HEIGHT = 200.0
        MAX_TREE_HEIGHT = 60.0
        
        building_heights_filtered = np.clip(building_heights_filtered, 0, MAX_BUILDING_HEIGHT)
        tree_heights_filtered = np.clip(tree_heights_filtered, 0, MAX_TREE_HEIGHT)
        
        # DSM = DTM + MAX(Buildings, Trees)
        # The tallest element (building or tree) determines the surface height
        surface_heights = np.maximum(building_heights_filtered, tree_heights_filtered)
        
        log(f"  Surface heights (MAX): max={np.max(surface_heights):.1f}m")
        
        dsm_array = np.where(
            valid_dtm,
            dtm_array + surface_heights,
            dtm_array  # Keep original DTM for nodata areas
        )
        
        # Final DSM stats
        dsm_valid = dsm_array[valid_dtm]
        log(f"  DSM finale: min={np.min(dsm_valid):.1f}m, max={np.max(dsm_valid):.1f}m")
        log(f"=========================")
        
        # 5. Write output
        log("Salvataggio DSM sintetico...")
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path, x_size, y_size, 1, gdal.GDT_Float32,
            options=['COMPRESS=DEFLATE', 'PREDICTOR=2', 'ZLEVEL=6']
        )
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        out_band = out_ds.GetRasterBand(1)
        if dtm_nodata is not None:
            out_band.SetNoDataValue(dtm_nodata)
        out_band.WriteArray(dsm_array)
        out_ds.FlushCache()
        out_ds = None
        dtm_ds = None
        
        # Stats
        valid_values = dsm_array[valid_dtm]
        log(f"DSM creato: min={np.min(valid_values):.1f}m, max={np.max(valid_values):.1f}m")
        
        return True, "DSM sintetico creato con successo", output_path

    def calculate_svf(self, log_callback=None, search_radius=100, num_sectors=16):
        """
        Calculates Sky View Factor (SVF) from the synthetic DSM using pure Python.
        
        Uses the horizon angle method: for each direction, find the maximum 
        elevation angle to obstacles, then calculate visible sky fraction.
        
        SVF = 1 - mean(sin²(horizon_angles)) across all directions
        
        Args:
            log_callback: Optional callback for logging messages
            search_radius: Maximum search radius in meters (default 100m for urban)
            num_sectors: Number of directional sectors for analysis (default 16)
        
        Returns:
            tuple: (success, message, output_path)
        """
        import numpy as np
        from osgeo import gdal
        
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        # Get paths
        base_dir = self.get_project_dir()
        if not base_dir:
            return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        if not os.path.exists(unified_dir):
            return False, "Cartella unified non trovata", None
        
        dsm_path = os.path.join(unified_dir, "dsm_10m.tif")
        output_svf = os.path.join(unified_dir, "svf_10m.tif")
        
        if not os.path.exists(dsm_path):
            return False, "DSM non trovato. Genera prima il DSM sintetico.", None
        
        # Check if already exists
        if os.path.exists(output_svf):
            log("SVF già presente, rimozione per ricalcolo...")
            os.remove(output_svf)
        
        log(f"Calcolo Sky View Factor (raggio={search_radius}m, settori={num_sectors})...")
        log("Algoritmo: Python/NumPy (horizon angle method)")
        
        try:
            # Open DSM
            dsm_ds = gdal.Open(dsm_path)
            if dsm_ds is None:
                return False, "Impossibile aprire DSM", None
            
            geotransform = dsm_ds.GetGeoTransform()
            projection = dsm_ds.GetProjection()
            x_size = dsm_ds.RasterXSize
            y_size = dsm_ds.RasterYSize
            
            dsm_band = dsm_ds.GetRasterBand(1)
            dsm_nodata = dsm_band.GetNoDataValue()
            dsm_array = dsm_band.ReadAsArray().astype(np.float32)
            
            # Get pixel size
            pixel_size = abs(geotransform[1])  # Assume square pixels
            
            # Calculate search radius in pixels
            radius_pixels = int(search_radius / pixel_size)
            radius_pixels = max(5, min(radius_pixels, 50))  # Limit between 5 and 50 pixels
            
            log(f"Raggio ricerca: {radius_pixels} pixel ({radius_pixels * pixel_size:.1f}m)")
            log(f"Dimensioni raster: {x_size}x{y_size} pixel")
            
            # Initialize SVF array
            svf_array = np.ones_like(dsm_array)
            
            # Create direction vectors (angles in radians)
            angles = np.linspace(0, 2 * np.pi, num_sectors, endpoint=False)
            
            # For each direction, calculate horizon angle contribution
            total_pixels = y_size * x_size
            processed = 0
            last_progress = 0
            
            log("Calcolo angoli orizzonte per ogni direzione...")
            
            # Process in batches for efficiency
            # Use vectorized approach for each direction
            horizon_sin2_sum = np.zeros_like(dsm_array)
            
            for idx, angle in enumerate(angles):
                # Direction vector
                dx = np.cos(angle)
                dy = np.sin(angle)
                
                # Create offset arrays for this direction
                max_horizon_angle = np.zeros_like(dsm_array)
                
                # Sample along the ray at increasing distances
                for dist in range(1, radius_pixels + 1):
                    # Calculate pixel offsets
                    offset_x = int(round(dx * dist))
                    offset_y = int(round(dy * dist))
                    
                    if offset_x == 0 and offset_y == 0:
                        continue
                    
                    # Distance in meters
                    distance_m = dist * pixel_size
                    
                    # Get elevation at offset position using array slicing
                    # Create shifted view of DSM
                    if offset_y >= 0 and offset_x >= 0:
                        src_y = slice(0, y_size - offset_y) if offset_y > 0 else slice(0, y_size)
                        src_x = slice(0, x_size - offset_x) if offset_x > 0 else slice(0, x_size)
                        dst_y = slice(offset_y, y_size) if offset_y > 0 else slice(0, y_size)
                        dst_x = slice(offset_x, x_size) if offset_x > 0 else slice(0, x_size)
                    elif offset_y >= 0 and offset_x < 0:
                        src_y = slice(0, y_size - offset_y) if offset_y > 0 else slice(0, y_size)
                        src_x = slice(-offset_x, x_size)
                        dst_y = slice(offset_y, y_size) if offset_y > 0 else slice(0, y_size)
                        dst_x = slice(0, x_size + offset_x)
                    elif offset_y < 0 and offset_x >= 0:
                        src_y = slice(-offset_y, y_size)
                        src_x = slice(0, x_size - offset_x) if offset_x > 0 else slice(0, x_size)
                        dst_y = slice(0, y_size + offset_y)
                        dst_x = slice(offset_x, x_size) if offset_x > 0 else slice(0, x_size)
                    else:  # both negative
                        src_y = slice(-offset_y, y_size)
                        src_x = slice(-offset_x, x_size)
                        dst_y = slice(0, y_size + offset_y)
                        dst_x = slice(0, x_size + offset_x)
                    
                    # Calculate elevation difference
                    elev_diff = dsm_array[src_y, src_x] - dsm_array[dst_y, dst_x]
                    
                    # Calculate horizon angle (arctan of elevation/distance)
                    horizon_angle = np.arctan2(elev_diff, distance_m)
                    
                    # Update maximum horizon angle
                    current_max = max_horizon_angle[dst_y, dst_x]
                    max_horizon_angle[dst_y, dst_x] = np.maximum(current_max, horizon_angle)
                
                # Accumulate sin²(horizon_angle) for this direction
                # Only count positive angles (obstacles above horizon)
                positive_angles = np.maximum(max_horizon_angle, 0)
                horizon_sin2_sum += np.sin(positive_angles) ** 2
                
                # Progress update
                progress = int((idx + 1) / num_sectors * 100)
                if progress >= last_progress + 10:
                    log(f"Progresso: {progress}%")
                    last_progress = progress
            
            # Calculate SVF: 1 - mean(sin²(horizon_angles))
            svf_array = 1 - (horizon_sin2_sum / num_sectors)
            
            # Clamp to valid range [0, 1]
            svf_array = np.clip(svf_array, 0, 1)
            
            # Handle nodata
            if dsm_nodata is not None:
                svf_array[dsm_array == dsm_nodata] = dsm_nodata
            
            # Close input
            dsm_ds = None
            
            # Write output
            log("Salvataggio SVF...")
            driver = gdal.GetDriverByName('GTiff')
            out_ds = driver.Create(
                output_svf, x_size, y_size, 1, gdal.GDT_Float32,
                options=['COMPRESS=DEFLATE', 'PREDICTOR=2', 'ZLEVEL=6']
            )
            out_ds.SetGeoTransform(geotransform)
            out_ds.SetProjection(projection)
            out_band = out_ds.GetRasterBand(1)
            if dsm_nodata is not None:
                out_band.SetNoDataValue(dsm_nodata)
            out_band.WriteArray(svf_array)
            out_ds.FlushCache()
            out_ds = None
            
            # Get stats
            valid_mask = svf_array != dsm_nodata if dsm_nodata is not None else np.ones_like(svf_array, dtype=bool)
            valid_svf = svf_array[valid_mask]
            log(f"SVF calcolato: min={np.min(valid_svf):.3f}, max={np.max(valid_svf):.3f}, mean={np.mean(valid_svf):.3f}")
            
            return True, "Sky View Factor calcolato con successo", output_svf
                
        except Exception as e:
            log(f"Errore durante il calcolo SVF: {str(e)}")
            return False, f"Errore SVF: {str(e)}", None


    def create_lcz_grid(self, extent, crs_auth_id, cell_size=100, log_callback=None):
        """
        Crea una griglia regolare per la classificazione LCZ.
        
        Args:
            extent: QgsRectangle dell'AOI
            crs_auth_id: CRS dell'extent
            cell_size: Dimensione cella in metri (30, 50, o 100)
            log_callback: Callback per logging
        
        Returns:
            tuple: (success, message, output_path)
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        # Get paths
        base_dir = self.get_project_dir()
        if not base_dir:
            return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        if not os.path.exists(unified_dir):
            os.makedirs(unified_dir)
        
        output_path = os.path.join(unified_dir, f"lcz_grid_{cell_size}m.gpkg")
        
        # Check if already exists
        if os.path.exists(output_path):
            log(f"Griglia {cell_size}m già esistente, rimuovo per rigenerare...")
            os.remove(output_path)
        
        # Get target CRS (UTM)
        target_crs_auth = self.get_utm_zone_for_extent(extent, crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem(target_crs_auth)
        log(f"CRS target: {target_crs_auth}")
        
        # Transform extent to UTM
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        utm_extent = transform.transformBoundingBox(extent)
        
        # Calculate grid dimensions
        width = utm_extent.xMaximum() - utm_extent.xMinimum()
        height = utm_extent.yMaximum() - utm_extent.yMinimum()
        n_cols = int(math.ceil(width / cell_size))
        n_rows = int(math.ceil(height / cell_size))
        total_cells = n_cols * n_rows
        
        log(f"Generazione griglia: {n_cols} colonne x {n_rows} righe = {total_cells} celle")
        log(f"Dimensione cella: {cell_size}m x {cell_size}m")
        
        try:
            # Use QGIS Processing to create grid
            extent_str = f"{utm_extent.xMinimum()},{utm_extent.xMaximum()},{utm_extent.yMinimum()},{utm_extent.yMaximum()} [{target_crs_auth}]"
            
            grid_params = {
                'TYPE': 2,  # Rectangle (polygon)
                'EXTENT': extent_str,
                'HSPACING': cell_size,
                'VSPACING': cell_size,
                'HOVERLAY': 0,
                'VOVERLAY': 0,
                'CRS': target_crs,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            
            result = processing.run("native:creategrid", grid_params)
            temp_grid = result['OUTPUT']
            
            log(f"Griglia temporanea creata: {temp_grid.featureCount()} celle")
            
            # Add grid_id, row, col attributes
            from qgis.core import QgsField, QgsVectorFileWriter, QgsFeature
            from qgis.PyQt.QtCore import QVariant
            
            # Create new layer with additional fields
            fields = temp_grid.fields()
            fields.append(QgsField("grid_id", QVariant.Int))
            fields.append(QgsField("row", QVariant.Int))
            fields.append(QgsField("col", QVariant.Int))
            
            # Write to GeoPackage
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.fileEncoding = "UTF-8"
            
            writer = QgsVectorFileWriter.create(
                output_path,
                fields,
                temp_grid.wkbType(),
                target_crs,
                QgsProject.instance().transformContext(),
                options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return False, f"Errore creazione file: {writer.errorMessage()}", None
            
            # Add features with calculated attributes
            grid_id = 0
            for feature in temp_grid.getFeatures():
                new_feat = QgsFeature(fields)
                new_feat.setGeometry(feature.geometry())
                
                # Copy original attributes
                for i in range(temp_grid.fields().count()):
                    new_feat.setAttribute(i, feature.attribute(i))
                
                # Calculate row and col from grid_id
                row = grid_id // n_cols
                col = grid_id % n_cols
                
                new_feat.setAttribute("grid_id", grid_id)
                new_feat.setAttribute("row", row)
                new_feat.setAttribute("col", col)
                
                writer.addFeature(new_feat)
                grid_id += 1
            
            del writer
            
            log(f"✓ Griglia salvata: {output_path}")
            log(f"  Celle totali: {grid_id}")
            
            return True, f"Griglia {cell_size}m creata con {grid_id} celle", output_path
            
        except Exception as e:
            log(f"✗ Errore creazione griglia: {str(e)}")
            return False, f"Errore: {str(e)}", None

    def use_existing_grid(self, layer, extent, crs_auth_id, log_callback=None):
        """
        Usa un layer vettoriale esistente come griglia LCZ.
        Clip e riproietta se necessario.
        
        Args:
            layer: QgsVectorLayer da usare come griglia
            extent: QgsRectangle dell'AOI
            crs_auth_id: CRS dell'extent
            log_callback: Callback per logging
        
        Returns:
            tuple: (success, message, output_path)
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        if not layer or not layer.isValid():
            return False, "Layer non valido", None
        
        # Get paths
        base_dir = self.get_project_dir()
        if not base_dir:
            return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        if not os.path.exists(unified_dir):
            os.makedirs(unified_dir)
        
        output_path = os.path.join(unified_dir, "lcz_grid_custom.gpkg")
        
        # Check if already exists
        if os.path.exists(output_path):
            log("Griglia custom già esistente, rimuovo per rigenerare...")
            os.remove(output_path)
        
        log(f"Usando layer esistente: {layer.name()}")
        log(f"Geometrie originali: {layer.featureCount()}")
        
        # Get target CRS (UTM)
        target_crs_auth = self.get_utm_zone_for_extent(extent, crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem(target_crs_auth)
        
        # Transform extent to UTM for clipping
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        utm_extent = transform.transformBoundingBox(extent)
        
        try:
            # Step 1: Reproject if needed
            if layer.crs() != target_crs:
                log(f"Riproiezione da {layer.crs().authid()} a {target_crs_auth}...")
                temp_reprojected = os.path.join(unified_dir, "temp_grid_reprojected.gpkg")
                
                reproject_params = {
                    'INPUT': layer,
                    'TARGET_CRS': target_crs,
                    'OUTPUT': temp_reprojected
                }
                processing.run("native:reprojectlayer", reproject_params)
                input_for_clip = temp_reprojected
            else:
                input_for_clip = layer
            
            # Step 2: Clip to AOI extent
            log("Ritaglio sull'estensione AOI...")
            extent_str = f"{utm_extent.xMinimum()},{utm_extent.xMaximum()},{utm_extent.yMinimum()},{utm_extent.yMaximum()}"
            
            clip_params = {
                'INPUT': input_for_clip,
                'EXTENT': extent_str,
                'CLIP': True,
                'OUTPUT': output_path
            }
            processing.run("native:extractbyextent", clip_params)
            
            # Cleanup temp file
            if layer.crs() != target_crs:
                temp_reprojected = os.path.join(unified_dir, "temp_grid_reprojected.gpkg")
                if os.path.exists(temp_reprojected):
                    os.remove(temp_reprojected)
            
            # Get final count
            from qgis.core import QgsVectorLayer
            result_layer = QgsVectorLayer(output_path, "temp", "ogr")
            if result_layer.isValid():
                final_count = result_layer.featureCount()
                log(f"✓ Griglia custom salvata: {final_count} celle")
                return True, f"Griglia custom con {final_count} celle", output_path
            else:
                return False, "Layer risultante non valido", None
                
        except Exception as e:
            log(f"✗ Errore: {str(e)}")
            return False, f"Errore: {str(e)}", None

    def load_grid_layer(self, grid_path, log_callback=None):
        """
        Carica il layer griglia nel progetto QGIS.
        
        Args:
            grid_path: Path al file griglia (.gpkg)
            log_callback: Callback per logging
        
        Returns:
            QgsVectorLayer or None
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        if not os.path.exists(grid_path):
            log(f"File griglia non trovato: {grid_path}")
            return None
        
        from qgis.core import QgsVectorLayer
        
        # Determine display name
        basename = os.path.basename(grid_path)
        if "custom" in basename:
            display_name = "Griglia LCZ (custom)"
        else:
            # Extract cell size from filename
            import re
            match = re.search(r'(\d+)m', basename)
            if match:
                display_name = f"Griglia LCZ ({match.group(1)}m)"
            else:
                display_name = "Griglia LCZ"
        
        # Check if already loaded
        existing = QgsProject.instance().mapLayersByName(display_name)
        for lyr in existing:
            QgsProject.instance().removeMapLayer(lyr.id())
            log(f"Rimosso layer precedente: {display_name}")
        
        # Load new layer
        layer = QgsVectorLayer(grid_path, display_name, "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            log(f"✓ Caricato layer: {display_name}")
            return layer
        else:
            log(f"✗ Layer non valido: {grid_path}")
            return None

    def calculate_surface_fractions(self, grid_path=None, log_callback=None):
        """
        Calcola le frazioni di superficie per ogni cella della griglia LCZ.
        
        Frazioni calcolate:
        - building_frac: % edifici (da TUM LoD1 vettoriale)
        - impervious_frac: % impermeabile esclusi edifici (ESA classe 50 - edifici)
        - pervious_frac: % permeabile (ESA classi 10,20,30,40,60,90,95,100)
        
        Args:
            grid_path: Path alla griglia LCZ (opzionale, cerca automaticamente)
            log_callback: Callback per logging
        
        Returns:
            tuple: (success, message, updated_grid_path)
        """
        import numpy as np
        from osgeo import gdal, ogr
        from qgis.core import QgsVectorLayer, QgsField, QgsFeature, QgsGeometry
        from qgis.PyQt.QtCore import QVariant
        
        def log(msg):
            if log_callback:
                log_callback(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        
        # Get paths
        base_dir = self.get_project_dir()
        if not base_dir:
            return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        if not os.path.exists(unified_dir):
            return False, "Cartella unified non trovata", None
        
        # Find grid file
        if grid_path is None:
            # Look for any grid file
            import glob
            grid_files = glob.glob(os.path.join(unified_dir, "lcz_grid_*.gpkg"))
            if not grid_files:
                return False, "Griglia LCZ non trovata. Genera prima la griglia.", None
            grid_path = grid_files[0]
        
        if not os.path.exists(grid_path):
            return False, f"File griglia non trovato: {grid_path}", None
        
        # Check required files
        landuse_path = os.path.join(unified_dir, "landuse_10m.tif")
        buildings_path = os.path.join(unified_dir, "buildings_lod1.gpkg")
        
        if not os.path.exists(landuse_path):
            return False, "ESA WorldCover non trovato. Scarica prima i dati.", None
        
        log(f"Griglia: {os.path.basename(grid_path)}")
        log(f"Land Use: {os.path.basename(landuse_path)}")
        log(f"Edifici: {'Presente' if os.path.exists(buildings_path) else 'Non presente'}")
        
        # Load grid layer
        grid_layer = QgsVectorLayer(grid_path, "grid_temp", "ogr")
        if not grid_layer.isValid():
            return False, "Impossibile aprire la griglia", None
        
        feature_count = grid_layer.featureCount()
        log(f"Celle griglia: {feature_count}")
        
        # ESA WorldCover class mapping
        # Pervious classes: 10 (tree), 20 (shrub), 30 (grass), 40 (crop), 
        #                   60 (bare), 90 (wetland), 95 (mangrove), 100 (moss)
        # Impervious: 50 (built-up)
        # Excluded: 70 (snow), 80 (water)
        PERVIOUS_CLASSES = [10, 20, 30, 40, 60, 90, 95, 100]
        IMPERVIOUS_CLASS = 50
        EXCLUDED_CLASSES = [70, 80]
        
        # Open landuse raster
        landuse_ds = gdal.Open(landuse_path)
        if not landuse_ds:
            return False, "Impossibile aprire ESA WorldCover", None
        
        landuse_band = landuse_ds.GetRasterBand(1)
        landuse_gt = landuse_ds.GetGeoTransform()
        landuse_data = landuse_band.ReadAsArray()
        
        # Load buildings if available
        buildings_layer = None
        if os.path.exists(buildings_path):
            buildings_layer = QgsVectorLayer(buildings_path, "buildings_temp", "ogr")
            if not buildings_layer.isValid():
                log("⚠ Layer edifici non valido, proseguo senza")
                buildings_layer = None
            else:
                log(f"Edifici caricati: {buildings_layer.featureCount()} feature")
        
        # Prepare output - create new grid with attributes
        output_path = grid_path.replace(".gpkg", "_lcz_params.gpkg")
        if os.path.exists(output_path):
            os.remove(output_path)
        
        # Copy grid and add new fields
        from qgis.core import QgsVectorFileWriter, QgsFields
        
        # Get existing fields and add new ones
        fields = grid_layer.fields()
        new_fields = [
            QgsField("building_frac", QVariant.Double, 'double', 10, 2),
            QgsField("impervious_frac", QVariant.Double, 'double', 10, 2),
            QgsField("pervious_frac", QVariant.Double, 'double', 10, 2),
        ]
        for f in new_fields:
            fields.append(f)
        
        # Create output file
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        
        writer = QgsVectorFileWriter.create(
            output_path,
            fields,
            grid_layer.wkbType(),
            grid_layer.crs(),
            QgsProject.instance().transformContext(),
            options
        )
        
        if writer.hasError() != QgsVectorFileWriter.NoError:
            return False, f"Errore creazione output: {writer.errorMessage()}", None
        
        # Process each grid cell
        log("Calcolo frazioni di superficie...")
        processed = 0
        
        for feature in grid_layer.getFeatures():
            geom = feature.geometry()
            bbox = geom.boundingBox()
            cell_area = geom.area()
            
            if cell_area <= 0:
                continue
            
            # 1. Calculate Building Fraction from vector layer
            building_frac = 0.0
            if buildings_layer:
                building_area = 0.0
                # Get buildings intersecting this cell
                for bldg in buildings_layer.getFeatures():
                    bldg_geom = bldg.geometry()
                    if bldg_geom.intersects(geom):
                        intersection = bldg_geom.intersection(geom)
                        if intersection:
                            building_area += intersection.area()
                
                building_frac = min(100.0, (building_area / cell_area) * 100)
            
            # 2. Calculate from ESA WorldCover (raster statistics)
            # Convert bbox to pixel coordinates
            x_min_px = int((bbox.xMinimum() - landuse_gt[0]) / landuse_gt[1])
            x_max_px = int((bbox.xMaximum() - landuse_gt[0]) / landuse_gt[1])
            y_min_px = int((bbox.yMaximum() - landuse_gt[3]) / landuse_gt[5])  # Note: inverted
            y_max_px = int((bbox.yMinimum() - landuse_gt[3]) / landuse_gt[5])
            
            # Clamp to raster bounds
            x_min_px = max(0, x_min_px)
            x_max_px = min(landuse_ds.RasterXSize, x_max_px)
            y_min_px = max(0, y_min_px)
            y_max_px = min(landuse_ds.RasterYSize, y_max_px)
            
            if x_max_px <= x_min_px or y_max_px <= y_min_px:
                # Cell outside raster bounds
                impervious_frac = 0.0
                pervious_frac = 100.0 - building_frac
            else:
                # Extract subset
                subset = landuse_data[y_min_px:y_max_px, x_min_px:x_max_px]
                total_pixels = subset.size
                
                if total_pixels > 0:
                    # Count pixels by class
                    impervious_pixels = np.sum(subset == IMPERVIOUS_CLASS)
                    pervious_pixels = sum(np.sum(subset == c) for c in PERVIOUS_CLASSES)
                    excluded_pixels = sum(np.sum(subset == c) for c in EXCLUDED_CLASSES)
                    
                    valid_pixels = total_pixels - excluded_pixels
                    
                    if valid_pixels > 0:
                        # ESA built-up fraction
                        esa_builtup_frac = (impervious_pixels / valid_pixels) * 100
                        
                        # Impervious = ESA built-up minus buildings (to avoid double counting)
                        impervious_frac = max(0, esa_builtup_frac - building_frac)
                        
                        # Pervious = rest
                        pervious_frac = max(0, 100.0 - building_frac - impervious_frac)
                    else:
                        impervious_frac = 0.0
                        pervious_frac = 100.0 - building_frac
                else:
                    impervious_frac = 0.0
                    pervious_frac = 100.0 - building_frac
            
            # Create new feature with calculated values
            new_feat = QgsFeature(fields)
            new_feat.setGeometry(geom)
            
            # Copy original attributes
            for i in range(grid_layer.fields().count()):
                new_feat.setAttribute(i, feature.attribute(i))
            
            # Set new attributes
            new_feat.setAttribute("building_frac", round(building_frac, 2))
            new_feat.setAttribute("impervious_frac", round(impervious_frac, 2))
            new_feat.setAttribute("pervious_frac", round(pervious_frac, 2))
            
            writer.addFeature(new_feat)
            
            processed += 1
            if processed % 100 == 0:
                log(f"Processate {processed}/{feature_count} celle...")
        
        del writer
        landuse_ds = None
        
        log(f"✓ Calcolo completato: {processed} celle processate")
        log(f"✓ Output salvato: {os.path.basename(output_path)}")
        
        return True, f"Frazioni calcolate per {processed} celle", output_path

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
