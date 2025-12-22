# -*- coding: utf-8 -*-

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
