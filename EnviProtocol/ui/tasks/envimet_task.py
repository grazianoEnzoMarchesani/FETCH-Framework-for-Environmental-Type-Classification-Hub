# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - ENVI-met Preparation Task
Background task for data clipping and vectorization.
"""

import os
from qgis.core import (
    QgsTask, QgsMessageLog, Qgis, QgsProject
)
from ...core.envimet_manager import ENVImetManager
from ...core.constants import FolderNames, FileNames

class ENVImetTask(QgsTask):
    """Background task to prepare GIS data for ENVI-met."""
    
    def __init__(self, data_manager, extent, crs):
        super().__init__("Preparazione Dati ENVI-met", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.extent = extent
        self.crs = crs
        self.em_manager = ENVImetManager()
        self.success = False
        self.message = ""

    def log(self, message, level=Qgis.Info):
        """Helper to log messages to the QGIS Message Log."""
        QgsMessageLog.logMessage(message, "EnviProtocol", level)

    def run(self):
        """Execute the preparation logic."""
        try:
            project_path = QgsProject.instance().fileName()
            project_dir = os.path.dirname(project_path)
            data_dir_name = self.data_manager.get_data_dir_name()
            root_data_dir = os.path.join(project_dir, data_dir_name)
            
            export_dir = os.path.join(root_data_dir, FolderNames.ENVIMET)
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)

            # 1. Analyze constraints using the correct data directory
            self.setProgress(10)
            margin, suggested_z, max_h, max_z = self.em_manager.get_model_constraints(root_data_dir)
            
            # 2. Prepare Sub Area
            self.setProgress(20)
            subarea_path = os.path.join(export_dir, FileNames.EM_SUB_AREA)
            crs_id = self.crs if isinstance(self.crs, str) else self.crs.authid()
            
            ok, msg = self.em_manager.prepare_sub_area(
                self.extent, crs_id, subarea_path, margin=margin
            )
            if not ok:
                self.message = f"Sub Area: {msg}"
                return False

            from qgis.core import QgsGeometry
            aoi_poly = QgsGeometry.fromRect(self.extent)
            if margin > 0:
                aoi_poly = aoi_poly.buffer(margin, 5)

            def find_file(folder, extension, keyword=None):
                folder_path = os.path.join(root_data_dir, folder)
                if not os.path.exists(folder_path): return None
                for root, dirs, files in os.walk(folder_path):
                    for f in files:
                        if f.lower().endswith(extension) and not f.startswith("."):
                            if keyword and keyword.lower() not in f.lower():
                                continue
                            return os.path.join(root, f)
                return None

            # 3. Vectorize Land Use (ESA)
            self.setProgress(40)
            esa_path = find_file(FolderNames.ESA, ".tif", "ESA")
            if esa_path:
                self.log(f"Processamento Land Use ESA: {esa_path}")
                surface_path = os.path.join(export_dir, FileNames.EM_SURFACES)
                ok, msg = self.em_manager.vectorize_land_use(esa_path, surface_path, self.extent)
                if not ok:
                    QgsMessageLog.logMessage(f"Avviso Land Use: {msg}", "EnviProtocol", Qgis.Warning)
                else:
                    self.log(f"Superfici salvate: {surface_path}")
            else:
                QgsMessageLog.logMessage(f"Dati Land Use (ESA) non trovati in {FolderNames.ESA}", "EnviProtocol", Qgis.Warning)

            # 4. Process Buildings (TUM)
            self.setProgress(60)
            bld_path = find_file(FolderNames.TUM, ".gpkg") # Any .gpkg in folder
            if bld_path:
                self.log(f"Processamento Edifici: {bld_path}")
                out_bld = os.path.join(export_dir, FileNames.EM_BUILDINGS)
                ok, msg = self.em_manager.process_buildings(bld_path, out_bld, aoi_poly, crs_id)
                if not ok:
                    QgsMessageLog.logMessage(f"Avviso Edifici: {msg}", "EnviProtocol", Qgis.Warning)
                else:
                    self.log(f"Edifici salvati: {out_bld}")
            else:
                QgsMessageLog.logMessage(f"Dati Edifici (TUM) non trovati in {FolderNames.TUM}", "EnviProtocol", Qgis.Warning)

            # 5. Process DTM (Tinitaly)
            self.setProgress(80)
            terrain_path = os.path.join(export_dir, "terrain_final.tif")
            ok, msg = self.em_manager.process_dtm(root_data_dir, terrain_path, self.extent, crs_id)
            if not ok:
                QgsMessageLog.logMessage(f"Avviso DTM: {msg}", "EnviProtocol", Qgis.Warning)
            else:
                self.log(f"DTM salvato: {terrain_path}")

            # 6. Process Vegetation (Advanced TCD + ETH)
            self.setProgress(90)
            tcd_path = find_file(FolderNames.HRL, ".tif", "TCD")
            eth_path = find_file(FolderNames.ETH, ".tif")
            if tcd_path and eth_path:
                self.log(f"Processamento Vegetazione: TCD={tcd_path}")
                veg_path = os.path.join(export_dir, FileNames.EM_VEGETATION)
                ok, msg = self.em_manager.process_vegetation_advanced(
                    tcd_path, eth_path, veg_path, aoi_poly, self.extent, crs_id
                )
                if not ok:
                    QgsMessageLog.logMessage(f"Avviso Vegetazione: {msg}", "EnviProtocol", Qgis.Warning)
                else:
                    self.log(f"Vegetazione salvata: {veg_path}")
            else:
                QgsMessageLog.logMessage(f"Dati Vegetazione (TCD/ETH) non trovati.", "EnviProtocol", Qgis.Warning)

            self.setProgress(100)
            self.success = True
            return True
        except Exception as e:
            self.message = str(e)
            return False

    def finished(self, result):
        """Called when the task is finished."""
        if result:
            QgsMessageLog.logMessage("Preparazione ENVI-met completata con successo.", "EnviProtocol", Qgis.Info)
        else:
            QgsMessageLog.logMessage(f"Errore preparazione ENVI-met: {self.message}", "EnviProtocol", Qgis.Critical)
