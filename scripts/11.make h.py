from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, QgsField,
                       QgsProcessingFeedback, QgsMessageLog, Qgis, QgsFeatureRequest)
from qgis.PyQt.QtCore import QVariant
from qgis.utils import iface
import processing
import traceback

class CustomFeedback(QgsProcessingFeedback):
    def __init__(self):
        super().__init__()
        self.error_message = ""

    def reportError(self, error, fatalError=False):
        self.error_message += error + "\n"
        QgsMessageLog.logMessage(f"Error in processing: {error}", "Object Heights", level=Qgis.Critical)

def get_layer(layer_name):
    """Ottiene un layer dal progetto corrente."""
    layer = QgsProject.instance().mapLayersByName(layer_name)
    if not layer:
        raise ValueError(f"Layer '{layer_name}' non trovato nel progetto.")
    return layer[0]

def validate_layers(grid_layer, dtm_layer, dsm_layer):
    """Valida i tipi dei layer."""
    if not isinstance(grid_layer, QgsVectorLayer):
        raise TypeError("Il layer 'grid' deve essere un layer vettoriale.")
    if not isinstance(dtm_layer, QgsRasterLayer) or not isinstance(dsm_layer, QgsRasterLayer):
        raise TypeError("I layer 'dtm' e 'dsm' devono essere layer raster.")

def calculate_zonal_stats(grid_layer, raster_layer, output_column):
    """Calcola le statistiche zonali e aggiorna il layer grid."""
    feedback = CustomFeedback()
    new_field = f'{output_column}median'
    
    # Verifica se il campo esiste già
    if new_field not in grid_layer.fields().names():
        grid_layer.dataProvider().addAttributes([QgsField(new_field, QVariant.Double)])
        grid_layer.updateFields()
    
    field_index = grid_layer.fields().indexFromName(new_field)
    
    params = {
        'INPUT': grid_layer,
        'INPUT_RASTER': raster_layer,
        'RASTER_BAND': 1,
        'COLUMN_PREFIX': '_temp_',
        'STATISTICS': [3],  # 3 corrisponde alla mediana
        'OUTPUT': 'memory:'
    }
    
    try:
        result = processing.run("native:zonalstatisticsfb", params, feedback=feedback)
    except Exception as e:
        QgsMessageLog.logMessage(f"Errore nel calcolo delle statistiche zonali: {str(e)}", "Object Heights", level=Qgis.Critical)
        if feedback.error_message:
            raise RuntimeError(f"Errore nel processing: {feedback.error_message}")
        raise

    result_layer = result['OUTPUT']
    temp_field = '_temp_median'
    
    # Creiamo un dizionario per memorizzare i valori calcolati
    calculated_values = {f.id(): f[temp_field] for f in result_layer.getFeatures()}
    
    # Aggiorniamo i valori nel campo esistente
    with edit(grid_layer):
        for feature in grid_layer.getFeatures():
            if feature.id() in calculated_values:
                grid_layer.changeAttributeValue(feature.id(), field_index, calculated_values[feature.id()])
            else:
                QgsMessageLog.logMessage(f"Feature ID {feature.id()} non trovata nei risultati", "Object Heights", level=Qgis.Warning)

    QgsMessageLog.logMessage(f"Campo {new_field} aggiornato con successo", "Object Heights", level=Qgis.Info)

