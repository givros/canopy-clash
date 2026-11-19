"""Fit a weathered basalt spur and its bedding to the existing surveyed west fall."""
from pathlib import Path
import json,sys,math
import numpy as np
from scipy.interpolate import RegularGridInterpolator,LinearNDInterpolator,NearestNDInterpolator
from scipy.ndimage import gaussian_filter
ROOT=Path(__file__).resolve().parents[1];DEST=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'Tools'))
import valley as v
from math import sin,cos,pi
rng=np.random.default_rng(2401)
heights=np.fromfile(ROOT/'Terrain/ValleyHeights.f32','<f4').reshape(505,505)/100
def terrain(x,y):
    a=(np.asarray(x)-48)/.8+252;b=np.asarray(y)/.8+252
    i=np.floor(a).astype(int);j=np.floor(b).astype(int);s=a-i;t=b-j
    return np.where(t>s,heights[j,i]+s*(heights[j+1,i+1]-heights[j+1,i])+t*(heights[j+1,i]-heights[j,i]),heights[j,i]+s*(heights[j,i+1]-heights[j,i])+t*(heights[j+1,i+1]-heights[j,i+1]))
def scan(source):
    p=ROOT/'Nature/Sources'/source;d=json.loads((p/(source+'.gltf')).read_text());p0=d['meshes'][0]['primitives'][0];a=d['accessors'][p0['attributes']['POSITION']];b=d['bufferViews'][a['bufferView']]
    xyz=np.frombuffer((p/d['buffers'][b['buffer']]['uri']).read_bytes(),'<f4',count=a['count']*3,offset=b.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,3)
    # The original scanned outcrop faces toward positive Z, with Y vertical.
    pu=(xyz[:,0]-xyz[:,0].min())/np.ptp(xyz[:,0])
    pv=(xyz[:,1]-xyz[:,1].min())/np.ptp(xyz[:,1]);ix=np.clip(np.rint(pu*127),0,127).astype(int);iy=np.clip(np.rint(pv*127),0,127).astype(int)
    front=np.full((128,128),-np.inf);np.maximum.at(front,(iy,ix),xyz[:,2]);yy,xx=np.indices(front.shape);sel=np.isfinite(front)
    filled=NearestNDInterpolator(np.c_[yy[sel],xx[sel]],front[sel])(yy,xx);base=gaussian_filter(filled,10)
    surface=gaussian_filter(filled,.9)-base
    return RegularGridInterpolator((np.arange(128)/127,np.arange(128)/127),np.clip(surface,-.8,.8),bounds_error=False,fill_value=0)
source=scan('rock_face_01')
Y,Z=np.meshgrid(np.linspace(-43.5,-20.8,160),np.linspace(27.2,55.6,202))
xs=np.linspace(83,118,800);X=np.empty_like(Y);continuity=np.zeros_like(Y)
for i in range(Y.shape[1]):
    y=Y[0,i];line=terrain(xs,y)
    for j,z in enumerate(Z[:,i]):
        hits=np.where((line[1:]>=z)&(line[:-1]<z-.0000001))[0]
        if not len(hits):X[j,i]=118;continue
        k=hits[0];X[j,i]=xs[k]+(xs[k+1]-xs[k])*(z-line[k])/(line[k+1]-line[k]);continuity[j,i]=1
def smooth(a):a=np.clip(a,0,1);return a*a*(3-2*a)
def reflect(a):return 1-abs((a%2)-1)
# Broad, broken beds can be read from the bridge. Fine fractures come from an actual scanned face.
wobble=.26*np.sin(.54*Y+1.8)+.17*np.sin(.34*Z-.17*Y)+.13*np.cos(.94*Y)
raw=Z+.13*Y+wobble
band=np.zeros_like(X);veins=np.zeros_like(X)
for j,(h,lo,hi,depth) in enumerate([(23.4,-42.5,-30.4,1.65),(28.5,-40.4,-23.8,2.5),(31.2,-41.8,-32.2,1.5),(34.6,-42.8,-26.8,2.1),(38.4,-38.5,-22.6,2.4),(40.9,-41.67,-34.42,1.8),(43.4,-41.4,-27.8,2.35),(46.9,-36.3,-22.3,2.1),(48.8,-41.7,-33.2,1.35)]):
    fault=.81*np.tanh((Y+32.65+.085*(Z-42)+.30*np.sin(.40*Z))/.39)
    dip=(Y+(lo+hi)*-.5)*(.12*math.sin(j*2.79+.4))
    delta=raw-h-.58*np.sin(.37*Y+j*.73)-fault-dip
    lens=smooth((Y-lo)/2.1)*smooth((hi-Y)/2.5)
    # Slower upward retreat over the shelf; sharp, undercut eyebrow below it.
    joint=np.exp(-((delta+.15)/np.where(delta<-.15,.72,1.56))**2)
    fracture=Y-((lo+hi)*.5+1.65*math.sin(2.13*j))-.12*(Z-h)
    breakage=1-(.64 if j%3 else .81)*np.exp(-(fracture/(.63+.24*(j%2)))**2)
    band+=depth*.87*lens*joint*breakage
    veins+=lens*np.exp(-((delta-.52)/.48)**2)
