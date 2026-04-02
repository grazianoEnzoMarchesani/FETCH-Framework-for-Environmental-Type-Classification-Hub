# FETCH: Framework for Environmental Type Classification Hub
### National-Scale Local Climate Zone Mapping Suite

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-2.0.0--alpha-orange.svg)](https://github.com/grazianoEnzoMarchesani/FETCH-Framework-for-Environmental-Type-Classification-Hub)
[![QGIS](https://img.shields.io/badge/QGIS-3.40%2B-green.svg)](https://qgis.org/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)](#)

<p align="center">
  <img src="assets/fetch_logo.png" alt="FETCH Logo" width="400">
</p>

**FETCH** is a cutting-edge geospatial framework designed to automate the classification and analysis of **Local Climate Zones (LCZ)**. Engineered for scalability, FETCH transitions from experimental scripts to a modular **QGIS Plugin**, providing a rigorous pipeline for urban climate research, sustainable planning, and environmental modeling.

---

## 🚀 Key Features

- 🛰️ **Automated Data Acquisition**: Integrated downloaders for ESA WorldCover, ETH Canopy Height, Sentinel-2 (Albedo), and TUM Buildings.
- 📐 **Synthetic DSM Strategy**: Advanced fusion of DTM, Building Footprints (LoD1), and Vegetation Height for high-fidelity urban morphology.
- 🧠 **Multi-Engine Classification**: From standard RMSEP matching to **v8.0 Semantic Expert (XAI)** engines.
- 📊 **Asynchronous Pipeline**: Modern Dashboard UI designed to handle heavy spatial computations without freezing the GIS environment.
- 🇮🇹 **Italian Territory Optimization**: Specialized integration with national datasets like **TINitaly** and Mediterranean morphology presets.

---

## 📐 The "Synthetic DSM" Methodology

FETCH doesn't just overlay data; it reconstructs the urban fabric. By integrating three distinct layers, it creates a **Synthetic Digital Surface Model (S-DSM)**:
1.  **Terrain**: 10m precision DTM (e.g., TINitaly).
2.  **Buildings**: LoD1 footprints with architectural height attributes.
3.  **Canopy**: ETH Global Canopy Height (10m) with customized transparency (0.7) for SVF calculation.

This unified model ensures that parameters like **Sky View Factor (SVF)** and **Roughness ($z_h$)** are calculated with unprecedented geometric consistency.

---

## 📊 The LCZ Parameter "Decathlon"

The framework calculates the 10 core physical properties defined by Stewart & Oke (2012):

| Parameter | Symbol | Source / Logic | Impact |
| :--- | :---: | :--- | :--- |
| **Sky View Factor** | $SVF$ | Ray-casting on Synthetic DSM | Radiation balance |
| **Aspect Ratio** | $H/W$ | Geometry-based (Height/Canyon Width) | Ventilation & heat trapping |
| **Building Fraction** | $BSF$ | Footprint intersection within grid | Urbanization level |
| **Impervious Fraction** | $ISF$ | Copernicus HRL / WorldCover | Runoff & heat storage |
| **Pervious Fraction** | $PSF$ | Residual area (Veg/Soil) | Evapotranspirative cooling |
| **Roughness Height** | $z_h$ | Area-weighted mean (Buildings + Trees) | Atmospheric Drag |
| **Terrain Roughness** | $z_0$ | Davenport-Wieringa class mapping | Wind profile |
| **Surface Admittance** | $\mu$ | Material thermal properties | Diurnal range |
| **Surface Albedo** | $\alpha$ | Sentinel-2 BOA Reflectance | Solar radiation |
| **Anthro. Heat Flux** | $Q_F$ | Population + Traffic + Industry | Direct heat release |

---

## 🧠 Classification Engines Portfolio

FETCH offers a tiered approach to LCZ classification, allowing researchers to choose the engine that best fits their accuracy and explainability requirements.

### 🔹 Deterministic & Statistical (Baseline)
- **Standard (v1.0)**: Pure RMSEP distance matching based on universal nominal ranges.
- **Experimental (v2.0)**: Balanced score logic with match bonuses for perfect archetype fits.
- **WZD-V (v6.0)**: Weighted Z-Distance with **Veto logic** for dominant parameters.

### 🔸 AI-Driven & Semantic (SOTA)
- **Fuzzy Archetype (v4.0)**: Gaussian membership functions for resilient Mediterranean mapping.
- **Semantic Expert (v8.0)**: *The "Perito"*. Uses District-based clustering and Explainable AI (XAI) to provide textual justifications for every classification.
- **Adaptive RF (v7.0)**: Random Forest model trained on a global knowledge base, optimal for capturing non-linear urban relationships.

---

## 🛠️ Installation & Setup

> [!WARNING]
> **Experimental Version**: FETCH is currently in Early Alpha. Features and API are subject to rapid change.

### 1. Plugin Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/grazianoEnzoMarchesani/FETCH-Framework-for-Environmental-Type-Classification-Hub.git
   ```
2. Symlink or copy the `FETCH` directory to your QGIS plugins folder:
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
3. Restart QGIS and enable **FETCH** in the Plugin Manager.

### 2. Dependency Management
FETCH requires several advanced Python libraries (`eodag`, `rasterio`, `hdbscan`, etc.). We provide an automated installer:
1. Open the **QGIS Python Console**.
2. Run the following command:
   ```python
   exec(open("path/to/FETCH/install_deps_qgis.py").read())
   ```
3. Restart QGIS.

---

## 🗺️ Project Roadmap

- [x] **Phase 1**: Modular refactoring & Data Manager implementation.
- [x] **Phase 2**: Albedo integration & Full 10-parameter pipeline.
- [x] **Phase 3**: v8.0 Semantic Engine & XAI reporting.
- [ ] **Phase 4**: Automated ground-truth validation & PDF Morphological Reports.
- [ ] **Phase 5**: Multi-temporal LCZ analysis (Urban Evolution).

---

## 📜 License & Acknowledgements

Distributed under the **GNU General Public License v3.0**. See `LICENSE` for details.

Special thanks to:
- **Copernicus & ESA** for the Sentinel-2 and WorldCover datasets.
- **ETH Zurich & TUM** for global height and morphological data.
- **TINitaly Team** for high-resolution Italian elevation data.
- The **QGIS Open Source Community**.
