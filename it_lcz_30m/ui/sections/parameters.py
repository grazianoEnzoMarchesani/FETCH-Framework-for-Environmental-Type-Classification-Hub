# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Parameters Section

Section 5: LCZ parameter calculation buttons and indicators.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton
)
from qgis.gui import QgsCollapsibleGroupBox

from ..constants import PARAM_VISUALIZATION, PARAM_DEFINITIONS


class ParametersSection(QgsCollapsibleGroupBox):
    """Section 5: LCZ Parameters - calculation buttons and status indicators."""
    
    # Signals
    parameter_requested = pyqtSignal(str)  # parameter_id
    visualization_requested = pyqtSignal(str)  # field_name
    classify_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("5. Calcolo Parametri LCZ", parent)
        self.param_buttons = {}
        self.indicator_buttons = {}
        self._setup_ui()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        
        # Info label
        self.params_info_label = QLabel("Calcola parametri LCZ per ogni cella:")
        self.params_info_label.setStyleSheet("font-size: 11px; color: #7f8c8d; font-style: italic;")
        self.main_layout.addWidget(self.params_info_label)
        
        # Grid of parameter buttons with indicator dots
        self.params_grid = QGridLayout()
        self.params_grid.setHorizontalSpacing(4)
        
        row = 0
        for i, (pid, name, tip, fields) in enumerate(PARAM_DEFINITIONS):
            col = (i % 2) * 3  # Each param takes 3 columns: button + indicators
            if i > 0 and i % 2 == 0:
                row += 1
            
            # Main parameter button
            btn = QPushButton(name)
            btn.setObjectName("AccentButton")
            btn.setStyleSheet("font-size: 10px; padding: 5px;")
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, p=pid: self.parameter_requested.emit(p))
            self.params_grid.addWidget(btn, row, col)
            self.param_buttons[pid] = btn
            
            # Indicator buttons container
            indicators_widget = QWidget()
            indicators_layout = QHBoxLayout(indicators_widget)
            indicators_layout.setContentsMargins(0, 0, 0, 0)
            indicators_layout.setSpacing(2)
            
            for field in fields:
                indicator = QPushButton()
                indicator.setObjectName("IndicatorButton")
                indicator.setEnabled(False)  # Start disabled
                indicator.setToolTip(f"Visualizza {PARAM_VISUALIZATION.get(field, {}).get('label', field)} sulla mappa")
                indicator.clicked.connect(lambda checked, f=field: self.visualization_requested.emit(f))
                indicators_layout.addWidget(indicator)
                self.indicator_buttons[field] = indicator
            
            indicators_layout.addStretch()
            self.params_grid.addWidget(indicators_widget, row, col + 1)
            
        self.main_layout.addLayout(self.params_grid)
        
        # Classification button
        self.btn_classify = QPushButton(" Esegui Classificazione Finale")
        self.btn_classify.setObjectName("SuccessButton")
        from qgis.core import QgsApplication
        self.btn_classify.setIcon(QgsApplication.getThemeIcon("mActionCheckHtml.svg"))
        self.btn_classify.setMinimumHeight(40)
        self.btn_classify.clicked.connect(self.classify_requested.emit)
        self.main_layout.addWidget(self.btn_classify)
        
    def set_indicator_enabled(self, field_name, enabled):
        """Enable/disable a specific indicator button."""
        if field_name in self.indicator_buttons:
            self.indicator_buttons[field_name].setEnabled(enabled)
            
    def set_all_indicators_disabled(self):
        """Disable all indicator buttons."""
        for btn in self.indicator_buttons.values():
            btn.setEnabled(False)
            
    def set_parameters_enabled(self, enabled):
        """Enable/disable all parameter buttons."""
        for btn in self.param_buttons.values():
            btn.setEnabled(enabled)
            
    def set_classify_enabled(self, enabled):
        """Enable/disable the classification button."""
        self.btn_classify.setEnabled(enabled)
        
    def set_enabled(self, enabled):
        """Enable or disable the entire section."""
        super().setEnabled(enabled)
        if not enabled:
            self.set_all_indicators_disabled()
