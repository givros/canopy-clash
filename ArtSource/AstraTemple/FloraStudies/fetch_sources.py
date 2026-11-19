"""Retrieve the 4K CC0 originals and preserve the hashes advertised by Poly Haven."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json

ROOT=Path(__file__).resolve().parent
UA={"User-Agent":"AstraForest-local-asset-authoring/1.0"}

def read(url):
    with urlopen(Request(url,headers=UA),timeout=120) as response:
        return response.read()

def acquire(job):
    path,info=job
    if not path.exists() or hashlib.md5(path.read_bytes()).hexdigest()!=info["md5"]:
        data=read(info["url"])
        if len(data)!=info["size"] or hashlib.md5(data).hexdigest()!=info["md5"]:
            raise RuntimeError("Integrity check failed for "+str(path))
        path.parent.mkdir(exist_ok=True,parents=True)
        temporary=path.with_suffix(path.suffix+".part")
        temporary.write_bytes(data)
        temporary.replace(path)

if __name__=="__main__":
    records=[]
    pending=[]
    for name in ("fern_02","potted_plant_02"):
        catalog=json.loads(read("https://api.polyhaven.com/files/"+name))
        meta=json.loads(read("https://api.polyhaven.com/info/"+name))
        blend=catalog["blend"]["4k"]["blend"]
        files={name+"_4k.blend":blend,**blend["include"]}
        prefix="" if name=="fern_02" else "leaves_"
        for channel in ("arm","nor_dx"):
            info=catalog[prefix+channel]["4k"]["png"]
            files["textures/"+info["url"].rsplit("/",1)[1]]=info
        rec={"asset":name,"title":meta.get("name"),"authors":meta.get("authors"),"site":"https://polyhaven.com/a/"+name,
             "license":"CC0 1.0 Universal","license_url":"https://polyhaven.com/license",
             "source_api":"https://api.polyhaven.com/files/"+name,"resolution":"4K","files":{}}
        for relative,info in files.items():
            path=ROOT/"Originals"/name/relative
            pending.append((path,info))
            rec["files"][relative]={i:info[i] for i in ("url","md5","size")}
        records.append(rec)
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(acquire,pending))
    (ROOT/"Provenance.json").write_text(json.dumps(records,indent=2)+"\n",encoding="utf-8")
    print("Verified",len(pending),"files;",sum(i["size"] for _,i in pending),"bytes")
