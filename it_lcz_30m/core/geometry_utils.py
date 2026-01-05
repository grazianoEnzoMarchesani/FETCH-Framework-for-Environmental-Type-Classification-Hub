# -*- coding: utf-8 -*-
"""
Geometry Utilities for LCZ v7
Focuses on clustering and hull generation.
"""

import numpy as np
from qgis.core import QgsGeometry, QgsPointXY

from qgis.core import QgsGeometry, QgsPointXY, QgsFeature, QgsVectorLayer
from sklearn.cluster import DBSCAN

def cluster_points_dbscan(features, eps=100.0, min_samples=3):
    """
    Clusters features using DBSCAN.
    
    Args:
        features: List of QgsFeature
        eps: Maximum distance between two samples for one to be considered as in the neighborhood of the other.
        min_samples: The number of samples in a neighborhood for a point to be considered as a core point.
    
    Returns:
        labels: Array of cluster labels ( -1 for noise)
    """
    # Extract coordinates
    coords = []
    for feat in features:
        geom = feat.geometry()
        if geom:
            p = geom.centroid().asPoint()
            coords.append([p.x(), p.y()])
    
    if not coords:
        return []
        
    coords = np.array(coords)
    
    # Run DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(coords)
    return db.labels_

def create_district_geometry(geometries):
    """
    Creates a smooth 'district' geometry from a list of grid cell geometries.
    Uses unaryUnion to ensure no self-overlap, and morphological closing 
    (buffer) to smooth the grid edges into a 'district' shape.
    """
    if not geometries:
        return None
        
    # 1. Union all cells to get the exact footprint
    # unaryUnion is efficient for many adjacent grid cells
    union_geom = QgsGeometry.unaryUnion(geometries)
    if not union_geom or union_geom.isEmpty():
        return None
        
    # 2. Morphological smoothing: buffer out then in
    # Using 8m distance and 1 segment to keep it more 'grid-like' but joined
    # This prevents the 'over-rounded' look the user disliked.
    smooth_geom = union_geom.buffer(8.0, 1).buffer(-8.0, 1)
    
    # 3. Final validation to ensure no self-intersections
    return smooth_geom.makeValid()

def cluster_multidimensional(features, params_list, eps=0.5, min_samples=3, spatial_scale=100.0, weights=None):
    """
    Clusters features based on both space and morphological parameters.
    Improved version: enforces spatial compactness by scaling morphological 
    variance relative to a fixed spatial radius.
    """
    from sklearn.preprocessing import StandardScaler
    
    data_morph = []
    coords = []
    for feat in features:
        # Spatial coords (absolute meters)
        p = feat.geometry().centroid().asPoint()
        coords.append([p.x(), p.y()])
        
        # Morphological params
        row = []
        for p_name in params_list:
            val = feat.attribute(p_name)
            row.append(float(val) if val is not None else 0.0)
        data_morph.append(row)
        
    if not coords:
        return []
        
    coords = np.array(coords)
    data_morph = np.array(data_morph)
    
    # 1. Scale morphological data to unit variance
    scaler = StandardScaler()
    morph_scaled = scaler.fit_transform(data_morph)
    
    # Apply custom weights if provided
    if weights:
        for i, p_name in enumerate(params_list):
            if p_name in weights:
                morph_scaled[:, i] *= weights[p_name]
    
    # 2. Scale coordinates such that 'eps' in DBSCAN has a physical meaning 
    # for the spatial component. 
    # Current spatial_scale: 1 unit in 'DBSCAN space' = spatial_scale meters
    coords_scaled = (coords - np.mean(coords, axis=0)) / spatial_scale
    
    # 3. Combine. 
    data_combined = np.hstack([coords_scaled, morph_scaled])
    
    # Run DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(data_combined)
    return db.labels_

def split_heterogeneous_clusters(features, labels, param_name, std_threshold=4.0):
    """
    Refines initial clustering by splitting any cluster that is too 
    morphologically diverse (The Perfectionist logic).
    
    Args:
        features: List of QgsFeature
        labels: Original cluster labels from cluster_multidimensional
        param_name: Field name to check for variance (e.g., z_h)
        std_threshold: Standard deviation threshold to trigger a split. (Default 4.0m)
        
    Returns:
        A list of sub-lists, where each sub-list contains features of a 'pure' cluster.
    """
    initial_clusters = {}
    for i, label in enumerate(labels):
        if label == -1: continue # Noise
        if label not in initial_clusters: initial_clusters[label] = []
        initial_clusters[label].append(features[i])
        
    final_clusters = []
    for cid, cluster_feats in initial_clusters.items():
        vals = [float(f.attribute(param_name)) for f in cluster_feats if f.attribute(param_name) is not None and str(f.attribute(param_name)) != 'NULL']
        
        # Perfectionist Split: if diversity is high, split by median
        if len(vals) > 4 and np.std(vals) > std_threshold:
            median_val = np.median(vals)
            sub1 = [f for f in cluster_feats if float(f.attribute(param_name) or 0) <= median_val]
            sub2 = [f for f in cluster_feats if float(f.attribute(param_name) or 0) > median_val]
            if sub1: final_clusters.append(sub1)
            if sub2: final_clusters.append(sub2)
        else:
            final_clusters.append(cluster_feats)
            
    return final_clusters
