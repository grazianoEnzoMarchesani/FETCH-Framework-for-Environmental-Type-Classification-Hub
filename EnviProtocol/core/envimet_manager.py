import os
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsFields, QgsField, QgsRectangle, QgsCoordinateReferenceSystem,
    Qgis, QgsMessageLog, QgsVectorFileWriter, QgsWkbTypes,
    QgsRasterLayer, QgsCoordinateTransform, QgsApplication
)
from qgis import processing
from .constants import FileNames, ESA_ENVIMET_MAPPING

class ENVImetManager:
    """
    Manager class for preparing GIS data for ENVI-met simulations.
    Handles Clipping, Vectorization, and Field Mapping.
    """
    
    def __init__(self, iface=None):
        self.iface = iface

    def log(self, message, level=Qgis.Info):
        QgsMessageLog.logMessage(message, "EnviProtocol-EM", level)

    def get_model_constraints(self, project_dir):
        """
        Analyzes Buildings and DTM to determine optimal ENVI-met constraints.
        Returns (lateral_margin, suggested_vertical_height, max_bld_h, max_dtm_z)
        """
        from .constants import FolderNames, FileNames
        max_bld_h = 20.0  # Default if layer missing
        max_dtm_z = 0.0

        # 1. Scan Buildings for Max Height
        bld_path = os.path.join(project_dir, FolderNames.TUM, FileNames.BUILDINGS)
        if os.path.exists(bld_path):
            try:
                res = processing.run("qgis:basicstatisticsforfields", {
                    'INPUT': bld_path, 'FIELD': 'height', 'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                # Check for both 'MAX' and 'MAXIMUM' as keys vary between QGIS versions
                max_bld_h = res.get('MAX', res.get('MAXIMUM', max_bld_h))
            except Exception as e:
                self.log(f"Impossibile leggere altezza edifici: {str(e)}", Qgis.Warning)

        # 2. Scan DTM for Max elevation
        dtm_path = os.path.join(project_dir, FileNames.DTM)
        if not os.path.exists(dtm_path):
             # Try to find a unified DTM or scan tiles
             dtm_dir = os.path.join(project_dir, FolderNames.TINITALY)
             self.log(f"Analisi DTM ricorsiva in: {dtm_dir}")
             if os.path.exists(dtm_dir):
                 tifs = []
                 for root, dirs, files in os.walk(dtm_dir):
                     for f in files:
                         if f.lower().endswith(".tif") and not f.startswith("."):
                             tifs.append(os.path.join(root, f))
                 
                 if tifs:
                     dtm_path = tifs[0]
                     self.log(f"Trovati {len(tifs)} tiles. Uso {os.path.basename(dtm_path)} per statistiche.")
        
        if dtm_path and os.path.exists(dtm_path):
            try:
                res = processing.run("native:rasterlayerstatistics", {
                    'INPUT': dtm_path, 'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                max_dtm_z = res.get('MAX', res.get('MAXIMUM', max_dtm_z))
            except Exception as e:
                self.log(f"Impossibile leggere statistiche DTM: {str(e)}", Qgis.Warning)

        # Prerequisites rules:
        # - Lateral boundary: 0.5 * max height of structures
        # - Vertical extent: 2 * (max_elev + max_height)
        lateral_margin = max_bld_h * 0.5
        suggested_z = (max_dtm_z + max_bld_h) * 2.0
        
        # Cap vertical height at 2500m
        suggested_z = min(suggested_z, 2500.0)
        
        return lateral_margin, suggested_z, max_bld_h, max_dtm_z

    def vectorize_land_use(self, input_raster, output_path, extent):
        """Vectorizes ESA Land Use raster (clipped to extent) and maps values to ENVI-met IDs."""
        try:
            # 1. Reproject extent to raster CRS to avoid PB disk space error
            raster_layer = QgsRasterLayer(input_raster, "temp_raster")
            raster_crs = raster_layer.crs()
            project_crs = QgsProject.instance().crs()
            
            x_extent = extent
            if raster_crs != project_crs:
                self.log(f"Reprojecting extent from {project_crs.authid()} to {raster_crs.authid()}")
                xf = QgsCoordinateTransform(project_crs, raster_crs, QgsProject.instance())
                x_extent = xf.transformBoundingBox(extent)
                self.log(f"New extent: {x_extent.toString()}")

            # 2. Clip raster first to study area (performance boost)
            clip_res = processing.run("gdal:cliprasterbyextent", {
                'INPUT': input_raster,
                'PROJWIN': x_extent,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            clipped_raster = clip_res['OUTPUT']

            # 3. Polygonize the clipped raster
            vec_res = processing.run("gdal:polygonize", {
                'INPUT': clipped_raster, 'BAND': 1, 'FIELD': 'DN', 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            # 4. Dissolve by DN to speed up processing
            dissolve_res = processing.run("native:dissolve", {
                'INPUT': vec_res['OUTPUT'], 'FIELD': ['DN'], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            output_layer = dissolve_res['OUTPUT']
            if isinstance(output_layer, str):
                layer = QgsVectorLayer(output_layer, "temp_vector", "ogr")
            else:
                layer = output_layer

            if not layer or not layer.isValid() or layer.featureCount() == 0:
                return False, "Impossibile vettorizzare Land Use ESA (area vuota?)."

            # 2. Add ENVI_ID and Map Values
            layer.startEditing()
            # Modern QgsField syntax: name, type
            layer.addAttribute(QgsField("ENVI_ID", QVariant.String))
            layer.updateFields()
            
            idx_dn = layer.fields().indexFromName("DN")
            idx_envi = layer.fields().indexFromName("ENVI_ID")
            
            for feat in layer.getFeatures():
                dn = feat.attributes()[idx_dn]
                envi_id = ESA_ENVIMET_MAPPING.get(dn, "000000") # Default to zero if unknown
                layer.changeAttributeValue(feat.id(), idx_envi, envi_id)
            
            layer.commitChanges()

            # 3. Save final using factory for compatibility
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.fileEncoding = "UTF-8"
            
            writer = QgsVectorFileWriter.create(
                output_path,
                layer.fields(),
                layer.wkbType(),
                layer.crs(),
                QgsProject.instance().transformContext(),
                options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return False, f"Errore salvataggio Land Use: {writer.errorMessage()}"
                
            for feat in layer.getFeatures():
                writer.addFeature(feat)
            
            del writer
            return True, output_path
        except Exception as e:
            return False, str(e)

    def prepare_sub_area(self, extent, crs_auth_id, output_path, margin=0.0):
        """Creates a rectangular Sub Area layer with an optional margin."""
        try:
            crs = QgsCoordinateReferenceSystem(crs_auth_id)
            if not crs.isValid():
                crs = QgsProject.instance().crs()
            
            # Apply margin to extent
            final_extent = QgsRectangle(extent)
            if margin > 0:
                final_extent.grow(margin)
                
            polygon = QgsGeometry.fromRect(final_extent)
            
            # Use explicit QgsVectorFileWriter.create for maximum compatibility
            fields = QgsFields()
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.fileEncoding = "UTF-8"
            
            writer = QgsVectorFileWriter.create(
                output_path,
                fields,
                QgsWkbTypes.Polygon,
                crs,
                QgsProject.instance().transformContext(),
                options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return False, f"Errore creazione file: {writer.errorMessage()}"
            
            feat = QgsFeature()
            feat.setGeometry(polygon)
            writer.addFeature(feat)
            
            del writer # Close file
            return True, output_path
        except Exception as e:
            return False, str(e)

    def process_buildings(self, input_path, output_path, aoi_geometry, crs_auth_id):
        """Clips buildings to AOI and adds a generic ENVI_ID."""
        if not os.path.exists(input_path):
            return False, "Layer edifici non trovato."

        try:
            # 1. Create a temporary layer for the AOI geometry to use as OVERLAY
            aoi_layer = QgsVectorLayer(f"Polygon?crs={crs_auth_id}", "aoi_mask", "memory")
            aoi_layer.startEditing()
            f = QgsFeature()
            f.setGeometry(aoi_geometry)
            aoi_layer.addFeature(f)
            aoi_layer.commitChanges()

            # 2. Clip buildings using processing
            params = {
                'INPUT': input_path,
                'OVERLAY': aoi_layer,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            res = processing.run("native:clip", params)
            clip_layer = res['OUTPUT']

            if not clip_layer or clip_layer.featureCount() == 0:
                return False, "Nessun edificio nell'area di studio."

            # 3. Add ENVI_ID
            clip_layer.startEditing()
            clip_layer.addAttribute(QgsField("ENVI_ID", QVariant.String))
            clip_layer.updateFields()
            
            idx_envi = clip_layer.fields().indexFromName("ENVI_ID")
            for feat in clip_layer.getFeatures():
                clip_layer.changeAttributeValue(feat.id(), idx_envi, "000001")
            clip_layer.commitChanges()

            # 3. Save using explicit writer factory (QGIS 3/4 compatible)
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.fileEncoding = "UTF-8"
            
            writer = QgsVectorFileWriter.create(
                output_path,
                clip_layer.fields(),
                clip_layer.wkbType(),
                clip_layer.crs(),
                QgsProject.instance().transformContext(),
                options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return False, f"Errore creazione edifici: {writer.errorMessage()}"
                
            for feat in clip_layer.getFeatures():
                writer.addFeature(feat)
            
            del writer
            return True, output_path
        except Exception as e:
            return False, str(e)

    def process_dtm(self, project_dir, output_path, extent, crs_auth_id):
        """Combines and clips Tinitaly DTM tiles to a single GeoTIFF."""
        from .constants import FolderNames, FileNames
        dtm_dir = os.path.join(project_dir, FolderNames.TINITALY)
        if not os.path.exists(dtm_dir):
            return False, f"Cartella DTM non trovata in: {dtm_dir}"

        # 1. Recursive search for .tif files (in case they are in subdirectories)
        tifs = []
        for root, dirs, files in os.walk(dtm_dir):
            for f in files:
                if f.lower().endswith(".tif") and not f.startswith("."):
                    tifs.append(os.path.join(root, f))
        
        self.log(f"DTM Search in {dtm_dir}: trovati {len(tifs)} file.")
        
        if not tifs:
            return False, f"Nessun tile DTM (.tif) trovato in {dtm_dir} (anche sottocartelle)."

        try:
            # 2. Merge tiles if more than one
            if len(tifs) > 1:
                merge_params = {
                    'INPUT': tifs,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
                res = processing.run("gdal:merge", merge_params)
                merged = res['OUTPUT']
            else:
                merged = tifs[0]

            # 3. Reproject extent to DTM CRS
            raster_layer = QgsRasterLayer(merged, "temp_dtm")
            raster_crs = raster_layer.crs()
            project_crs = QgsProject.instance().crs()
            
            x_extent = extent
            if raster_crs.authid() != project_crs.authid():
                xf = QgsCoordinateTransform(project_crs, raster_crs, QgsProject.instance())
                x_extent = xf.transformBoundingBox(extent)

            # 4. Clip to extent
            clip_params = {
                'INPUT': merged,
                'PROJWIN': x_extent,
                'NODATA': -9999,
                'OPTIONS': 'COMPRESS=LZW',
                'DATA_TYPE': 5, # Float32
                'OUTPUT': output_path
            }
            processing.run("gdal:cliprasterbyextent", clip_params)
            return True, output_path
        except Exception as e:
            return False, str(e)

    def process_vegetation_advanced(self, tcd_raster, eth_raster, output_path, aoi_geometry, extent, crs_auth_id):
        """Generates random tree points based on Tree Cover Density (TCD) and ETH height."""
        if not os.path.exists(tcd_raster) or not os.path.exists(eth_raster):
            return False, "Dati TCD o ETH mancanti."

        try:
            # 1. Reproject extent to TCD CRS
            raster_layer = QgsRasterLayer(tcd_raster, "temp_tcd")
            raster_crs = raster_layer.crs()
            project_crs = QgsProject.instance().crs()
            
            x_extent = extent
            if raster_crs.authid() != project_crs.authid():
                xf = QgsCoordinateTransform(project_crs, raster_crs, QgsProject.instance())
                x_extent = xf.transformBoundingBox(extent)

            # 2. Clip TCD to extent for speed
            clip_res = processing.run("gdal:cliprasterbyextent", {
                'INPUT': tcd_raster,
                'PROJWIN': x_extent,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            tcd_clipped = clip_res['OUTPUT']

            # 3. Vectorize TCD
            vec_res = processing.run("gdal:polygonize", {
                'INPUT': tcd_clipped, 'BAND': 1, 'FIELD': 'TCD', 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            # 4. Dissolve and Filter TCD (10% to 100%) to exclude NoData (255)
            dissolve_res = processing.run("native:dissolve", {
                'INPUT': vec_res['OUTPUT'], 'FIELD': ['TCD'], 'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            # Filter valid density range [10, 100] using expression to exclude NoData (255)
            filter_res = processing.run("native:extractbyexpression", {
                'INPUT': dissolve_res['OUTPUT'],
                'EXPRESSION': '"TCD" >= 10 AND "TCD" <= 100',
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            tcd_filtered = filter_res['OUTPUT']
            
            # Reproject to metric (project CRS) to ensure "points per area" uses square meters
            self.log(f"Reprojecting TCD polygons to metric CRS: {crs_auth_id}")
            repro_res = processing.run("native:reprojectlayer", {
                'INPUT': tcd_filtered,
                'TARGET_CRS': crs_auth_id,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            tcd_metric = repro_res['OUTPUT']
            
            # 5. Generate Random Points proportional to TCD
            # Detect algorithm ID (native vs qgis provider)
            algo_id = "native:randompointsinsidepolygons"
            if not QgsApplication.processingRegistry().algorithmById(algo_id):
                algo_id = "qgis:randompointsinsidepolygons"

            pts_res = processing.run(algo_id, {
                'INPUT': tcd_metric,
                'STRATEGY': 1, # Points per area (density)
                'VALUE': 0.01, # Default 1 point every 100m2 (overridden by expression)
                'EXPRESSION': '("TCD" / 100.0) * 0.01', # Scale density by TCD percentage
                'MIN_DISTANCE': 2.0, # Minimum distance between trees (meters)
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            # Safe layer load (could be a path or a layer object)
            pts_out = pts_res['OUTPUT']
            pts_layer = pts_out if not isinstance(pts_out, str) else QgsVectorLayer(pts_out, "temp_pts", "ogr")

            if not pts_layer or not pts_layer.isValid() or pts_layer.featureCount() == 0:
                return False, "Nessun albero generato (TCD troppo bassa?)"

            # 4. Sample ETH Heights
            sample_res = processing.run("native:rastersampling", {
                'INPUT': pts_layer,
                'RASTERCOPY': eth_raster,
                'COLUMN_PREFIX': 'height_',
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            final_pts = sample_res['OUTPUT']

            # 6. Clean up and Assign ENVI_IDs based on Height
            final_vec = final_pts if not isinstance(final_pts, str) else QgsVectorLayer(final_pts, "final", "ogr")
            final_vec.startEditing()
            # Modern QgsField syntax
            final_vec.addAttribute(QgsField("ENVI_ID", QVariant.String, "string", 6))
            final_vec.updateFields()
            
            # Find height column (could be height_1, height, or just BAND_1)
            f_names = [f.name() for f in final_vec.fields()]
            idx_h = -1
            for target in ["height_1", "height", "height_1_1", "SAMPLE"]:
                if target in f_names:
                    idx_h = final_vec.fields().indexFromName(target)
                    break
            
            idx_envi = final_vec.fields().indexFromName("ENVI_ID")
            
            if idx_h == -1:
                # Fallback: if no height field found, use a default height
                for feat in final_vec.getFeatures():
                    final_vec.changeAttributeValue(feat.id(), idx_envi, "0010MO") # Default medium tree
            else:
                for feat in final_vec.getFeatures():
                    h = feat.attributes()[idx_h]
                    if h is None or (isinstance(h, QVariant) and h.isNull()) or h < 2: h_id = "0000XX"
                    elif h < 8: h_id = "0010SK"
                    elif h < 15: h_id = "0010MO"
                    else: h_id = "0010L1"
                    final_vec.changeAttributeValue(feat.id(), idx_envi, h_id)
            
            final_vec.commitChanges()

            # 6. Save final Points using explicit writer factory
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.fileEncoding = "UTF-8"
            
            writer = QgsVectorFileWriter.create(
                output_path,
                final_vec.fields(),
                final_vec.wkbType(),
                final_vec.crs(),
                QgsProject.instance().transformContext(),
                options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return False, f"Errore creazione vegetazione: {writer.errorMessage()}"
                
            for feat in final_vec.getFeatures():
                writer.addFeature(feat)
            
            del writer
            return True, output_path

        except Exception as e:
            return False, str(e)

    def process_vegetation(self, esa_raster, eth_raster, output_path):
        """Legacy placeholder replaced by process_vegetation_advanced."""
        return True, "Usare process_vegetation_advanced"
