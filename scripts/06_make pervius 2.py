from qgis.core import QgsPointXY, edit, QgsMessageLog
from PyQt5.QtCore import QVariant

def log_message(message):
    print(message)
    QgsMessageLog.logMessage(message, 'PercentageCalculation', level=Qgis.Info)

# Carica i layer
raster_layer = QgsProject.instance().mapLayersByName("pervius_impervius_buildings")[0]
vector_layer = QgsProject.instance().mapLayersByName("grid")[0]

log_message(f"Raster layer: {raster_layer.name()}")
log_message(f"Vector layer: {vector_layer.name()}")

# Verifica che i campi necessari esistano
required_fields = ['perc_impervious', 'perc_pervious', 'perc_buildings']
existing_fields = [field.name() for field in vector_layer.fields()]

for field in required_fields:
    if field not in existing_fields:
        log_message(f"Campo mancante: {field}. Aggiunta in corso...")
        vector_layer.dataProvider().addAttributes([QgsField(field, QVariant.Double)])
        vector_layer.updateFields()

# Funzione per calcolare le percentuali per una singola feature
def calculate_percentages(feature, raster_layer):
    geometry = feature.geometry()
    if not geometry:
        log_message(f"Geometria non valida per la feature {feature.id()}")
        return None

    extent = geometry.boundingBox()
    raster_data_provider = raster_layer.dataProvider()
    xres = raster_layer.rasterUnitsPerPixelX()
    yres = raster_layer.rasterUnitsPerPixelY()
    
    cols = int((extent.xMaximum() - extent.xMinimum()) / xres)
    rows = int((extent.yMaximum() - extent.yMinimum()) / yres)
    
    block = raster_data_provider.block(1, extent, cols, rows)
    
    counts = {0: 0, 1: 0, 2: 0}
    total_pixels = 0
    
    for row in range(rows):
        for col in range(cols):
            value = block.value(row, col)
            if value in counts:
                point = QgsPointXY(extent.xMinimum() + (col + 0.5) * xres,
                                   extent.yMaximum() - (row + 0.5) * yres)
                if geometry.contains(point):
                    counts[value] += 1
                    total_pixels += 1
    
    if total_pixels > 0:
        return {
            'perc_impervious': (counts[0] / total_pixels) * 100,
            'perc_pervious': (counts[1] / total_pixels) * 100,
            'perc_buildings': (counts[2] / total_pixels) * 100
        }
    else:
        log_message(f"Nessun pixel trovato per la feature {feature.id()}")
        return None

# Calcola le percentuali per tutte le feature
feature_count = vector_layer.featureCount()
log_message(f"Numero totale di feature: {feature_count}")

with edit(vector_layer):
    for current, feature in enumerate(vector_layer.getFeatures(), 1):
        if current % 100 == 0:
            log_message(f"Elaborazione feature {current}/{feature_count}")
        
        percentages = calculate_percentages(feature, raster_layer)
        if percentages:
            vector_layer.changeAttributeValues(feature.id(), {
                vector_layer.fields().indexOf(field): value
                for field, value in percentages.items()
            })
        else:
            log_message(f"Impossibile calcolare le percentuali per la feature {feature.id()}")

log_message("Calcolo delle percentuali completato")

# Verifica finale
log_message("Verifica dei risultati:")
required_fields = ['perc_impervious', 'perc_pervious', 'perc_buildings']

for field in required_fields:
    field_index = vector_layer.fields().indexOf(field)
    values = []
    for feature in vector_layer.getFeatures():
        value = feature[field]
        if value is not None and value != NULL:
            values.append(value)
    
    if values:
        min_value = min(values)
        max_value = max(values)
        mean_value = sum(values) / len(values)
        log_message(f"{field} - Min: {min_value:.2f}, Max: {max_value:.2f}, Media: {mean_value:.2f}")
    else:
        log_message(f"{field} - Nessun valore valido trovato")

log_message("Verifica completata")