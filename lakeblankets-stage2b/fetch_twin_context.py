#!/usr/bin/env python3
"""Fetch all Connecticut hydrography polygons intersecting the Twin Lakes review envelope."""
from __future__ import annotations
import hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = Path(os.environ.get("OUTPUT_ROOT", "network_output")) / "twin-lakes-context"
ENDPOINT = "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/ArcGIS/rest/services/Connecticut_Hydrography_Set/FeatureServer/1"
ENVELOPE = "-73.455,42.006,-73.407,42.052"

def fetch(params: dict) -> bytes:
    url = ENDPOINT + "/query?" + urlencode(params)
    last = None
    for attempt in range(5):
        try:
            req = Request(url, headers={"User-Agent":"LakeBlankets-Stage2B/1.2 (+official GIS context review)"})
            with urlopen(req, timeout=150) as response:
                return response.read()
        except Exception as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Twin Lakes context request failed: {last}")

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = fetch({
        "where":"1=1",
        "geometry":ENVELOPE,
        "geometryType":"esriGeometryEnvelope",
        "inSR":"4326",
        "spatialRel":"esriSpatialRelIntersects",
        "outFields":"*",
        "returnGeometry":"true",
        "outSR":"4326",
        "geometryPrecision":"9",
        "f":"geojson",
    })
    data = json.loads(raw)
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"]))
    (OUT / "context_features.geojson").write_bytes(raw)
    meta = {
        "lake_id":"LB-CT-TWIN-LAKES",
        "endpoint":ENDPOINT,
        "review_envelope_wgs84":ENVELOPE,
        "candidate_count":len(data.get("features", [])),
        "accessed_utc":datetime.now(timezone.utc).isoformat(),
        "response_sha256":hashlib.sha256(raw).hexdigest(),
        "purpose":"Identify adjacent unnamed or differently named polygons that may belong to Washinee or Washining."
    }
    (OUT / "context_query_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
