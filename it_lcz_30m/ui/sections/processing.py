# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Processing Section

Section 3: Sequential processing steps (Unify, DSM, SVF).
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton
)
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
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(10)
        
        # Pipeline Card
        self.pipeline_card = QWidget()
        self.pipeline_card.setObjectName("ResultsCard")
        self.pipeline_layout = QVBoxLayout(self.pipeline_card)
        self.pipeline_layout.setContentsMargins(0, 5, 0, 5)
        self.pipeline_layout.setSpacing(0)
        
        # Header inside card
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(12, 10, 12, 5)
        lbl_card_title = QLabel("WORKFLOW DI ELABORAZIONE")
        lbl_card_title.setObjectName("ResultsHeader")
        header_layout.addWidget(lbl_card_title)
        self.pipeline_layout.addWidget(header_container)
        
        # Step 1: Unify
        self.row_unify, self.btn_unify, self.ind_unify = self._create_process_row(
            "1", "Unificazione Dati", "Riproiezione UTM e ritaglio AOI", "mActionRelationAdd.svg"
        )
        self.btn_unify.setToolTip("Riproietta tutti i dati scaricati e ritaglia sull'area di studio")
        self.pipeline_layout.addWidget(self.row_unify)
        
        # Step 2: DSM
        self.row_dsm, self.btn_dsm, self.ind_dsm = self._create_process_row(
            "2", "Generazione DSM", "Modello Superficie (Edifici + Alberi)", "mActionHillshade.svg"
        )
        self.btn_dsm.setToolTip("Crea il DSM sintetico sommando DTM e altezze di edifici e vegetazione")
        self.pipeline_layout.addWidget(self.row_dsm)
        
        # Step 3: SVF
        self.row_svf, self.btn_svf, self.ind_svf = self._create_process_row(
            "3", "Calcolo Sky View Factor", "Algoritmo Interno (FETCH Engine)", "mActionAlgorithm.svg"
        )
        self.btn_svf.setToolTip("Calcola la frazione di cielo visibile utilizzando l'algoritmo ottimizzato NumPy")
        self.pipeline_layout.addWidget(self.row_svf)
        
        self.main_layout.addWidget(self.pipeline_card)
        
    def _create_process_row(self, number, title, subtitle, icon_name):
        """Helper to create a professional process row."""
        row = QWidget()
        row.setObjectName("ProcessRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Badge
        lbl_badge = QLabel(number)
        lbl_badge.setObjectName("StepBadge")
        lbl_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_badge)
        
        # Info
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("StepTitle")
        info_layout.addWidget(lbl_title)
        
        lbl_subtitle = QLabel(subtitle)
        lbl_subtitle.setObjectName("StepSubtitle")
        info_layout.addWidget(lbl_subtitle)
        
        layout.addWidget(info_container)
        layout.addStretch()
        
        # Action Button
        btn = QPushButton("ESEGUI")
        btn.setObjectName("CalculateButton")
        btn.setIcon(QgsApplication.getThemeIcon(icon_name))
        btn.setFixedWidth(90)
        layout.addWidget(btn)
        
        # Status Indicator
        indicator = QPushButton()
        indicator.setObjectName("IndicatorButton")
        indicator.setFixedSize(12, 12)  # Slightly smaller than results dots
        indicator.setEnabled(False)
        layout.addWidget(indicator)
        
        return row, btn, indicator

    def _connect_signals(self):
        """Connect button signals."""
        self.btn_unify.clicked.connect(self.unify_requested.emit)
        self.btn_dsm.clicked.connect(self.dsm_requested.emit)
        self.btn_svf.clicked.connect(self.svf_requested.emit)
        
    def set_step_status(self, step_idx, completed):
        """Update step indicator color (1: Unify, 2: DSM, 3: SVF)."""
        indicators = {1: self.ind_unify, 2: self.ind_dsm, 3: self.ind_svf}
        if step_idx in indicators:
            indicators[step_idx].setEnabled(completed)
            
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
