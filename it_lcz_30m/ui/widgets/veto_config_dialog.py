# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QWidget, QLabel, QSpinBox, QPushButton, QGridLayout
)
from qgis.PyQt.QtCore import Qt

class VetoConfigDialog(QDialog):
    """Dialog to configure individual veto counts for each LCZ class."""
    
    LCZ_NAMES = {
        '1': 'Compact high-rise',
        '2': 'Compact midrise',
        '3': 'Compact low-rise',
        '4': 'Open high-rise',
        '5': 'Open midrise',
        '6': 'Open low-rise',
        '7': 'Lightweight low-rise',
        '8': 'Large low-rise',
        '9': 'Sparsely built',
        '10': 'Heavy industry',
        'A': 'Dense trees',
        'B': 'Scattered trees',
        'C': 'Bush, scrub',
        'D': 'Low plants',
        'E': 'Bare rock or paved',
        'F': 'Bare soil or sand',
        'G': 'Water'
    }

    def __init__(self, current_configs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurazione Avanzata Veto (V6.0)")
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)
        
        # Internal state: {lcz_id: count}
        self.config = current_configs or {lcz_id: 1 for lcz_id in self.LCZ_NAMES.keys()}
        self.spin_boxes = {}
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        intro = QLabel("Imposta il numero di parametri statistici leader da usare come 'Veto' per ogni classe.\nValore: 1 (solo Leader) a 10 (tutti i parametri statistici).")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(intro)
        
        # Scroll Area for the list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setColumnStretch(1, 1) # Expand names
        
        # Headers
        h1 = QLabel("ID")
        h2 = QLabel("Nome Classe LCZ")
        h3 = QLabel("Parametri Veto")
        for h in [h1, h2, h3]:
            h.setStyleSheet("font-weight: bold; border-bottom: 1px solid #bdc3c7;")
        
        scroll_layout.addWidget(h1, 0, 0)
        scroll_layout.addWidget(h2, 0, 1)
        scroll_layout.addWidget(h3, 0, 2)
        
        # Rows
        row = 1
        # Order: 1-10, A-G
        ordered_ids = [str(i) for i in range(1, 11)] + list("ABCDEFG")
        
        for lcz_id in ordered_ids:
            name = self.LCZ_NAMES.get(lcz_id, "-")
            
            lbl_id = QLabel(lcz_id)
            lbl_id.setAlignment(Qt.AlignCenter)
            lbl_name = QLabel(name)
            
            spin = QSpinBox()
            spin.setRange(1, 10)
            spin.setValue(self.config.get(lcz_id, 1))
            spin.setFixedWidth(60)
            self.spin_boxes[lcz_id] = spin
            
            scroll_layout.addWidget(lbl_id, row, 0)
            scroll_layout.addWidget(lbl_name, row, 1)
            scroll_layout.addWidget(spin, row, 2)
            row += 1
            
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_reset = QPushButton("Reset tutti a 1")
        btn_reset.clicked.connect(self._reset_all)
        
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = QPushButton("Applica")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_accept)
        btn_ok.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px 15px;")
        
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        
        layout.addLayout(btn_layout)

    def _reset_all(self):
        for spin in self.spin_boxes.values():
            spin.setValue(1)

    def _on_accept(self):
        # Update config dict
        for lcz_id, spin in self.spin_boxes.items():
            self.config[lcz_id] = spin.value()
        self.accept()

    def get_config(self):
        """Returns {lcz_id: count} mapping."""
        return self.config
