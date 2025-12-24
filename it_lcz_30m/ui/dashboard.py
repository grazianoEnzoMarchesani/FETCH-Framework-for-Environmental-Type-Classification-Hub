# -*- coding: utf-8 -*-

import os
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QCheckBox, QProgressBar, 
    QGroupBox, QScrollArea, QFileDialog, QComboBox,
    QRadioButton, QLineEdit, QInputDialog, QGridLayout
)
from qgis.core import (
    QgsProject, QgsMapLayer, QgsWkbTypes, QgsMapLayerProxyModel, 
    QgsRectangle, QgsMessageLog, Qgis, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, QgsGeometry, QgsTask, QgsApplication
)
from qgis.gui import QgsMapLayerComboBox, QgsFileWidget, QgsCollapsibleGroupBox
from ..core.utils import is_within_italy
from ..core.data_manager import DataManager

STYLESHEET = """
QWidget#DashboardRoot {
    background-color: #f5f6f7;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #dcdde1;
    border-radius: 6px;
    margin-top: 20px;
    padding: 15px 10px 10px 10px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #2c3e50;
}
QPushButton {
    border: none;
    border-radius: 4px;
    padding: 8px 15px;
    font-size: 12px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: rgba(0,0,0,0.1);
}
#PrimaryButton {
    background-color: #3498db;
    color: white;
    font-weight: bold;
}
#PrimaryButton:hover {
    background-color: #2980b9;
}
#DarkButton {
    background-color: #2c3e50;
    color: white;
    font-weight: bold;
}
#DarkButton:hover {
    background-color: #1a252f;
}
#AccentButton {
    background-color: #9b59b6;
    color: white;
}
#AccentButton:hover {
    background-color: #8e44ad;
}
#SuccessButton {
    background-color: #27ae60;
    color: white;
    font-weight: bold;
}
#SuccessButton:hover {
    background-color: #219150;
}
#WarningLabel {
    color: #d35400; 
    font-weight: bold; 
    background-color: #fff3e0; 
    border: 1px solid #ffe0b2; 
    border-radius: 4px; 
    padding: 8px;
}
#ExtentLabel {
    font-family: 'Courier New', Courier, monospace;
    font-size: 11px;
    background-color: #f1f2f6;
    border: 1px solid #dfe4ea;
    border-radius: 3px;
    padding: 5px;
    color: #57606f;
}
#PrimaryButton:disabled, #DarkButton:disabled, #AccentButton:disabled, #SuccessButton:disabled {
    background-color: #e0e0e0;
    color: #a0a0a0;
}
QLabel:disabled, QCheckBox:disabled, QRadioButton:disabled {
    color: #b2bec3;
}
"""

