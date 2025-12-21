# -*- coding: utf-8 -*-

import os
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QCheckBox, QProgressBar, 
    QGroupBox, QScrollArea, QFileDialog, QComboBox,
    QRadioButton, QLineEdit
)
from qgis.core import (
    QgsProject, QgsMapLayer, QgsWkbTypes, QgsMapLayerProxyModel, 
    QgsRectangle, QgsMessageLog, Qgis, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, QgsGeometry
)
from qgis.gui import QgsMapLayerComboBox, QgsFileWidget
from ..core.utils import is_within_italy
from ..core.data_manager import DataManager

class ITLCZDashboard(QDockWidget):
    def __init__(self, iface, parent=None):
        super(ITLCZDashboard, self).__init__(parent)
        self.iface = iface
        self.data_manager = DataManager(iface)
        self.setWindowTitle("IT-LCZ 30m Dashboard")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.root = QWidget()
        self.layout = QVBoxLayout(self.root)
        
        # ... (rest of the layout)
        self.extent_val = None
        self.extent_crs = None
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        
        self.layout.addWidget(self.scroll)
        
        # 1. Project Setup
        self.setup_group = QGroupBox("1. Project Setup")
        self.setup_layout = QVBoxLayout(self.setup_group)
        
        # AOI Layer Selection
        self.setup_layout.addWidget(QLabel("Area of Interest (AOI):"))
        
        self.aoi_layer_radio = QRadioButton("Use Vector Layer")
        self.aoi_layer_radio.setChecked(True)
        self.setup_layout.addWidget(self.aoi_layer_radio)
        
        self.aoi_combo = QgsMapLayerComboBox()
        self.aoi_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.setup_layout.addWidget(self.aoi_combo)
        
        # AOI Extent Selection
        self.aoi_extent_radio = QRadioButton("Use Map Canvas Extent")
        self.setup_layout.addWidget(self.aoi_extent_radio)
        
        self.btn_current_extent = QPushButton("Capture Current Extent")
        self.btn_current_extent.setEnabled(False)
        self.setup_layout.addWidget(self.btn_current_extent)
        
        self.extent_label = QLabel("Extent: Not captured")
        self.extent_label.setStyleSheet("font-size: 10px; color: #7f8c8d;")
        self.setup_layout.addWidget(self.extent_label)
        
        # Italy Validation Warning
        self.warning_label = QLabel("⚠ Attenzione: l'area selezionata sembra essere fuori dall'Italia. Alcuni dati (es. Tinitaly) potrebbero non essere disponibili.")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #d35400; font-weight: bold; background-color: #fce4ec; border: 1px solid #f8bbd0; border-radius: 4px; padding: 5px;")
        self.warning_label.hide()
        self.setup_layout.addWidget(self.warning_label)
        
        # Toggle logic
        self.aoi_layer_radio.toggled.connect(self.toggle_aoi_mode)
        self.btn_current_extent.clicked.connect(self.capture_extent)
        self.aoi_combo.layerChanged.connect(self.validate_aoi_layer)
        
        self.setup_layout.addSpacing(10)
        
        # Output Directory information removed as it will be project-based
        self.project_label = QLabel("Output: Saving to project directory")
        self.project_label.setStyleSheet("font-style: italic; color: #2c3e50;")
        self.setup_layout.addWidget(self.project_label)
        
        self.scroll_layout.addWidget(self.setup_group)
        
        # 2. Data Acquisition
        self.data_group = QGroupBox("2. Data Acquisition")
        self.data_layout = QVBoxLayout(self.data_group)
        
        self.sources = [
            "Tinitaly (DTM 10m)",
            "TUM (Edifici H 10m)",
            "ETH (Alberi H 10m)",
            "ESA WorldCover (Land Use)",
            "Meta HRSL (Popolazione)",
            "S2GM (Albedo Sentinel-2)"
        ]
        self.checks = {}
        for src in self.sources:
            cb = QCheckBox(src)
            cb.setChecked(True)
            self.data_layout.addWidget(cb)
            self.checks[src] = cb
        
        # CDSE Credentials for Sentinel-2
        self.data_layout.addSpacing(10)
        self.cdse_label = QLabel("Credenziali Copernicus (CDSE):")
        self.cdse_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.data_layout.addWidget(self.cdse_label)
        
        self.cdse_user_layout = QHBoxLayout()
        self.cdse_user_layout.addWidget(QLabel("Email:"))
        self.cdse_username = QLineEdit()
        self.cdse_username.setPlaceholderText("email@copernicus.eu")
        self.cdse_user_layout.addWidget(self.cdse_username)
        self.data_layout.addLayout(self.cdse_user_layout)
        
        self.cdse_pass_layout = QHBoxLayout()
        self.cdse_pass_layout.addWidget(QLabel("Password:"))
        self.cdse_password = QLineEdit()
        self.cdse_password.setEchoMode(QLineEdit.Password)
        self.cdse_password.setPlaceholderText("password")
        self.cdse_pass_layout.addWidget(self.cdse_password)
        self.data_layout.addLayout(self.cdse_pass_layout)
        
        self.data_layout.addSpacing(10)
            
        self.btn_download = QPushButton("Esegui Download Selezione")
        self.btn_download.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold; padding: 5px;")
        self.btn_download.clicked.connect(self.run_downloads)
        self.data_layout.addWidget(self.btn_download)
        
        self.scroll_layout.addWidget(self.data_group)
        
        # 3. Processing
        self.proc_group = QGroupBox("3. Processing & Classification")
        self.proc_layout = QVBoxLayout(self.proc_group)
        
        self.btn_dsm = QPushButton("Genera DSM Sintetico")
        self.btn_params = QPushButton("Calcola Parametri LCZ")
        self.btn_classify = QPushButton("Esegui Classificazione Finale")
        self.btn_classify.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        
        self.proc_layout.addWidget(self.btn_dsm)
        self.proc_layout.addWidget(self.btn_params)
        self.proc_layout.addWidget(self.btn_classify)
        
        self.scroll_layout.addWidget(self.proc_group)
        
        # Progress & Log
        self.info_group = QGroupBox("Status")
        self.info_layout = QVBoxLayout(self.info_group)
        self.progress = QProgressBar()
        self.status_label = QLabel("Pronto")
        self.info_layout.addWidget(self.status_label)
        self.info_layout.addWidget(self.progress)
        
        self.scroll_layout.addStretch()
        self.layout.addWidget(self.info_group)
        
        self.setWidget(self.root)
        
        # Initial validation if a layer is selected
        self.validate_aoi_layer()

    def toggle_aoi_mode(self, checked):
        self.aoi_combo.setEnabled(checked)
        self.btn_current_extent.setEnabled(not checked)
        if checked:
            self.validate_aoi_layer()
        else:
            self.warning_label.hide()

    def validate_aoi_layer(self):
        layer = self.aoi_combo.currentLayer()
        if layer:
            within = is_within_italy(layer.extent(), layer.crs().authid())
            self.warning_label.setVisible(not within)
        else:
            self.warning_label.hide()

    def capture_extent(self):
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs().authid()
        self.extent_val = extent
        self.extent_crs = crs
        self.extent_label.setText(f"Captured: {extent.toString(2)} ({crs})")
        within = is_within_italy(extent, crs)
        self.warning_label.setVisible(not within)

    def run_downloads(self):
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            self.status_label.setText("⚠ Salva il progetto prima di continuare")
            self.project_label.setText("Output: PROGETTO NON SALVATO")
            self.project_label.setStyleSheet("font-style: italic; color: #c0392b; font-weight: bold;")
            return
            
        project_dir = os.path.dirname(project_path)
        self.project_label.setText(f"Output: {project_dir}")
        self.project_label.setStyleSheet("font-style: italic; color: #27ae60;")
        self.status_label.setText("Calcolo dei quadranti Tinitaly...")

        # Get AOI extent and CRS
        if self.aoi_layer_radio.isChecked():
            layer = self.aoi_combo.currentLayer()
            if not layer:
                self.iface.messageBar().pushMessage("Errore", "Nessun layer AOI selezionato.", level=2)
                return
            extent = layer.extent()
            crs = layer.crs().authid()
        else:
            if not self.extent_val:
                self.iface.messageBar().pushMessage("Errore", "Cattura l'estensione della mappa prima di procedere.", level=2)
                return
            extent = self.extent_val
            crs = self.extent_crs

        # Calculate tiles
        tiles = self.data_manager.calculate_tinitaly_tiles(extent, crs)
        
        if not tiles:
             self.iface.messageBar().pushMessage("Info", "Nessun quadrante DTM trovato nell'area scelta.", level=1)
             return

        self.status_label.setText(f"Trovati {len(tiles)} quadranti Tinitaly.")
        
        # Check if Tinitaly download is enabled
        if self.checks["Tinitaly (DTM 10m)"].isChecked():
            self.progress.setMaximum(len(tiles))
            self.progress.setValue(0)
            
            error_count = 0
            for i, tile in enumerate(tiles):
                self.status_label.setText(f"Download in corso: {tile} ({i+1}/{len(tiles)})")
                QgsMessageLog.logMessage(f"Avvio download {i+1}/{len(tiles)}: {tile}", "IT-LCZ", Qgis.Info)
                
                success, msg = self.data_manager.download_tinitaly_tile(tile)
                
                if success:
                    QgsMessageLog.logMessage(f"Successo {tile}: {msg}", "IT-LCZ", Qgis.Success)
                else:
                    QgsMessageLog.logMessage(f"Fallimento {tile}: {msg}", "IT-LCZ", Qgis.Critical)
                    error_count += 1
                
                self.progress.setValue(i + 1)
                # Allow UI to refresh (basic approach for now, usually needs a thread)
                from qgis.PyQt.QtWidgets import QApplication
                QApplication.processEvents()

            if error_count == 0:
                self.status_label.setText("Download terminato con successo.")
                self.iface.messageBar().pushMessage("IT-LCZ 30m", "Tutti i quadranti DTM scaricati correttamente.", level=3)
            else:
                self.status_label.setText(f"Download completato con {error_count} errori.")
                self.iface.messageBar().pushMessage("IT-LCZ 30m", f"Download completato con {error_count} errori. Controlla il log.", level=2)
        
        # --- TUM Global Building Heights ---
        if self.checks["TUM (Edifici H 10m)"].isChecked():
            # Get AOI Geometry for clipping (WGS84)
            source_crs = QgsCoordinateReferenceSystem(crs)
            wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(source_crs, wgs84_crs, QgsProject.instance())
            aoi_geom = QgsGeometry.fromRect(extent)
            aoi_geom.transform(transform)

            for category in self.data_manager.tum_categories:
                self.status_label.setText(f"Acquisizione TUM {category} via WFS...")
                results = self.data_manager.download_tum_data(category=category, aoi_geometry=aoi_geom)
                
                downloaded = [r[0] for r in results if r[1]]
                if downloaded:
                    self.iface.messageBar().pushMessage("TUM GBA", f"Scaricato file {category}: {', '.join(downloaded)}", level=0)
                else:
                    QgsMessageLog.logMessage(f"Nessun file trovato per categoria TUM: {category}", "IT-LCZ", Qgis.Warning)

        # --- ETH Global Canopy Height ---
        if self.checks["ETH (Alberi H 10m)"].isChecked():
            self.status_label.setText("Acquisizione ETH Global Canopy Height...")
            # fetch_eth_canopy calculates tiles internally
            results = self.data_manager.fetch_eth_canopy(extent, crs)
            
            downloaded = [r[0] for r in results if r[1]]
            if downloaded:
                self.iface.messageBar().pushMessage("ETH Canopy", f"Scaricati {len(downloaded)} file ETH Canopy.", level=0)
            else:
                QgsMessageLog.logMessage("Nessun file ETH Canopy scaricato o trovato.", "IT-LCZ", Qgis.Warning)

        # --- ESA WorldCover ---
        if self.checks["ESA WorldCover (Land Use)"].isChecked():
            self.status_label.setText("Acquisizione ESA WorldCover (Land Use)...")
            results = self.data_manager.fetch_esa_worldcover(extent, crs)
            
            downloaded = [r[0] for r in results if r[1]]
            if downloaded:
                self.iface.messageBar().pushMessage("ESA WorldCover", f"Scaricati {len(downloaded)} file ESA WorldCover.", level=0)
            else:
                QgsMessageLog.logMessage("Nessun file ESA WorldCover scaricato o trovato.", "IT-LCZ", Qgis.Warning)

        # --- Meta HRSL Population ---
        if self.checks["Meta HRSL (Popolazione)"].isChecked():
            self.status_label.setText("Acquisizione Meta HRSL (Popolazione)...")
            success, msg = self.data_manager.fetch_meta_hrsl(extent, crs)
            
            if success:
                self.iface.messageBar().pushMessage("Meta HRSL", "Popolazione acquisita e ritagliata con successo.", level=3)
            else:
                self.iface.messageBar().pushMessage("Meta HRSL", f"Errore: {msg}", level=2)
                QgsMessageLog.logMessage(f"Meta HRSL Fallimento: {msg}", "IT-LCZ", Qgis.Critical)

        # --- Sentinel-2 Albedo ---
        if self.checks["S2GM (Albedo Sentinel-2)"].isChecked():
            self.status_label.setText("Acquisizione Sentinel-2 Albedo (potrebbe richiedere alcuni minuti)...")
            from qgis.PyQt.QtWidgets import QApplication
            QApplication.processEvents()  # Update UI before long operation
            
            # Get credentials from UI fields
            cdse_user = self.cdse_username.text().strip()
            cdse_pass = self.cdse_password.text()
            
            if not cdse_user or not cdse_pass:
                self.iface.messageBar().pushMessage("Sentinel-2 Albedo", "Inserisci le credenziali CDSE.", level=2)
                QgsMessageLog.logMessage("Credenziali CDSE mancanti.", "IT-LCZ", Qgis.Warning)
            else:
                success, msg = self.data_manager.fetch_sentinel2_albedo(extent, crs, cdse_user, cdse_pass)
                
                if success:
                    self.iface.messageBar().pushMessage("Sentinel-2 Albedo", "Albedo calcolato con successo.", level=3)
                else:
                    self.iface.messageBar().pushMessage("Sentinel-2 Albedo", f"Errore: {msg}", level=2)
                    QgsMessageLog.logMessage(f"Sentinel-2 Albedo Fallimento: {msg}", "IT-LCZ", Qgis.Critical)

        self.status_label.setText("Processo completato.")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    closingPlugin = pyqtSignal()
