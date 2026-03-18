#!/usr/bin/env python3
"""
Sentinel-2 Albedo Calculation Script (10m Resolution)
======================================================

This script downloads Sentinel-2 Level-2A imagery from the Copernicus Data Space 
Ecosystem (CDSE) using EODAG, and calculates Broadband Surface Albedo at 10m 
resolution using the Liang (2001) formula.

Author: Senior Geospatial Python Developer
Date: 2024
License: MIT

Requirements:
    pip install eodag rasterio numpy

Usage:
    Set your CDSE credentials as environment variables or in the script,
    then run the script with your desired parameters.
"""

import os
import glob
import logging
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge

# Apply platform-specific fixes (MacOS multiprocessing, PROJ_LIB)
from .utils import apply_plugin_fixes
apply_plugin_fixes()

# Disable EODAG parallel downloads to avoid multiprocessing issues in QGIS
os.environ['EODAG__COP_DATASPACE__DOWNLOAD__OUTPUTS_EXTENSION'] = '.zip'
os.environ['EODAG__COP_DATASPACE__DOWNLOAD__EXTRACT'] = 'true'

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# ============================================================================
# CONFIGURATION
# ============================================================================

class Sentinel2AlbedoConfig:
    """Configuration class for Sentinel-2 Albedo calculation."""
    
    # CDSE Credentials (set via environment variables or directly here)
    # IMPORTANT: Never commit real credentials to version control!
    USERNAME: str = os.getenv("CDSE_USERNAME", "")
    PASSWORD: str = os.getenv("CDSE_PASSWORD", "")
    
    # Search Parameters
    PRODUCT_TYPE: str = "S2_MSI_L2A"  # Sentinel-2 Level-2A
    MAX_CLOUD_COVER: int = 10  # Maximum cloud cover percentage
    
    # Output Settings
    OUTPUT_DIR: str = "./output"
    DOWNLOAD_DIR: str = "./downloads"
    
    # Albedo Coefficients - Liang (2001) formula for Sentinel-2
    # Albedo = 0.356*B2 + 0.130*B4 + 0.373*B8 + 0.085*B11 + 0.072*B12 - 0.0018
    ALBEDO_COEFFICIENTS: Dict[str, float] = {
        "B02": 0.356,
        "B04": 0.130,
        "B08": 0.373,
        "B11": 0.085,
        "B12": 0.072,
        "offset": -0.0018
    }
    
    # SCL (Scene Classification Layer) classes to mask
    # 0: No Data, 3: Cloud Shadow, 8: Cloud Medium Prob, 9: Cloud High Prob, 10: Thin Cirrus
    SCL_MASK_VALUES: List[int] = [0, 3, 8, 9, 10]
    
    # DN to Reflectance conversion factor
    DN_TO_REFLECTANCE_FACTOR: float = 10000.0


# ============================================================================
# AUTHENTICATION & DOWNLOAD (EODAG)
# ============================================================================

def setup_eodag_credentials(username: str, password: str) -> None:
    """
    Set up EODAG credentials for the Copernicus Data Space Ecosystem.
    
    Args:
        username: CDSE username
        password: CDSE password
    """
    # EODAG expects credentials in specific environment variables
    # Note: The provider name is 'cop_dataspace' for CDSE
    os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME"] = username
    os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD"] = password
    logger.info("EODAG credentials configured for Copernicus Data Space Ecosystem")


