# -*- coding: utf-8 -*-

import os
from qgis.core import QgsProject, QgsMessageLog, Qgis

# Import new specialized modules
from .downloaders.tinitaly import TinitalyDownloader
from .downloaders.tum import TUMDownloader
from .downloaders.eth import ETHDownloader
from .downloaders.esa import ESADownloader
from .downloaders.meta import MetaDownloader
from .processors.raster import RasterProcessor
from .processors.vector import VectorProcessor
from .processors.lcz_calculator import LCZCalculator
from .utils import get_utm_zone_for_extent, download_file_generic

class DataManager:
    """
    Orchestrator class for managing data download and processing.
    Delegates actual work to specialized downloader and processor classes.
    """
    def __init__(self, iface):
        self.iface = iface
        
        # Initialize internal modules
        self.tinitaly = TinitalyDownloader(self)
        self.tum = TUMDownloader(self)
        self.eth = ETHDownloader(self)
        self.esa = ESADownloader(self)
        self.meta = MetaDownloader(self)
        
        self.raster_proc = RasterProcessor(self)
        self.vector_proc = VectorProcessor(self)
        self.lcz_calc = LCZCalculator(self)

        # Fix PROJ environment for macOS
        self._setup_proj_env()

        # UI Compatibility Attributes
        self.tum_categories = ["LoD1"]

    def _setup_proj_env(self):
        import sys
        if sys.platform == 'darwin':
            from qgis.core import QgsApplication
            proj_path = os.path.join(QgsApplication.pkgDataPath(), "proj")
            if os.path.exists(proj_path):
                os.environ['PROJ_LIB'] = proj_path
                os.environ['PROJ_DATA'] = proj_path
                try:
                    import pyproj
                    pyproj.datadir.set_data_dir(proj_path)
                except:
                    pass

    def get_project_dir(self):
        project_path = QgsProject.instance().fileName()
        return os.path.dirname(project_path) if project_path else None

    def get_download_dir(self, subfolder):
        base_dir = self.get_project_dir()
        if not base_dir: return None
        target_dir = os.path.join(base_dir, "it_lcz_data", subfolder)
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        return target_dir

    # --- Backward compatibility wrappers for Dashboard.py ---

    def calculate_tinitaly_tiles(self, extent, crs_auth_id):
        return self.tinitaly.calculate_tiles(extent, crs_auth_id)

    def download_tinitaly_tile(self, tile_name):
        return self.tinitaly.download_tile(tile_name)

    def download_tum_data(self, category="LoD1", aoi_geometry=None):
        return self.tum.download_data(category, aoi_geometry)

    def fetch_eth_canopy(self, extent, crs_auth_id):
        return self.eth.fetch_canopy(extent, crs_auth_id)

    def fetch_esa_worldcover(self, extent, crs_auth_id):
        return self.esa.fetch_worldcover(extent, crs_auth_id)

    def fetch_meta_hrsl(self, extent, crs_auth_id):
        return self.meta.fetch_hrsl(extent, crs_auth_id)

    def fetch_sentinel2_albedo(self, extent, crs_auth_id, username=None, password=None):
        # Keep original logic for albedo as it's already in its own file
        from .sentinel2_albedo import fetch_albedo_for_aoi
        output_dir = self.get_download_dir("sentinel2_albedo")
        if not output_dir: return False, "Project not saved"
        
        # Check existing
        existing = [f for f in os.listdir(output_dir) if f.endswith('_albedo_10m.tif')]
        if existing: return True, f"Albedo già presente: {existing[0]}"
        
        # WGS84 Extent
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
        source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        w84 = transform.transformBoundingBox(extent)
        bbox = (w84.xMinimum(), w84.yMinimum(), w84.xMaximum(), w84.yMaximum())
        
        # Call with keyword arguments to avoid positional errors
        success, msg, path = fetch_albedo_for_aoi(
            bbox=bbox, 
            output_dir=output_dir, 
            username=username, 
            password=password, 
            log_callback=lambda m: QgsMessageLog.logMessage(m, "IT-LCZ")
        )
        return success, msg

    def get_utm_zone_for_extent(self, extent, crs_auth_id):
        return get_utm_zone_for_extent(extent, crs_auth_id)

    def unify_and_clip_data(self, extent, crs_auth_id, log_callback=None):
        """Orchestrates the unification of all downloaded datasets."""
        base_dir = self.get_project_dir()
        if not base_dir: return False, "Progetto non salvato", []
        
        data_dir = os.path.join(base_dir, "it_lcz_data")
        unified_dir = os.path.join(data_dir, "unified")
        if not os.path.exists(unified_dir): os.makedirs(unified_dir)
        
        target_crs_auth = self.get_utm_zone_for_extent(extent, crs_auth_id)
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
        t_crs = QgsCoordinateReferenceSystem(target_crs_auth)
        s_crs = QgsCoordinateReferenceSystem(crs_auth_id)
        transform = QgsCoordinateTransform(s_crs, t_crs, QgsProject.instance())
        t_extent = transform.transformBoundingBox(extent)
        
        mapping = {
            "tinitaly_tiles": {"pattern": "**/*_s10.tif", "output_name": "dtm_10m.tif", "merge": True, "recursive": True},
            "tum_lod1": {"pattern": "*.json", "output_name": "buildings_lod1.gpkg", "type": "vector"},
            "eth_canopy": {"pattern": "*.tif", "output_name": "canopy_height_10m.tif", "merge": True},
            "esa_worldcover": {"pattern": "*.tif", "output_name": "landuse_10m.tif", "merge": True},
            "meta_hrsl": {"pattern": "meta_hrsl_aoi.tif", "output_name": "population_10m.tif", "merge": False},
            "sentinel2_albedo": {"pattern": "*_albedo_10m.tif", "output_name": "albedo_10m.tif", "merge": False},
        }
        
        output_paths = []
        for folder, config in mapping.items():
            f_path = os.path.join(data_dir, folder)
            if not os.path.exists(f_path): continue
            out_path = os.path.join(unified_dir, config["output_name"])
            if os.path.exists(out_path):
                output_paths.append(out_path); continue
            
            proc = self.vector_proc if config.get("type") == "vector" else self.raster_proc
            if proc.process_dataset(f_path, config, out_path, target_crs_auth, t_extent):
                output_paths.append(out_path)
                
        return (True, f"Processati {len(output_paths)} dataset", output_paths) if output_paths else (False, "Nessun dato", [])

    def load_unified_layers(self, log_callback=None):
        # Keep loading logic here as it interacts closely with QGIS Project
        base_dir = self.get_project_dir()
        if not base_dir: return []
        unified_dir = os.path.join(base_dir, "it_lcz_data", "unified")
        
        from qgis.core import QgsRasterLayer, QgsVectorLayer
        layers = []
        mapping = {
            "dtm_10m.tif": "DTM Tinitaly (10m)", "buildings_lod1.gpkg": "Edifici TUM LoD1",
            "canopy_height_10m.tif": "Altezza Alberi ETH (10m)", "landuse_10m.tif": "Land Use ESA (10m)",
            "population_10m.tif": "Popolazione Meta HRSL", "albedo_10m.tif": "Albedo Sentinel-2 (10m)",
        }
        for fname, dname in mapping.items():
            path = os.path.join(unified_dir, fname)
            if not os.path.exists(path) or QgsProject.instance().mapLayersByName(dname): continue
            lyr = QgsRasterLayer(path, dname) if fname.endswith('.tif') else QgsVectorLayer(path, dname, "ogr")
            if lyr.isValid():
                QgsProject.instance().addMapLayer(lyr)
                layers.append(lyr)
        return layers

    def load_grid_layer(self, grid_path, layer_name=None, log_callback=None):
        """Loads the LCZ grid layer into the QGIS project."""
        if not os.path.exists(grid_path):
            return None
            
        if not layer_name:
            layer_name = os.path.basename(grid_path).replace(".gpkg", "")

        # Check if already loaded
        existing = QgsProject.instance().mapLayersByName(layer_name)
        if existing:
            return existing[0]

        from qgis.core import QgsVectorLayer
        layer = QgsVectorLayer(grid_path, layer_name, "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return layer
        return None

    def create_synthetic_dsm(self, log_callback=None, overwrite=False):
        return self.raster_proc.create_synthetic_dsm(log_callback, overwrite)

    def calculate_svf(self, log_callback=None, search_radius=100, num_sectors=16, canopy_opacity=0.7):
        return self.lcz_calc.calculate_svf(log_callback, search_radius, num_sectors, canopy_opacity)

    def create_lcz_grid(self, extent, crs_auth_id, cell_size=100, log_callback=None):
        return self.vector_proc.create_lcz_grid(extent, crs_auth_id, cell_size, log_callback)

    def use_existing_grid(self, layer, extent, crs_auth_id, log_callback=None):
        return self.vector_proc.use_existing_grid(layer, extent, crs_auth_id, log_callback)

    def calculate_lcz_parameters(self, grid_path=None, parameter_id=None, log_callback=None):
        return self.lcz_calc.calculate_parameters(grid_path, parameter_id, log_callback)

    def _download_file_generic(self, url, local_path, auth=None):
        return download_file_generic(url, local_path, auth)
