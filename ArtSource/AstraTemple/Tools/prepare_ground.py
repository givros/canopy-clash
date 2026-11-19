"""Fetch original CC0 ground maps at the chosen four-kilopixel authoring resolution."""
import concurrent.futures
import json
from pathlib import Path
import requests

folder = Path(__file__).resolve().parents[1] / "Terrain"
sources = {}
headers = {"User-Agent": "AstraForest/1.0 local Unreal environment authoring"}

def fetch(asset):
    response = requests.get(f"https://api.polyhaven.com/files/{asset}", headers=headers, timeout=35)
    response.raise_for_status()
    data = response.json()
    records = {}
    for suffix, keys in [("Color", ("Diffuse","diff","color")), ("Normal", ("nor_dx",)), ("Rough", ("Rough","rough"))]:
        variant = next(data[key]["4k"] for key in keys if key in data)
        extension = next(key for key in ("jpg", "png", "exr") if key in variant)
        url = variant[extension]["url"]
        file = folder / f"T_{asset}_{suffix}.{extension}"
        if not file.exists():
            for attempt in range(5):
                try:
                    content = requests.get(url, params={"download":attempt}, headers=headers, timeout=50)
                    content.raise_for_status()
                    blob=content.content
                    if len(blob)!=variant[extension]["size"]:raise IOError("Incomplete texture download")
                    file.write_bytes(blob)
                    break
                except (requests.RequestException,IOError):
                    if attempt==4:raise
        records[suffix] = {"filename": file.name, "url": url}
    return asset, records

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    sources.update(pool.map(fetch, ["forest_ground_04", "mossy_rock", "brown_mud_rocks_01","leafy_grass","mossy_sandstone"]))
(folder / "ground_sources.json").write_text(json.dumps({"license":"CC0", "source":"https://polyhaven.com/license", "assets":sources}, indent=2))