def search_sentinel2_products(
    bbox: Tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    max_cloud_cover: int = 10,
    product_type: str = "S2_MSI_L2A"
) -> List:
    """
    Search for Sentinel-2 Level-2A products using EODAG.
    
    Args:
        bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'
        max_cloud_cover: Maximum cloud cover percentage (0-100)
        product_type: EODAG product type (default: S2_MSI_L2A)
    
    Returns:
        List of search results (EOProduct objects)
    
    Raises:
        ValueError: If no products are found
    """
    try:
        from eodag import EODataAccessGateway
    except ImportError:
        raise ImportError(
            "EODAG is not installed. Install it with: pip install eodag"
        )
    
    logger.info(f"Searching for {product_type} products...")
    logger.info(f"  Bounding Box: {bbox}")
    logger.info(f"  Date Range: {start_date} to {end_date}")
    logger.info(f"  Max Cloud Cover: {max_cloud_cover}%")
    
    # Initialize EODAG
    dag = EODataAccessGateway()
    
    # Set the preferred provider to CDSE
    dag.set_preferred_provider("cop_dataspace")
    
    # Perform the search
    # EODAG expects geometry as a dict with 'lonmin', 'latmin', 'lonmax', 'latmax'
    search_criteria = {
        "productType": product_type,
        "start": start_date,
        "end": end_date,
        "geom": {
            "lonmin": bbox[0],
            "latmin": bbox[1],
            "lonmax": bbox[2],
            "latmax": bbox[3]
        },
        "cloudCover": max_cloud_cover
    }
    
    results = dag.search_all(**search_criteria)
    
    if not results:
        raise ValueError(
            f"No products found matching the search criteria:\n"
            f"  Product Type: {product_type}\n"
            f"  Bbox: {bbox}\n"
            f"  Dates: {start_date} to {end_date}\n"
            f"  Cloud Cover: <{max_cloud_cover}%"
        )
    
    logger.info(f"Found {len(results)} products matching the criteria")
    
    # Sort by cloud cover (ascending) and date (most recent first)
    results = sorted(
        results,
        key=lambda x: (
            x.properties.get("cloudCover", 100),
            -datetime.fromisoformat(
                x.properties.get("startTimeFromAscendingNode", "1970-01-01T00:00:00Z")
                .replace("Z", "+00:00")
            ).timestamp()
        )
    )
    
    # Log the first few results
    for i, product in enumerate(results[:5]):
        props = product.properties
        logger.info(
            f"  [{i+1}] {product.properties.get('id', 'N/A')} - "
            f"Cloud: {props.get('cloudCover', 'N/A')}% - "
            f"Date: {props.get('startTimeFromAscendingNode', 'N/A')[:10]}"
        )
    
    return results


def download_product(
    product,
    download_dir: str,
    extract: bool = True
) -> Path:
    """
    Download a Sentinel-2 product.
    
    Args:
        product: EOProduct object from EODAG search
        download_dir: Directory to download the product to
        extract: Whether to extract the downloaded archive
    
    Returns:
        Path to the downloaded .SAFE directory
    """
    try:
        from eodag import EODataAccessGateway
    except ImportError:
        raise ImportError("EODAG is not installed. Install it with: pip install eodag")
    
    logger.info(f"Downloading product: {product.properties.get('id', 'Unknown')}")
    
    # Ensure download directory exists
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize EODAG
    dag = EODataAccessGateway()
    dag.set_preferred_provider("cop_dataspace")
    
    # Download the product
    downloaded_path = dag.download(
        product,
        outputs_prefix=str(download_path),
        extract=extract
    )
    
    # The download function returns the path to the downloaded file/folder
    if isinstance(downloaded_path, str):
        downloaded_path = Path(downloaded_path)
    
    logger.info(f"Product downloaded to: {downloaded_path}")
    
    return downloaded_path


# ============================================================================
# DATA PROCESSING (RASTERIO & NUMPY)
# ============================================================================

def find_band_files(safe_dir: Path) -> Dict[str, Path]:
    """
    Locate the required band files inside the .SAFE folder structure.
    
    Sentinel-2 L2A Structure:
    ├── MTD_MSIL2A.xml
    ├── GRANULE/
    │   └── L2A_TILE_ID/
    │       └── IMG_DATA/
    │           ├── R10m/
    │           │   ├── *_B02_10m.jp2
    │           │   ├── *_B04_10m.jp2
    │           │   └── *_B08_10m.jp2
    │           └── R20m/
    │               ├── *_B11_20m.jp2
    │               ├── *_B12_20m.jp2
    │               └── *_SCL_20m.jp2
    
    Args:
        safe_dir: Path to the .SAFE directory
    
    Returns:
        Dictionary mapping band names to file paths
    
    Raises:
        FileNotFoundError: If required bands are not found
    """
    logger.info(f"Locating band files in: {safe_dir}")
    
    required_bands = {
        "B02": ("R10m", "*_B02_10m.jp2"),
        "B04": ("R10m", "*_B04_10m.jp2"),
        "B08": ("R10m", "*_B08_10m.jp2"),
        "B11": ("R20m", "*_B11_20m.jp2"),
        "B12": ("R20m", "*_B12_20m.jp2"),
        "SCL": ("R20m", "*_SCL_20m.jp2")
    }
    
    band_files = {}
    
    # Navigate to the IMG_DATA directory
    img_data_pattern = str(safe_dir / "GRANULE" / "*" / "IMG_DATA")
    img_data_dirs = glob.glob(img_data_pattern)
    
    if not img_data_dirs:
        raise FileNotFoundError(
            f"Could not locate IMG_DATA directory in {safe_dir}"
        )
    
    img_data_dir = Path(img_data_dirs[0])
    logger.info(f"Found IMG_DATA directory: {img_data_dir}")
    
    # Find each required band
    for band_name, (resolution_folder, pattern) in required_bands.items():
        search_pattern = str(img_data_dir / resolution_folder / pattern)
        matches = glob.glob(search_pattern)
        
        if not matches:
            raise FileNotFoundError(
                f"Could not find band {band_name} with pattern: {search_pattern}"
            )
        
        band_files[band_name] = Path(matches[0])
        logger.info(f"  {band_name}: {band_files[band_name].name}")
    
    return band_files


