# -*- coding: utf-8 -*-

import os
import sys


def apply_plugin_fixes():
    """
    Apply necessary platform-specific fixes for the FETCH plugin.
    
    On macOS, this:
    1. Sets sys.executable to the actual Python interpreter (prevents QGIS GUI duplication)
    2. Sets multiprocessing start method to 'spawn'
    3. Configures PROJ_LIB/PROJ_DATA environment variables
    
    Should be called at plugin startup (main.py) and in specialized modules (e.g. downloaders).
    """
    if sys.platform != 'darwin':
        return  # Only needed on macOS
    
    import multiprocessing
    
    # --- Multiprocessing Fix ---
    # Prevents QGIS from opening duplicate GUI windows when using multiprocessing
    exe_dir = os.path.dirname(sys.executable)
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    candidate_names = [f"python{py_ver}", "python3", "Python"]
    
    found_p = None
    for folder in [exe_dir, os.path.join(exe_dir, "bin")]:
        for name in candidate_names:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                found_p = p
                break
        if found_p:
            break
    
    if found_p:
        try:
            if not hasattr(sys, '_qgis_executable'):
                sys._qgis_executable = sys.executable
            sys.executable = found_p
            multiprocessing.set_executable(found_p)
        except:
            pass
    
    try:
        if multiprocessing.get_start_method(allow_none=True) != 'spawn':
            multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # Already set
    
    # --- PROJ Environment Fix ---
    # Fixes "Valid PROJ data directory not found" errors
    try:
        from qgis.core import QgsApplication
        proj_path = os.path.join(QgsApplication.pkgDataPath(), "proj")
        if os.path.exists(proj_path):
            os.environ['PROJ_LIB'] = proj_path
            os.environ['PROJ_DATA'] = proj_path
            try:
                import pyproj
                pyproj.datadir.set_data_dir(proj_path)
            except:
                pass
    except:
        pass


from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsGeometry

def is_within_italy(extent, crs_auth_id):
    """
    Verifica se un extent si trova nell'area di competenza dei sistemi Monte Mario (Italia).
    Utilizza un bounding box generoso (Lon 6-19, Lat 35-48) per evitare falsi negativi 
    nelle zone costiere o di confine.
    """
    if extent.isEmpty():
        return False
        
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
    
    # Transform centroid to WGS84
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    try:
        center = extent.center()
        w84_center = transform.transform(center)
        lon, lat = w84_center.x(), w84_center.y()
        
        # Generous bounds for Italy (Mainland + Islands + Territorial Waters)
        # Longitude: 6.0E to 19.0E
        # Latitude: 35.0N to 48.0N
        return (6.0 <= lon <= 19.0) and (35.0 <= lat <= 48.0)
        
    except Exception:
        return False

def get_target_crs_for_extent(extent, crs_auth_id):
    """
    Determina il CRS ottimale per l'elaborazione metrica.
    Se in Italia: restituisce Gauss-Boaga (EPSG:3003/3004) basato sul meridiano 12°E.
    Se fuori Italia: restituisce la zona UTM appropriata (EPSG:326xx per Nord, 327xx per Sud).
    """
    try:
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
        
        # Transform the centroid for better stability on large/invalid extents
        center = extent.center()
        w84_center = transform.transform(center)
        
        center_lon = w84_center.x()
        center_lat = w84_center.y()

        # Step 1: Check if inside Italy to apply Monte Mario Gauss-Boaga fix
        if is_within_italy(extent, crs_auth_id):
            # Monte Mario Fuso Ovest (Zone 1) is ~6E to 12.0E
            # Monte Mario Fuso Est (Zone 2) is ~12.0E to 19E
            if center_lon < 12.0:
                return "EPSG:3003"
            else:
                return "EPSG:3004"
        
        # Step 2: Global fallback to UTM Zone
        import math
        utm_zone = int((center_lon + 180) / 6) + 1
        # EPSG:32601-32660 for North hemisphere, 32701-32760 for South
        epsg_base = 32600 if center_lat >= 0 else 32700
        return f"EPSG:{epsg_base + utm_zone}"

    except Exception as e:
        QgsMessageLog.logMessage(f"Fallback Target CRS detection (e: {e})", "FETCH", Qgis.Warning)
        # Default for Italy (Zone 1) if all fails
        return "EPSG:3003"

