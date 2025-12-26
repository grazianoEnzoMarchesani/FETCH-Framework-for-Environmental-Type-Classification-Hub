# -*- coding: utf-8 -*-

import os
import requests
from ..utils import download_file_generic

class IndustryDownloader:
    def __init__(self, data_manager):
        self.dm = data_manager
        # Updated ArcGIS REST endpoint for IED (Industrial Emissions Directive) Sites
        self.rest_url = "https://air.discomap.eea.europa.eu/arcgis/rest/services/Air/IED_SiteMap/MapServer/0/query"

    def fetch_eprtr(self, extent, crs_auth_id, log_callback=None):
        """Fetches industrial points (IED/E-PRTR) via ArcGIS REST API."""
        import json
        from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform
        
        def log(msg):
            if log_callback: log_callback(msg)
            
        output_dir = self.dm.get_download_dir("eprtr_industry")
        if not output_dir: return False, "Project not saved"

        output_path = os.path.join(output_dir, "industrial_sites.json")
        if os.path.exists(output_path):
            log("Dati industria già presenti, salto download.")
            return True, output_path

        log("Interrogazione ArcGIS REST per stabilimenti industriali (IED/E-PRTR)...")
        
        # 1. Transform extent to EPSG:4326 for ArcGIS REST Query
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        w84 = transform.transformBoundingBox(extent)
        
        # ArcGIS REST uses envelope in JSON format or xmin,ymin,xmax,ymax string
        # format: xmin,ymin,xmax,ymax
        bbox_str = f"{w84.xMinimum()},{w84.yMinimum()},{w84.xMaximum()},{w84.yMaximum()}"
        
        params = {
            'where': '1=1',
            'geometry': bbox_str,
            'geometryType': 'esriGeometryEnvelope',
            'inSR': '4326',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': '*',
            'returnGeometry': 'true',
            'f': 'geojson'
        }

        try:
            log(f"Interrogazione REST EEA su area: {bbox_str}")
            resp = requests.get(self.rest_url, params=params, timeout=20)
            resp.raise_for_status()
            
            data = resp.json()
            features = data.get('features', [])
            log(f"Ricevuti {len(features)} stabilimenti industriali nell'area.")
            
            if features:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                log(f"Salvataggio punti industriali completato: {output_path}")
                return True, output_path
            else:
                log("Nessuno stabilimento industriale trovato nell'area specifica.")
                # Create empty geojson to avoid error
                empty = {"type": "FeatureCollection", "features": []}
                with open(output_path, 'w') as f: json.dump(empty, f)
                return True, output_path
                
        except Exception as e:
            log(f"Errore REST Industry: {str(e)}")
            return False, str(e)
