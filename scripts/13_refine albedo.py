# Importazione delle librerie necessarie
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, 
                       QgsField, QgsExpression, QgsExpressionContext, 
                       QgsExpressionContextUtils)
from qgis.PyQt.QtCore import QVariant
from qgis.utils import iface
import processing

def get_layer(layer_name):
    """
    Funzione per ottenere un layer dal progetto QGIS corrente.
    
    :param layer_name: Nome del layer da cercare
    :return: Oggetto layer se trovato, altrimenti None
    """
    return QgsProject.instance().mapLayersByName(layer_name)[0] if QgsProject.instance().mapLayersByName(layer_name) else None

def check_layers(grid_layer, albedo_layer):
    """
    Funzione per verificare la presenza dei layer richiesti.
    
    :param grid_layer: Layer vettoriale grid
    :param albedo_layer: Layer raster albedo
    :return: True se entrambi i layer sono presenti, False altrimenti
    """
    if not grid_layer:
        iface.messageBar().pushMessage("Errore", "Layer 'grid' non trovato nel progetto.", level=Qgis.Critical)
        return False
    if not albedo_layer:
        iface.messageBar().pushMessage("Errore", "Layer 'albedo' non trovato nel progetto.", level=Qgis.Critical)
        return False
    return True

def calculate_zonal_statistics(grid_layer, albedo_layer):
    """
    Funzione per calcolare le statistiche zonali utilizzando l'algoritmo di processing.
    
    :param grid_layer: Layer vettoriale grid
    :param albedo_layer: Layer raster albedo
    :return: Il nome del campo creato per la maggioranza
    """
    # Utilizzo dell'algoritmo 'qgis:zonalstatistics' per calcolare le statistiche
    params = {
        'INPUT_RASTER': albedo_layer,
        'RASTER_BAND': 1,
        'INPUT_VECTOR': grid_layer,
        'COLUMN_PREFIX': 'albedo_',
        'STATISTICS': [9],  # 9 corrisponde alla statistica "Majority"
    }
    processing.run("qgis:zonalstatistics", params)
    
    # Identifica il campo creato per la maggioranza
    majority_field = next((field.name() for field in grid_layer.fields() 
                           if field.name().startswith('albedo_') and field.name().endswith('majority')), None)
    
    if majority_field:
        return majority_field
    else:
        iface.messageBar().pushMessage("Errore", "Campo di maggioranza non trovato dopo il calcolo delle statistiche zonali.", level=Qgis.Critical)
        return None

def normalize_albedo(grid_layer, field_name):
    """
    Funzione per normalizzare i valori di albedo.
    
    :param grid_layer: Layer vettoriale grid
    :param field_name: Nome del campo contenente i valori di albedo da normalizzare
    """
    # Verifica se il campo esiste
    if field_name not in [field.name() for field in grid_layer.fields()]:
        iface.messageBar().pushMessage("Errore", f"Campo '{field_name}' non trovato nel layer.", level=Qgis.Critical)
        return
    
    # Creazione di un'espressione per dividere i valori per 10000
    expression = QgsExpression(f'"{field_name}" / 10000')
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(grid_layer))
    
    # Aggiornamento dei valori
    with edit(grid_layer):
        for feature in grid_layer.getFeatures():
            context.setFeature(feature)
            new_value = expression.evaluate(context)
            if new_value is not None:  # Verifica che il nuovo valore non sia None
                feature[field_name] = new_value
                grid_layer.updateFeature(feature)
            else:
                iface.messageBar().pushMessage("Avviso", f"Valore nullo trovato durante la normalizzazione per la feature ID {feature.id()}", level=Qgis.Warning)

def main():
    """
    Funzione principale dello script.
    """
    # Ottenimento dei layer
    grid_layer = get_layer('grid')
    albedo_layer = get_layer('albedo')
    
    # Verifica della rougpresenza dei layer
    if not check_layers(grid_layer, albedo_layer):
        return
    
    # Calcolo delle statistiche zonali
    albedo_field = calculate_zonal_statistics(grid_layer, albedo_layer)
    if not albedo_field:
        return
    
    # Normalizzazione dei valori di albedo
    normalize_albedo(grid_layer, albedo_field)
    
    iface.messageBar().pushMessage("Successo", "Analisi completata con successo!", level=Qgis.Success)

# Esecuzione dello script
main()