#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
from pyproj import Geod
from requests.adapters import HTTPAdapter
from shapely.geometry import shape
from urllib3.util.retry import Retry

ACRES_PER_SQ_M = 1 / 4046.8564224
GEOD = Geod(ellps="WGS84")


def session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "LakeBlankets-Stage2B/1.0 (+official GIS QA)"})
    return s


def query_geojson(s: requests.Session, spec: dict[str, Any]) -> tuple[bytes, dict[str, Any], str]:
    url = spec["endpoint"].rstrip("/") + "/query"
    params = {
        "where": spec["where"],
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "geometryPrecision": "9",
        "resultRecordCount": "2000",
        "f": "geojson",
    }
    r = s.get(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(json.dumps(data["error"], indent=2))
    return r.content, data, r.url


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    _, _, meters = GEOD.inv(lon1, lat1, lon2, lat2)
    return abs(meters) / 1000.0


def geometry_metrics(feature: dict[str, Any], working_crs: str) -> dict[str, Any]:
    geom = shape(feature["geometry"])
    gdf = gpd.GeoDataFrame([{"geometry": geom}], crs="EPSG:4326")
    projected = gdf.to_crs(working_crs)
    area_acres = float(projected.geometry.area.iloc[0] * ACRES_PER_SQ_M)
    centroid = projected.geometry.centroid.iloc[0]
    centroid_wgs = gpd.GeoSeries([centroid], crs=working_crs).to_crs("EPSG:4326").iloc[0]
    return {
        "geometry_area_acres": area_acres,
        "centroid_lon": float(centroid_wgs.x),
        "centroid_lat": float(centroid_wgs.y),
        "geom_type": geom.geom_type,
        "part_count": len(geom.geoms) if hasattr(geom, "geoms") else 1,
        "interior_ring_count": sum(len(poly.interiors) for poly in geom.geoms) if geom.geom_type == "MultiPolygon" else (len(geom.interiors) if geom.geom_type == "Polygon" else 0),
    }


def score_candidate(spec: dict[str, Any], metrics: dict[str, Any]) -> dict[str, float]:
    expected_area = spec.get("expected_area_acres")
    if expected_area and expected_area > 0:
        area_rel_error = abs(metrics["geometry_area_acres"] - expected_area) / expected_area
    else:
        area_rel_error = 0.0
    expected_centroid = spec.get("expected_centroid_lonlat")
    if expected_centroid:
        distance_km = haversine_km(
            metrics["centroid_lon"], metrics["centroid_lat"],
            expected_centroid[0], expected_centroid[1],
        )
    else:
        distance_km = 0.0
    score = area_rel_error * 100.0 + min(distance_km, 500.0) / 10.0
    return {"area_relative_error": area_rel_error, "centroid_distance_km": distance_km, "selection_score": score}


def main() -> int:
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "stage2b/config.json")
    output_root = Path(sys.argv[2] if len(sys.argv) > 2 else "candidate-output")
    output_root.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    s = session()

    all_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for index, spec in enumerate(config["lakes"], start=1):
        lake_dir = output_root / spec["lake_id"]
        lake_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{len(config['lakes'])}] {spec['lake_name']} ({spec['lake_id']})", flush=True)
        try:
            raw, data, query_url = query_geojson(s, spec)
            (lake_dir / "candidate_features.geojson").write_bytes(raw)
            feature_summaries = []
            for feature in data.get("features", []):
                props = feature.get("properties") or {}
                metrics = geometry_metrics(feature, spec["working_crs"])
                score = score_candidate(spec, metrics)
                object_id = props.get(spec["object_id_field"])
                summary = {
                    "lake_id": spec["lake_id"],
                    "lake_name": spec["lake_name"],
                    "state": spec["state"],
                    "object_id_field": spec["object_id_field"],
                    "object_id": object_id,
                    **metrics,
                    **score,
                    "properties": props,
                }
                feature_summaries.append(summary)
                row = {k: v for k, v in summary.items() if k != "properties"}
                for key in [
                    "GPO_NAME", "GNIS_Name", "GNIS_NAME", "gnis_name", "name", "NAME",
                    "AreaSqKm", "AREASQKM", "areasqkm", "ACREAGE", "acres",
                    "GPO_County", "HU8", "GPO_HUC", "NAMED_POLY", "LAKE", "wtype", "wbid", "mgtwbid",
                    "permanent_identifier", "PERMANENT_IDENTIFIER", "GNIS_ID", "gnis_id",
                ]:
                    if key in props:
                        row[key] = props.get(key)
                all_rows.append(row)
            feature_summaries.sort(key=lambda x: x["selection_score"])
            result = {
                "lake_id": spec["lake_id"],
                "lake_name": spec["lake_name"],
                "query_url": query_url,
                "query_where": spec["where"],
                "expected_area_acres": spec.get("expected_area_acres"),
                "expected_centroid_lonlat": spec.get("expected_centroid_lonlat"),
                "expected_feature_count": spec.get("expected_feature_count", 1),
                "selection_notes": spec.get("selection_notes"),
                "candidate_count": len(feature_summaries),
                "candidates": feature_summaries,
                "status": "QUERY_COMPLETE",
            }
            (lake_dir / "candidate_summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            results.append(result)
        except Exception as exc:
            result = {
                "lake_id": spec["lake_id"],
                "lake_name": spec["lake_name"],
                "status": "ERROR",
                "error": repr(exc),
            }
            (lake_dir / "candidate_error.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            results.append(result)
            print(f"ERROR: {exc!r}", flush=True)
        time.sleep(0.15)

    fieldnames = []
    for row in all_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if fieldnames:
        with (output_root / "all_candidates.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
    (output_root / "candidate_discovery_report.json").write_text(json.dumps({"results": results}, indent=2, default=str), encoding="utf-8")

    error_count = sum(1 for r in results if r["status"] == "ERROR")
    empty_count = sum(1 for r in results if r.get("candidate_count") == 0)
    print(f"Completed: {len(results)} lakes; errors={error_count}; empty={empty_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
