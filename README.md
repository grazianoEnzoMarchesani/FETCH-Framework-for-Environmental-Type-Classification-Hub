![FETCH Logo](assets/fetch_logo.png)

# FETCH: Framework for Environmental Type Classification Hub

**FETCH** is an advanced geospatial framework designed to automate the classification and analysis of **Local Climate Zones (LCZ)**. Originally developed as a collection of processing scripts, FETCH has evolved into a modular **QGIS Plugin** that streamlines the entire workflow: from multi-source data acquisition to the calculation of complex urban climate parameters.

---

## Technical Vision: From Scripts to Framework

The project is currently transitioning from a series of standalone scripts to a fully integrated QGIS Plugin environment. This evolution improves:
- **Modularity**: Specialized "Downloaders" and "Processors".
- **Reproducibility**: Standardized workflows for LCZ mapping based on Stewart & Oke (2012).
- **Usability**: A modern Dashboard UI to manage the entire pipeline asynchronously.

---

## Data Methodology

### 1. Data Acquisition
FETCH integrates specialized downloaders for high-resolution global and regional datasets:
- **ESA WorldCover (10m)**: Authoritative land cover classification.
- **ETH Global Canopy Height (10m)**: Vegetation height data for $z_h$ and SVF transparency.
- **Meta HRSL**: High-resolution population density for Anthropogenic Heat estimation.
- **TINitaly**: 10m precision DEM for the Italian territory.
- **TUM Building Height**: Building morphological data (LoD1 footprints).
- **Sentinel-2 Albedo**: Automated calculation of surface albedo using Copernicus raw data.
- **Copernicus HRL**: Imperviousness and Tree Cover Density (TCD) for refined surface fractions.
- **OSM & ANAS**: Road network and traffic volume points for vehicular heat.

### 2. Transformation & Unification
The framework handles the heavy lifting of spatial alignment:
- **Auto-UTM Projection**: All datasets are automatically re-projected to the appropriate UTM zone based on the Area of Interest (AOI).
- **Clipping & Merging**: Disparate tiles are merged and clipped exactly to the AOI extent.
- **Synthetic DSM**: Integration of DTM, Buildings, and Canopy layers into a unified high-resolution Synthetic DSM.

---

## LCZ Parameter "Decathlon"

FETCH calculates the 10 core physical properties defined in the LCZ standard:

| Parameter | Logic & Implementation | Specific Use |
| :--- | :--- | :--- |
| **Sky View Factor (SVF)** | Measured from ground-level POV; includes tree canopy transparency (0.7 opacity). | Radiation balance and sky accessibility. |
| **Aspect Ratio (H/W)** | Measured via direct geometry: $\text{Mean Height} / \text{Median Distance to Neighbors}$. | Flow blockage and urban canyon geometry. |
| **Building Surface Fraction (BSF)** | Exact intersection of building footprints within the grid cell. | Building density and urbanization level. |
| **Impervious Surface Fraction (ISF)** | Derived from Copernicus HRL or ESA WorldCover minus BSF. | Surface sealing and runoff/heat storage. |
| **Pervious Surface Fraction (PSF)** | Area covered by vegetation or bare soil (100% - BSF - ISF). | Evapotranspirative cooling potential. |
| **Roughness Elements Height ($z_h$)** | Area-weighted mean height of buildings and tree canopies. | Drag and momentum exchange in the ABL. |
| **Terrain Roughness ($z_0$)** | Mapped from LCZ-specific roughness classes (Davenport-Wieringa). | Wind profile and surface friction. |
| **Surface Admittance** | Estimated based on the dominant surface materials (concrete vs soil). | Thermal inertia and diurnal temperature range. |
| **Surface Albedo** | Calculated via Sentinel-2 BOA reflectance (automated pipeline). | Solar radiation reflection/absorption. |
| **Anthro. Heat Flux (AHF)** | Combined model of population density, traffic volume, and industrial points. | Direct heat release from human activity. |

---

## Classification Philosophies

FETCH offers a wide array of engines to accommodate different research needs, from standard-compliant statistical matching to advanced AI-driven contextual analysis.

