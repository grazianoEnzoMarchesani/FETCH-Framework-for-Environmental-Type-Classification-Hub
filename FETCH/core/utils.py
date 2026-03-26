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
    Checks if a QgsRectangle is within the Italian territory using a simplified polygon.
    Italy approximate polygon in WGS84 to exclude Balkans and neighboring areas.
    """
    if extent.isEmpty():
        return False
        
    # Simplified WKT for Italy (Mainland + major islands)
    italy_wkt = (
        "POLYGON(("
        "6.6 47.1, 11.1 47.1, 13.9 46.8, 14.0 45.4, 15.5 42.0, 18.6 40.5, "
        "18.6 39.7, 17.5 39.0, 15.8 36.5, 14.5 36.5, 11.5 35.3, 11.0 38.0, "
        "8.0 38.0, 7.5 41.0, 6.6 44.0, 6.6 47.1"
        "))"
    )
    italy_geom = QgsGeometry.fromWkt(italy_wkt)
    
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
    
    # Transform extent to WGS84
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    try:
        # Create a geometry from the extent
        extent_geom = QgsGeometry.fromRect(extent)
        # In QGIS 3, transform() modifies the geometry in-place and returns a status code
        res = extent_geom.transform(transform)
        if res != 0: # 0 means Success
            return False
    except:
        return False
        
    # Check if the AOI intersects the Italian territory
    return italy_geom.intersects(extent_geom)

def get_target_crs_for_extent(extent, crs_auth_id):
    """
    Determina il CRS Gauss-Boaga (Monte Mario) corretto basato sul centroide dell'extent.
    Restituisce EPSG:3003 (Fuso Ovest) o EPSG:3004 (Fuso Est) separati dal meridiano 12°E.
    """
    try:
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
        
        # Transform the centroid for better stability on large/invalid extents
        center = extent.center()
        w84_center = transform.transform(center)
        
        center_lon = w84_center.x()
        
        # Monte Mario Fuso Ovest (Zone 1) is ~6E to 12.0E
        # Monte Mario Fuso Est (Zone 2) is ~12.0E to 19E
        if center_lon < 12.0:
            return "EPSG:3003"
        else:
            return "EPSG:3004"
    except Exception as e:
        QgsMessageLog.logMessage(f"Fallback Target CRS detection (e: {e})", "FETCH", Qgis.Warning)
        # Default for Italy (Zone 1)
        return "EPSG:3003"

def download_file_generic(url, local_path, auth=None):
    """Generic file downloader used by various modules with robust SSL error handling."""
    import requests
    from qgis.core import QgsMessageLog, Qgis

    try:
        # Try with SSL verification first
        response = requests.get(url, stream=True, auth=auth, timeout=30)
        response.raise_for_status()
    except Exception as e:
        error_msg = str(e)
        # Be very inclusive for SSL/Connection errors on macOS
        is_ssl_issue = any(phrase in error_msg for phrase in ["SSL", "certificate", "verify", "handshake", "connection"])
        
        if is_ssl_issue:
            QgsMessageLog.logMessage(f"Possible SSL/Connection issue for {url}. Retrying without verification...", "FETCH", Qgis.Warning)
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = requests.get(url, stream=True, auth=auth, timeout=60, verify=False)
                response.raise_for_status()
            except Exception as e2:
                return False, f"Second-attempt failure: {str(e2)}"
        else:
            return False, error_msg

    try:
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk: f.write(chunk)
        return True, "Success"
    except Exception as e:
        return False, str(e)


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