def read_band_10m_crop(band_path: Path, bbox_wgs84: Tuple[float, float, float, float]) -> Tuple[np.ndarray, dict]:
    """Read a 10m band clipped to the bounding box."""
    import rasterio.warp
    from rasterio.windows import from_bounds, Window
    from rasterio.windows import transform as window_transform
    
    logger.info(f"Reading cropped 10m band: {band_path.name}")
    with rasterio.open(band_path) as src:
        bounds = rasterio.warp.transform_bounds('EPSG:4326', src.crs, *bbox_wgs84)
        buffer = 100 # buffer in meters to ensure full coverage during resampling
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
        logger.info(f"  Cropped shape: {data.shape}, dtype: {data.dtype}")
        return data, profile


def read_and_align_20m_band_crop(
    band_path: Path,
    target_profile: dict,
    resampling_method: Resampling = Resampling.bilinear
) -> np.ndarray:
    """Read a 20m band and reproject it directly to align with the cropped 10m profile."""
    import rasterio.warp
    logger.info(f"Reading and aligning cropped 20m band: {band_path.name}")
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
        logger.info(f"  Aligned shape: {out_data[0].shape}")
        return out_data[0]


def convert_dn_to_reflectance(
    data: np.ndarray,
    scale_factor: float = 10000.0
) -> np.ndarray:
    """
    Convert Digital Numbers (DN) to Reflectance values.
    
    Sentinel-2 L2A stores reflectance values as DN * 10000.
    
    Args:
        data: Band data as DN values
        scale_factor: Scaling factor (default 10000.0 for Sentinel-2 L2A)
    
    Returns:
        Reflectance values (0-1 range, float32)
    """
    return data / scale_factor


# ============================================================================
# ALBEDO CALCULATION
# ============================================================================

