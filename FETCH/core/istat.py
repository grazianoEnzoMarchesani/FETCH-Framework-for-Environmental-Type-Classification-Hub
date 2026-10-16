# -*- coding: utf-8 -*-
"""
FETCH - ISTAT municipal boundaries

Downloads the ISTAT "Confini delle unità amministrative a fini statistici"
(non-generalized shapefiles), caches them at profile level (shared by all
projects) and resolves "Comune (SIGLA)" queries into polygons.

Source: https://www.istat.it/notizia/confini-delle-unita-amministrative-a-fini-statistici/
License: CC BY 4.0 (ISTAT)
"""

import hashlib
import os
import re
import shutil
import unicodedata
import zipfile
import difflib

from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsFeatureRequest, QgsField, QgsFields, QgsGeometry,
    QgsProject, QgsRectangle, QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes
)
from qgis.PyQt.QtCore import QMetaType

from .exceptions import FetchConfigError, FetchDataError
from .utils import download_file_generic, get_target_crs_for_extent

ISTAT_YEAR = 2026
ISTAT_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    f"non_generalizzati/{ISTAT_YEAR}/Limiti0101{ISTAT_YEAR}.zip"
)
ISTAT_CRS = "EPSG:32632"  # WGS84 / UTM 32N, as declared in the shapefile .prj

_COM_NAME = f"Com0101{ISTAT_YEAR}"
_PROV_NAME = f"ProvCM0101{ISTAT_YEAR}"

BOUNDARY_PREFIX = "boundary_city_"
BOUNDARY_LAYER_NAME = "Confini comunali (ISTAT)"


# ---------------------------------------------------------------------------
# Input parsing / name matching (no QGIS dependency)
# ---------------------------------------------------------------------------

