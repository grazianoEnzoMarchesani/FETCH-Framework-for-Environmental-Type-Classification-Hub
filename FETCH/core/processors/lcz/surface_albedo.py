# -*- coding: utf-8 -*-

import os
from .base import LCZBaseProcessor

class SurfaceAlbedoProcessor(LCZBaseProcessor):
    def process(self, layer, target_path, log_callback=None):
        base_dir = self.dm.get_project_dir()
        albedo_path = os.path.join(base_dir, self.dm.get_data_dir_name(), "unified", "albedo_10m.tif")
        return self._calc_zonal_mean(layer, target_path, albedo_path, 'albedo', 'alb', log_callback)