def calculate_roughness_height(grid_layer):
    """Calcola l'altezza degli elementi di rugosità."""
    height_field = 'Height_rou'
    
    # Verifica se il campo esiste già
    if height_field not in grid_layer.fields().names():
        grid_layer.dataProvider().addAttributes([QgsField(height_field, QVariant.Double)])
        grid_layer.updateFields()
    
    height_idx = grid_layer.fields().indexFromName(height_field)
    dtm_idx = grid_layer.fields().indexFromName('dtm_median')
    dsm_idx = grid_layer.fields().indexFromName('dsm_median')
    
    count_total = count_success = count_error = count_missing = 0
    
    with edit(grid_layer):
        for feature in grid_layer.getFeatures():
            count_total += 1
            dtm_value = feature[dtm_idx]
            dsm_value = feature[dsm_idx]
            
            # Debug: stampa i valori per le prime 10 features
            if count_total <= 10:
                QgsMessageLog.logMessage(f"Feature {count_total}: DTM = {dtm_value}, DSM = {dsm_value}", "Object Heights", level=Qgis.Info)
            
            if dtm_value is not None and dsm_value is not None and isinstance(dtm_value, (int, float)) and isinstance(dsm_value, (int, float)):
                try:
                    height = float(dsm_value) - float(dtm_value)
                    grid_layer.changeAttributeValue(feature.id(), height_idx, height)
                    count_success += 1
                    if count_total % 1000 == 0:
                        QgsMessageLog.logMessage(f"Processed {count_total} features. Last height: {height}", "Object Heights", level=Qgis.Info)
                except (ValueError, TypeError) as e:
                    count_error += 1
                    QgsMessageLog.logMessage(f"Errore nella conversione dei valori per feature ID {feature.id()}: {str(e)}", "Object Heights", level=Qgis.Warning)
            else:
                count_missing += 1
                QgsMessageLog.logMessage(f"Valori mancanti o non numerici per feature ID {feature.id()}: DTM = {dtm_value}, DSM = {dsm_value}", "Object Heights", level=Qgis.Warning)
    
    QgsMessageLog.logMessage(f"Totale features processate: {count_total}", "Object Heights", level=Qgis.Info)
    QgsMessageLog.logMessage(f"Calcoli riusciti: {count_success}", "Object Heights", level=Qgis.Info)
    QgsMessageLog.logMessage(f"Errori di conversione: {count_error}", "Object Heights", level=Qgis.Info)
    QgsMessageLog.logMessage(f"Valori mancanti o non numerici: {count_missing}", "Object Heights", level=Qgis.Info)

def calculate_object_heights():
    """Funzione principale per calcolare l'altezza degli oggetti."""
    try:
        # 1. Verifica e ottenimento dei layer richiesti
        grid_layer = get_layer("grid")
        dtm_layer = get_layer("dtm")
        dsm_layer = get_layer("dsm")

        # Validazione dei layer
        validate_layers(grid_layer, dtm_layer, dsm_layer)

        # 2. Calcolo delle statistiche zonali
        QgsMessageLog.logMessage("Inizio calcolo statistiche zonali per DTM", "Object Heights", level=Qgis.Info)
        calculate_zonal_stats(grid_layer, dtm_layer, 'dtm_')
        QgsMessageLog.logMessage("Inizio calcolo statistiche zonali per DSM", "Object Heights", level=Qgis.Info)
        calculate_zonal_stats(grid_layer, dsm_layer, 'dsm_')

        # 3. Calcolo dell'altezza degli elementi di rugosità
        QgsMessageLog.logMessage("Inizio calcolo altezza elementi di rugosità", "Object Heights", level=Qgis.Info)
        calculate_roughness_height(grid_layer)

        # Aggiorna il layer nella mappa
        grid_layer.triggerRepaint()
        iface.mapCanvas().refresh()

        QgsMessageLog.logMessage("Calcolo completato con successo.", "Object Heights", level=Qgis.Success)
        iface.messageBar().pushMessage("Successo", "Calcolo dell'altezza degli oggetti completato.", level=Qgis.Success)

    except Exception as e:
        error_message = f"Si è verificato un errore: {str(e)}"
        QgsMessageLog.logMessage(error_message, "Object Heights", level=Qgis.Critical)
        QgsMessageLog.logMessage(f"Traceback: {traceback.format_exc()}", "Object Heights", level=Qgis.Critical)
        iface.messageBar().pushMessage("Errore", error_message, level=Qgis.Critical)

# Esegui la funzione
calculate_object_heights()