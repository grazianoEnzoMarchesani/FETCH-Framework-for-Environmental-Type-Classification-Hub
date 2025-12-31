# -*- coding: utf-8 -*-
"""
WUDAPT LCZ Global Map Downloader & Sampler

Downloads WUDAPT Global LCZ tiles and extracts LCZ classes at specific coordinates.
"""

import os
import math
import requests
import io
import numpy as np
from PIL import Image
from qgis.core import (QgsProject, QgsCoordinateReferenceSystem, 
                       QgsCoordinateTransform, QgsRectangle, QgsPointXY)

class WudaptDownloader:
    """Downloads and samples WUDAPT Global LCZ tiles."""
    
    TMS_URL = "https://lcz-generator.rub.de/tms/global-map-tiles/latest/{z}/{x}/{y}.png"
    
    # LCZ Color Mapping (RGB -> LCZ Class)
    COLOR_MAP = {
        (140, 0, 0): '1', (207, 2, 1): '2', (254, 1, 0): '3',
        (189, 77, 1): '4', (255, 102, 0): '5', (255, 153, 87): '6',
        (249, 239, 0): '7', (188, 188, 188): '8', (254, 204, 169): '9',
        (85, 85, 85): '10', (0, 106, 0): 'A', (0, 170, 0): 'B',
        (100, 133, 37): 'C', (185, 219, 121): 'D', (0, 0, 0): 'E',
        (251, 247, 174): 'F', (106, 106, 255): 'G',
    }

    def __init__(self, data_manager=None):
        self.dm = data_manager
        self.tile_cache = {} # {(z,x,y): Image}

    def _get_tile_coords(self, lat, lon, zoom):
        """Convert lat/lon to standard XYZ tile and pixel coordinates."""
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        xtile = ((lon + 180.0) / 360.0 * n)
        ytile = ((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
        
        # Absolute tile index (Standard XYZ / OSM)
        tx = int(xtile)
        ty = int(ytile)
        
        # Pixel index within tile (256x256)
        px = int((xtile - tx) * 256)
        py = int((ytile - ty) * 256)
        
        return tx, ty, px, py

    def get_lcz_at(self, lat, lon, zoom=12):
        """Fetches tile and returns LCZ class at specific lat/lon."""
        tx, ty, px, py = self._get_tile_coords(lat, lon, zoom)
        
        tile_key = (zoom, tx, ty)
        if tile_key not in self.tile_cache:
            url = self.TMS_URL.format(z=zoom, x=tx, y=ty)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
            }
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    self.tile_cache[tile_key] = Image.open(io.BytesIO(resp.content)).convert('RGB')
                else:
                    return None
            except:
                return None
        
        img = self.tile_cache[tile_key]
        rgb = img.getpixel((px, py))
        
        # Match closest color
        best_match = None
        min_dist = 999999
        for c, lcz in self.COLOR_MAP.items():
            dist = sum((a - b) ** 2 for a, b in zip(rgb, c))
            if dist < min_dist:
                min_dist = dist
                best_match = lcz
        
        return best_match if min_dist < 500 else None # Tolerance for compression artifacts
