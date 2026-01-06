# -*- coding: utf-8 -*-
"""
Geometry Utilities for LCZ v8
Advanced clustering, district generation, and geometry operations.

Improvements:
- HDBSCAN for adaptive density clustering
- Multi-parameter split with configurable thresholds
- Natural area district support
- Road-aware clustering (optional)
- Alpha shapes for organic geometries
"""

import numpy as np
from qgis.core import QgsGeometry, QgsPointXY, QgsFeature, QgsVectorLayer, QgsSpatialIndex
from sklearn.preprocessing import StandardScaler

# Try to import HDBSCAN, fallback to DBSCAN if not available
try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    from sklearn.cluster import DBSCAN


def cluster_points_dbscan(features, eps=100.0, min_samples=3):
    """
    Basic DBSCAN clustering on spatial coordinates only.
    """
    coords = []
    for feat in features:
        geom = feat.geometry()
        if geom:
            p = geom.centroid().asPoint()
            coords.append([p.x(), p.y()])
    
    if not coords:
        return []
        
    coords = np.array(coords)
    
    from sklearn.cluster import DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(coords)
    return db.labels_


def create_district_geometry(geometries, use_alpha_shape=False, alpha_ratio=0.3):
    """
    Creates a district geometry from grid cell geometries.
    
    Args:
        geometries: List of QgsGeometry objects
        use_alpha_shape: If True, use concave hull for more organic shapes
        alpha_ratio: Ratio for concave hull (0=convex, 1=very concave)
    
    Returns:
        QgsGeometry: The district boundary
    """
    if not geometries:
        return None
        
    # 1. Union all cells
    union_geom = QgsGeometry.unaryUnion(geometries)
    if not union_geom or union_geom.isEmpty():
        return None
    
    if use_alpha_shape:
        try:
            # Use Shapely for alpha shapes if available
            from shapely.wkb import loads, dumps
            from shapely.ops import unary_union
            from shapely import concave_hull
            
            # Convert to Shapely
            shapely_geom = loads(union_geom.asWkb())
            
            # Create concave hull for more organic shape
            hull = concave_hull(shapely_geom, ratio=alpha_ratio)
            
            # Convert back to QGIS
            return QgsGeometry().fromWkb(dumps(hull))
        except ImportError:
            pass  # Fall through to buffer method
    
    # 2. Morphological smoothing: buffer out then in (original method)
    smooth_geom = union_geom.buffer(8.0, 1).buffer(-8.0, 1)
    
    return smooth_geom.makeValid()


def cluster_multidimensional_advanced(features, params_list, weights=None, 
                                       min_cluster_size=3, spatial_scale=45.0,
                                       use_hdbscan=True, eps=1.2):
    """
    Advanced multidimensional clustering using HDBSCAN or DBSCAN.
    
    Args:
        features: List of QgsFeature
        params_list: List of field names to include in clustering
        weights: Dict of {field_name: weight} for parameter importance
        min_cluster_size: Minimum cluster size (HDBSCAN) or min_samples (DBSCAN)
        spatial_scale: One unit in cluster space = this many meters
        use_hdbscan: Use HDBSCAN if available (adaptive density)
        eps: DBSCAN epsilon (only if HDBSCAN not used)
        
    Returns:
        labels: Array of cluster labels
    """
    data_morph = []
    coords = []
    
    for feat in features:
        # Spatial coords
        p = feat.geometry().centroid().asPoint()
        coords.append([p.x(), p.y()])
        
        # Morphological params
        row = []
        for p_name in params_list:
            val = feat.attribute(p_name)
            if val is not None and str(val) not in ('NULL', ''):
                row.append(float(val))
            else:
                row.append(0.0)
        data_morph.append(row)
        
    if not coords:
        return []
        
    coords = np.array(coords)
    data_morph = np.array(data_morph)
    
    # Scale morphological data
    scaler = StandardScaler()
    morph_scaled = scaler.fit_transform(data_morph)
    
    # Apply custom weights
    if weights:
        for i, p_name in enumerate(params_list):
            if p_name in weights:
                morph_scaled[:, i] *= weights[p_name]
    
    # Scale spatial coordinates
    coords_scaled = (coords - np.mean(coords, axis=0)) / spatial_scale
    
    # Combine features
    data_combined = np.hstack([coords_scaled, morph_scaled])
    
    # Clustering
    if use_hdbscan and HDBSCAN_AVAILABLE:
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=2,
            metric='euclidean',
            cluster_selection_epsilon=0.5,
            core_dist_n_jobs=1  # Disable parallel to avoid joblib crashes in QGIS
        )
        labels = clusterer.fit_predict(data_combined)
    else:
        from sklearn.cluster import DBSCAN
        db = DBSCAN(eps=eps, min_samples=min_cluster_size).fit(data_combined)
        labels = db.labels_
    
    return labels


