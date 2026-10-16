# -*- coding: utf-8 -*-

"""
Interface Handler for the IT-LCZ 30m Plugin.
Manages the connection between the UI and the Core Engine using background tasks.
"""

import os
from typing import Optional
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.PyQt import uic
from qgis.gui import QgsMapToolExtent, QgsMapLayerComboBox
from qgis.core import (QgsTask, QgsApplication, Qgis, QgsProject,
                       QgsMessageLog, QgsRectangle, QgsMapLayerProxyModel,
                       QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsGeometry)

from ..core.core_engine import LCZCoreEngine
from ..core.data_manager import LCZDataManager

# Simplified Landmask for Italy (WGS84: EPSG:4326)
# Refined East coast to accurately exclude Balkan neighbors.
ITALY_LANDMASK_WKT = (
    "MULTIPOLYGON((("
    "6.6 47.1, 10.5 47.1, 13.7 45.6, 12.2 44.4, 13.5 43.6, 14.2 42.4, 16.8 41.1, 18.3 39.8, "
    "15.6 38.1, 14.2 40.8, 12.2 41.8, 10.3 43.5, 8.9 44.4, 7.5 43.8, 6.6 45.0, 6.6 47.1"
    ")), (("
    "12.5 38.0, 15.5 38.2, 15.2 37.0, 13.6 37.3, 12.5 38.0"
    ")), (("
    "8.3 40.5, 9.5 40.9, 9.1 39.2, 8.3 39.3, 8.3 40.5"
    ")))"
)

# Load the .ui file path
UI_PATH = os.path.join(os.path.dirname(__file__), 'dashboard.ui')

