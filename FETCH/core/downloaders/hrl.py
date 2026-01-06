# -*- coding: utf-8 -*-

import os
import requests
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle
from ..utils import download_file_generic

class HRLDownloader:
    def __init__(self, data_manager):
        self.dm = data_manager
        # Updated WMS endpoint for 10m Imperviousness (2018)
        self.wms_url = "https://image.discomap.eea.europa.eu/arcgis/services/GioLandPublic/HRL_ImperviousnessDensity_2018/ImageServer/WMSServer"

    def fetch_imperviousness(self, extent, crs_auth_id, log_callback=None):
        """
        Fetches Copernicus HRL Imperviousness 10m by creating a WMS layer 
        and translating it to a physical TIF using GDAL.
        """
        import processing
        from qgis.core import QgsRasterLayer, QgsProject
        
        def log(msg):
            if log_callback: log_callback(msg)
            
        output_dir = self.dm.get_download_dir("copernicus_hrl")
        if not output_dir: return False, "Project not saved"
        
        output_path = os.path.join(output_dir, "imperviousness_10m.tif")
        if os.path.exists(output_path):
            log("Dati HRL già presenti, salto download.")
            return True, output_path

        log("Acquisizione Copernicus HRL tramite ArcGIS REST Export Image...")
        
        # 1. Transform extent to EPSG:3857 (native for this service) or keep as is
        # The service native is 3857, but we can request in 4326.
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        w84 = transform.transformBoundingBox(extent)
        
        # Calculate size based on 10m resolution
        # First, get extent in metric (UTM or 3857) to estimate pixel count
        metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        metric_transform = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())
        metric_extent = metric_transform.transformBoundingBox(extent)
        
        width_pixels = int(abs(metric_extent.width()) / 10.0)
        height_pixels = int(abs(metric_extent.height()) / 10.0)
        
        # Limit size to ArcGIS default max (usually 4096)
        width_pixels = min(max(width_pixels, 100), 4000)
        height_pixels = min(max(height_pixels, 100), 4000)
        
        rest_url = "https://image.discomap.eea.europa.eu/arcgis/rest/services/GioLandPublic/HRL_ImperviousnessDensity_2018/ImageServer/exportImage"
        
        params = {
            'bbox': f"{w84.xMinimum()},{w84.yMinimum()},{w84.xMaximum()},{w84.yMaximum()}",
            'bboxSR': '4326',
            'size': f"{width_pixels},{height_pixels}",
            'format': 'tiff',
            'pixelType': 'U8',
            'noData': '255',
            'f': 'image'
        }

        try:
            log(f"Richiesta exportImage (Risoluzione stimata: {width_pixels}x{height_pixels} px)...")
            
            # Prepare full URL with params for download_file_generic
            prep = requests.Request('GET', rest_url, params=params).prepare()
            full_url = prep.url
            log(f"DEBUG URL: {full_url}")
            
            success, msg = download_file_generic(full_url, output_path)
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                log(f"Download HRL completato con successo: {output_path}")
                return True, output_path
            else:
                log(f"ERRORE Acquisizione HRL: {msg}")
                return False, msg
                
        except Exception as e:
            log(f"Errore critico acquisizione HRL: {str(e)}")
            import traceback
            log(traceback.format_exc())
            return False, str(e)