def cluster_multidimensional(features, params_list, eps=0.5, min_samples=3, 
                             spatial_scale=100.0, weights=None):
    """
    Legacy wrapper for backward compatibility.
    Calls cluster_multidimensional_advanced with DBSCAN fallback.
    """
    return cluster_multidimensional_advanced(
        features, params_list, 
        weights=weights,
        min_cluster_size=min_samples,
        spatial_scale=spatial_scale,
        use_hdbscan=False,  # Use DBSCAN for legacy compatibility
        eps=eps
    )


def split_heterogeneous_clusters(features, labels, param_name, std_threshold=4.0):
    """
    Legacy single-parameter split for backward compatibility.
    """
    return split_heterogeneous_clusters_multi(
        features, labels, 
        params_thresholds={param_name: std_threshold}
    )


def split_heterogeneous_clusters_multi(features, labels, params_thresholds):
    """
    Splits clusters that are too morphologically diverse on ANY of the specified parameters.
    
    Args:
        features: List of QgsFeature
        labels: Cluster labels from clustering
        params_thresholds: Dict of {param_name: std_threshold}
                          e.g. {'z_h': 4.0, 'building_frac': 15.0, 'svf_mean': 0.15}
    
    Returns:
        List of feature lists (each sublist is a pure cluster)
    """
    # Group features by label
    initial_clusters = {}
    for i, label in enumerate(labels):
        if label == -1:  # Noise
            continue
        if label not in initial_clusters:
            initial_clusters[label] = []
        initial_clusters[label].append(features[i])
    
    final_clusters = []
    
    for cid, cluster_feats in initial_clusters.items():
        needs_split = False
        split_param = None
        
        # Check each parameter for heterogeneity
        for param_name, threshold in params_thresholds.items():
            vals = []
            for f in cluster_feats:
                v = f.attribute(param_name)
                if v is not None and str(v) not in ('NULL', ''):
                    vals.append(float(v))
            
            if len(vals) > 4 and np.std(vals) > threshold:
                needs_split = True
                split_param = param_name
                break
        
        if needs_split and split_param:
            # Split by median of the most heterogeneous parameter
            vals = [float(f.attribute(split_param) or 0) for f in cluster_feats]
            median_val = np.median(vals)
            
            sub1 = [f for f in cluster_feats if float(f.attribute(split_param) or 0) <= median_val]
            sub2 = [f for f in cluster_feats if float(f.attribute(split_param) or 0) > median_val]
            
            if sub1:
                final_clusters.append(sub1)
            if sub2:
                final_clusters.append(sub2)
        else:
            final_clusters.append(cluster_feats)
    
    return final_clusters


