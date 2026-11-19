"""Acquire the photographed moss and woodland litter used on the two low-bank zones."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import requests

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'Sources';DEST.mkdir(exist_ok=True)
HEAD={'User-Agent':'AstraForest-local-ground-authoring/1.0'}
def read(url,**kwargs):
    r=requests.get(url,headers=HEAD,timeout=90,**kwargs);r.raise_for_status();return r

def moss():
    items=read('https://ambientcg.com/api/v2/full_json',params={'q':'moss','type':'Material','limit':100,'include':'downloadData'}).json()['foundAssets']
    entry=next(a for a in items if a['assetId']=='Moss001'); choices=entry['downloadFolders']['default']['downloadFiletypeCategories']['zip']['downloads']
    file=next(i for i in choices if i['attribute']=='2K-JPG');r=read(file['downloadLink']);data=r.content
    if len(data)!=file['size']:raise RuntimeError('Partial moss scan')
    with ZipFile(BytesIO(data)) as z:
        names=[]
        for part in ['Color','NormalDX','Roughness']:
            member=next(n for n in z.namelist() if n.endswith('_'+part+'.jpg'))
            target=DEST/('Moss001_'+part+'.jpg');target.write_bytes(z.read(member));names.append(target.name)
    return {'asset':'Moss001','provider':'ambientCG','source':'https://ambientcg.com/view?id=Moss001','license':'CC0','technique':entry['creationMethodName'],'width_m':.45,'files':names,'download':file['downloadLink'],'sha256_archive':hashlib.sha256(data).hexdigest()}

def leaves():
    name='forest_leaves_03';listing=read('https://api.polyhaven.com/files/'+name).json();urls={}
    for key,part in [('Diffuse','Color'),('nor_dx','NormalDX'),('Rough','Roughness')]:
        file=listing[key]['2k']['jpg'];data=read(file['url']).content
        if hashlib.md5(data).hexdigest()!=file['md5']:raise RuntimeError(key)
        (DEST/('ForestLeaves03_'+part+'.jpg')).write_bytes(data);urls[part]={'url':file['url'],'md5':file['md5']}
    return {'asset':name,'provider':'Poly Haven','source':'https://polyhaven.com/a/'+name,'license':'CC0','photography':'Dimitrios Savva','processing':'Rob Tuytel','width_m':2.3,'maps':urls}

with ThreadPoolExecutor(max_workers=2) as workers:
    rows=[f.result() for f in [workers.submit(moss),workers.submit(leaves)]]
(ROOT/'Sources.json').write_text(json.dumps(rows,indent=2))
