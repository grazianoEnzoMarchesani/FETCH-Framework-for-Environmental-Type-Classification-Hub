# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Processing Section

Section 3: Sequential processing steps (Unify, DSM, SVF).
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QVBoxLayout, QLabel, QPushButton
from qgis.core import QgsApplication
from qgis.gui import QgsCollapsibleGroupBox


class ProcessingSection(QgsCollapsibleGroupBox):
    """Section 3: Sequential Processing - Unify, DSM, SVF steps."""
    
    # Signals
    unify_requested = pyqtSignal()
    dsm_requested = pyqtSignal()
    svf_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("3. Elaborazione Sequenziale", parent)
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(2)
        
        # Step 1: Unify
        self.btn_unify = QPushButton(" 1. Unifica e Ritaglia Dati")
        self.btn_unify.setObjectName("PrimaryButton")
        self.btn_unify.setIcon(QgsApplication.getThemeIcon("mActionRelationAdd.svg"))
        self.btn_unify.setToolTip("FASE 1: Riproietta tutti i dati in UTM e ritaglia sull'AOI")
        self.main_layout.addWidget(self.btn_unify)
        
        # Arrow 1
        self.arrow1 = QLabel("▼")
        self.arrow1.setAlignment(Qt.AlignCenter)
        self.arrow1.setStyleSheet("color: #bdc3c7; font-size: 10px; margin: 2px 0;")
        self.main_layout.addWidget(self.arrow1)
        
        # Step 2: DSM
        self.btn_dsm = QPushButton(" 2. Genera DSM Sintetico")
        self.btn_dsm.setObjectName("PrimaryButton")
        self.btn_dsm.setIcon(QgsApplication.getThemeIcon("mActionHillshade.svg"))
        self.btn_dsm.setToolTip("FASE 2: Crea DSM = DTM + Altezze Edifici + Altezze Alberi")
        self.main_layout.addWidget(self.btn_dsm)
        
        # Arrow 2
        self.arrow2 = QLabel("▼")
        self.arrow2.setAlignment(Qt.AlignCenter)
        self.arrow2.setStyleSheet("color: #bdc3c7; font-size: 10px; margin: 2px 0;")
        self.main_layout.addWidget(self.arrow2)
        
        # Step 3: SVF
        self.btn_svf = QPushButton(" 3. Calcola Sky View Factor")
        self.btn_svf.setObjectName("PrimaryButton")
        self.btn_svf.setIcon(QgsApplication.getThemeIcon("mActionAlgorithm.svg"))
        self.btn_svf.setToolTip("FASE 3: Calcola SVF dal DSM usando SAGA GIS")
        self.main_layout.addWidget(self.btn_svf)
        
    def _connect_signals(self):
        """Connect button signals."""
        self.btn_unify.clicked.connect(self.unify_requested.emit)
        self.btn_dsm.clicked.connect(self.dsm_requested.emit)
        self.btn_svf.clicked.connect(self.svf_requested.emit)
        
    def set_dsm_enabled(self, enabled):
        """Enable/disable DSM button based on dependencies."""
        self.btn_dsm.setEnabled(enabled)
        
    def set_svf_enabled(self, enabled):
        """Enable/disable SVF button based on dependencies."""
        self.btn_svf.setEnabled(enabled)
        
    def set_all_enabled(self, enabled):
        """Enable or disable all buttons."""
        self.btn_unify.setEnabled(enabled)
        self.btn_dsm.setEnabled(enabled)
        self.btn_svf.setEnabled(enabled)
