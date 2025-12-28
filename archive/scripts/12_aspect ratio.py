from qgis.core import QgsProject, QgsVectorLayer, QgsField, QgsExpression, QgsFeature, QgsExpressionContext, QgsExpressionContextUtils
from PyQt5.QtCore import QVariant

def find_layer(layer_name):
    """
    Trova un layer nel progetto QGIS dato il suo nome.
    Restituisce None se il layer non viene trovato.
    """
    layers = QgsProject.instance().mapLayersByName(layer_name)
    return layers[0] if layers else None

def check_field_exists(layer, field_name):
    """
    Verifica se un campo esiste nel layer.
    """
    return field_name in [field.name() for field in layer.fields()]

def add_field(layer, field_name, field_type):
    """
    Aggiunge un nuovo campo al layer se non esiste già.
    """
    if not check_field_exists(layer, field_name):
        layer.dataProvider().addAttributes([QgsField(field_name, field_type)])
        layer.updateFields()

def main():
    # Identificazione e selezione del layer "grid"
    grid_layer = find_layer("grid")
    if not grid_layer:
        raise ValueError("Il layer 'grid' non è stato trovato nel progetto.")

    # Verifica della presenza delle colonne richieste
    required_fields = ["median_dist", "mean_build_height"]
    for field in required_fields:
        if not check_field_exists(grid_layer, field):
            raise ValueError(f"La colonna '{field}' non è presente nel layer 'grid'.")

    # Aggiunta della nuova colonna "aspect_ratio" se non esiste già
    add_field(grid_layer, "aspect_ratio", QVariant.Double)

    # Inizia la modifica del layer
    grid_layer.startEditing()

    # Aggiorna i valori di median_dist per essere sempre >= 1 e sostituisce i valori NULL con 1
    median_dist_idx = grid_layer.fields().indexOf("median_dist")
    for feature in grid_layer.getFeatures():
        median_dist = feature["median_dist"]
        # Controllo per NULL e valori inferiori a 1
        if median_dist is None or median_dist < 1:
            grid_layer.changeAttributeValue(feature.id(), median_dist_idx, 1)

    # Calcolo dei valori per la colonna "aspect_ratio"
    expression = QgsExpression('CASE WHEN "median_dist" < 1 THEN "mean_build_height" ELSE "mean_build_height" / "median_dist" END')
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(grid_layer))

    # Itera attraverso le features e calcola l'aspect_ratio
    aspect_ratio_idx = grid_layer.fields().indexOf("aspect_ratio")
    for feature in grid_layer.getFeatures():
        context.setFeature(feature)
        aspect_ratio = expression.evaluate(context)
        grid_layer.changeAttributeValue(feature.id(), aspect_ratio_idx, aspect_ratio)

    # Commit delle modifiche
    success = grid_layer.commitChanges()

    if success:
        print("Calcolo dell'aspect_ratio completato con successo.")
    else:
        print("Si è verificato un errore durante il calcolo dell'aspect_ratio.")

# Esecuzione dello script
try:
    main()
except ValueError as e:
    print(f"Errore: {str(e)}")
except Exception as e:
    print(f"Si è verificato un errore imprevisto: {str(e)}")