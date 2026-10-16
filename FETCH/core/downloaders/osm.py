# -*- coding: utf-8 -*-

import json
import math
import os
import time
import requests
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle

class OSMDownloader:
    # Public Overpass instances are often slow or down (502/504/timeouts), so several
    # mirrors are tried in turn. Order = preference; a failing one just falls through.
    ENDPOINTS = [
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]
    HIGHWAYS = "motorway|trunk|primary|secondary|tertiary|residential"
    TILE_DEG = 0.25         # large areas are split in tiles of at most this size (degrees)
    ROUNDS = 3              # full passes over all mirrors before giving up
    BACKOFF = (5, 15)       # seconds to wait between rounds
    SERVER_TIMEOUT = 120    # Overpass [timeout:] (query runtime on the server)
    REQUEST_TIMEOUT = (10, 150)  # (connect, read) seconds for requests

    def __init__(self, data_manager):
        self.dm = data_manager
        self.overpass_url = self.ENDPOINTS[0]  # kept for backward compatibility

    def fetch_roads(self, extent, crs_auth_id, log_callback=None):
        """Fetches road segments from OSM using the Overpass API (mirrors, retries, tiling)."""
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
        
        # (south, west, north, east)
        bbox = (
            w84_extent.yMinimum(), w84_extent.xMinimum(),
            w84_extent.yMaximum(), w84_extent.xMaximum()
        )

        tiles = self._split_bbox(bbox)
        log(f"Esecuzione Overpass su area {tuple(round(v, 4) for v in bbox)} in {len(tiles)} riquadri...")

        # 2. Download tile by tile; ways are de-duplicated by id across tiles
        ways = {}
        for i, tile in enumerate(tiles, 1):
            try:
                data = self._query_tile(tile, log, f"riquadro {i}/{len(tiles)}")
            except Exception as e:
                log(f"ERRORE OSM: {e}")
                return False, str(e)
            for el in data.get('elements', []):
                if el.get('type') == 'way' and el.get('geometry'):
                    ways[el['id']] = el
            log(f"Riquadro {i}/{len(tiles)} ok ({len(ways)} strade finora).")

        # 3. Save to GeoJSON (temp file + rename: never leave a partial result)
        try:
            log("Conversione OSM JSON -> GeoJSON...")
            geojson = self._ways_to_geojson(ways.values())
            tmp_path = output_path + ".part"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, ensure_ascii=False)
            os.replace(tmp_path, output_path)
            log(f"Salvataggio completato: {output_path} ({len(ways)} strade)")
            return True, output_path
        except Exception as e:
            log(f"ERRORE OSM: {str(e)}")
            return False, str(e)

    def _split_bbox(self, bbox):
        """Split (s, w, n, e) into tiles no larger than TILE_DEG per side."""
        south, west, north, east = bbox
        rows = max(1, math.ceil((north - south) / self.TILE_DEG))
        cols = max(1, math.ceil((east - west) / self.TILE_DEG))
        dlat, dlon = (north - south) / rows, (east - west) / cols
        return [
            (south + r * dlat, west + c * dlon, south + (r + 1) * dlat, west + (c + 1) * dlon)
            for r in range(rows) for c in range(cols)
        ]

    def _query_tile(self, tile, log, label):
        """Run the roads query for one tile, trying every mirror, with retries and backoff."""
        query = (
            f"[out:json][timeout:{self.SERVER_TIMEOUT}];"
            f'way["highway"~"{self.HIGHWAYS}"]({tile[0]},{tile[1]},{tile[2]},{tile[3]});'
            "out geom;"
        )
        headers = {'User-Agent': 'FETCH-Plugin/1.0 (QGIS)', 'Accept': 'application/json'}
        errors = []
        for round_no in range(self.ROUNDS):
            for url in self.ENDPOINTS:
                host = url.split("/")[2]
                try:
                    r = requests.post(url, data={'data': query}, headers=headers, timeout=self.REQUEST_TIMEOUT)
                    r.raise_for_status()
                    data = r.json()
                    # Overpass answers 200 with a "remark" when the query ran out of time/memory
                    if 'elements' not in data or ('runtime error' in str(data.get('remark', '')).lower() and not data['elements']):
                        raise RuntimeError(data.get('remark') or "risposta senza elementi")
                    return data
                except Exception as e:
                    msg = f"{host}: {type(e).__name__}: {e}"[:200]
                    errors.append(msg)
                    log(f"OSM {label}: {msg} -> provo il prossimo server")
            if round_no < len(self.BACKOFF):
                wait = self.BACKOFF[round_no]
                log(f"OSM {label}: tutti i server hanno fallito, nuovo tentativo tra {wait}s...")
                time.sleep(wait)
        raise RuntimeError(
            "Overpass non raggiungibile su tutti i server dopo vari tentativi. Ultimi errori: " + " | ".join(errors[-3:])
        )

    def _ways_to_geojson(self, ways):
        """Overpass `out geom` ways -> GeoJSON LineStrings."""
        features = []
        for el in ways:
            coords = [(pt['lon'], pt['lat']) for pt in el['geometry']]
            if len(coords) < 2: continue
            features.append({
                "type": "Feature",
                "id": el['id'],
                "properties": el.get('tags', {}),
                "geometry": {"type": "LineString", "coordinates": coords}
            })
        return {"type": "FeatureCollection", "features": features}
