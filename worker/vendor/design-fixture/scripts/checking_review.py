"""Append actual CAD station views to the inherited two review images."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from export_step import read_step
from checking_geometry import station_shapes
from render_review import triangles,_raster_mesh
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax2


def append_insets(step_path,out,report,plan):
    out=Path(out);shapes=read_step(step_path);rows=report.get('stations',[])
    if not rows:return
    stations={s['id']:s for f in plan['flanges'] for s in f.get('checks',[])}
    try:font=ImageFont.truetype('DejaVuSans.ttf',17)
    except OSError:font=ImageFont.load_default()
    cache={}
    for filename in ('assembled.png','empty-fixture.png'):
        path=out/filename
        if not path.exists():continue
        im=Image.open(path).convert('RGB');tw=im.width//3;th=310
        image=Image.new('RGB',(im.width,im.height+45+th*((len(rows)+2)//3)),(243,245,247));image.paste(im,(0,0))
        draw=ImageDraw.Draw(image);draw.text((25,im.height+12),'Checking stations | actual CAD sections | nominal gap, not calibration',font=font,fill='#203746')
        for i,row in enumerate(rows):
            s=stations[row['id']];tile=Image.new('RGB',(tw,th),(243,245,247));td=ImageDraw.Draw(tile)
            if s['kind']!='alternative' and row.get('part_shape') in shapes and row.get('fixture_shape') in shapes:
                p=np.array(s['point_mm'],float);n=np.array(s['direction'],float)
                u=np.array(s.get('patch',{}).get('u',[1,0,0]),float)
                if abs(u@n)>.99:u=np.array([0,1,0],float)
                u=u-n*(u@n);u/=np.linalg.norm(u);depth_axis=np.cross(u,n);basis=np.array([u,n,depth_axis]).T
                span=45.;origin=p-u*span/2-n*span/2-depth_axis*.05
                slab=BRepPrimAPI_MakeBox(gp_Ax2(gp_Pnt(*origin),gp_Dir(*depth_axis),gp_Dir(*u)),span,span,.1).Shape()
                scale=min(tw/45,9);canvas=np.full((th,tw,3),[243,245,247],dtype=np.uint8);depth=np.full((th,tw),-np.inf)
                for name,color in ((row['part_shape'],[215,146,56]),(row['fixture_shape'],[55,107,131])):
                    key=(row['id'],name)
                    if key not in cache:
                        section=BRepAlgoAPI_Common(station_shapes(shapes,plan,s)[name],slab);section.Build()
                        if not section.IsDone():raise ValueError('Checking section failed')
                        cache[key]=triangles(section.Shape())
                    q=(cache[key]-p)@basis;q[...,0]=q[...,0]*scale+tw/2;q[...,1]=th/2-q[...,1]*scale
                    _raster_mesh(canvas,depth,q,np.array(color),scale)
                tile=Image.fromarray(canvas);td=ImageDraw.Draw(tile)
                g=float(s.get('nominal_gap_mm',3));x=tw/2;td.line((x,th/2,x,th/2-g*scale),fill='#c31a30',width=2)
            td.rectangle((0,0,tw,57),fill='#f3f5f7');td.rectangle((0,th-55,tw,th),fill='#f3f5f7')
            td.text((12,5),row['id']+' | '+row['status'],font=font,fill='#203746')
            if s['kind']!='alternative':
                td.text((12,28),f"Gap {s.get('nominal_gap_mm',3):g} | GO {s.get('go_mm',2.5):g} / NO-GO {s.get('no_go_mm',3.5):g} mm",font=font,fill='#203746')
            td.text((12,th-49),'GO enters; NO-GO must not enter',font=font,fill='#203746')
            td.text((12,th-25),'Light pressure; do not deflect flange',font=font,fill='#203746')
            image.paste(tile,((i%3)*tw,im.height+45+(i//3)*th))
        image.save(path)