def cluster_with_road_barriers(features, roads_layer, params_list, weights=None,
                                min_cluster_size=3, spatial_scale=45.0):
    """
    Clusters features while respecting road boundaries.
    Features separated by roads are assigned to different clusters.
    
    Args:
        features: List of QgsFeature
        roads_layer: QgsVectorLayer of roads (polylines)
        params_list: Morphological parameters for clustering
        weights: Parameter weights
        min_cluster_size: Minimum cluster size
        spatial_scale: Spatial scaling factor
    
    Returns:
        labels: Cluster labels
    """
    if not roads_layer or not roads_layer.isValid():
        # Fallback to regular clustering if no roads
        return cluster_multidimensional_advanced(
            features, params_list, weights,
            min_cluster_size, spatial_scale
        )
    
    # Step 1: Pre-segment features by road crossings
    # Build spatial index for roads
    road_index = QgsSpatialIndex()
    road_geoms = {}
    for road in roads_layer.getFeatures():
        road_index.addFeature(road)
        road_geoms[road.id()] = road.geometry()
    
    # For each pair of adjacent features, check if a road separates them
    # This is a simplified approach - assign a "road zone" ID to each feature
    zone_ids = {}
    current_zone = 0
    
    for feat in features:
        if feat.id() in zone_ids:
            continue
            
        # BFS to find all connected features (not separated by roads)
        queue = [feat]
        visited = {feat.id()}
        zone_ids[feat.id()] = current_zone
        
        while queue:
            current = queue.pop(0)
            current_geom = current.geometry()
            
            for other in features:
                if other.id() in visited:
                    continue
                    
                other_geom = other.geometry()
                
                # Check if path between centroids crosses a road
                path = QgsGeometry.fromPolylineXY([
                    current_geom.centroid().asPoint(),
                    other_geom.centroid().asPoint()
                ])
                
                # Quick bounding box check
                candidate_roads = road_index.intersects(path.boundingBox())
                
                crosses_road = False
                for road_id in candidate_roads:
                    if path.crosses(road_geoms[road_id]):
                        crosses_road = True
                        break
                
                if not crosses_road and current_geom.distance(other_geom) < spatial_scale:
                    visited.add(other.id())
                    zone_ids[other.id()] = current_zone
                    queue.append(other)
        
        current_zone += 1
    
    # Step 2: Cluster within each zone
    zones = {}
    for feat in features:
        z = zone_ids.get(feat.id(), -1)
        if z not in zones:
            zones[z] = []
        zones[z].append(feat)
    
    # Assign final labels
    final_labels = np.full(len(features), -1)
    feat_id_to_idx = {f.id(): i for i, f in enumerate(features)}
    
    label_offset = 0
    for zone_feats in zones.values():
        if len(zone_feats) < min_cluster_size:
            continue
            
        zone_labels = cluster_multidimensional_advanced(
            zone_feats, params_list, weights,
            min_cluster_size, spatial_scale, 
            use_hdbscan=HDBSCAN_AVAILABLE
        )
        
        for i, feat in enumerate(zone_feats):
            idx = feat_id_to_idx[feat.id()]
            if zone_labels[i] != -1:
                final_labels[idx] = zone_labels[i] + label_offset
        
        label_offset += max(zone_labels) + 1 if len(zone_labels) > 0 else 0
    
    return final_labels


def cluster_natural_areas(features, canopy_field='z_h', tcd_path=None, 
                          min_cluster_size=3, spatial_scale=60.0):
    """
    Clusters natural (non-built) areas using canopy height and tree cover density.
    
    Args:
        features: List of QgsFeature (natural areas only)
        canopy_field: Field name for canopy height
        tcd_path: Path to TCD raster (optional, for TCD-weighted clustering)
        min_cluster_size: Minimum cluster size
        spatial_scale: Spatial scaling in meters
    
    Returns:
        labels: Cluster labels for natural area distinction (A vs B vs C vs D)
    """
    if not features:
        return []
    
    # Use canopy height as primary clustering parameter
    params_list = [canopy_field]
    weights = {canopy_field: 2.0}
    
    # If we have SVF calculated, use it too
    # Check if svf_mean exists
    if features[0].fields().indexFromName('svf_mean') != -1:
        params_list.append('svf_mean')
        weights['svf_mean'] = 2.5
    
    # If pervious fraction exists, include it
    if features[0].fields().indexFromName('pervious_frac') != -1:
        params_list.append('pervious_frac')
        weights['pervious_frac'] = 1.0
    
    return cluster_multidimensional_advanced(
        features, params_list, weights,
        min_cluster_size=min_cluster_size,
        spatial_scale=spatial_scale,
        use_hdbscan=HDBSCAN_AVAILABLE
    )
