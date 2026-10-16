# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Project Setup Section

Section 1: AOI selection, extent capture, and project info.
Includes automatic boundary layer creation on extent capture for OSM compatibility.
"""

import os
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, 
    QPushButton, QRadioButton, QButtonGroup, QLineEdit
)
from qgis.core import (
    QgsMapLayerProxyModel, QgsApplication, QgsProject,
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField,
    QgsVectorFileWriter, QgsFields, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsSimpleFillSymbolLayer,
    QgsSymbol, QgsSingleSymbolRenderer, QgsFeatureRequest
)
from qgis.PyQt.QtCore import QVariant, QMetaType
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapLayerComboBox, QgsCollapsibleGroupBox

from ...core.utils import is_within_italy, get_target_crs_for_extent
from ...core.istat import BOUNDARY_LAYER_NAME
from ..mixins.help_mixin import HelpMixin
from ..help_content import HELP_PROJECT_SETUP


class ProjectSetupSection(QgsCollapsibleGroupBox, HelpMixin):
    """Section 1: Project Setup - AOI selection and extent configuration."""
    
    WARN_OUTSIDE_ITALY = "⚠ Area fuori dall'Italia. Alcuni dati potrebbero mancare."

    # Signals
    aoi_changed = pyqtSignal()  # Emitted when AOI selection changes
    extent_captured = pyqtSignal(object, str)  # extent, crs
    city_requested = pyqtSignal(str)  # raw "Comune (SIGLA); ..." text
    
    def __init__(self, iface, parent=None):
        super().__init__("1. Configurazione Progetto", parent)
        self.iface = iface
        self.extent_val = None
        self.extent_crs = None
        self.boundary_layer_path = None  # Path to generated boundary layer
        self.city_layer_id = None  # ISTAT municipalities layer in the project (city mode)
        self.city_info = ""
        self._setup_ui()
        self._connect_signals()
        QgsProject.instance().readProject.connect(self._restore_city_state)
        self._restore_city_state()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(10)
        
        # AOI Mode Selection (Grouped for mutual exclusivity)
        self.aoi_group = QButtonGroup(self)
        
        self.selection_container = QWidget()
        self.selection_layout = QVBoxLayout(self.selection_container)
        self.selection_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_layout.setSpacing(0)
        
        # Row 1: Vector Layer
        self.row_layer = QWidget()
        self.row_layer.setObjectName("SourceRow")
        layout_layer = QHBoxLayout(self.row_layer)
        layout_layer.setContentsMargins(10, 5, 10, 5)
        
        self.aoi_layer_radio = QRadioButton("Usa Layer Vettoriale (AOI)")
        self.aoi_layer_radio.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
        self.aoi_layer_radio.setChecked(True)
        self.aoi_group.addButton(self.aoi_layer_radio)
        layout_layer.addWidget(self.aoi_layer_radio)
        
        layout_layer.addStretch()
        
        self.aoi_combo = QgsMapLayerComboBox()
        self.aoi_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.aoi_combo.setFixedWidth(180)
        layout_layer.addWidget(self.aoi_combo)
        
        # Add Help
        help_aoi = self.create_help_button("aoi_layer", HELP_PROJECT_SETUP)
        layout_layer.addWidget(help_aoi)
        
        self.selection_layout.addWidget(self.row_layer)
        
        # Row 2: Map Canvas Extent
        self.row_extent = QWidget()
        self.row_extent.setObjectName("SourceRow")
        layout_extent = QHBoxLayout(self.row_extent)
        layout_extent.setContentsMargins(10, 5, 10, 5)
        
        self.aoi_extent_radio = QRadioButton("Usa Estensione Mappa")
        self.aoi_extent_radio.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
        self.aoi_group.addButton(self.aoi_extent_radio)
        layout_extent.addWidget(self.aoi_extent_radio)
        
        layout_extent.addStretch()
        
        self.btn_current_extent = QPushButton("Cattura")
        self.btn_current_extent.setObjectName("PrimaryButton")
        self.btn_current_extent.setFixedWidth(100)
        self.btn_current_extent.setIcon(QgsApplication.getThemeIcon("mActionSelectExtent.svg"))
        self.btn_current_extent.setEnabled(False)
        layout_extent.addWidget(self.btn_current_extent)
        
        # Add Help
        help_extent = self.create_help_button("capture_extent", HELP_PROJECT_SETUP)
        layout_extent.addWidget(help_extent)
        
        self.selection_layout.addWidget(self.row_extent)
        
        # Row 3: Italian cities (ISTAT boundaries)
        self.row_city = QWidget()
        self.row_city.setObjectName("SourceRow")
        layout_city = QVBoxLayout(self.row_city)
        layout_city.setContentsMargins(10, 5, 10, 5)
        layout_city.setSpacing(4)
        
        layout_city_top = QHBoxLayout()
        self.aoi_city_radio = QRadioButton("Usa Città (confini ISTAT)")
        self.aoi_city_radio.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
        self.aoi_group.addButton(self.aoi_city_radio)
        layout_city_top.addWidget(self.aoi_city_radio)
        layout_city_top.addStretch()
        
        help_city = self.create_help_button("city", HELP_PROJECT_SETUP)
        layout_city_top.addWidget(help_city)
        
        self.btn_city = QPushButton("Carica")
        self.btn_city.setObjectName("PrimaryButton")
        self.btn_city.setFixedWidth(100)
        self.btn_city.setIcon(QgsApplication.getThemeIcon("mActionAddPolygon.svg"))
        self.btn_city.setEnabled(False)
        layout_city_top.addWidget(self.btn_city)
        layout_city.addLayout(layout_city_top)
        
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Camerino (MC); Macerata (MC)")
        self.city_input.setToolTip("Comune (SIGLA provincia), separati da ';'. La sigla serve a evitare gli omonimi.")
        self.city_input.setEnabled(False)
        layout_city.addWidget(self.city_input)
        
        lbl_city_hint = QLabel("Formato: Nome (SIGLA). Più città separate da  ;")
        lbl_city_hint.setStyleSheet("font-size: 10px; color: #7f8c8d;")
        layout_city.addWidget(lbl_city_hint)
        
        self.selection_layout.addWidget(self.row_city)
        
        self.main_layout.addWidget(self.selection_container)
        
        # Area Details Card
        self.details_card = QWidget()
        self.details_card.setObjectName("ResultsCard")
        self.details_layout = QVBoxLayout(self.details_card)
        self.details_layout.setContentsMargins(12, 10, 12, 10)
        self.details_layout.setSpacing(8)
        
        self.lbl_card_title = QLabel("DETTAGLI AREA SELEZIONATA")
        self.lbl_card_title.setObjectName("ResultsHeader")
        self.details_layout.addWidget(self.lbl_card_title)
        
        self.extent_label = QLabel("Nessun dato catturato")
        self.extent_label.setObjectName("ExtentLabel")
        self.extent_label.setWordWrap(True)
        self.details_layout.addWidget(self.extent_label)
        
        # Warning (inside card)
        self.warning_label = QLabel(self.WARN_OUTSIDE_ITALY)
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        self.details_layout.addWidget(self.warning_label)
        
        self.main_layout.addWidget(self.details_card)
        
        # Output info
        self.project_label = QLabel("Progetto: Salvataggio in cartella locale")
        self.project_label.setStyleSheet("font-size: 10px; color: #7f8c8d; margin-left: 5px;")
        self.main_layout.addWidget(self.project_label)
        
    def _connect_signals(self):
        """Connect internal signals."""
        self.aoi_layer_radio.toggled.connect(self._update_mode)
        self.aoi_extent_radio.toggled.connect(self._update_mode)
        self.aoi_city_radio.toggled.connect(self._update_mode)
        self.btn_current_extent.clicked.connect(self._capture_extent)
        self.btn_city.clicked.connect(self._request_city)
        self.city_input.returnPressed.connect(self._request_city)
        self.aoi_combo.layerChanged.connect(self._validate_aoi_layer)
        
    @property
    def city_layer(self):
        """The city boundary layer if it is still in the project, else None.

        Only the layer id is stored: a reference to the Python wrapper breaks
        ("wrapped C/C++ object ... has been deleted") when the layer is removed.
        """
        if not self.city_layer_id:
            return None
        layer = QgsProject.instance().mapLayer(self.city_layer_id)
        return layer if layer is not None and layer.isValid() else None

    def _update_mode(self, *_):
        """Enable the controls of the active AOI mode (layer / map extent / city)."""
        layer_mode = self.aoi_layer_radio.isChecked()
        extent_mode = self.aoi_extent_radio.isChecked()
        city_mode = self.aoi_city_radio.isChecked()
        self.warning_label.setText(self.WARN_OUTSIDE_ITALY)
        self.aoi_combo.setEnabled(layer_mode)
        self.btn_current_extent.setEnabled(extent_mode)
        self.city_input.setEnabled(city_mode)
        self.btn_city.setEnabled(city_mode)
        if layer_mode:
            self._validate_aoi_layer()
            return
        self.warning_label.hide()
        if city_mode:
            self.extent_label.setText(self.city_info or "Nessuna città caricata")
        elif self.extent_val is not None:
            self.extent_label.setText(f"Catturata: {self.extent_val.toString(2)} ({self.extent_crs})")
        else:
            self.extent_label.setText("Nessun dato catturato")
        self.aoi_changed.emit()

    def _request_city(self):
        text = self.city_input.text().strip()
        if text:
            self.city_requested.emit(text)

    def set_city_result(self, path, crs_authid, names, warning=""):
        """Load the ISTAT boundary layer produced by IstatTask and make it the AOI."""
        self.city_layer_id = None  # before removing: removal triggers signals that read the AOI
        for old in QgsProject.instance().mapLayersByName(BOUNDARY_LAYER_NAME):
            QgsProject.instance().removeMapLayer(old.id())
        layer = QgsVectorLayer(path, BOUNDARY_LAYER_NAME, "ogr")
        if not layer.isValid():
            self.set_city_error("Layer dei confini non valido.")
            return
        QgsProject.instance().addMapLayer(layer)
        self._apply_boundary_styling(layer)
        self.city_layer_id = layer.id()
        self.city_info = self._city_info(names, layer.extent(), crs_authid)
        QgsProject.instance().writeEntry("FETCH", "city_layer_id", layer.id())
        QgsProject.instance().writeEntry("FETCH", "city_text", self.city_input.text().strip())
        self.extent_label.setText(self.city_info)
        self.warning_label.setText(warning or "")
        self.warning_label.setVisible(bool(warning))
        self.aoi_changed.emit()

    @staticmethod
    def _city_info(names, ext, crs_authid):
        return (
            f"{', '.join(names)}\n"
            f"Rettangolo di download: {ext.width() / 1000:.1f} x {ext.height() / 1000:.1f} km ({crs_authid})"
        )

    def _restore_city_state(self, *_):
        """After opening a project, re-select the city AOI that was loaded when it was saved."""
        project = QgsProject.instance()
        layer_id, ok = project.readEntry("FETCH", "city_layer_id", "")
        layer = project.mapLayer(layer_id) if ok and layer_id else None
        if layer is None or not layer.isValid():
            return
        text, _ok = project.readEntry("FETCH", "city_text", "")
        self.city_layer_id = layer_id
        self.city_input.setText(text)
        names = [f"{f['name']} ({f['sigla']})" for f in layer.getFeatures()]
        self.city_info = self._city_info(names, layer.extent(), layer.crs().authid())
        if self.aoi_city_radio.isChecked():
            self._update_mode()
        else:
            self.aoi_city_radio.setChecked(True)  # triggers _update_mode

    def set_city_error(self, message):
        self.city_layer_id = None
        self.city_info = ""
        self.extent_label.setText("Nessuna città caricata")
        self.warning_label.setText(f"⚠ {message}")
        self.warning_label.show()
        self.aoi_changed.emit()

    def set_city_busy(self, busy):
        self.btn_city.setEnabled(not busy and self.aoi_city_radio.isChecked())

    def is_city_mode(self):
        return self.aoi_city_radio.isChecked()

    def get_clip_layer_path(self):
        """
        Polygons the LCZ grid is clipped to, as a layer source string; None = plain rectangle.

        City mode: the ISTAT municipalities. Layer mode: the chosen AOI layer if it is a
        polygon layer saved on disk and not just a rectangle (like the auto boundary).
        """
        if self.is_city_mode():
            layer = self.city_layer
        elif self.is_layer_mode():
            layer = self.aoi_combo.currentLayer()
            if layer is None or not self._is_clipping_polygon_layer(layer):
                return None
        else:
            return None
        if layer is None:
            return None
        source = layer.source()
        return source if os.path.exists(source.split("|")[0]) else None

    @staticmethod
    def _is_clipping_polygon_layer(layer):
        """True for a vector polygon layer that is more than a single plain rectangle."""
        if not isinstance(layer, QgsVectorLayer) or layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            return False
        feats = list(layer.getFeatures(QgsFeatureRequest().setLimit(2)))
        if len(feats) != 1:
            return len(feats) > 1
        geom = feats[0].geometry()
        if geom.isNull():
            return False
        bbox_area = geom.boundingBox().area()
        return bbox_area <= 0 or abs(geom.area() - bbox_area) > 1e-6 * bbox_area

    def missing_aoi_message(self):
        if self.is_layer_mode():
            return "Nessun layer AOI selezionato."
        if self.is_city_mode():
            return "Carica prima i confini della città."
        return "Cattura l'estensione della mappa prima di procedere."
            
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
        """Capture the current map canvas extent and create boundary layer."""
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs().authid()
        self.extent_val = extent
        self.extent_crs = crs
        # Update details label in Italian
        self.extent_label.setText(f"Catturata: {extent.toString(2)} ({crs})")
        within = is_within_italy(extent, crs)
        self.warning_label.setVisible(not within)
        
        # Create boundary layer for OSM compatibility
        self._create_boundary_layer(extent, crs)
        
        self.extent_captured.emit(extent, crs)
    
    def _create_boundary_layer(self, extent, crs_authid):
        """
        Create a boundary polygon layer from the extent.
        This serves as a fallback for OSM download which requires a vector layer.
        
        Args:
            extent: QgsRectangle with the captured extent
            crs_authid: CRS authority ID (e.g., "EPSG:32632")
        """
        try:
            # Get project directory
            project_path = QgsProject.instance().fileName()
            if not project_path:
                return  # Project not saved yet
            
            base_dir = os.path.dirname(project_path)
            project_name = os.path.splitext(os.path.basename(project_path))[0]
            data_dir = os.path.join(base_dir, f"FETCH+{project_name}")
            os.makedirs(data_dir, exist_ok=True)
            
            boundary_path = os.path.join(data_dir, "boundary.gpkg")
            
            # Set up fields
            fields = QgsFields()
            fields.append(QgsField("name", QMetaType.QString))
            fields.append(QgsField("source", QMetaType.QString))
            
            # Create CRS - Standardized to 3003/3004 if in Italy
            target_crs_auth = get_target_crs_for_extent(extent, crs_authid)
            crs = QgsCoordinateReferenceSystem(target_crs_auth)
            
            # Transform extent to target CRS for layer creation
            source_crs = QgsCoordinateReferenceSystem(crs_authid)
            if source_crs != crs:
                from qgis.core import QgsCoordinateTransform
                transform = QgsCoordinateTransform(source_crs, crs, QgsProject.instance())
                extent_target = transform.transformBoundingBox(extent)
                polygon = QgsGeometry.fromRect(extent_target)
            else:
                polygon = QgsGeometry.fromRect(extent)
            
            # Set up writer options
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "GPKG"
            save_options.fileEncoding = "UTF-8"
            save_options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            
            # Create the writer
            writer = QgsVectorFileWriter.create(
                boundary_path,
                fields,
                QgsWkbTypes.Polygon,
                crs,
                QgsProject.instance().transformContext(),
                save_options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return
            
            # Create and add feature
            feature = QgsFeature()
            feature.setFields(fields)
            feature.setGeometry(polygon)
            feature.setAttribute("name", "Captured AOI Boundary")
            feature.setAttribute("source", "Map Canvas Extent")
            writer.addFeature(feature)
            
            del writer  # Close the writer
            
            # Check if layer already exists in project and remove it
            existing = QgsProject.instance().mapLayersByName("Boundary AOI (auto)")
            for lyr in existing:
                QgsProject.instance().removeMapLayer(lyr.id())
            
            # Add to project
            boundary_layer = QgsVectorLayer(boundary_path, "Boundary AOI (auto)", "ogr")
            if boundary_layer.isValid():
                QgsProject.instance().addMapLayer(boundary_layer)
                self.boundary_layer_path = boundary_path
                
                # Apply custom styling
                self._apply_boundary_styling(boundary_layer)
                
                # Select the new boundary layer in the combo
                self.aoi_combo.setLayer(boundary_layer)
                
        except Exception as e:
            # Silently fail - this is a convenience feature
            pass
            
    def _apply_boundary_styling(self, layer):
        """
        Apply custom styling to the boundary layer as requested:
        - Fill: Light brown semi-transparent
        - Stroke: Red dashed line (1mm)
        """
        # Create a simple fill symbol layer
        # Fill: Light Tan (matched from image) alpha ~80/255
        fill_color = QColor(200, 180, 140, 80) 
        # Stroke: Solid Red (matched from image)
        stroke_color = QColor(192, 0, 38)
        
        props = {
            'color': f'{fill_color.red()},{fill_color.green()},{fill_color.blue()},{fill_color.alpha()}',
            'outline_color': f'{stroke_color.red()},{stroke_color.green()},{stroke_color.blue()}',
            'outline_width': '1.0',
            'outline_width_unit': 'MM',
            'outline_style': 'dash',
            'joinstyle': 'bevel',
            'style': 'no'
        }
        
        symbol_layer = QgsSimpleFillSymbolLayer.create(props)
        if symbol_layer:
            # Create a fill symbol and set the layer
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.changeSymbolLayer(0, symbol_layer)
            
            # Apply renderer
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
        
    def get_extent_and_crs(self):
        """Get the current AOI extent and CRS."""
        if self.aoi_layer_radio.isChecked():
            layer = self.aoi_combo.currentLayer()
            if layer:
                return layer.extent(), layer.crs().authid()
            return None, None
        elif self.aoi_city_radio.isChecked():
            layer = self.city_layer
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
    
    def get_boundary_layer_path(self):
        """Get the path to the generated boundary layer."""
        return self.boundary_layer_path
        
    def set_project_path_status(self, saved, path=""):
        """Update the project path status label."""
        if saved:
            self.project_label.setText("Progetto: Salvataggio in cartella locale")
            self.project_label.setStyleSheet("font-size: 10px; color: #7f8c8d; margin-left: 5px;")
        else:
            self.project_label.setText("Progetto: ATTENZIONE - NON SALVATO")
            self.project_label.setStyleSheet("font-style: italic; color: #c0392b; font-weight: bold; margin-left: 5px;")

