# -*- coding: utf-8 -*-
"""
LCZ Global Validator (REAL ENGINE)

Performs pixel-to-pixel validation against WUDAPT Global LCZ map.
"""

from ...downloaders.wudapt import WudaptDownloader
from qgis.core import (QgsProject, QgsRectangle, QgsCoordinateReferenceSystem, 
                       QgsCoordinateTransform, QgsFeatureRequest, QgsMessageLog, Qgis)

class LCZValidator:
    def __init__(self, data_manager):
        self.dm = data_manager
        self.wudapt = WudaptDownloader(data_manager)
        
    def validate_layer(self, layer, log_callback=None):
        def log(msg):
            if log_callback: log_callback(msg)
            QgsMessageLog.logMessage(msg, "FETCH", Qgis.Info)

        log("📊 Avvio Validazione REALE con WUDAPT Global LCZ...")
        
        # 1. Transform setup
        source_crs = layer.crs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84_crs, QgsProject.instance())
        
        # 2. Iteration: Compute for ALL features
        total = layer.featureCount()
        matches = 0
        total_valid = 0
        
        features = list(layer.getFeatures())
        samples = features # Now using all features
        
        log(f"Avvio analisi su {len(samples)} celle (copertura totale)...")
        
        lcz_field = 'lcz_class'
        accuracy_matrix = {} # {fetch_lcz: {wudapt_lcz: count}}
        processed_count = 0
        for feat in samples:
            processed_count += 1
            if processed_count % 500 == 0:
                log(f"Analisi in corso: {processed_count}/{total} celle...")
                
            fetch_lcz = str(feat.attribute(lcz_field))
            if fetch_lcz in (None, 'NULL', 'ERRORE'): continue
            
            # Get centroid in WGS84
            geom = feat.geometry()
            centroid = geom.centroid().asPoint()
            w_pt = transform.transform(centroid)
            
            # Sample WUDAPT
            wudapt_lcz = self.wudapt.get_lcz_at(w_pt.y(), w_pt.x())
            
            if wudapt_lcz:
                total_valid += 1
                if fetch_lcz == wudapt_lcz:
                    matches += 1
                
                # Matrix stats
                if fetch_lcz not in accuracy_matrix: accuracy_matrix[fetch_lcz] = {}
                accuracy_matrix[fetch_lcz][wudapt_lcz] = accuracy_matrix[fetch_lcz].get(wudapt_lcz, 0) + 1

        if total_valid == 0:
            return False, "Impossibile connettersi a WUDAPT o area fuori copertura."

        agreement_pct = (matches / total_valid) * 100
        
        # Build Report
        report = (
            "### Report di Validazione REALE (WUDAPT)\n\n"
            f"**Indice di Accordo Globale:** {agreement_pct:.1f}%\n"
            f"*Campioni analizzati: {total_valid} celle griglia.*\n\n"
            "**Dettaglio per classe (Top Match):**\n"
        )
        
        for fetch_lcz, w_counts in sorted(accuracy_matrix.items()):
            top_w = max(w_counts, key=w_counts.get)
            top_pct = (w_counts[top_w] / sum(w_counts.values())) * 100
            status = "✓" if fetch_lcz == top_w else "⚠"
            report += f"- LCZ {fetch_lcz}: {status} Concorda con WUDAPT {top_w} ({top_pct:.0f}%)\n"
            
        report += "\n**Nota Scientifica:** FETCH utilizza dati locali a 10m/30m, mentre WUDAPT è un prodotto globale a 100m. Una concordanza > 70% è considerata eccellente."
        
        return True, {'summary': report, 'agreement': agreement_pct}
