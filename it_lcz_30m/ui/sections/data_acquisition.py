# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Data Acquisition Section

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

from ..constants import DATA_SOURCES

# Unique ID for CDSE credentials in QGIS auth database
CDSE_AUTH_CONFIG_ID = "fetch_cdse_auth"


class DataAcquisitionSection(QgsCollapsibleGroupBox):
    """Section 2: Data Acquisition - source selection and download controls."""
    
    # Signals
    download_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("2. Data Acquisition", parent)
        self._setup_ui()
        self._connect_signals()
        self._load_saved_credentials()
        
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
        
        # Remember credentials row
        creds_actions = QHBoxLayout()
        
        self.remember_checkbox = QCheckBox("Ricorda credenziali")
        self.remember_checkbox.setToolTip("Salva le credenziali in modo cifrato nel database QGIS")
        creds_actions.addWidget(self.remember_checkbox)
        
        self.saved_status = QLabel("")
        self.saved_status.setStyleSheet("font-size: 10px; color: #27ae60; font-weight: bold;")
        creds_actions.addWidget(self.saved_status)
        
        creds_actions.addStretch()
        
        self.btn_clear_creds = QPushButton("Elimina salvate")
        self.btn_clear_creds.setToolTip("Rimuovi le credenziali salvate dal database QGIS")
        self.btn_clear_creds.setStyleSheet("font-size: 10px;")
        self.btn_clear_creds.setFixedWidth(100)
        self.btn_clear_creds.setVisible(False)
        creds_actions.addWidget(self.btn_clear_creds)
        
        self.creds_layout.addLayout(creds_actions, 3, 0, 1, 2)
        
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
        self.btn_download.clicked.connect(self._on_download_clicked)
        # Clear saved credentials
        self.btn_clear_creds.clicked.connect(self._clear_saved_credentials)
        
    def _load_saved_credentials(self):
        """Load credentials from QGIS auth manager if available."""
        try:
            auth_mgr = QgsApplication.authManager()
            
            # First check if our config ID exists to avoid CRITICAL log message
            if CDSE_AUTH_CONFIG_ID not in auth_mgr.configIds():
                # No saved credentials - this is normal, not an error
                return False
            
            # Load existing config
            config = QgsAuthMethodConfig()
            if auth_mgr.loadAuthenticationConfig(CDSE_AUTH_CONFIG_ID, config, True):
                username = config.config("username", "")
                password = config.config("password", "")
                
                if username and password:
                    self.cdse_username.setText(username)
                    self.cdse_password.setText(password)
                    self.remember_checkbox.setChecked(True)
                    self.saved_status.setText("✓ Credenziali salvate")
                    self.btn_clear_creds.setVisible(True)
                    return True
        except Exception:
            # Auth manager may not be initialized in all contexts
            pass
        
        return False
    
    def _save_credentials(self, username, password):
        """Save credentials to QGIS auth manager (encrypted)."""
        try:
            auth_mgr = QgsApplication.authManager()
            
            # Create auth config
            config = QgsAuthMethodConfig("Basic")
            config.setId(CDSE_AUTH_CONFIG_ID)
            config.setName("FETCH CDSE Credentials")
            config.setConfig("username", username)
            config.setConfig("password", password)
            
            # Check if config already exists using configIds (avoids CRITICAL log)
            if CDSE_AUTH_CONFIG_ID in auth_mgr.configIds():
                # Update existing
                auth_mgr.updateAuthenticationConfig(config)
            else:
                # Store new
                auth_mgr.storeAuthenticationConfig(config)
            
            self.saved_status.setText("✓ Credenziali salvate")
            self.btn_clear_creds.setVisible(True)
            return True
            
        except Exception as e:
            self.saved_status.setText(f"✗ Errore: {str(e)[:30]}")
            return False
    
    def _clear_saved_credentials(self):
        """Remove saved credentials from QGIS auth manager."""
        try:
            auth_mgr = QgsApplication.authManager()
            auth_mgr.removeAuthenticationConfig(CDSE_AUTH_CONFIG_ID)
            
            self.cdse_username.clear()
            self.cdse_password.clear()
            self.remember_checkbox.setChecked(False)
            self.saved_status.setText("")
            self.btn_clear_creds.setVisible(False)
            
        except Exception:
            pass
    
    def _on_download_clicked(self):
        """Handle download button click - save credentials if requested."""
        if self.remember_checkbox.isChecked():
            username, password = self.cdse_username.text().strip(), self.cdse_password.text()
            if username and password:
                self._save_credentials(username, password)
        
        self.download_requested.emit()
        
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
