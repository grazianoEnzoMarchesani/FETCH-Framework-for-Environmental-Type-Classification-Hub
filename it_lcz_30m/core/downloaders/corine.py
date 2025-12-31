# -*- coding: utf-8 -*-
"""
CORINE Land Cover 2018 Downloader

Downloads CORINE Land Cover 2018 vector data via EEA ArcGIS REST API.
Used for LCZ v3.0 industrial areas correction (class 121).

References:
- REST API: https://image.discomap.eea.europa.eu/arcgis/rest/services/Corine/CLC2018_WM/MapServer
- Documentation: https://land.copernicus.eu/pan-european/corine-land-cover
"""

import os
import json
import requests
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform


class CorineDownloader:
    """Downloads CORINE Land Cover 2018 data via EEA REST API."""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        # CORINE 2018 Vector Layer (Layer 0 in the MapServer)
        self.rest_url = "https://image.discomap.eea.europa.eu/arcgis/rest/services/Corine/CLC2018_WM/MapServer/0/query"
    
    def fetch_corine(self, extent, crs_auth_id, log_callback=None):
        """
        Fetches CORINE Land Cover 2018 vector polygons via ArcGIS REST API.
        
        Args:
            extent: QgsRectangle with the area of interest
            crs_auth_id: CRS authority ID (e.g., "EPSG:32632")
            log_callback: Optional function for logging messages
            
        Returns:
            Tuple (success: bool, path_or_error: str)
        """
        def log(msg):
            if log_callback: 
                log_callback(msg)
        
        # Setup output directory
        output_dir = self.dm.get_download_dir("corine_clc2018")
        if not output_dir: 
            return False, "Project not saved"
        
        output_path = os.path.join(output_dir, "corine_clc2018.json")
        
        # Skip if already downloaded
        if os.path.exists(output_path):
            log("Dati CORINE già presenti, salto download.")
            return True, output_path
        
        log("📥 Download CORINE Land Cover 2018 da EEA...")
        
        # 1. Transform extent to EPSG:4326 for ArcGIS REST Query
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        w84 = transform.transformBoundingBox(extent)
        
        # ArcGIS REST format: xmin,ymin,xmax,ymax
        bbox_str = f"{w84.xMinimum()},{w84.yMinimum()},{w84.xMaximum()},{w84.yMaximum()}"
        
        # 2. Query parameters
        # Only request essential fields to reduce payload
        params = {
            'where': '1=1',
            'geometry': bbox_str,
            'geometryType': 'esriGeometryEnvelope',
            'inSR': '4326',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': 'Code_18,ID,Area_Ha',  # Essential fields only (Code_18 is the main one)
            'returnGeometry': 'true',
            'outSR': '4326',  # Return in WGS84
            'f': 'geojson'
        }
        
        try:
            log(f"Interrogazione REST EEA CORINE su area: {bbox_str}")
            
            # Make request with longer timeout (CORINE polygons can be large)
            resp = requests.get(self.rest_url, params=params, timeout=120)
            resp.raise_for_status()
            
            data = resp.json()
            
            # Check for errors in response
            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown error')
                log(f"Errore API CORINE: {error_msg}")
                return False, error_msg
            
            features = data.get('features', [])
            log(f"Ricevuti {len(features)} poligoni CORINE nell'area.")
            
            # Count industrial areas (class 121)
            industrial_count = sum(
                1 for f in features 
                if str(f.get('properties', {}).get('Code_18', '')).startswith('121')
            )
            if industrial_count > 0:
                log(f"  └ Di cui {industrial_count} aree industriali/commerciali (121)")
            
            # Save result
            if features:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                log(f"✓ Salvataggio CORINE completato: {output_path}")
                return True, output_path
            else:
                log("Nessun dato CORINE trovato nell'area (potrebbe essere fuori Europa).")
                # Create empty geojson to avoid repeated downloads
                empty = {"type": "FeatureCollection", "features": []}
                with open(output_path, 'w') as f: 
                    json.dump(empty, f)
                return True, output_path
                
        except requests.exceptions.Timeout:
            log("Timeout durante download CORINE (area troppo grande?)")
            return False, "Timeout"
        except requests.exceptions.RequestException as e:
            log(f"Errore rete CORINE: {str(e)}")
            return False, str(e)
        except Exception as e:
            log(f"Errore CORINE: {str(e)}")
            return False, str(e)
    
    def get_corine_path(self):
        """Returns the path to downloaded CORINE data if it exists."""
        output_dir = self.dm.get_download_dir("corine_clc2018")
        if not output_dir:
            return None
        path = os.path.join(output_dir, "corine_clc2018.json")
        return path if os.path.exists(path) else None
