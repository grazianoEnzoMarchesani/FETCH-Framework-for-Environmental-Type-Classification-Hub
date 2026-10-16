import os
from qgis.core import (QgsProject, QgsRasterLayer, QgsProcessingFeedback,
                       QgsProcessingException)
from qgis.analysis import QgsNativeAlgorithms
import processing
import tempfile

def check_layer_exists(layer_name):
    """
    Verifica se un layer con il nome specificato esiste nel progetto.
    
    :param layer_name: Nome del layer da cercare
    :return: Il layer se trovato, altrimenti None
    """
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if not layers:
        raise ValueError(f"Layer '{layer_name}' non trovato nel progetto.")
    return layers[0]

def run_processing_algorithm(algorithm, params, feedback):
    """
    Esegue un algoritmo di processing e gestisce le eccezioni.
    
    :param algorithm: Nome dell'algoritmo
    :param params: Parametri dell'algoritmo
    :param feedback: Oggetto QgsProcessingFeedback
    :return: Risultato dell'algoritmo
    """
    try:
        result = processing.run(algorithm, params, feedback=feedback)
        return result
    except QgsProcessingException as e:
        raise RuntimeError(f"Errore nell'esecuzione dell'algoritmo {algorithm}: {str(e)}")

def add_layer_to_project(layer_path, layer_name):
    """
    Aggiunge un layer raster al progetto QGIS.
    
    :param layer_path: Percorso del file raster
    :param layer_name: Nome da assegnare al layer
    """
    layer = QgsRasterLayer(layer_path, layer_name)
    if layer.isValid():
        QgsProject.instance().addMapLayer(layer)
        print(f"Layer '{layer_name}' aggiunto al progetto.")
    else:
        print(f"Errore nel caricamento del layer '{layer_name}'.")

def dsm_to_dtm_process():
    """
    Funzione principale per convertire DSM in DTM.
    """
    feedback = QgsProcessingFeedback()
    
    # 1. Identificazione dei layer DSM e mask
    try:
        dsm_layer = check_layer_exists("dsm")
        mask_layer = check_layer_exists("mask")
    except ValueError as e:
        raise RuntimeError(str(e))
    
    # 2. Calcolo della pendenza
    slope_output = tempfile.NamedTemporaryFile(suffix='.tif', delete=False).name
    slope_params = {
        'INPUT': dsm_layer,
        'Z_FACTOR': 1,
        'OUTPUT': slope_output
    }
    run_processing_algorithm("native:slope", slope_params, feedback)
    # Layer "Pendenza" non viene aggiunto al progetto
    
    # 3. Filtraggio basato sulla pendenza usando r.mapcalc
    filtered_output = tempfile.NamedTemporaryFile(suffix='.tif', delete=False).name
    expression = 'if(A <= 5.71, B, null())'
    mapcalc_params = {
        'a': slope_output,
        'b': dsm_layer.source(),
        'expression': expression,
        'output': filtered_output,
        'GRASS_REGION_PARAMETER': None,
        'GRASS_REGION_CELLSIZE_PARAMETER': 0,
        'GRASS_RASTER_FORMAT_OPT': '',
        'GRASS_RASTER_FORMAT_META': ''
    }
    run_processing_algorithm("grass7:r.mapcalc.simple", mapcalc_params, feedback)
    # Layer "DSM_filtrato" non viene aggiunto al progetto
    
    # 4. Applicazione della maschera
    masked_output = tempfile.NamedTemporaryFile(suffix='.tif', delete=False).name
    mask_expression = 'A * (B != 1)'
    mask_params = {
        'a': filtered_output,
        'b': mask_layer.source(),
        'expression': mask_expression,
        'output': masked_output,
        'GRASS_REGION_PARAMETER': None,
        'GRASS_REGION_CELLSIZE_PARAMETER': 0,
        'GRASS_RASTER_FORMAT_OPT': '',
        'GRASS_RASTER_FORMAT_META': ''
    }
    run_processing_algorithm("grass7:r.mapcalc.simple", mask_params, feedback)
    add_layer_to_project(masked_output, "dtm")
    
    print("Processo completato. Il layer risultante 'DSM_mascherato' è stato aggiunto al progetto.")

# Esecuzione dello script
try:
    dsm_to_dtm_process()
except Exception as e:
    print(f"Si è verificato un errore: {str(e)}")