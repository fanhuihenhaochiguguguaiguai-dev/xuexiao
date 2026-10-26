"""Author new tileable PBR source maps; never upscale a reference photograph."""
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'.campus-cache/v06/assets';out.mkdir(exist_ok=True)
n=4096;rng=np.random.default_rng(606);x=np.arange(n)[None,:];y=np.arange(n)[:,None]
grain=rng.normal(0,1.2,(n,n)).astype(np.float32);seam=(x%1024<9)|(y%512<9);height=grain*.0007-seam*.015
base=np.array([194,183,169]);rgb=np.clip(base[None,None,:]+grain[...,None]*1.5-seam[...,None]*22,0,255).astype('uint8')
rough=np.uint8(np.clip(187+grain*1.5+seam*24,0,255))
dx=(np.roll(height,-1,1)-np.roll(height,1,1))*20;dy=(np.roll(height,-1,0)-np.roll(height,1,0))*20;norm=np.sqrt(dx*dx+dy*dy+1)
normal=np.uint8(np.stack([(-dx/norm*.5+.5)*255,(-dy/norm*.5+.5)*255,(1/norm*.5+.5)*255],axis=-1).clip(0,255))
for name,data in [('stone-basecolor',rgb),('stone-roughness',rough),('stone-normal',normal)]:
 im=Image.fromarray(data);im.save(out/(name+'-source4096.png'),optimize=True)
 for size in [1024,2048]:
  small=im.resize((size,size),Image.Resampling.LANCZOS)
  small.save(out/(name+f'-{size}.png'),optimize=True)
print('V06_PBR_MAPS_AUTHORED',n)
