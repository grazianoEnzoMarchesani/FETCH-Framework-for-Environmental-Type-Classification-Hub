from qgis.core import *
import processing
import math
import statistics

def get_layers():
    # Ottiene tutti i layer caricati nel progetto QGIS
    layers = QgsProject.instance().mapLayers().values()
    
    # Trova i layer "grid" e "mask"
    grid_layer = None
    mask_layer = None
    
    for layer in layers:
        if layer.name().lower() == "grid" and isinstance(layer, QgsVectorLayer):
            grid_layer = layer
        elif layer.name().lower() == "mask" and isinstance(layer, QgsRasterLayer):
            mask_layer = layer
    
    # Verifica se entrambi i layer sono stati trovati
    if not grid_layer:
        print("Errore: Layer 'grid' non trovato.")
    if not mask_layer:
        print("Errore: Layer 'mask' non trovato.")
    
    return mask_layer, grid_layer

def calculate_distance_raster(binary_raster_layer):
    # Calcola il raster delle distanze utilizzando il processo "Prossimità (distanza raster)"
    output_path = '/tmp/distance_raster.tif'  # Definisci il percorso di output per il raster delle distanze

    # Esegui il processo di prossimità
    params = {
        'INPUT': binary_raster_layer,
        'BAND': 1,  # Banda da utilizzare, di solito la prima
        'VALUES': '1',  # Calcola la distanza dai pixel con valore 1 (edifici)
        'OUTPUT': output_path
    }

    result = processing.run("gdal:proximity", params)

    # Carica il raster delle distanze risultante
    distance_raster_layer = QgsRasterLayer(result['OUTPUT'], "Distance Raster")
    
    if not distance_raster_layer.isValid():
        print("Errore durante la creazione del raster delle distanze.")
        return None

    # Aggiungi il layer alla mappa di QGIS
    QgsProject.instance().addMapLayer(distance_raster_layer)
    return distance_raster_layer

def calculate_median_distance(raster_layer, vector_layer):
    # Verifica che entrambi i layer siano validi
    if not raster_layer or not vector_layer:
        print("Errore: Uno o entrambi i layer non sono stati trovati.")
        return

    if not raster_layer.isValid() or not vector_layer.isValid():
        print("Errore: uno o entrambi i layer non sono validi.")
        return

    # Aggiunge un campo per la mediana se non esiste già
    provider = vector_layer.dataProvider()
    field_name = 'median_dist'

    if vector_layer.fields().indexOf(field_name) == -1:
        provider.addAttributes([QgsField(field_name, QVariant.Double)])
        vector_layer.updateFields()

    idx = vector_layer.fields().indexOf(field_name)

    # Inizia la modifica del layer vettoriale
    vector_layer.startEditing()

    features = vector_layer.getFeatures()
    total_features = vector_layer.featureCount()

    for current, feature in enumerate(features, 1):
        geom = feature.geometry()
        values = []

        # Ottieni l'estensione del poligono
        extent = geom.boundingBox()
        intersection = extent.intersect(raster_layer.extent())

        if intersection.isEmpty():
            median_value = None
        else:
            # Definisci la risoluzione del raster
            pixel_size_x = raster_layer.rasterUnitsPerPixelX()
            pixel_size_y = raster_layer.rasterUnitsPerPixelY()
            cols = int(intersection.width() / pixel_size_x)
            rows = int(intersection.height() / pixel_size_y)

            # Evita dimensioni negative o zero
            if cols <= 0 or rows <= 0:
                median_value = None
            else:
                # Crea un blocco raster dell'area di interesse
                block = raster_layer.dataProvider().block(1, intersection, cols, rows)
                for i in range(cols):
                    for j in range(rows):
                        val = block.value(i, j)
                        if val != 0 and not math.isnan(val):
                            values.append(val)
                if values:
                    median_value = statistics.median(values)
                else:
                    median_value = None

        # Aggiorna l'attributo della feature
        vector_layer.changeAttributeValue(feature.id(), idx, median_value)

        # Aggiorna la barra di avanzamento
        percent = int((current / total_features) * 100)
        print(f"\rProgresso: {percent}%", end="", flush=True)

    # Salva le modifiche
    vector_layer.commitChanges()
    print("\nCalcolo completato. La colonna 'median_dist' è stata aggiunta o aggiornata nel layer vettoriale.")

# Ottieni i layer automaticamente
binary_raster_layer, vector_layer = get_layers()

if binary_raster_layer and vector_layer:
    # Calcola il raster delle distanze a partire dal raster binario
    distance_raster_layer = calculate_distance_raster(binary_raster_layer)

    if distance_raster_layer:
        # Stampa informazioni sui layer
        print(f"Layer raster delle distanze: {distance_raster_layer.name()}")
        print(f"Layer vettoriale: {vector_layer.name()}")
        print(f"  - Numero di feature: {vector_layer.featureCount()}")

        # Calcola la mediana delle distanze all'interno delle celle del reticolo
        calculate_median_distance(distance_raster_layer, vector_layer)
    else:
        print("Errore durante la creazione del raster delle distanze.")
else:
    print("Errore: Uno o entrambi i layer richiesti non sono stati trovati.")