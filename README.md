![FETCH Logo](assets/fetch_logo.png)

# FETCH: Framework for Environmental Type Classification Hub

**FETCH** is an advanced geospatial framework designed to automate the classification and analysis of **Local Climate Zones (LCZ)**. Originally developed as a collection of processing scripts, FETCH has evolved into a modular **QGIS Plugin** that streamlines the entire workflow: from multi-source data acquisition to the calculation of complex urban climate parameters.

---

## Technical Vision: From Scripts to Framework

The project is currently transitioning from a series of standalone scripts to a fully integrated QGIS Plugin environment. This evolution improves:
- **Modularity**: Specialized "Downloaders" and "Processors".
- **Reproducibility**: Standardized workflows for LCZ mapping.
- **Usability**: A modern Dashboard UI to manage the entire pipeline.

---

## Key Features

### Automated Data Acquisition
Integrated downloaders for high-resolution global and regional datasets:
- **ESA WorldCover (10m)**: Land cover classification.
- **ETH Global Canopy Height (10m)**: Vegetation height data.
- **Meta HRSL**: High-resolution population density.
- **TINitaly**: High-precision DEM for the Italian territory.
- **TUM Building Height**: Building morphological data.
- **Sentinel-2 Albedo**: Automated calculation of surface albedo using Copernicus data.

### LCZ Parameter Calculation
Automated calculation of core LCZ physical properties:
- **Sky View Factor (SVF)**: Including tree canopy transparency.
- **Building Surface Fraction (BSF)**
- **Impervious/Pervious Surface Fraction**
- **Height of Roughness Elements**
- **Surface Albedo** (Integrated Sentinel-2 pipeline)
- *In Progress*: Aspect Ratio, Terrain Roughness Class, and Surface Admittance.

### Integrated Dashboard
A centralized UI within QGIS to select the Area of Interest (AOI), manage credentials, and trigger processing tasks asynchronously (using `QgsTask` to avoid UI freezing).

---

## Installation (Developer/Early Alpha)

> [!CAUTION]
> The plugin is currently in active development. Features may change rapidly.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/grazianoEnzoMarchesani/FETCH-Framework-for-Environmental-Type-Classification-Hub.git
    ```
2.  **Plugin Setup**:
    - Link the `FETCH` folder to your QGIS plugins directory.
    - Restart QGIS and enable the **FETCH** plugin in the Plugin Manager.
3.  **Dependencies**:
    - QGIS 3.34+ (LTS recommended)
    - Python libraries: `numpy`, `eodag`, `rasterio`, `requests`, `pyproj`.

---

## Project Roadmap

### Phase 1: Foundation (Completed)
- [x] Modular architecture refactoring.
- [x] Basic Data Manager and Downloader structure.
- [x] Implementation of core geometry processors (Vector/Raster).

### Phase 2: Core Parameters & Albedo (In Progress)
- [x] Sentinel-2 Albedo integration.
- [ ] Optimization of Sky View Factor with transparency (In progress).
- [ ] Refactor of building height calculation logic (Synthetic DSM) (In progress).
- [ ] Full UI integration for parameter weights and thresholds.

### Phase 3: Advanced Analytics & UX (Planned)
- [ ] **Automated Validation**: Compare LCZ results with ground truth or existing maps.
- [ ] **Morphological Reports**: Generate PDF/Markdown summaries for each AOI.
- [ ] **External API Expansion**: Support for custom STAC catalogs and Google Solar API (legacy integration).
- [ ] **Multi-temporal Analysis**: Track LCZ changes over time using historical satellite series.

---

## Contributing

We welcome contributions from the geospatial and urban climate community!
1. Check the [current issues](https://github.com/grazianoEnzoMarchesani/FETCH-Framework-for-Environmental-Type-Classification-Hub/issues).
2. Follow the modular structure in `core/downloaders` and `core/processors` when adding features.
3. Open a Pull Request with a clear description of your changes.

---

## License

Distributed under the **GNU General Public License v3.0**. See `LICENSE` for details.

---

## Acknowledgements

- **Copernicus ecosystem** for Sentinel data.
- **ESA, ETH, and TUM** for providing essential global datasets.
- The **QGIS community** for the incredible open-source GIS engine.

