# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - Main UI Module

This module contains the main EnviProtocolDashboard class for the EnviProtocol QGIS plugin.
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
from .tasks import (
    DownloadTask
)
from .sections import (
    ProjectSetupSection, DataAcquisitionSection,
    ENVImetExportSection, ProgressInfoSection
)

from .mixins import LayerMixin



class EnviProtocolDashboard(LayerMixin, QDockWidget):
    """Main EnviProtocol Dashboard dock widget."""
    
    closingPlugin = pyqtSignal()
    
    def __init__(self, iface, parent=None):
        super(EnviProtocolDashboard, self).__init__(parent)
        self.iface = iface
        self.data_manager = DataManager(iface)
        self.setWindowTitle("EnviProtocol Dashboard")
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
        
        # Section 3: ENVI-met Integration
        self.envimet_section = ENVImetExportSection(self)
        self.scroll_layout.addWidget(self.envimet_section)
        
        

        
        # Progress & Status
        self.progress_section = ProgressInfoSection(self)
        self.scroll_layout.addStretch()
        self.layout.addWidget(self.progress_section)
        

        
        self.setWidget(self.root)
        
        # =====================================================
        # Connect Section Signals
        # Section 2: Data Acquisition
        self.data_section.download_requested.connect(self.run_downloads)
        
        # ENVI-met Integration
        self.envimet_section.conversion_requested.connect(self.run_envimet_prep)
        
        

        
        # Project signals for dynamic UI gating
        QgsProject.instance().layersAdded.connect(self.check_layers_and_update_ui)
        QgsProject.instance().layersRemoved.connect(self.check_layers_and_update_ui)
        

        
        # Initial state
        self.check_layers_and_update_ui()

    # =========================================================================
    # UI State Management
    # =========================================================================
    
    def set_dashboard_enabled(self, enabled):
        """Enable or disable the entire plugin UI during background tasks."""
        self.data_section.set_enabled(enabled)
        self.envimet_section.set_enabled(enabled)
        self.setup_section.setEnabled(enabled)
        
        if not enabled:
            self.progress_section.set_status("⚠ Operazione in corso... Attendere", is_busy=True)
        else:
            self.progress_section.reset()
            self.check_layers_and_update_ui()

    def check_layers_and_update_ui(self, *args):
        """Enable or disable processing steps based on layer presence."""
        pass


    # =========================================================================
    # Task Execution Methods
    # =========================================================================

    def run_downloads(self):
        """Execute data downloads based on user selection."""
        project_path = QgsProject.instance().fileName()
        if not project_path:
            self.iface.messageBar().pushMessage(
                "Errore", "Salva il progetto QGIS prima di procedere.", level=Qgis.Warning, duration=5
            )
            self.progress_section.set_status("⚠ Salva il progetto prima di continuare", is_error=True)
            self.setup_section.set_project_path_status(False)
            return
            
        extent, crs = self.setup_section.get_extent_and_crs()
        if extent is None or extent.isEmpty():
            self.iface.messageBar().pushMessage("EnviProtocol", "Manca l'Area di Studio (AOI). Vai in 'Project Setup' e clicca su 'Capture'!", level=Qgis.Warning)
            self.progress_section.set_status("⚠ Area di Studio non definita", is_error=True)
            return

        selected_checks = self.data_section.get_selected_sources()
        total_steps = sum(1 for val in selected_checks.values() if val)
        
        if total_steps == 0:
            self.iface.messageBar().pushMessage("EnviProtocol", "Seleziona almeno una sorgente dati (es. Tinitaly) nella sezione 'Data Acquisition'.", level=Qgis.Info)
            self.progress_section.set_status("⚠ Nessun dato selezionato", is_error=True)
            return

        tiles = self.data_manager.calculate_tinitaly_tiles(extent, crs) if selected_checks.get("Tinitaly (DTM 10m)") else []
        
        self.set_dashboard_enabled(False)
        self.progress_section.set_status("Avvio acquisizione dati in background...")
        self.progress_section.set_progress(0)
        
        task = DownloadTask(self.data_manager, selected_checks, extent, crs, tiles)
        
        def on_progress_update(step_name, step_num, total_steps, percent):
            self.progress_section.set_status(f"[{step_num}/{total_steps}] {step_name} ({percent}%)")
            self.progress_section.set_progress(percent)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            self.progress_section.set_progress(100 if success else 0)
            
            if success:
                self.progress_section.set_status("✓ Acquisizione dati completata.")
                if task.error_count == 0:
                    self.iface.messageBar().pushMessage("EnviProtocol", "Download dati completato con successo!", level=Qgis.Success)
                else:
                    self.iface.messageBar().pushMessage("EnviProtocol", f"Download completato con {task.error_count} errori. Controlla il log.", level=Qgis.Warning)
            else:
                self.progress_section.set_status(f"✗ Download interrotto: {task.message}", is_error=True)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        task.progressUpdated.connect(on_progress_update)
        
        QgsApplication.taskManager().addTask(task)


    def run_envimet_prep(self):
        """Execute the ENVI-met data preparation task."""
        extent, crs = self.setup_section.get_extent_and_crs()
        if extent is None:
            self.iface.messageBar().pushMessage("Errore", "Definisci l'AOI prima di procedere.", level=Qgis.Warning)
            return

        self.set_dashboard_enabled(False)
        self.progress_section.set_status("Preparazione dati ENVI-met in corso...")
        self.progress_section.set_progress(0)
        
        # NOTE: ENVImetTask will be implemented in the next step
        from .tasks import ENVImetTask
        task = ENVImetTask(self.data_manager, extent, crs)
        
        def on_finished(success):
            self.set_dashboard_enabled(True)
            if success:
                self.progress_section.set_status("✓ Dati ENVI-met pronti (cartella envimet_export).")
                self.iface.messageBar().pushMessage("EnviProtocol", "Dati pronti per ENVI-met!", level=Qgis.Success)
            else:
                msg = getattr(task, 'message', 'Errore sconosciuto')
                self.progress_section.set_status(f"✗ Errore: {msg}", is_error=True)
                self.iface.messageBar().pushMessage("Errore ENVI-met", msg, level=Qgis.Critical)
        
        task.taskCompleted.connect(lambda: on_finished(True))
        task.taskTerminated.connect(lambda: on_finished(False))
        
        QgsApplication.taskManager().addTask(task)