block=.70*np.cos(.69*Y+.22*Z+1.15*np.sin(.18*Z))+.38*np.sin(.37*Y-.15*Z)
seams=(abs(np.sin(.55*Y+.097*Z+.6*np.sin(.49*Z+.18*Y)))**.40-.58)*1.18
scanface=source(np.stack((reflect((Z+.13*Y)/4.95),reflect((Y+.16*Z)/7.54)),axis=-1))
river=np.array([v.river_sample(float(x),float(y))[0] for x,y in zip(X.flat,Y.flat)]).reshape(X.shape)
trail=np.array([v.trail_sample(float(x),float(y))[0] for x,y in zip(X.flat,Y.flat)]).reshape(X.shape)
bound=smooth((Y+43.4+.44*np.sin(Z*.39))/2.75)*smooth((-21.0-Y+.56*np.sin(.57*Z))/2.7)*smooth((Z-27.35-1.5*np.sin(.29*Y+1))/3)*smooth((54.2+.75*np.sin(.57*Y)-Z)/2.35)
fit=bound*smooth((river-.27)/1.95)*smooth((trail-4)/2)*continuity
relief=-.62+fit*(2.18+block+seams+band+1.87*scanface)
front=X-relief;back=X+1.15
# Triangles with discontinuous attachment are cut and capped at the natural vertical fissure.
ny,nx=Y.shape;cells=np.minimum.reduce([fit[:-1,:-1],fit[1:,:-1],fit[:-1,1:],fit[1:,1:]])>.002
for d in (abs(X[:-1,:-1]-X[:-1,1:]),abs(X[:-1,:-1]-X[1:,:-1]),abs(X[1:,:-1]-X[1:,1:]),abs(X[:-1,1:]-X[1:,1:])):cells&=(d<.80)
verts=[];colors=[];faces=[];indices={}
wet=np.clip(.78-(Y+43.5)*.038+.29*np.sin(.54*Y+.13*Z)+.28*np.cos(.81*Y+.06*Z),0,1)
moss=np.clip(.19+.59*veins+.27*np.sin(.89*Y+1.18*np.cos(.38*Z))+.23*scanface,0,1)
def vid(i,j,backing):
    key=(i,j,backing)
    if key not in indices:
        f=back if backing else front
        indices[key]=len(verts);verts.append([f[i,j],Y[i,j],Z[i,j]])
        colors.append([moss[i,j],wet[i,j],min(1,max(0,veins[i,j]*.59)),1.])
    return indices[key]
for ii,jj in np.argwhere(cells):
    i=int(ii);j=int(jj);rect=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)];a=[vid(*p,False) for p in rect];b=[vid(*p,True) for p in rect]
    faces.extend([(a[0],a[1],a[2]),(a[0],a[2],a[3]),(b[0],b[3],b[2]),(b[0],b[2],b[1])])
    for e,(di,dj) in enumerate(((0,-1),(1,0),(0,1),(-1,0))):
        p=i+di;q=j+dj
        if p<0 or p>=ny-1 or q<0 or q>=nx-1 or not cells[p,q]:
            k=(e+1)%4;faces.extend([(a[e],b[e],a[k]),(a[k],b[e],b[k])])
origin=(97.,-37.,30.);verts=np.array(verts);np.savez_compressed(DEST/'survey.npz',verts=verts-origin,colors=colors,faces=faces)
# Root vegetation into real upward-facing, exposed shoulders. Sparse forest pockets nearest spray.
plants=[];taken=[]
fy,fx=np.gradient(front,Z[1,0]-Z[0,0],Y[0,1]-Y[0,0]);normZ=fy/np.sqrt(1+fx*fx+fy*fy)
candidates=np.argwhere((fit>.65)&(normZ>.41)&(relief>1.25)&(np.pad(cells,[(0,1),(0,1)])))
rng.shuffle(candidates)
for i,j in candidates:
    pos=np.array((front[i,j],Y[i,j],Z[i,j]))
    if any(np.linalg.norm(pos-q)<1.6 for q in taken):continue
    taken.append(pos);kind=rng.choice(['Fern','Heliconia','MossCushion','LianaCurtain'],p=[.40,.10,.31,.19])
    plants.append([str(kind),pos.tolist(),float(rng.uniform(.69,1.45)),float(rng.uniform(-180,180))])
    if len(plants)>=48:break
(DEST/'escarpment.json').write_text(json.dumps(dict(origin=origin,plants=plants,triangles=len(faces),min_channel_m=float(river[fit>.01].min()),min_trail_m=float(trail[fit>.01].min()),source='https://polyhaven.com/a/rock_face_01'),indent=2))
print(len(faces),len(plants))

