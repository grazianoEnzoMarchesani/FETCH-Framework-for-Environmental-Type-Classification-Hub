# -*- coding: utf-8 -*-

import os
import processing
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform, Qgis, QgsMessageLog, QgsGeometry
)

class VectorProcessor:
    def __init__(self, data_manager):
        self.dm = data_manager

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def process_dataset(self, folder_path, config, output_path, target_crs, target_extent):
        """Process vector data: reproject and clip to AOI."""
        import glob
        from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsFeature
        
        pattern = os.path.join(folder_path, config["pattern"])
        input_files = glob.glob(pattern)
        if not input_files: return False
        
        input_file = input_files[0]
        # Load the input layer
        layer = QgsVectorLayer(input_file, "temp_input", "ogr")
        if not layer.isValid():
            self.log(f"Layer non valido: {input_file}", Qgis.Critical)
            return False
            
        # Ensure CRS is set (fallback to EPSG:4326 if unknown/missing)
        if not layer.crs().isValid():
            self.log(f"CRS non valido per {os.path.basename(input_file)}. Imposto EPSG:4326 come fallback.", Qgis.Warning)
            layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        
        # Prepare processing context with geometry validation fallback
        from qgis.core import QgsProcessingContext, QgsFeatureRequest, QgsProcessing
        context = QgsProcessingContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
        
        # Step 0: Projection Safety Check
        if not layer.crs().isValid() or layer.crs().authid() == "":
            self.log(f"Assegnazione CRS 4326 a layer sorgente senza metadati...")
            res_assigned = processing.run("native:assignprojection", {
                'INPUT': layer,
                'CRS': QgsCoordinateReferenceSystem("EPSG:4326"),
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }, context=context)
            assigned_layer = res_assigned['OUTPUT']
        else:
            assigned_layer = layer
        
        # Step 1/4: Reproject to Target CRS (Internal Layer)
        res_repro = processing.run("native:reprojectlayer", {
            'INPUT': assigned_layer, 
            'TARGET_CRS': target_crs, 
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context)
        repro_layer = res_repro['OUTPUT']
        
        # Diagnostic Log: verify coordinate range in UTM
        repro_ext = repro_layer.extent()
        self.log(f"Step 1/4 (Reproject): {repro_layer.featureCount()} features a {target_crs}")
        self.log(f" -> Extent UTM: {repro_ext.xMinimum():.1f}, {repro_ext.yMinimum():.1f}")
        
        # Step 2/4: Fix Geometries (Internal Layer)
        res_fixed = processing.run("native:fixgeometries", {
            'INPUT': repro_layer,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context)
        fixed_layer = res_fixed['OUTPUT']
        self.log(f"Step 2/4 (Fix): {fixed_layer.featureCount()} geometrie riparate")
        
        # Step 3/4: Clip to extent (Final File)
        # Usage of object-based Extent avoids locale/precision issues
        processing.run("native:extractbyextent", {
            'INPUT': fixed_layer,
            'EXTENT': target_extent, 
            'CLIP': True, 
            'OUTPUT': output_path
        }, context=context)
        
        # Step 4/4: Create Spatial Index (Crucial for visibility/rendering)
        if os.path.exists(output_path):
            processing.run("native:createspatialindex", {
                'INPUT': output_path
            }, context=context)
            
            # Final validation check
            result_layer = QgsVectorLayer(output_path, "temp_result", "ogr")
            if result_layer.isValid():
                self.log(f"Step 3/4 (Clip): {result_layer.featureCount()} features salvate in {os.path.basename(output_path)}")
                self.log(f"Step 4/4 (Index): Indice spaziale creato per {os.path.basename(output_path)}")
            else:
                self.log(f"ERRORE: Layer finale non valido: {output_path}", Qgis.Critical)
        else:
            self.log(f"ERRORE: Output non creato in {output_path}", Qgis.Critical)
            
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
            QgsField("lcz_class", QMetaType.QString, len=10),  # String for LCZ codes: "1"-"10", "A"-"G"
            QgsField("lcz_vulnerability", QMetaType.QString, len=20), # UHI Vulnerability: "Very High" to "Very Low"
            QgsField("lcz_rmsep", QMetaType.Double),           # RMSEP value for classification quality
            QgsField("lcz_matches", QMetaType.Int),            # Number of perfect parameter matches
            QgsField("lcz_esa_fix", QMetaType.QString, len=12), # ESA correction: "original → new" (e.g., "C → D") or "-"
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
