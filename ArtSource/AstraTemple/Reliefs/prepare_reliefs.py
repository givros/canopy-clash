"""Resample the sculpt studies in physical centimetres for the native mesh builder."""
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter


SOURCE = Path(__file__).resolve().parent
CACHE = SOURCE.parents[2] / "Saved" / "AstraAuthoring" / "ReliefHeights"
WIDTH, HEIGHT = 657, 311


def prepare(name):
    image = Image.open(SOURCE / (name + "_Height.png")).convert("L")
    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    values = np.asarray(image, dtype=np.float32)[::-1] / 255.
    dark, light = np.percentile(values, (1.5,99.3))
    relief = np.clip((values-dark)/(light-dark), 0,1)
    # Lift complete silhouettes out of the bed while preserving the interior modelling.
    field = gaussian_filter(relief, .44)
    silhouette = np.clip((gaussian_filter(field,1.0)-.085)/.43,0,1)
    shoulder = np.minimum(1.,distance_transform_edt(field>.23)/10.0)
    y,z = np.meshgrid(np.linspace(-350,350,WIDTH),np.linspace(-165,165,HEIGHT))
    weather = .0018*np.sin(y*.16 + z*.11) + .0022*np.sin(z*.065 - y*.028)
    depth = np.clip(.015 + .055*silhouette + .274*field**1.29 + .048*shoulder + weather,.006,.425)
    payload = np.rint(depth*100000).astype("<u2").tobytes()
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE/(name+".rawz")).write_bytes(struct.pack("<HH",WIDTH,HEIGHT)+zlib.compress(payload,8))


if __name__=="__main__":
    for subject in ("JaguarProcession","RainbirdOffering"):
        prepare(subject)
