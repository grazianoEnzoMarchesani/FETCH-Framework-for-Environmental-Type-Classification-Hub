import os
import shutil
from qgis.core import QgsRasterLayer, QgsProject
from qgis import processing
from PyQt5.QtWidgets import QFileDialog

# Funzione per selezionare la cartella
def select_folder():
    folder = QFileDialog.getExistingDirectory(None, "Seleziona cartella con file DSM, RGB e MASK")
    return folder

# Funzione per unire i raster con tipo di output specificato
def merge_rasters(input_files, output_file, output_type):
    processing.run("gdal:merge", {
        'INPUT': input_files,
        'PCT': False,
        'SEPARATE': False,
        'NODATA_INPUT': None,
        'NODATA_OUTPUT': None,
        'OPTIONS': '',
        'EXTRA': f'-ot {output_type}',
        'OUTPUT': output_file
    })

# Funzione per spostare i file in una sottocartella
def move_files(input_files, destination_folder):
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    for file in input_files:
        # Sposta il file .tif
        shutil.move(file, os.path.join(destination_folder, os.path.basename(file)))
        
        # Verifica e sposta il file .tif.aux.xml associato
        aux_file = file + ".aux.xml"
        if os.path.exists(aux_file):
            shutil.move(aux_file, os.path.join(destination_folder, os.path.basename(aux_file)))

# Seleziona la cartella
folder_path = select_folder()

# Verifica se la cartella è stata selezionata
if not folder_path:
    print("Nessuna cartella selezionata.")
else:
    # Crea la sottocartella "file_separati"
    separated_folder = os.path.join(folder_path, "file_separati")

    # Unisci i file DSM in formato Float32 e sposta i file separati
    dsm_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.startswith("dsm") and f.endswith(".tif")]
    if dsm_files:
        dsm_output = os.path.join(folder_path, "dsm_unito.tif")
        merge_rasters(dsm_files, dsm_output, "Float32")
        print(f"File DSM unito salvato in: {dsm_output}")
        move_files(dsm_files, separated_folder)
    else:
        print("Nessun file DSM trovato con il prefisso 'dsm'.")

    # Unisci i file RGB in formato Byte (8 bit senza segno) e sposta i file separati
    rgb_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.startswith("rgb") and f.endswith(".tif")]
    if rgb_files:
        rgb_output = os.path.join(folder_path, "rgb_unito.tif")
        merge_rasters(rgb_files, rgb_output, "Byte")
        print(f"File RGB unito salvato in: {rgb_output}")
        move_files(rgb_files, separated_folder)
    else:
        print("Nessun file RGB trovato con il prefisso 'rgb'.")

    # Unisci i file MASK in formato Byte (8 bit senza segno) e sposta i file separati
    mask_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.startswith("mask") and f.endswith(".tif")]
    if mask_files:
        mask_output = os.path.join(folder_path, "mask_unito.tif")
        merge_rasters(mask_files, mask_output, "Byte")
        print(f"File MASK unito salvato in: {mask_output}")
        move_files(mask_files, separated_folder)
    else:
        print("Nessun file MASK trovato con il prefisso 'mask'.")