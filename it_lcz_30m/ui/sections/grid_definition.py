# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Grid Definition Section

Section 4: LCZ Grid creation and configuration.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QRadioButton, QComboBox
)
from qgis.core import QgsMapLayerProxyModel, QgsApplication
from qgis.gui import QgsMapLayerComboBox, QgsCollapsibleGroupBox


class GridDefinitionSection(QgsCollapsibleGroupBox):
    """Section 4: Grid Definition - LCZ grid creation settings."""
    
    # Signals
    grid_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("4. Definizione Griglia LCZ", parent)
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        
        # Auto grid option
        self.grid_auto_radio = QRadioButton("Genera griglia automatica")
        self.grid_auto_radio.setChecked(True)
        self.main_layout.addWidget(self.grid_auto_radio)
        
        # Cell size selection
        self.cell_size_layout = QHBoxLayout()
        self.cell_size_layout.addWidget(QLabel("Dimensione:"))
        self.cell_size_combo = QComboBox()
        self.cell_size_combo.addItems(["30m", "50m", "100m"])
        self.cell_size_combo.setCurrentText("30m")
        self.cell_size_layout.addWidget(self.cell_size_combo)
        self.main_layout.addLayout(self.cell_size_layout)
        
        # Grid info label
        self.grid_info_label = QLabel("(Seleziona area per calcolare celle)")
        self.grid_info_label.setStyleSheet("font-size: 10px; color: #95a5a6; font-style: italic;")
        self.main_layout.addWidget(self.grid_info_label)
        
        # Existing layer option
        self.grid_layer_radio = QRadioButton("Usa layer esistente")
        self.main_layout.addWidget(self.grid_layer_radio)
        
        self.grid_layer_combo = QgsMapLayerComboBox()
        self.grid_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.grid_layer_combo.setEnabled(False)
        self.main_layout.addWidget(self.grid_layer_combo)
        
        # Generate button
        self.btn_grid = QPushButton(" Genera/Applica Griglia")
        self.btn_grid.setObjectName("DarkButton")
        self.btn_grid.setIcon(QgsApplication.getThemeIcon("mActionRectangle.svg"))
        self.main_layout.addWidget(self.btn_grid)
        
    def _connect_signals(self):
        """Connect internal signals."""
        self.grid_auto_radio.toggled.connect(self._toggle_grid_mode)
        self.btn_grid.clicked.connect(self.grid_requested.emit)
        
    def _toggle_grid_mode(self, auto_checked):
        """Toggle between auto and existing layer mode."""
        self.cell_size_combo.setEnabled(auto_checked)
        self.grid_layer_combo.setEnabled(not auto_checked)
        
    def is_auto_mode(self):
        """Check if using automatic grid mode."""
        return self.grid_auto_radio.isChecked()
        
    def get_cell_size(self):
        """Get the selected cell size in meters."""
        text = self.cell_size_combo.currentText()
        return int(text.replace("m", ""))
        
    def get_existing_layer(self):
        """Get the selected existing layer."""
        return self.grid_layer_combo.currentLayer() if not self.is_auto_mode() else None
        
    def set_enabled(self, enabled):
        """Enable or disable the section."""
        super().setEnabled(enabled)
        self.btn_grid.setEnabled(enabled)