def parse_city_input(text):
    """
    Parse "Camerino (MC); Macerata (MC)" into [("Camerino", "MC"), ("Macerata", "MC")].
    Items are separated by ';', newlines, or a comma following a closing bracket.
    The province code is optional here; ambiguity is reported at lookup time.
    """
    items = []
    # Separators: ';', newline, a comma after ')', or just whitespace after ')'
    for chunk in re.split(r"[;\n]|(?<=\))\s*,|(?<=\))\s+(?=[^\s,;])", text or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(.+?)\s*(?:\(\s*([A-Za-z]{2})\s*\))?$", chunk)
        if not m:
            raise FetchConfigError(
                f"Voce non valida: {chunk}",
                f"Voce non valida: «{chunk}». Usa il formato Comune (SIGLA), separando le città con ';'."
            )
        items.append((m.group(1).strip(), (m.group(2) or "").upper() or None))
    if not items:
        raise FetchConfigError("Nessuna città indicata", "Inserisci almeno una città, es. Camerino (MC).")
    return items


def codes_hash(codes):
    """Short, order-independent hash of ISTAT municipality codes (used in file names)."""
    return hashlib.sha1(",".join(sorted(str(c) for c in codes)).encode()).hexdigest()[:8]


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Spaces, apostrophes and hyphens are ignored, so "Castel di Lama", "Castel  di  Lama"
    # and "Casteldilama" all match.
    return re.sub(r"[\s'’‘`\-]+", "", s).casefold()


def _name_keys(*names):
    """Normalized keys for a comune: full name plus each part of 'Bolzano/Bozen'."""
    keys = set()
    for n in names:
        if not n:
            continue
        keys.add(_norm(n))
        for part in n.split("/"):
            keys.add(_norm(part))
    return keys


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def get_cache_dir():
    """Profile-level cache, shared across projects."""
    return os.path.join(QgsApplication.qgisSettingsDirPath(), "FETCH_cache", "istat", str(ISTAT_YEAR))


class IstatBoundaries:
    def __init__(self, cache_dir=None, log=None):
        self.cache_dir = cache_dir or get_cache_dir()
        self.log = log or (lambda msg: None)
        self._index = None

    # -- download & cache ---------------------------------------------------

    def _shp_paths(self):
        return (
            os.path.join(self.cache_dir, _COM_NAME, f"{_COM_NAME}_WGS84.shp"),
            os.path.join(self.cache_dir, _PROV_NAME, f"{_PROV_NAME}_WGS84.shp"),
        )

    def _cache_ready(self):
        for shp in self._shp_paths():
            base = os.path.splitext(shp)[0]
            if not all(os.path.exists(base + ext) for ext in (".shp", ".shx", ".dbf", ".prj")):
                return False
        return True

    def ensure_data(self):
        """Download and extract the ISTAT shapefiles if not cached. Returns (com_shp, prov_shp)."""
        if not self._cache_ready():
            os.makedirs(self.cache_dir, exist_ok=True)
            zip_path = os.path.join(self.cache_dir, f"Limiti0101{ISTAT_YEAR}.zip.part")
            self.log(f"Download confini ISTAT {ISTAT_YEAR} (~100 MB, solo la prima volta)...")
            ok, msg = download_file_generic(ISTAT_URL, zip_path)
            if not ok:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                raise FetchDataError(
                    f"Download ISTAT fallito: {msg}",
                    "Impossibile scaricare i confini ISTAT. Controlla la connessione e riprova.",
                    source="ISTAT"
                )
            try:
                self._extract(zip_path)
            except zipfile.BadZipFile:
                raise FetchDataError(
                    "Archivio ISTAT corrotto", "Il file scaricato da ISTAT non è valido. Riprova.", source="ISTAT"
                )
            finally:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            if not self._cache_ready():
                raise FetchDataError(
                    "Layer comuni/province non trovati nell'archivio ISTAT",
                    "La struttura dell'archivio ISTAT è cambiata: aggiornare il plugin.",
                    source="ISTAT"
                )
        return self._shp_paths()

    def _extract(self, zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                top = member.split("/")[0]
                if top not in (_COM_NAME, _PROV_NAME) or member.endswith("/"):
                    continue
                target = os.path.normpath(os.path.join(self.cache_dir, member))
                if not target.startswith(os.path.normpath(self.cache_dir) + os.sep):
                    continue  # zip-slip guard
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    # -- lookup -------------------------------------------------------------

    def _build_index(self):
        if self._index is not None:
            return self._index
        com_shp, prov_shp = self.ensure_data()

        prov_layer = QgsVectorLayer(prov_shp, "prov", "ogr")
        com_layer = QgsVectorLayer(com_shp, "com", "ogr")
        if not prov_layer.isValid() or not com_layer.isValid():
            raise FetchDataError("Shapefile ISTAT non leggibili", "I dati ISTAT in cache non sono leggibili. Elimina la cartella FETCH_cache/istat e riprova.", source="ISTAT")

        no_geom = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        sigla_by_uts = {f["COD_UTS"]: (f["SIGLA"] or "").upper() for f in prov_layer.getFeatures(no_geom)}

        index = []
        for f in com_layer.getFeatures(no_geom):
            index.append({
                "fid": f.id(),
                "comune": f["COMUNE"],
                "sigla": sigla_by_uts.get(f["COD_UTS"], ""),
                "pro_com": f["PRO_COM_T"],
                "keys": _name_keys(f["COMUNE"], f["COMUNE_A"]),
            })
        self._com_layer = com_layer
        self._index = index
        return index

    def find(self, queries):
        """Resolve [(name, sigla|None)] to unique index entries; raises on unknown/ambiguous."""
        index = self._build_index()
        resolved, seen = [], set()
        for name, sigla in queries:
            key = _norm(name)
            hits = [e for e in index if key in e["keys"] and (not sigla or e["sigla"] == sigla)]
            label = f"{name} ({sigla})" if sigla else name
            if not hits and sigla:
                elsewhere = [e for e in index if key in e["keys"]]
                if elsewhere:
                    options = ", ".join(f"{e['comune']} ({e['sigla']})" for e in elsewhere)
                    raise FetchConfigError(
                        f"Comune non trovato in provincia {sigla}: {name}",
                        f"«{name}» non risulta in provincia di {sigla}. Trovato: {options}."
                    )
            if not hits:
                pool = [e for e in index if not sigla or e["sigla"] == sigla]
                all_names = {e["comune"]: e for e in pool}
                close = difflib.get_close_matches(name, list(all_names), n=3, cutoff=0.7)
                hint = " Forse intendevi: " + ", ".join(f"{c} ({all_names[c]['sigla']})" for c in close) + "?" if close else ""
                raise FetchConfigError(
                    f"Comune non trovato: {label}",
                    f"Comune non trovato: «{label}».{hint}"
                )
            if len(hits) > 1:
                options = ", ".join(f"{e['comune']} ({e['sigla']})" for e in hits)
                raise FetchConfigError(
                    f"Comune ambiguo: {label}",
                    f"«{name}» è ambiguo: {options}. Specifica la sigla di provincia, es. {hits[0]['comune']} ({hits[0]['sigla']})."
                )
            entry = hits[0]
            if entry["pro_com"] not in seen:
                seen.add(entry["pro_com"])
                resolved.append(entry)
        return resolved

    # -- output -------------------------------------------------------------

    def build_aoi(self, text, out_dir):
        """
        Resolve the user's cities and write their polygons to a GeoPackage in the
        optimal metric CRS (same logic as the rest of the plugin).

        The file name carries a hash of the municipality codes, so a different
        selection never overwrites a file that may be loaded in the project.

        Returns dict: path, crs, extent (QgsRectangle in `crs`), names, pro_com.
        """
        entries = self.find(parse_city_input(text))
        names = [f"{e['comune']} ({e['sigla']})" for e in entries]
        codes = [e["pro_com"] for e in entries]
        out_path = os.path.join(out_dir, f"{BOUNDARY_PREFIX}{codes_hash(codes)}.gpkg")

        if os.path.exists(out_path):
            existing = QgsVectorLayer(out_path, "boundary", "ogr")
            if existing.isValid() and existing.featureCount() == len(entries):
                return {"path": out_path, "crs": existing.crs().authid(),
                        "extent": existing.extent(), "names": names, "pro_com": codes}
            os.remove(out_path)

        com_layer = self._com_layer
        src_crs = QgsCoordinateReferenceSystem(ISTAT_CRS)
        geoms = []
        for e in entries:
            f = next(com_layer.getFeatures(QgsFeatureRequest(e["fid"])))
            g = f.geometry()
            if not g.isGeosValid():
                g = g.makeValid()
            geoms.append(g)

        union_extent = QgsRectangle()
        for g in geoms:
            union_extent.combineExtentWith(g.boundingBox())

        target_auth = get_target_crs_for_extent(union_extent, ISTAT_CRS)
        target_crs = QgsCoordinateReferenceSystem(target_auth)
        transform = QgsCoordinateTransform(src_crs, target_crs, QgsProject.instance().transformContext())

        fields = QgsFields()
        fields.append(QgsField("name", QMetaType.QString))
        fields.append(QgsField("sigla", QMetaType.QString))
        fields.append(QgsField("pro_com", QMetaType.QString))
        fields.append(QgsField("source", QMetaType.QString))

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.fileEncoding = "UTF-8"
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        writer = QgsVectorFileWriter.create(
            out_path, fields, QgsWkbTypes.MultiPolygon, target_crs,
            QgsProject.instance().transformContext(), opts
        )
        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise FetchDataError(
                f"Scrittura {out_path} fallita: {writer.errorMessage()}",
                "Impossibile scrivere il layer dei confini nella cartella del progetto.",
                source="ISTAT"
            )

        out_extent = QgsRectangle()
        for e, g in zip(entries, geoms):
            g = QgsGeometry(g)
            if g.transform(transform) != 0:
                raise FetchDataError(f"Riproiezione fallita per {e['comune']}", f"Riproiezione dei confini di {e['comune']} fallita.", source="ISTAT")
            g.convertToMultiType()
            feat = QgsFeature(fields)
            feat.setGeometry(g)
            feat.setAttributes([e["comune"], e["sigla"], e["pro_com"], f"ISTAT {ISTAT_YEAR} (non generalizzati)"])
            writer.addFeature(feat)
            out_extent.combineExtentWith(g.boundingBox())
        del writer

        return {"path": out_path, "crs": target_auth, "extent": out_extent, "names": names, "pro_com": codes}
