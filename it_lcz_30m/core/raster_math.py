# -*- coding: utf-8 -*-

"""
Raster Math Utilities for LCZ Classification.
Provides high-performance pixel-level algebra using NumPy.
"""

import numpy as np
from typing import Tuple

class RasterMath:
    """
    Static utility class for raster operations.
    """

    @staticmethod
    def calculate_ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
        """
        Calculates the Normalized Difference Built-up Index (NDBI).
        Formula: (SWIR - NIR) / (SWIR + NIR)
        """
        denominator = swir + nir
        # Avoid division by zero
        denominator[denominator == 0] = 0.0001
        return (swir - nir) / denominator

    @staticmethod
    def calculate_building_density(height_array: np.ndarray, threshold: float = 3.0) -> float:
        """
        Calculates the percentage of pixels above a certain height threshold.
        """
        total_pixels = height_array.size
        built_pixels = np.count_nonzero(height_array > threshold)
        return (built_pixels / total_pixels) * 100.0

    @staticmethod
    def resample_array(array: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
        """
        Simple resampling placeholder. 
        In production, we should use GDAL or scipy.ndimage for high-quality resampling.
        """
        # This is a very crude nearest neighbor placeholder
        return array # TODO: Implement proper resampling
