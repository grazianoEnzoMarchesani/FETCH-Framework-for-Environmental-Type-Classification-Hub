from qgis.core import *
from qgis.PyQt.QtCore import QVariant
import processing
import math
import statistics

# Funzione per ottenere i layer automaticamente
def get_layers():
    project = QgsProject.instance()
    mask_layer = project.mapLayersByName("mask")
    grid_layer = project.mapLayersByName("grid")
    
    if not mask_layer:
        raise ValueError("Layer 'mask' non trovato nel progetto")
    if not grid_layer:
        raise ValueError("Layer 'grid' non trovato nel progetto")
    
    return mask_layer[0], grid_layer[0]

def calculate_distance_raster(binary_raster_layer):
    print("Calcolo del raster delle distanze...")
    output_path = '/tmp/distance_raster.tif'
    
    params = {
        'INPUT': binary_raster_layer,
        'BAND': 1,
        'VALUES': '1',
        'OUTPUT': output_path
    }

    result = processing.run("gdal:proximity", params)
    distance_raster_layer = QgsRasterLayer(result['OUTPUT'], "Distance Raster")
    
    if not distance_raster_layer.isValid():
        raise ValueError("Errore durante la creazione del raster delle distanze.")

    QgsProject.instance().addMapLayer(distance_raster_layer)
    print("Raster delle distanze calcolato e aggiunto al progetto.")
    return distance_raster_layer

def calculate_median_distance(raster_layer, vector_layer):
    print("Inizio calcolo della distanza mediana per ogni feature del layer grid...")
    
    provider = vector_layer.dataProvider()
    field_name = 'median_dist'

    if vector_layer.fields().indexOf(field_name) == -1:
        provider.addAttributes([QgsField(field_name, QVariant.Double)])
        vector_layer.updateFields()
        print(f"Campo '{field_name}' aggiunto al layer grid.")

    idx = vector_layer.fields().indexOf(field_name)
    vector_layer.startEditing()

    features = vector_layer.getFeatures()
    total_features = vector_layer.featureCount()

    for current, feature in enumerate(features, 1):
        geom = feature.geometry()
        values = []
        extent = geom.boundingBox()
        intersection = extent.intersect(raster_layer.extent())

        if intersection.isEmpty():
            median_value = 0.001  # Valore piccolo invece di None
        else:
            pixel_size_x = raster_layer.rasterUnitsPerPixelX()
            pixel_size_y = raster_layer.rasterUnitsPerPixelY()
            cols = int(intersection.width() / pixel_size_x)
            rows = int(intersection.height() / pixel_size_y)

            if cols <= 0 or rows <= 0:
                median_value = 0.001  # Valore piccolo invece di None
            else:
                block = raster_layer.dataProvider().block(1, intersection, cols, rows)
                for i in range(cols):
                    for j in range(rows):
                        val = block.value(i, j)
                        if val != 0 and not math.isnan(val):
                            values.append(val)
                if values:
                    median_value = statistics.median(values)
                else:
                    median_value = 0.001  # Valore piccolo invece di None

        vector_layer.changeAttributeValue(feature.id(), idx, median_value)

        if current % 100 == 0 or current == total_features:
            percent = int((current / total_features) * 100)
            print(f"Progresso: {percent}%")

    vector_layer.commitChanges()
    print("Calcolo completato. La colonna 'median_dist' è stata aggiunta o aggiornata nel layer grid.")

def main():
    print("Inizio dell'elaborazione...")
    try:
        # Ottieni i layer automaticamente
        mask_layer, grid_layer = get_layers()
        print(f"Layer mask: {mask_layer.name()}")
        print(f"Layer grid: {grid_layer.name()}")
        print(f"Numero di feature nel layer grid: {grid_layer.featureCount()}")

        # Calcola il raster delle distanze
        distance_raster_layer = calculate_distance_raster(mask_layer)

        # Calcola la mediana delle distanze
        calculate_median_distance(distance_raster_layer, grid_layer)

        print("Elaborazione completata con successo.")
    except Exception as e:
        print(f"Si è verificato un errore durante l'elaborazione: {str(e)}")

# Esegui lo script
main()