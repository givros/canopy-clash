"""Retrieve and verify the original CC0 sky panorama and ground texture maps."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import requests
import json
root=Path(__file__).resolve().parents[1]/"Terrain"
def download(spec,filename):
    save=root/filename
    if save.exists() and save.stat().st_size==spec["size"]:return filename
    size=spec["size"]
    def part(start):
        last=min(start+1048575,size-1)
        for retry in range(5):
            try:
                res=requests.get(spec["url"],params={"bytes":start,"v":retry},headers={"User-Agent":"AstraForest/1.0","Range":f"bytes={start}-{last}"},timeout=18)
                res.raise_for_status()
                if len(res.content)==last-start+1:return res.content
                raise IOError("Incomplete byte range")
            except (requests.RequestException,IOError):
                if retry==4:raise
    with ThreadPoolExecutor(6) as pool:blob=b"".join(pool.map(part,range(0,size,1048576)))
    if hashlib.md5(blob).hexdigest()!=spec["md5"]:raise IOError("Checksum mismatch "+filename)
    save.write_bytes(blob)
    return filename
def info(slug):return requests.get("https://api.polyhaven.com/files/"+slug,timeout=20).json()
if __name__=="__main__":
    sky=info("kloofendal_48d_partly_cloudy_puresky")["hdri"]["4k"]["hdr"]
    ground=info("forest_ground_04")
    with ThreadPoolExecutor(3) as pool:
        result=list(pool.map(lambda item:download(*item),[(sky,"T_KloofendalDaylight.hdr"),(ground["nor_dx"]["4k"]["jpg"],"T_forest_ground_04_Normal.jpg"),(ground["Rough"]["4k"]["jpg"],"T_forest_ground_04_Rough.jpg")]))
    print(result)
    (root/"sky_source.json").write_text(json.dumps({"license":"CC0","asset":"https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky","original":sky},indent=2))
