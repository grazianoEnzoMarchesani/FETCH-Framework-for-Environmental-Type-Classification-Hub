# -*- coding: utf-8 -*-

"""
Data Manager for the IT-LCZ Suite.
Handles programmatic fetching, caching, and preprocessing of national-scale datasets.
"""

import os
from typing import Dict, Any, Optional, List
from qgis.core import (QgsRectangle, QgsCoordinateReferenceSystem, 
                       QgsCoordinateTransform, QgsProject, QgsMessageLog, Qgis)

class LCZDataManager:
    """
    Orchestrates downloads from multiple geospatial services for Italy.
    Supports Tinitaly, TUM, ETH, ESA, Meta, and Copernicus.
    """

    def __init__(self, base_dir: str):
        """
        Initialize the DataManager.
        
        Args:
            base_dir: Absolute path where data should be stored (usually the project folder).
        """
        self.base_dir = base_dir
        self.data_dir = os.path.join(base_dir, 'lcz_data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Define paths for specific layers
        self.paths = {
            'dtm': os.path.join(self.data_dir, 'tinitaly_dtm.tif'),
            'buildings': os.path.join(self.data_dir, 'tum_buildings.tif'),
            'canopy': os.path.join(self.data_dir, 'eth_canopy.tif'),
            'landcover': os.path.join(self.data_dir, 'esa_worldcover.tif'),
            'population': os.path.join(self.data_dir, 'meta_population.tif'),
            'albedo': os.path.join(self.data_dir, 's2_albedo.tif')
        }

    def log(self, message: str, level: Qgis.MessageLevel = Qgis.Info):
        """Standardized logging to QGIS Message Log."""
        QgsMessageLog.logMessage(message, "IT-LCZ DataMgr", level)

    def download_all(self, extent_wgs84: QgsRectangle, progress_callback=None):
        """
        High-level orchestrator to download all datasets for the given AOI.
        """
        self.log(f"Project Workspace: {self.data_dir}")
        self.log(f"Target BBox (WGS84): {extent_wgs84.asWktCoordinates()}")
        
        services = [
            ('DTM (Tinitaly)', self.fetch_tinitaly),
            ('Buildings (TUM)', self.fetch_tum_buildings),
            ('Canopy (ETH)', self.fetch_eth_canopy),
            ('Landcover (ESA)', self.fetch_esa_worldcover),
            ('Population (Meta)', self.fetch_meta_population),
            ('Albedo (S2)', self.fetch_s2_albedo)
        ]
        
        total = len(services)
        for i, (name, method) in enumerate(services):
            if progress_callback:
                progress_callback(int(i / total * 100), f"Starting: {name}...")
            
            try:
                method(extent_wgs84)
            except Exception as e:
                err_msg = str(e)
                self.log(f"Failed to download {name}: {err_msg}", Qgis.Critical)
                if progress_callback:
                    progress_callback(int((i + 1) / total * 100), f"❌ Failed: {name} ({err_msg[:50]}...)")
                
        if progress_callback:
            progress_callback(100, f"✅ Download process finished. Files are in: {self.data_dir}")

    def fetch_tinitaly(self, extent_wgs84: QgsRectangle):
        """
        Fetches Tinitaly DTM data via INGV WCS.
        """
        self.log("Accessing Tinitaly DTM via INGV WCS...")
        
        # Calculate width/height for ~10m resolution
        width = int(extent_wgs84.width() * 111320 / 10)
        height = int(extent_wgs84.height() * 111320 / 10)
        width = max(10, min(width, 8000))  # Max limit for WCS request
        height = max(10, min(height, 8000))
        
        # WCS URL for Tinitaly - Version 1.0.0
        wcs_url = (
            "https://tinitaly.pi.ingv.it/services/wcs?"
            "SERVICE=WCS&VERSION=1.0.0&REQUEST=GetCoverage&"
            "COVERAGE=TINItaly_DEM&FORMAT=GeoTIFF&"
            f"BBOX={extent_wgs84.xMinimum()},{extent_wgs84.yMinimum()},"
            f"{extent_wgs84.xMaximum()},{extent_wgs84.yMaximum()}&"
            "CRS=EPSG:4326&"
            f"WIDTH={width}&HEIGHT={height}"
        )
        
        output_path = self.paths['dtm']
        try:
            import requests
            import urllib3
            # Disable insecure request warnings for INGV
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.get(wcs_url, stream=True, verify=False, timeout=120)
            response.raise_for_status()
            
            # Check if it's actually a TIFF and not an XML error
            content_type = response.headers.get('Content-Type', '')
            if 'xml' in content_type or 'text' in content_type:
                # Read start of content to see if it's an error
                error_msg = response.content[:500].decode('utf-8', errors='ignore')
                raise Exception(f"WCS Server returned error: {error_msg}")

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                self.log(f"Tinitaly DTM saved successfully: {os.path.basename(output_path)}")
            else:
                raise Exception("Downloaded DTM file is too small or missing.")
        except Exception as e:
            self.log(f"Error in Tinitaly fetch: {str(e)}", Qgis.Critical)
            raise e

    def fetch_esa_worldcover(self, extent_wgs84: QgsRectangle):
        """Fetches ESA WorldCover via Microsoft Planetary Computer STAC."""
        self.log("Accessing ESA WorldCover via Planetary Computer...")
        
        import requests
        stac_api = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
        bbox = [extent_wgs84.xMinimum(), extent_wgs84.yMinimum(), 
                extent_wgs84.xMaximum(), extent_wgs84.yMaximum()]
        
        payload = {
            "collections": ["esa-worldcover"],
            "bbox": bbox,
            "limit": 1
        }
        
        try:
            response = requests.post(stac_api, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data['features']:
                self.log("No ESA WorldCover features found for this AOI.", Qgis.Warning)
                return
            
            assets = data['features'][0]['assets']
            asset_key = 'map' if 'map' in assets else list(assets.keys())[0]
            cog_url = assets[asset_key]['href']
            
            # Since Planetary Computer uses SAS tokens, we might need to sign the URL
            # but usually for public-ish datasets it works directly or via vsicurl
            self.log(f"Found ESA WorldCover asset: {os.path.basename(cog_url)}")
            
            from qgis import processing
            output_path = self.paths['landcover']
            
            # Format extent for GDAL: [xmin, xmax, ymin, ymax]
            extent_str = f"{extent_wgs84.xMinimum()},{extent_wgs84.xMaximum()},{extent_wgs84.yMinimum()},{extent_wgs84.yMaximum()} [EPSG:4326]"
            
            processing.run("gdal:warp", {
                'INPUT': f"/vsicurl/{cog_url}",
                'OUTPUT': output_path,
                'TARGET_EXTENT': extent_str,
                'TARGET_EXTENT_CRS': 'EPSG:4326',
                'RESAMPLING': 0, # Nearest Neighbor for categorical landcover
                'OPTIONS': 'COMPRESS=DEFLATE'
            })
            
            if os.path.exists(output_path):
                self.log(f"ESA WorldCover clipped: {os.path.basename(output_path)}")
            else:
                raise Exception("Failed to create clipped ESA WorldCover file.")
            
        except Exception as e:
            self.log(f"Error in ESA WorldCover fetch: {str(e)}", Qgis.Critical)
            raise e

    def fetch_tum_buildings(self, extent_wgs84: QgsRectangle):
        """Fetches TUM Building Height data."""
        self.log("Fetching TUM Building Heights (GlobalBuildingAtlas)...")
        # Reference URL: https://mediatum.ub.tum.de/1782307
        # This dataset is split into tiles. For a generic approach, we'd need a tile index.
        # Placeholder for tile-based fetching logic.
        self.log("Note: TUM Buildings currently requires manual download or a specific tile index.", Qgis.Info)
        pass

    def fetch_eth_canopy(self, extent_wgs84: QgsRectangle):
        """Fetches ETH Global Canopy Height via direct COG access if available."""
        self.log("Fetching ETH Global Canopy Height (10m)...")
        # ETH Canopy is often hosted as COGs. 
        # Known mirror/public access point (example URL format)
        cog_url = "https://data.source.coop/fiboa/eth-canopy-height/canopy_height_2020_italy.tif" 
        
        output_path = self.paths['canopy']
        try:
            from qgis import processing
            extent_str = f"{extent_wgs84.xMinimum()},{extent_wgs84.xMaximum()},{extent_wgs84.yMinimum()},{extent_wgs84.yMaximum()} [EPSG:4326]"
            
            processing.run("gdal:cliprasterbyextent", {
                'INPUT': f"/vsicurl/{cog_url}",
                'PROJWIN': extent_str,
                'OUTPUT': output_path
            })
            if os.path.exists(output_path):
                self.log(f"ETH Canopy Height saved to {output_path}")
        except Exception as e:
            self.log(f"Error in ETH Canopy fetch: {str(e)}", Qgis.Warning)

    def fetch_meta_population(self, extent_wgs84: QgsRectangle):
        """Fetches Meta (Facebook) HRSL Population data."""
        self.log("Fetching Meta Population data (ITA 2020)...")
        # Direct link for Italy general population 2020 on AWS
        aws_url = "https://dataforgood-datasets.s3.amazonaws.com/hrsl/italy/ita_general_2020.tif"
        
        output_path = self.paths['population']
        try:
            from qgis import processing
            extent_str = f"{extent_wgs84.xMinimum()},{extent_wgs84.xMaximum()},{extent_wgs84.yMinimum()},{extent_wgs84.yMaximum()} [EPSG:4326]"
            
            processing.run("gdal:cliprasterbyextent", {
                'INPUT': f"/vsicurl/{aws_url}",
                'PROJWIN': extent_str,
                'OUTPUT': output_path
            })
            if os.path.exists(output_path):
                self.log(f"Meta Population saved to {output_path}")
        except Exception as e:
            self.log(f"Error in Meta Population fetch: {str(e)}", Qgis.Warning)

    def fetch_s2_albedo(self, extent_wgs84: QgsRectangle):
        """Fetches Sentinel-2 based Albedo/Reflectance."""
        self.log("Fetching Sentinel-2 Surface Reflectance (STAC)...")
        # Using Microsoft Planetary Computer for S2-L2A
        import requests
        stac_api = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
        bbox = [extent_wgs84.xMinimum(), extent_wgs84.yMinimum(), 
                extent_wgs84.xMaximum(), extent_wgs84.yMaximum()]
        
        payload = {
            "collections": ["sentinel-2-l2a"],
            "bbox": bbox,
            "datetime": "2023-06-01/2023-08-31", # Summer period for clearer albedo
            "query": {"eo:cloud_cover": {"lt": 10}},
            "limit": 1
        }
        
        try:
            response = requests.post(stac_api, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data['features']:
                self.log("No clear Sentinel-2 scenes found for summer 2023.", Qgis.Warning)
                return
                
            self.log(f"Found S2 Scene: {data['features'][0]['id']}")
            # In a real implementation, we'd download B02, B03, B04, B08 
            # and compute Albedo. For now, we log the success and scene ID.
        except Exception as e:
            self.log(f"Error in S2 fetch: {str(e)}", Qgis.Warning)

    def _download_file(self, url: str, output_path: str, progress_callback=None):
        """Helper to download a file with progress reporting."""
        import requests
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Note: We'd need to map this to the global progress
                    pass
