"""Combine source coverage with sRGB reflectance and preserve the original ARM and DX normals."""
from pathlib import Path
import numpy as np
from PIL import Image

root=Path(__file__).resolve().parent
maps=root/'Maps'
maps.mkdir(exist_ok=True)
for asset,name,prefix in [('fern_02','WoodFern','fern_02'),('potted_plant_02','ElephantEar','potted_plant_02_leaves')]:
    src=root/'Originals'/asset/'textures'
    with Image.open(next(src.glob(prefix+'_diff*'))) as diffuse, Image.open(next(src.glob(prefix+'_alpha*'))) as coverage:
        color=diffuse.convert('RGB')
        array=np.asarray(coverage)
        if array.dtype==np.uint16:array=np.rint(array.astype(np.float32)/257).astype(np.uint8)
        color.putalpha(Image.fromarray(array).convert('L'))
        color.save(maps/('T_'+name+'_ColorAlpha.png'),compress_level=2)
        print(name,color.size,'coverage',float(np.mean(array>85)))
    for channel,suffix in [('arm','ARM'),('nor_dx','NormalDX')]:
        with Image.open(next(src.glob(prefix+'_'+channel+'*'))) as image:
            image.convert('RGB').save(maps/('T_'+name+'_'+suffix+'.png'),compress_level=2)
