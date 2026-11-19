"""Create original woven banner surfaces. Coordinates are on the warp (vertical) and weft."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
W, H = 1024, 1536
yy, xx = np.indices((H,W),dtype=np.float32)
rng = np.random.default_rng(90124)

def field(w,h):
    sample=rng.normal(0,1,(h,w)).astype("float32")
    return np.asarray(Image.fromarray(sample).resize((W,H),Image.Resampling.BICUBIC))

def save(a,name):
    image=Image.fromarray(np.clip(a,0,255).astype("uint8"))
    image.resize((1024,2048),Image.Resampling.LANCZOS).save(OUT/(name+".png"),optimize=True)

def bands(draw,color,team):
    for left in [59,W-59]:
        for off,weight in [(-24,4),(-11,4),(0,12),(13,4),(24,4)]:
            draw.line((left+off,0,left+off,H), fill=color, width=weight)
    for y in [83,103,294,311,1229,1246,1410,1429]:
        draw.rectangle((0,y,W,y+6),fill=color)
    for y in [187,1330]:
        for cx in range(-17,W+104,110):
            draw.line([(cx-50,y),(cx-24,y-24),(cx-8,y-24),(cx-8,y-39),(cx+8,y-39),(cx+8,y-24),(cx+24,y-24),(cx+50,y)],fill=color,width=6)
            draw.line([(cx-50,y+8),(cx,y+52),(cx+50,y+8)],fill=color,width=5)
            draw.polygon([(cx-12,y+7),(cx,y-6),(cx+12,y+7),(cx,y+20)],fill=color)
    for s in [-1,1]:
        cx=512+s*292
        for y in range(418,1176,91):
            draw.line([(cx-9,y-11),(cx+1,y),(cx-9,y+11)],fill=color,width=4)

def sigil(draw,c,team):
    if team=="Red":
        # Rising twin ridges; the notched keel follows the chevrons on the player's HUD.
        for y,w in [(522,251),(727,182)]:
            pts=[(512,y),(512+w,y+int(.96*w)),(512+w-32,y+int(.96*w)+25),
                 (512,y+105),(512-w+32,y+int(.96*w)+25),(512-w,y+int(.96*w))]
            draw.polygon(pts,fill=c)
        draw.polygon([(512,905),(554,947),(512,1001),(470,947)],fill=c)
    else:
        outer=[(512,480),(772,753),(512,1026),(252,753),(512,480)]
        inner=[(512,563),(691,753),(512,943),(333,753),(512,563)]
        draw.line(outer,fill=c,width=21,joint="curve")
        draw.line(inner,fill=c,width=32,joint="curve")
        draw.polygon([(383,753),(445,722),(579,722),(641,753),(579,784),(445,784)],fill=c)
        for y in (429,1064):
            draw.polygon([(512,y-17),(527,y),(512,y+17),(497,y)],fill=c)

macro=field(14,22)
fleck=field(96,156)
thread_x=xx+.98*field(15,65)
thread_y=yy+.68*field(72,25)
warp=np.cos(thread_x*2*np.pi/5.2)
weft=np.cos(thread_y*2*np.pi/4.1)
interlace=np.cos(thread_x*np.pi/5.2)*np.cos(thread_y*np.pi/4.1)
weave=(warp*.40+weft*.56+(warp-weft)*interlace*.35)
irregular=rng.normal(0,1,(H,W)).astype("float32")
rough=.82+.032*macro+.025*weave+.017*fleck
save(rough*255,"T_StandardWeave_R")
for team in ("Red","Blue"):
    pat=Image.new("L",(W,H)); d=ImageDraw.Draw(pat); bands(d,150,team); sigil(d,255,team)
    pattern=np.asarray(pat).astype("float32")/255
    fade=np.clip(.92+.05*macro+.029*fleck+.055*irregular, .58,1.0)
    body=np.array([145,48,34] if team=="Red" else [39,94,130])
    edge=np.array([154,112,63] if team=="Red" else [143,147,109])
    linen=np.array([213,187,131] if team=="Red" else [214,206,164])
    base=np.empty((H,W,3),dtype="float32");base[:]=body
    bandsmask=np.clip(pattern/.59,0,1)*fade
    base+=(edge-body)*bandsmask[:,:,None]
    emblem=np.clip((pattern-.59)/.41,0,1)*fade
    base+=(linen-edge)*emblem[:,:,None]
    variation=(1.+.049*macro+.026*fleck+.043*weave+.012*irregular)
    # The selvedges and folded hems carry slightly darkened warp yarns.
    hem=np.clip((24-np.minimum(xx,W-xx))/20,0,1)+np.clip((20-np.minimum(yy,H-yy))/22,0,1)
    variation-=.13*hem
    save(base*variation[:,:,None],"T_Standard"+team+"_C")
    ridges=weave*.85+.14*fleck+pattern*(.75+.28*warp)
    gy,gx=np.gradient(ridges)
    n=np.stack((-gx*.72,gy*.72,np.ones_like(gx)),axis=-1)
    n/=np.linalg.norm(n,axis=-1,keepdims=True)
    save((n*.5+.5)*255,"T_Standard"+team+"_N")
