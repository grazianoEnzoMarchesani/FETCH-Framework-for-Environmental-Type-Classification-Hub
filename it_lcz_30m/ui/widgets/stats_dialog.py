# -*- coding: utf-8 -*-
"""
Advanced Statistics Dialog for FETCH Plugin
Provides visual charts and metrics about the LCZ classification result.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QWidget, QFrame, QScrollArea
)
from qgis.PyQt.QtGui import QColor, QFont

import numpy as np

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    # Dummy classes to avoid NameError during plugin loading if matplotlib is missing
    class FigureCanvas:
        def __init__(self, *args, **kwargs): pass
    class DummyPatch:
        def set_facecolor(self, color): pass
    class Figure:
        def __init__(self, *args, **kwargs):
            self.patch = DummyPatch()
        def add_subplot(self, *args, **kwargs): return self

from ...core.constants import LCZMappings

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor('#ffffff')
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class AdvancedStatsDialog(QDialog):
    def __init__(self, stats, parent=None):
        super(AdvancedStatsDialog, self).__init__(parent)
        self.stats = stats
        self.setWindowTitle("Statistiche Avanzate FETCH")
        self.resize(1000, 700)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("background-color: #2c3e50; border: none;")
        header_layout = QHBoxLayout(self.header)
        
        title_label = QLabel("Dashboard Statistiche Avanzate")
        title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        close_btn = QPushButton("Chiudi")
        close_btn.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        
        self.layout.addWidget(self.header)
        
        # Main Content - Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #dcdde1; 
                background: white; 
                border-radius: 6px;
                margin-top: -1px;
            }
            QTabBar::tab {
                background: #f1f2f6;
                border: 1px solid #dcdde1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 12px 25px;
                min-width: 120px;
                color: #7f8c8d;
                font-size: 11px;
                font-weight: 500;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border: 1px solid #dcdde1;
                border-bottom: 3px solid #3498db;
                color: #2c3e50;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #e9ecef;
                color: #2c3e50;
            }
        """)
        
        self.tabs.addTab(self.create_overview_tab(), "Panoramica")
        self.tabs.addTab(self.create_quality_tab(), "Qualità (RMSEP)")
        self.tabs.addTab(self.create_parameters_tab(), "Morfologia")
        self.tabs.addTab(self.create_physical_tab(), "Proprietà Fisiche")
        self.tabs.addTab(self.create_esa_tab(), "Correzione ESA")
        
        self.layout.addWidget(self.tabs)

    def create_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not HAS_MATPLOTLIB:
            layout.addWidget(QLabel("Matplotlib non è installato. Impossibile visualizzare i grafici."))
            return tab

        # Top section: Summary cards
        summary_layout = QHBoxLayout()
        
        total_cells = sum(self.stats['lcz_counts'].values())
        unique_classes = len(self.stats['lcz_counts'])
        
        summary_layout.addWidget(self.create_stat_card("Celle Totali", str(total_cells), "#3498db"))
        summary_layout.addWidget(self.create_stat_card("Classi LCZ Unite", str(unique_classes), "#2ecc71"))
        
        avg_rmsep = np.mean(list(self.stats['rmsep_stats'].values())) if self.stats['rmsep_stats'] else 0
        summary_layout.addWidget(self.create_stat_card("RMSEP Medio", f"{avg_rmsep:.2f}", "#f1c40f"))
        
        layout.addLayout(summary_layout)
        
        # Distribution Chart
        chart_container = QFrame()
        chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
        chart_layout = QVBoxLayout(chart_container)
        
        canvas = MplCanvas(self, width=8, height=6)
        
        labels = sorted(self.stats['lcz_counts'].keys())
        counts = [self.stats['lcz_counts'][l] for l in labels]
        colors = [LCZMappings.COLORS.get(l, '#bebebe') for l in labels]
        
        # Bar chart
        bars = canvas.axes.bar(labels, counts, color=colors, edgecolor='#555555', linewidth=0.5)
        canvas.axes.set_title("Distribuzione Classi LCZ", fontsize=14, fontweight='bold', pad=20)
        canvas.axes.set_ylabel("Numero di celle")
        canvas.axes.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Add values on top
        for bar in bars:
            height = bar.get_height()
            canvas.axes.annotate(f'{int(height)}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=9)
        
        chart_layout.addWidget(canvas)
        layout.addWidget(chart_container)
        
        return tab

    def create_quality_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not HAS_MATPLOTLIB: return tab
        
        chart_container = QFrame()
        chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
        chart_layout = QVBoxLayout(chart_container)
        
        canvas = MplCanvas(self, width=8, height=6)
        
        labels = sorted(self.stats['rmsep_stats'].keys())
        rmseps = [self.stats['rmsep_stats'][l] for l in labels]
        colors = [LCZMappings.COLORS.get(l, '#bebebe') for l in labels]
        
        canvas.axes.barh(labels, rmseps, color=colors, alpha=0.8, edgecolor='black')
        canvas.axes.set_title("Qualità della Classificazione (RMSEP medio per classe)", fontsize=12, fontweight='bold')
        canvas.axes.set_xlabel("RMSEP (Più basso = Migliore match)")
        canvas.axes.invert_yaxis()
        
        chart_layout.addWidget(canvas)
        layout.addWidget(chart_container)
        
        # Match Stats description
        info = QLabel("Nota: Un RMSEP vicino a 0 indica un match quasi perfetto con le definizioni teoriche di Stewart & Oke (2012).")
        info.setStyleSheet("color: #7f8c8d; font-style: italic; padding: 10px;")
        layout.addWidget(info)
        
        return tab

    def create_parameters_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        if not HAS_MATPLOTLIB: return tab
        
        # We'll create small bar charts for each major parameter
        params_to_show = [
            ('building_surface_fraction', 'Building Frac (%)'),
            ('sky_view_factor', 'SVF (0-1)'),
            ('impervious_surface_fraction', 'Impervious (%)'),
            ('pervious_surface_fraction', 'Pervious (%)'),
            ('height_roughness', 'Roughness H (m)'),
            ('aspect_ratio', 'Aspect Ratio (H/W)'),
            ('terrain_roughness', 'Terrain Roughness (z0)')
        ]
        
        for p_id, p_label in params_to_show:
            chart_container = QFrame()
            chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1; margin-bottom: 20px;")
            chart_layout = QVBoxLayout(chart_container)
            chart_layout.setContentsMargins(5, 5, 5, 5)
            
            canvas = MplCanvas(self, width=8, height=3)
            
            # Extract data
            valid_classes = []
            values = []
            colors = []
            for lcz in sorted(self.stats['param_means'].keys()):
                if p_id in self.stats['param_means'][lcz]:
                    valid_classes.append(lcz)
                    values.append(self.stats['param_means'][lcz][p_id])
                    colors.append(LCZMappings.COLORS.get(lcz, '#bebebe'))
            
            if values:
                canvas.axes.bar(valid_classes, values, color=colors, alpha=0.7)
                canvas.axes.set_title(f"Valore Medio: {p_label}", fontsize=10, fontweight='bold')
                canvas.axes.tick_params(axis='both', which='major', labelsize=8)
                chart_layout.addWidget(canvas)
                content_layout.addWidget(chart_container)

        return tab

    def create_physical_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        if not HAS_MATPLOTLIB: return tab
        
        params_to_show = [
            ('surface_albedo', 'Albedo (0-1)'),
            ('surface_admittance', 'Surface Admittance (J/m²s½K)'),
            ('anthropogenic_heat', 'Anthro. Heat (W/m²)')
        ]
        
        for p_id, p_label in params_to_show:
            chart_container = QFrame()
            chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1; margin-bottom: 20px;")
            chart_layout = QVBoxLayout(chart_container)
            chart_layout.setContentsMargins(5, 5, 5, 5)
            
            canvas = MplCanvas(self, width=8, height=3)
            
            valid_classes = []
            values = []
            colors = []
            for lcz in sorted(self.stats['param_means'].keys()):
                if p_id in self.stats['param_means'][lcz]:
                    valid_classes.append(lcz)
                    values.append(self.stats['param_means'][lcz][p_id])
                    colors.append(LCZMappings.COLORS.get(lcz, '#bebebe'))
            
            if values:
                canvas.axes.bar(valid_classes, values, color=colors, alpha=0.7)
                canvas.axes.set_title(f"Valore Medio: {p_label}", fontsize=10, fontweight='bold')
                canvas.axes.tick_params(axis='both', which='major', labelsize=8)
                chart_layout.addWidget(canvas)
                content_layout.addWidget(chart_container)

        return tab

    def create_esa_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not HAS_MATPLOTLIB: return tab
        
        chart_container = QFrame()
        chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
        chart_layout = QVBoxLayout(chart_container)
        
        canvas = MplCanvas(self, width=6, height=6)
        
        corrected = self.stats['esa_correction']['corrected']
        total = self.stats['esa_correction']['total']
        unchanged = total - corrected
        
        if total > 0:
            sizes = [corrected, unchanged]
            labels = [f'Corrette ESA ({corrected})', f'Originali ({unchanged})']
            colors = ['#3498db', '#ecf0f1']
            
            canvas.axes.pie(sizes, labels=labels, autopct='%1.1f%%', 
                          startangle=90, colors=colors, shadow=False,
                          wedgeprops={'edgecolor': 'white', 'linewidth': 2})
            canvas.axes.set_title("Impatto Correzione ESA WorldCover", fontsize=12, fontweight='bold')
        
        chart_layout.addWidget(canvas)
        layout.addWidget(chart_container)
        
        info = QLabel("Questa metrica indica quante celle classificate inizialmente come 'Naturali' sono state sovrascritte dai dati ESA WorldCover.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #7f8c8d; font-style: italic; padding: 10px;")
        layout.addWidget(info)
        
        return tab

    def create_stat_card(self, label, value, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{ background-color: white; border-left: 5px solid {color}; border-radius: 4px; border-top: 1px solid #eee; border-right: 1px solid #eee; border-bottom: 1px solid #eee; }}
        """)
        layout = QVBoxLayout(card)
        
        val_label = QLabel(value)
        val_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        layout.addWidget(val_label)
        
        txt_label = QLabel(label)
        txt_label.setStyleSheet("font-size: 11px; color: #7f8c8d; text-transform: uppercase;")
        layout.addWidget(txt_label)
        
        return card
