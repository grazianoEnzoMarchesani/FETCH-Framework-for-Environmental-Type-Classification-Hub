# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Main UI Module

This module contains the main ITLCZDashboard class for the FETCH QGIS plugin.
The UI is composed of modular section widgets and mixins for better maintainability.
"""

import os
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QScrollArea, QPushButton
)
from qgis.core import QgsProject, QgsMessageLog, Qgis, QgsApplication

# Local modular imports
from ..core.data_manager import DataManager
from ..core.constants import LayerNames, FileNames
from .styles import STYLESHEET
from .constants import PARAM_VISUALIZATION
from .tasks import (
    DownloadTask, UnifyTask, DSMTask, SVFTask, 
    GridTask, LCZParameterTask, ClassificationTask
)
from .sections import (
    ProjectSetupSection, DataAcquisitionSection, ProcessingSection,
    GridDefinitionSection, ParametersSection, ProgressInfoSection
)
from .widgets.stats_dialog import AdvancedStatsDialog
from .widgets.canvas_legend import CanvasLegend
from ..core.stats_aggregator import StatsAggregator
from .mixins import LayerMixin, StyleMixin
from .tools.training_tool import LCZTrainingTool


class ITLCZDashboard(LayerMixin, StyleMixin, QDockWidget):
    """Main FETCH Dashboard dock widget."""
    
    closingPlugin = pyqtSignal()
    
    def __init__(self, iface, parent=None):
        super(ITLCZDashboard, self).__init__(parent)
        self.iface = iface
        self.data_manager = DataManager(iface)
        self.setWindowTitle("FETCH Dashboard")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Root widget
        self.root = QWidget()
        self.root.setObjectName("DashboardRoot")
        self.root.setStyleSheet(STYLESHEET)
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)
        
        # =====================================================
        # Create Section Widgets
        # =====================================================
        
        # Section 1: Project Setup
        self.setup_section = ProjectSetupSection(iface, self)
        self.scroll_layout.addWidget(self.setup_section)
        
        # Section 2: Data Acquisition
        self.data_section = DataAcquisitionSection(self)
        self.scroll_layout.addWidget(self.data_section)
        
        # Section 3: Processing
        self.proc_section = ProcessingSection(self)
        self.scroll_layout.addWidget(self.proc_section)
        
        # Section 4: Grid Definition
        self.grid_section = GridDefinitionSection(self)
        self.scroll_layout.addWidget(self.grid_section)
        
        # Section 5: Parameters
        self.params_section = ParametersSection(self)
        self.scroll_layout.addWidget(self.params_section)
        
        # Progress & Status
        self.progress_section = ProgressInfoSection(self)
        self.scroll_layout.addStretch()
        self.layout.addWidget(self.progress_section)
        
        # Legend Widget (Floating on Canvas)
        self.canvas_legend = CanvasLegend(self.iface.mapCanvas())
        
        # Phase 2: Training Tool
        self.training_tool = LCZTrainingTool(self.iface, self.data_manager)
        self.previous_tool = None
        
        self.setWidget(self.root)
        
        # =====================================================
        # Connect Section Signals
        # =====================================================
        
        # Data Acquisition
        self.data_section.download_requested.connect(self.run_downloads)
        
        # Processing
        self.proc_section.unify_requested.connect(self.run_unification)
        self.proc_section.dsm_requested.connect(self.run_dsm_generation)
        self.proc_section.svf_requested.connect(self.run_svf_calculation)
        
        # Grid
        self.grid_section.grid_requested.connect(self.run_grid_creation)
        self.grid_section.info_requested.connect(self.refresh_grid_info)
        
        # Connect Setup signals to Grid Info refresh
        self.setup_section.aoi_changed.connect(self.refresh_grid_info)
        self.setup_section.extent_captured.connect(self.refresh_grid_info)
        
        # Parameters
        self.params_section.parameter_requested.connect(self.run_specific_lcz_param)
        self.params_section.visualization_requested.connect(self.apply_param_style)
        self.params_section.classify_requested.connect(self.run_classification)
        self.params_section.stats_requested.connect(self.show_advanced_stats)
        self.params_section.training_mode_requested.connect(self.toggle_training_mode)
        
        # Training Tool signals
        self.training_tool.sampleAdded.connect(self._on_sample_added)
        
        # Project signals for dynamic UI gating
        QgsProject.instance().layersAdded.connect(self.check_layers_and_update_ui)
        QgsProject.instance().layersRemoved.connect(self.check_layers_and_update_ui)
        
        # Connect Map Canvas resize to legend repositioning
        self.iface.mapCanvas().canvasColorChanged.connect(self.canvas_legend._reposition) # Proxy for layout changes
        # Better: use a timer or a specific event if QgsMapCanvas doesn't have a direct resize signal in Python API
        # Actually, QgsMapCanvas is a QWidget, so it has it.
        
        # Initial state
        self.check_layers_and_update_ui()
        self.refresh_grid_info()

    # =========================================================================
    # UI State Management
    # =========================================================================
    
    def set_dashboard_enabled(self, enabled):
        """Enable or disable the entire plugin UI during background tasks."""
        self.data_section.set_enabled(enabled)
        self.proc_section.set_all_enabled(enabled)
        self.grid_section.set_enabled(enabled)
        self.params_section.set_enabled(enabled)
        self.setup_section.setEnabled(enabled)
        
        if not enabled:
            self.progress_section.set_status("⚠ Operazione in corso... Attendere", is_busy=True)
        else:
            self.progress_section.reset()
            self.check_layers_and_update_ui()
            self.refresh_grid_info()

    def refresh_grid_info(self, *args):
        """Update the grid information label based on current AOI and settings."""
        extent, crs = self.setup_section.get_extent_and_crs()
        self.grid_section.update_grid_info(extent, crs)

    def check_layers_and_update_ui(self, *args):
        """Enable or disable Sections 4, 5 and Classification based on layer presence."""
        data_dir = os.path.join(self.data_manager.get_project_dir() or "", self.data_manager.get_data_dir_name())
        
        def has_valid_layer(name):
            layers = QgsProject.instance().mapLayersByName(name)
            for lyr in layers:
                if os.path.normpath(lyr.source()).startswith(os.path.normpath(data_dir)):
                    return True
            return False

        # 1. Sequential Processing Dependencies (Section 3)
        has_dtm = has_valid_layer(LayerNames.DTM)
        has_dsm = has_valid_layer(LayerNames.DSM)
        has_svf = has_valid_layer(LayerNames.SVF)
        
        self.proc_section.set_dsm_enabled(has_dtm)
        self.proc_section.set_svf_enabled(has_dsm)
        
        # 2. Update Processing Section indicators
        self.proc_section.set_step_status(1, has_dtm)  # Unify done if DTM exists
        self.proc_section.set_step_status(2, has_dsm)  # DSM done if DSM exists
        self.proc_section.set_step_status(3, has_svf)  # SVF done if SVF exists
        
        # 3. Section 4 (Grid) needs SVF (end of sequential process)
        self.grid_section.setEnabled(has_svf)
        
        # 3. Section 5 needs a Grid layer
        grid_names = [
            LayerNames.grid_name(30), LayerNames.grid_name(50), LayerNames.grid_name(100),
            LayerNames.GRID_CUSTOM,
            LayerNames.grid_params_name(30), LayerNames.grid_params_name(50),
            LayerNames.grid_params_name(100),
            LayerNames.GRID_CUSTOM + LayerNames.GRID_PARAMS_SUFFIX
        ]
        
        has_grid = any(has_valid_layer(name) for name in grid_names)
        
        # Section 5 is enabled if Section 3 is done AND a grid exists
        self.params_section.setEnabled(has_svf and has_grid)
        
        # Update indicator buttons based on available data
        if has_grid:
            self.update_param_indicators()
        
        # Classification enabled if grid exists
        self.params_section.set_classify_enabled(has_grid)
        
        # Stats enabled if grid exists AND has lcz_class field populated
        has_stats = False
        if has_grid:
            grid_layer = self.find_valid_grid_layer()
            if grid_layer and grid_layer.fields().indexFromName('lcz_class') != -1:
                # Check if at least one feature has a class
                count = grid_layer.featureCount()
                if count > 0:
                    # We assume if the field exists and we ran classification, it's enough to enable the button.
                    # A more thorough check would be to check if any value != NULL/N/D.
                    has_stats = True
        
        self.params_section.set_stats_enabled(has_stats)

    # =========================================================================
    # Task Execution Methods
    # =========================================================================

    def run_downloads(self):
        """Execute data downloads based on user selection."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5
            )
            self.progress_section.set_status("⚠ Salva il progetto prima di continuare", is_error=True)
            self.setup_section.set_project_path_status(False)
            return
            
        extent, crs = self.setup_section.get_extent_and_crs()
        if extent is None:
            if self.setup_section.is_layer_mode():
                self.iface.messageBar().pushMessage("Errore", "Nessun layer AOI selezionato.", level=2)
            else:
                self.iface.messageBar().pushMessage("Errore", "Cattura l'estensione della mappa prima di procedere.", level=2)
            return

        selected_checks = self.data_section.get_selected_sources()
        cdse_user, cdse_pass = self.data_section.get_cdse_credentials()
        tiles = self.data_manager.calculate_tinitaly_tiles(extent, crs) if selected_checks.get("Tinitaly (DTM 10m)") else []
        
        self.set_dashboard_enabled(False)
        self.progress_section.set_status("Avvio acquisizione dati in background...")
        self.progress_section.set_progress(0)
        
        task = DownloadTask(self.data_manager, selected_checks, extent, crs, cdse_user, cdse_pass, tiles)
        
        def on_progress_update(step_name, step_num, total_steps, percent):
            self.progress_section.set_status(f"[{step_num}/{total_steps}] {step_name} ({percent}%)")
            self.progress_section.set_progress(percent)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ Acquisizione dati completata.")
                if task.error_count == 0:
                    self.iface.messageBar().pushMessage("FETCH", "Download dati completato con successo!", level=3)
                else:
                    self.iface.messageBar().pushMessage("IT-LCZ", f"Download completato con {task.error_count} errori. Controlla il log.", level=2)
            else:
                self.progress_section.set_status(f"✗ Download interrotto: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        task.progressUpdated.connect(on_progress_update)
        
        QgsApplication.taskManager().addTask(task)

    def run_unification(self):
        """Unify and clip all downloaded data."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage("Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5)
            return
        
        extent, crs = self.setup_section.get_extent_and_crs()
        if extent is None:
            if self.setup_section.is_layer_mode():
                self.iface.messageBar().pushMessage("Errore", "Nessun layer AOI selezionato.", level=2)
            else:
                self.iface.messageBar().pushMessage("Errore", "Cattura l'estensione della mappa prima di procedere.", level=2)
            return
        
        self.set_dashboard_enabled(False)
        self.progress_section.set_status("Avvio unificazione dati in corso...")
        self.progress_section.set_indeterminate(True)
        
        task = UnifyTask(self.data_manager, extent, crs)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_indeterminate(False)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ Unificazione completata.")
                self.iface.messageBar().pushMessage("FETCH", "Dati unificati con successo!", level=3)
                # Load all unified layers
                self.data_manager.load_unified_layers()
            else:
                self.progress_section.set_status(f"✗ Unificazione fallita: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def run_dsm_generation(self):
        """Generate synthetic DSM."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage("Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5)
            return
            
        self.set_dashboard_enabled(False)
        self.progress_section.set_status("Avvio generazione DSM...")
        self.progress_section.set_indeterminate(True)
        
        data_dir = os.path.join(self.data_manager.get_project_dir(), self.data_manager.get_data_dir_name())
        
        task = DSMTask(self.data_manager)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_indeterminate(False)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ DSM generato con successo.")
                self.iface.messageBar().pushMessage("FETCH", "DSM sintetico generato!", level=3)
                if task.output_path:
                    self._load_raster_layer(task.output_path, LayerNames.DSM)
                    # Create grid if extent available
                    extent, crs = self.setup_section.get_extent_and_crs()
                    if extent:
                        grid_path = os.path.join(data_dir, "griglia_lcz.gpkg")
                        if not os.path.exists(grid_path):
                            self.data_manager.create_lcz_grid(extent, crs, log_callback=lambda m: None)
            else:
                self.progress_section.set_status(f"✗ Generazione DSM fallita: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def run_svf_calculation(self, method='ground'):
        """Calculate Sky View Factor from DSM."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage("Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5)
            return
            
        self.set_dashboard_enabled(False)
        self.progress_section.set_status(f"Avvio calcolo SVF ({method})... (può richiedere tempo)")
        self.progress_section.set_indeterminate(True)
        
        data_dir = os.path.join(self.data_manager.get_project_dir(), self.data_manager.get_data_dir_name())
        
        task = SVFTask(self.data_manager, method=method)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_indeterminate(False)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ SVF calcolato con successo.")
                self.iface.messageBar().pushMessage("FETCH", "Sky View Factor calcolato!", level=3)
                if task.output_path:
                    self._load_raster_layer(task.output_path, LayerNames.SVF)
                    # Create grid if extent available
                    extent, crs = self.setup_section.get_extent_and_crs()
                    if extent:
                        grid_path = os.path.join(data_dir, "griglia_lcz.gpkg")
                        if not os.path.exists(grid_path):
                            self.data_manager.create_lcz_grid(extent, crs, log_callback=lambda m: None)
            else:
                self.progress_section.set_status(f"✗ Calcolo SVF fallito: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def run_grid_creation(self):
        """Create or apply the LCZ grid."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage("Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5)
            return
        
        extent, crs = self.setup_section.get_extent_and_crs()
        if extent is None:
            if self.setup_section.is_layer_mode():
                self.iface.messageBar().pushMessage("Errore", "Nessun layer AOI selezionato.", level=2)
            else:
                self.iface.messageBar().pushMessage("Errore", "Cattura l'estensione della mappa prima di procedere.", level=2)
            return
        
        self.set_dashboard_enabled(False)
        self.progress_section.set_status("Creazione griglia LCZ...")
        self.progress_section.set_indeterminate(True)
        
        data_dir = os.path.join(self.data_manager.get_project_dir(), self.data_manager.get_data_dir_name())
        
        if self.grid_section.is_auto_mode():
            cell_size = self.grid_section.get_cell_size()
            task = GridTask(self.data_manager, extent, crs, cell_size=cell_size)
        else:
            existing_layer = self.grid_section.get_existing_layer()
            if not existing_layer:
                self.iface.messageBar().pushMessage("Errore", "Seleziona un layer esistente.", level=2)
                self.set_dashboard_enabled(True)
                return
            task = GridTask(self.data_manager, extent, crs, existing_layer=existing_layer)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_indeterminate(False)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ Griglia creata con successo.")
                self.iface.messageBar().pushMessage("FETCH", "Griglia LCZ creata!", level=3)
                if task.output_path:
                    if self.grid_section.is_auto_mode():
                        cell_size = self.grid_section.get_cell_size()
                        layer_name = LayerNames.grid_name(cell_size)
                    else:
                        layer_name = LayerNames.GRID_CUSTOM
                    self.data_manager.load_grid_layer(task.output_path, layer_name)
            else:
                self.progress_section.set_status(f"✗ Creazione griglia fallita: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def run_specific_lcz_param(self, parameter_id):
        """Calculate a specific LCZ parameter."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage("Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5)
            return
        
        data_dir = os.path.join(self.data_manager.get_project_dir(), self.data_manager.get_data_dir_name())
        
        grid_layer = self.find_valid_grid_layer()
        if not grid_layer:
            self.iface.messageBar().pushMessage("Errore", "Nessuna griglia LCZ trovata. Creane una prima.", level=2)
            return
            
        grid_path = grid_layer.source()
        
        self.set_dashboard_enabled(False)
        self.progress_section.set_status(f"Calcolo parametro {parameter_id}...")
        self.progress_section.set_indeterminate(True)
        
        task = LCZParameterTask(self.data_manager, grid_path, parameter_id)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_indeterminate(False)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status(f"✓ Parametro {parameter_id} calcolato.")
                self.iface.messageBar().pushMessage("FETCH", f"Parametro {parameter_id} calcolato!", level=3)
                
                if task.output_path:
                    # Determine layer name based on current grid
                    suffix = grid_layer.name().replace("Griglia LCZ ", "").replace(" - Parametri", "")
                    new_name = f"Griglia LCZ {suffix} - Parametri"
                    
                    old_layers = QgsProject.instance().mapLayersByName(grid_layer.name())
                    for old in old_layers:
                        if os.path.normpath(old.source()).startswith(os.path.normpath(data_dir)):
                            QgsProject.instance().removeMapLayer(old.id())
                    
                    self.data_manager.load_grid_layer(task.output_path, new_name)
                    self.update_param_indicators()
            else:
                self.progress_section.set_status(f"✗ Calcolo fallito: {task.message}", is_error=True)
                for msg in task.log_msgs:
                    QgsMessageLog.logMessage(msg, "FETCH", Qgis.Info)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def run_classification(self, method='stable', apply_smoothing=True, is_training=False, veto_count=1, adaptive_calibration=False, profile='z-score'):
        """Run final LCZ classification."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage("Errore", "Salva il progetto QGIS prima di procedere.", level=2, duration=5)
            return
        
        data_dir = os.path.join(self.data_manager.get_project_dir(), self.data_manager.get_data_dir_name())
        
        grid_layer = self.find_valid_grid_layer()
        if not grid_layer:
            self.iface.messageBar().pushMessage("Errore", "Nessuna griglia LCZ trovata.", level=2)
            return
            
        grid_path = grid_layer.source()
        
        # UI label for status message
        method_labels = {
            'stable': "Standard (Stable)",
            'experimental': "Experimental (v2.0)",
            'v3': "Advanced (v3.0)",
            'v4': "Fuzzy Archetype (v4.0)",
            'v5': "Mahalanobis Adaptive (v5.0)",
            'v6': "Weighted Z-Distance (v6.0)",
            'v7': "District-Based RF (v7.0)",
            'v8': "Semantic Expert (v8.0)"
        }
        method_label = method_labels.get(method, method)
        
        self.set_dashboard_enabled(False)
        
        status_msg = f"Avvio classificazione LCZ finale ({method_label})..."
        if method in ('v4', 'v6'):
            veto_display = "Custom" if isinstance(veto_count, dict) else str(veto_count)
            status_msg += f" Veto: {veto_display}"
            
        self.progress_section.set_status(status_msg)
        self.progress_section.set_indeterminate(True)
        
        task = ClassificationTask(self.data_manager, grid_path, method=method, apply_smoothing=apply_smoothing, is_training=is_training, veto_count=veto_count, adaptive_calibration=adaptive_calibration, profile=profile)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_indeterminate(False)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ Classificazione LCZ completata!")
                self.iface.messageBar().pushMessage("FETCH", "Classificazione LCZ completata con successo!", level=3)
                
                # Refresh the layer structure and data
                grid_layer.updateFields()
                grid_layer.triggerRepaint()
                
                # Use reloadData() instead of deprecated forceReload()
                if hasattr(grid_layer, 'dataProvider'):
                    grid_layer.dataProvider().reloadData()
                
                self.iface.mapCanvas().refresh()
                self.update_param_indicators()
            else:
                self.progress_section.set_status(f"✗ Classificazione fallita: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)

    def show_advanced_stats(self):
        """Show the advanced statistics dialog."""
        grid_layer = self.find_valid_grid_layer()
        if not grid_layer:
            self.iface.messageBar().pushMessage("Errore", "Nessun layer di classificazione utile trovato.", level=2)
            return
            
        stats = StatsAggregator.get_layer_stats(grid_layer)
        if not stats or not stats['lcz_counts']:
            self.iface.messageBar().pushMessage("Info", "Nessun dato di classificazione trovato nel layer.", level=3)
            return
            
        dialog = AdvancedStatsDialog(stats, self)
        dialog.exec_()

    def take_high_res_snapshot(self, auto_path=None):
        """Take a high-resolution (300 DPI) snapshot of the map canvas."""
        from qgis.PyQt.QtWidgets import QFileDialog
        from qgis.PyQt.QtGui import QImage, QPainter
        from qgis.PyQt.QtCore import QSize
        from qgis.core import QgsMapSettings, QgsMapRendererCustomPainterJob
        
        if auto_path:
            path = auto_path
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva Snapshot Alta Risoluzione", "snapshot_fetch.png", "PNG Files (*.png)"
            )
        
        if not path:
            return
            
        if not auto_path:
            self.progress_section.set_status("Generazione snapshot HQ...", is_busy=True)
        
        canvas = self.iface.mapCanvas()
        settings = canvas.mapSettings()
        
        # Increase resolution for professional output (300 DPI)
        dpi = 300
        scale_factor = dpi / 96.0 # Standard screen DPI is approx 96
        
        # Adjust size based on target DPI
        size = settings.outputSize()
        new_size = QSize(int(size.width() * scale_factor), int(size.height() * scale_factor))
        settings.setOutputSize(new_size)
        settings.setOutputDpi(dpi)
        
        # Prepare image buffer
        image = QImage(new_size, QImage.Format_ARGB32_Premultiplied)
        image.setDotsPerMeterX(int(dpi / 0.0254))
        image.setDotsPerMeterY(int(dpi / 0.0254))
        image.fill(Qt.transparent)
        
        # Render the map
        painter = QPainter(image)
        job = QgsMapRendererCustomPainterJob(settings, painter)
        job.start()
        job.waitForFinished()
        
        # Draw the legend overlay if visible
        if hasattr(self, 'canvas_legend') and self.canvas_legend.isVisible():
            # Use the specialized method to get the perfect size for HQ content
            full_size = self.canvas_legend.prepare_for_snapshot()
            full_w = full_size.width()
            full_h = full_size.height()
            
            # Calculate position on HQ image (bottom-right)
            margin = int(15 * scale_factor)
            leg_w = int(full_w * scale_factor)
            leg_h = int(full_h * scale_factor)
            
            x = new_size.width() - leg_w - margin
            y = new_size.height() - leg_h - margin
            
            painter.save()
            painter.translate(x, y)
            painter.scale(scale_factor, scale_factor)
            # Render the widget content onto the snapshot painter
            self.canvas_legend.render(painter)
            painter.restore()
            
            # Restore screen-appropriate size
            if hasattr(self.canvas_legend, '_reposition'):
                self.canvas_legend._reposition()
            
        painter.end()
        
        if image.save(path, "PNG"):
            self.iface.messageBar().pushMessage("FETCH", f"Snapshot salvato: {os.path.basename(path)}", level=3)
            self.progress_section.set_status("✓ Snapshot HQ salvato.")
        else:
            self.iface.messageBar().pushMessage("Errore", "Impossibile salvare lo snapshot.", level=2)
            self.progress_section.set_status("✗ Errore salvataggio snapshot.", is_error=True)

    # =========================================================================
    # Phase 2: Training & Iterative Feedback
    # =========================================================================

    def toggle_training_mode(self, enabled):
        """Activates or deactivates the manual training map tool."""
        if enabled:
            # Check if grid exists
            grid = self.find_valid_grid_layer()
            if not grid:
                self.iface.messageBar().pushMessage("Istruzione", "Carica una griglia LCZ prima di addestrare.", level=Qgis.Warning)
                self.params_section.btn_training_mode.setChecked(False)
                return

            self.previous_tool = self.iface.mapCanvas().mapTool()
            self.iface.mapCanvas().setMapTool(self.training_tool)
            self.progress_section.set_status("🎯 Modalità Addestramento Attiva: clicca sulla mappa", is_busy=True)
        else:
            if self.previous_tool:
                self.iface.mapCanvas().setMapTool(self.previous_tool)
            else:
                self.iface.mapCanvas().unsetMapTool(self.training_tool)
            self.progress_section.set_status("✓ Modalità Addestramento Disattivata")
            # Trigger check to update UI indicators if new data changed something
            self.check_layers_and_update_ui()

    def _on_sample_added(self, lcz_id):
        """Handler for when a new training sample is added via map tool."""
        msg = f"Campione LCZ {lcz_id} aggiunto. Riesegui la classificazione v7 per aggiornare la mappa."
        self.progress_section.set_status(f"✨ KB Aggiornata ({lcz_id})")
        # Optimization: we could automatically trigger classification if the user is in "Auto-Retrain" mode.
        # For now, just notifications.
        self.iface.messageBar().pushMessage("Iterative Feedback", msg, level=Qgis.Info, duration=5)

    def closeEvent(self, event):
        """Handle close event."""
        # Ensure tool is deactivated on close
        if self.iface.mapCanvas().mapTool() == self.training_tool:
            self.iface.mapCanvas().unsetMapTool(self.training_tool)
        self.closingPlugin.emit()
        event.accept()
