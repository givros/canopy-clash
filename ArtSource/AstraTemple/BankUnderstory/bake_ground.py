"""Bake a seamless damp-floor PBR tile and the low-bank mask in native world metres."""
from pathlib import Path
import math
import json
import random
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates,gaussian_filter

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'Tools'))
import valley

def smooth(lo,hi,v):
    t=np.clip((v-lo)/(hi-lo),0,1);return t*t*(3-2*t)

def extract(name,slot,repeat,u,v):
    with Image.open(ROOT/'Sources'/f'{name}_{slot}.jpg') as im:
        mode='L' if slot=='Roughness' else 'RGB'
        sub=im.convert(mode).resize((u.shape[1]//repeat,u.shape[1]//repeat),Image.Resampling.LANCZOS)
        source=np.asarray(sub,dtype=np.float32)/255
    n=source.shape[0];coords=[(v*repeat*n)%n,(u*repeat*n)%n]
    if source.ndim==2:return map_coordinates(source,coords,order=1,mode='grid-wrap')
    return np.stack([map_coordinates(source[:,:,i],coords,order=1,mode='grid-wrap') for i in range(3)],axis=-1)

def tile():
    n=2048;v,u=np.mgrid[0:n,0:n].astype(np.float32)/n;t=math.tau
    # A single 4.6 m square contains eight 57.5 cm repeats of the 45 cm moss
    # scan and two true 2.3 m repeats of litter. Both layers remain periodic.
    litter_albedo=extract('ForestLeaves03','Color',2,u,v)
    leaf=litter_albedo@np.array([.23,.66,.11],np.float32)
    # Fine bright leaf edges cross a shared moss bed. Broad stripes baked into a
    # repeating tile would remain conspicuous on the nearly vertical bank.
    noise=np.random.default_rng(812).normal(size=(128,128)).astype(np.float32)
    noise=gaussian_filter(noise,3.,mode='wrap');noise/=max(.001,noise.std())
    grain=map_coordinates(noise,[v*128,u*128],order=1,mode='grid-wrap')
    mix=np.clip(.72+.051*grain-.33*smooth(.18,.39,leaf),.35,.81)[:,:,None]
    def combined(slot):
        moss=extract('Moss001',slot,8,u,v)
        leaves=extract('ForestLeaves03',slot,2,u,v)
        if slot=='Color':
            moss=np.power(moss,2.2)*[.30,.48,.28];leaves=np.power(leaves,2.2)*[.77,.80,.65]
            return np.power(leaves*(1-mix)+moss*mix,1/2.2)
        if slot=='NormalDX':
            norm=(leaves*2-1)*(1-mix)+(moss*2-1)*mix
            return norm/(np.linalg.norm(norm,axis=2,keepdims=True)+.00001)*.5+.5
        rough=leaves*(1-mix[:,:,0])+moss*mix[:,:,0]
        return np.clip(rough*(.86-.08*mix[:,:,0])+.04,.36,.94)
    rgba=np.dstack([combined('Color'),combined('Roughness')]);normal=combined('NormalDX')
    for name,arr in [('T_DampForest_ColorRough',rgba),('T_DampForest_NormalDX',normal)]:
        Image.fromarray(np.uint8(np.clip(arr*255+.5,0,255))).save(ROOT/(name+'.png'),compress_level=2)

def mask(x,y):
    # Half-plane and elliptical distances bound the correction to the eastern
    # bank and the shoulders between the spawn and first approach turn.
    ed=((x+24)/43)**2+((y-51.0)/14.75)**2
    bank=1-smooth(.66,1.12,ed)
    close=0
    for (ax,ay,ra),(bx,by,rb) in zip(SHOULDER,SHOULDER[1:]):
        dx,dy=bx-ax,by-ay;t=np.clip(((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy),0,1)
        dist=np.hypot(x-ax-t*dx,y-ay-t*dy);width=ra+(rb-ra)*t
        close=np.maximum(close,1-smooth(width*.65,width,dist))
    area=np.maximum(bank,close)
    route=np.full(x.shape,1000.,dtype=np.float32)
    for path in valley.TRAILS.values():
        for a,b in zip(path,path[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];t=np.clip(((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy),0,1)
            route=np.minimum(route,np.hypot(x-a[0]-t*dx,y-a[1]-t*dy))
    heights=np.fromfile(ROOT.parent/'Terrain'/'ValleyHeights.f32',np.float32).reshape(505,505)/100
    uv=[(y+201.6)/.8,(x+153.6)/.8]
    z=map_coordinates(heights,uv,order=1,mode='nearest')
    # Preserve the shrine paving and its thresholds in its exact local frame.
    ang=math.radians(-84);px=((x+27)*math.cos(ang)+(y-54)*math.sin(ang))/.68;py=(-(x+27)*math.sin(ang)+(y-54)*math.cos(ang))/.68
    shrine=smooth(.05,1.25,np.maximum(np.maximum(-1.7-px,px-8.20),np.abs(py)-5.22))
    rocky=np.asarray(Image.open(ROOT.parent/'Terrain'/'T_ValleyZones.png'))[:,:,0]/255
    rock=map_coordinates(rocky,uv,order=1,mode='nearest')
    fine=np.sin(.813*x+.37*y)*np.sin(.48*y-.16*x)
    broad=.5+.22*np.sin(.145*x+.19*y)+.18*np.sin(.23*x-.11*y)+.10*np.sin(.37*y+.64*np.sin(.31*x))
    bounds=smooth(0,1.5,x+101)*smooth(0,1.5,19-x)*smooth(0,1.5,y)*smooth(0,1.5,75-y)
    w=area*smooth(1.55,3.45,route+.17*fine)*smooth(.14,1.13,z)*shrine*(1-smooth(.42,.77,rock))*(1-smooth(12,20,z))*bounds
    return np.clip(w*(.78+.175*broad+.035*fine),0,1),np.clip(.25+.65*broad+.065*fine,0,1)

SHOULDER=[(-90,15,6.5),(-82,19,10.6),(-73,27,12.7),(-62,35,12.1),(-52,43,12.9),(-44,49,10.2)]

def footprint():
    n=512;y,x=np.mgrid[0:n,0:n].astype(np.float32)
    x=-101+(x+.5)*120/n;y=0+(y+.5)*75/n
    w,b=mask(x,y)
    w[:4]=0;w[-4:]=0;w[:,:4]=0;w[:,-4:]=0
    noise=gaussian_filter(np.random.default_rng(339).normal(size=(128,128)),3.5,mode='reflect')
    warp=map_coordinates(noise,[y/75*127,(x+101)/120*127],order=1,mode='nearest');warp=np.clip(.5+.22*warp/warp.std(),.02,.98)
    im=np.dstack([w,b,warp])
    Image.fromarray(np.uint8(np.clip(im*255+.5,0,255))).save(ROOT/'T_LowBankFootprint.png')

def clumps():
    rng=random.Random(903117);out=[]
    centres=[(-84,20.6),(-78.5,16.3),(-75.6,28.8),(-68.6,34.7),(-63,31.7),(-56.7,42.6),(-53,54.4),(-45.5,47.0),(-37.2,46.9),(-31.4,47.5),(-19.3,47.5),(-11.5,46.8),(-5.2,46.2),(2.2,44.8),(-15.2,50.7),(-34,57.5)]
    for index,(cx,cy) in enumerate(centres):
        for j in range(2+index%3):
            for attempt in range(14):
                x=cx+rng.uniform(-1.9,1.9);y=cy+rng.uniform(-1.45,1.45)
                w,_=mask(np.array([[x]]),np.array([[y]]))
                if w[0,0]>.54 and all(math.hypot(x-i[1],y-i[2])>.65 for i in out):break
            else:continue
            name='WoodFernFountain' if j==0 or rng.random()<.27 else 'WoodFernYoung'
            scale=rng.uniform(1.05,1.82)*(1.08 if j==0 else .92)
            out.append([name,round(x,3),round(y,3),round(scale,3),round(rng.uniform(-180,180),2)])
    # Two broader low patches interrupt the bare lower slope below the ford.
    # Their largest fronds stay below the distant shrine's foundation level.
    for name,x,y,s,angle in [('WoodFernFountain',-32,46.30,2.42,32),('WoodFernFountain',-31,45.65,2.12,151),('WoodFernYoung',-33.,46.,1.73,-71),('WoodFernYoung',-32.6,45.55,1.66,93),('WoodFernFountain',-24.45,46.32,2.52,-41),('WoodFernFountain',-23.48,46.56,2.20,131),('WoodFernYoung',-22.8,46.22,1.80,27),('WoodFernYoung',-23.80,45.82,1.62,64)]:
        out.append([name,x,y,s,angle])
    (ROOT/'Clumps.json').write_text(json.dumps(out,indent=1))

if __name__=='__main__':
    tile();footprint();clumps()
