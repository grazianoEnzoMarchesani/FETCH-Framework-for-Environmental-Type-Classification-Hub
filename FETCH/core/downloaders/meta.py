# -*- coding: utf-8 -*-

import os
import zipfile
import processing
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, Qgis
)
from .base import BaseDownloader

class MetaDownloader(BaseDownloader):
    def __init__(self, data_manager):
        super().__init__(data_manager)
        self.url = "https://data.humdata.org/dataset/0eb77b21-06be-42c8-9245-2edaff79952f/resource/a5f709f2-9871-46ab-a573-a25b0a7615ca/download/ita_general_2020_geotiff.zip"

    def fetch_hrsl(self, extent, crs_auth_id):
        self.log("Avvio acquisizione Meta HRSL (Popolazione)...")
        
        download_dir = self.get_download_dir("meta_hrsl")
        if not download_dir: return False, "Project not saved"
        
        cache_dir = os.path.join(download_dir, "cache")
        if not os.path.exists(cache_dir): os.makedirs(cache_dir)
        
        zip_path = os.path.join(cache_dir, "ita_population.zip")
        output_aoi = os.path.join(download_dir, "meta_hrsl_aoi.tif")
        
        if os.path.exists(output_aoi):
            return True, "Clipped population raster già presente"

        if not os.path.exists(zip_path):
            self.log("Download del dataset nazionale Meta HRSL (~500MB)...")
            success, msg = self._download_file(self.url, zip_path)
            if not success: return False, f"Download fallito: {msg}"
        
        tif_found = None
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for name in zip_ref.namelist():
                    if name.lower().endswith('.tif') and not name.startswith('__MACOSX'):
                        tif_found = os.path.join(cache_dir, name)
                        if not os.path.exists(tif_found):
                            self.log(f"Estrazione {name}...")
                            zip_ref.extract(name, cache_dir)
                        break
        except Exception as e:
            return False, f"Errore estrazione ZIP: {e}"
        
        if not tif_found or not os.path.exists(tif_found):
            return False, "Nessun file TIF trovato nello ZIP della popolazione"

        try:
            self.log(f"Ritaglio Meta HRSL sull'estensione AOI...")
            
            source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
            wgs84_extent = transform.transformBoundingBox(extent)
            
            if os.path.exists(output_aoi):
                if os.path.getsize(output_aoi) > 1024 * 1024 * 1024:
                    self.log("Rilevato file AOI sovradimensionato, rimozione...", Qgis.Warning)
                    os.remove(output_aoi)

            params = {
                'INPUT': tif_found,
                'PROJWIN': wgs84_extent,
                'OVERWM': 0,
                'RTYPE': 5,
                'OPTIONS': 'COMPRESS=DEFLATE|PREDICTOR=2|ZLEVEL=9',
                'DATA_TYPE': 5,
                'EXTRA': '',
                'OUTPUT': output_aoi
            }
            
            processing.run("gdal:cliprasterbyextent", params)
            
            if os.path.exists(output_aoi):
                try:
                    self.log("Pulizia cache: rimozione dataset nazionale.")
                    os.remove(tif_found)
                except Exception as e:
                    self.log(f"Impossibile rimuovere file cache: {e}", Qgis.Warning)
                return True, "Ritaglio popolazione completato"
            else:
                return False, "Errore durante il clipping GDAL"
        except Exception as e:
            return False, f"Errore durante il clipping: {e}"
