# -*- coding: utf-8 -*-

import os
import logging
from typing import Optional, Tuple, List, Dict
from datetime import datetime
from pathlib import Path

from .base import BaseDownloader

# Configure logging
logger = logging.getLogger(__name__)

class StacAssetWrapper:
    def __init__(self, asset_dict):
        self.href = asset_dict.get("href")

class StacItemWrapper:
    def __init__(self, feature):
        self.id = feature.get("id")
        self.properties = feature.get("properties", {})
        self.geometry = feature.get("geometry", {})
        self.assets = {k: StacAssetWrapper(v) for k, v in feature.get("assets", {}).items()}

class Sentinel2Downloader(BaseDownloader):
    """
    Downloader for Sentinel-2 Level-2A imagery from the Copernicus Data Space Ecosystem (CDSE).
    Uses EODAG for searching and downloading.
    """
    
    PRODUCT_TYPE = "S2_MSI_L2A"
    
    def __init__(self, data_manager):
        super().__init__(data_manager)
        self.username = os.getenv("CDSE_USERNAME", "")
        self.password = os.getenv("CDSE_PASSWORD", "")

    def _setup_eodag(self) -> Optional[object]:
        """Sets up EODAG with CDSE credentials."""
        try:
            from eodag import EODataAccessGateway
            
            if not self.username or not self.password:
                self.log("Credenziali CDSE mancanti (CDSE_USERNAME / CDSE_PASSWORD).", level=2)
                return None
                
            os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME"] = self.username
            os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD"] = self.password
            
            dag = EODataAccessGateway()
            dag.set_preferred_provider("cop_dataspace")
            return dag
        except Exception as e:
            self.log(f"EODAG non disponibile o backend incompatibile ({e}).", level=1) # Qgis.Warning is 1
            return None

    def search_products(
        self,
        bbox: Tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        max_cloud_cover: int = 10
    ) -> List:
        """
        Search for Sentinel-2 products.
        bbox: (min_lon, min_lat, max_lon, max_lat)
        """
        dag = self._setup_eodag()
        if not dag:
            self.log("Avvio fallback su AWS STAC API...", level=1)
            return self._search_aws_stac(bbox, start_date, end_date, max_cloud_cover)
        
        search_criteria = {
            "productType": self.PRODUCT_TYPE,
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
        
        self.log(f"Ricerca Sentinel-2 ({start_date} - {end_date}, Cloud < {max_cloud_cover}%)...")
        try:
            results = dag.search_all(**search_criteria)
        except Exception as e:
            self.log(f"Errore durante la ricerca EODAG: {e}. Avvio fallback su AWS STAC API...", level=1)
            return self._search_aws_stac(bbox, start_date, end_date, max_cloud_cover)
        
        if not results:
            self.log("Nessun prodotto trovato per i criteri specificati con CDSE (EODAG). Avvio fallback su AWS STAC API...", level=1) # Qgis.Warning is 1
            return self._search_aws_stac(bbox, start_date, end_date, max_cloud_cover)
            
        self.log(f"Trovati {len(results)} prodotti con EODAG.")
        return list(results)

    def _search_aws_stac(self, bbox, start_date, end_date, max_cloud_cover):
        """Fallback method to search Sentinel-2 L2A via AWS Earth Search STAC API using plain requests."""
        try:
            import requests
            
            start_dt = f"{start_date}T00:00:00Z"
            end_dt = f"{end_date}T23:59:59Z"
            
            payload = {
                "collections": ["sentinel-2-l2a"],
                "bbox": list(bbox),
                "datetime": f"{start_dt}/{end_dt}",
                "query": {"eo:cloud_cover": {"lt": max_cloud_cover}},
                "limit": 30
            }
            
            response = requests.post("https://earth-search.aws.element84.com/v1/search", json=payload)
            response.raise_for_status()
            
            features = response.json().get("features", [])
            items = [StacItemWrapper(f) for f in features]
            
            if not items:
                self.log("⚠ Albedo: Nessun prodotto Sentinel-2 trovato per l'area selezionata neanche su AWS.", level=1)
                return []
                
            self.log(f"Trovati {len(items)} prodotti tramite AWS STAC Fallback.")
            return items
        except Exception as e:
            self.log(f"Errore durante fallback AWS: {e}", level=2)
            return []

    def download_product(self, product, download_dir: str) -> Optional[Path]:
        """Downloads a specific product or configures a COG manifest for AWS fallback."""
        # Ensure download directory exists
        path = Path(download_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        # Intercept AWS STAC items (fallback)
        if hasattr(product, 'assets') and hasattr(product, 'id'):
            return self._download_aws_product(product, path)
            
        # Standard CDSE EODAG logic
        dag = self._setup_eodag()
        if not dag: return None
        
        self.log(f"Download prodotto Sentinel-2: {product.properties.get('id', 'Unknown')}")
        
        # Disable parallel downloads to avoid issues in QGIS
        os.environ['EODAG__COP_DATASPACE__DOWNLOAD__OUTPUTS_EXTENSION'] = '.zip'
        os.environ['EODAG__COP_DATASPACE__DOWNLOAD__EXTRACT'] = 'true'
        
        try:
            downloaded_path = dag.download(
                product,
                outputs_prefix=str(path),
                extract=True
            )
            if isinstance(downloaded_path, str):
                downloaded_path = Path(downloaded_path)
            return downloaded_path
        except Exception as e:
            self.log(f"Errore durante il download Sentinel-2: {e}", level=2)
            return None

    def _download_aws_product(self, item, download_dir: Path) -> Optional[Path]:
        """Creates a virtual local product pointing to AWS COGs."""
        product_dir = download_dir / item.id
        product_dir.mkdir(parents=True, exist_ok=True)
        
        self.log(f"Configurazione prodotto virtuale Sentinel-2 (AWS STAC COG): {item.id}")
        
        # Map Earth Search STAC assets to band names
        needed_assets = {
            "blue": "B02",
            "red": "B04",
            "nir": "B08",
            "swir16": "B11",
            "swir22": "B12",
            "scl": "SCL"
        }
        
        import json
        manifest_path = product_dir / "aws_stac_manifest.json"
        
        manifest = {}
        for asset_key, band_name in needed_assets.items():
            if asset_key in item.assets:
                manifest[band_name] = item.assets[asset_key].href
            elif asset_key == "nir":
                if "nir08" in item.assets: manifest[band_name] = item.assets["nir08"].href
                elif "nir09" in item.assets: manifest[band_name] = item.assets["nir09"].href
                
        # Validate all required bands are present
        if len(manifest) < len(needed_assets):
            self.log(f"Errore: Il prodotto STAC {item.id} non contiene tutte le bande necessarie.", level=2)
            return None
            
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
            
        return product_dir

    def get_optimal_products(self, products, bbox, max_products=1) -> List:
        """Optimal tile selection logic extracted from sentinel2_albedo.py."""
        if not products: return []
        
        try:
            from shapely.geometry import box, shape
            aoi_shape = box(*bbox)
            
            # Calculate coverage and sort
            products_list = list(products)
            for prod in products_list:
                try:
                    prod_geom = shape(prod.geometry)
                    coverage_pct = prod_geom.intersection(aoi_shape).area / aoi_shape.area
                    prod.properties['_coverage_pct'] = coverage_pct
                except Exception:
                    prod.properties['_coverage_pct'] = 0.0

            # Sort descending by coverage, ascending by cloud cover
            products_list.sort(key=lambda x: (-x.properties.get('_coverage_pct', 0.0), x.properties.get('cloudCover', x.properties.get('eo:cloud_cover', 100))))

            selected = []
            current_coverage = None
            for prod in products_list:
                if prod.properties.get('_coverage_pct', 0) == 0: continue
                
                try:
                    prod_geom = shape(prod.geometry)
                    if current_coverage is None:
                        selected.append(prod)
                        current_coverage = prod_geom.intersection(aoi_shape)
                    else:
                        missing_coverage = aoi_shape.difference(current_coverage)
                        if missing_coverage.area > (aoi_shape.area * 0.001):
                            if prod_geom.intersects(missing_coverage):
                                if prod_geom.intersection(missing_coverage).area > (aoi_shape.area * 0.001):
                                    selected.append(prod)
                                    current_coverage = current_coverage.union(prod_geom).intersection(aoi_shape)
                        else:
                            break
                except Exception:
                    selected.append(prod)
            
            return selected if selected else products_list[:max_products]
            
        except ImportError:
            # Fallback to simple cloud cover sort
            products_list = sorted(products, key=lambda x: x.properties.get('cloudCover', x.properties.get('eo:cloud_cover', 100)))
            return products_list[:max_products]
