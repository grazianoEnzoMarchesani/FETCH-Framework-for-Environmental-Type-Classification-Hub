# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Data Acquisition Section

Section 2: Data source selection and download controls.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, 
    QPushButton, QCheckBox, QLineEdit
)
from qgis.core import QgsApplication
from qgis.gui import QgsCollapsibleGroupBox

from ..constants import DATA_SOURCES


class DataAcquisitionSection(QgsCollapsibleGroupBox):
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
        
        # Sources Grid
        self.sources_grid = QGridLayout()
        self.checks = {}
        
        for i, src in enumerate(DATA_SOURCES):
            cb = QCheckBox(src)
            cb.setChecked(True)
            self.sources_grid.addWidget(cb, i // 2, i % 2)
            self.checks[src] = cb
            
        self.main_layout.addLayout(self.sources_grid)
        
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
        
        self.main_layout.addWidget(self.creds_group)
        
        # Download button
        self.btn_download = QPushButton(" Esegui Download Selezione")
        self.btn_download.setObjectName("DarkButton")
        self.btn_download.setIcon(QgsApplication.getThemeIcon("mActionArrowDown.svg"))
        self.main_layout.addWidget(self.btn_download)
        
    def _connect_signals(self):
        """Connect internal signals."""
        # Link S2GM checkbox to credentials visibility
        self.checks["S2GM (Albedo Sentinel-2)"].toggled.connect(self.creds_group.setVisible)
        # Initial state based on checkbox
        self.creds_group.setVisible(self.checks["S2GM (Albedo Sentinel-2)"].isChecked())
        # Download button
        self.btn_download.clicked.connect(self.download_requested.emit)
        
    def get_selected_sources(self):
        """Get dictionary of selected data sources."""
        return {name: cb.isChecked() for name, cb in self.checks.items()}
        
    def get_cdse_credentials(self):
        """Get CDSE username and password."""
        return self.cdse_username.text().strip(), self.cdse_password.text()
        
    def set_enabled(self, enabled):
        """Enable or disable the section."""
        super().setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
