# -*- coding: utf-8 -*-

import os
import processing
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, Qgis, QgsMessageLog, QgsGeometry
)
from ..constants import LCZMappings

class VectorProcessor:
    def __init__(self, data_manager):
        self.dm = data_manager

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def process_dataset(self, folder_path, config, output_path, target_crs, target_extent):
        """Process vector data: reproject and clip to AOI (Optimized: Clip -> Reproject)."""
        import glob
        import time
        from qgis.core import (
            QgsVectorLayer, QgsProcessingContext, QgsFeatureRequest, 
            QgsCoordinateTransform, QgsProject, QgsCoordinateReferenceSystem
        )
        
        start_time = time.time()
        pattern = os.path.join(folder_path, config["pattern"])
        self.log(f"Process dataset: {folder_path} (pattern: {config['pattern']})")
        all_files = glob.glob(pattern)
        if not all_files: 
            self.log("Nessun file trovato matching il pattern.")
            return False
            
        # Filter by valid vector extensions
        valid_exts = ('.parquet', '.gpkg', '.json', '.geojson', '.shp', '.kml')
        input_files = [f for f in all_files if f.lower().endswith(valid_exts)]
        
        if not input_files:
            self.log(f"Nessun file vettoriale valido trovato tra i {len(all_files)} file presenti.")
            return False

        # Prioritization: if a merged/AOI file exists, use it exclusively to avoid duplicates
        aoi_files = [f for f in input_files if "_aoi" in os.path.basename(f).lower()]
        if aoi_files:
            self.log(f"Priorità: Uso file AOI già pronto: {os.path.basename(aoi_files[0])}")
            input_files = [aoi_files[0]]
        
        # Prepare processing context with geometry validation fallback
        context = QgsProcessingContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
        
        # Determine the source layer (merge if multiple files found)
        if len(input_files) > 1:
            self.log(f"Inizializzazione di {len(input_files)} layer per l'unione...")
            layers_to_merge = []
            for f in input_files:
                l = QgsVectorLayer(f, os.path.basename(f), "ogr")
                if l.isValid():
                    layers_to_merge.append(l)
                else:
                    self.log(f"Salto file non caricabile: {os.path.basename(f)}", Qgis.Warning)
            
            if not layers_to_merge:
                self.log("Nessun layer valido trovato per l'unione.", Qgis.Critical)
                return False
                
            self.log(f"Unione di {len(layers_to_merge)} layer validi...")
            try:
                res_merge = processing.run("native:mergevectorlayers", {
                    'LAYERS': layers_to_merge,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }, context=context)
                assigned_layer = res_merge['OUTPUT']
            except Exception as e:
                self.log(f"Errore durante l'unione (mergevectorlayers): {str(e)}", Qgis.Critical)
                return False
        else:
            input_file = input_files[0]
            self.log(f"Caricamento file sorgente: {os.path.basename(input_file)}")
            layer = QgsVectorLayer(input_file, "temp_input", "ogr")
            if not layer.isValid():
                self.log(f"Layer non valido: {input_file}", Qgis.Critical)
                return False
            assigned_layer = layer
            
        # Ensure CRS is set (fallback to EPSG:4326 if unknown/missing)
        if not assigned_layer.crs().isValid() or assigned_layer.crs().authid() == "":
            self.log(f"Layer {assigned_layer.name()} senza CRS definito. Assegnazione EPSG:4326...")
            try:
                res_assigned = processing.run("native:assignprojection", {
                    'INPUT': assigned_layer,
                    'CRS': QgsCoordinateReferenceSystem("EPSG:4326"),
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }, context=context)
                assigned_layer = res_assigned['OUTPUT']
            except Exception as e:
                self.log(f"Errore assegnazione CRS: {str(e)}")
        
        # OPTIMIZATION: CLIP -> REPROJECT -> FIX
        
        # Step 1/4: Back-transform extent and Clip in Source CRS
        source_crs = assigned_layer.crs()
        target_crs_obj = QgsCoordinateReferenceSystem(target_crs)
        self.log(f"Step 1/4: Ritaglio in CRS sorgente ({source_crs.authid()})...")
        
        try:
            # Transform target_extent (UTM) back to source CRS (usually 4326)
            transform = QgsCoordinateTransform(target_crs_obj, source_crs, QgsProject.instance())
            source_extent = transform.transformBoundingBox(target_extent)
            
            res_clip = processing.run("native:extractbyextent", {
                'INPUT': assigned_layer,
                'EXTENT': source_extent,
                'CLIP': True,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }, context=context)
            clipped_layer = res_clip['OUTPUT']
            self.log(f" -> Ritaglio completato: {clipped_layer.featureCount()} features restanti.")
        except Exception as e:
            self.log(f"Errore Step 1 (Optimized Clip): {str(e)}. Provo reprojection classica...", Qgis.Warning)
            clipped_layer = assigned_layer # Fallback if back-transform fails
            
        # Step 2/4: Reproject to Target CRS (Only the clipped subset)
        self.log(f"Step 2/4: Riproiezione a {target_crs}...")
        try:
            res_repro = processing.run("native:reprojectlayer", {
                'INPUT': clipped_layer, 
                'TARGET_CRS': target_crs, 
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }, context=context)
            repro_layer = res_repro['OUTPUT']
        except Exception as e:
            self.log(f"Errore Step 2 (Reproject): {str(e)}", Qgis.Critical)
            return False
        
        # Step 3/4: Fix Geometries
        self.log(f"Step 3/4: Correzione geometrie...")
        try:
            res_fixed = processing.run("native:fixgeometries", {
                'INPUT': repro_layer,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }, context=context)
            fixed_layer = res_fixed['OUTPUT']
        except Exception as e:
            self.log(f"Errore Step 3 (Fix): {str(e)}", Qgis.Critical)
            return False
        
        # Step 4/4: Final Save to output_path and Spatial Index
        self.log(f"Step 4/4: Salvataggio finale e indicizzazione...")
        try:
            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            processing.run("native:savefeatures", {
                'INPUT': fixed_layer,
                'OUTPUT': output_path
            }, context=context)
            
            if os.path.exists(output_path):
                processing.run("native:createspatialindex", {
                    'INPUT': output_path
                }, context=context)
                
                result_layer = QgsVectorLayer(output_path, "temp_result", "ogr")
                if result_layer.isValid():
                    duration = time.time() - start_time
                    self.log(f"✓ Completato in {duration:.1f}s: {os.path.basename(output_path)} ({result_layer.featureCount()} f.)")
                else:
                    self.log(f"✗ Layer finale creato ma non valido", Qgis.Critical)
            else:
                self.log(f"❌ Errore: File di output non generato", Qgis.Critical)
        except Exception as e:
            self.log(f"Errore Step 4 (Save): {str(e)}", Qgis.Critical)
            
        return os.path.exists(output_path)





    def create_lcz_grid(self, extent, crs_auth_id, cell_size=100, log_callback=None):
        """Crea una griglia regolare per la classificazione LCZ."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        base_dir = self.dm.get_project_dir()
        if not base_dir: return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        output_path = os.path.join(unified_dir, f"lcz_grid_{cell_size}m.gpkg")
        
        if os.path.exists(output_path):
            return True, f"Griglia {cell_size}m già presente", output_path

        log_local(f"Creazione griglia LCZ {cell_size}x{cell_size}m...")
        
        # Ensure extent is in a metric CRS for grid creation
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        if not source_crs.isGeographic():
             metric_crs = source_crs
             metric_extent = extent
        else:
             from ..utils import get_utm_zone_for_extent
             metric_crs_auth = get_utm_zone_for_extent(extent, crs_auth_id)
             metric_crs = QgsCoordinateReferenceSystem(metric_crs_auth)
             transform = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())
             metric_extent = transform.transformBoundingBox(extent)

        # Create grid
        grid_res = processing.run("native:creategrid", {
            'TYPE': 2, # Rectangle (Polygon)
            'EXTENT': f"{metric_extent.xMinimum()},{metric_extent.xMaximum()},{metric_extent.yMinimum()},{metric_extent.yMaximum()}",
            'HSPACING': cell_size, 'VSPACING': cell_size, 'HOVERLAP': 0, 'VOVERLAP': 0,
            'CRS': metric_crs, 'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        grid_layer = grid_res['OUTPUT']
        
        # Add required LCZ fields
        from qgis.core import QgsField
        from qgis.PyQt.QtCore import QVariant, QMetaType
        fields = [
            QgsField("lcz_class", QMetaType.QString, len=10),
            QgsField("lcz_vulnerability", QMetaType.QString, len=20),
            QgsField("lcz_score", QMetaType.Double),
            QgsField("lcz_rmsep", QMetaType.Double),
            QgsField("lcz_confidence", QMetaType.Double),
            QgsField("lcz_matches", QMetaType.Int),
            QgsField("lcz_esa_fix", QMetaType.QString, len=12),
            QgsField("svf_mean", QMetaType.Double),
            QgsField("building_frac", QMetaType.Double),
            QgsField("impervious_frac", QMetaType.Double),
            QgsField("pervious_frac", QMetaType.Double),
            QgsField("aspect_ratio", QMetaType.Double),
            QgsField("z_h", QMetaType.Double),
            QgsField("terrain_rough", QMetaType.Int),
            QgsField("admittance", QMetaType.Double),
            QgsField("anthro_heat", QMetaType.Double),
            QgsField("albedo", QMetaType.Double)
        ]
        
        # Add Distance fields for diagnostic analysis
        for lcz_id in LCZMappings.CLASSES.keys():
            fields.append(QgsField(f"dist_{lcz_id}", QMetaType.Double))
            
        grid_layer.dataProvider().addAttributes(fields)
        grid_layer.updateFields()
        
        # Save to file
        processing.run("native:savefeatures", {
            'INPUT': grid_layer, 'OUTPUT': output_path
        })
        
        return True, "Griglia creata con successo", output_path

    def use_existing_grid(self, layer, extent, crs_auth_id, log_callback=None):
        """Usa un layer vettoriale esistente come griglia LCZ."""
        def log_local(msg):
            if log_callback: log_callback(msg)
            self.log(msg)

        if not layer or not layer.isValid():
            return False, "Layer non valido", None
        
        base_dir = self.dm.get_project_dir()
        if not base_dir: return False, "Progetto non salvato", None
        
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified")
        output_path = os.path.join(unified_dir, "lcz_grid_custom.gpkg")
        
        if os.path.exists(output_path):
            os.remove(output_path)
        
        log_local(f"Usando layer esistente: {layer.name()}")
        
        from ..utils import get_utm_zone_for_extent
        target_crs_auth = get_utm_zone_for_extent(extent, crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem(target_crs_auth)
        
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        utm_extent = transform.transformBoundingBox(extent)
        
        try:
            input_for_clip = layer
            if layer.crs() != target_crs:
                log_local(f"Riproiezione da {layer.crs().authid()} a {target_crs_auth}...")
                temp_reprojected = os.path.join(unified_dir, "temp_grid_reprojected.gpkg")
                processing.run("native:reprojectlayer", {
                    'INPUT': layer, 'TARGET_CRS': target_crs, 'OUTPUT': temp_reprojected
                })
                input_for_clip = temp_reprojected
            
            log_local("Ritaglio sull'estensione AOI...")
            extent_str = f"{utm_extent.xMinimum()},{utm_extent.xMaximum()},{utm_extent.yMinimum()},{utm_extent.yMaximum()}"
            processing.run("native:extractbyextent", {
                'INPUT': input_for_clip, 'EXTENT': extent_str, 'CLIP': True, 'OUTPUT': output_path
            })
            
            if input_for_clip != layer and os.path.exists(input_for_clip):
                os.remove(input_for_clip)
            
            from qgis.core import QgsVectorLayer
            result_layer = QgsVectorLayer(output_path, "temp", "ogr")
            if result_layer.isValid():
                return True, f"Griglia custom con {result_layer.featureCount()} celle", output_path
            return False, "Layer risultante non valido", None
        except Exception as e:
            return False, f"Errore: {str(e)}", None