def calculate_broadband_albedo(
    bands: Dict[str, np.ndarray],
    coefficients: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Calculate Broadband Surface Albedo using the Liang (2001) formula.
    
    Formula:
        Albedo = 0.356*B2 + 0.130*B4 + 0.373*B8 + 0.085*B11 + 0.072*B12 - 0.0018
    
    Args:
        bands: Dictionary of band reflectance data (B02, B04, B08, B11, B12)
        coefficients: Optional custom coefficients dictionary
    
    Returns:
        Broadband albedo array
    """
    logger.info("Calculating broadband albedo using Liang (2001) formula")
    
    if coefficients is None:
        coefficients = Sentinel2AlbedoConfig.ALBEDO_COEFFICIENTS
    
    # Apply the Liang (2001) formula
    albedo = (
        coefficients["B02"] * bands["B02"] +
        coefficients["B04"] * bands["B04"] +
        coefficients["B08"] * bands["B08"] +
        coefficients["B11"] * bands["B11"] +
        coefficients["B12"] * bands["B12"] +
        coefficients["offset"]
    )
    
    # Clip values to valid range [0, 1]
    albedo = np.clip(albedo, 0.0, 1.0)
    
    logger.info(f"  Albedo range (before masking): {np.nanmin(albedo):.4f} - {np.nanmax(albedo):.4f}")
    
    return albedo


def create_cloud_mask(
    scl_data: np.ndarray,
    mask_values: Optional[List[int]] = None
) -> np.ndarray:
    """
    Create a cloud mask from the Scene Classification Layer (SCL).
    
    SCL Classes:
        0: No Data
        1: Saturated or defective
        2: Topographic casted shadows / Dark Area Pixels
        3: Cloud shadows
        4: Vegetation
        5: Not-vegetated (bare soils, desert, rocks...)
        6: Water
        7: Unclassified
        8: Cloud medium probability
        9: Cloud high probability
        10: Thin cirrus
        11: Snow or ice
    
    Args:
        scl_data: Scene Classification Layer data
        mask_values: List of SCL values to mask (default: [0, 3, 8, 9, 10])
    
    Returns:
        Boolean mask (True = valid pixel, False = masked pixel)
    """
    logger.info("Creating cloud mask from SCL")
    
    if mask_values is None:
        mask_values = Sentinel2AlbedoConfig.SCL_MASK_VALUES
    
    logger.info(f"  Masking SCL classes: {mask_values}")
    
    # Create mask: True for pixels to KEEP (valid), False for pixels to MASK
    valid_mask = np.ones(scl_data.shape, dtype=bool)
    
    for value in mask_values:
        invalid_count = np.sum(scl_data == value)
        valid_mask[scl_data == value] = False
        logger.info(f"    Class {value}: {invalid_count} pixels masked")
    
    valid_percentage = (np.sum(valid_mask) / valid_mask.size) * 100
    logger.info(f"  Valid pixels: {valid_percentage:.1f}%")
    
    return valid_mask


def apply_mask(
    data: np.ndarray,
    mask: np.ndarray
) -> np.ndarray:
    """
    Apply a mask to the data, setting masked pixels to NaN.
    
    Args:
        data: Input data array
        mask: Boolean mask (True = keep, False = set to NaN)
    
    Returns:
        Masked data array with NaN for invalid pixels
    """
    masked_data = data.copy()
    masked_data[~mask] = np.nan
    return masked_data


# ============================================================================
# OUTPUT
# ============================================================================

def save_geotiff(
    data: np.ndarray,
    output_path: Path,
    profile: dict,
    nodata: float = np.nan
) -> None:
    """
    Save data as a GeoTIFF file.
    
    Args:
        data: Data array to save
        output_path: Output file path
        profile: Rasterio profile (from input band)
        nodata: NoData value to use
    """
    logger.info(f"Saving GeoTIFF to: {output_path}")
    
    # Update profile for output
    profile.update(
        dtype=rasterio.float32,
        count=1,
        nodata=nodata,
        compress='deflate',
        driver='GTiff'
    )
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(data.astype(np.float32), 1)
    
    logger.info(f"  File saved successfully")
    logger.info(f"  Shape: {data.shape}")
    logger.info(f"  CRS: {profile.get('crs')}")


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def process_sentinel2_albedo(
    safe_dir: Path,
    bbox: Tuple[float, float, float, float],
    output_path: Optional[Path] = None
) -> Path:
    """
    Process a Sentinel-2 .SAFE directory to calculate albedo.
    
    This function handles:
        1. Locating band files
        2. Reading cropped bands to 10m
        3. Converting DN to reflectance
        4. Calculating broadband albedo
        5. Applying cloud mask
        6. Saving output GeoTIFF
    
    Args:
        safe_dir: Path to the .SAFE directory
        bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat) in WGS84 for dynamic cropping
        output_path: Optional output file path (default: auto-generated)
    
    Returns:
        Path to the output GeoTIFF file
    """
    logger.info("=" * 60)
    logger.info("SENTINEL-2 BROADBAND ALBEDO CALCULATION")
    logger.info("=" * 60)
    
    safe_dir = Path(safe_dir)
    
    # Step 1: Locate band files
    logger.info("\n[Step 1/6] Locating band files...")
    band_files = find_band_files(safe_dir)
    
    # Step 2: Read cropped 10m bands (B02, B04, B08)
    logger.info("\n[Step 2/6] Reading cropped 10m bands...")
    b02_data, profile = read_band_10m_crop(band_files["B02"], bbox)
    b04_data, _ = read_band_10m_crop(band_files["B04"], bbox)
    b08_data, _ = read_band_10m_crop(band_files["B08"], bbox)
    
    target_shape = b02_data.shape
    logger.info(f"  Cropped target shape (10m): {target_shape}")
    
    # Step 3: Read and resample 20m bands (B11, B12, SCL)
    logger.info("\n[Step 3/6] Reading and aligning cropped 20m bands to 10m...")
    
    # Spectral bands: use bilinear interpolation
    b11_data = read_and_align_20m_band_crop(band_files["B11"], profile, Resampling.bilinear)
    b12_data = read_and_align_20m_band_crop(band_files["B12"], profile, Resampling.bilinear)
    
    # SCL: use nearest neighbor (categorical data)
    scl_data = read_and_align_20m_band_crop(band_files["SCL"], profile, Resampling.nearest)
    
    # Step 4: Convert DN to Reflectance
    logger.info("\n[Step 4/6] Converting DN to Reflectance...")
    scale_factor = Sentinel2AlbedoConfig.DN_TO_REFLECTANCE_FACTOR
    
    bands = {
        "B02": convert_dn_to_reflectance(b02_data, scale_factor),
        "B04": convert_dn_to_reflectance(b04_data, scale_factor),
        "B08": convert_dn_to_reflectance(b08_data, scale_factor),
        "B11": convert_dn_to_reflectance(b11_data, scale_factor),
        "B12": convert_dn_to_reflectance(b12_data, scale_factor)
    }
    
    logger.info(f"  Reflectance ranges:")
    for band_name, band_data in bands.items():
        logger.info(f"    {band_name}: {np.nanmin(band_data):.4f} - {np.nanmax(band_data):.4f}")
    
    # Step 5: Calculate Albedo and Apply Cloud Mask
    logger.info("\n[Step 5/6] Calculating albedo and applying cloud mask...")
    
    # Calculate albedo
    albedo = calculate_broadband_albedo(bands)
    
    # Create and apply cloud mask
    cloud_mask = create_cloud_mask(scl_data)
    albedo_masked = apply_mask(albedo, cloud_mask)
    
    valid_albedo = albedo_masked[~np.isnan(albedo_masked)]
    if len(valid_albedo) > 0:
        logger.info(f"  Final albedo range: {np.nanmin(valid_albedo):.4f} - {np.nanmax(valid_albedo):.4f}")
        logger.info(f"  Mean albedo: {np.nanmean(valid_albedo):.4f}")
    
    # Step 6: Save Output
    logger.info("\n[Step 6/6] Saving output GeoTIFF...")
    
    if output_path is None:
        # Generate output filename based on input
        safe_name = safe_dir.stem.replace(".SAFE", "")
        output_path = Path(Sentinel2AlbedoConfig.OUTPUT_DIR) / f"{safe_name}_albedo_10m.tif"
    
    save_geotiff(albedo_masked, output_path, profile)
    
    logger.info("\n" + "=" * 60)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 60)
    
    return output_path


def main(
    bbox: Tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    max_cloud_cover: int = 10,
    download_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    max_products: int = 1
) -> List[Path]:
    """
    Main function to search, download, and process Sentinel-2 imagery for albedo.
    
    Args:
        bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'
        username: CDSE username (optional, uses env var if not provided)
        password: CDSE password (optional, uses env var if not provided)
        max_cloud_cover: Maximum cloud cover percentage
        download_dir: Directory for downloads
        output_dir: Directory for output files
        max_products: Maximum number of products to process
    
    Returns:
        List of paths to output albedo GeoTIFF files
    """
    logger.info("=" * 60)
    logger.info("SENTINEL-2 ALBEDO PROCESSING PIPELINE")
    logger.info("=" * 60)
    
    # Set up credentials
    username = username or Sentinel2AlbedoConfig.USERNAME
    password = password or Sentinel2AlbedoConfig.PASSWORD
    
    if not username or not password:
        raise ValueError(
            "CDSE credentials not provided. Set via:\n"
            "  - Environment variables: CDSE_USERNAME, CDSE_PASSWORD\n"
            "  - Function parameters: username, password"
        )
    
    setup_eodag_credentials(username, password)
    
    # Set directories
    download_dir = download_dir or Sentinel2AlbedoConfig.DOWNLOAD_DIR
    if output_dir:
        Sentinel2AlbedoConfig.OUTPUT_DIR = output_dir
    
    # Search for products
    logger.info("\n[Phase 1] Searching for Sentinel-2 products...")
    products = search_sentinel2_products(
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        max_cloud_cover=max_cloud_cover
    )
    
    # Filter products: we want the best product (lowest cloud cover) for EACH tile
    # found in the search results that intersects our AOI.
    tiles_found = {}
    for prod in products:
        # Try to get tile ID from properties
        tile_id = prod.properties.get('tileId') or prod.properties.get('granuleIdentifier')
        if not tile_id:
            import re
            prod_id = prod.properties.get('id', 'unknown')
            # Extract tile ID like T33TWH from S2A_MSIL2A_...
            match = re.search(r'_T([0-9]{2}[A-Z]{3})_', prod_id)
            if match:
                tile_id = match.group(1)
            else:
                # Fallback for EODAG results if tileId is missing
                tile_id = prod_id
            
        if tile_id not in tiles_found:
            tiles_found[tile_id] = prod
            
    products_to_process = list(tiles_found.values())
    
    # Filter products: we want the optimal tiling layout minimizing redundant downloads.
    try:
        from shapely.geometry import box, shape
        aoi_shape = box(*bbox)
        
        # Calculate coverage of each product
        for prod in products_to_process:
            try:
                prod_geom = shape(prod.geometry)
                coverage_pct = prod_geom.intersection(aoi_shape).area / aoi_shape.area
                prod.properties['_coverage_pct'] = coverage_pct
            except Exception:
                prod.properties['_coverage_pct'] = 0.0

        # Sort descending by coverage, ascending by cloud cover
        products_to_process.sort(key=lambda x: (-x.properties.get('_coverage_pct', 0.0), x.properties.get('cloudCover', 100)))

        # Only keep tiles until we reach full coverage
        selected_products = []
        current_coverage = None
        for prod in products_to_process:
            if prod.properties.get('_coverage_pct', 0) == 0: continue
            
            try:
                prod_geom = shape(prod.geometry)
                if current_coverage is None:
                    selected_products.append(prod)
                    current_coverage = prod_geom.intersection(aoi_shape)
                else:
                    # Check if this new product adds any missing coverage
                    missing_coverage = aoi_shape.difference(current_coverage)
                    if missing_coverage.area > (aoi_shape.area * 0.001): # Not fully covered
                        if prod_geom.intersects(missing_coverage):
                            intersection_with_missing = prod_geom.intersection(missing_coverage)
                            if intersection_with_missing.area > (aoi_shape.area * 0.001):
                                selected_products.append(prod)
                                current_coverage = current_coverage.union(prod_geom).intersection(aoi_shape)
                    else:
                        break # Fully covered
            except Exception:
                selected_products.append(prod)
                
        if selected_products:
            products_to_process = selected_products
            
    except ImportError:
        logger.warning("Shapely not installed. Skipping advanced coverage filtering.")
        # Sort them by cloud cover again just to be sure
        products_to_process.sort(key=lambda x: x.properties.get("cloudCover", 100))
        if len(products_to_process) > max_products and max_products > 0:
            logger.info(f"Limiting processing to the first {max_products} tiles out of {len(products_to_process)} found.")
            products_to_process = products_to_process[:max_products]
    
    logger.info(f"\nProcessing {len(products_to_process)} product(s) across {len(tiles_found)} unique tiles...")
    
    individual_outputs = []
    
    for i, product in enumerate(products_to_process, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing product {i}/{len(products_to_process)}: {product.properties.get('id')}")
        logger.info(f"{'='*60}")
        
        try:
            # Download product
            logger.info("\n[Phase 2] Downloading product...")
            safe_path = download_product(product, download_dir)
            
            # Process albedo
            logger.info("\n[Phase 3] Processing albedo...")
            output_path = process_sentinel2_albedo(safe_path, bbox)
            individual_outputs.append(output_path)
            
            logger.info(f"\n✓ Product processed successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing product: {e}")
            continue
    
    output_files = []
    if len(individual_outputs) > 1:
        logger.info("\n[Phase 4] Mosaicking multiple tiles...")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mosaic_path = Path(output_dir) / f"sentinel2_albedo_mosaic_{timestamp}.tif"
            
            src_files_to_mosaic = []
            for fp in individual_outputs:
                src = rasterio.open(fp)
                src_files_to_mosaic.append(src)
                
            mosaic, out_trans = merge(src_files_to_mosaic)
            
            # Copy the profile from the first file
            out_meta = src_files_to_mosaic[0].meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_trans,
                "compress": 'deflate'
            })
            
            with rasterio.open(mosaic_path, "w", **out_meta) as dest:
                dest.write(mosaic)
                
            # Close sources
            for src in src_files_to_mosaic:
                src.close()
            
            logger.info(f"✓ Mosaic created successfully: {mosaic_path}")
            
            # Use original expected filename if possible
            final_path = Path(output_dir) / "sentinel2_albedo_10m.tif"
            if final_path.exists():
                final_path.unlink()
            shutil.copy(mosaic_path, final_path)
            output_files = [final_path]
            
        except Exception as e:
            logger.error(f"Error during mosaicking: {e}")
            output_files = individual_outputs
    else:
        output_files = individual_outputs
    
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Processed {len(output_files)} output file(s)")
    for f in output_files:
        logger.info(f"  → {f}")
    logger.info("=" * 60)
    
    return output_files


# ============================================================================
# QGIS PLUGIN INTEGRATION HELPER
# ============================================================================

def fetch_albedo_for_aoi(
    bbox: Tuple[float, float, float, float],
    output_dir: str,
    download_dir: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_cloud_cover: int = 10,
    max_products: int = 6,
    log_callback: Optional[callable] = None
) -> Tuple[bool, str, Optional[Path]]:
    """
    QGIS Plugin-friendly function to fetch Sentinel-2 albedo for an AOI.
    
    Uses "best available" logic: searches the last 3 months for the image
    with the lowest cloud cover.
    
    Args:
        bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat) in WGS84
        output_dir: Directory to save the final albedo GeoTIFF
        download_dir: Optional directory for temporary downloads (default: temp folder)
        username: CDSE username (uses CDSE_USERNAME env var if not provided)
        password: CDSE password (uses CDSE_PASSWORD env var if not provided)
        start_date: Optional start date (default: 3 months ago)
        end_date: Optional end date (default: today)
        max_cloud_cover: Maximum cloud cover percentage
        log_callback: Optional callback function for logging (receives message string)
    
    Returns:
        Tuple of (success: bool, message: str, output_path: Optional[Path])
    """
    import tempfile
    from datetime import datetime, timedelta
    
    def log(msg):
        if log_callback:
            log_callback(msg)
        logger.info(msg)
    
    # Get credentials from environment if not provided
    username = username or os.getenv("CDSE_USERNAME", "")
    password = password or os.getenv("CDSE_PASSWORD", "")
    
    if not username or not password:
        return False, "Credenziali CDSE non configurate. Imposta CDSE_USERNAME e CDSE_PASSWORD.", None
    
    # Default date range: last 12 months (1 year) - extended for better coverage
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_dt = datetime.now() - timedelta(days=365)
        start_date = start_dt.strftime("%Y-%m-%d")
    
    # Use temp directory for downloads if not specified
    if not download_dir:
        download_dir = tempfile.mkdtemp(prefix="sentinel2_")
    
    log(f"Ricerca Sentinel-2 per AOI: {bbox}")
    log(f"Periodo: {start_date} - {end_date}, Cloud Cover max: {max_cloud_cover}%")
    
    try:
        # Search, download and process
        output_files = main(
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            username=username,
            password=password,
            max_cloud_cover=max_cloud_cover,
            download_dir=download_dir,
            output_dir=output_dir,
            max_products=max_products
        )
        
        if output_files:
            output_path = output_files[0]
            return True, f"Albedo calcolato: {output_path.name}", output_path
        else:
            return False, "Nessun prodotto elaborato", None
            
    except ValueError as e:
        return False, f"Errore ricerca: {str(e)}", None
    except Exception as e:
        return False, f"Errore: {str(e)}", None


# ============================================================================
# EXAMPLE USAGE / ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Example usage of the Sentinel-2 Albedo calculation script.
    
    Set credentials via environment variables:
        export CDSE_USERNAME="your_email@example.com"
        export CDSE_PASSWORD="your_password"
    """
    
    # Check for credentials
    if not os.getenv("CDSE_USERNAME") or not os.getenv("CDSE_PASSWORD"):
        print("ERROR: Set CDSE credentials via environment variables:")
        print("  export CDSE_USERNAME='your_email@example.com'")
        print("  export CDSE_PASSWORD='your_password'")
        exit(1)
    
    # Example: Rome, Italy area
    BBOX = (12.35, 41.80, 12.55, 41.95)
    
    success, message, output_path = fetch_albedo_for_aoi(
        bbox=BBOX,
        output_dir="./sentinel2_albedo_output",
        max_cloud_cover=10
    )
    
    if success:
        print(f"\n✓ {message}")
        print(f"  File: {output_path}")
    else:
        print(f"\n✗ {message}")
