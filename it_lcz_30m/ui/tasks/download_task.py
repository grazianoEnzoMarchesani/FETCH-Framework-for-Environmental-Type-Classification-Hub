# -*- coding: utf-8 -*-
"""
FETCH Download Task

Background task for downloading all required data sources.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (
    QgsTask, QgsMessageLog, Qgis, QgsProject,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry
)
from ...core.exceptions import FetchError, FetchDataError, FetchWarning, FetchCriticalError


class DownloadTask(QgsTask):
    """Task for running all data downloads in the background."""
    
    # Signal to update UI with detailed progress: (step_name, step_num, total_steps, percent)
    progressUpdated = pyqtSignal(str, int, int, int)
    
    # Mapping from checkbox names to human-readable step names
    STEP_NAMES = {
        "Tinitaly (DTM 10m)": "Download DTM Tinitaly",
        "TUM (Edifici H 10m)": "Download Edifici TUM",
        "ETH (Alberi H 10m)": "Download Altezze Alberi ETH",
        "ESA WorldCover (Land Use)": "Download Land Cover ESA",
        "Meta HRSL (Popolazione)": "Download Popolazione Meta HRSL",
        "S2GM (Albedo Sentinel-2)": "Download Albedo Sentinel-2",
        "OSM Roads (Vettoriale)": "Download Strade OSM",
        "Traffic ANAS (Italia)": "Download Traffico ANAS",
        "Copernicus HRL (10m)": "Download Impermeabilità HRL",
        "Industrial Points (E-PRTR)": "Download Industrie E-PRTR",
        "CORINE Land Cover (EEA)": "Download CORINE Land Cover"
    }
    
    def __init__(self, data_manager, selected_checks, extent, crs, cdse_user, cdse_pass, tiles):
        super().__init__("Download Dati FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.selected_checks = selected_checks
        self.extent = extent
        self.crs = crs
        self.cdse_user = cdse_user
        self.cdse_pass = cdse_pass
        self.tiles = tiles
        self.success = False
        self.message = ""
        self.error_count = 0
    
    def emit_progress(self, check_name, step_num, total_steps):
        """Emit progress signal with calculated percentage."""
        step_name = self.STEP_NAMES.get(check_name, check_name)
        percent = int((step_num / total_steps) * 100)
        self.progressUpdated.emit(step_name, step_num, total_steps, percent)

    def run(self):
        def task_log(msg, level=Qgis.Info):
            QgsMessageLog.logMessage(msg, "FETCH", level)

        try:
            total_steps = sum(1 for val in self.selected_checks.values() if val)
            current_step = 0
            
            # 1. Tinitaly
            if self.selected_checks.get("Tinitaly (DTM 10m)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("Tinitaly (DTM 10m)", current_step, total_steps)
                
                for i, tile in enumerate(self.tiles):
                    if self.isCanceled(): return False
                    task_log(f"Download Tinitaly {i+1}/{len(self.tiles)}: {tile}")
                    # Update with sub-progress for tiles
                    sub_percent = int(((current_step - 1) + (i+1)/len(self.tiles)) / total_steps * 100)
                    self.progressUpdated.emit(f"Download DTM Tinitaly (tile {i+1}/{len(self.tiles)})", current_step, total_steps, sub_percent)
                    success, msg = self.data_manager.download_tinitaly_tile(tile)
                    if not success:
                        task_log(f"⚠ Tinitaly {tile}: {msg}", Qgis.Warning)
                        self.error_count += 1
                    self.setProgress(sub_percent)

            # 2. TUM Building Heights
            if self.selected_checks.get("TUM (Edifici H 10m)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("TUM (Edifici H 10m)", current_step, total_steps)
                
                source_crs = QgsCoordinateReferenceSystem(self.crs)
                wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                transform = QgsCoordinateTransform(source_crs, wgs84_crs, QgsProject.instance())
                aoi_geom = QgsGeometry.fromRect(self.extent)
                aoi_geom.transform(transform)

                for category in self.data_manager.tum_categories:
                    if self.isCanceled(): return False
                    task_log(f"Acquisizione TUM {category}...")
                    self.data_manager.download_tum_data(category=category, aoi_geometry=aoi_geom)
                self.setProgress(int(current_step / total_steps * 100))

            # 3. ETH Canopy Height
            if self.selected_checks.get("ETH (Alberi H 10m)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("ETH (Alberi H 10m)", current_step, total_steps)
                task_log("Acquisizione ETH Global Canopy Height...")
                self.data_manager.fetch_eth_canopy(self.extent, self.crs)
                self.setProgress(int(current_step / total_steps * 100))

            # 4. ESA WorldCover
            if self.selected_checks.get("ESA WorldCover (Land Use)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("ESA WorldCover (Land Use)", current_step, total_steps)
                task_log("Acquisizione ESA WorldCover...")
                self.data_manager.fetch_esa_worldcover(self.extent, self.crs)
                self.setProgress(int(current_step / total_steps * 100))

            # 5. Meta HRSL Population
            if self.selected_checks.get("Meta HRSL (Popolazione)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("Meta HRSL (Popolazione)", current_step, total_steps)
                task_log("Acquisizione Meta HRSL Population...")
                self.data_manager.fetch_meta_hrsl(self.extent, self.crs)
                self.setProgress(int(current_step / total_steps * 100))

            # 6. Sentinel-2 Albedo
            if self.selected_checks.get("S2GM (Albedo Sentinel-2)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("S2GM (Albedo Sentinel-2)", current_step, total_steps)
                
                if not self.cdse_user or not self.cdse_pass:
                    task_log("⚠ Credenziali CDSE mancanti per Albedo.", Qgis.Warning)
                    self.error_count += 1
                else:
                    task_log("Acquisizione Sentinel-2 Albedo (richiede tempo)...")
                    success, msg = self.data_manager.fetch_sentinel2_albedo(
                        self.extent, self.crs, self.cdse_user, self.cdse_pass
                    )
                    if not success:
                        task_log(f"⚠ Albedo: {msg}", Qgis.Warning)
                        self.error_count += 1
                self.setProgress(int(current_step / total_steps * 100))

            # 7. OSM Roads
            if self.selected_checks.get("OSM Roads (Vettoriale)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("OSM Roads (Vettoriale)", current_step, total_steps)
                task_log("Acquisizione Reti Stradali OSM...")
                self.data_manager.fetch_osm_roads(self.extent, self.crs, log_callback=task_log)
                self.setProgress(int(current_step / total_steps * 100))

            # 8. Traffic ANAS
            if self.selected_checks.get("Traffic ANAS (Italia)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("Traffic ANAS (Italia)", current_step, total_steps)
                task_log("Acquisizione Dati Traffico ANAS...")
                self.data_manager.fetch_anas_traffic(self.extent, self.crs, log_callback=task_log)
                self.setProgress(int(current_step / total_steps * 100))

            # 9. Copernicus HRL
            if self.selected_checks.get("Copernicus HRL (10m)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("Copernicus HRL (10m)", current_step, total_steps)
                task_log("Acquisizione Copernicus HRL Imperviousness...")
                self.data_manager.fetch_copernicus_hrl(self.extent, self.crs, log_callback=task_log)
                self.setProgress(int(current_step / total_steps * 100))

            # 10. E-PRTR Industrial Points
            if self.selected_checks.get("Industrial Points (E-PRTR)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("Industrial Points (E-PRTR)", current_step, total_steps)
                task_log("Acquisizione Punti Industriali E-PRTR...")
                self.data_manager.fetch_eprtr_industrial(self.extent, self.crs, log_callback=task_log)
                self.setProgress(int(current_step / total_steps * 100))

            # 11. CORINE Land Cover (EEA)
            if self.selected_checks.get("CORINE Land Cover (EEA)"):
                current_step += 1
                if self.isCanceled(): return False
                self.emit_progress("CORINE Land Cover (EEA)", current_step, total_steps)
                task_log("Acquisizione CORINE Land Cover (EEA)...")
                self.data_manager.fetch_corine_landcover(self.extent, self.crs, log_callback=task_log)
                self.setProgress(int(current_step / total_steps * 100))

            self.success = True
            return True
        except FetchWarning as w:
            task_log(f"⚠ Avviso: {w.user_message}", Qgis.Warning)
            self.error_count += 1
            # Non-blocking, continue
            return True
        except FetchCriticalError as e:
            self.message = e.user_message
            task_log(f"✗ Errore critico: {e.user_message}", Qgis.Critical)
            return False
        except FetchDataError as e:
            self.message = e.user_message
            source_info = f" (sorgente: {e.source})" if e.source else ""
            task_log(f"✗ Errore dati{source_info}: {e.user_message}", Qgis.Critical)
            return not e.recoverable  # Return True if recoverable
        except FetchError as e:
            self.message = e.user_message
            task_log(f"✗ Errore: {e.user_message}", Qgis.Critical if not e.recoverable else Qgis.Warning)
            return e.recoverable
        except Exception as e:
            self.message = f"Errore imprevisto: {str(e)}"
            task_log(self.message, Qgis.Critical)
            return False

