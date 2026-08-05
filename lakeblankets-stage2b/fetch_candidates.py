#!/usr/bin/env python3
"""Fetch official ArcGIS candidate lake polygons for Lake Blankets Stage 2B.

This script preserves the exact GeoJSON responses and does not approve features.
"""
from __future__ import annotations
import csv, hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SPECS = {
  "lake-placid": {
    "lake_id": "LB-NY-LAKE-PLACID",
    "name": "Lake Placid",
    "state": "NY",
    "endpoint": "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/9",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GPO_NAME) = 'LAKE PLACID'",
    "candidate_fields": ["OBJECTID","GPO_NAME","GNIS_ID","AreaSqKm","Elevation","Permanent_Identifier","ReachCode","FType","FCode","FCode_Description","GPO_County","GPO_NAME_SOURCE","GPO_HUC"],
    "package_relative_path": "NY/lake-placid",
    "working_crs": "EPSG:32618"
  },
  "lake-mohawk": {
    "lake_id": "LB-NJ-LAKE-MOHAWK",
    "name": "Lake Mohawk",
    "state": "NJ",
    "endpoint": "https://mapsdep.nj.gov/arcgis/rest/services/Features/Hydrography/MapServer/33",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GNIS_NAME) = 'LAKE MOHAWK' OR UPPER(WATERBODY_NAME) = 'LAKE MOHAWK' OR UPPER(FEATURE_NAME) = 'LAKE MOHAWK'",
    "candidate_fields": ["OBJECTID","COMID","PERMANENT_IDENTIFIER","GNIS_ID","GNIS_NAME","AREASQKM","REACHCODE","FTYPE_DISPLAY","HU8","WATERBODY_NAME","FEATURE_ID","FEATURE_NAME","FEATURE_CLASS","LEVELELEV","GLOBALID"],
    "package_relative_path": "NJ/lake-mohawk",
    "working_crs": "EPSG:32618"
  },
  "culver-lake": {
    "lake_id": "LB-NJ-CULVER-LAKE",
    "name": "Culver Lake",
    "state": "NJ",
    "endpoint": "https://mapsdep.nj.gov/arcgis/rest/services/Features/Hydrography/MapServer/33",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GNIS_NAME) LIKE '%CULVER%' OR UPPER(WATERBODY_NAME) LIKE '%CULVER%' OR UPPER(FEATURE_NAME) LIKE '%CULVER%'",
    "candidate_fields": ["OBJECTID","COMID","PERMANENT_IDENTIFIER","GNIS_ID","GNIS_NAME","AREASQKM","REACHCODE","FTYPE_DISPLAY","HU8","WATERBODY_NAME","FEATURE_ID","FEATURE_NAME","FEATURE_CLASS","LEVELELEV","GLOBALID"],
    "package_relative_path": "NJ/culver-lake",
    "working_crs": "EPSG:32618"
  },
  "lake-sunapee": {
    "lake_id": "LB-NH-LAKE-SUNAPEE",
    "name": "Lake Sunapee",
    "state": "NH",
    "endpoint": "https://nhgeodata.unh.edu/hosting/rest/services/Hosted/IWR_WaterResources/FeatureServer/9",
    "object_id_field": "objectid",
    "where_clause": "UPPER(gnis_name) = 'LAKE SUNAPEE' OR UPPER(gnis_name) = 'SUNAPEE LAKE'",
    "candidate_fields": ["objectid","permanent_identifier","fdate","resolution","gnis_id","gnis_name","areasqkm","elevation","reachcode","ftype","fcode"],
    "package_relative_path": "NH/lake-sunapee",
    "working_crs": "EPSG:32618"
  },
  "squam-lake": {
    "lake_id": "LB-NH-SQUAM-LAKE",
    "name": "Squam Lake",
    "state": "NH",
    "endpoint": "https://nhgeodata.unh.edu/hosting/rest/services/Hosted/IWR_WaterResources/FeatureServer/9",
    "object_id_field": "objectid",
    "where_clause": "UPPER(gnis_name) = 'SQUAM LAKE' OR UPPER(gnis_name) = 'BIG SQUAM LAKE'",
    "candidate_fields": ["objectid","permanent_identifier","fdate","resolution","gnis_id","gnis_name","areasqkm","elevation","reachcode","ftype","fcode"],
    "package_relative_path": "NH/squam-lake",
    "working_crs": "EPSG:32619"
  },
  "newfound-lake": {
    "lake_id": "LB-NH-NEWFOUND-LAKE",
    "name": "Newfound Lake",
    "state": "NH",
    "endpoint": "https://nhgeodata.unh.edu/hosting/rest/services/Hosted/IWR_WaterResources/FeatureServer/9",
    "object_id_field": "objectid",
    "where_clause": "UPPER(gnis_name) = 'NEWFOUND LAKE'",
    "candidate_fields": ["objectid","permanent_identifier","fdate","resolution","gnis_id","gnis_name","areasqkm","elevation","reachcode","ftype","fcode"],
    "package_relative_path": "NH/newfound-lake",
    "working_crs": "EPSG:32619"
  },
  "lake-waramaug": {
    "lake_id": "LB-CT-LAKE-WARAMAUG",
    "name": "Lake Waramaug",
    "state": "CT",
    "endpoint": "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/ArcGIS/rest/services/Connecticut_Hydrography_Set/FeatureServer/1",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(LAKE) LIKE '%WARAMAUG%' OR UPPER(NAMED_POLY) LIKE '%WARAMAUG%'",
    "candidate_fields": ["OBJECTID","HYPOLY_COD","HYDRO_POLY","AV_LEGEND","NAMEDP_COD","NAMED_POLY","LAKE_NO","LAKE","ACREAGE","Shape__Area","Shape__Length"],
    "package_relative_path": "CT/lake-waramaug",
    "working_crs": "EPSG:32618"
  },
  "otsego-lake": {
    "lake_id": "LB-NY-OTSEGO-LAKE",
    "name": "Otsego Lake",
    "state": "NY",
    "endpoint": "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/9",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GPO_NAME) = 'OTSEGO LAKE'",
    "candidate_fields": ["OBJECTID","GPO_NAME","GNIS_ID","AreaSqKm","Elevation","Permanent_Identifier","ReachCode","FType","FCode","FCode_Description","GPO_County","GPO_NAME_SOURCE","GPO_HUC"],
    "package_relative_path": "NY/otsego-lake",
    "working_crs": "EPSG:32618"
  },
  "skaneateles-lake": {
    "lake_id": "LB-NY-SKANEATELES-LAKE",
    "name": "Skaneateles Lake",
    "state": "NY",
    "endpoint": "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/9",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GPO_NAME) = 'SKANEATELES LAKE'",
    "candidate_fields": ["OBJECTID","GPO_NAME","GNIS_ID","AreaSqKm","Elevation","Permanent_Identifier","ReachCode","FType","FCode","FCode_Description","GPO_County","GPO_NAME_SOURCE","GPO_HUC"],
    "package_relative_path": "NY/skaneateles-lake",
    "working_crs": "EPSG:32618"
  },
  "lake-wentworth": {
    "lake_id": "LB-NH-LAKE-WENTWORTH",
    "name": "Lake Wentworth",
    "state": "NH",
    "endpoint": "https://nhgeodata.unh.edu/hosting/rest/services/Hosted/IWR_WaterResources/FeatureServer/9",
    "object_id_field": "objectid",
    "where_clause": "UPPER(gnis_name) = 'LAKE WENTWORTH' OR UPPER(gnis_name) = 'WENTWORTH LAKE'",
    "candidate_fields": ["objectid","permanent_identifier","fdate","resolution","gnis_id","gnis_name","areasqkm","elevation","reachcode","ftype","fcode"],
    "package_relative_path": "NH/lake-wentworth",
    "working_crs": "EPSG:32619"
  },
  "bantam-lake": {
    "lake_id": "LB-CT-BANTAM-LAKE",
    "name": "Bantam Lake",
    "state": "CT",
    "endpoint": "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/ArcGIS/rest/services/Connecticut_Hydrography_Set/FeatureServer/1",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(LAKE) = 'BANTAM LAKE' OR UPPER(NAMED_POLY) = 'BANTAM LAKE'",
    "candidate_fields": ["OBJECTID","HYPOLY_COD","HYDRO_POLY","AV_LEGEND","NAMEDP_COD","NAMED_POLY","LAKE_NO","LAKE","ACREAGE","Shape__Area","Shape__Length"],
    "package_relative_path": "CT/bantam-lake",
    "working_crs": "EPSG:32618"
  },
  "twin-lakes": {
    "lake_id": "LB-CT-TWIN-LAKES",
    "name": "Twin Lakes (Washinee / Washining)",
    "state": "CT",
    "endpoint": "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/ArcGIS/rest/services/Connecticut_Hydrography_Set/FeatureServer/1",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(LAKE) LIKE '%TWIN%' OR UPPER(NAMED_POLY) LIKE '%WASHIN%'",
    "candidate_fields": ["OBJECTID","HYPOLY_COD","HYDRO_POLY","AV_LEGEND","NAMEDP_COD","NAMED_POLY","LAKE_NO","LAKE","ACREAGE","Shape__Area","Shape__Length"],
    "package_relative_path": "CT/twin-lakes-washinee-washining",
    "working_crs": "EPSG:32618"
  },
  "caspian-lake": {
    "lake_id": "LB-VT-CASPIAN-LAKE",
    "name": "Caspian Lake",
    "state": "VT",
    "endpoint": "https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRINVENTORYCONSERVATION_WM_NOCACHE/MapServer/4",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GNIS_NAME) = 'CASPIAN LAKE'",
    "candidate_fields": ["OBJECTID","COMID","GNIS_NAME","AREASQKM","REACHCODE","FTYPE"],
    "package_relative_path": "VT/caspian-lake",
    "working_crs": "EPSG:32618"
  },
  "megunticook-lake": {
    "lake_id": "LB-ME-MEGUNTICOOK-LAKE",
    "name": "Megunticook Lake",
    "state": "ME",
    "endpoint": "https://gis.maine.gov/arcgis/rest/services/Hosted/PublicMasterWaters/FeatureServer/1",
    "object_id_field": "fid",
    "where_clause": "UPPER(name) = 'MEGUNTICOOK LAKE' AND wtype = 'Lentic'",
    "candidate_fields": ["fid","name","wtype","reachcode","wbid","mgtwbid","mgtwat1","altname","lat","long","acres","reg"],
    "package_relative_path": "ME/megunticook-lake",
    "working_crs": "EPSG:32619"
  },
  "kezar-lake": {
    "lake_id": "LB-ME-KEZAR-LAKE",
    "name": "Kezar Lake",
    "state": "ME",
    "endpoint": "https://gis.maine.gov/arcgis/rest/services/Hosted/PublicMasterWaters/FeatureServer/1",
    "object_id_field": "fid",
    "where_clause": "UPPER(name) = 'KEZAR LAKE' AND wtype = 'Lentic'",
    "candidate_fields": ["fid","name","wtype","reachcode","wbid","mgtwbid","mgtwat1","altname","lat","long","acres","reg"],
    "package_relative_path": "ME/kezar-lake",
    "working_crs": "EPSG:32619"
  },
  "lake-mahopac": {
    "lake_id": "LB-NY-LAKE-MAHOPAC",
    "name": "Lake Mahopac",
    "state": "NY",
    "endpoint": "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/9",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GPO_NAME) = 'LAKE MAHOPAC' OR UPPER(GPO_NAME) = 'MAHOPAC LAKE'",
    "candidate_fields": ["OBJECTID","GPO_NAME","GNIS_ID","AreaSqKm","Elevation","Permanent_Identifier","ReachCode","FType","FCode","FCode_Description","GPO_County","GPO_NAME_SOURCE","GPO_HUC"],
    "package_relative_path": "NY/lake-mahopac",
    "working_crs": "EPSG:32618"
  },
  "cazenovia-lake": {
    "lake_id": "LB-NY-CAZENOVIA-LAKE",
    "name": "Cazenovia Lake",
    "state": "NY",
    "endpoint": "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/9",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GPO_NAME) = 'CAZENOVIA LAKE'",
    "candidate_fields": ["OBJECTID","GPO_NAME","GNIS_ID","AreaSqKm","Elevation","Permanent_Identifier","ReachCode","FType","FCode","FCode_Description","GPO_County","GPO_NAME_SOURCE","GPO_HUC"],
    "package_relative_path": "NY/cazenovia-lake",
    "working_crs": "EPSG:32618"
  },
  "green-pond": {
    "lake_id": "LB-NJ-GREEN-POND",
    "name": "Green Pond",
    "state": "NJ",
    "endpoint": "https://mapsdep.nj.gov/arcgis/rest/services/Features/Hydrography/MapServer/33",
    "object_id_field": "OBJECTID",
    "where_clause": "UPPER(GNIS_NAME) = 'GREEN POND' OR UPPER(WATERBODY_NAME) = 'GREEN POND' OR UPPER(FEATURE_NAME) = 'GREEN POND'",
    "candidate_fields": ["OBJECTID","COMID","PERMANENT_IDENTIFIER","GNIS_ID","GNIS_NAME","AREASQKM","REACHCODE","FTYPE_DISPLAY","HU8","WATERBODY_NAME","FEATURE_ID","FEATURE_NAME","FEATURE_CLASS","LEVELELEV","GLOBALID"],
    "package_relative_path": "NJ/green-pond",
    "working_crs": "EPSG:32618"
  },
  "pleasant-lake-new-london": {
    "lake_id": "LB-NH-PLEASANT-LAKE",
    "name": "Pleasant Lake (New London)",
    "state": "NH",
    "endpoint": "https://nhgeodata.unh.edu/hosting/rest/services/Hosted/IWR_WaterResources/FeatureServer/9",
    "object_id_field": "objectid",
    "where_clause": "UPPER(gnis_name) = 'PLEASANT LAKE'",
    "candidate_fields": ["objectid","permanent_identifier","fdate","resolution","gnis_id","gnis_name","areasqkm","elevation","reachcode","ftype","fcode"],
    "package_relative_path": "NH/pleasant-lake-new-london",
    "working_crs": "EPSG:32619"
  }
}
OUTPUT = Path(os.environ.get("OUTPUT_ROOT", "network_output"))

