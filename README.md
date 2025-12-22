# FETCH: Framework for Environmental Type Classification Hub - LCZ Classifier

LCZ Classifier is a project that automates the classification of Local Climate Zones (LCZ) using geospatial data. The process begins with satellite data acquisition through the Google Solar API and continues with a series of QGIS processing steps for LCZ classification.

## Features

- **Data Acquisition**: Web interface for downloading DSM, RGB and MASK tiles via Google Solar API
- **Automated Processing**: Series of Python scripts for QGIS that process data sequentially
- **LCZ Parameter Calculation**: Analysis of:
  - Sky View Factor
  - Aspect Ratio
  - Building Surface Fraction
  - Impervious/Pervious Surface Fraction
  - Height of Roughness Elements
  - Terrain Roughness Class
  - Surface Admittance
  - Surface Albedo
  - Anthropogenic Heat Output

## Prerequisites

- QGIS 3.x
- Python 3.x
- Google API Key for Google Solar API
- Python Libraries:
  - NumPy
  - Statsmodels
  - PyQt5

## Installation

1. Clone the repository
2. Open index.html in browser for the data download interface
3. Import Python scripts into QGIS

## Usage

### 1. Data Acquisition
- Open index.html
- Draw an area on the map
- Enter your Google API Key
- Generate API links and download tiles

### 2. QGIS Processing
Execute the scripts in the following order:
1. `01_merge_fetch_files.py`: Merges downloaded files
2. `02_import_raster_files.py`: Imports raster files into the project
3. `03_make_grid.py`: Creates analysis grid
4. `04_make_buildings.py`: Extracts buildings
5. `05_make_pervius_1.py`: Pervious surfaces analysis (part 1)
6. `06_make_pervius_2.py`: Pervious surfaces analysis (part 2)
7. `07_make_dtm.py`: Generates digital terrain model
8. `08_make_dist.py`: Calculates distances
9. `09_median_distance.py`: Calculates median distances
10. `10_mediana_altezze.py`: Calculates median heights
11. `11_make_h.py`: Calculates height of roughness elements
12. `12_aspect_ratio.py`: Calculates aspect ratio
13. `13_refine_albedo.py`: Refines albedo values
14. `14_rmsep.py`: Calculates and classifies LCZs

## Project Structure

- `index.html`: Web interface for data download
- `scripts/`: Directory containing numbered Python scripts
- `docs/`: Additional documentation

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a branch for your changes
3. Submit a pull request

## License

This project is distributed under the MIT license. See the `LICENSE` file for details.


## Acknowledgements

- Google Solar API
- QGIS Development Team
- Leaflet.js and contributors

## Data Acquisition Interface Details

### Features
- Interactive map interface using Leaflet.js
- Automatic grid generation (195m x 195m tiles)
- Batch download functionality for DSM, RGB, and mask files
- Progress tracking for downloads
- Automatic ZIP file creation
- Built-in geocoding for location search

### Technical Requirements
- Modern web browser with JavaScript enabled
- Active internet connection
- Google Cloud Platform account with:
  - Solar API enabled
  - Valid API key with billing configured
  - Sufficient quota for Solar API requests

### Download Process
1. The interface automatically divides the selected area into 195m x 195m tiles
2. For each tile, three files are downloaded:
   - DSM (Digital Surface Model)
   - RGB (Aerial imagery)
   - Mask (Building footprints)
3. Files are named using the format:
   - `dsm_[latitude]_[longitude].tif`
   - `rgb_[latitude]_[longitude].tif`
   - `mask_[latitude]_[longitude].tif`
4. All files are automatically compressed into a single `tiles.zip` file

### Browser Compatibility
- Chrome (recommended)
- Firefox
- Safari
- Edge

### Data Usage Notes
- Each tile requires 3 API calls
- Approximate file sizes:
  - DSM: ~2-3 MB per tile
  - RGB: ~1-2 MB per tile
  - Mask: ~0.5-1 MB per tile
