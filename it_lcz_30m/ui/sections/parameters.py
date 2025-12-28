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
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(0)
        
        # Info label
        self.params_info_label = QLabel("Calcola parametri LCZ per ogni cella:")
        self.params_info_label.setStyleSheet("font-size: 11px; color: #7f8c8d; font-style: italic; margin-bottom: 5px;")
        self.main_layout.addWidget(self.params_info_label)
        
        # Container for the list of parameters
        self.params_container = QWidget()
        self.params_list_layout = QVBoxLayout(self.params_container)
        self.params_list_layout.setContentsMargins(0, 0, 0, 0)
        self.params_list_layout.setSpacing(0)
        
        for pid, name, tip, fields in PARAM_DEFINITIONS:
            row_widget = QWidget()
            row_widget.setObjectName("ParamRow")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(10, 8, 10, 8)
            
            # Label
            lbl = QLabel(name)
            lbl.setWordWrap(True)  # Allow name to wrap in narrow panels
            lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #2c3e50;")
            lbl.setToolTip(tip)
            row_layout.addWidget(lbl)
            
            row_layout.addStretch()
            
            # Calculate Button
            btn = QPushButton("Calcola")
            btn.setObjectName("CalculateButton")
            btn.setFixedWidth(80)  # Align buttons by giving them a fixed width
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, p=pid: self.parameter_requested.emit(p))
            row_layout.addWidget(btn)
            self.param_buttons[pid] = btn
            
            # Indicators Container (Fixed width to align buttons)
            indicators_area = QWidget()
            indicators_area.setFixedWidth(75)  # Space for 3 dots + spacing
            indicators_layout = QHBoxLayout(indicators_area)
            indicators_layout.setContentsMargins(5, 0, 0, 0)
            indicators_layout.setSpacing(4)
            
            for field in fields:
                indicator = QPushButton()
                indicator.setObjectName("VisualButton")
                indicator.setFixedSize(18, 18)
                indicator.setEnabled(False)
                indicator.setToolTip(f"Visualizza {PARAM_VISUALIZATION.get(field, {}).get('label', field)} sulla mappa")
                indicator.clicked.connect(lambda checked, f=field: self.visualization_requested.emit(f))
                indicators_layout.addWidget(indicator)
                self.indicator_buttons[field] = indicator
            
            indicators_layout.addStretch()
            row_layout.addWidget(indicators_area)
            
            self.params_list_layout.addWidget(row_widget)
            
        self.main_layout.addWidget(self.params_container)
        self.main_layout.addSpacing(10)
        
        # Classification Results Visualization (footer grid for better responsiveness)
        self.results_card = QWidget()
        self.results_card.setObjectName("ResultsCard")
        self.results_grid = QGridLayout(self.results_card)
        self.results_grid.setContentsMargins(12, 12, 12, 12)
        self.results_grid.setHorizontalSpacing(15)
        self.results_grid.setVerticalSpacing(10)
        
        self.lbl_results_header = QLabel("Visualizza Risultati Classificazione:")
        self.lbl_results_header.setObjectName("ResultsHeader")
        self.results_grid.addWidget(self.lbl_results_header, 0, 0, 1, 2)
        
        # Helper nested function to create result items with indicators on the right (consistent with top list)
        def add_result_item(field, label, tooltip, row, col, span=1):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(10)
            
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #34495e;")
            layout.addWidget(lbl)
            
            layout.addStretch()
            
            # Indicator Dot (same style as above)
            btn = QPushButton()
            btn.setObjectName("VisualButton")
            btn.setFixedSize(18, 18)
            btn.setEnabled(False)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda: self.visualization_requested.emit(field))
            layout.addWidget(btn)
            
            self.results_grid.addWidget(container, row, col, 1, span)
            self.indicator_buttons[field] = btn
            return btn

        # Row 1
        self.ind_lcz = add_result_item('lcz_class', "LCZ", "Visualizza Classi LCZ", 1, 0)
        self.ind_rmsep = add_result_item('lcz_rmsep', "ERRORE", "Visualizza Errore (RMSEP)", 1, 1)
        
        # Row 2
        self.ind_matches = add_result_item('lcz_matches', "MATCH", "Visualizza Corrispondenze", 2, 0)
        self.ind_esa = add_result_item('lcz_esa_fix', "FIX ESA", "Visualizza Rettifica ESA", 2, 1)
        
        # Row 3 (Full width for longer label)
        self.ind_vuln = add_result_item('lcz_vulnerability', "VULNERABILITÀ", "Visualizza Vulnerabilità", 3, 0, 2)
        
        self.main_layout.addWidget(self.results_card)
        self.main_layout.addSpacing(10)
        
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
