"""Bring the static local water reflection probe into fixed-exposure linear colour."""
from pathlib import Path
import cv2
import numpy as np

terrain=Path(__file__).resolve().parents[1]/"Terrain"
radiance=cv2.imread(str(terrain/"PoolPanorama.hdr"),cv2.IMREAD_UNCHANGED)
if radiance is None:raise RuntimeError("Export T_PoolRadiance from the native Unreal capture first")
exposed=np.maximum(0,radiance)/4600.
reflected=(.88*exposed/(1+exposed)).astype(np.float32)
if not cv2.imwrite(str(terrain/"T_PoolSurroundings.hdr"),reflected):
    raise RuntimeError("Could not write the local reflection cubemap")
