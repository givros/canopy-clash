"""Periodic damp seams, fine runoff threads and lichen islands, independent of stone UVs."""
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
root=Path(__file__).resolve().parents[1]
rng=np.random.default_rng(62014)
n=1024
def field(s):
    value=gaussian_filter(rng.normal(size=(n,n)),s,mode="wrap")
    return (value-value.mean())/(value.std()+1e-8)
lichen=field(43)*.61+field(14)*.28+field(4)*.16+field(1)*.10
runoff=field((45,4))*.32+field((18,2))*.34+field((8,1))*.16+field(41)*.28
coating=np.stack([np.clip(lichen*1.7-.24,0,1),np.clip(runoff-.12,0,1),np.clip(.52+.21*field(25),0,1)],axis=-1)
Image.fromarray((255*coating).round().astype("uint8")).save(root/"Terrain/T_MasonryWeathering.png")
