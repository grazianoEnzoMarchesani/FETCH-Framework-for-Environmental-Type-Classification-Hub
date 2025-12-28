from qgis.core import QgsProject, QgsRasterLayer
from qgis.utils import iface
from PyQt5.QtWidgets import QFileDialog, QMessageBox

def load_and_rename_layers():
    """
    Carica e rinomina i layer richiesti in QGIS usando una finestra di dialogo per la selezione dei file.
    """
    # Definizione dei nomi dei layer richiesti
    required_layers = ['rgb', 'dsm', 'mask', 'class']
    
    # Dizionario per memorizzare i layer
    layers = {}
    
    for layer_name in required_layers:
        # Verifica se il layer è già caricato
        existing_layer = QgsProject.instance().mapLayersByName(layer_name)
        
        if existing_layer:
            print(f"Layer '{layer_name}' già presente nel progetto.")
            layers[layer_name] = existing_layer[0]
        else:
            # Apri la finestra di dialogo per selezionare il file
            file_path, _ = QFileDialog.getOpenFileName(iface.mainWindow(), f"Seleziona il file per {layer_name}",
                                                       "", "Raster Files (*.tif *.tiff *.img);;All Files (*)")
            
            if file_path:
                # Carica il layer
                layer = QgsRasterLayer(file_path, layer_name)
                
                if layer.isValid():
                    # Aggiungi il layer al progetto
                    QgsProject.instance().addMapLayer(layer)
                    print(f"Layer '{layer_name}' caricato con successo.")
                    layers[layer_name] = layer
                else:
                    QMessageBox.warning(iface.mainWindow(), "Errore", f"Impossibile caricare il layer {layer_name}.")
                    print(f"Errore nel caricamento del layer '{layer_name}'.")
                    return None
            else:
                QMessageBox.warning(iface.mainWindow(), "Errore", f"Nessun file selezionato per il layer {layer_name}.")
                print(f"Nessun file selezionato per il layer '{layer_name}'.")
                return None
    
    # Rinomina i layer se necessario
    for layer_name, layer in layers.items():
        if layer.name() != layer_name:
            old_name = layer.name()
            layer.setName(layer_name)
            print(f"Layer rinominato da '{old_name}' a '{layer_name}'.")
    
    print("Tutti i layer sono stati caricati e rinominati correttamente.")
    return layers

# Esegui la funzione principale
result = load_and_rename_layers()

if result:
    print("Elaborazione completata con successo.")
else:
    print("Si è verificato un errore durante l'elaborazione.")