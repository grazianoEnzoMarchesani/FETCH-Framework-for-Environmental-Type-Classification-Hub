# -*- coding: utf-8 -*-
import os
from qgis.gui import QgsMapToolIdentifyFeature
from qgis.core import QgsProject, QgsMessageLog, Qgis, QgsFeature, QgsGeometry
from qgis.PyQt.QtWidgets import QMenu, QAction, QMessageBox
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt import sip

from ...core.constants import LayerNames, FieldNames, LCZMappings
from ...core.processors.lcz.classification_v5_mahalanobis import LCZKnowledgeBaseManager

class LCZTrainingTool(QgsMapToolIdentifyFeature):
    """
    Map tool to identify an LCZ grid cell and assign a correct class 
    to be added to the Knowledge Base.
    """
    
    sampleAdded = pyqtSignal(str) # Emits the LCZ ID added

    def __init__(self, iface, data_manager):
        self.iface = iface
        self.dm = data_manager
        self.canvas = iface.mapCanvas()
        
        # Find the active grid layer
        self.layer = self._find_active_grid()
        super(LCZTrainingTool, self).__init__(self.canvas, self.layer)
        
        self.kb_manager = LCZKnowledgeBaseManager(data_manager)
        self.setCursor(Qt.CrossCursor)

    def _is_layer_valid(self):
        """Ultra-robust check to see if the layer C++ object still exists."""
        try:
            if self.layer is None:
                return False
            if sip.isdeleted(self.layer):
                return False
            return self.layer.isValid()
        except (RuntimeError, AttributeError, NameError):
            return False

    def _find_active_grid(self):
        """Finds the first valid LCZ grid layer in the project."""
        for layer in QgsProject.instance().mapLayers().values():
            if "Griglia LCZ" in layer.name() and layer.type() == 0: # VectorLayer
                return layer
        return None

    def canvasReleaseEvent(self, event):
        """Handle mouse click."""
        if not self._is_layer_valid():
            self.layer = self._find_active_grid()
            if not self._is_layer_valid():
                self.iface.messageBar().pushMessage("FETCH", "Nessuna griglia LCZ valida trovata in questo progetto.", level=Qgis.Warning)
                return
            # Inform the base class about the new layer if possible, 
            # though identify() usually takes the layer list as argument anyway.

        # Identify feature
        found_features = self.identify(event.x(), event.y(), [self.layer], self.IdentifyMode.TopDownStopAtFirst)
        
        if not found_features:
            return

        feature = found_features[0].mFeature
        self._show_lcz_selection_menu(feature, event.globalPos())

    def _show_lcz_selection_menu(self, feature, pos):
        """Shows a context menu to select the correct LCZ class."""
        if not self._is_layer_valid():
            return

        menu = QMenu()
        menu.setTitle("Seleziona LCZ Corretta")
        
        try:
            selection = self.layer.selectedFeatures()
        except RuntimeError:
            selection = []
            
        is_in_selection = any(f.id() == feature.id() for f in selection)
        
        # Determine features to add
        if is_in_selection:
            target_features = selection
            title = f"Assegna alla selezione ({len(selection)} celle)"
        else:
            target_features = [feature]
            title = f"Cella ID: {feature.id()}"

        header = menu.addAction(title)
        header.setEnabled(False)
        menu.addSeparator()

        # Build menu by categories (Built/Natural)
        built_menu = menu.addMenu("Built Types (1-10)")
        natural_menu = menu.addMenu("Natural Types (A-G)")

        for lcz_id, desc in LCZMappings.CLASSES.items():
            target = built_menu if lcz_id.isdigit() else natural_menu
            action = target.addAction(f"LCZ {lcz_id}: {desc}")
            action.setData(lcz_id)
            action.triggered.connect(lambda checked, lid=lcz_id: self._save_to_kb(target_features, lid))

        menu.exec_(pos)

    def _save_to_kb(self, features, correct_lcz_id):
        """Extracts parameters from features and saves them to the Knowledge Base."""
        samples_to_add = []
        
        for feature in features:
            params = {}
            valid_cell = True
            for f_src, p_name in LCZMappings.FIELD_TO_PARAM.items():
                val = feature.attribute(f_src)
                if val is not None and str(val) not in ('NULL', ''):
                    params[p_name] = float(val)
                else:
                    valid_cell = False
                    break
            
            if valid_cell:
                sample = {'lcz_id': correct_lcz_id}
                sample.update(params)
                samples_to_add.append(sample)

        if not samples_to_add:
            QMessageBox.warning(self.iface.mainWindow(), "Dati Incompleti", 
                              "Nessuna delle celle selezionate ha tutti i parametri calcolati. Calcola i parametri prima di addestrare.")
            return

        added = self.kb_manager.append_samples(samples_to_add)
        if added > 0:
            msg = f"Aggiunti {added} campioni alla KB (LCZ {correct_lcz_id})!" if len(features) > 1 else f"Campione aggiunto alla KB (LCZ {correct_lcz_id})!"
            self.iface.messageBar().pushMessage("FETCH", msg, level=Qgis.Success, duration=3)
            self.sampleAdded.emit(correct_lcz_id)
        else:
            self.iface.messageBar().pushMessage("FETCH", "Campioni già presenti o errore nel salvataggio.", level=Qgis.Info)

    def activate(self):
        super(LCZTrainingTool, self).activate()
        self.iface.messageBar().pushMessage("FETCH", "Strumento di addestramento attivo: clicca su una cella della griglia.", level=Qgis.Info)

    def deactivate(self):
        super(LCZTrainingTool, self).deactivate()
