"""Fetch full-mesh scans at 2K and construct the original foliage surface textures."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "Textures"
MAPS.mkdir(exist_ok=True)
MODELS = ("rock_face_01", "namaqualand_cliff_01", "rock_moss_set_01")

def download(url):
    request = Request(url, headers={"User-Agent": "GameAstraForest art preparation"})
    with urlopen(request, timeout=80) as stream:
        return stream.read()

def get_file(pair):
    path, entry = pair
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == entry["md5"]:
        return
    data = download(entry["url"])
    assert hashlib.md5(data).hexdigest() == entry["md5"], path
    path.write_bytes(data)

def prepare_scans():
    tasks = []
    for asset in (*MODELS, "japanese_hackberry_bark", "palm_bark"):
        files = json.loads(download("https://api.polyhaven.com/files/" + asset))
        if asset in MODELS:
            source = ROOT / "Sources" / asset
            entry = files["gltf"]["2k"]["gltf"]
            tasks.append((source / (asset + ".gltf"), entry))
            tasks.extend((source / key, dep) for key, dep in entry["include"].items())
        else:
            for channel, dest in (("Diffuse","Color"),("nor_gl","NormalGL"),("Rough","Roughness")):
                tasks.append((MAPS / f"T_{asset}_{dest}.jpg",files[channel]["2k"]["jpg"]))
    with ThreadPoolExecutor(5) as pool:
        list(pool.map(get_file,tasks))

def leaf_materials():
    n = 1024
    rng = np.random.default_rng(411)
    v, u = np.mgrid[0:n,0:n].astype(np.float32)/(n-1)
    v=1-v
    s = (u-.5)*2
    mapped = np.abs(s)
    cloud = gaussian_filter(rng.normal(size=(n,n)),17,mode="wrap")
    cloud = (cloud-cloud.mean()) / cloud.std()
    middle = np.exp(-np.square(s/.022))
    # Veins ascend from the petiole, taper and disappear before the margin.
    field=(v-.16*mapped**.68-.003*np.sin(v*32+mapped*11))*17
    ribs=np.exp(-np.square(np.sin(field*np.pi)/.20))*(1-mapped**1.7)
    tertiary=np.cos((v-.058*mapped)*1000)*.018
    error=rng.normal(0,.035,(n,n))
    tone = 1+.19*ribs+.16*middle+tertiary+.045*cloud+error-.14*mapped**4
    depth=.30*middle+.08*ribs+.012*cloud
    dy,dx=np.gradient(depth)
    nx=-dx*4.4
    ny=dy*5
    nz=np.ones_like(nx)
    inv=1/np.sqrt(nx**2+ny**2+nz**2)
    normal=np.stack([(nx*inv+1)*127.5,(ny*inv+1)*127.5,(nz*inv+1)*127.5],axis=-1)
    Image.fromarray(normal.astype('uint8')).save(MAPS/'T_Botanical_NormalGL.png',optimize=True)
    colors={
        'RainLeaf':(59,94,36),'RainLeafLight':(86,119,45),'RainLeafShade':(39,75,38),
        'PalmBlade':(68,105,38),'MonsteraBlade':(48,88,45),'BractRed':(191,32,30),
        'BractGold':(218,113,27),'LilyLeaf':(83,115,50),'PetalRose':(222,132,164),
        'PetalCream':(241,215,154),'FernBlade':(67,110,44),'LivingStem':(80,104,48)}
    for name,color in colors.items():
        rgb=tone[...,None]*np.array(color)
        rgb+=middle[...,None]*np.array([22,23,8])
        if name=='BractRed':
            rgb+=np.maximum(v-.55,0)[...,None]**1.1*np.array([130,230,28])
        if name=='PetalRose':
            rgb+=np.maximum(1-v,0)[...,None]**1.2*np.array([4,72,46])
        if name=='LilyLeaf':
            x=(u-.5)*2
            y=(v-.5)*2
            radius=np.sqrt(x*x+y*y)
            angle=np.arctan2(y,x)
            rays=np.exp(-np.square(np.sin(10*angle+.82*radius)/(np.maximum(.05,radius)**-.4*.09)))
            offshoot=np.exp(-np.square(np.sin(20*angle+8*radius)/.13))*np.clip(radius-.3,0,1)
            light=1+.22*rays+.09*offshoot+.047*cloud+.08*np.cos(3*angle)*radius+error
            rgb=light[...,None]*np.array(color)
            rgb+=np.exp(-radius**2/.012)[...,None]*np.array([26,27,3])
        Image.fromarray(np.clip(rgb,0,255).astype('uint8')).save(MAPS/f'T_{name}_Color.jpg',quality=94)
    grain=rng.random((n,n))
    sprouts=gaussian_filter(grain,1.12,mode="wrap")
    sprouts=(sprouts-sprouts.mean())/(sprouts.std()+1e-8)
    luma=np.clip(.48+.14*sprouts+.11*cloud,0,1)
    moss=np.stack([34+75*luma**1.5,48+78*luma,24+32*luma],axis=-1)
    Image.fromarray(moss.astype('uint8')).save(MAPS/'T_MossNap_Color.jpg',quality=96)
    # A far-distance twig retains individual leaf silhouettes and the fine negative space
    # between them. The card is used only by authored tree LODs.
    atlas=Image.new('RGBA',(1024,1024),(52,83,37,0))
    draw=ImageDraw.Draw(atlas)
    draw.line([(518,1019),(502,756),(525,405),(514,32)],fill=(83,85,53,255),width=8)
    arng=np.random.default_rng(78)
    for i in range(8):
        for side in (-1,1):
            t=.10+i*.105+(.022 if side==1 else 0)
            start=np.array([512+8*np.sin(t*8),1015-t*915])
            dx=side*(250+131*np.sin(t*3.4))*(1-.32*t)
            dy=-arng.uniform(100,189)
            axis=np.array([dx,dy]);cross=np.array([-dy,dx])/np.linalg.norm(axis)
            width=arng.uniform(57,82)*(1-.32*t)
            outline=[]
            for half in (-1,1):
                path=np.linspace(0,1,12)
                if half==1:path=path[::-1]
                for s in path:
                    c=start+s*axis+cross*(18*np.sin(s*np.pi)*side)
                    q=c+cross*(width*half*np.sin(np.pi*s)**.82)
                    outline.append(tuple(q))
            pigment=arng.uniform(.83,1.21)
            draw.polygon(outline,fill=tuple(int(q*pigment) for q in (62,94,39))+(255,))
            draw.line([tuple(start),tuple(start+axis*.88)],fill=(80,104,48,255),width=3)
            for h in (.18,.34,.50,.66):
                for b in (-1,1):
                    c=start+axis*h
                    dest=c+axis*.15+cross*width*b*.77*np.sin(h*np.pi)
                    draw.line([tuple(c),tuple(dest)],fill=(71,98,43,255),width=2)
    atlas.save(MAPS/'T_CanopySpray_ColorOpacity.png')

if __name__ == "__main__":
    with ThreadPoolExecutor(2) as pool:
        tasks=[pool.submit(function) for function in (prepare_scans,leaf_materials)]
        for task in tasks:
            task.result()
