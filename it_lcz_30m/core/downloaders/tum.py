# -*- coding: utf-8 -*-

import os
from qgis.core import Qgis
from .base import BaseDownloader

class TUMDownloader(BaseDownloader):
    def __init__(self, data_manager):
        super().__init__(data_manager)

    def download_data(self, category="LoD1", aoi_geometry=None):
        self.log(f"Avvio acquisizione TUM {category}. AOI: {'Disponibile' if aoi_geometry else 'Mancante'}")
        download_dir = self.get_download_dir(f"tum_{category.lower()}")
        if not download_dir: return []

        if category == "LoD1" and aoi_geometry:
            return self._download_lod1_wfs(download_dir, aoi_geometry)

        self.log(f"Categoria {category} non supportata o AOI mancante.", Qgis.Warning)
        return []

    def _download_lod1_wfs(self, download_dir, aoi_geometry):
        extent = aoi_geometry.boundingBox()
        bbox_str = f"{extent.xMinimum()},{extent.yMinimum()},{extent.xMaximum()},{extent.yMaximum()}"
        
        wfs_url = (
            "https://tubvsig-so2sat-vm1.srv.mwn.de/geoserver/ows?"
            "service=WFS&version=1.1.0&request=GetFeature&"
            "typeName=global3D:lod1_global&outputFormat=application/json&"
            f"srsName=EPSG:4326&bbox={bbox_str},EPSG:4326"
        )
        
        save_path = os.path.join(download_dir, "tum_lod1_aoi.json")

        if os.path.exists(save_path):
            self.log(f"LoD1 AOI già presente (JSON). Salto.")
            return [("tum_lod1_aoi.json", True, "Gia' presente")]

        self.log(f"Download WFS TUM LoD1 per AOI...")
        success, msg = self._download_file(wfs_url, save_path)
        if success:
            return [("tum_lod1_aoi.json", True, "Download completato")]
        else:
            self.log(f"Download WFS fallito: {msg}", Qgis.Critical)
            return [("tum_lod1_aoi.json", False, msg)]
