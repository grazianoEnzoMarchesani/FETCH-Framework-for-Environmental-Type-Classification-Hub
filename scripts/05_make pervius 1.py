import os
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsMessageLog, Qgis
from qgis.utils import iface
from qgis import processing

def get_layer(layer_name):
    return QgsProject.instance().mapLayersByName(layer_name)[0] if QgsProject.instance().mapLayersByName(layer_name) else None

def log_message(message, level=Qgis.Info):
    QgsMessageLog.logMessage(message, 'RasterProcessingScript', level)
    iface.messageBar().pushMessage("Info", message, level=level)

# 1. Layer verification
class_layer = get_layer("class")
buildings_layer = get_layer("buildings")

if not class_layer or not buildings_layer:
    log_message("Error: 'class' or 'buildings' layer not found in the project.", Qgis.Critical)
    raise Exception("Missing layers")

if not isinstance(class_layer, QgsRasterLayer) or not isinstance(buildings_layer, QgsVectorLayer):
    log_message("Error: Incorrect layer type.", Qgis.Critical)
    raise Exception("Invalid layer type")

# 2. Raster remapping
log_message("Starting raster remapping...")
remapped_raster = processing.run("qgis:reclassifybytable", {
    'INPUT_RASTER': class_layer,
    'RASTER_BAND': 1,
    'TABLE': [0, 5, 1, 5, 9, 0],
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'NODATA_FOR_MISSING': False,
    'DATA_TYPE': 5,
    'OUTPUT': 'TEMPORARY_OUTPUT'
})['OUTPUT']

# Add remapped layer to the project
remapped_layer = QgsRasterLayer(remapped_raster, "Remapped Raster")
QgsProject.instance().addMapLayer(remapped_layer)
log_message("Remapped raster added to the project.")

# 3. Rasterization of vector layer
log_message("Starting vector layer rasterization...")
rasterized_buildings = processing.run("gdal:rasterize", {
    'INPUT': buildings_layer,
    'FIELD': '',
    'BURN': 2,
    'UNITS': 1,
    'WIDTH': class_layer.rasterUnitsPerPixelX(),
    'HEIGHT': class_layer.rasterUnitsPerPixelY(),
    'EXTENT': class_layer.extent(),
    'NODATA': 0,
    'OUTPUT': 'TEMPORARY_OUTPUT'
})['OUTPUT']

# 4. Raster combination
log_message("Combining rasters...")
final_raster = processing.run("gdal:merge", {
    'INPUT': [remapped_raster, rasterized_buildings],
    'PCT': False,
    'SEPARATE': False,
    'NODATA_INPUT': None,
    'NODATA_OUTPUT': None,
    'OPTIONS': '',
    'PSEUDO_COLOR_TABLE': '',
    'OUTPUT': 'TEMPORARY_OUTPUT'
})['OUTPUT']

# 5. Saving and adding the resulting raster
log_message("Saving the final raster...")
output_path = os.path.join(os.path.dirname(class_layer.source()), "raster_modified.tif")
processing.run("gdal:translate", {
    'INPUT': final_raster,
    'TARGET_CRS': None,
    'NODATA': None,
    'COPY_SUBDATASETS': False,
    'OPTIONS': '',
    'EXTRA': '',
    'DATA_TYPE': 0,
    'OUTPUT': output_path
})

# Add final raster to the project
final_layer = QgsRasterLayer(output_path, "pervius_impervius_buildings")
if final_layer.isValid():
    QgsProject.instance().addMapLayer(final_layer)
    log_message("Final raster added to the project: " + output_path)
else:
    log_message("Error loading the final raster.", Qgis.Warning)

log_message("Process completed successfully!")

# 6. Remove all temporary layers
log_message("Removing temporary layers...")
project = QgsProject.instance()
temporary_layers = [layer for layer in project.mapLayers().values() if layer.isTemporary()]
for layer in temporary_layers:
    project.removeMapLayer(layer.id())
log_message(f"Removed {len(temporary_layers)} temporary layers.")

# 7. Manage layers with duplicate names
log_message("Managing layers with duplicate names...")
layer_names = {}
layers_to_remove = []

for layer_id, layer in project.mapLayers().items():
    if not layer.isTemporary():
        if layer.name() in layer_names:
            layers_to_remove.append(layer_id)
        else:
            layer_names[layer.name()] = layer_id

for layer_id in layers_to_remove:
    project.removeMapLayer(layer_id)

log_message(f"Removed {len(layers_to_remove)} duplicate layers.")

log_message("Project cleanup completed!")