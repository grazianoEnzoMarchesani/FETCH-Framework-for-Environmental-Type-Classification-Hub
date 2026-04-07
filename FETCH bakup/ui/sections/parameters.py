# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Parameters Section

Section 5: LCZ parameter calculation buttons and indicators.
"""

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton, QComboBox, QCheckBox, QSpinBox
)
from qgis.gui import QgsCollapsibleGroupBox

from ..constants import PARAM_VISUALIZATION, PARAM_DEFINITIONS
from ..mixins.help_mixin import HelpMixin
from ..help_content import HELP_PARAMETERS


class ParametersSection(QgsCollapsibleGroupBox, HelpMixin):
    """Section 5: LCZ Parameters - calculation buttons and status indicators."""
    
    # Signals
    parameter_requested = pyqtSignal(str)  # parameter_id
    visualization_requested = pyqtSignal(str)  # field_name
    classify_requested = pyqtSignal(str, bool, bool, object, bool, str, bool) # method, smoothing, training, veto, adaptive, profile, force_urban_esa
    stats_requested = pyqtSignal()
    crystallize_requested = pyqtSignal()  # export styled vector layers
    training_mode_requested = pyqtSignal(bool) # enabled
    
    def __init__(self, parent=None):
        super().__init__("5. Calcolo Parametri LCZ", parent)
        self.param_buttons = {}
        self.indicator_buttons = {}
        # Custom Veto Configuration for V6 (None means use global spinbox)
        self.custom_veto_config = None
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
            
            # Help Icon (Right aligned, before action)
            help_btn = self.create_help_button(pid, HELP_PARAMETERS)
            row_layout.addWidget(help_btn)
            
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
        
        # Helper nested function to create result items with indicators on the LEFT (more compact)
        def add_result_item(field, label, tooltip, row, col, span=1):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(6)
            
            # Indicator Dot (LEFT aligned)
            btn = QPushButton()
            btn.setObjectName("VisualButton")
            btn.setFixedSize(16, 16)
            btn.setEnabled(False)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda: self.visualization_requested.emit(field))
            layout.addWidget(btn)
            
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #34495e;")
            layout.addWidget(lbl)
            
            layout.addStretch() # Pushes the label-dot pair to stay left-aligned
            
            self.results_grid.addWidget(container, row, col, 1, span)
            self.indicator_buttons[field] = btn
            self.result_containers[field] = container
            return btn

        self.result_containers = {}
        # Triple column layout for very compact view
        # Row 1: Primary 
        self.ind_lcz = add_result_item('lcz_class', "LCZ", "Visualizza Classi LCZ", 1, 0)
        self.ind_matches = add_result_item('lcz_matches', "MATCH", "Visualizza Corrispondenze", 1, 1)
        self.ind_esa = add_result_item('lcz_esa_fix', "FIX ESA", "Visualizza Rettifica ESA", 1, 2)
        
        # Row 2: Metrics
        self.ind_score = add_result_item('lcz_score', "SCORE", "Visualizza Punteggio (Score)", 2, 0)
        self.ind_confidence = add_result_item('lcz_confidence', "CONFIDENCE", "Visualizza Grado di Confidenza", 2, 1)
        self.ind_rmsep = add_result_item('lcz_rmsep', "ERRORE", "Visualizza Errore (RMSEP)", 2, 2)
        
        # Row 3: Full width for Vulnerability
        self.ind_vuln = add_result_item('lcz_vulnerability', "VULNERABILITÀ", "Visualizza Vulnerabilità", 3, 0, 3)
        
        # Initial Visibility
        self.result_containers['lcz_score'].setVisible(False)
        self.result_containers['lcz_confidence'].setVisible(False)
        self.result_containers['lcz_rmsep'].setVisible(True) # Visible for stable by default
        
        # Add help to class results
        help_lcz = self.create_help_button("lcz_class", HELP_PARAMETERS)
        self.results_grid.addWidget(help_lcz, 0, 2)
        
        self.main_layout.addWidget(self.results_card)
        
        # --- Final Actions Container ---
        self.actions_container = QWidget()
        actions_layout = QVBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(0, 15, 0, 5)
        actions_layout.setSpacing(10)
        
        # Classification Method Selector (added above button)
        self.classify_method_combo = QComboBox()
        self.classify_method_combo.addItems([
            "Standard (Stable - Dec 29)", 
            "Weighted Contextual (v1.1)",
            "Experimental (v2.0)",
            "Weighted Experimental (v2.1)",
            "Advanced (v3.0)",
            "Fuzzy Archetype (v4.0 - FAD)",
            "Mahalanobis Adaptive (v5.0)",
            "Weighted Z-Distance (v6.0)",
            "District-Based RF (v7.0)",
            "Semantic Expert (v8.0)"
        ])
        self.classify_method_combo.setToolTip("Scegli la logica di classificazione finale LCZ.\n- v7.0: District-Based RF.\n- v8.0: Semantic Expert Engine (Explainable).")
        self.classify_method_combo.setFixedWidth(200)
        self.classify_method_combo.setObjectName("ParamCombo")
        self.classify_method_combo.currentIndexChanged.connect(self._on_method_changed)
        actions_layout.addWidget(self.classify_method_combo)
        
        # Smoothing Toggle
        self.chk_smoothing = QCheckBox("Applica Smoothing Spaziale (3x3)")
        self.chk_smoothing.setStyleSheet("font-size: 11px; color: #34495e; padding: 5px;")
        actions_layout.addWidget(self.chk_smoothing)
        
        # Adaptive Calibration Toggle
        self.chk_adaptive = QCheckBox("Usa Calibrazione Adattiva (2-passi)")
        self.chk_adaptive.setChecked(False)
        self.chk_adaptive.setToolTip("Esegue un primo passaggio per adattare i range LCZ alla morfologia locale (es. città italiane),\nquindi riesegue la classificazione per migliorare la confidenza e ridurre le ambiguità.")
        self.chk_adaptive.setStyleSheet("font-size: 11px; color: #8e44ad; font-weight: bold; padding: 5px;")
        actions_layout.addWidget(self.chk_adaptive)
        
        # ESA v8 Force Urban Toggle
        self.chk_force_urban_esa = QCheckBox("Forza LCZ 1-10 se ESA = 50 (Urbano)")
        self.chk_force_urban_esa.setChecked(True)
        self.chk_force_urban_esa.setToolTip("Se attivato, i distretti semantici con ESA WorldCover = 50 (Built-up) verranno forzati a cercare corrispondenze solo nelle classi urbane (1-10).")
        self.chk_force_urban_esa.setStyleSheet("font-size: 11px; color: #d35400; font-weight: bold; padding: 5px;")
        self.chk_force_urban_esa.setVisible(False)
        actions_layout.addWidget(self.chk_force_urban_esa)
        
        # Recommendation Label (Hidden by default)
        self.lbl_smoothing_rec = QLabel("💡 Consigliato disattivare lo smoothing con v1.1/v2.1")
        self.lbl_smoothing_rec.setStyleSheet("color: #e67e22; font-size: 10px; font-weight: bold; margin-left: 20px;")
        self.lbl_smoothing_rec.setVisible(False)
        actions_layout.addWidget(self.lbl_smoothing_rec)
        
        # Training Toggle
        self.chk_training = QCheckBox("Contribuisci alla Knowledge Base (Addestramento)")
        self.chk_training.setChecked(True)
        self.chk_training.setToolTip("Se attivato, i nuovi campioni puri verranno salvati nel database per migliorare le future classificazioni.")
        self.chk_training.setStyleSheet("font-size: 11px; color: #2980b9; font-weight: bold; padding: 5px;")
        self.chk_training.setVisible(False) # Only visible for v5
        self.chk_training.toggled.connect(self._on_training_toggled)
        actions_layout.addWidget(self.chk_training)
        
        # Veto Count Selector (v6 only)
        self.veto_container = QWidget()
        veto_layout = QHBoxLayout(self.veto_container)
        veto_layout.setContentsMargins(5, 5, 5, 5)
        veto_layout.setSpacing(10)
        
        lbl_veto = QLabel("Veto:")
        lbl_veto.setStyleSheet("font-size: 11px; color: #2c3e50; font-weight: bold;")
        veto_layout.addWidget(lbl_veto)
        
        self.spin_veto = QSpinBox()
        self.spin_veto.setRange(1, 10)
        self.spin_veto.setValue(1)
        self.spin_veto.setFixedWidth(40)
        self.spin_veto.setToolTip("Numero di parametri statistici 'Leader' usati per scartare una classe.\nPiù alto è il numero, più la classificazione è restrittiva.")
        self.spin_veto.valueChanged.connect(self._on_global_veto_changed)
        veto_layout.addWidget(self.spin_veto)
        
        self.btn_veto_adv = QPushButton("⚙️")
        self.btn_veto_adv.setFixedWidth(30)
        self.btn_veto_adv.setToolTip("Configurazione avanzata: imposta veto differenti per ogni classe.")
        self.btn_veto_adv.setStyleSheet("font-size: 14px; background: #ecf0f1; border: 1px solid #bdc3c7;")
        self.btn_veto_adv.clicked.connect(self._on_veto_adv_clicked)
        veto_layout.addWidget(self.btn_veto_adv)

        veto_layout.addSpacing(10)
        
        lbl_profile = QLabel("Profilo:")
        lbl_profile.setStyleSheet("font-size: 11px; color: #2c3e50; font-weight: bold;")
        veto_layout.addWidget(lbl_profile)

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Z-score", "Unic-score", "Fuzzy-unic-score"])
        self.profile_combo.setToolTip("Seleziona il profilo di pesi e parametri leader per la classificazione V6.")
        self.profile_combo.setStyleSheet("font-size: 11px;")
        veto_layout.addWidget(self.profile_combo)

        
        veto_layout.addStretch()
        
        self.veto_container.setVisible(False)
        actions_layout.addWidget(self.veto_container)
        
        # Classification button
        self.btn_classify = QPushButton(" Esegui Classificazione Finale")
        self.btn_classify.setObjectName("SuccessButton")
        from qgis.core import QgsApplication
        self.btn_classify.setIcon(QgsApplication.getThemeIcon("mActionCheckHtml.svg"))
        self.btn_classify.setMinimumHeight(42)
        self.btn_classify.setCursor(Qt.PointingHandCursor)
        
        self.btn_classify.clicked.connect(self._on_classify_clicked)
        actions_layout.addWidget(self.btn_classify)
        
        # Advanced Statistics button
        self.btn_stats = QPushButton(" Statistiche Avanzate")
        self.btn_stats.setObjectName("AccentButton")
        self.btn_stats.setIcon(QgsApplication.getThemeIcon("mActionShowTable.svg")) # Statistics/Analysis look
        self.btn_stats.setToolTip("Visualizza statistiche e grafici avanzati della classificazione")
        self.btn_stats.setEnabled(False)
        self.btn_stats.setMinimumHeight(42)
        self.btn_stats.setCursor(Qt.PointingHandCursor)
        self.btn_stats.clicked.connect(self.stats_requested.emit)
        actions_layout.addWidget(self.btn_stats)
        
        # Crystallize Maps button
        self.btn_crystallize = QPushButton(" 💎 Cristallizza Mappe")
        self.btn_crystallize.setObjectName("AccentButton")
        self.btn_crystallize.setToolTip(
            "Esporta layer vettoriali individuali per ogni parametro LCZ, "
            "con vestizioni colori e attributi minimali.\n"
            "I file vengono salvati in unified/crystallized/"
        )
        self.btn_crystallize.setEnabled(False)
        self.btn_crystallize.setMinimumHeight(42)
        self.btn_crystallize.setCursor(Qt.PointingHandCursor)
        self.btn_crystallize.clicked.connect(self.crystallize_requested.emit)
        actions_layout.addWidget(self.btn_crystallize)
        
        # Training Mode Toggle (v7 specific)
        self.btn_training_mode = QPushButton(" 🎯 Attiva Addestramento Manuale")
        self.btn_training_mode.setCheckable(True)
        self.btn_training_mode.setObjectName("AccentButton")
        self.btn_training_mode.setStyleSheet("font-weight: bold; background-color: #f39c12;")
        self.btn_training_mode.setMinimumHeight(42)
        self.btn_training_mode.setToolTip("Attiva lo strumento per cliccare sulla mappa e correggere la classificazione (v7).")
        self.btn_training_mode.toggled.connect(self.training_mode_requested.emit)
        self.btn_training_mode.setVisible(False)
        actions_layout.addWidget(self.btn_training_mode)
        
        self.main_layout.addWidget(self.actions_container)
        
    def _on_method_changed(self, index):
        """Handle classification method change."""
        # Index 1 is v1.1, Index 3 is v2.1, Index 6 is v5.0
        # For these, we prefer smoothing OFF (or forced OFF for training)
        if index in [1, 3, 6]:
            self.chk_smoothing.setChecked(False)
            self.lbl_smoothing_rec.setVisible(index in [1, 3])
        else:
            self.lbl_smoothing_rec.setVisible(False)
            if index in [0, 2, 4, 5]: # Stable, Experimental v2.0, Adv v3.0, FAD v4.0
                 self.chk_smoothing.setChecked(True)
        
        # Show/hide training checkbox for Mahalanobis Adaptive (v5.0 is index 6)
        self.chk_training.setVisible(index == 6)
        
        # v6.0 (index 7) also prefers smoothing ON or OFF?
        # Traditionally WZDV is a local classifier, smoothing is good for noise.
        if index == 7:
            self.chk_smoothing.setChecked(True)
            self.veto_container.setVisible(True)
        else:
            self.veto_container.setVisible(False)

        # v7.0 (index 8)
        self.btn_training_mode.setVisible(index == 8)
        if index == 8:
            self.chk_smoothing.setChecked(False) # v7 is object-based, doesn't need pixel smoothing

        # v8.0 (index 9)
        self.chk_force_urban_esa.setVisible(index == 9)
        if index == 9:
            self.chk_smoothing.setChecked(False) # v8 is also object-based
            self.chk_adaptive.setChecked(False) # v8 uses rigid archetypes, 2-pass not needed

        # Handle Score/Confidence visibility
        # Methods with Score/Confidence: v3(4), v4(5), v5(6), v6(7)
        show_metrics = index >= 4
        self.result_containers['lcz_score'].setVisible(show_metrics)
        self.result_containers['lcz_confidence'].setVisible(show_metrics)
        
        # Hide RMSEP for v4, v5, v6 as it's redundant (equal to Score)
        self.result_containers['lcz_rmsep'].setVisible(index < 5)
        
        # Update labels for v3 (RMSEP Norm instead of raw RMSEP)
        if index == 4:
            # For v3, Score is technically rmsep_norm
            # But we'll keep the indicator as 'lcz_score' for signals, 
            # and just handle the mapping if necessary. Actually classification_v3 writes both.
            pass

    def _on_training_toggled(self, checked):
        """If training is enabled, force smoothing OFF to ensure data purity."""
        if checked:
            self.chk_smoothing.setChecked(False)

    def _on_global_veto_changed(self, value):
        """Reset custom config if global spinbox is touched."""
        if self.custom_veto_config:
            self.custom_veto_config = None
            self.btn_veto_adv.setStyleSheet("font-size: 14px; background: #ecf0f1; border: 1px solid #bdc3c7;")
            self.spin_veto.setStyleSheet("")

    def _on_veto_adv_clicked(self):
        from ..widgets.veto_config_dialog import VetoConfigDialog
        dlg = VetoConfigDialog(current_configs=self.custom_veto_config, parent=self)
        if dlg.exec_():
            self.custom_veto_config = dlg.get_config()
            # Visual feedback that custom config is active
            self.btn_veto_adv.setStyleSheet("font-size: 14px; background: #27ae60; color: white; border: 1px solid #27ae60;")
            self.spin_veto.setStyleSheet("color: #7f8c8d; background: #f9f9f9;")
            self.spin_veto.setToolTip("Configurazione avanzata attiva. Modifica qui per resettare.")

    def _on_classify_clicked(self):
        """Handle classification button click with method selection."""
        idx = self.classify_method_combo.currentIndex()
        # Mapping: 0:stable, 1:v1.1, 2:experimental, 3:v2.1, 4:v3, 5:v4, 6:v5, 7:v6, 8:v7, 9:v8
        methods = ['stable', 'v1.1', 'experimental', 'v2.1', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8']
        method = methods[idx] if idx < len(methods) else 'stable'
        apply_smoothing = self.chk_smoothing.isChecked()
        is_training = self.chk_training.isChecked() if idx == 6 else False
        
        # Determine veto_count (int or dict)
        if idx == 7: # V6
            veto_count = self.custom_veto_config if self.custom_veto_config else self.spin_veto.value()
        else:
            veto_count = 1
            
        # Determine profile
        profile_map = {0: 'z-score', 1: 'unic-score', 2: 'fuzzy-unic-score'}
        profile = profile_map.get(self.profile_combo.currentIndex(), 'z-score') if idx == 7 else 'z-score'
            
        adaptive_calibration = self.chk_adaptive.isChecked()
        force_urban_esa = self.chk_force_urban_esa.isChecked() if idx == 9 else False
        
        self.classify_requested.emit(method, apply_smoothing, is_training, veto_count, adaptive_calibration, profile, force_urban_esa)


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
        self.classify_method_combo.setEnabled(enabled)
        
    def set_stats_enabled(self, enabled):
        """Enable/disable the advanced statistics button."""
        self.btn_stats.setEnabled(enabled)
    
    def set_crystallize_enabled(self, enabled):
        """Enable/disable the crystallize maps button."""
        self.btn_crystallize.setEnabled(enabled)
        
    def set_enabled(self, enabled):
        """Enable or disable the entire section."""
        super().setEnabled(enabled)
        if not enabled:
            self.set_all_indicators_disabled()