def download_file_generic(url, local_path, auth=None):
    """Generic file downloader used by various modules with robust SSL error handling."""
    import requests
    from qgis.core import QgsMessageLog, Qgis

    try:
        # Try with SSL verification first
        with requests.get(url, stream=True, auth=auth, timeout=30) as response:
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            return True, "Success"
    except Exception as e:
        error_msg = str(e)
        # Be very inclusive for SSL/Connection errors on macOS
        is_ssl_issue = any(phrase in error_msg for phrase in ["SSL", "certificate", "verify", "handshake", "connection"])
        
        if is_ssl_issue:
            QgsMessageLog.logMessage(f"Possible SSL/Connection issue for {url}. Retrying without verification...", "FETCH", Qgis.Warning)
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                with requests.get(url, stream=True, auth=auth, timeout=60, verify=False) as response:
                    response.raise_for_status()
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    return True, "Success"
            except Exception as e2:
                return False, f"Second-attempt failure: {str(e2)}"
        else:
            return False, error_msg


# =============================================================================
# Project Logger - Dual output to QGIS and file
# =============================================================================

from datetime import datetime
from qgis.core import QgsMessageLog, Qgis


class FetchLogger:
    """
    Dual-output logger for FETCH plugin.
    
    Writes simultaneously to:
    - QgsMessageLog (immediate visibility in QGIS Log Messages panel)
    - Persistent .log file in FETCH+ProjectName folder
    
    Usage:
        from FETCH.core.utils import get_logger
        log = get_logger()
        log.info("Operation completed")
        log.warning("Missing parameter")
        log.critical("Fatal error")
    """
    
    def __init__(self, log_name="FETCH"):
        """
        Initialize the logger.
        
        Args:
            log_name: Name shown in QGIS Log Messages panel
        """
        self.log_name = log_name
        self.log_file = None
        self._setup_file_logger()
    
    def _setup_file_logger(self):
        """Set up file logging to FETCH+ProjectName folder."""
        try:
            project_path = QgsProject.instance().fileName()
            if project_path:
                base_dir = os.path.dirname(project_path)
                project_name = os.path.splitext(os.path.basename(project_path))[0]
                data_dir = os.path.join(base_dir, f"FETCH+{project_name}")
                os.makedirs(data_dir, exist_ok=True)
                self.log_file = os.path.join(data_dir, "fetch_operations.log")
        except Exception:
            pass  # File logging not available
    
    def log(self, message, level=Qgis.Info):
        """
        Log a message to both QGIS and file.
        
        Args:
            message: The message to log
            level: Qgis.Info, Qgis.Warning, or Qgis.Critical
        """
        # QGIS Message Log
        QgsMessageLog.logMessage(str(message), self.log_name, level)
        
        # File log
        self._write_to_file(message, level)
    
    def info(self, message):
        """Log an info message."""
        self.log(message, Qgis.Info)
    
    def warning(self, message):
        """Log a warning message."""
        self.log(message, Qgis.Warning)
    
    def critical(self, message):
        """Log a critical error message."""
        self.log(message, Qgis.Critical)
    
    def success(self, message):
        """Log a success message (shows as info with checkmark prefix)."""
        self.log(f"✓ {message}", Qgis.Info)
    
    def _write_to_file(self, message, level):
        """Write a log entry to the file."""
        if not self.log_file:
            self._setup_file_logger()
        
        if self.log_file:
            try:
                level_map = {
                    Qgis.Info: "INFO",
                    Qgis.Warning: "WARNING",
                    Qgis.Critical: "CRITICAL",
                    Qgis.Success: "SUCCESS"
                }
                level_str = level_map.get(level, "INFO")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] [{level_str}] {message}\n")
            except Exception:
                pass  # Silently fail if file writing fails


# Singleton logger instance
_fetch_logger = None


def get_logger():
    """
    Get or create the FETCH logger singleton instance.
    
    Returns:
        FetchLogger: The shared logger instance
    """
    global _fetch_logger
    if _fetch_logger is None:
        _fetch_logger = FetchLogger()
    return _fetch_logger

