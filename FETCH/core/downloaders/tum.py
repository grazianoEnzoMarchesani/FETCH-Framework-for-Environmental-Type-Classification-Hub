# -*- coding: utf-8 -*-

import os
import math
from qgis.core import Qgis, QgsVectorLayer, QgsFeature
import processing
from .base import BaseDownloader

class TUMDownloader(BaseDownloader):
    def __init__(self, data_manager):
        super().__init__(data_manager)
        self.base_data_url = "https://data.source.coop/tge-labs/globalbuildingatlas-lod1/"

    def download_data(self, category="LoD1", aoi_geometry=None):
        self.log(f"Avvio acquisizione TUM {category}. AOI: {'Disponibile' if aoi_geometry else 'Mancante'}")
        download_dir = self.get_download_dir(f"tum_{category.lower()}")
        if not download_dir: return[]

        if category == "LoD1" and aoi_geometry:
            return self._download_lod1_static(download_dir, aoi_geometry)

        self.log(f"Categoria {category} non supportata o AOI mancante.", Qgis.Warning)
        return[]

    def _get_static_tile_urls(self, aoi_geometry):
        """
        Calcola gli URL dei file Parquet MATEMATICAMENTE usando la griglia 5x5 gradi
        del Global Building Atlas, senza bisogno di scaricare alcun file indice.
        """
        extent = aoi_geometry.boundingBox()
        
        # SAFETY CHECK: If coordinates are clearly NOT geographic (decimal degrees), 
        # force a transformation to WGS84. This handles cases where the incoming geometry
        # is still in a local metric CRS (e.g. Monte Mario 3003/3004 or UTM).
        if extent.xMinimum() > 180 or extent.xMinimum() < -180:
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
            self.log("AOI in metri rilevata: conversione interna in WGS84 per la griglia TUM Building Atlas.")
            
            # Use the project CRS as the source
            source_crs = QgsProject.instance().crs()
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            # Using transformContext is required for reliable results in QGIS 3 background threads
            transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance().transformContext())
            
            # transform() modifies the geometry in place
            res = aoi_geometry.transform(transform)
            if res != 0:
                self.log(f"⚠ Fallimento trasformazione interna TUM (Codice: {res}).", Qgis.Warning)
                
            extent = aoi_geometry.boundingBox()

        # FINAL VALIDATION: Avoid infinite loops if coordinates are still metric
        if extent.xMinimum() > 180 or extent.xMinimum() < -180:
            self.log("✗ ERRORE CRITICO: AOI non convertibile in gradi geografici. Verifica il CRS del progetto.", Qgis.Critical)
            return []

        lon_min_aoi = extent.xMinimum()
        lat_min_aoi = extent.yMinimum()
        lon_max_aoi = extent.xMaximum()
        lat_max_aoi = extent.yMaximum()

        # Arrotonda ai multipli di 5 per trovare il "quadrato" di partenza della griglia
        start_lon = int(math.floor(lon_min_aoi / 5.0) * 5)
        end_lon = int(math.floor(lon_max_aoi / 5.0) * 5)
        start_lat = int(math.floor(lat_min_aoi / 5.0) * 5)
        end_lat = int(math.floor(lat_max_aoi / 5.0) * 5)
        
        # SAFETY CAP: Max 40 tiles allowed to prevent infinite download loops on CRS errors
        num_lon_tiles = (end_lon - start_lon) // 5 + 1
        num_lat_tiles = (end_lat - start_lat) // 5 + 1
        total_tiles = num_lon_tiles * num_lat_tiles
        
        if total_tiles > 40:
            self.log(f"✗ Richiesta di troppi tasselli ({total_tiles} > 40). Probabile errore di proiezione. Interruzione di sicurezza.", Qgis.Critical)
            return []

        urls = []
        # Itera su tutti i quadrati 5x5 intersecati
        for lon in range(start_lon, end_lon + 5, 5):
            for lat in range(start_lat, end_lat + 5, 5):
                tile_lon_min = lon
                tile_lon_max = lon + 5
                tile_lat_min = lat
                tile_lat_max = lat + 5

                # Formattazione Longitudine (es. e010, w005)
                ew_min = 'e' if tile_lon_min >= 0 else 'w'
                lon_min_str = f"{abs(tile_lon_min):03d}"
                ew_max = 'e' if tile_lon_max >= 0 else 'w'
                lon_max_str = f"{abs(tile_lon_max):03d}"

                # Formattazione Latitudine (es. n50, s05)
                ns_min = 'n' if tile_lat_min >= 0 else 's'
                lat_min_str = f"{abs(tile_lat_min):02d}"
                ns_max = 'n' if tile_lat_max >= 0 else 's'
                lat_max_str = f"{abs(tile_lat_max):02d}"

                # Nomenclatura esatta richiesta dal server: {e/w}{lon_min}_{n/s}{lat_max}_{e/w}{lon_max}_{n/s}{lat_min}.parquet
                filename = f"{ew_min}{lon_min_str}_{ns_max}{lat_max_str}_{ew_max}{lon_max_str}_{ns_min}{lat_min_str}.parquet"
                urls.append(f"{self.base_data_url}{filename}")

        return urls

    def _download_lod1_static(self, download_dir, aoi_geometry):
        urls = self._get_static_tile_urls(aoi_geometry)
        
        results = []
        downloaded_paths =[]
        final_output = os.path.join(download_dir, "tum_lod1_aoi.gpkg")

        if os.path.exists(final_output):
            self.log(f"LoD1 AOI già presente in formato GPKG. Salto.")
            return[("tum_lod1_aoi.gpkg", True, "Già presente")]

        # 1. DOWNLOAD
        for url in urls:
            filename = os.path.basename(url)
            local_path = os.path.join(download_dir, filename)
            
            # Controllo esistenza e validità (> 2KB per scartare gli XML di errore)
            if os.path.exists(local_path) and os.path.getsize(local_path) > 2000:
                self.log(f"File Parquet {filename} già presente localmente.")
                downloaded_paths.append(local_path)
                continue

            self.log(f"Download tassello {filename}...")
            success, msg = self._download_file(url, local_path)
            
            if success:
                # AWS restituisce un file HTML/XML se l'area è in mare o senza edifici (404 Not Found)
                # I veri Parquet pesano MB, gli errori pesano ~300 byte.
                if os.path.getsize(local_path) < 2000:
                    self.log(f"Il tassello {filename} non esiste sul server (area vuota/oceano). Salto.")
                    os.remove(local_path)
                else:
                    downloaded_paths.append(local_path)
            else:
                self.log(f"Errore download {filename}: {msg}", Qgis.Warning)

        if not downloaded_paths:
            self.log("Nessun dato valido scaricato. L'area potrebbe essere senza copertura.", Qgis.Warning)
            return[("tum_lod1_aoi.gpkg", False, "Nessun tassello disponibile per l'AOI specificata")]

        # 2. CREAZIONE MASCHERA DI RITAGLIO
        self.log(f"Ritaglio di {len(downloaded_paths)} file Parquet sull'AOI...")
        aoi_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "aoi_mask", "memory")
        pr = aoi_layer.dataProvider()
        fet = QgsFeature()
        fet.setGeometry(aoi_geometry)
        pr.addFeatures([fet])
        aoi_layer.updateExtents()

        # 3. CLIP SPAZIALE
        clipped_layers =[]
        for path in downloaded_paths:
            p_layer = QgsVectorLayer(path, os.path.basename(path), "ogr")
            if not p_layer.isValid():
                self.log(f"Impossibile leggere il file Parquet (richiede QGIS recente con GDAL Arrow): {path}", Qgis.Warning)
                continue
            
            clip_params = {
                'INPUT': p_layer,
                'OVERLAY': aoi_layer,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            try:
                res = processing.run("native:clip", clip_params)
                out_layer_path = res['OUTPUT']
                
                # Verifichiamo che il ritaglio non sia vuoto (nessun edificio intersecato)
                if isinstance(out_layer_path, QgsVectorLayer):
                    test_layer = out_layer_path
                else:
                    test_layer = QgsVectorLayer(out_layer_path, "test", "ogr")
                    
                if test_layer.isValid() and test_layer.featureCount() > 0:
                    clipped_layers.append(out_layer_path)
                    
            except Exception as e:
                self.log(f"Errore durante il ritaglio di {path}: {str(e)}", Qgis.Warning)

        if not clipped_layers:
            self.log("L'AOI non interseca nessun edificio all'interno dei tasselli.", Qgis.Warning)
            return[("tum_lod1_aoi.gpkg", False, "Nessun edificio ritagliato all'interno dell'AOI")]

        # 4. UNIONE E SALVATAGGIO IN GEOPACKAGE
        try:
            self.log("Unione dei tasselli e salvataggio nel GeoPackage finale...")
            if len(clipped_layers) > 1:
                merge_params = {
                    'LAYERS': clipped_layers,
                    'OUTPUT': final_output
                }
                processing.run("native:mergevectorlayers", merge_params)
            else:
                # Se c'è un solo tassello, usiamo savefeatures
                save_params = {
                    'INPUT': clipped_layers[0],
                    'OUTPUT': final_output
                }
                processing.run("native:savefeatures", save_params)
                
            self.log(f"TUM LoD1 salvato con successo in: {final_output}")
            
            # Pulizia opzionale: se vuoi cancellare i Parquet originali de-commenta queste righe
            # for p in downloaded_paths:
            #     os.remove(p)
                
            return[("tum_lod1_aoi.gpkg", True, "Completato")]
            
        except Exception as e:
            self.log(f"Errore durante il salvataggio: {str(e)}", Qgis.Critical)
            return[("tum_lod1_aoi.gpkg", False, str(e))]