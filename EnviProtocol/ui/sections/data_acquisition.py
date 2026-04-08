# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - Data Acquisition Section

Section 2: Data source selection and download controls.
Includes secure credential storage using QGIS Auth Manager.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, 
    QPushButton, QCheckBox, QLineEdit
)
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.gui import QgsCollapsibleGroupBox

from ..mixins.help_mixin import HelpMixin
from ..help_content import HELP_DATA_ACQUISITION

from ..constants import DATA_SOURCES




class DataAcquisitionSection(QgsCollapsibleGroupBox, HelpMixin):
    """Section 2: Data Acquisition - source selection and download controls."""
    
    # Signals
    download_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("2. Data Acquisition", parent)
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(10)
        
        # Sources List
        self.sources_container = QWidget()
        self.sources_list_layout = QVBoxLayout(self.sources_container)
        self.sources_list_layout.setContentsMargins(0, 0, 0, 0)
        self.sources_list_layout.setSpacing(0)
        
        self.checks = {}
        for src in DATA_SOURCES:
            row_widget = QWidget()
            row_widget.setObjectName("SourceRow")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(10, 5, 10, 5)
            
            cb = QCheckBox(src)
            cb.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
            cb.setChecked(True)
            row_layout.addWidget(cb)
            
            # Map source name to help key
            key_map = {
                "Tinitaly (DTM 10m)": "tinitaly",
                "TUM (Edifici H 10m)": "tum",
                "ETH (Alberi H 10m)": "eth",
                "ESA WorldCover (Land Use)": "esa",
                "OSM Roads (Vettoriale)": "osm",
                "Copernicus HRL (10m)": "copernicus",
                "Tree Cover Density (Copernicus)": "tcd"
            }
            row_layout.addStretch()
            
            help_key = key_map.get(src)
            if help_key:
                help_btn = self.create_help_button(help_key, HELP_DATA_ACQUISITION)
                row_layout.addWidget(help_btn)
            
            self.sources_list_layout.addWidget(row_widget)
            self.checks[src] = cb
            
        self.main_layout.addWidget(self.sources_container)
        
        # Download button
        self.btn_download = QPushButton(" Esegui Download Selezione")
        self.btn_download.setObjectName("DarkButton")
        self.btn_download.setIcon(QgsApplication.getThemeIcon("mActionArrowDown.svg"))
        self.btn_download.setMinimumHeight(38)
        self.main_layout.addSpacing(5)
        self.main_layout.addWidget(self.btn_download)
        self.main_layout.addSpacing(5)
        
    def _connect_signals(self):
        """Connect internal signals."""
        # Download button
        self.btn_download.clicked.connect(self._on_download_clicked)
    
    def _on_download_clicked(self):
        """Handle download button click."""
        self.download_requested.emit()
        
    def get_selected_sources(self):
        """Get dictionary of selected data sources."""
        return {name: cb.isChecked() for name, cb in self.checks.items()}
        
    def set_enabled(self, enabled):
        """Enable or disable the section."""
        super().setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
