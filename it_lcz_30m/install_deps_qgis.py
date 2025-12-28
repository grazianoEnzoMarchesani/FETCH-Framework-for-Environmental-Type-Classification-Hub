# -*- coding: utf-8 -*-
"""
FETCH Plugin - Dependency Installer for QGIS
Run this script inside the QGIS Python Console to install missing dependencies.
"""

import sys
import subprocess
import os

def install_dependencies():
    import sys
    import subprocess
    import os
    from qgis.core import QgsMessageLog, Qgis, QgsApplication
    from qgis.utils import iface

    def log(msg, level=Qgis.Info):
        print(msg)
        QgsMessageLog.logMessage(str(msg), 'FETCH', level)
        if iface:
            iface.messageBar().pushMessage("FETCH", str(msg), level=level, duration=3)

    log("=== FETCH: Avvio Installazione Dipendenze ===")
    
    # Updated Requirements with prerequisites for statsmodels
    requirements = ["scipy", "pandas", "numpy", "rasterio", "eodag", "statsmodels", "matplotlib"]
    
    # On MacOS, sys.executable might point to the QGIS binary instead of python
    python_exe = sys.executable
    if "QGIS" in python_exe and "MacOS" in python_exe and not python_exe.endswith("python3"):
        base = os.path.dirname(python_exe)
        potential = os.path.join(base, "python3")
        if os.path.exists(potential):
            python_exe = potential

    log(f"Utilizzo Python: {python_exe}")
    log(f"QGIS sys.prefix: {sys.prefix}")
    log(f"QGIS sys.path: {sys.path}")
    
    # Prepare environment for subprocess
    env = os.environ.copy()
    
    # We found libraries here
    res_python = "/Applications/QGIS-final-3_44_5.app/Contents/Resources/python3.11"
    
    paths = sys.path.copy()
    if os.path.exists(res_python) and res_python not in paths:
        paths.insert(0, res_python)
    
    env["PYTHONPATH"] = os.pathsep.join(paths)
    
    # Force PYTHONHOME to the app contents if prefix is broken
    if "/Users/runner" in sys.prefix:
        log("Rilevato prefix errato (build runner). Forzo PYTHONPATH e home.", Qgis.Warning)
        # On Mac, PYTHONPATH is often enough if it contains the stdlib

    # Try to upgrade pip first
    try:
        log("Aggiornamento pip...")
        subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], env=env, capture_output=True)
    except:
        pass

    for package in requirements:
        try:
            # Check availability
            __import__(package.replace("-", "_"))
            log(f"✓ {package} è già presente.")
            continue
        except ImportError:
            log(f"⏳ Installazione di {package} (binary preference)...")
            try:
                # Use subprocess.run to capture output for debugging
                cmd = [python_exe, "-m", "pip", "install", "--prefer-binary", "--no-cache-dir", package]
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                if result.returncode == 0:
                    log(f"✓ {package} installato!")
                else:
                    raise Exception(result.stderr or result.stdout)
            except Exception as e:
                log(f"⚠ Prova user-mode per {package}...", Qgis.Warning)
                try:
                    cmd = [python_exe, "-m", "pip", "install", "--user", "--prefer-binary", package]
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                    if result.returncode == 0:
                        log(f"✓ {package} installato (user)!")
                    else:
                        raise Exception(result.stderr or result.stdout)
                except Exception as e2:
                    log(f"❌ Fallito: {package}.", Qgis.Critical)
                    log(f"ERRORE DETTAGLIATO:\n{e2}", Qgis.Critical)

    log("=== PROCESSO COMPLETATO ===")
    log("RIAVVIA QGIS per caricare i nuovi pacchetti.", Qgis.Success)

# Call directly to ensure execution when using exec()
install_dependencies()
