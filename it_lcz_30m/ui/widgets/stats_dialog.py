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
from qgis.core import QgsMessageLog, Qgis, QgsProject
import os
import numpy as np

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_pdf import PdfPages
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
        # Balanced layout parameters
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor('#ffffff')
        self.axes = fig.add_subplot(111)
        
        # Consistent margins to avoid label cutting and leave space for legend on top
        fig.subplots_adjust(left=0.1, right=0.95, top=0.82, bottom=0.25)
        
        # Remove top and right spines for a cleaner look
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['right'].set_visible(False)
        
        super(MplCanvas, self).__init__(fig)
        self.setMinimumHeight(200) # Prevents squashing


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
        
        export_btn = QPushButton("Esporta PDF")
        export_btn.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; border-radius: 4px; padding: 6px 15px; font-weight: bold; margin-right: 10px; }
            QPushButton:hover { background-color: #2980b9; }
        """)
        export_btn.clicked.connect(self.export_to_pdf)
        header_layout.addWidget(export_btn)
        
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
        self.tabs.addTab(self.create_esa_comparison_tab(), "Validazione Post-ESA")
        self.tabs.addTab(self.create_validation_tab(), "Validazione Globale")
        
        self.layout.addWidget(self.tabs)
        
    def create_info_box(self, title, text):
        box = QFrame()
        box.setStyleSheet("""
            QFrame { 
                background-color: #e3f2fd; 
                border-left: 5px solid #2196f3; 
                border-radius: 4px; 
                margin: 10px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(box)
        
        header = QLabel(f"{title}")
        header.setStyleSheet("font-weight: bold; color: #1565c0; font-size: 12px;")
        layout.addWidget(header)
        
        content = QLabel(text)
        content.setStyleSheet("color: #0d47a1; font-size: 11px;")
        content.setWordWrap(True)
        layout.addWidget(content)
        
        return box

    def create_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not HAS_MATPLOTLIB:
            layout.addWidget(QLabel("Matplotlib non è installato. Impossibile visualizzare i grafici."))
            return tab

        # Top section: Summary cards
        summary_layout = QHBoxLayout()
        
        total_cells = sum(self.stats['lcz_counts'].values())
        
        # Calculate Dominant Class
        counts = self.stats['lcz_counts']
        dominant_class = max(counts, key=counts.get) if counts else "N/D"
        
        # Calculate Total Area (Each 30m cell is 900m2 = 0.09 hectares)
        total_ha = total_cells * 0.09
        
        summary_layout.addWidget(self.create_stat_card("Celle Totali", str(total_cells), "#3498db"))
        summary_layout.addWidget(self.create_stat_card("Superficie (ha)", f"{total_ha:.1f}", "#2ecc71"))
        
        avg_rmsep = np.mean(list(self.stats['rmsep_stats'].values())) if self.stats['rmsep_stats'] else 0
        summary_layout.addWidget(self.create_stat_card("RMSEP Medio", f"{avg_rmsep:.2f}", "#f1c40f"))
        summary_layout.addWidget(self.create_stat_card("Classe Dominante", f"LCZ {dominant_class}", "#e67e22"))
        
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
        
        layout.addWidget(self.create_info_box(
            "Interpretazione Panoramica",
            "Questa vista mostra la 'composizione genetica' del territorio. Una prevalenza di classi 1-3 indica un centro storico compatto, mentre classi 4-6 suggeriscono espansione urbana moderna. "
            "Controlla se la distribuzione delle classi naturali (A-G) riflette la reale presenza di parchi o corpi idrici nell'area."
        ))
        
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
        
        layout.addWidget(self.create_info_box(
            "Interpretazione Qualità (RMSEP)",
            "L'RMSEP misura lo scostamento tra i dati reali del sito e il profilo teorico di Stewart & Oke. "
            "Valori bassi (< 0.5) indicano un match eccellente. Se una classe ha un RMSEP alto, potrebbe indicare un'anomalia nei dati sorgente o una morfologia urbana 'atípica' per gli standard internazionali."
        ))
        
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
            container = QWidget()
            cont_layout = QVBoxLayout(container)
            
            # Label Title
            title = QLabel(f"{p_label}")
            title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50; margin-top: 10px;")
            cont_layout.addWidget(title)
            
            chart_container = QFrame()
            chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
            chart_container.setMinimumHeight(240)
            chart_layout = QVBoxLayout(chart_container)
            chart_layout.setContentsMargins(5, 5, 5, 5)
            
            # Width is flexible, height is fixed contextually
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
                # Plot actual values
                bars = canvas.axes.bar(valid_classes, values, color=colors, alpha=0.7, edgecolor='#333', linewidth=0.5, label='Media Sito')
                
                # Plot Reference Ranges (Stewart & Oke 2012)
                ref_mins = []
                ref_maxs = []
                ref_x = []
                for i, lcz in enumerate(valid_classes):
                    lcz_ref = LCZMappings.PARAMETERS.get(lcz, {})
                    if p_id in lcz_ref:
                        p_min, p_max = lcz_ref[p_id]
                        # Handle infinity for visualization
                        display_max = p_max
                        if p_max == float('inf'):
                            # Use site max or 1.5x of min, but never less than min
                            site_max = max(values) if values else 0
                            display_max = max(p_min * 1.1, site_max * 1.2)
                        
                        # Ensure mx is at least mn to avoid negative yerr
                        mn = p_min
                        mx = max(mn + 0.001, display_max)
                        
                        ref_x.append(i)
                        ref_mins.append(mn)
                        ref_maxs.append(mx)
                
                if ref_x:
                    # Center and half-width for symmetric errorbar
                    y_centers = [(mn + mx)/2 for mn, mx in zip(ref_mins, ref_maxs)]
                    y_errs = [max(0, (mx - mn)/2) for mn, mx in zip(ref_mins, ref_maxs)]
                    
                    # Draw reference ranges as vertical lines with caps
                    canvas.axes.errorbar(ref_x, y_centers, yerr=y_errs,
                                       fmt='none', ecolor='#2c3e50', elinewidth=2, capsize=4, 
                                       alpha=0.6, label='Range Stewart & Oke')
                
                # Move legend above the plot to avoid overlapping
                canvas.axes.legend(fontsize=8, frameon=False, loc='lower center', 
                                 bbox_to_anchor=(0.5, 1.02), ncol=2)
                
                canvas.axes.set_ylabel("Media")
                canvas.axes.tick_params(axis='both', which='major', labelsize=9)
                
                chart_layout.addWidget(canvas)
                cont_layout.addWidget(chart_container)
                content_layout.addWidget(container)

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
            container = QWidget()
            cont_layout = QVBoxLayout(container)
            
            title = QLabel(f"{p_label}")
            title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50; margin-top: 10px;")
            cont_layout.addWidget(title)
            
            chart_container = QFrame()
            chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
            chart_container.setMinimumHeight(240)
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
                canvas.axes.bar(valid_classes, values, color=colors, alpha=0.7, edgecolor='#333', linewidth=0.5, label='Media Sito')
                
                # Plot Reference Ranges
                ref_mins = []
                ref_maxs = []
                ref_x = []
                for i, lcz in enumerate(valid_classes):
                    lcz_ref = LCZMappings.PARAMETERS.get(lcz, {})
                    if p_id in lcz_ref:
                        p_min, p_max = lcz_ref[p_id]
                        display_max = p_max
                        if p_max == float('inf'):
                            site_max = max(values) if values else 0
                            display_max = max(p_min * 1.1, site_max * 1.2)
                        
                        mn = p_min
                        mx = max(mn + 0.001, display_max)
                        ref_x.append(i)
                        ref_mins.append(mn)
                        ref_maxs.append(mx)

                if ref_x:
                     y_centers = [(mn + mx)/2 for mn, mx in zip(ref_mins, ref_maxs)]
                     y_errs = [max(0, (mx - mn)/2) for mn, mx in zip(ref_mins, ref_maxs)]
                     
                     canvas.axes.errorbar(ref_x, y_centers, yerr=y_errs,
                                       fmt='none', ecolor='#2c3e50', elinewidth=2, capsize=4, 
                                       alpha=0.6, label='Range Stewart & Oke')

                # Move legend above the plot to avoid overlapping
                canvas.axes.legend(fontsize=8, frameon=False, loc='lower center', 
                                 bbox_to_anchor=(0.5, 1.02), ncol=2)
                
                canvas.axes.set_ylabel("Media")
                canvas.axes.tick_params(axis='both', which='major', labelsize=9)
                
                chart_layout.addWidget(canvas)
                cont_layout.addWidget(chart_container)
                content_layout.addWidget(container)

        return tab

    def create_esa_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        
        if not HAS_MATPLOTLIB: return tab
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 1. Overview Section
        overview_container = QFrame()
        overview_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
        over_layout = QVBoxLayout(overview_container)
        
        canvas_over = MplCanvas(self, width=6, height=5)
        corrected = self.stats['esa_correction']['corrected']
        total = self.stats['esa_correction']['total']
        unchanged = total - corrected
        
        if total > 0:
            sizes = [corrected, unchanged]
            labels = [f'Corrette ESA ({corrected})', f'Originali ({unchanged})']
            colors = ['#3498db', '#ecf0f1']
            canvas_over.axes.pie(sizes, labels=labels, autopct='%1.1f%%', 
                               startangle=90, colors=colors, shadow=False,
                               wedgeprops={'edgecolor': 'white', 'linewidth': 2})
            canvas_over.axes.set_title("Percentuale Celle Rettificate da ESA WorldCover", fontsize=12, fontweight='bold')
        
        over_layout.addWidget(canvas_over)
        scroll_layout.addWidget(overview_container)
        
        # 2. Detailed Transitions Section
        transitions = self.stats['esa_correction'].get('transitions', {})
        if transitions:
            detail_title = QLabel("Dettaglio Transizioni (Classe Originale → Nuova)")
            detail_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 20px; color: #2c3e50;")
            scroll_layout.addWidget(detail_title)
            
            # Use a grid layout or flow for small pie charts
            # For simplicity and readability, we'll use a wrap-around layout or just a list of containers
            for orig_class, targets in sorted(transitions.items()):
                chart_cont = QFrame()
                chart_cont.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1; margin-bottom: 20px;")
                chart_cont.setMinimumHeight(450) # Enforce larger height
                c_layout = QVBoxLayout(chart_cont)
                
                # Larger canvas for better visibility
                canvas_t = MplCanvas(self, width=8, height=6)
                
                # Data for this original class
                legend_labels = []
                sizes = []
                colors = []
                total_orig = sum(targets.values())
                
                for target_class, count in sorted(targets.items()):
                    pct = (count / total_orig) * 100
                    legend_labels.append(f"→ LCZ {target_class}: {count} ({pct:.1f}%)")
                    sizes.append(count)
                    colors.append(LCZMappings.COLORS.get(target_class, '#bebebe'))
                
                # Plot without internal labels to avoid overlapping
                wedges, _ = canvas_t.axes.pie(sizes, 
                                startangle=140, 
                                colors=colors,
                                wedgeprops={'edgecolor': 'white', 'linewidth': 1.5})
                
                # Use a larger legend on the right
                canvas_t.axes.legend(wedges, legend_labels, 
                                   title="Destinazione Classi",
                                   loc="center left", 
                                   bbox_to_anchor=(1, 0, 0.5, 1), 
                                   fontsize=10, frameon=False)
                
                canvas_t.axes.set_title(f"Rettifica ESA: Evoluzione delle celle LCZ {orig_class}", 
                                      fontsize=13, fontweight='bold', pad=30)
                
                # Optimize layout space for long legend
                canvas_t.figure.subplots_adjust(left=0.05, right=0.65, top=0.85, bottom=0.05)
                
                c_layout.addWidget(canvas_t)
                scroll_layout.addWidget(chart_cont)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        main_layout.addWidget(self.create_info_box(
            "Interpretazione Correzione ESA",
            "I grafici a torta mostrano la 'migrazione' delle classi. "
            "Se molte celle LCZ A (Dense Trees) sono diventate LCZ D (Low Plants), significa che il sensore satellitare ha rilevato una densità di vegetazione inferiore a quella stimata dai parametri proxy."
        ))

        return tab

    def create_esa_comparison_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        if not HAS_MATPLOTLIB: return tab
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # --- Section 1: Scientific Consistency Index (The "Effective" Validation) ---
        coherence_container = QWidget()
        coh_layout = QVBoxLayout(coherence_container)
        
        coh_title = QLabel("Indice di Coerenza Scientifica (Stewart & Oke Compliance)")
        coh_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1565c0; margin-top: 5px;")
        coh_layout.addWidget(coh_title)
        
        coh_desc = QLabel("Questo indice misura la percentuale di celle i cui parametri ricadono nei range teorici. "
                          "Un aumento dell'indice dopo la correzione ESA indica un miglioramento della qualità scientifica.")
        coh_desc.setStyleSheet("font-size: 11px; color: #546e7a; margin-bottom: 10px;")
        coh_layout.addWidget(coh_desc)
        
        coh_chart_frame = QFrame()
        coh_chart_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 8px; border: 2px solid #1565c0;")
        coh_chart_frame.setMinimumHeight(350)
        coh_chart_layout = QVBoxLayout(coh_chart_frame)
        
        coh_canvas = MplCanvas(self, width=8, height=4)
        
        # Calculate Global Coherence per LCZ (average across all 10 params)
        all_lczs = sorted(list(set(self.stats['coherence_stats_pre'].keys()) | set(self.stats['coherence_stats_post'].keys())))
        
        global_pre = []
        global_post = []
        lcz_labels = []
        
        for lcz in all_lczs:
            pre_p = self.stats['coherence_stats_pre'].get(lcz, {})
            post_p = self.stats['coherence_stats_post'].get(lcz, {})
            
            if pre_p or post_p:
                lcz_labels.append(lcz)
                global_pre.append(np.mean(list(pre_p.values())) if pre_p else 0)
                global_post.append(np.mean(list(post_p.values())) if post_p else 0)
        
        if lcz_labels:
            x = np.arange(len(lcz_labels))
            width = 0.35
            
            # Use distinct colors for quality
            coh_canvas.axes.bar(x - width/2, global_pre, width, label='Qualità Originale (%)', color='#90a4ae', alpha=0.6)
            coh_canvas.axes.bar(x + width/2, global_post, width, label='Qualità Post-ESA (%)', color='#1565c0', alpha=0.9)
            
            # Add Delta Markers (Arrows or text)
            for i in range(len(lcz_labels)):
                delta = global_post[i] - global_pre[i]
                color = '#2e7d32' if delta >= 0 else '#c62828'
                prefix = '+' if delta >= 0 else ''
                coh_canvas.axes.text(x[i], max(global_pre[i], global_post[i]) + 2, f"{prefix}{delta:.1f}%", 
                                     ha='center', va='bottom', fontsize=8, fontweight='bold', color=color)
            
            coh_canvas.axes.set_xticks(x)
            coh_canvas.axes.set_xticklabels(lcz_labels)
            coh_canvas.axes.set_ylabel("Coerenza Scientifica (%)")
            coh_canvas.axes.set_ylim(0, 110)
            coh_canvas.axes.grid(axis='y', linestyle='--', alpha=0.3)
            coh_canvas.axes.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=2, fontsize=9, frameon=False)
            
            coh_chart_layout.addWidget(coh_canvas)
            coh_layout.addWidget(coh_chart_frame)
            content_layout.addWidget(coherence_container)
            
            # Separator
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("color: #cfd8dc; margin: 20px 0;")
            content_layout.addWidget(line)

        # --- Section 2: Detailed Mean Comparisons (The current charts) ---
        detailed_title = QLabel("Confronto Medie Parametri (Pre vs Post)")
        detailed_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50; margin-top: 10px;")
        content_layout.addWidget(detailed_title)
        
        # We compare all 10 parameters Before vs After
        params_to_compare = [
            ('building_surface_fraction', 'Building Fraction (%)'),
            ('sky_view_factor', 'SVF (0-1)'),
            ('impervious_surface_fraction', 'Impervious (%)'),
            ('pervious_surface_fraction', 'Pervious (%)'),
            ('height_roughness', 'Roughness H (m)'),
            ('aspect_ratio', 'Aspect Ratio (H/W)'),
            ('terrain_roughness', 'Terrain Roughness (z0)'),
            ('surface_albedo', 'Albedo (0-1)'),
            ('surface_admittance', 'Surface Admittance'),
            ('anthropogenic_heat', 'Anthro. Heat (W/m²)')
        ]
        
        for p_id, p_label in params_to_compare:
            container = QWidget()
            cont_layout = QVBoxLayout(container)
            
            title = QLabel(p_label)
            title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50; margin-top: 10px;")
            cont_layout.addWidget(title)
            
            chart_container = QFrame()
            chart_container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #dcdde1;")
            chart_container.setMinimumHeight(300)
            chart_layout = QVBoxLayout(chart_container)
            
            canvas = MplCanvas(self, width=8, height=4)
            
            # Combine classes from pre and post to have a complete X axis
            all_classes = sorted(list(set(self.stats['param_means'].keys()) | set(self.stats['param_means_pre'].keys())))
            
            vals_post = []
            vals_pre = []
            valid_x = []
            
            for lcz in all_classes:
                v_post = self.stats['param_means'].get(lcz, {}).get(p_id)
                v_pre = self.stats['param_means_pre'].get(lcz, {}).get(p_id)
                
                if v_post is not None or v_pre is not None:
                    valid_x.append(lcz)
                    vals_post.append(v_post if v_post is not None else 0)
                    vals_pre.append(v_pre if v_pre is not None else 0)
            
            if valid_x:
                x = np.arange(len(valid_x))
                width = 0.35
                
                canvas.axes.bar(x - width/2, vals_pre, width, label='Prima (Originale)', color='#bdc3c7', alpha=0.7)
                canvas.axes.bar(x + width/2, vals_post, width, label='Dopo (ESA Corrected)', color='#3498db', alpha=0.8)
                
                canvas.axes.set_xticks(x)
                canvas.axes.set_xticklabels(valid_x)
                canvas.axes.legend(fontsize=9, frameon=False, loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=2)
                canvas.axes.set_ylabel("Media")
                
                chart_layout.addWidget(canvas)
                cont_layout.addWidget(chart_container)
                content_layout.addWidget(container)

        layout.addWidget(self.create_info_box(
            "Validazione Scientifica Post-Correzione",
            "Questi grafici permettono di verificare se il rimescolamento delle classi LCZ operato da ESA WorldCover altera significativamente le medie morfologiche. "
            "Idealmente, le barre dovrebbero essere simili: se noti scostamenti enormi, significa che la correzione ESA ha spostato molte celle in classi che non rispecchiano i parametri locali calcolati."
        ))
        
        return tab

    def create_validation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #f1f2f6; border-radius: 8px; padding: 15px;")
        h_layout = QVBoxLayout(header_box)
        
        title = QLabel("Modulo di Validazione Scientifica Globale")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        h_layout.addWidget(title)
        
        desc = QLabel("Questo modulo confronta i tuoi risultati FETCH con i benchmark globali standard della comunità scientifica (WUDAPT e AH4GUC).")
        desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        desc.setWordWrap(True)
        h_layout.addWidget(desc)
        
        self.run_val_btn = QPushButton("Esegui Validazione Globale (WUDAPT & AH4GUC)")
        self.run_val_btn.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; border-radius: 4px; padding: 10px; font-weight: bold; margin-top: 10px; }
            QPushButton:hover { background-color: #219150; }
        """)
        self.run_val_btn.clicked.connect(self.run_global_validation)
        h_layout.addWidget(self.run_val_btn)
        
        layout.addWidget(header_box)
        
        # Results container
        self.val_report_scroll = QScrollArea()
        self.val_report_scroll.setWidgetResizable(True)
        self.val_report_content = QLabel("Clicca sul pulsante sopra per avviare il confronto con i dataset globali.\nRegistra l'accordo spaziale con WUDAPT e la coerenza del calore antropogenico con AH4GUC.")
        self.val_report_content.setStyleSheet("padding: 20px; color: #95a5a6; font-style: italic;")
        self.val_report_content.setAlignment(Qt.AlignCenter)
        self.val_report_scroll.setWidget(self.val_report_content)
        
        layout.addWidget(self.val_report_scroll)
        
        return tab

    def run_global_validation(self):
        """Runs the external validation logic."""
        from ...core.processors.lcz.validator import LCZValidator
        
        grid_layer = self.parent().find_valid_grid_layer() if self.parent() else None
        if not grid_layer:
            self.val_report_content.setText("✗ Impossibile trovare il layer della griglia.")
            return

        self.run_val_btn.setEnabled(False)
        self.run_val_btn.setText("Validazione in corso...")
        
        validator = LCZValidator(None)
        success, results = validator.validate_layer(grid_layer)
        
        if success:
            report_text = results['summary']
            # Simple conversion to HTML for rich display in QLabel
            report_html = "<html><body>"
            for line in report_text.split('\n'):
                if line.startswith('###'):
                    report_html += f"<h2>{line[3:].strip()}</h2>"
                elif line.startswith('**'):
                    report_html += f"<b>{line.strip('* ')}</b><br>"
                elif line.startswith('*'):
                    report_html += f"<i>{line.strip('* ')}</i><br>"
                elif line.startswith('✓'):
                    report_html += f"<font color='green'>{line}</font><br>"
                elif line.startswith('⚠'):
                    report_html += f"<font color='orange'>{line}</font><br>"
                else:
                    report_html += f"{line}<br>"
            report_html += "</body></html>"
            
            self.val_report_content.setText(report_html)
            self.val_report_content.setStyleSheet("padding: 20px; color: #2c3e50; font-family: sans-serif;")
            self.val_report_content.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        else:
            self.val_report_content.setText(f"✗ Errore durante la validazione: {results}")

        self.run_val_btn.setEnabled(True)
        self.run_val_btn.setText("Esegui Nuova Validazione")

    def export_to_pdf(self):
        from qgis.PyQt.QtWidgets import QFileDialog
        import os
        
        # Try to suggest a safe path (Home folder if possible)
        home = os.path.expanduser("~")
        default_path = os.path.join(home, "Report_FETCH_LCZ.pdf")
        
        path, _ = QFileDialog.getSaveFileName(self, "Esporta Report Statistiche", default_path, "PDF Files (*.pdf)")
        if not path:
            return
            
        try:
            with PdfPages(path) as pdf:
                # 1. Front Page
                fig_cover = Figure(figsize=(8.27, 11.69)) # A4
                fig_cover.text(0.5, 0.7, "Report Analisi Climatica Locale", fontsize=24, fontweight='bold', ha='center')
                fig_cover.text(0.5, 0.65, "FETCH - Framework for Environmental Type Classification Hub", fontsize=14, ha='center', color='#7f8c8d')
                
                # Context info
                total_cells = sum(self.stats['lcz_counts'].values())
                total_ha = total_cells * 0.09
                counts = self.stats['lcz_counts']
                dominant = max(counts, key=counts.get) if counts else "N/D"
                
                from datetime import datetime
                now = datetime.now().strftime("%d/%m/%Y %H:%M")
                
                info_text = (
                    f"Superficie Analizzata: {total_ha:.1f} ha\n"
                    f"Numero Totale Celle: {total_cells}\n"
                    f"Classe LCZ Dominante: LCZ {dominant}\n"
                    f"Data di Generazione: {now}"
                )
                fig_cover.text(0.5, 0.4, info_text, fontsize=12, ha='center', linespacing=2)
                
                pdf.savefig(fig_cover)
                plt.close(fig_cover)
                
                # 2. Distribution Page
                fig_dist = Figure(figsize=(8.27, 11.69))
                ax = fig_dist.add_subplot(211)
                labels = sorted(self.stats['lcz_counts'].keys())
                counts_list = [self.stats['lcz_counts'][l] for l in labels]
                colors = [LCZMappings.COLORS.get(l, '#bebebe') for l in labels]
                ax.bar(labels, counts_list, color=colors, edgecolor='black', linewidth=0.5)
                ax.set_title("Distribuzione Classi LCZ (Frequenza)", fontsize=14, fontweight='bold', pad=20)
                ax.set_ylabel("Numero di celle")
                
                # Add scientific note
                note = "Distribuzione spaziale delle classi. Valori elevati in classi 1-6 indicano aree urbanizzate."
                fig_dist.text(0.1, 0.45, "Interpretazione: " + note, fontsize=10, style='italic', wrap=True)
                
                pdf.savefig(fig_dist)
                plt.close(fig_dist)
                
                # 3. Parameters Pages
                all_param_groups = [
                    ("Morfologia Urbana", [
                        ('building_surface_fraction', 'Building Frac (%)'),
                        ('sky_view_factor', 'SVF (0-1)'),
                        ('impervious_surface_fraction', 'Impervious (%)'),
                        ('pervious_surface_fraction', 'Pervious (%)'),
                        ('height_roughness', 'Roughness H (m)'),
                        ('aspect_ratio', 'Aspect Ratio (H/W)'),
                        ('terrain_roughness', 'Terrain Roughness (z0)')
                    ]), 
                    ("Proprietà Fisiche", [
                        ('surface_albedo', 'Albedo (0-1)'),
                        ('surface_admittance', 'Surface Admittance'),
                        ('anthropogenic_heat', 'Anthro. Heat (W/m²)')
                    ])
                ]

                for group_name, params in all_param_groups:
                    # Grouping 3 charts per page for better readability in A4
                    for i in range(0, len(params), 3):
                        fig_p = Figure(figsize=(8.27, 11.69))
                        fig_p.suptitle(f"{group_name} (Parte {i//3 + 1})", fontsize=16, fontweight='bold', y=0.95)
                        
                        chunk = params[i:i+3]
                        for k, (p_id, p_label) in enumerate(chunk):
                            ax = fig_p.add_subplot(3, 1, k+1)
                            valid_classes = []
                            values = []
                            colors_p = []
                            for lcz in sorted(self.stats['param_means'].keys()):
                                if p_id in self.stats['param_means'][lcz]:
                                    valid_classes.append(lcz)
                                    values.append(self.stats['param_means'][lcz][p_id])
                                    colors_p.append(LCZMappings.COLORS.get(lcz, '#bebebe'))
                            
                            if values:
                                ax.bar(valid_classes, values, color=colors_p, alpha=0.7)
                                # Draw ref ranges (simplified for PDF)
                                for j, lcz in enumerate(valid_classes):
                                    lcz_ref = LCZMappings.PARAMETERS.get(lcz, {})
                                    if p_id in lcz_ref:
                                        p_min, p_max = lcz_ref[p_id]
                                        disp_max = p_max if p_max != float('inf') else p_min * 1.5
                                        ax.vlines(j, p_min, disp_max, color='#2c3e50', alpha=0.5, linewidth=3)
                                
                                ax.set_title(p_label, fontsize=11, fontweight='bold')
                                ax.tick_params(labelsize=8)
                        
                        fig_p.tight_layout(rect=[0, 0.03, 1, 0.92])
                        pdf.savefig(fig_p)
                        plt.close(fig_p)

                # 4. ESA Correction Page
                fig_esa = Figure(figsize=(8.27, 11.69))
                ax_p = fig_esa.add_subplot(211)
                corrected = self.stats['esa_correction']['corrected']
                total = self.stats['esa_correction']['total']
                if total > 0:
                    ax_p.pie([corrected, total-corrected], labels=['Corrette ESA', 'Originali'], colors=['#3498db', '#ecf0f1'], autopct='%1.1f%%')
                    ax_p.set_title("Impatto Correzione ESA WorldCover", fontsize=14, fontweight='bold')
                
                pdf.savefig(fig_esa)
                plt.close(fig_esa)
                
                # 5. ESA Detailed Transitions Pages
                transitions = self.stats['esa_correction'].get('transitions', {})
                if transitions:
                    # Grouping 2 charts per page for good visibility in A4
                    orig_classes = sorted(transitions.keys())
                    for i in range(0, len(orig_classes), 2):
                        fig_trans = Figure(figsize=(8.27, 11.69))
                        fig_trans.suptitle("Dettaglio Transizioni ESA (Evoluzione Classi)", fontsize=16, fontweight='bold', y=0.95)
                        
                        chunk = orig_classes[i:i+2]
                        for j, orig_class in enumerate(chunk):
                            ax = fig_trans.add_subplot(2, 1, j+1)
                            targets = transitions[orig_class]
                            
                            legend_labels = []
                            sizes = []
                            colors_t = []
                            total_orig = sum(targets.values())
                            
                            for target_class, count in sorted(targets.items()):
                                pct = (count / total_orig) * 100
                                legend_labels.append(f"→ LCZ {target_class}: {count} ({pct:.1f}%)")
                                sizes.append(count)
                                colors_t.append(LCZMappings.COLORS.get(target_class, '#bebebe'))
                            
                            wedges, _ = ax.pie(sizes, startangle=140, colors=colors_t, 
                                             wedgeprops={'edgecolor': 'white', 'linewidth': 1})
                            
                            ax.legend(wedges, legend_labels, title="Destinazione", 
                                     loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), 
                                     fontsize=9, frameon=False)
                            
                            ax.set_title(f"Evoluzione celle LCZ {orig_class}", fontsize=12, fontweight='bold')
                        
                        fig_trans.tight_layout(rect=[0, 0.03, 1, 0.92])
                        pdf.savefig(fig_trans)
                        plt.close(fig_trans)
                # 6. Scientific Consistency Index Page (Validation Summary)
                fig_coh = Figure(figsize=(8.27, 11.69))
                fig_coh.suptitle("Indice di Coerenza Scientifica (Qualità Globale)", fontsize=16, fontweight='bold', y=0.95)
                
                ax_c = fig_coh.add_subplot(211)
                all_l = sorted(list(set(self.stats['coherence_stats_pre'].keys()) | set(self.stats['coherence_stats_post'].keys())))
                g_pre = [np.mean(list(self.stats['coherence_stats_pre'].get(l, {}).values())) if self.stats['coherence_stats_pre'].get(l) else 0 for l in all_l]
                g_post = [np.mean(list(self.stats['coherence_stats_post'].get(l, {}).values())) if self.stats['coherence_stats_post'].get(l) else 0 for l in all_l]
                
                x = np.arange(len(all_l))
                ax_c.bar(x - 0.2, g_pre, 0.4, label='Qualità Originale (%)', color='#90a4ae', alpha=0.6)
                ax_c.bar(x + 0.2, g_post, 0.4, label='Qualità Post-ESA (%)', color='#1565c0', alpha=0.9)
                
                # Add Delta Markers (Annotations)
                for i in range(len(all_l)):
                    delta = g_post[i] - g_pre[i]
                    color = '#2e7d32' if delta >= 0 else '#c62828'
                    prefix = '+' if delta >= 0 else ''
                    ax_c.text(x[i], max(g_pre[i], g_post[i]) + 2, f"{prefix}{delta:.1f}%", 
                             ha='center', va='bottom', fontsize=7, fontweight='bold', color=color)
                
                ax_c.set_xticks(x)
                ax_c.set_xticklabels(all_l, fontsize=8)
                ax_c.set_ylabel("Coerenza (%)")
                ax_c.set_ylim(0, 110)
                ax_c.grid(axis='y', linestyle='--', alpha=0.3)
                ax_c.set_title("Percentuale di celle nei range di Stewart & Oke", fontsize=12)
                ax_c.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=2, fontsize=9, frameon=False)
                
                note_coh = "L'indice rappresenta il grado di conformità del modello alla teoria climatica. Un delta positivo indica una correzione efficace."
                fig_coh.text(0.1, 0.45, "Commento Tecnico: " + note_coh, fontsize=10, style='italic', wrap=True)
                
                pdf.savefig(fig_coh)
                plt.close(fig_coh)

                # 7. ESA Validation Detailed (All 10 params with pagination)
                val_params = [
                    ('building_surface_fraction', 'Building Fraction (%)'),
                    ('sky_view_factor', 'SVF (0-1)'),
                    ('impervious_surface_fraction', 'Impervious (%)'),
                    ('pervious_surface_fraction', 'Pervious (%)'),
                    ('height_roughness', 'Roughness H (m)'),
                    ('aspect_ratio', 'Aspect Ratio (H/W)'),
                    ('terrain_roughness', 'Terrain Roughness (z0)'),
                    ('surface_albedo', 'Albedo (0-1)'),
                    ('surface_admittance', 'Surface Admittance'),
                    ('anthropogenic_heat', 'Anthro. Heat (W/m²)')
                ]
                
                for i in range(0, len(val_params), 2): # 2 comparison charts per page
                    fig_val = Figure(figsize=(8.27, 11.69))
                    fig_val.suptitle(f"Validazione Post-ESA (Confronto Medie) - Parte {i//2 + 1}", fontsize=16, fontweight='bold', y=0.95)
                    
                    chunk = val_params[i:i+2]
                    for k, (p_id, p_label) in enumerate(chunk):
                        ax_v = fig_val.add_subplot(2, 1, k+1)
                        all_cls = sorted(list(set(self.stats['param_means'].keys()) | set(self.stats['param_means_pre'].keys())))
                        v_pre = [self.stats['param_means_pre'].get(l, {}).get(p_id, 0) for l in all_cls]
                        v_post = [self.stats['param_means'].get(l, {}).get(p_id, 0) for l in all_cls]
                        
                        x = np.arange(len(all_cls))
                        width = 0.35
                        ax_v.bar(x - width/2, v_pre, width, label='Originale', color='#bdc3c7', alpha=0.7)
                        ax_v.bar(x + width/2, v_post, width, label='Corrected', color='#3498db', alpha=0.8)
                        
                        ax_v.set_xticks(x)
                        ax_v.set_xticklabels(all_cls, fontsize=8)
                        ax_v.set_title(p_label, fontsize=12, fontweight='bold')
                        ax_v.legend(loc='upper center', bbox_to_anchor=(0.5, 1.2), ncol=2, fontsize=8, frameon=False)
                    
                    fig_val.tight_layout(rect=[0, 0.03, 1, 0.92])
                    pdf.savefig(fig_val)
                    plt.close(fig_val)

            QgsMessageLog.logMessage(f"Report PDF salvato correttamente in: {path}", "FETCH", Qgis.Success)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Errore durante l'esportazione PDF: {e}", "FETCH", Qgis.Critical)

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
