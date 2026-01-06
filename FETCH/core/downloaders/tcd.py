# -*- coding: utf-8 -*-
"""
Tree Cover Density (TCD) Downloader

Downloads Copernicus HRL Tree Cover Density data via ArcGIS REST API.
Source: https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover
"""

import os
import requests
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle
from ..utils import download_file_generic


class TCDDownloader:
    def __init__(self, data_manager):
        self.dm = data_manager
        # ArcGIS REST endpoint for Tree Cover Density 2018 (10m)
        self.rest_url = "https://image.discomap.eea.europa.eu/arcgis/rest/services/GioLandPublic/HRL_TreeCoverDensity_2018/ImageServer/exportImage"

    def fetch_tree_cover_density(self, extent, crs_auth_id, log_callback=None):
        """
        Fetches Copernicus HRL Tree Cover Density 10m via ArcGIS REST exportImage.
        
        TCD values: 0-100 (percentage of tree cover per pixel)
        
        Returns:
            tuple: (success: bool, path_or_message: str)
        """
        def log(msg):
            if log_callback: log_callback(msg)
            
        output_dir = self.dm.get_download_dir("copernicus_hrl")
        if not output_dir: 
            return False, "Project not saved"
        
        output_path = os.path.join(output_dir, "tcd_10m.tif")
        if os.path.exists(output_path):
            log("Dati TCD già presenti, salto download.")
            return True, output_path

        log("Acquisizione Copernicus Tree Cover Density (TCD) 10m...")
        
        # 1. Transform extent to EPSG:4326 for REST API
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        w84 = transform.transformBoundingBox(extent)
        
        # 2. Calculate pixel dimensions based on 10m resolution
        metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        metric_transform = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())
        metric_extent = metric_transform.transformBoundingBox(extent)
        
        width_pixels = int(abs(metric_extent.width()) / 10.0)
        height_pixels = int(abs(metric_extent.height()) / 10.0)
        
        # Limit size to ArcGIS default max (usually 4096)
        width_pixels = min(max(width_pixels, 100), 4000)
        height_pixels = min(max(height_pixels, 100), 4000)
        
        # 3. Build REST request
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
            log(f"Richiesta TCD exportImage (Risoluzione: {width_pixels}x{height_pixels} px)...")
            
            # Prepare full URL for download
            prep = requests.Request('GET', self.rest_url, params=params).prepare()
            full_url = prep.url
            
            success, msg = download_file_generic(full_url, output_path)
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                log(f"Download TCD completato: {output_path}")
                return True, output_path
            else:
                log(f"ERRORE Acquisizione TCD: {msg}")
                return False, msg
                
        except Exception as e:
            log(f"Errore critico acquisizione TCD: {str(e)}")
            import traceback
            log(traceback.format_exc())
            return False, str(e)
