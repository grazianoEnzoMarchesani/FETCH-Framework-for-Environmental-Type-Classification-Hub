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

    def export_to_pdf(self):
        from qgis.PyQt.QtWidgets import QFileDialog
        import os
        
        path, _ = QFileDialog.getSaveFileName(self, "Esporta Report Statistiche", "Report_FETCH_LCZ.pdf", "PDF Files (*.pdf)")
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
                
                info_text = (
                    f"Superficie Analizzata: {total_ha:.1f} ha\n"
                    f"Numero Totale Celle: {total_cells}\n"
                    f"Classe LCZ Dominante: LCZ {dominant}\n"
                    f"Data Report: {QColor(Qt.white).name()} (Sistema)" # Placeholder for real date if needed
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
                
                # 3. Parameters Pages (1 for Morph, 1 for Phys)
                for group_name, params in [("Morfologia Urbana", [
                    ('building_surface_fraction', 'Building Frac (%)'),
                    ('sky_view_factor', 'SVF (0-1)'),
                    ('height_roughness', 'Roughness H (m)'),
                    ('aspect_ratio', 'Aspect Ratio (H/W)')
                ]), ("Proprietà Fisiche", [
                    ('surface_albedo', 'Albedo (0-1)'),
                    ('surface_admittance', 'Surface Admittance'),
                    ('anthropogenic_heat', 'Anthro. Heat (W/m²)')
                ])]:
                    fig_p = Figure(figsize=(8.27, 11.69))
                    fig_p.suptitle(group_name, fontsize=16, fontweight='bold', y=0.95)
                    
                    for i, (p_id, p_label) in enumerate(params):
                        ax = fig_p.add_subplot(4, 1, i+1)
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
                            
                            ax.set_title(p_label, fontsize=10)
                    
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

            from ...core.stats_aggregator import QgsMessageLog, Qgis # Using aggregator's alias
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