class ITLCZDashboard(QDockWidget):
    def __init__(self, iface, parent=None):
        super(ITLCZDashboard, self).__init__(parent)
        self.iface = iface
        self.data_manager = DataManager(iface)
        self.setWindowTitle("FETCH Dashboard")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.root = QWidget()
        self.root.setObjectName("DashboardRoot")
        self.root.setStyleSheet(STYLESHEET)
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)
        
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
        self.setup_group = QgsCollapsibleGroupBox("1. Project Setup")
        self.setup_layout = QVBoxLayout(self.setup_group)
        
        # AOI Selection Grid
        self.aoi_grid = QGridLayout()
        self.aoi_grid.setContentsMargins(0, 5, 0, 5)
        
        self.aoi_layer_radio = QRadioButton("Use Vector Layer")
        self.aoi_layer_radio.setChecked(True)
        self.aoi_grid.addWidget(self.aoi_layer_radio, 0, 0)
        
        self.aoi_combo = QgsMapLayerComboBox()
        self.aoi_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.aoi_grid.addWidget(self.aoi_combo, 0, 1)
        
        self.aoi_extent_radio = QRadioButton("Use Map Canvas Extent")
        self.aoi_grid.addWidget(self.aoi_extent_radio, 1, 0)
        
        self.btn_current_extent = QPushButton("Capture Extent")
        self.btn_current_extent.setObjectName("PrimaryButton")
        self.btn_current_extent.setIcon(QgsApplication.getThemeIcon("mActionSelectExtent.svg"))
        self.btn_current_extent.setEnabled(False)
        self.aoi_grid.addWidget(self.btn_current_extent, 1, 1)
        
        self.setup_layout.addLayout(self.aoi_grid)
        
        self.extent_label = QLabel("No extent captured")
        self.extent_label.setObjectName("ExtentLabel")
        self.extent_label.setAlignment(Qt.AlignCenter)
        self.setup_layout.addWidget(self.extent_label)
        
        # Italy Validation Warning
        self.warning_label = QLabel("⚠ Area fuori dall'Italia. Alcuni dati potrebbero mancare.")
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        self.setup_layout.addWidget(self.warning_label)
        
        # Toggle logic
        self.aoi_layer_radio.toggled.connect(self.toggle_aoi_mode)
        self.btn_current_extent.clicked.connect(self.capture_extent)
        self.aoi_combo.layerChanged.connect(self.validate_aoi_layer)
        
        # Output info
        self.project_label = QLabel("Output: Saving to project directory")
        self.project_label.setStyleSheet("font-size: 11px; color: #7f8c8d; margin-top: 5px;")
        self.setup_layout.addWidget(self.project_label)
        
        self.scroll_layout.addWidget(self.setup_group)
        
        # 2. Data Acquisition
        self.data_group = QgsCollapsibleGroupBox("2. Data Acquisition")
        self.data_layout = QVBoxLayout(self.data_group)
        
        # Sources Grid
        self.sources_grid = QGridLayout()
        self.sources = [
            "Tinitaly (DTM 10m)", "TUM (Edifici H 10m)",
            "ETH (Alberi H 10m)", "ESA WorldCover (Land Use)",
            "Meta HRSL (Popolazione)", "S2GM (Albedo Sentinel-2)"
        ]
        self.checks = {}
        for i, src in enumerate(self.sources):
            cb = QCheckBox(src)
            cb.setChecked(True)
            self.sources_grid.addWidget(cb, i // 2, i % 2)
            self.checks[src] = cb
        self.data_layout.addLayout(self.sources_grid)
        
        # CDSE Credentials
        self.creds_group = QWidget()
        self.creds_layout = QGridLayout(self.creds_group)
        self.creds_layout.setContentsMargins(0, 10, 0, 5)
        
        # Help label with registration link
        self.cdse_help = QLabel('Richiede account <a href="https://dataspace.copernicus.eu">Copernicus Data Space</a>')
        self.cdse_help.setOpenExternalLinks(True)
        self.cdse_help.setStyleSheet("font-size: 10px; color: #34495e;")
        self.creds_layout.addWidget(self.cdse_help, 0, 0, 1, 2)
        
        self.creds_layout.addWidget(QLabel("Email CDSE:"), 1, 0)
        self.cdse_username = QLineEdit()
        self.cdse_username.setPlaceholderText("email@copernicus.eu")
        self.creds_layout.addWidget(self.cdse_username, 1, 1)
        
        self.creds_layout.addWidget(QLabel("Password CDSE:"), 2, 0)
        self.cdse_password = QLineEdit()
        self.cdse_password.setEchoMode(QLineEdit.Password)
        self.cdse_password.setPlaceholderText("••••••••")
        self.creds_layout.addWidget(self.cdse_password, 2, 1)
        
        self.data_layout.addWidget(self.creds_group)
        
        # Link S2GM checkbox to credentials visibility
        self.checks["S2GM (Albedo Sentinel-2)"].toggled.connect(self.creds_group.setVisible)
        # Initial state based on checkbox
        self.creds_group.setVisible(self.checks["S2GM (Albedo Sentinel-2)"].isChecked())
            
        self.btn_download = QPushButton(" Esegui Download Selezione")
        self.btn_download.setObjectName("DarkButton")
        self.btn_download.setIcon(QgsApplication.getThemeIcon("mActionArrowDown.svg"))
        self.btn_download.clicked.connect(self.run_downloads)
        self.data_layout.addWidget(self.btn_download)
        
        self.scroll_layout.addWidget(self.data_group)
        
        # 3. Processing
        self.proc_group = QgsCollapsibleGroupBox("3. Elaborazione Sequenziale")
        self.proc_layout = QVBoxLayout(self.proc_group)
        self.proc_layout.setSpacing(2)
        
        self.btn_unify = QPushButton(" 1. Unifica e Ritaglia Dati")
        self.btn_unify.setObjectName("PrimaryButton")
        self.btn_unify.setIcon(QgsApplication.getThemeIcon("mActionRelationAdd.svg"))
        self.btn_unify.setToolTip("FASE 1: Riproietta tutti i dati in UTM e ritaglia sull'AOI")
        self.btn_unify.clicked.connect(self.run_unification)
        self.proc_layout.addWidget(self.btn_unify)
        
        self.arrow1 = QLabel("▼")
        self.arrow1.setAlignment(Qt.AlignCenter)
        self.arrow1.setStyleSheet("color: #bdc3c7; font-size: 10px; margin: 2px 0;")
        self.proc_layout.addWidget(self.arrow1)
        
        self.btn_dsm = QPushButton(" 2. Genera DSM Sintetico")
        self.btn_dsm.setObjectName("PrimaryButton")
        self.btn_dsm.setIcon(QgsApplication.getThemeIcon("mActionHillshade.svg"))
        self.btn_dsm.setToolTip("FASE 2: Crea DSM = DTM + Altezze Edifici + Altezze Alberi")
        self.btn_dsm.clicked.connect(self.run_dsm_generation)
        self.proc_layout.addWidget(self.btn_dsm)
        
        self.arrow2 = QLabel("▼")
        self.arrow2.setAlignment(Qt.AlignCenter)
        self.arrow2.setStyleSheet("color: #bdc3c7; font-size: 10px; margin: 2px 0;")
        self.proc_layout.addWidget(self.arrow2)
        
        self.btn_svf = QPushButton(" 3. Calcola Sky View Factor")
        self.btn_svf.setObjectName("PrimaryButton")
        self.btn_svf.setIcon(QgsApplication.getThemeIcon("mActionAlgorithm.svg"))
        self.btn_svf.setToolTip("FASE 3: Calcola SVF dal DSM usando SAGA GIS")
        self.btn_svf.clicked.connect(self.run_svf_calculation)
        self.proc_layout.addWidget(self.btn_svf)
        
        self.scroll_layout.addWidget(self.proc_group)
        
        # 4. Grid Definition
        self.grid_group = QgsCollapsibleGroupBox("4. Definizione Griglia LCZ")
        self.grid_layout = QVBoxLayout(self.grid_group)
        
        self.grid_auto_radio = QRadioButton("Genera griglia automatica")
        self.grid_auto_radio.setChecked(True)
        self.grid_layout.addWidget(self.grid_auto_radio)
        
        self.cell_size_layout = QHBoxLayout()
        self.cell_size_layout.addWidget(QLabel("Dimensione:"))
        self.cell_size_combo = QComboBox()
        self.cell_size_combo.addItems(["30m", "50m", "100m"])
        self.cell_size_combo.setCurrentText("30m")
        self.cell_size_layout.addWidget(self.cell_size_combo)
        self.grid_layout.addLayout(self.cell_size_layout)
        
        self.grid_info_label = QLabel("(Seleziona area per calcolare celle)")
        self.grid_info_label.setStyleSheet("font-size: 10px; color: #95a5a6; font-style: italic;")
        self.grid_layout.addWidget(self.grid_info_label)
        
        self.grid_layer_radio = QRadioButton("Usa layer esistente")
        self.grid_layout.addWidget(self.grid_layer_radio)
        
        self.grid_layer_combo = QgsMapLayerComboBox()
        self.grid_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.grid_layer_combo.setEnabled(False)
        self.grid_layout.addWidget(self.grid_layer_combo)
        
        self.grid_auto_radio.toggled.connect(self.toggle_grid_mode)
        
        self.btn_grid = QPushButton(" Genera/Applica Griglia")
        self.btn_grid.setObjectName("DarkButton")
        self.btn_grid.setIcon(QgsApplication.getThemeIcon("mActionRectangle.svg"))
        self.btn_grid.clicked.connect(self.run_grid_creation)
        self.grid_layout.addWidget(self.btn_grid)
        
        self.scroll_layout.addWidget(self.grid_group)
        
        # 5. LCZ Parameters Calculation
        self.params_group = QgsCollapsibleGroupBox("5. Calcolo Parametri LCZ")
        self.params_layout = QVBoxLayout(self.params_group)
        
        self.params_info_label = QLabel("Calcola parametri LCZ per ogni cella:")
        self.params_info_label.setStyleSheet("font-size: 11px; color: #7f8c8d; font-style: italic;")
        self.params_layout.addWidget(self.params_info_label)
        
        # Grid of 10 atomic buttons
        self.params_grid = QGridLayout()
        self.param_buttons = {}
        
        params = [
            ('sky_view_factor', 'SVF Mean', 'Rapporto tra la porzione di volta celeste visibile dal suolo e una semisfera non ostruita.'),
            ('aspect_ratio', 'Aspect Ratio', 'Rapporto medio altezza-larghezza dei canyon stradali (LCZ 1–7), spaziatura tra edifici (8–10) e alberi (A–G).'),
            ('surface_fractions', 'Surface Frac.', 'Frazioni di copertura: edifici (BSF), superfici impermeabili (ISF) e permeabili (PSF).'),
            ('roughness_elements_height', 'Roughness H', 'Media geometrica dell\'altezza degli edifici (LCZ 1–10) e degli elementi vegetali (LCZ A–F) [m].'),
            ('terrain_roughness_class', 'Terrain Rough.', 'Classificazione della rugosità del terreno (Davenport et al., 2000) per contesti urbani e rurali.'),
            ('surface_admittance', 'S. Admittance', 'Capacità della superficie di assorbire o rilasciare calore [J m⁻² s⁻¹/² K⁻¹].'),
            ('surface_albedo', 'S. Albedo', 'Rapporto tra la radiazione solare riflessa da una superficie e quella ricevuta.'),
            ('anthropogenic_heat_output', 'Anthro. Heat', 'Densità media del flusso di calore annuo da combustione e attività umana [W m⁻²].')
        ]
        
        for i, (pid, name, tip) in enumerate(params):
            btn = QPushButton(name)
            btn.setObjectName("AccentButton")
            btn.setStyleSheet("font-size: 10px; padding: 5px;")
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, p=pid: self.run_specific_lcz_param(p))
            self.params_grid.addWidget(btn, i // 2, i % 2)
            self.param_buttons[pid] = btn
            
        self.params_layout.addLayout(self.params_grid)
        self.scroll_layout.addWidget(self.params_group)
        
        # 6. Final Classification
        self.btn_classify = QPushButton(" Esegui Classificazione Finale")
        self.btn_classify.setObjectName("SuccessButton")
        self.btn_classify.setIcon(QgsApplication.getThemeIcon("mActionCheckHtml.svg"))
        self.btn_classify.setMinimumHeight(40)
        self.scroll_layout.addWidget(self.btn_classify)
        
        # Progress & Log
        self.info_group = QWidget()
        self.info_layout = QVBoxLayout(self.info_group)
        self.info_layout.setContentsMargins(10, 10, 10, 10)
        
        self.status_label = QLabel("Pronto")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.info_layout.addWidget(self.status_label)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                text-align: center;
                background-color: #f1f2f6;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        self.info_layout.addWidget(self.progress)
        
        self.scroll_layout.addStretch()
        self.layout.addWidget(self.info_group)
        
        self.setWidget(self.root)
        
        # Connect to project signals for dynamic UI gating
        QgsProject.instance().layersAdded.connect(self.check_layers_and_update_ui)
        QgsProject.instance().layersRemoved.connect(self.check_layers_and_update_ui)
        
        # Initial validation and gating
        self.validate_aoi_layer()
        self.check_layers_and_update_ui()

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

    def set_dashboard_enabled(self, enabled):
        """Enable or disable the entire plugin UI during background tasks."""
        self.btn_download.setEnabled(enabled)
        self.btn_unify.setEnabled(enabled)
        self.btn_dsm.setEnabled(enabled)
        self.btn_svf.setEnabled(enabled)
        self.btn_grid.setEnabled(enabled)
        self.btn_classify.setEnabled(enabled)
        
        # Disable parameter buttons
        for btn in self.param_buttons.values():
            btn.setEnabled(enabled)
            
        # Disable settings sections
        self.setup_group.setEnabled(enabled)
        self.data_group.setEnabled(enabled)
        self.grid_group.setEnabled(enabled)
        
        if not enabled:
            self.status_label.setText("⚠ Operazione in corso... Attendere")
            self.status_label.setStyleSheet("font-weight: bold; color: #c0392b;")
        else:
            self.status_label.setText("Pronto")
            self.status_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
            # Always check gating state when re-enabling
            self.check_layers_and_update_ui()

    def check_layers_and_update_ui(self, *args):
        """Enable or disable Sections 4, 5 and Classification based on layer presence."""
        # 1. Sequential Processing Dependencies (Section 3)
        has_dtm = bool(QgsProject.instance().mapLayersByName("DTM Tinitaly (10m)"))
        has_dsm = bool(QgsProject.instance().mapLayersByName("DSM Sintetico (10m)"))
        has_svf = bool(QgsProject.instance().mapLayersByName("Sky View Factor (10m)"))
        
        self.btn_dsm.setEnabled(has_dtm)
        self.btn_svf.setEnabled(has_dsm)
        
        # 2. Section 4 (Grid) needs SVF (end of sequential process)
        self.grid_group.setEnabled(has_svf)
        
        # 3. Section 5 needs a Grid layer
        grid_names = ["Griglia LCZ (30m)", "Griglia LCZ (50m)", "Griglia LCZ (100m)", 
                      "Griglia LCZ (custom)", "Griglia LCZ (30m) - Parametri", 
                      "Griglia LCZ (50m) - Parametri", "Griglia LCZ (100m) - Parametri", 
                      "Griglia LCZ (custom) - Parametri"]
        
        has_grid = False
        for name in grid_names:
            if QgsProject.instance().mapLayersByName(name):
                has_grid = True
                break
        
        # Section 5 is enabled if Section 3 is done AND a grid exists
        self.params_group.setEnabled(has_svf and has_grid)
        
        # Classification enabled if grid exists
        self.btn_classify.setEnabled(has_grid)

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

        # Prepare parameters for task
        selected_checks = {name: cb.isChecked() for name, cb in self.checks.items()}
        cdse_user = self.cdse_username.text().strip()
        cdse_pass = self.cdse_password.text()
        
        # Calculate tiles for Tinitaly early to show feedback
        tiles = self.data_manager.calculate_tinitaly_tiles(extent, crs) if selected_checks["Tinitaly (DTM 10m)"] else []
        
        # Disable dashboard
        self.set_dashboard_enabled(False)
        self.status_label.setText("Avvio acquisizione dati in background...")
        self.progress.setValue(0)
        self.progress.setMaximum(0) # Indeterminate at start
        
        # Create and start task
        task = DownloadTask(self.data_manager, selected_checks, extent, crs, cdse_user, cdse_pass, tiles)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress.setMaximum(100)
            self.progress.setValue(100 if success else 0)
            
            if success:
                self.status_label.setText("Processo di download completato.")
                if task.error_count == 0:
                    self.iface.messageBar().pushMessage("FETCH", "Griglia LCZ creata con successo!", level=3)
                else:
                    self.iface.messageBar().pushMessage("IT-LCZ", f"Download completato con {task.error_count} errori. Controlla il log.", level=2)
            else:
                self.status_label.setText(f"Download interrotto o fallito: {task.message}")
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        # Update progress label via background task progress signal if needed, 
        # but for simplicity we'll use the progress bar and status updates in task
        
        QgsApplication.taskManager().addTask(task)

    def run_unification(self):
        """Unifica tutti i dati scaricati in proiezione UTM e ritaglia sull'AOI."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            return
        
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
        
        self.set_dashboard_enabled(False)
        self.status_label.setText("Avvio unificazione dati in corso...")
        self.progress.setMaximum(0)
        
        task = UnifyTask(self.data_manager, extent, crs)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress.setMaximum(100)
            self.progress.setValue(100 if success else 0)
            
            if success:
                self.status_label.setText("Caricamento layer nel progetto...")
                loaded = self.data_manager.load_unified_layers()
                self.status_label.setText(f"Completato: {len(task.output_paths)} dataset unificati, {len(loaded)} layer caricati.")
                self.iface.messageBar().pushMessage("IT-LCZ", "Dati unificati e caricati con successo!", level=3)
            else:
                self.status_label.setText(f"Errore unificazione: {task.message}")
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        QgsApplication.taskManager().addTask(task)

    def run_dsm_generation(self):
        """Genera il DSM sintetico combinando DTM, altezze edifici e altezze alberi."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            return
        
        self.set_dashboard_enabled(False)
        self.status_label.setText("Avvio generazione DSM sintetico...")
        self.progress.setMaximum(0)
        
        task = DSMTask(self.data_manager)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress.setMaximum(100)
            self.progress.setValue(100 if success else 0)
            
            if success and task.output_path:
                self.status_label.setText("Caricamento DSM nel progetto...")
                from qgis.core import QgsRasterLayer
                layer_name = "DSM Sintetico (10m)"
                existing = QgsProject.instance().mapLayersByName(layer_name)
                if not existing:
                    layer = QgsRasterLayer(task.output_path, layer_name)
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        self.status_label.setText("DSM sintetico creato e caricato.")
                        self.iface.messageBar().pushMessage("IT-LCZ", "DSM sintetico generato con successo!", level=3)
                    else:
                        self.status_label.setText("DSM creato ma layer non valido.")
                else:
                    self.status_label.setText("DSM aggiornato.")
                    self.iface.messageBar().pushMessage("IT-LCZ", "DSM generato con successo!", level=3)
            else:
                self.status_label.setText(f"Errore DSM: {task.message}")
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        QgsApplication.taskManager().addTask(task)

    def run_svf_calculation(self):
        """Calcola il Sky View Factor dal DSM usando SAGA GIS."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            return
        
        self.set_dashboard_enabled(False)
        self.status_label.setText("Avvio calcolo Sky View Factor...")
        self.progress.setMaximum(0)
        
        task = SVFTask(self.data_manager)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress.setMaximum(100)
            self.progress.setValue(100 if success else 0)
            
            if success and task.output_path:
                self.status_label.setText("Caricamento SVF nel progetto...")
                from qgis.core import QgsRasterLayer
                layer_name = "Sky View Factor (10m)"
                
                existing = QgsProject.instance().mapLayersByName(layer_name)
                for lyr in existing:
                    QgsProject.instance().removeMapLayer(lyr.id())
                
                layer = QgsRasterLayer(task.output_path, layer_name)
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    self.status_label.setText("Sky View Factor calcolato e caricato.")
                    self.iface.messageBar().pushMessage("IT-LCZ", "SVF calcolato con successo!", level=3)
                else:
                    self.status_label.setText("SVF calcolato ma layer non valido.")
            else:
                self.status_label.setText(f"Errore SVF: {task.message}")
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        QgsApplication.taskManager().addTask(task)

    def toggle_grid_mode(self, auto_checked):
        """Toggle between automatic grid and existing layer mode."""
        self.cell_size_combo.setEnabled(auto_checked)
        self.grid_layer_combo.setEnabled(not auto_checked)
        
        if auto_checked:
            self.btn_grid.setText("Genera Griglia Automatica")
        else:
            self.btn_grid.setText("Applica Layer Esistente")

    def run_grid_creation(self):
        """Create or apply the LCZ grid based on user selection."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            return
        
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
        
        # Prepare parameters
        cell_size = None
        existing_layer = None
        if self.grid_auto_radio.isChecked():
            cell_size_text = self.cell_size_combo.currentText()
            cell_size = int(cell_size_text.replace("m", ""))
        else:
            existing_layer = self.grid_layer_combo.currentLayer()
            if not existing_layer:
                self.iface.messageBar().pushMessage("Errore", "Nessun layer griglia selezionato.", level=2)
                return

        self.set_dashboard_enabled(False)
        self.status_label.setText("Inizializzazione creazione griglia...")
        self.progress.setMaximum(0)
        
        task = GridTask(self.data_manager, extent, crs, cell_size, existing_layer)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress.setMaximum(100)
            self.progress.setValue(100 if success else 0)
            
            if success and task.output_path:
                # Determine layer name
                if cell_size:
                    layer_name = f"Griglia LCZ ({cell_size}m)"
                else:
                    layer_name = "Griglia LCZ (custom)"
                    
                loaded_layer = self.data_manager.load_grid_layer(task.output_path, layer_name=layer_name)
                
                if loaded_layer:
                    self.status_label.setText(f"Griglia creata: {loaded_layer.featureCount()} celle")
                    self.iface.messageBar().pushMessage("IT-LCZ", "Griglia LCZ creata con successo!", level=3)
                else:
                    self.status_label.setText("Griglia creata ma non caricata.")
            else:
                self.status_label.setText(f"Errore griglia: {task.message}")
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        QgsApplication.taskManager().addTask(task)

    def run_specific_lcz_param(self, parameter_id=None):
        """Calculate a specific LCZ parameter for each grid cell in background."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            return
        
        # 1. Scan for valid grid layers
        grid_layer_names = [
            "Griglia LCZ (30m)", "Griglia LCZ (50m)", "Griglia LCZ (100m)", "Griglia LCZ (custom)",
            "Griglia LCZ (30m) - Parametri", "Griglia LCZ (50m) - Parametri", 
            "Griglia LCZ (100m) - Parametri", "Griglia LCZ (custom) - Parametri"
        ]
        
        found_layers = []
        for name in grid_layer_names:
            layers = QgsProject.instance().mapLayersByName(name)
            if layers: found_layers.append(layers[0])
        
        if not found_layers:
            self.iface.messageBar().pushMessage("Errore", "Nessuna griglia LCZ trovata.", level=2)
            return

        # Priority Selection: if there are any " - Parametri" layers, stick to those
        param_layers = [l for l in found_layers if l.name().endswith(" - Parametri")]
        if param_layers:
            found_layers = param_layers
        
        if len(found_layers) == 1:
            selected_layer = found_layers[0]
        else:
            items = [layer.name() for layer in found_layers]
            item, ok = QInputDialog.getItem(self, "Selezione Griglia", "Scegli la griglia:", items, 0, False)
            if ok and item:
                for layer in found_layers:
                    if layer.name() == item: selected_layer = layer; break
            else: return

        grid_path = selected_layer.source()
        
        # Disable dashboard
        self.set_dashboard_enabled(False)
        self.status_label.setText(f"Avvio calcolo {parameter_id}...")
        self.progress.setMaximum(0)
        
        # Create and start task
        task = LCZParameterTask(self.data_manager, grid_path, parameter_id)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress.setMaximum(100)
            self.progress.setValue(100 if success else 0)
            
            if success and task.output_path:
                self.status_label.setText(f"Calcolo {parameter_id} completato.")
                # Update layer
                source_name = selected_layer.name().replace(" - Parametri", "")
                layer_name = f"{source_name} - Parametri"
                existing = QgsProject.instance().mapLayersByName(layer_name)
                if not existing:
                    from qgis.core import QgsVectorLayer
                    layer = QgsVectorLayer(task.output_path, layer_name, "ogr")
                    if layer.isValid(): QgsProject.instance().addMapLayer(layer)
                else:
                    for lyr in existing:
                        lyr.triggerRepaint()
                        if hasattr(lyr, 'dataProvider'): lyr.dataProvider().reloadData()
                
                self.iface.messageBar().pushMessage("IT-LCZ", f"Parametro {parameter_id} calcolato!", level=3)
            else:
                self.status_label.setText(f"Errore: {task.message}")
                self.iface.messageBar().pushMessage("IT-LCZ", f"Errore: {task.message}", level=2)

        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    closingPlugin = pyqtSignal()

class DownloadTask(QgsTask):
    """Task for running all data downloads in the background."""
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

    def run(self):
        def task_log(msg, level=Qgis.Info):
            QgsMessageLog.logMessage(msg, "IT-LCZ", level)

        try:
            total_steps = sum(1 for val in self.selected_checks.values() if val)
            current_step = 0
            
            # 1. Tinitaly
            if self.selected_checks.get("Tinitaly (DTM 10m)"):
                current_step += 1
                if self.isCanceled(): return False
                
                for i, tile in enumerate(self.tiles):
                    if self.isCanceled(): return False
                    task_log(f"Download Tinitaly {i+1}/{len(self.tiles)}: {tile}")
                    success, msg = self.data_manager.download_tinitaly_tile(tile)
                    if not success:
                        task_log(f"Fallimento Tinitaly {tile}: {msg}", Qgis.Critical)
                        self.error_count += 1
                    self.setProgress(int((current_step - 1 + (i+1)/len(self.tiles)) / total_steps * 100))

            # 2. TUM Building Heights
            if self.selected_checks.get("TUM (Edifici H 10m)"):
                current_step += 1
                if self.isCanceled(): return False
                
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
                task_log("Acquisizione ETH Global Canopy Height...")
                self.data_manager.fetch_eth_canopy(self.extent, self.crs)
                self.setProgress(int(current_step / total_steps * 100))

            # 4. ESA WorldCover
            if self.selected_checks.get("ESA WorldCover (Land Use)"):
                current_step += 1
                if self.isCanceled(): return False
                task_log("Acquisizione ESA WorldCover...")
                self.data_manager.fetch_esa_worldcover(self.extent, self.crs)
                self.setProgress(int(current_step / total_steps * 100))

            # 5. Meta HRSL Population
            if self.selected_checks.get("Meta HRSL (Popolazione)"):
                current_step += 1
                if self.isCanceled(): return False
                task_log("Acquisizione Meta HRSL Population...")
                self.data_manager.fetch_meta_hrsl(self.extent, self.crs)
                self.setProgress(int(current_step / total_steps * 100))

            # 6. Sentinel-2 Albedo
            if self.selected_checks.get("S2GM (Albedo Sentinel-2)"):
                current_step += 1
                if self.isCanceled(): return False
                
                if not self.cdse_user or not self.cdse_pass:
                    task_log("Credenziali CDSE mancanti per Albedo.", Qgis.Warning)
                    self.error_count += 1
                else:
                    task_log("Acquisizione Sentinel-2 Albedo (richiede tempo)...")
                    success, msg = self.data_manager.fetch_sentinel2_albedo(
                        self.extent, self.crs, self.cdse_user, self.cdse_pass
                    )
                    if not success:
                        task_log(f"Fallimento Albedo: {msg}", Qgis.Critical)
                        self.error_count += 1
                self.setProgress(int(current_step / total_steps * 100))

            self.success = True
            return True
        except Exception as e:
            self.message = str(e)
            task_log(f"Errore critico durante il download: {self.message}", Qgis.Critical)
            return False

class UnifyTask(QgsTask):
    """Task for unifying and clipping data in the background."""
    def __init__(self, data_manager, extent, crs):
        super().__init__("Unificazione Dati FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.extent = extent
        self.crs = crs
        self.success = False
        self.message = ""
        self.output_paths = []

    def run(self):
        def task_log(msg): QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        try:
            self.success, self.message, self.output_paths = self.data_manager.unify_and_clip_data(
                self.extent, self.crs, log_callback=task_log
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False

class DSMTask(QgsTask):
    """Task for generating synthetic DSM in the background."""
    def __init__(self, data_manager):
        super().__init__("Generazione DSM FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg): QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        try:
            self.success, self.message, self.output_path = self.data_manager.create_synthetic_dsm(
                log_callback=task_log, overwrite=True
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False

class SVFTask(QgsTask):
    """Task for calculating Sky View Factor in the background."""
    def __init__(self, data_manager):
        super().__init__("Calcolo SVF FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg): QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        try:
            # Default params for SVF
            self.success, self.message, self.output_path = self.data_manager.calculate_svf(
                log_callback=task_log, search_radius=100, num_sectors=16
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False

class GridTask(QgsTask):
    """Task for creating the LCZ grid in the background."""
    def __init__(self, data_manager, extent, crs, cell_size=None, existing_layer=None):
        super().__init__("Creazione Griglia FETCH", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.extent = extent
        self.crs = crs
        self.cell_size = cell_size
        self.existing_layer = existing_layer
        self.success = False
        self.message = ""
        self.output_path = ""

    def run(self):
        def task_log(msg): QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)
        try:
            if self.cell_size:
                self.success, self.message, self.output_path = self.data_manager.create_lcz_grid(
                    self.extent, self.crs, cell_size=self.cell_size, log_callback=task_log
                )
            elif self.existing_layer:
                self.success, self.message, self.output_path = self.data_manager.use_existing_grid(
                    self.existing_layer, self.extent, self.crs, log_callback=task_log
                )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False

class LCZParameterTask(QgsTask):
    """Task for running LCZ parameter calculation in the background."""
    def __init__(self, data_manager, grid_path, parameter_id):
        super().__init__(f"Calcolo LCZ: {parameter_id}", QgsTask.CanCancel)
        self.data_manager = data_manager
        self.grid_path = grid_path
        self.parameter_id = parameter_id
        self.success = False
        self.message = ""
        self.output_path = ""
        self.log_msgs = []

    def run(self):
        def task_log(msg):
            self.log_msgs.append(msg)
            QgsMessageLog.logMessage(msg, "IT-LCZ", Qgis.Info)

        try:
            self.success, self.message, self.output_path = self.data_manager.calculate_lcz_parameters(
                grid_path=self.grid_path,
                parameter_id=self.parameter_id,
                log_callback=task_log
            )
            return self.success
        except Exception as e:
            self.message = str(e)
            return False
