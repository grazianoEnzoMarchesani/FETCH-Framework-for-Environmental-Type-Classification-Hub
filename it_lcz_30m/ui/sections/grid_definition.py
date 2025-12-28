# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Grid Definition Section

Section 4: LCZ Grid creation and configuration.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QRadioButton, QComboBox, QButtonGroup
)
from qgis.core import QgsMapLayerProxyModel, QgsApplication
from qgis.gui import QgsMapLayerComboBox, QgsCollapsibleGroupBox


from ..mixins.help_mixin import HelpMixin
from ..help_content import HELP_GRID_DEFINITION


class GridDefinitionSection(QgsCollapsibleGroupBox, HelpMixin):
    """Section 4: Grid Definition - LCZ grid creation settings."""
    
    # Signals
    grid_requested = pyqtSignal()
    info_requested = pyqtSignal()  # Request an AOI refresh from dashboard
    
    def __init__(self, parent=None):
        super().__init__("4. Definizione Griglia LCZ", parent)
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(10)
        
        # Mode Selection Group
        self.grid_group = QButtonGroup(self)
        
        self.selection_container = QWidget()
        self.selection_layout = QVBoxLayout(self.selection_container)
        self.selection_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_layout.setSpacing(0)
        
        # Row 1: Auto Grid
        self.row_auto = QWidget()
        self.row_auto.setObjectName("SourceRow")
        layout_auto = QHBoxLayout(self.row_auto)
        layout_auto.setContentsMargins(10, 5, 10, 5)
        
        self.grid_auto_radio = QRadioButton("Genera griglia automatica")
        self.grid_auto_radio.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
        self.grid_auto_radio.setChecked(True)
        self.grid_group.addButton(self.grid_auto_radio)
        layout_auto.addWidget(self.grid_auto_radio)
        
        # Help auto
        help_auto = self.create_help_button("automatic_grid", HELP_GRID_DEFINITION)
        layout_auto.addWidget(help_auto)
        
        layout_auto.addStretch()
        
        # Cell size selection
        lbl_size = QLabel("Dim:")
        lbl_size.setStyleSheet("font-size: 10px; color: #7f8c8d;")
        layout_auto.addWidget(lbl_size)
        
        self.cell_size_combo = QComboBox()
        self.cell_size_combo.addItems(["30m", "50m", "100m"])
        self.cell_size_combo.setCurrentText("30m")
        self.cell_size_combo.setFixedWidth(70)
        layout_auto.addWidget(self.cell_size_combo)
        
        self.selection_layout.addWidget(self.row_auto)
        
        # Row 2: Existing Layer
        self.row_layer = QWidget()
        self.row_layer.setObjectName("SourceRow")
        layout_layer = QHBoxLayout(self.row_layer)
        layout_layer.setContentsMargins(10, 5, 10, 5)
        
        self.grid_layer_radio = QRadioButton("Usa layer esistente")
        self.grid_layer_radio.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
        self.grid_group.addButton(self.grid_layer_radio)
        layout_layer.addWidget(self.grid_layer_radio)
        
        # Help existing
        help_exist = self.create_help_button("existing_layer", HELP_GRID_DEFINITION)
        layout_layer.addWidget(help_exist)
        
        layout_layer.addStretch()
        
        self.grid_layer_combo = QgsMapLayerComboBox()
        self.grid_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.grid_layer_combo.setEnabled(False)
        self.grid_layer_combo.setFixedWidth(150)
        layout_layer.addWidget(self.grid_layer_combo)
        
        self.selection_layout.addWidget(self.row_layer)
        
        self.main_layout.addWidget(self.selection_container)
        
        # Info Card
        self.info_card = QWidget()
        self.info_card.setObjectName("ResultsCard")
        self.info_layout = QVBoxLayout(self.info_card)
        self.info_layout.setContentsMargins(12, 10, 12, 10)
        self.info_layout.setSpacing(5)
        
        lbl_card_title = QLabel("INFORMAZIONI GRIGLIA")
        lbl_card_title.setObjectName("ResultsHeader")
        self.info_layout.addWidget(lbl_card_title)
        
        self.grid_info_label = QLabel("(Seleziona area per calcolare celle)")
        self.grid_info_label.setObjectName("ExtentLabel") # Consistent with other sections
        self.grid_info_label.setWordWrap(True)
        self.info_layout.addWidget(self.grid_info_label)
        
        self.main_layout.addWidget(self.info_card)
        
        # Generate button
        self.btn_grid = QPushButton(" Genera/Applica Griglia")
        self.btn_grid.setObjectName("DarkButton")
        self.btn_grid.setIcon(QgsApplication.getThemeIcon("mActionRectangle.svg"))
        self.btn_grid.setMinimumHeight(38)
        self.main_layout.addSpacing(5)
        self.main_layout.addWidget(self.btn_grid)
        self.main_layout.addSpacing(5)
        
    def _connect_signals(self):
        """Connect internal signals."""
        self.grid_auto_radio.toggled.connect(self._toggle_grid_mode)
        self.btn_grid.clicked.connect(self.grid_requested.emit)
        self.cell_size_combo.currentIndexChanged.connect(self.info_requested.emit)
        self.grid_layer_radio.toggled.connect(self.info_requested.emit)
        self.grid_layer_combo.layerChanged.connect(self.info_requested.emit)
        
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

    def update_grid_info(self, extent, crs_authid):
        """
        Calculate and display estimated number of cells.
        
        Args:
            extent: QgsRectangle of the AOI
            crs_authid: CRS of the AOI
        """
        if not extent or extent.isEmpty():
            self.grid_info_label.setText("(Seleziona area per calcolare celle)")
            return

        if not self.is_auto_mode():
            layer = self.grid_layer_combo.currentLayer()
            if layer:
                count = layer.featureCount()
                self.grid_info_label.setText(f"Griglia esistente: {count:,} celle rilevate.")
            else:
                self.grid_info_label.setText("(Seleziona un layer griglia)")
            return

        # Calculate for auto mode
        size = self.get_cell_size()
        width = extent.width()
        height = extent.height()
        
        cols = int(width / size)
        rows = int(height / size)
        total = cols * rows
        
        if total > 0:
            self.grid_info_label.setText(
                f"Griglia stimata: ~{total:,} celle\n"
                f"Dimensioni: {cols} x {rows} (Cella {size}m)"
            )
        else:
            self.grid_info_label.setText("(Area troppo piccola per questa dimensione)")

