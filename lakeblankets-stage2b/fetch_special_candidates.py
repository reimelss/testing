#!/usr/bin/env python3
"""Fetch the two Stage 2B candidate cases requiring expanded source queries."""
from __future__ import annotations
import csv, hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUTPUT = Path(os.environ.get("OUTPUT_ROOT", "network_output"))
SPECS = {
    "twin-lakes-washinee-washining": {
        "lake_id": "LB-CT-TWIN-LAKES",
        "lake_name": "Twin Lakes (Washinee / Washining)",
        "endpoint": "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/ArcGIS/rest/services/Connecticut_Hydrography_Set/FeatureServer/1",
        "where": "UPPER(LAKE) LIKE '%WASHIN%'",
        "fields": ["OBJECTID","HYPOLY_COD","HYDRO_POLY","AV_LEGEND","NAMEDP_COD","NAMED_POLY","LAKE_NO","LAKE","ACREAGE","Shape__Area","Shape__Length"],
    },
    "stockbridge-bowl-lake-mahkeenac": {
        "lake_id": "LB-MA-STOCKBRIDGE-BOWL-LAKE-MAHKEENAC",
        "lake_name": "Stockbridge Bowl / Lake Mahkeenac",
        "endpoint": "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/MassDEP_Hydrography/FeatureServer/16",
        "where": "UPPER(NAME) LIKE '%STOCKBRIDGE%' OR UPPER(NAME) LIKE '%MAHKEENAC%'",
        "fields": ["*"],
    },
}

def fetch(endpoint: str, params: dict, attempts: int = 5) -> bytes:
    url = endpoint.rstrip('/') + '/query?' + urlencode(params)
    last = None
    for n in range(attempts):
        try:
            req = Request(url, headers={"User-Agent":"LakeBlankets-Stage2B/1.2 (+official GIS acquisition)"})
            with urlopen(req, timeout=150) as response:
                return response.read()
        except Exception as exc:
            last = exc
            time.sleep(2 ** n)
    raise RuntimeError(f"Fetch failed: {url}: {last}")

def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for key, spec in SPECS.items():
        out = OUTPUT / key
        out.mkdir(parents=True, exist_ok=True)
        raw = fetch(spec["endpoint"], {
            "where": spec["where"],
            "outFields": ",".join(spec["fields"]),
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "9",
            "f": "geojson",
        })
        data = json.loads(raw)
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"{key}: {json.dumps(data['error'])}")
        features = data.get("features", [])
        (out / "candidate_features.geojson").write_bytes(raw)
        if features:
            fields = sorted({k for feature in features for k in (feature.get("properties") or {}).keys()})
        else:
            fields = []
        with (out / "candidate_features.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if fields:
                writer.writeheader()
                for feature in features:
                    writer.writerow({k:(feature.get("properties") or {}).get(k) for k in fields})
        meta = {
            "key": key,
            "lake_id": spec["lake_id"],
            "lake_name": spec["lake_name"],
            "endpoint": spec["endpoint"],
            "where_clause": spec["where"],
            "accessed_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_count": len(features),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "status": "CANDIDATE_REVIEW_REQUIRED",
        }
        (out / "candidate_query_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"{key}: {len(features)} candidates")

if __name__ == "__main__":
    main()
