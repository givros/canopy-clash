"""Build the closed portrait volume from its study and anatomical planes, in centimetres."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import cv2
from PIL import Image
from scipy.ndimage import binary_fill_holes, distance_transform_edt, gaussian_filter, label
from skimage.measure import marching_cubes


ROOT=Path(__file__).resolve().parent
CACHE=ROOT.parents[2]/"Saved"/"AstraAuthoring"/"ReliefHeights"


def portrait():
    src=np.asarray(Image.open(ROOT/"SpringKeeper_Height.png").convert("L"))
    components,n=label(src>19)
    largest=np.bincount(components.ravel())[1:].argmax()+1
    mask=binary_fill_holes(components==largest)
    yy,xx=np.where(mask)
    bounds=(xx.min(),yy.min(),xx.max()+1,yy.max()+1)
    width,height=545,475
    gray=np.asarray(Image.fromarray(src).crop(bounds).resize((width,height),Image.Resampling.LANCZOS),dtype=np.float32)/255.
    shape=np.asarray(Image.fromarray(mask.astype(np.uint8)*255).crop(bounds).resize((width,height),Image.Resampling.LANCZOS))>=120
    pad=4
    gray=np.pad(gray,pad)
    shape=np.pad(shape,pad)
    count_y,count_x=gray.shape
    u,v=np.meshgrid((np.arange(count_x)-pad)/(width-1),(np.arange(count_y)-pad)/(height-1))
    spacing_y=1000./(width-1)
    spacing_z=870./(height-1)
    def bump(cx,cy,rx,ry):
        return np.exp(-(((u-cx)/rx)**2+((v-cy)/ry)**2))
    dist=distance_transform_edt(shape,sampling=(spacing_z,spacing_y))
    outside=distance_transform_edt(~shape,sampling=(spacing_z,spacing_y))
    signed=gaussian_filter(dist-outside,.63)
    # Suppress apparent pits inherited from the study's stony surface. Retain
    # the larger sculpt cuts as geometry; native stone normals supply the grain.
    clean=cv2.bilateralFilter(gray,11,.12,3.35)
    field=gaussian_filter(clean,.92)
    relief=np.clip((field-.045)/.82,0,1)
    # The broad volumes are independent of stone colour or the lighting in the study.
    face=np.exp(-(((u-.5)/.324)**4+((v-.699)/.37)**6))
    jaw=bump(.50,.865,.275,.128)
    chin=bump(.5,.93,.133,.068)
    cheeks=bump(.302,.687,.117,.105)+bump(.705,.686,.12,.10)
    brows=bump(.332,.508,.118,.046)+bump(.671,.504,.118,.046)
    eyes=bump(.339,.559,.084,.025)+bump(.670,.557,.084,.025)
    bridge=bump(.503,.584,.052,.105)
    bulb=bump(.507,.665,.073,.047)
    wings=bump(.418,.672,.045,.038)+bump(.582,.671,.045,.039)
    septum=bump(.501,.704,.030,.018)
    nares=bump(.441,.694,.026,.016)+bump(.563,.692,.027,.017)
    lips=bump(.498,.800,.15,.051)
    temple=bump(.505,.419,.31,.075)
    crown=bump(.5,.24,.325,.21)
    spools=bump(.125,.77,.107,.162)+bump(.884,.767,.105,.158)
    white=gaussian_filter(relief,3.4)
    face_mass=(37.+42.*face+15.*jaw+13.*chin+16.*cheeks+12.*brows-10.*eyes
               +23.*bridge+40.*bulb+16.*wings+13.*septum-6.*nares+17.*lips+12.*temple+14.*crown+12.*spools)
    # Stronger silhouette modulation on crown glyphs and earspools; the
    # cheeks, lips and eye sockets have gentler transitions than the headdress.
    feature=1.-.24*face
    carving=feature*(35.*relief+6.*(relief-white)+8.*white)
    # Thick turned cheeks and ears taper gently back to the hewn outer arris.
    shoulder=np.sin(np.pi*.5*np.clip(dist/58.,0,1))**.74
    depth=27.+(face_mass+carving-27.)*(.23+.77*shoulder)
    depth*=193.0/np.max(depth[shape])
    # Intersect the sculpted front, planar rear, and profile-aware chamfered perimeter.
    step=1.8
    distances=np.arange(-2.*step,198.+step,step,dtype=np.float32)
    packed=np.empty((len(distances),count_y,count_x),dtype=np.float32)
    for i,d in enumerate(distances):
        bevel=11.*(max(0,1.-d/23.0)**2)+4.*np.maximum(0.,(d-(depth-8.8))/8.8)**2
        packed[i]=np.minimum(np.minimum(d,depth-d),signed-bevel)
    verts,triangles,normals,_=marching_cubes(packed,level=0,spacing=(step,spacing_z,spacing_y),
                                              allow_degenerate=False,gradient_direction="descent")
    x=-(verts[:,0]+distances[0])
    y=verts[:,2]-pad*spacing_y-500.
    z=435.-(verts[:,1]-pad*spacing_z)
    # Keep the measured silhouette exactly on the mounting dimensions.
    y=(y-y.min())*(1000./np.ptp(y))-500.
    z=(z-z.min())*(870./np.ptp(z))-435.
    coords=np.column_stack((x,y,z)).astype("<f4")
    normal=np.column_stack((-normals[:,0],normals[:,2],-normals[:,1]))
    outer=np.argmin(x)
    if normal[outer,0]>0:normal*=-1.
    normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1.e-8)
    t=triangles[::max(1,len(triangles)//34000)]
    ue_cross=np.cross(coords[t[:,2]]-coords[t[:,0]],coords[t[:,1]]-coords[t[:,0]])
    if np.sum(ue_cross*normal[t[:,0]])<0.:
        triangles=triangles[:,[0,2,1]]
    tone=np.clip(.14+.57*np.clip(-x/185.,0,1)+.24*np.maximum(0.,normal[:,2]),0,1)
    packed_data={"positions":coords,"normals":normal.astype("<f4"),
                 "faces":triangles.astype("<i4"),"tone":np.rint(255*tone).astype("u1")}
    CACHE.mkdir(exist_ok=True,parents=True)
    with ZipFile(CACHE/"SpringKeeperVolume.zip","w",ZIP_DEFLATED,compresslevel=5) as out:
        for key,values in packed_data.items():
            out.writestr(key,np.ascontiguousarray(values).tobytes())
    print(f"{len(coords)} vertices, {len(triangles)} triangles, bounds {coords.min(axis=0)} to {coords.max(axis=0)} cm")


if __name__=="__main__":
    portrait()