def fetch(url: str, params: dict, attempts: int = 4) -> bytes:
    full = url.rstrip('/') + '/query?' + urlencode(params)
    err = None
    for attempt in range(attempts):
        try:
            req = Request(full, headers={"User-Agent": "LakeBlankets-Stage2B/1.2 (+official GIS acquisition)"})
            with urlopen(req, timeout=120) as response:
                return response.read()
        except Exception as exc:
            err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {attempts} attempts: {full}: {err}")

def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary=[]
    for key, spec in SPECS.items():
        out_dir=OUTPUT / key
        out_dir.mkdir(parents=True, exist_ok=True)
        params={
            "where": spec["where_clause"],
            "outFields": ",".join(spec["candidate_fields"]),
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "9",
            "f": "geojson",
        }
        raw=fetch(spec["endpoint"], params)
        (out_dir / "candidate_features.geojson").write_bytes(raw)
        data=json.loads(raw)
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"{key} ArcGIS error: {data['error']}")
        features=data.get("features", [])
        fields=spec["candidate_fields"]
        with (out_dir / "candidate_features.csv").open("w", newline="", encoding="utf-8") as f:
            w=csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for feat in features:
                props=feat.get("properties") or {}
                w.writerow({field: props.get(field) for field in fields})
        metadata={
            "key": key,
            "lake_id": spec["lake_id"],
            "lake_name": spec["name"],
            "endpoint": spec["endpoint"],
            "where_clause": spec["where_clause"],
            "candidate_fields": fields,
            "accessed_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_count": len(features),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "status": "CANDIDATE_REVIEW_REQUIRED",
        }
        (out_dir / "candidate_query_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
        summary.append(metadata)
        print(f"{key}: {len(features)} candidates")
    (OUTPUT / "candidate_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

if __name__ == "__main__":
    main()
