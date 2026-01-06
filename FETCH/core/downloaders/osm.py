# -*- coding: utf-8 -*-

import os
import requests
import json
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle

class OSMDownloader:
    def __init__(self, data_manager):
        self.dm = data_manager
        self.overpass_url = "https://overpass-api.de/api/interpreter"

    def fetch_roads(self, extent, crs_auth_id, log_callback=None):
        """Fetches road segments from OSM using Overpass API."""
        def log(msg):
            if log_callback: log_callback(msg)
            
        output_dir = self.dm.get_download_dir("osm_roads")
        if not output_dir: return False, "Project not saved"

        output_path = os.path.join(output_dir, "roads.geojson")
        if os.path.exists(output_path):
            log("Dati OSM già presenti, salto download.")
            return True, f"Dati OSM già presenti: {output_path}"

        # 1. Transform extent to EPSG:4326 for Overpass
        log("Parametrizzazione query Overpass (AOI -> EPSG:4326)...")
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        w84_extent = transform.transformBoundingBox(extent)
        
        bbox = (
            w84_extent.yMinimum(), w84_extent.xMinimum(),
            w84_extent.yMaximum(), w84_extent.xMaximum()
        ) # (south, west, north, east)

        # 2. Build Overpass Query
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"motorway|trunk|primary|secondary|tertiary|residential"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
        );
        out body;
        >;
        out skel qt;
        """
        log(f"Esecuzione Overpass Query su area: {bbox}")

        # 3. Request data
        try:
            response = requests.post(self.overpass_url, data={'data': query}, timeout=30)
            response.raise_for_status()
            osm_data = response.json()
            
            elements = osm_data.get('elements', [])
            log(f"Ricevuti {len(elements)} elementi da OSM.")
            
            # 4. Save to GeoJSON
            log("Conversione OSM JSON -> GeoJSON...")
            geojson = self._osm_to_geojson(osm_data)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, ensure_ascii=False)
            
            log(f"Salvataggio completato: {output_path}")
            return True, output_path
        except Exception as e:
            log(f"ERRORE OSM: {str(e)}")
            return False, str(e)

    def _osm_to_geojson(self, osm_data):
        """Minimalist conversion from Overpass JSON to GeoJSON."""
        nodes = {n['id']: (n['lon'], n['lat']) for n in osm_data['elements'] if n['type'] == 'node'}
        features = []
        
        for el in osm_data['elements']:
            if el['type'] == 'way':
                coords = [nodes[node_id] for node_id in el['nodes'] if node_id in nodes]
                if len(coords) < 2: continue
                
                feature = {
                    "type": "Feature",
                    "id": el['id'],
                    "properties": el.get('tags', {}),
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords
                    }
                }
                features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
