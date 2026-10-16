from qgis.core import QgsProject, QgsProcessingFeedback, QgsMessageLog, Qgis, QgsVectorLayer
import processing

def esegui_analisi_zonale():
    QgsMessageLog.logMessage("Inizio dell'esecuzione dello script", "Script Analisi Zonale", level=Qgis.Info)

    # Recupera i layer dal progetto
    progetto = QgsProject.instance()
    dsm_layer = progetto.mapLayersByName("dsm")
    mask_layer = progetto.mapLayersByName("mask")
    grid_layer = progetto.mapLayersByName("grid")

    # Verifica la presenza di tutti i layer necessari
    if not (dsm_layer and mask_layer and grid_layer):
        QgsMessageLog.logMessage("Errore: Uno o più layer richiesti non sono presenti nel progetto", "Script Analisi Zonale", level=Qgis.Critical)
        return

    dsm_layer = dsm_layer[0]
    mask_layer = mask_layer[0]
    grid_layer = grid_layer[0]

    QgsMessageLog.logMessage("Tutti i layer necessari sono stati trovati", "Script Analisi Zonale", level=Qgis.Info)

    # Moltiplica il layer DSM con il layer MASK usando l'algoritmo di processing "gdal:rastercalculator"
    QgsMessageLog.logMessage("Inizio moltiplicazione dei layer DSM e MASK", "Script Analisi Zonale", level=Qgis.Info)
    
    params = {
        'INPUT_A': dsm_layer,
        'BAND_A': 1,
        'INPUT_B': mask_layer,
        'BAND_B': 1,
        'FORMULA': 'A*B',
        'NO_DATA': None,
        'RTYPE': 5,  # Float32
        'OUTPUT': 'TEMPORARY_OUTPUT'
    }
    
    result = processing.run("gdal:rastercalculator", params)
    temp_layer = result['OUTPUT']

    QgsMessageLog.logMessage("Moltiplicazione dei layer completata", "Script Analisi Zonale", level=Qgis.Info)

    # Calcola la statistica zonale usando l'algoritmo di processing "qgis:zonalstatistics"
    QgsMessageLog.logMessage("Inizio calcolo della statistica zonale", "Script Analisi Zonale", level=Qgis.Info)
    
    params = {
        'INPUT_RASTER': temp_layer,
        'RASTER_BAND': 1,
        'INPUT_VECTOR': grid_layer,
        'COLUMN_PREFIX': 'med_',
        'STATISTICS': [2],  # 2 corrisponde alla mediana
    }
    
    processing.run("qgis:zonalstatistics", params)

    QgsMessageLog.logMessage("Calcolo della statistica zonale completato", "Script Analisi Zonale", level=Qgis.Info)

    # Gestione dei valori nulli direttamente sul layer grid
    QgsMessageLog.logMessage("Sostituzione dei valori nulli con 0", "Script Analisi Zonale", level=Qgis.Info)
    
    # Assicuriamoci che il layer sia in modalità di modifica
    grid_layer.startEditing()

    # Iterazione sulle features per sostituire i valori nulli con 0
    for feature in grid_layer.getFeatures():
        if feature['med_median'] is None:
            feature['med_median'] = 0
            grid_layer.updateFeature(feature)

    # Salva le modifiche e esci dalla modalità di modifica
    grid_layer.commitChanges()

    QgsMessageLog.logMessage("Sostituzione dei valori nulli completata", "Script Analisi Zonale", level=Qgis.Info)
    QgsMessageLog.logMessage("Script completato con successo", "Script Analisi Zonale", level=Qgis.Success)

# Esegui la funzione principale
esegui_analisi_zonale()