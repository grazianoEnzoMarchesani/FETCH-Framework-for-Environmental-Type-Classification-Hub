#!/bin/bash

# FETCH Dependency Installer for MacOS
# This script targets the QGIS Python environment found in the standard MacOS installation path.

echo "FETCH Framework - Installer Dipendenze"
echo "--------------------------------------"

# Standard MacOS QGIS Python Path (confirmed from user log)
QGIS_PYTHON="/Applications/QGIS-final-3_44_5.app/Contents/MacOS/python3.12"

if [ ! -f "$QGIS_PYTHON" ]; then
    # Try alternate path
    QGIS_PYTHON="/Applications/QGIS-final-3_44_5.app/Contents/MacOS/bin/python3"
fi

if [ ! -f "$QGIS_PYTHON" ]; then
    echo "ERRORE: Non ho trovato l'eseguibile Python di QGIS."
    echo "Il percorso $QGIS_PYTHON non esiste."
    exit 1
fi

echo "Uso Python QGIS: $QGIS_PYTHON"
echo "Tentativo di installazione dipendenze (prefer-binary)..."

# Ensure pip is present and updated
"$QGIS_PYTHON" -m ensurepip --user
"$QGIS_PYTHON" -m pip install --upgrade pip --user

# Install requirements
# We use --user to avoid permissions issues and --prefer-binary for faster, safer install on Mac
"$QGIS_PYTHON" -m pip install --user --prefer-binary --no-cache-dir scipy pandas numpy rasterio eodag statsmodels matplotlib

if [ $? -eq 0 ]; then
    echo "--------------------------------------"
    echo "✓ Installazione completata con successo!"
    echo "Riavvia QGIS per utilizzare il plugin."
else
    echo "--------------------------------------"
    echo "✗ Si è verificato un errore durante l'installazione."
    echo "Prova a eseguire lo script install_deps_qgis.py all'interno della console Python di QGIS."
fi
