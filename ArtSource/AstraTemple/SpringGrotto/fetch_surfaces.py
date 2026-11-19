"""Full PBR surface photographs for the spring passage, from Poly Haven (CC0)."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

FOLDER=Path(__file__).resolve().parent/"Textures"
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"Astra Forest environment preparation"}),timeout=60) as response:
        return response.read()
def save(task):
    filename,entry=task
    if filename.exists() and hashlib.md5(filename.read_bytes()).hexdigest()==entry["md5"]:return
    data=fetch(entry["url"])
    assert hashlib.md5(data).hexdigest()==entry["md5"]
    filename.write_bytes(data)
if __name__=="__main__":
    FOLDER.mkdir(exist_ok=True)
    jobs=[]
    for key,group in (("rock_face_04","JointedRock"),("cliff_side","SedimentaryBand")):
        record=json.loads(fetch("https://api.polyhaven.com/files/"+key))
        for kind,role in (("Diffuse","Color"),("nor_gl","NormalGL"),("Rough","Roughness")):
            jobs.append((FOLDER/("T_"+group+"_"+role+".jpg"),record[kind]["2k"]["jpg"]))
    with ThreadPoolExecutor(5) as pool:list(pool.map(save,jobs))
