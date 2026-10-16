import os
from qgis.core import QgsProject, QgsVectorLayer, QgsProcessingFeedback, QgsFeatureRequest, QgsProcessing

# Funzione per vettorializzare un raster e salvare il risultato in un file GeoPackage
def vettorializza_raster(raster_layer):
    # Ottieni il percorso del file raster originale
    raster_path = raster_layer.source()
    
    # Costruisci il percorso del file GeoPackage dove salvare il vettoriale
    base_path = os.path.splitext(raster_path)[0]  # Rimuove l'estensione del file raster
    geopackage_path = f"{base_path}_buildings.gpkg"  # Aggiungi "_buildings" al nome del file
    
    # Imposta i parametri per la vettorializzazione
    params = {
        'INPUT': raster_layer,
        'BAND': 1,  # Usa la banda 1
        'FIELD': 'value',  # Nome del campo dei valori
        'EIGHT_CONNECTEDNESS': False,
        'EXTRA': '',
        'OUTPUT': geopackage_path  # Salva il risultato nel file GeoPackage
    }
    
    # Esegui il processo di vettorializzazione
    processing.run('gdal:polygonize', params)
    
    # Carica il layer vettoriale risultante
    vector_layer = QgsVectorLayer(geopackage_path, 'buildings', 'ogr')  # Imposta il nome del layer a "buildings"
    
    return vector_layer

# Funzione per rimuovere i poligoni con "value" pari a 0
def rimuovi_poligoni_zero(vector_layer):
    # Inizia la modifica del layer
    vector_layer.startEditing()
    
    # Costruisci una richiesta per selezionare le feature con "value" pari a 0
    request = QgsFeatureRequest().setFilterExpression('"value" = 0')
    
    # Trova le feature corrispondenti e rimuovile
    ids = [f.id() for f in vector_layer.getFeatures(request)]
    if ids:
        vector_layer.deleteFeatures(ids)
    
    # Salva le modifiche e termina la modifica
    vector_layer.commitChanges()

# Funzione per rimuovere layer duplicati chiamati "buildings" nel gruppo
def rimuovi_duplicati_buildings(group):
    layers_to_remove = [layer for layer in group.findLayers() if layer.layer().name() == "buildings"]
    
    # Mantieni solo l'ultimo layer e rimuovi gli altri
    if len(layers_to_remove) > 1:
        for layer_tree in layers_to_remove[:-1]:  # Rimuove tutti tranne l'ultimo
            group.removeLayer(layer_tree.layer())

# Ottieni il progetto attuale
project = QgsProject.instance()

# Cerca i layer raster chiamati "mask"
raster_layers = [layer for layer in project.mapLayers().values() if layer.name() == "mask" and layer.type() == layer.RasterLayer]

# Itera su ogni layer raster trovato
for raster_layer in raster_layers:
    # Vettorializza il raster
    vector_layer = vettorializza_raster(raster_layer)
    
    # Rimuovi i poligoni con "value" pari a 0
    rimuovi_poligoni_zero(vector_layer)
    
    # Trova il gruppo del raster originale
    root = project.layerTreeRoot()
    layer_tree = root.findLayer(raster_layer.id())
    group = layer_tree.parent() if isinstance(layer_tree.parent(), QgsLayerTreeLayer) else layer_tree.parent()
    
    # Aggiungi il layer vettoriale nello stesso gruppo del raster originale
    if group is not None:
        project.addMapLayer(vector_layer, False)  # Non aggiungere automaticamente alla root
        group.addLayer(vector_layer)
        rimuovi_duplicati_buildings(group)  # Rimuovi eventuali duplicati di "buildings"
    else:
        # Se il gruppo non esiste, aggiungi il vettore direttamente nella root del progetto
        project.addMapLayer(vector_layer)

print("Vettorializzazione completata, poligoni rimossi e file salvati in formato GeoPackage con nome 'buildings'. Duplicati rimossi.")