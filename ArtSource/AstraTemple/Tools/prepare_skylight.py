from pathlib import Path
import cv2
import numpy as np
base=Path(__file__).resolve().parents[1]/"Terrain"
sky=cv2.imread(str(base/"T_KloofendalDaylight.hdr"),cv2.IMREAD_UNCHANGED)
# Remove the direct solar disk from the environment light. Keep HDR cloud and sky.
lum=np.max(sky,axis=2)
ys,xs=np.indices(lum.shape)
sy,sx=np.unravel_index(lum.argmax(),lum.shape)
radius=np.sqrt(((xs-sx)*.68)**2+(ys-sy)**2)
ring=(radius>25)&(radius<35)
fill=np.median(sky[ring],axis=0)
amount=np.clip((24-radius)/10,0,1)[...,None]
sky=sky*(1-amount)+fill*amount
cv2.imwrite(str(base/"T_SkyDiffuse.hdr"),sky.astype(np.float32))
# Keep the photographic roll-off outside the sun disk in the visible backdrop.
# The cubemap used for diffuse lighting retains its full open-sky radiance.
peak=np.maximum(sky.max(axis=2),1e-6)
shoulder=np.maximum(peak-.95,0)
display=np.minimum(peak,.95)+1.32*shoulder/(shoulder+1.32)
cv2.imwrite(str(base/"T_CanopySky.hdr"),(sky*(display/peak)[...,None]).astype(np.float32))