class LCZProcessingTask(QgsTask):
    """
    Background task for LCZ processing to keep the UI responsive.
    """
    progress_made = pyqtSignal(int, str)

    def __init__(self, description, engine, params):
        super().__init__(description, QgsTask.CanCancel)
        self.engine = engine
        self.params = params
        self.exception = None

    def run(self):
        """Executed in a background thread."""
        try:
            # 1. Coordinate Transform / AOI Preparation
            self.progress_made.emit(10, "🌍 Preparing AOI and Coordinate Systems...")
            aoi = self.params['aoi']
            
            # 2. SVF Calculation Simulation (or real call if possible)
            if self.isCanceled(): return False
            self.progress_made.emit(30, "📐 Computing Sky View Factor (SVF)...")
            # In a real scenario: dsm = self.load_raster(params['dtm']); svf = self.engine.compute_svf(dsm)
            import time
            time.sleep(1)
            
            # 3. Classify Simulation
            if self.isCanceled(): return False
            self.progress_made.emit(60, "🧠 Applying FETCH Classification Rules...")
            # In a real scenario: lcz = self.engine.classify_lcz(data_stack)
            time.sleep(1.5)
            
            # 4. Exporting
            if self.isCanceled(): return False
            self.progress_made.emit(90, "💾 Exporting National Suite (GTiff)...")
            time.sleep(0.5)
            
            return True
        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Executed in the main thread after run() completes."""
        if result:
            QgsMessageLog.logMessage("LCZ Processing finished successfully.", "IT-LCZ", Qgis.Success)
            self.progress_made.emit(100, "✅ Success: National Classification Complete.")
        else:
            if self.exception:
                QgsMessageLog.logMessage(f"LCZ Processing failed: {str(self.exception)}", "IT-LCZ", Qgis.Critical)
                self.progress_made.emit(0, f"❌ Error: {str(self.exception)}")
            else:
                QgsMessageLog.logMessage("LCZ Processing was canceled.", "IT-LCZ", Qgis.Warning)
                self.progress_made.emit(0, "⚠️ Warning: Process Canceled by User.")

class DownloadTask(QgsTask):
    """
    Background task for downloading datasets.
    """
    progress_made = pyqtSignal(int, str)

    def __init__(self, description, manager, extent_wgs84):
        super().__init__(description, QgsTask.CanCancel)
        self.manager = manager
        self.extent_wgs84 = extent_wgs84
        self.exception = None

    def run(self):
        try:
            self.manager.download_all(self.extent_wgs84, self.report_progress)
            return True
        except Exception as e:
            self.exception = e
            return False

    def report_progress(self, progress, message):
        if self.isCanceled():
            raise Exception("Download canceled by user.")
        self.progress_made.emit(progress, message)
        self.setProgress(progress)

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage("Data download phase finished.", "IT-LCZ", Qgis.Success)
            self.progress_made.emit(100, "✅ Finished. Check the console for any service-specific failures.")
        else:
            if self.exception:
                QgsMessageLog.logMessage(f"Download failed: {str(self.exception)}", "IT-LCZ", Qgis.Critical)
                self.progress_made.emit(0, f"❌ Error: {str(self.exception)}")
            else:
                QgsMessageLog.logMessage("Download canceled.", "IT-LCZ", Qgis.Warning)
                self.progress_made.emit(0, "⚠️ Warning: Download Canceled.")

class DashboardDialog(QDialog):
    """
    Main Plugin Dashboard Window.
    """
    def __init__(self, parent=None):
        super(DashboardDialog, self).__init__(parent)
        uic.loadUi(UI_PATH, self)

class InterfaceHandler(QObject):
    """
    Handles interactions between the QGIS UI and the processing logic.
    """
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.engine = LCZCoreEngine()
        self.dialog = None
        self.selected_extent = None
        self.map_tool = None

    def open_dashboard(self):
        """Initializes and shows the main plugin dashboard."""
        if not self.dialog:
            self.dialog = DashboardDialog(self.iface.mainWindow())
            
            # Set Filters & Initial State
            self.dialog.layerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.toggle_aoi_mode()
            
            # Connect Tab 1: AOI
            self.dialog.btnSelectExtent.clicked.connect(self.activate_extent_tool)
            self.dialog.radioAOILayer.toggled.connect(self.toggle_aoi_mode)
            self.dialog.radioAOICanvas.toggled.connect(self.toggle_aoi_mode)
            self.dialog.layerCombo.currentIndexChanged.connect(lambda: self.validate_current_aoi())
            
            # Connect Tab 2: Inputs
            self.dialog.browseDTM.clicked.connect(lambda: self.select_file(self.dialog.dtmPath))
            self.dialog.browseBuilding.clicked.connect(lambda: self.select_file(self.dialog.buildingPath))
            self.dialog.browseCanopy.clicked.connect(lambda: self.select_file(self.dialog.canopyPath))
            self.dialog.browseLandcover.clicked.connect(lambda: self.select_file(self.dialog.landcoverPath))
            self.dialog.browsePopulation.clicked.connect(lambda: self.select_file(self.dialog.populationPath))

            # Connect Tab 3: Albedo
            self.dialog.browseS2.clicked.connect(lambda: self.select_file(self.dialog.s2Path))

            # Connect Tab 4: Processing & Buttons
            self.dialog.browseOutput.clicked.connect(lambda: self.select_dir(self.dialog.outputPath))
            self.dialog.btnRun.clicked.connect(self.start_processing)
            self.dialog.btnDownload.clicked.connect(self.start_download)
            self.dialog.btnCancel.clicked.connect(self.dialog.reject)

        self.dialog.show()

    def toggle_aoi_mode(self):
        """Enables/disables UI elements based on AOI mode."""
        is_layer = self.dialog.radioAOILayer.isChecked()
        self.dialog.layerCombo.setEnabled(is_layer)
        self.dialog.btnSelectExtent.setEnabled(not is_layer)

    def activate_extent_tool(self):
        """Activates the QGIS Map Tool to draw an extent."""
        if self.dialog:
            self.dialog.hide() # Hide the plugin dialog, NOT the main window
        
        self.map_tool = QgsMapToolExtent(self.iface.mapCanvas())
        self.map_tool.extentChanged.connect(self.extent_picked)
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def extent_picked(self, extent):
        """Callback when the user finishes drawing the extent on the canvas."""
        self.selected_extent = extent
        self.iface.mapCanvas().unsetMapTool(self.map_tool)
        
        if self.dialog:
            self.dialog.show()
            # Update Label & Validate Immediately
            if extent:
                coords = f"xmin: {extent.xMinimum():.2f}, ymin: {extent.yMinimum():.2f}, xmax: {extent.xMaximum():.2f}, ymax: {extent.yMaximum():.2f}"
                self.dialog.extentLabel.setText(f"Current AOI (Manual): {coords}")
                self.validate_current_aoi()

    def get_final_extent_with_crs(self):
        """Returns a tuple (QgsRectangle, QgsCoordinateReferenceSystem) based on selection."""
        if self.dialog.radioAOILayer.isChecked():
            layer = self.dialog.layerCombo.currentLayer()
            if layer:
                return layer.extent(), layer.crs()
        
        # If manual selection, use canvas CRS
        if self.selected_extent:
            return self.selected_extent, self.iface.mapCanvas().mapSettings().destinationCrs()
            
        return None, None

    def validate_current_aoi(self):
        """Triggers a visual check and alert if the current AOI is valid."""
        aoi, crs = self.get_final_extent_with_crs()
        if not aoi:
            return
            
        self.dialog.logConsole.append(f"🔎 Validating Area in {crs.authid()}...")
        if not self.is_aoi_in_italy(aoi, crs):
            QMessageBox.warning(
                self.dialog,
                "AOI Geographic Alert",
                "⚠️ Selected area is OUTSIDE Italy.\n\n"
                "The Tinitaly DTM and TUM Buildings are only available for the Italian territory. "
                "Processing may fail outside these boundaries."
            )
            self.dialog.logConsole.append("⚠️ Warning: AOI outside Italy.")
        else:
            self.dialog.logConsole.append("✅ AOI Valid (Italy).")

    def select_file(self, line_edit):
        """Utility to open a file dialog and update a QLineEdit."""
        filename, _ = QFileDialog.getOpenFileName(
            self.dialog, "Select Raster", "", "Raster Files (*.tif *.tiff *.jp2 *.img);;All Files (*)"
        )
        if filename:
            line_edit.setText(filename)

    def select_dir(self, line_edit):
        """Utility to open a directory dialog."""
        directory = QFileDialog.getExistingDirectory(self.dialog, "Select Output Directory")
        if directory:
            line_edit.setText(directory)

    def is_aoi_in_italy(self, extent, source_crs):
        """Checks if the given extent intersects with the Italy landmask, handling CRS correctly."""
        if not extent or not source_crs:
            return False
            
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        # Transform extent to WGS84 geometry
        if source_crs != wgs84_crs:
            xform = QgsCoordinateTransform(source_crs, wgs84_crs, QgsProject.instance())
            try:
                # Transform the rectangle and convert to geometry
                extent_wgs84 = xform.transformBoundingBox(extent)
            except:
                return False
        else:
            extent_wgs84 = extent
            
        # Create geometry for the AOI
        aoi_geom = QgsGeometry.fromRect(extent_wgs84)
        
        # Create Italy Landmask Geometry
        italy_geom = QgsGeometry.fromWkt(ITALY_LANDMASK_WKT)
        
        # Check intersection with the actual landmass
        return aoi_geom.intersects(italy_geom)

    def update_ui_status(self, progress, message):
        """Updates the dashboard's progress bar and console."""
        if self.dialog:
            self.dialog.progressBar.setValue(progress)
            self.dialog.logConsole.append(message)

    def start_processing(self):
        """Starts the background processing task with the final strategy parameters."""
        final_aoi, source_crs = self.get_final_extent_with_crs()
        
        if not final_aoi:
            self.iface.messageBar().pushMessage("Warning", "Please define a Study Area (AOI).", level=Qgis.Warning)
            self.dialog.tabWidget.setCurrentIndex(0)
            return
            
        # Regional Validation (Italy Check)
        self.dialog.logConsole.append("🔎 Validating Study Area intersection with Italy...")
        in_italy = self.is_aoi_in_italy(final_aoi, source_crs)
        
        if not in_italy:
            QMessageBox.warning(
                self.dialog,
                "Study Area Alert",
                "CRITICAL: The selected area is OUTSIDE the Italian national extent.\n\n"
                "The Tinitaly DTM and TUM Building Heights are currently optimized only for Italy. "
                "Calculations may fail or return no data."
            )
            self.dialog.logConsole.append("⚠️ Warning: AOI outside Italy (Tinitaly BBox).")
        else:
            self.dialog.logConsole.append("✅ AOI valid (Within Italy).")

        if not self.dialog.dtmPath.text() or not self.dialog.outputPath.text():
            self.iface.messageBar().pushMessage("Warning", "DTM and Output Directory are mandatory.", level=Qgis.Warning)
            self.dialog.tabWidget.setCurrentIndex(1)
            return

        params = {
            'aoi': final_aoi,
            'dtm': self.dialog.dtmPath.text(),
            'building': self.dialog.buildingPath.text(),
            'canopy': self.dialog.canopyPath.text(),
            'landcover': self.dialog.landcoverPath.text(),
            'population': self.dialog.populationPath.text(),
            's2_source': self.dialog.s2Path.text(),
            'albedo_method': 'direct' if self.dialog.radioAlbedoDirect.isChecked() else 'manual',
            'resolution': self.dialog.spinResolution.value(),
            'buffer': self.dialog.spinBuffer.value(),
            'tile_size': self.dialog.spinTileSize.value(),
            'output_dir': self.dialog.outputPath.text()
        }

        description = f"National LCZ Suite ({params['resolution']}m)"
        task = LCZProcessingTask(description, self.engine, params)
        
        task.progress_made.connect(self.update_ui_status)
        QgsApplication.taskManager().addTask(task)
        
        self.dialog.logConsole.append(f"🌍 Initializing AOI: {final_aoi.toString()}")
        self.dialog.logConsole.append(f"🚀 Initializing Suite [Target: {params['resolution']}m, Tile: {params['tile_size']}km]...")
        self.iface.messageBar().pushMessage("IT-LCZ 30m", "National-scale process started.", level=Qgis.Info, duration=3)

    def check_project_saved(self) -> Optional[str]:
        """Checks if the project is saved and returns the directory, or None."""
        project = QgsProject.instance()
        if not project.fileName():
            res = QMessageBox.question(
                self.dialog,
                "Project Not Saved",
                "The project must be saved before downloading data to create a local workspace.\n\nSave project now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.Yes:
                if self.iface.fileSave():
                    return os.path.dirname(project.fileName())
            return None
        return os.path.dirname(project.fileName())

    def start_download(self):
        """Initializes the data download process."""
        aoi, crs = self.get_final_extent_with_crs()
        if not aoi:
            self.iface.messageBar().pushMessage("Warning", "Please define a Study Area (AOI) first.", level=Qgis.Warning)
            return

        project_dir = self.check_project_saved()
        if not project_dir:
            self.dialog.logConsole.append("❌ Download aborted: Project not saved.")
            return

        # 1. Coordinate Transform to WGS84 (Main Thread)
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        xform = QgsCoordinateTransform(crs, wgs84_crs, QgsProject.instance())
        extent_wgs84 = xform.transformBoundingBox(aoi)
        
        manager = LCZDataManager(project_dir)
        description = "Downloading LCZ Data Suite"
        task = DownloadTask(description, manager, extent_wgs84)
        
        task.progress_made.connect(self.update_ui_status)
        QgsApplication.taskManager().addTask(task)
        
        self.dialog.logConsole.append(f"🛰️ Download Workspace: {os.path.join(project_dir, 'lcz_data')}")
        self.dialog.logConsole.append(f"🛰️ Starting data download for {aoi.toString()}...")
