"""Author the original quarry sample and shared stone textures in linear material roles."""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates
root=Path(__file__).parent
rng=np.random.default_rng(3917)
N=1024
def field(s):
    a=gaussian_filter(rng.standard_normal((N,N)),s,mode="wrap")
    return (a-a.mean())/a.std()
low=field(68); mid=field(16); blot=field(6); grain=field(.65); detail=field(1.8); streak=gaussian_filter(rng.standard_normal((N,N)),(1.2,29),mode='wrap'); streak/=streak.std()
sed=np.sin(np.arange(N)[:,None]*2*np.pi/64 + low*.72 + mid*.18 + .17*blot)
f=.038*low+.027*mid+.027*blot+.019*detail+.043*grain+.012*streak+.012*sed
holes=np.clip((-detail-1.33)*.11,0,.17)
pale=np.clip((blot+detail*.45-1.40),0,1)*.035
loam=np.clip((mid*.72+low*.55+.35*detail-.9)*.11,0,.14)
base=np.stack([.672+f+1.05*pale-1.05*loam-holes,.585+f+.96*pale-.40*loam-holes,.435+f+.84*pale-.72*loam-holes],axis=-1)
height=detail*.0022+grain*.0018+blot*.0032+streak*.00065+sed*.0011-holes*.036
dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*N/4.8
dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*N/4.8
normal=np.stack([-dx,dy,np.ones_like(dx)],axis=-1);normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
for role,a in [('BaseColor',base),('Normal',normal*.5+.5),('Roughness',.85+.022*grain+.025*mid+.015*holes)]:
    Image.fromarray(np.round(255*np.clip(a,0,1)).astype('uint8')).save(root/f'T_Astra_TempleStone_{role}.png')
