# -*- coding: utf-8 -*-

import os
import glob
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge

# Configure logging
logger = logging.getLogger(__name__)

class Sentinel2Processor:
    """
    Processor for Sentinel-2 imagery.
    Handles albedo calculation using the Liang (2001) formula.
    """
    
    # Albedo Coefficients - Liang (2001) formula for Sentinel-2
    # Albedo = 0.356*B2 + 0.130*B4 + 0.373*B8 + 0.085*B11 + 0.072*B12 - 0.0018
    ALBEDO_COEFFICIENTS = {
        "B02": 0.356,
        "B04": 0.130,
        "B08": 0.373,
        "B11": 0.085,
        "B12": 0.072,
        "offset": -0.0018
    }
    
    # SCL (Scene Classification Layer) classes to mask
    # 0: No Data, 3: Cloud Shadow, 8: Cloud Medium Prob, 9: Cloud High Prob, 10: Thin Cirrus
    SCL_MASK_VALUES = [0, 3, 8, 9, 10]
    
    DN_TO_REFLECTANCE_FACTOR = 10000.0

    def __init__(self, data_manager):
        self.dm = data_manager

    def process_albedo(self, safe_dir: Path, bbox: Tuple[float, float, float, float], output_path: Path) -> bool:
        """
        Processes a .SAFE directory to calculate albedo.
        """
        try:
            # 1. Locate band files
            band_files = self._find_band_files(safe_dir)
            
            # Use rasterio Env to avoid AWS credentials issues when streaming public COGs
            with rasterio.Env(AWS_NO_SIGN_REQUEST='YES'):
                # 2. Read cropped 10m bands (B02, B04, B08)
                b02_data, profile = self._read_band_10m_crop(band_files["B02"], bbox)
                b04_data, _ = self._read_band_10m_crop(band_files["B04"], bbox)
                b08_data, _ = self._read_band_10m_crop(band_files["B08"], bbox)
                
                # 3. Read and resample 20m bands (B11, B12, SCL)
                b11_data = self._read_and_align_20m_band_crop(band_files["B11"], profile, Resampling.bilinear)
                b12_data = self._read_and_align_20m_band_crop(band_files["B12"], profile, Resampling.bilinear)
                scl_data = self._read_and_align_20m_band_crop(band_files["SCL"], profile, Resampling.nearest)
            
            # 4. Convert DN to Reflectance
            bands = {
                "B02": b02_data / self.DN_TO_REFLECTANCE_FACTOR,
                "B04": b04_data / self.DN_TO_REFLECTANCE_FACTOR,
                "B08": b08_data / self.DN_TO_REFLECTANCE_FACTOR,
                "B11": b11_data / self.DN_TO_REFLECTANCE_FACTOR,
                "B12": b12_data / self.DN_TO_REFLECTANCE_FACTOR
            }
            
            # 5. Calculate Albedo
            albedo = (
                self.ALBEDO_COEFFICIENTS["B02"] * bands["B02"] +
                self.ALBEDO_COEFFICIENTS["B04"] * bands["B04"] +
                self.ALBEDO_COEFFICIENTS["B08"] * bands["B08"] +
                self.ALBEDO_COEFFICIENTS["B11"] * bands["B11"] +
                self.ALBEDO_COEFFICIENTS["B12"] * bands["B12"] +
                self.ALBEDO_COEFFICIENTS["offset"]
            )
            albedo = np.clip(albedo, 0.0, 1.0)
            
            # 6. Apply Cloud Mask
            valid_mask = np.ones(scl_data.shape, dtype=bool)
            for value in self.SCL_MASK_VALUES:
                valid_mask[scl_data == value] = False
            
            albedo[~valid_mask] = np.nan
            
            # 7. Save output
            profile.update(
                dtype=rasterio.float32,
                count=1,
                nodata=np.nan,
                compress='deflate',
                driver='GTiff'
            )
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(albedo.astype(np.float32), 1)
            
            return True
        except Exception as e:
            logger.error(f"Errore nel processamento dell'albedo: {e}")
            return False

    def mosaic_tiles(self, input_paths: List[Path], output_path: Path) -> bool:
        """Mosaics multiple albedo tiles."""
        if not input_paths: return False
        if len(input_paths) == 1:
            import shutil
            shutil.copy(input_paths[0], output_path)
            return True
            
        try:
            src_files = [rasterio.open(fp) for fp in input_paths]
            mosaic, out_trans = merge(src_files)
            
            out_meta = src_files[0].meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_trans,
                "compress": 'deflate'
            })
            
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(mosaic)
                
            for src in src_files: src.close()
            return True
        except Exception as e:
            logger.error(f"Errore durante il mosaicking: {e}")
            return False

    def _find_band_files(self, safe_dir: Path) -> Dict[str, Path]:
        # Support AWS STAC Fallback virtual manifest
        manifest_path = safe_dir / "aws_stac_manifest.json"
        if manifest_path.exists():
            import json
            with open(manifest_path, 'r') as f:
                return json.load(f)
                
        required_bands = {
            "B02": ("R10m", "*_B02_10m.jp2"),
            "B04": ("R10m", "*_B04_10m.jp2"),
            "B08": ("R10m", "*_B08_10m.jp2"),
            "B11": ("R20m", "*_B11_20m.jp2"),
            "B12": ("R20m", "*_B12_20m.jp2"),
            "SCL": ("R20m", "*_SCL_20m.jp2")
        }
        band_files = {}
        img_data_dirs = glob.glob(str(safe_dir / "GRANULE" / "*" / "IMG_DATA"))
        if not img_data_dirs:
            raise FileNotFoundError(f"IMG_DATA non trovata in {safe_dir}")
        
        img_data_dir = Path(img_data_dirs[0])
        for band_name, (res_folder, pattern) in required_bands.items():
            matches = glob.glob(str(img_data_dir / res_folder / pattern))
            if not matches:
                raise FileNotFoundError(f"Band {band_name} non trovata.")
            band_files[band_name] = Path(matches[0])
        return band_files

    def _read_band_10m_crop(self, band_path, bbox_wgs84: Tuple[float, float, float, float]):
        import rasterio.warp
        from rasterio.windows import from_bounds, Window
        from rasterio.windows import transform as window_transform
        
        with rasterio.open(band_path) as src:
            bounds = rasterio.warp.transform_bounds('EPSG:4326', src.crs, *bbox_wgs84)
            buffer = 100
            bounds = (bounds[0]-buffer, bounds[1]-buffer, bounds[2]+buffer, bounds[3]+buffer)
            
            window = from_bounds(*bounds, transform=src.transform).round_lengths().round_offsets()
            read_window = window.intersection(Window(0, 0, src.width, src.height))
            
            data = src.read(1, window=read_window).astype(np.float32)
            profile = src.profile.copy()
            profile.update({
                'height': read_window.height,
                'width': read_window.width,
                'transform': window_transform(read_window, src.transform)
            })
            return data, profile

    def _read_and_align_20m_band_crop(self, band_path, target_profile: dict, resampling_method: Resampling):
        import rasterio.warp
        with rasterio.open(band_path) as src:
            out_data = np.zeros((1, target_profile['height'], target_profile['width']), dtype=np.float32)
            rasterio.warp.reproject(
                source=rasterio.band(src, 1),
                destination=out_data,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=target_profile['transform'],
                dst_crs=target_profile['crs'],
                resampling=resampling_method
            )
            return out_data[0]
