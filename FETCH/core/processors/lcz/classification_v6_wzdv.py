# -*- coding: utf-8 -*-
"""
LCZ Classification Module - WEIGHTED Z-DISTANCE WITH VETO (v6.0)

Implements a statistically weighted classification method.
Weights are derived from the Z-score leadership table (Z^2).
Includes a Veto mechanism for dominant parameters.
"""

import numpy as np
from qgis.core import QgsVectorLayer, QgsField, Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QMetaType

# Centralized constants
from ...constants import LCZMappings, FileNames, FolderNames, FieldNames


class LCZClassifierWZDV:
    """
    Classifies features using Weighted Z-Distance and Veto logic.
    """
    
    LCZ_CLASSES = LCZMappings.CLASSES
    LCZ_PARAMETERS = LCZMappings.PARAMETERS
    
    # Internal mapping between Z-score keys and LCZMappings keys
    PARAM_MAP = {
        'svf': 'sky_view_factor',
        'aspect_ratio': 'aspect_ratio',
        'building_frac': 'building_surface_fraction',
        'impervious_frac': 'impervious_surface_fraction',
        'pervious_frac': 'pervious_surface_fraction',
        'z_h': 'height_roughness',
        'terrain_rough': 'terrain_roughness',
        'admittance': 'surface_admittance',
        'albedo': 'surface_albedo',
        'anthro_heat': 'anthropogenic_heat'
    }
    
    # --- CONFIGURATION PROFILES ---
    # Each profile defines WEIGHTS (Z^2 style) and VETO_RANKING (statistical leadership)
    PROFILES = {
        'z-score': {
            'weights': {
                '1':  {'aspect_ratio': 5.36, 'z_h': 3.65, 'svf': 2.96, 'anthro_heat': 2.57, 'terrain_rough': 2.00, 'pervious_frac': 1.73, 'building_frac': 1.15, 'impervious_frac': 0.96, 'albedo': 0.51, 'admittance': 0.40},
                '2':  {'admittance': 2.06, 'building_frac': 1.73, 'aspect_ratio': 1.52, 'z_h': 1.03, 'pervious_frac': 1.00, 'svf': 1.00, 'albedo': 0.51, 'terrain_rough': 0.50, 'impervious_frac': 0.25, 'anthro_heat': 0.11},
                '3':  {'building_frac': 1.73, 'svf': 1.54, 'aspect_ratio': 0.64, 'albedo': 0.51, 'pervious_frac': 0.47, 'terrain_rough': 0.22, 'anthro_heat': 0.11, 'z_h': 0.09, 'impervious_frac': 0.07, 'admittance': 0.00},
                '4':  {'z_h': 3.65, 'terrain_rough': 1.39, 'aspect_ratio': 0.34, 'pervious_frac': 0.28, 'admittance': 0.19, 'svf': 0.08, 'impervious_frac': 0.07, 'building_frac': 0.01, 'anthro_heat': 0.00, 'albedo': 0.00},
                '5':  {'z_h': 1.03, 'admittance': 0.70, 'pervious_frac': 0.47, 'impervious_frac': 0.25, 'anthro_heat': 0.09, 'aspect_ratio': 0.06, 'terrain_rough': 0.06, 'building_frac': 0.01, 'svf': 0.00, 'albedo': 0.00},
                '6':  {'svf': 0.19, 'z_h': 0.09, 'anthro_heat': 0.09, 'impervious_frac': 0.07, 'aspect_ratio': 0.06, 'terrain_rough': 0.06, 'pervious_frac': 0.05, 'building_frac': 0.01, 'admittance': 0.00, 'albedo': 0.00},
                '7':  {'building_frac': 5.25, 'svf': 2.19, 'aspect_ratio': 2.10, 'admittance': 1.85, 'albedo': 1.84, 'z_h': 0.51, 'pervious_frac': 0.47, 'impervious_frac': 0.20, 'terrain_rough': 0.06, 'anthro_heat': 0.03},
                '8':  {'pervious_frac': 1.00, 'aspect_ratio': 0.65, 'impervious_frac': 0.55, 'building_frac': 0.34, 'albedo': 0.10, 'z_h': 0.09, 'svf': 0.04, 'admittance': 0.00, 'anthro_heat': 0.00, 'terrain_rough': 0.00},
                '9':  {'aspect_ratio': 0.72, 'svf': 0.46, 'building_frac': 0.40, 'pervious_frac': 0.31, 'anthro_heat': 0.23, 'impervious_frac': 0.20, 'admittance': 0.13, 'z_h': 0.09, 'terrain_rough': 0.06, 'albedo': 0.00},
                '10': {'anthro_heat': 10.15, 'admittance': 1.07, 'aspect_ratio': 0.30, 'albedo': 0.26, 'svf': 0.19, 'terrain_rough': 0.06, 'pervious_frac': 0.05, 'building_frac': 0.02, 'z_h': 0.01, 'impervious_frac': 0.00},
                'A':  {'terrain_rough': 2.00, 'svf': 1.54, 'pervious_frac': 1.40, 'impervious_frac': 0.85, 'z_h': 0.80, 'building_frac': 0.76, 'albedo': 0.51, 'anthro_heat': 0.37, 'aspect_ratio': 0.34, 'admittance': 0.00},
                'B':  {'pervious_frac': 1.40, 'impervious_frac': 0.85, 'building_frac': 0.76, 'anthro_heat': 0.37, 'admittance': 0.13, 'albedo': 0.10, 'aspect_ratio': 0.08, 'terrain_rough': 0.06, 'svf': 0.00, 'z_h': 0.00},
                'C':  {'admittance': 2.43, 'pervious_frac': 1.40, 'impervious_frac': 0.85, 'building_frac': 0.76, 'albedo': 0.71, 'z_h': 0.70, 'svf': 0.46, 'anthro_heat': 0.37, 'terrain_rough': 0.06, 'aspect_ratio': 0.00},
                'D':  {'pervious_frac': 1.40, 'svf': 1.34, 'aspect_ratio': 0.96, 'z_h': 0.91, 'impervious_frac': 0.85, 'building_frac': 0.76, 'terrain_rough': 0.50, 'anthro_heat': 0.37, 'admittance': 0.13, 'albedo': 0.10},
                'E':  {'impervious_frac': 8.28, 'terrain_rough': 2.72, 'admittance': 2.06, 'pervious_frac': 1.73, 'svf': 1.34, 'z_h': 1.09, 'aspect_ratio': 0.96, 'building_frac': 0.76, 'albedo': 0.71, 'anthro_heat': 0.37},
                'F':  {'admittance': 3.84, 'albedo': 3.52, 'terrain_rough': 2.72, 'pervious_frac': 1.40, 'svf': 1.34, 'z_h': 1.09, 'aspect_ratio': 0.96, 'impervious_frac': 0.85, 'building_frac': 0.76, 'anthro_heat': 0.37},
                'G':  {'albedo': 6.63, 'terrain_rough': 3.56, 'pervious_frac': 1.40, 'svf': 1.34, 'z_h': 1.16, 'aspect_ratio': 0.96, 'impervious_frac': 0.85, 'building_frac': 0.76, 'anthro_heat': 0.37, 'admittance': 0.00}
            },
            'veto_ranking': {
                '1':  ['aspect_ratio', 'height_roughness', 'sky_view_factor', 'anthropogenic_heat', 'terrain_roughness', 'pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'surface_albedo', 'surface_admittance'],
                '2':  ['surface_admittance', 'building_surface_fraction', 'aspect_ratio', 'height_roughness', 'pervious_surface_fraction', 'sky_view_factor', 'surface_albedo', 'terrain_roughness', 'impervious_surface_fraction', 'anthropogenic_heat'],
                '3':  ['building_surface_fraction', 'sky_view_factor', 'aspect_ratio', 'surface_albedo', 'pervious_surface_fraction', 'terrain_roughness', 'anthropogenic_heat', 'height_roughness', 'impervious_surface_fraction', 'surface_admittance'],
                '4':  ['height_roughness', 'terrain_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'surface_admittance', 'sky_view_factor', 'impervious_surface_fraction', 'building_surface_fraction', 'anthropogenic_heat', 'surface_albedo'],
                '5':  ['height_roughness', 'surface_admittance', 'pervious_surface_fraction', 'impervious_surface_fraction', 'anthropogenic_heat', 'aspect_ratio', 'terrain_roughness', 'building_surface_fraction', 'sky_view_factor', 'surface_albedo'],
                '6':  ['sky_view_factor', 'height_roughness', 'anthropogenic_heat', 'impervious_surface_fraction', 'aspect_ratio', 'terrain_roughness', 'pervious_surface_fraction', 'building_surface_fraction', 'surface_admittance', 'surface_albedo'],
                '7':  ['building_surface_fraction', 'sky_view_factor', 'aspect_ratio', 'surface_admittance', 'surface_albedo', 'height_roughness', 'pervious_surface_fraction', 'impervious_surface_fraction', 'terrain_roughness', 'anthropogenic_heat'],
                '8':  ['pervious_surface_fraction', 'aspect_ratio', 'impervious_surface_fraction', 'building_surface_fraction', 'surface_albedo', 'height_roughness', 'sky_view_factor', 'surface_admittance', 'anthropogenic_heat', 'terrain_roughness'],
                '9':  ['aspect_ratio', 'sky_view_factor', 'building_surface_fraction', 'pervious_surface_fraction', 'anthropogenic_heat', 'impervious_surface_fraction', 'surface_admittance', 'height_roughness', 'terrain_roughness', 'surface_albedo'],
                '10': ['anthropogenic_heat', 'surface_admittance', 'aspect_ratio', 'surface_albedo', 'sky_view_factor', 'terrain_roughness', 'pervious_surface_fraction', 'building_surface_fraction', 'height_roughness', 'impervious_surface_fraction'],
                'A':  ['terrain_roughness', 'sky_view_factor', 'pervious_surface_fraction', 'impervious_surface_fraction', 'height_roughness', 'building_surface_fraction', 'surface_albedo', 'anthropogenic_heat', 'aspect_ratio', 'surface_admittance'],
                'B':  ['pervious_surface_fraction', 'impervious_surface_fraction', 'building_surface_fraction', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo', 'aspect_ratio', 'terrain_roughness', 'sky_view_factor', 'height_roughness'],
                'C':  ['surface_admittance', 'pervious_surface_fraction', 'impervious_surface_fraction', 'building_surface_fraction', 'surface_albedo', 'height_roughness', 'sky_view_factor', 'anthropogenic_heat', 'terrain_roughness', 'aspect_ratio'],
                'D':  ['pervious_surface_fraction', 'sky_view_factor', 'aspect_ratio', 'height_roughness', 'impervious_surface_fraction', 'building_surface_fraction', 'terrain_roughness', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                'E':  ['impervious_surface_fraction', 'terrain_roughness', 'surface_admittance', 'pervious_surface_fraction', 'sky_view_factor', 'height_roughness', 'aspect_ratio', 'building_surface_fraction', 'surface_albedo', 'anthropogenic_heat'],
                'F':  ['surface_admittance', 'surface_albedo', 'terrain_roughness', 'pervious_surface_fraction', 'sky_view_factor', 'height_roughness', 'aspect_ratio', 'impervious_surface_fraction', 'building_surface_fraction', 'anthropogenic_heat'],
                'G':  ['surface_albedo', 'terrain_roughness', 'pervious_surface_fraction', 'sky_view_factor', 'height_roughness', 'aspect_ratio', 'impervious_surface_fraction', 'building_surface_fraction', 'anthropogenic_heat', 'surface_admittance']
            }
        },
        'unic-score': {
            'weights': {
                '1':  {'terrain_rough': 196, 'aspect_ratio': 169, 'svf': 144, 'z_h': 144, 'pervious_frac': 121, 'anthro_heat': 121, 'building_frac': 81, 'impervious_frac': 81, 'admittance': 4, 'albedo': 0},
                '2':  {'pervious_frac': 100, 'building_frac': 81, 'impervious_frac': 81, 'terrain_rough': 81, 'svf': 49, 'aspect_ratio': 49, 'z_h': 36, 'admittance': 4, 'anthro_heat': 1, 'albedo': 0},
                '3':  {'terrain_rough': 100, 'building_frac': 81, 'aspect_ratio': 64, 'pervious_frac': 64, 'svf': 49, 'impervious_frac': 49, 'z_h': 49, 'admittance': 1, 'anthro_heat': 1, 'albedo': 0},
                '4':  {'terrain_rough': 169, 'z_h': 144, 'pervious_frac': 121, 'impervious_frac': 81, 'aspect_ratio': 64, 'building_frac': 64, 'svf': 49, 'admittance': 1, 'albedo': 1, 'anthro_heat': 1},
                '5':  {'impervious_frac': 81, 'pervious_frac': 81, 'aspect_ratio': 64, 'building_frac': 64, 'terrain_rough': 49, 'svf': 36, 'z_h': 36, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                '6':  {'pervious_frac': 100, 'aspect_ratio': 64, 'building_frac': 64, 'impervious_frac': 49, 'z_h': 49, 'terrain_rough': 49, 'svf': 9, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                '7':  {'building_frac': 169, 'aspect_ratio': 100, 'svf': 81, 'z_h': 81, 'pervious_frac': 64, 'terrain_rough': 64, 'impervious_frac': 36, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                '8':  {'pervious_frac': 100, 'building_frac': 81, 'impervious_frac': 81, 'terrain_rough': 81, 'z_h': 49, 'aspect_ratio': 36, 'svf': 25, 'admittance': 1, 'albedo': 1, 'anthro_heat': 1},
                '9':  {'pervious_frac': 225, 'aspect_ratio': 64, 'z_h': 49, 'terrain_rough': 49, 'svf': 36, 'impervious_frac': 36, 'building_frac': 25, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                '10': {'anthro_heat': 225, 'pervious_frac': 169, 'building_frac': 121, 'aspect_ratio': 100, 'z_h': 64, 'impervious_frac': 49, 'terrain_rough': 49, 'svf': 9, 'admittance': 1, 'albedo': 1},
                'A':  {'admittance': 256, 'terrain_rough': 196, 'svf': 144, 'pervious_frac': 121, 'aspect_ratio': 100, 'building_frac': 81, 'impervious_frac': 81, 'z_h': 25, 'anthro_heat': 4, 'albedo': 0},
                'B':  {'pervious_frac': 121, 'building_frac': 81, 'impervious_frac': 81, 'aspect_ratio': 49, 'z_h': 49, 'terrain_rough': 49, 'svf': 36, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                'C':  {'pervious_frac': 121, 'z_h': 121, 'building_frac': 81, 'impervious_frac': 81, 'terrain_rough': 64, 'svf': 25, 'aspect_ratio': 25, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                'D':  {'terrain_rough': 196, 'z_h': 144, 'aspect_ratio': 121, 'pervious_frac': 121, 'building_frac': 81, 'impervious_frac': 81, 'svf': 64, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                'E':  {'impervious_frac': 256, 'terrain_rough': 196, 'z_h': 144, 'aspect_ratio': 121, 'pervious_frac': 121, 'building_frac': 81, 'svf': 64, 'anthro_heat': 4, 'admittance': 1, 'albedo': 1},
                'F':  {'terrain_rough': 196, 'z_h': 144, 'aspect_ratio': 121, 'pervious_frac': 121, 'building_frac': 81, 'impervious_frac': 81, 'svf': 64, 'admittance': 16, 'anthro_heat': 4, 'albedo': 1},
                'G':  {'terrain_rough': 196, 'z_h': 144, 'albedo': 144, 'aspect_ratio': 121, 'pervious_frac': 121, 'building_frac': 81, 'impervious_frac': 81, 'svf': 64, 'admittance': 4, 'anthro_heat': 4}
            },
            'veto_ranking': {
                '1':  ['terrain_roughness', 'aspect_ratio', 'sky_view_factor', 'height_roughness', 'pervious_surface_fraction', 'anthropogenic_heat', 'building_surface_fraction', 'impervious_surface_fraction', 'surface_admittance', 'surface_albedo'],
                '2':  ['pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'terrain_roughness', 'sky_view_factor', 'aspect_ratio', 'height_roughness', 'surface_admittance', 'anthropogenic_heat', 'surface_albedo'],
                '3':  ['terrain_roughness', 'building_surface_fraction', 'aspect_ratio', 'pervious_surface_fraction', 'sky_view_factor', 'impervious_surface_fraction', 'height_roughness', 'surface_admittance', 'anthropogenic_heat', 'surface_albedo'],
                '4':  ['terrain_roughness', 'height_roughness', 'pervious_surface_fraction', 'impervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'sky_view_factor', 'surface_admittance', 'surface_albedo', 'anthropogenic_heat'],
                '5':  ['impervious_surface_fraction', 'pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'terrain_roughness', 'sky_view_factor', 'height_roughness', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '6':  ['pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'impervious_surface_fraction', 'height_roughness', 'terrain_roughness', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '7':  ['building_surface_fraction', 'aspect_ratio', 'sky_view_factor', 'height_roughness', 'pervious_surface_fraction', 'terrain_roughness', 'impervious_surface_fraction', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '8':  ['pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'terrain_roughness', 'height_roughness', 'aspect_ratio', 'sky_view_factor', 'surface_admittance', 'surface_albedo', 'anthropogenic_heat'],
                '9':  ['pervious_surface_fraction', 'aspect_ratio', 'height_roughness', 'terrain_roughness', 'sky_view_factor', 'impervious_surface_fraction', 'building_surface_fraction', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '10': ['anthropogenic_heat', 'pervious_surface_fraction', 'building_surface_fraction', 'aspect_ratio', 'height_roughness', 'impervious_surface_fraction', 'terrain_roughness', 'sky_view_factor', 'surface_admittance', 'surface_albedo'],
                'A':  ['surface_admittance', 'terrain_roughness', 'sky_view_factor', 'pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'impervious_surface_fraction', 'height_roughness', 'anthropogenic_heat', 'surface_albedo'],
                'B':  ['pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'aspect_ratio', 'height_roughness', 'terrain_roughness', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                'C':  ['pervious_surface_fraction', 'height_roughness', 'building_surface_fraction', 'impervious_surface_fraction', 'terrain_roughness', 'sky_view_factor', 'aspect_ratio', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                'D':  ['terrain_roughness', 'height_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                'E':  ['impervious_surface_fraction', 'terrain_roughness', 'height_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'building_surface_fraction', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                'F':  ['terrain_roughness', 'height_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'sky_view_factor', 'surface_admittance', 'anthropogenic_heat', 'surface_albedo'],
                'G':  ['terrain_roughness', 'height_roughness', 'surface_albedo', 'aspect_ratio', 'pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'sky_view_factor', 'surface_admittance', 'anthropogenic_heat']
            }
        },
        'fuzzy-unic-score': {
            'weights': {
                '1':  {'terrain_rough': 272.25, 'aspect_ratio': 196, 'z_h': 169, 'anthro_heat': 156.25, 'svf': 144, 'building_frac': 121, 'pervious_frac': 121, 'impervious_frac': 100, 'admittance': 12.25, 'albedo': 1},
                '2':  {'terrain_rough': 156.25, 'building_frac': 110.25, 'pervious_frac': 110.25, 'aspect_ratio': 81, 'impervious_frac': 81, 'z_h': 81, 'svf': 64, 'anthro_heat': 20.25, 'admittance': 12.25, 'albedo': 1},
                '3':  {'terrain_rough': 196, 'building_frac': 110.25, 'aspect_ratio': 90.25, 'pervious_frac': 81, 'svf': 64, 'impervious_frac': 64, 'z_h': 64, 'anthro_heat': 20.25, 'admittance': 1, 'albedo': 1},
                '4':  {'terrain_rough': 210.25, 'z_h': 169, 'pervious_frac': 156.25, 'building_frac': 100, 'impervious_frac': 100, 'aspect_ratio': 90.25, 'svf': 72.25, 'anthro_heat': 25, 'admittance': 2.25, 'albedo': 1},
                '5':  {'pervious_frac': 110.25, 'aspect_ratio': 100, 'building_frac': 100, 'terrain_rough': 90.25, 'impervious_frac': 81, 'z_h': 81, 'svf': 49, 'anthro_heat': 30.25, 'admittance': 2.25, 'albedo': 1},
                '6':  {'pervious_frac': 132.25, 'aspect_ratio': 100, 'building_frac': 100, 'terrain_rough': 90.25, 'impervious_frac': 64, 'z_h': 64, 'svf': 36, 'anthro_heat': 30.25, 'admittance': 1, 'albedo': 1},
                '7':  {'building_frac': 182.25, 'terrain_rough': 132.25, 'aspect_ratio': 121, 'svf': 110.25, 'z_h': 90.25, 'pervious_frac': 81, 'impervious_frac': 56.25, 'anthro_heat': 30.25, 'admittance': 6.25, 'albedo': 1},
                '8':  {'terrain_rough': 182.25, 'pervious_frac': 110.25, 'impervious_frac': 100, 'building_frac': 90.25, 'aspect_ratio': 81, 'z_h': 64, 'svf': 30.25, 'anthro_heat': 25, 'admittance': 1, 'albedo': 1},
                '9':  {'pervious_frac': 240.25, 'aspect_ratio': 121, 'building_frac': 110.25, 'terrain_rough': 90.25, 'z_h': 64, 'impervious_frac': 56.25, 'svf': 49, 'anthro_heat': 30.25, 'admittance': 1, 'albedo': 1},
                '10': {'anthro_heat': 240.25, 'pervious_frac': 196, 'building_frac': 144, 'aspect_ratio': 100, 'terrain_rough': 90.25, 'impervious_frac': 81, 'z_h': 64, 'svf': 36, 'albedo': 2.25, 'admittance': 1},
                'A':  {'admittance': 289, 'terrain_rough': 272.25, 'anthro_heat': 169, 'svf': 144, 'pervious_frac': 121, 'aspect_ratio': 110.25, 'building_frac': 90.25, 'impervious_frac': 81, 'z_h': 25, 'albedo': 1},
                'B':  {'anthro_heat': 169, 'pervious_frac': 121, 'building_frac': 90.25, 'terrain_rough': 90.25, 'aspect_ratio': 81, 'impervious_frac': 81, 'svf': 49, 'z_h': 49, 'admittance': 1, 'albedo': 1},
                'C':  {'anthro_heat': 169, 'z_h': 144, 'terrain_rough': 132.25, 'pervious_frac': 121, 'building_frac': 90.25, 'impervious_frac': 81, 'svf': 56.25, 'aspect_ratio': 42.25, 'admittance': 6.25, 'albedo': 1},
                'D':  {'terrain_rough': 225, 'anthro_heat': 169, 'z_h': 156.25, 'aspect_ratio': 144, 'pervious_frac': 121, 'svf': 90.25, 'building_frac': 90.25, 'impervious_frac': 81, 'admittance': 1, 'albedo': 1},
                'E':  {'impervious_frac': 256, 'terrain_rough': 210.25, 'anthro_heat': 169, 'z_h': 156.25, 'aspect_ratio': 144, 'pervious_frac': 121, 'svf': 90.25, 'building_frac': 90.25, 'admittance': 1, 'albedo': 1},
                'F':  {'terrain_rough': 210.25, 'anthro_heat': 169, 'z_h': 156.25, 'aspect_ratio': 144, 'pervious_frac': 121, 'svf': 90.25, 'building_frac': 90.25, 'impervious_frac': 81, 'admittance': 25, 'albedo': 12.25},
                'G':  {'terrain_rough': 256, 'z_h': 225, 'albedo': 196, 'anthro_heat': 169, 'aspect_ratio': 144, 'pervious_frac': 121, 'svf': 90.25, 'building_frac': 90.25, 'impervious_frac': 81, 'admittance': 25}
            },
            'veto_ranking': {
                '1':  ['terrain_roughness', 'aspect_ratio', 'height_roughness', 'anthropogenic_heat', 'sky_view_factor', 'building_surface_fraction', 'pervious_surface_fraction', 'impervious_surface_fraction', 'surface_admittance', 'surface_albedo'],
                '2':  ['terrain_roughness', 'building_surface_fraction', 'pervious_surface_fraction', 'aspect_ratio', 'impervious_surface_fraction', 'height_roughness', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '3':  ['terrain_roughness', 'building_surface_fraction', 'aspect_ratio', 'pervious_surface_fraction', 'sky_view_factor', 'impervious_surface_fraction', 'height_roughness', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '4':  ['terrain_roughness', 'height_roughness', 'pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'aspect_ratio', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '5':  ['pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'terrain_roughness', 'impervious_surface_fraction', 'height_roughness', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '6':  ['pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'terrain_roughness', 'impervious_surface_fraction', 'height_roughness', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '7':  ['building_surface_fraction', 'terrain_roughness', 'aspect_ratio', 'sky_view_factor', 'height_roughness', 'pervious_surface_fraction', 'impervious_surface_fraction', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '8':  ['terrain_roughness', 'pervious_surface_fraction', 'impervious_surface_fraction', 'building_surface_fraction', 'aspect_ratio', 'height_roughness', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '9':  ['pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'terrain_roughness', 'height_roughness', 'impervious_surface_fraction', 'sky_view_factor', 'anthropogenic_heat', 'surface_admittance', 'surface_albedo'],
                '10': ['anthropogenic_heat', 'pervious_surface_fraction', 'building_surface_fraction', 'aspect_ratio', 'terrain_roughness', 'impervious_surface_fraction', 'height_roughness', 'sky_view_factor', 'surface_albedo', 'surface_admittance'],
                'A':  ['surface_admittance', 'terrain_roughness', 'anthropogenic_heat', 'sky_view_factor', 'pervious_surface_fraction', 'aspect_ratio', 'building_surface_fraction', 'impervious_surface_fraction', 'height_roughness', 'surface_albedo'],
                'B':  ['anthropogenic_heat', 'pervious_surface_fraction', 'building_surface_fraction', 'terrain_roughness', 'aspect_ratio', 'impervious_surface_fraction', 'sky_view_factor', 'height_roughness', 'surface_admittance', 'surface_albedo'],
                'C':  ['anthropogenic_heat', 'height_roughness', 'terrain_roughness', 'pervious_surface_fraction', 'building_surface_fraction', 'impervious_surface_fraction', 'sky_view_factor', 'aspect_ratio', 'surface_admittance', 'surface_albedo'],
                'D':  ['terrain_roughness', 'anthropogenic_heat', 'height_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'sky_view_factor', 'building_surface_fraction', 'impervious_surface_fraction', 'surface_admittance', 'surface_albedo'],
                'E':  ['impervious_surface_fraction', 'terrain_roughness', 'anthropogenic_heat', 'height_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'sky_view_factor', 'building_surface_fraction', 'surface_admittance', 'surface_albedo'],
                'F':  ['terrain_roughness', 'anthropogenic_heat', 'height_roughness', 'aspect_ratio', 'pervious_surface_fraction', 'sky_view_factor', 'building_surface_fraction', 'impervious_surface_fraction', 'surface_admittance', 'surface_albedo'],
                'G':  ['terrain_roughness', 'height_roughness', 'surface_albedo', 'anthropogenic_heat', 'aspect_ratio', 'pervious_surface_fraction', 'sky_view_factor', 'building_surface_fraction', 'impervious_surface_fraction', 'surface_admittance']
            }
        },
    }


    def __init__(self, parameters, calibration_overrides=None, profile_name='z-score'):
        """
        Args:
            parameters: dict with parameter names (internal) and values
            calibration_overrides: dict {lcz_id: {param_name: offset}}
            profile_name: one of 'z-score', 'unic-score', 'fuzzy-unic-score'
        """
        self.parameters = {k: v for k, v in parameters.items() if v is not None}
        self.available_params_count = len(self.parameters)
        self.calibration_overrides = calibration_overrides or {}
        
        # Load profile configuration
        profile = self.PROFILES.get(profile_name, self.PROFILES['z-score'])
        self.z_weights = profile.get('weights', {})
        self.veto_ranking = profile.get('veto_ranking', {})
        self.profile_name = profile_name


    def calculate_weighted_score(self, lcz_id, veto_count=1):
        """
        Calculates a Weighted Z-Distance Score.
        Returns: (score, veto_triggered)
        """
        params_definition = self.LCZ_PARAMETERS[lcz_id]
        class_weights_p = self.z_weights.get(lcz_id, {})
        
        # Determine the set of parameters that can trigger a Veto
        # veto_count can be an integer (global) or a dictionary (per-class)
        current_veto_count = veto_count.get(lcz_id, 1) if isinstance(veto_count, dict) else veto_count
        
        veto_params_ranked = self.veto_ranking.get(lcz_id, [])
        veto_active_set = set(veto_params_ranked[:current_veto_count])

        
        weighted_error_sum = 0
        total_weight = 0
        veto_triggered = False

        for param_name_internal, current_val in self.parameters.items():
            if param_name_internal not in params_definition:
                continue
                
            min_val, max_val = params_definition[param_name_internal]
            
            # 1. Target Value (Center of range) shifted by local calibration
            offset = self.calibration_overrides.get(lcz_id, {}).get(param_name_internal, 0.0)
            
            if max_val == float('inf'):
                target_val = (min_val * 1.5) + offset # Heuristic for open ranges
            else:
                target_val = ((min_val + max_val) / 2) + offset
            
            if target_val <= 0: target_val = 0.001
            
            # 2. Normalized Error (Bounds are also shifted)
            eff_min = min_val + offset
            eff_max = max_val + offset
            
            if eff_min <= current_val <= eff_max:
                error = 0
            else:
                error = abs(current_val - target_val) / target_val

            # 3. VETO TRIGGER
            if param_name_internal in veto_active_set:
                # If statistical leader error > 50%, veto the class
                if error > 0.5:
                    veto_triggered = True

            # 4. Weight (Z^2 or custom)
            # Find the Z-name for this internal name
            z_name = next((k for k, v in self.PARAM_MAP.items() if v == param_name_internal), None)
            weight = class_weights_p.get(z_name, 1.0)

            
            weighted_error_sum += weight * (error ** 2)
            total_weight += weight

        if total_weight == 0:
            return float('inf'), False

        score = np.sqrt(weighted_error_sum / total_weight)
        return score, veto_triggered

    def classify(self, veto_count=1):
        """
        Main classification logic.
        """
        if self.available_params_count < 3:
            return {'lcz_class': 'N/D', 'score': 0, 'confidence': 0}

        results = {}
        vetos = {}

        for lcz_id in self.LCZ_CLASSES.keys():
            score, vetoed = self.calculate_weighted_score(lcz_id, veto_count=veto_count)
            results[lcz_id] = score
            vetos[lcz_id] = vetoed

        # Filter out vetoed classes if possible, but keep at least something?
        # No, if vetoed, it's out.
        valid_results = {k: v for k, v in results.items() if not vetos[k] and v != float('inf')}
        
        if not valid_results:
            # If all classes are vetoed, fallback to the one with best score even if vetoed
            # or just return N/D? Let's be strict for v6.0.
            return {'lcz_class': 'N/D', 'score': 0, 'confidence': 0, 'method': 'WZDV_Veto_All'}

        sorted_results = sorted(valid_results.items(), key=lambda x: x[1])
        best_id, best_score = sorted_results[0]
        
        # Confidence logic: inverse of distance
        # best_score = 0 means perfect weighted match. 
        # Let's map score to [0, 1] confidence
        confidence = 1.0 / (1.0 + best_score)
        
        # Tie-breaker logic (Perfect matches count)
        second_id, second_score = None, None
        if len(sorted_results) > 1:
            second_id, second_score = sorted_results[1]
            if abs(best_score - second_score) < 0.05:
                # Check actual range matches for tie-breaking
                m1 = self._count_perfect_matches(best_id)
                m2 = self._count_perfect_matches(second_id)
                if m2 > m1:
                    # Swap winner and runner-up
                    best_id, second_id = second_id, best_id
                    best_score, second_score = second_score, best_score

        # Final Rejection
        if confidence < 0.3:
            return {
                'lcz_class': 'N/D', 
                'score': round(best_score, 3), 
                'confidence': round(confidence, 2),
                'second_class': second_id,
                'second_score': round(second_score, 3) if second_score is not None else None,
                'perfect_matches': self._count_perfect_matches('N/D')
            }

        return {
            'lcz_class': best_id, 
            'score': round(best_score, 3), 
            'confidence': round(confidence, 2),
            'second_class': second_id,
            'second_score': round(second_score, 3) if second_score is not None else None,
            'perfect_matches': self._count_perfect_matches(best_id),
            'method': 'WZDV'
        }

    def _count_perfect_matches(self, lcz_id):
        if lcz_id == 'N/D': return 0
        count = 0
        params_def = self.LCZ_PARAMETERS[lcz_id]
        overrides = self.calibration_overrides.get(lcz_id, {})
        
        for p_name_internal, val in self.parameters.items():
            if p_name_internal in params_def:
                low, high = params_def[p_name_internal]
                # Account for calibration offset in matching logic
                offset = overrides.get(p_name_internal, 0.0)
                if (low + offset) <= val <= (high + offset):
                    count += 1
        return count


from .base import LCZBaseProcessor

class LCZClassificationProcessorV6(LCZBaseProcessor):
    """
    Processor for WZDV (v6.0). 
    Includes ESA WorldCover-based correction (same as Standard).
    """
    
    ESA_TO_LCZ = LCZMappings.ESA_TO_LCZ
    
    def __init__(self, data_manager):
        self.dm = data_manager

    def log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "FETCH", level)

    def _get_landuse_raster_path(self):
        import os
        base_dir = self.dm.get_project_dir()
        if not base_dir: return None
        unified_dir = os.path.join(base_dir, self.dm.get_data_dir_name(), FolderNames.UNIFIED)
        landuse_path = os.path.join(unified_dir, FileNames.LANDUSE)
        return landuse_path if os.path.exists(landuse_path) else None

    def _compute_esa_majority(self, layer, raster_path, log_callback=None):
        import processing
        try:
            result = processing.run('native:zonalstatisticsfb', {
                'INPUT': layer,
                'INPUT_RASTER': raster_path,
                'RASTER_BAND': 1,
                'COLUMN_PREFIX': 'esa_',
                'STATISTICS': [9], # Majority
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            return result['OUTPUT']
        except Exception as e:
            self.log(f"ESA Stats Error: {e}", Qgis.Warning)
            return None

    def _apply_esa_correction(self, lcz_class, esa_class, impervious_frac=None, building_frac=None, z_h=None):
        """Applies logic to reconcile the morphological classifier with ESA WorldCover."""
        # 1. Protection for Water
        if esa_class == 80: return 'G'
        
        # 2. Rejection Fallback
        if esa_class is None or lcz_class == 'N/D': return lcz_class
        
        suggested_lcz = self.ESA_TO_LCZ.get(esa_class)
        
        # 3. BUILT -> NATURAL Correction (Critical for LCZ 9/6 misclassification)
        # If morphology chose a built class (1-10) but buildings are nearly absent, force a natural class.
        if lcz_class in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
            if building_frac is not None and building_frac <= 10:
                # If building density is <= 10%, morphology is likely picking up trees or terrain
                if suggested_lcz in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                    return suggested_lcz
                
                # Special Case: ESA says Built-up (50) but there are no buildings!
                # This often happens for roads, parking lots, or small paved spots.
                if esa_class == 50 or suggested_lcz is None:
                    if z_h is not None and z_h > 2.0:
                        return 'A' # Trees
                    if impervious_frac is not None and impervious_frac > 30:
                        return 'E' # Pavement
                    return 'D' # Low Plants/Soil
                    
            return lcz_class
            
        # 4. NATURAL -> NATURAL/URBAN Correction (Same as before)
        if lcz_class == 'G' and esa_class != 80:
            if esa_class == 50: return '9'
            return suggested_lcz if suggested_lcz else 'D'
            
        if suggested_lcz is None: return lcz_class
        
        if esa_class == 10: # Trees
            return lcz_class if lcz_class in ['A', 'B'] else 'A'
        if esa_class == 60: # Bare
            return 'E' if (impervious_frac is not None and impervious_frac > 50) else 'F'
            
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']: return suggested_lcz
        return lcz_class

    def process(self, layer, log_callback=None, apply_smoothing=False, veto_count=1, calibration_overrides=None, profile='z-score'):

        import os
        
        def log_local(msg, level=Qgis.Info):
            if log_callback:
                log_callback(msg, level)
            else:
                self.log(msg, level)

        log_local("🧪 Avvio classificazione WEIGHTED Z-DISTANCE WITH VETO (v6.0)...")
        log_local(f"⚖️ Profilo: {profile.upper()}. Veto attivi: {veto_count}")


        # Sanitization: Ensure existing data doesn't violate field constraints
        self._sanitize_layer(layer)
        
        # --- ESA Setup ---
        landuse_path = self._get_landuse_raster_path()
        use_esa_correction = False
        esa_majority_lookup = {}
        
        if landuse_path:
            log_local("⏳ Analisi ESA WorldCover per rettifica fisica (v6.0)...")
            esa_layer = self._compute_esa_majority(layer, landuse_path, log_local)
            if esa_layer:
                idx_esa_maj = esa_layer.fields().indexFromName('esa_majority')
                if idx_esa_maj != -1:
                    for feat in esa_layer.getFeatures():
                        val = feat.attribute(idx_esa_maj)
                        if val is not None and str(val) not in ('NULL', ''):
                            try: esa_majority_lookup[feat.id()] = int(float(val))
                            except: pass
                    use_esa_correction = len(esa_majority_lookup) > 0

        # --- Field Setup ---
        field_defs = [
            ('lcz_class', QMetaType.QString, 10),
            ('lcz_score', QMetaType.Double, 0),
            ('lcz_rmsep', QMetaType.Double, 0),
            ('lcz_confidence', QMetaType.Double, 0),
            ('lcz_class_2nd', QMetaType.QString, 10),
            ('lcz_score_2nd', QMetaType.Double, 0),
            ('lcz_matches', QMetaType.Int, 0),
            ('lcz_vulnerability', QMetaType.QString, 20),
            ('lcz_esa_fix', QMetaType.QString, 50)
        ]
        
        layer.startEditing()
        fields_added = False
        for f, t, l in field_defs:
            if layer.fields().indexFromName(f) == -1:
                layer.dataProvider().addAttributes([QgsField(f, t, len=l)])
                fields_added = True
        
        if fields_added:
            layer.updateFields()
        
        # Re-fetch field indices after update
        idx_class = layer.fields().lookupField('lcz_class')
        idx_score = layer.fields().lookupField('lcz_score')
        idx_rmsep = layer.fields().lookupField('lcz_rmsep')
        idx_conf = layer.fields().lookupField('lcz_confidence')
        idx_class2 = layer.fields().lookupField('lcz_class_2nd')
        idx_score2 = layer.fields().lookupField('lcz_score_2nd')
        idx_matches = layer.fields().lookupField('lcz_matches')
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')
        idx_esa_f = layer.fields().lookupField('lcz_esa_fix')
        
        # Try to find impervious fraction efficiently
        idx_imp = layer.fields().indexFromName('impervious_surface_fraction')
        if idx_imp == -1:
             idx_imp = layer.fields().indexFromName(FieldNames.IMPERVIOUS_FRAC)

        processed = 0
        corrected = 0
        total_count = layer.featureCount()
        
        for feat in layer.getFeatures():
            params = {}
            for f_src, p_name in LCZMappings.FIELD_TO_PARAM.items():
                v = feat.attribute(f_src)
                params[p_name] = float(v) if (v is not None and str(v) not in ('NULL', '')) else None
            
            if any(v is not None for v in params.values()):
                res = LCZClassifierWZDV(params, calibration_overrides=calibration_overrides, profile_name=profile).classify(veto_count=veto_count)

                lcz = res['lcz_class']
                esa_status = '-'
                
                # ESA Correction
                if use_esa_correction and lcz != 'N/D':
                    esa_class = esa_majority_lookup.get(feat.id())
                    imp_f = None
                    if idx_imp != -1:
                        iv = feat.attribute(idx_imp)
                        try: imp_f = float(iv) if iv is not None else None
                        except: pass
                    
                    b_f = params.get('building_surface_fraction', 0)
                    z_h_val = params.get('height_roughness', 0)
                    
                    original_lcz = lcz
                    lcz = self._apply_esa_correction(lcz, esa_class, imp_f, b_f, z_h_val)
                    if lcz != original_lcz:
                        corrected += 1
                        esa_status = f"{original_lcz} → {lcz}"

                layer.changeAttributeValue(feat.id(), idx_class, lcz)
                if idx_score != -1: layer.changeAttributeValue(feat.id(), idx_score, float(res.get('score', 0)))
                if idx_rmsep != -1: layer.changeAttributeValue(feat.id(), idx_rmsep, float(res.get('score', 0))) 
                if idx_conf != -1: layer.changeAttributeValue(feat.id(), idx_conf, float(res.get('confidence', 0)))
                if idx_class2 != -1: layer.changeAttributeValue(feat.id(), idx_class2, res.get('second_class', ''))
                if idx_score2 != -1: layer.changeAttributeValue(feat.id(), idx_score2, float(res.get('second_score', 0)) if res.get('second_score') else 0)
                if idx_matches != -1: layer.changeAttributeValue(feat.id(), idx_matches, res.get('perfect_matches', 0))
                if idx_vuln != -1: layer.changeAttributeValue(feat.id(), idx_vuln, LCZMappings.VULNERABILITY_MAPPING.get(lcz, 'Unknown'))
                if idx_esa_f != -1: layer.changeAttributeValue(feat.id(), idx_esa_f, esa_status)
                
                processed += 1
                
                if processed % 50000 == 0:
                    perc = (processed / total_count) * 100
                    log_local(f"⏳ Avanzamento V6.0: {processed:,} / {total_count:,} celle ({perc:.1f}%)")
        
        layer.commitChanges()
        log_local(f"✓ Classificazione v6.0 completata: {processed} celle ({corrected} rettifiche ESA).")

        # --- Spatial Smoothing (NEW in v6.0) ---
        if apply_smoothing:
            log_local("⏳ Applicazione smoothing spaziale (v6 - Regola 7/9)...")
            smoothed_count = self._apply_spatial_smoothing(layer, log_local)
            if smoothed_count > 0:
                log_local(f"  └ {smoothed_count} celle allineate al vicinato")
        else:
            log_local("ℹ Smoothing spaziale disabilitato dall'utente.")

        return processed

    def _apply_spatial_smoothing(self, layer, log_callback=None):
        """
        Applies spatial smoothing using a majority filter to reduce salt-and-pepper noise.
        Ported from v3.0 logic.
        """
        from collections import Counter
        from qgis.core import QgsSpatialIndex, QgsGeometry
        
        def log(msg):
            if log_callback: log_callback(msg)
        
        idx_class = layer.fields().lookupField('lcz_class')
        idx_conf = layer.fields().lookupField('lcz_confidence')
        idx_vuln = layer.fields().lookupField('lcz_vulnerability')
        
        if idx_class == -1:
            return 0
        
        # Build spatial index
        spatial_index = QgsSpatialIndex()
        feature_dict = {}
        
        for feat in layer.getFeatures():
            spatial_index.addFeature(feat)
            feature_dict[feat.id()] = {
                'lcz': feat.attribute(idx_class),
                'conf': feat.attribute(idx_conf) if idx_conf != -1 else 1.0,
                'geom': QgsGeometry(feat.geometry())
            }
        
        # Calculate neighborhood for each cell
        smoothed = 0
        updates = {} # Store updates to apply in batch
        
        # Confidence threshold for smoothing (Higher = More aggressive)
        CONFIDENCE_THRESHOLD = 0.5
        
        # Minimum neighbor agreement for smoothing (Lower = More aggressive)
        MIN_NEIGHBOR_AGREEMENT = 6
        
        for fid, data in feature_dict.items():
            cell_lcz = data['lcz']
            cell_conf = data['conf'] if data['conf'] is not None else 0.5
            cell_geom = data['geom']
            
            if cell_lcz in ['N/D', 'ERRORE', None]:
                continue
            if cell_conf >= CONFIDENCE_THRESHOLD:
                continue
            
            # Get bounding box expanded by cell size (approximate 3x3 kernel)
            bbox = cell_geom.boundingBox()
            expansion = max(bbox.width(), bbox.height()) * 1.5
            bbox.grow(expansion)
            
            # Query spatial index
            candidates = spatial_index.intersects(bbox)
            
            neighbor_classes = []
            for cand_id in candidates:
                if cand_id == fid:
                    neighbor_classes.append(cell_lcz)
                else:
                    cand_data = feature_dict.get(cand_id)
                    if cand_data:
                        cand_lcz = cand_data['lcz']
                        if cand_lcz not in ['N/D', 'ERRORE', None]:
                            neighbor_classes.append(cand_lcz)
            
            if not neighbor_classes:
                continue
                
            # Find majority
            counter = Counter(neighbor_classes)
            majority_class, majority_count = counter.most_common(1)[0]
            
            if cell_lcz != majority_class and majority_count >= MIN_NEIGHBOR_AGREEMENT:
                updates[fid] = majority_class
                smoothed += 1
                
        if updates:
            layer.startEditing()
            for fid, new_lcz in updates.items():
                layer.changeAttributeValue(fid, idx_class, new_lcz)
                if idx_vuln != -1:
                    layer.changeAttributeValue(fid, idx_vuln, LCZMappings.VULNERABILITY_MAPPING.get(new_lcz, 'Unknown'))
            layer.commitChanges()
            
        return smoothed
