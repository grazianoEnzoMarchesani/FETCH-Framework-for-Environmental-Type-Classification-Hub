# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - ENVI-met Integration Section
Section 3: Geographic to ENVI-met Data Transformation.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame
)
from qgis.core import QgsApplication
from qgis.gui import QgsCollapsibleGroupBox

from ..mixins.help_mixin import HelpMixin

class ENVImetExportSection(QgsCollapsibleGroupBox, HelpMixin):
    """Section 3: ENVI-met Integration - Data transformation controls."""
    
    # Signals
    conversion_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("3. Integrazione ENVI-met", parent)
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(10)
        
        # Info Box
        self.info_frame = QFrame()
        self.info_frame.setObjectName("InfoFrame")
        self.info_frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;")
        self.info_layout = QVBoxLayout(self.info_frame)
        
        info_text = QLabel(
            "Questa sezione permette di trasformare i dati acquisiti (ESA, ETH, TUM, Tinitaly) "
            "in layer vettoriali ottimizzati per l'importazione in ENVI-met (file .inx).\n\n"
            "• Genera la <b>Sub Area</b> (Model Area)\n"
            "• Vettorizza le superfici (ESA WorldCover)\n"
            "• Allinea la topografia (Tinitaly)"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("font-size: 11px; color: #495057;")
        self.info_layout.addWidget(info_text)
        
        self.main_layout.addWidget(self.info_frame)
        
        # Action Buttons
        self.btn_layout = QHBoxLayout()
        
        self.btn_convert = QPushButton(" Prepara Dati per ENVI-met")
        self.btn_convert.setObjectName("DarkButton")
        self.btn_convert.setIcon(QgsApplication.getThemeIcon("mActionCalculateField.svg"))
        self.btn_convert.setMinimumHeight(40)
        
        self.btn_layout.addWidget(self.btn_convert)
        self.main_layout.addLayout(self.btn_layout)
        self.main_layout.addSpacing(5)
        
    def _connect_signals(self):
        """Connect internal signals."""
        self.btn_convert.clicked.connect(self.conversion_requested.emit)
    
    def set_enabled(self, enabled):
        """Toggle section interactive state."""
        self.btn_convert.setEnabled(enabled)
        self.setEnabled(enabled)
