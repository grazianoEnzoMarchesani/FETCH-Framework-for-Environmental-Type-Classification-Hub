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
            
            self.sources_list_layout.addWidget(row_widget)
            self.checks[src] = cb
            
        self.main_layout.addWidget(self.sources_container)
        
        # CDSE Credentials Card
        self.creds_card = QWidget()
        self.creds_card.setObjectName("CredentialCard")
        self.creds_layout = QVBoxLayout(self.creds_card)
        self.creds_layout.setContentsMargins(15, 12, 15, 12)
        self.creds_layout.setSpacing(8)
        
        # Header for Card
        header_row = QHBoxLayout()
        self.lbl_card_title = QLabel("ACCESSO COPERNICUS (CDSE)")
        self.lbl_card_title.setObjectName("CardHeader")
        header_row.addWidget(self.lbl_card_title)
        
        header_row.addStretch()
        
        self.cdse_link = QLabel('<a href="https://dataspace.copernicus.eu">Registrati</a>')
        self.cdse_link.setObjectName("AuthLink")
        self.cdse_link.setOpenExternalLinks(True)
        header_row.addWidget(self.cdse_link)
        self.creds_layout.addLayout(header_row)
        
        # Form
        form_layout = QGridLayout()
        form_layout.setSpacing(5)
        
        lbl_user = QLabel("Email:")
        lbl_user.setStyleSheet("font-size: 10px; color: #7f8c8d;")
        self.cdse_username = QLineEdit()
        self.cdse_username.setPlaceholderText("email@copernicus.eu")
        form_layout.addWidget(lbl_user, 0, 0)
        form_layout.addWidget(self.cdse_username, 0, 1)
        
        lbl_pass = QLabel("Password:")
        lbl_pass.setStyleSheet("font-size: 10px; color: #7f8c8d;")
        self.cdse_password = QLineEdit()
        self.cdse_password.setEchoMode(QLineEdit.Password)
        self.cdse_password.setPlaceholderText("••••••••")
        form_layout.addWidget(lbl_pass, 1, 0)
        form_layout.addWidget(self.cdse_password, 1, 1)
        
        self.creds_layout.addLayout(form_layout)
        
        # Creds Actions
        actions_row = QHBoxLayout()
        self.remember_checkbox = QCheckBox("Ricorda")
        self.remember_checkbox.setStyleSheet("font-size: 10px; color: #34495e;")
        actions_row.addWidget(self.remember_checkbox)
        
        self.saved_status = QLabel("")
        self.saved_status.setObjectName("StatusText")
        self.saved_status.setStyleSheet("color: #27ae60;") # Success green
        actions_row.addWidget(self.saved_status)
        
        actions_row.addStretch()
        
        self.btn_clear_creds = QPushButton("Elimina")
        self.btn_clear_creds.setObjectName("CalculateButton") # Use small button style
        self.btn_clear_creds.setFixedWidth(60)
        self.btn_clear_creds.setVisible(False)
        actions_row.addWidget(self.btn_clear_creds)
        
        self.creds_layout.addLayout(actions_row)
        
        self.main_layout.addWidget(self.creds_card)
        self.creds_group = self.creds_card # Keep alias for visibility toggle
        
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