### Standard & Experimental Engines
- **Standard (Stable)**: Pure RMSEP (Root Mean Square Error of Prediction) matching based on Stewart & Oke (2012) nominal ranges. It is the baseline for LCZ classification ([DOI: 10.2495/SC250031](https://doi.org/10.2495/SC250031)).
- **Experimental (v2.0)**: Uses a **Balanced Score** logic. It weights statistical proximity against a **Match Bonus** (15% error reduction for every parameter that falls perfectly within its archetype range), improving tie-breaking between similar classes.

### Contextual Smoothing (v1.1 & v2.1)
- **v1.1 & v2.1 (Weighted Contextual)**: These versions apply a 3x3 spatial kernel (Center=2, Neighbors=1) to the raw parameters *before* classification. This acts as a "physical smoothing" that reduces "salt-and-pepper" noise by considering the immediate morphological neighborhood.

### Advanced Distance Engines (v3.0 & v6.0)
### 1. v3.0 Advanced (RMSEP)
- **Philosophy**: Statistical distance matching.
- **How it works**: Calculates the Root Mean Square Error of Prediction (RMSEP) between the cell's parameters and the 10 ideal archetype ranges.
- **Pros**: Perfectly compliant with the statistical standard; stable and predictable.
- **Limits**: Can be sensitive to outliers in a single parameter (e.g., one very tall building).

### 2. v6.0 WZD-V (Weighted Z-Distance with Veto)
- **Philosophy**: Hierarchical statistical leadership.
- **How it works**: Uses Z-scores weights ($Z^2$) to prioritize parameters that are most distinctive for a specific class (e.g., BSF for LCZ 3). Includes a **Veto** mechanism: if a dominant parameter (like SVF for LCZ A) is way out of range, the class is rejected regardless of others.
- **Pros**: More robust than simple RMSEP; handles "tie-breaks" better.
- **Limits**: Requires fine-tuning of weights for specific regional topographies.

### Adaptive & Machine Learning Engines (v4.0 - v7.0)
- **v4.0 FAD (Fuzzy Archetype Distance)**: Uses **Gaussian and Sigmoid membership** functions instead of binary ranges. This allows for a probabilistic fit that is highly resilient to Italian and Mediterranean morphological anomalies.
- **v5.0 Mahalanobis Adaptive**: Implements a data-driven distance that considers parameter correlations (covariance). It uses a persistent **Knowledge Base** to blend theoretical ranges (60%) with local empirical data (40%).
- **v7.0 RF (District-Based Random Forest)**: Clusters buildings into morphological districts (HDBSCAN) and classifies the coherent groups using a **Random Forest** model trained on the global Knowledge Base. It captures complex non-linear relationships between parameters.

### Current State-of-the-Art
### 3. v8.0 Semantic Expert Engine (The "Perito")
- **Philosophy**: Contextual district logic and Explainable AI (XAI).
- **How it works**: Clusters cells into "Districts" before classifying. It translates numbers into **Fuzzy Tags** (e.g., "High-rise", "Dense mix", "Mostly paved") and matches them against a rule-based expert system.
- **Pros**: Absorbs salt-and-pepper noise locally; provides textual justification for every choice (XAI).
- **Limits**: Higher computational cost due to spatial clustering; requires building height data for optimal results.

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

### Phase 2: Core Parameters & Albedo (Completed)
- [x] Sentinel-2 Albedo integration.
- [x] Optimization of Sky View Factor with transparency.
- [x] Refactor of building height calculation logic (Synthetic DSM).
- [x] Full 10-parameter calculation pipeline.

### Phase 3: Advanced Analytics & UX (In Progress)
- [x] **Semantic v8 Engine**: Clustering and XAI.
- [x] **Map Crystallization**: Automated styling and export of parameter maps.
- [ ] **Automated Validation**: Compare LCZ results with ground truth.
- [ ] **Morphological Reports**: Generate PDF/Markdown summaries for each AOI.

---

## Known Issues & Current Limitations

> [!IMPORTANT]
> **Regional Specification**: While FETCH utilizes global datasets (ESA, ETH, TUM, Sentinel-2), it is currently optimized for the **Italian territory**. This is due to the integration of high-precision national datasets like **TINitaly** and specific morphology tunings for Mediterranean urban contexts.

### Current Technical Challenges
- **Albedo Download Latency**: The Albedo layer download currently requests an area significantly larger than the strict AOI to ensure full coverage. This can result in slow processing and high bandwidth usage (optimization in progress).
- **Projection Rotation Artifacts**: In some instances, the captured boundary based on the visible map extent exhibits a slight rotation. This indicates a minor projection alignment error that requires further evaluation and refinement within Italian coordinate systems.
- **Computation Cost**: Advanced engines like v8.0 Semantic and v7.0 RF require significant CPU/Memory resources due to district-based spatial clustering.

---

## License

Distributed under the **GNU General Public License v3.0**. See `LICENSE` for details.

---

## Acknowledgements

- **Copernicus ecosystem** for Sentinel data.
- **ESA, ETH, and TUM** for providing essential global datasets.
- The **QGIS community** for the incredible open-source GIS engine.

