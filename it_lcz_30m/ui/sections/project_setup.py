# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Project Setup Section

Section 1: AOI selection, extent capture, and project info.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, 
    QPushButton, QRadioButton
)
from qgis.core import QgsMapLayerProxyModel, QgsApplication
from qgis.gui import QgsMapLayerComboBox, QgsCollapsibleGroupBox

from ...core.utils import is_within_italy


class ProjectSetupSection(QgsCollapsibleGroupBox):
    """Section 1: Project Setup - AOI selection and extent configuration."""
    
    # Signals
    aoi_changed = pyqtSignal()  # Emitted when AOI selection changes
    extent_captured = pyqtSignal(object, str)  # extent, crs
    
    def __init__(self, iface, parent=None):
        super().__init__("1. Project Setup", parent)
        self.iface = iface
        self.extent_val = None
        self.extent_crs = None
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        
        # AOI Selection Grid
        self.aoi_grid = QGridLayout()
        self.aoi_grid.setContentsMargins(0, 5, 0, 5)
        
        # Vector Layer option
        self.aoi_layer_radio = QRadioButton("Use Vector Layer")
        self.aoi_layer_radio.setChecked(True)
        self.aoi_grid.addWidget(self.aoi_layer_radio, 0, 0)
        
        self.aoi_combo = QgsMapLayerComboBox()
        self.aoi_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.aoi_grid.addWidget(self.aoi_combo, 0, 1)
        
        # Map Canvas Extent option
        self.aoi_extent_radio = QRadioButton("Use Map Canvas Extent")
        self.aoi_grid.addWidget(self.aoi_extent_radio, 1, 0)
        
        self.btn_current_extent = QPushButton("Capture Extent")
        self.btn_current_extent.setObjectName("PrimaryButton")
        self.btn_current_extent.setIcon(QgsApplication.getThemeIcon("mActionSelectExtent.svg"))
        self.btn_current_extent.setEnabled(False)
        self.aoi_grid.addWidget(self.btn_current_extent, 1, 1)
        
        self.main_layout.addLayout(self.aoi_grid)
        
        # Extent display label
        self.extent_label = QLabel("No extent captured")
        self.extent_label.setObjectName("ExtentLabel")
        self.extent_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.extent_label)
        
        # Italy Validation Warning
        self.warning_label = QLabel("⚠ Area fuori dall'Italia. Alcuni dati potrebbero mancare.")
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        self.main_layout.addWidget(self.warning_label)
        
        # Output info
        self.project_label = QLabel("Output: Saving to project directory")
        self.project_label.setStyleSheet("font-size: 11px; color: #7f8c8d; margin-top: 5px;")
        self.main_layout.addWidget(self.project_label)
        
    def _connect_signals(self):
        """Connect internal signals."""
        self.aoi_layer_radio.toggled.connect(self._toggle_aoi_mode)
        self.btn_current_extent.clicked.connect(self._capture_extent)
        self.aoi_combo.layerChanged.connect(self._validate_aoi_layer)
        
    def _toggle_aoi_mode(self, use_layer):
        """Toggle between layer and extent mode."""
        self.aoi_combo.setEnabled(use_layer)
        self.btn_current_extent.setEnabled(not use_layer)
        if use_layer:
            self._validate_aoi_layer()
        else:
            self.warning_label.hide()
        self.aoi_changed.emit()
            
    def _validate_aoi_layer(self):
        """Validate the selected AOI layer."""
        layer = self.aoi_combo.currentLayer()
        if layer:
            within = is_within_italy(layer.extent(), layer.crs().authid())
            self.warning_label.setVisible(not within)
        else:
            self.warning_label.hide()
        self.aoi_changed.emit()
            
    def _capture_extent(self):
        """Capture the current map canvas extent."""
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs().authid()
        self.extent_val = extent
        self.extent_crs = crs
        self.extent_label.setText(f"Captured: {extent.toString(2)} ({crs})")
        within = is_within_italy(extent, crs)
        self.warning_label.setVisible(not within)
        self.extent_captured.emit(extent, crs)
        
    def get_extent_and_crs(self):
        """Get the current AOI extent and CRS."""
        if self.aoi_layer_radio.isChecked():
            layer = self.aoi_combo.currentLayer()
            if layer:
                return layer.extent(), layer.crs().authid()
            return None, None
        else:
            return self.extent_val, self.extent_crs
            
    def is_layer_mode(self):
        """Check if using layer mode."""
        return self.aoi_layer_radio.isChecked()
        
    def get_current_layer(self):
        """Get the currently selected AOI layer."""
        return self.aoi_combo.currentLayer() if self.aoi_layer_radio.isChecked() else None
        
    def set_project_path_status(self, saved, path=""):
        """Update the project path status label."""
        if saved:
            self.project_label.setText("Output: Saving to project directory")
            self.project_label.setStyleSheet("font-size: 11px; color: #7f8c8d; margin-top: 5px;")
        else:
            self.project_label.setText("Output: PROGETTO NON SALVATO")
            self.project_label.setStyleSheet("font-style: italic; color: #c0392b; font-weight: bold;")
