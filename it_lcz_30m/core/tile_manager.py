# -*- coding: utf-8 -*-

"""
Tile Manager for National-Scale LCZ Mapping.
Handles the splitting of a large extent into manageable processing tiles (quadrants).
"""

from typing import List, Tuple
from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransformContext

class TileManager:
    """
    Manages spatial partitioning for national-scale processing to prevent OOM errors.
    Target resolution: 30m.
    Target CRS: EPSG:32632 (WGS 84 / UTM zone 32N) for Italy.
    """

    def __init__(self, extent: QgsRectangle, tile_size_meters: float = 10000.0, resolution: float = 30.0):
        """
        Initialize the TileManager.
        
        Args:
            extent: The total extent to process.
            tile_size_meters: The size of one side of a square tile in meters.
            resolution: The pixel resolution in meters.
        """
        self.total_extent = extent
        self.tile_size = tile_size_meters
        self.resolution = resolution
        self.tiles = self._generate_tiles()

    def _generate_tiles(self) -> List[QgsRectangle]:
        """
        Generates a grid of QgsRectangle tiles based on the total extent and tile size.
        """
        tiles = []
        xmin = self.total_extent.xMinimum()
        xmax = self.total_extent.xMaximum()
        ymin = self.total_extent.yMinimum()
        ymax = self.total_extent.yMaximum()

        curr_x = xmin
        while curr_x < xmax:
            curr_y = ymin
            while curr_y < ymax:
                tile_rect = QgsRectangle(
                    curr_x, 
                    curr_y, 
                    min(curr_x + self.tile_size, xmax), 
                    min(curr_y + self.tile_size, ymax)
                )
                tiles.append(tile_rect)
                curr_y += self.tile_size
            curr_x += self.tile_size
            
        return tiles

    def get_tile_count(self) -> int:
        """Returns the total number of tiles to process."""
        return len(self.tiles)

    def get_tile(self, index: int) -> QgsRectangle:
        """Returns the tile at the specified index."""
        if 0 <= index < len(self.tiles):
            return self.tiles[index]
        raise IndexError("Tile index out of range.")
