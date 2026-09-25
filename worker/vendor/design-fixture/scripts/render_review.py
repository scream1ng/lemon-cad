#!/usr/bin/env python3
"""Render the actual exported solids; hardware stays in its supplied pose."""
import argparse
from pathlib import Path
import numpy as np
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from export_step import read_step

def triangles(shape):
    BRepMesh_IncrementalMesh(shape,.35,False,.3,True).Perform()
    out=[]; ex=TopExp_Explorer(shape,TopAbs_FACE)
    while ex.More():
        f=TopoDS.Face_s(ex.Current());ex.Next();loc=TopLoc_Location()
        tri=BRep_Tool.Triangulation_s(f,loc)
        if tri is None:continue
        for i in range(1,tri.NbTriangles()+1):
            ids=tri.Triangle(i).Get()
            out.append([tri.Node(j).Transformed(loc.Transformation()).Coord() for j in ids])
    if not out:raise ValueError('STEP shape could not be tessellated')
    return np.array(out)

def _raster_mesh(canvas, depth, mesh, color, scale):
    height,width=canvas.shape[:2]
    light=np.array([-.3,.6,1]);light/=np.linalg.norm(light)
    for tri in mesh:
        x0=max(0,int(np.floor(tri[:,0].min())));x1=min(width-1,int(np.ceil(tri[:,0].max())))
        y0=max(0,int(np.floor(tri[:,1].min())));y1=min(height-1,int(np.ceil(tri[:,1].max())))
        if x1<x0 or y1<y0:continue
        a,b,c=tri;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-9:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
        wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wc=1-wa-wb
        z=wa*a[2]+wb*b[2]+wc*c[2];region=depth[y0:y1+1,x0:x1+1]
        mask=(wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8)&(z>region)
        # Undo pixel scaling before finding the surface normal for shading.
        modeltri=tri.copy();modeltri[:,0]/=scale;modeltri[:,1]/=-scale
        normal=np.cross(modeltri[1]-modeltri[0],modeltri[2]-modeltri[0]);length=np.linalg.norm(normal)
        shade=.45+.55*abs((normal/length)@light) if length else 1
        canvas[y0:y1+1,x0:x1+1][mask]=np.clip(color*shade,0,255).astype(np.uint8);region[mask]=z[mask]

def render(step_path,out,revision,mount_heights=None,shapes=None):
    """Orthographic triangle rasterization with a per-pixel depth buffer (no painter sorting)."""
    from PIL import Image, ImageDraw, ImageFont
    out=Path(out);shapes=read_step(step_path) if shapes is None else shapes
    meshes={n:triangles(shape) for n,shape in shapes.items()}
    allpts=np.concatenate([m.reshape(-1,3) for m in meshes.values()])
    centre=(allpts.min(axis=0)+allpts.max(axis=0))/2
    az,el=np.deg2rad([-125,32])
    view=np.array([np.cos(az)*np.cos(el),np.sin(az)*np.cos(el),np.sin(el)])
    right=np.array([-np.sin(az),np.cos(az),0]);up=np.cross(view,right)
    frame=np.array([right,up,view]).T
    projected={n:(m-centre)@frame for n,m in meshes.items()}
    points=np.concatenate([m.reshape(-1,3) for m in projected.values()]);lo,hi=points.min(axis=0),points.max(axis=0)
    width,height=1600,1120;scale=min(1340/(hi[0]-lo[0]),800/(hi[1]-lo[1]));mid=(lo+hi)/2
    def pixel(points):
        q=points.copy();q[...,0]=(q[...,0]-mid[0])*scale+width/2;q[...,1]=height/2-(q[...,1]-mid[1])*scale
        return q
    try:
        titlefont=ImageFont.truetype('DejaVuSans.ttf',32);font=ImageFont.truetype('DejaVuSans.ttf',18);small=ImageFont.truetype('DejaVuSans.ttf',16)
    except OSError:titlefont=font=small=ImageFont.load_default()
    light=np.array([-.3,.6,1]);light/=np.linalg.norm(light)
    for loaded,filename in ((True,'assembled.png'),(False,'empty-fixture.png')):
        canvas=np.full((height,width,3),[243,245,247],dtype=np.uint8);depth=np.full((height,width),-np.inf)
        labels=[];has_ref=False
        for name,mesh in projected.items():
            leaf=name.split('/')[-1];part=leaf.startswith('Part_');ref=leaf.startswith(('REF_','HW_'))
            if (part or leaf.startswith('REF_source_')) and not loaded:continue
            has_ref|=ref
            color=np.array([215,146,56] if part else [187,68,68] if ref else [143,164,177] if name=='BASE' else [55,107,131])
            _raster_mesh(canvas,depth,pixel(mesh),color,scale)
            if not part and not ref and name!='BASE':
                labels.append((name,pixel(mesh.reshape(-1,3).mean(axis=0))))
        im=Image.fromarray(canvas);draw=ImageDraw.Draw(im)
        draw.text((65,35),('Assembled fixture' if loaded else 'Empty fixture')+f' | {revision}',font=titlefont,fill='#182a35')
        # Label parts outside the model with short leaders, keeping hidden contacts honest.
        for i,(name,p) in enumerate(sorted(labels,key=lambda item:item[1][1])):
            left=p[0]<width/2;side=[item for item in sorted(labels,key=lambda item:item[1][1]) if (item[1][0]<width/2)==left]
            index=next(j for j,item in enumerate(side) if item[0]==name)
            x=65 if left else width-160;y=170+index*min(52,780/max(1,len(side)-1))
            draw.line((x+75 if left else x-10,y+10,p[0],p[1]),fill='#687c89',width=1)
            draw.text((x,y),name,font=font,fill='#203746')
        draw.text((65,height-100),'Review concept | millimetres | images are not verification evidence',font=small,fill='#404b55')
        note='Red: hardware/reference CAD. Saved clamp pose and motion require verification.' if has_ref else 'Purchased hardware geometry absent; mounting details only.'
        draw.text((65,height-70),note,font=small,fill='#404b55')
        if loaded and mount_heights:im=height_insets(im,meshes,mount_heights)
        im.save(out/filename)

def height_insets(main, meshes, report):
    """Append actual CAD side projections; retain the routine two-image contract."""
    from PIL import Image, ImageDraw, ImageFont
    rows=report.get('clamps',[])
    if not rows:return main
    columns=min(3,len(rows));tile_w=main.width//columns;tile_h=300
    out=Image.new('RGB',(main.width,main.height+45+tile_h*((len(rows)+columns-1)//columns)),(243,245,247));out.paste(main,(0,0))
    try:font=ImageFont.truetype('DejaVuSans.ttf',16)
    except OSError:font=ImageFont.load_default()
    draw=ImageDraw.Draw(out);draw.text((25,main.height+12),'Mounting height | actual CAD side projections | saved clamp pose',font=font,fill='#203746')
    for i,row in enumerate(rows):
        tile=Image.new('RGB',(tile_w,tile_h),(243,245,247));td=ImageDraw.Draw(tile)
        frame=row.get('frame');base_names=[n for n in meshes if n==row['mount_plate'] or n.startswith('HW_'+row['tag']+'_')]
        if frame and base_names:
            x=np.array(frame['x']);z=np.array(frame['z']);basis=np.array([x,z,np.cross(x,z)]).T
            origin=np.array(row['target_contact']);projected={n:(meshes[n]-origin)@basis for n in base_names}
            points=np.concatenate([m.reshape(-1,3) for m in projected.values()]);lo,hi=points.min(axis=0),points.max(axis=0)
            lo[:2]=np.minimum(lo[:2],[0,0]);hi[:2]=np.maximum(hi[:2],[0,0]);mid=(lo+hi)/2
            scale=min((tile_w-45)/max(hi[0]-lo[0],1),(tile_h-90)/max(hi[1]-lo[1],1))
            def pixel(m):
                q=m.copy();q[...,0]=(q[...,0]-mid[0])*scale+tile_w/2;q[...,1]=tile_h/2+10-(q[...,1]-mid[1])*scale;return q
            if row.get('part') in meshes:projected[row['part']]=(meshes[row['part']]-origin)@basis
            canvas=np.full((tile_h,tile_w,3),[243,245,247],dtype=np.uint8);depth=np.full((tile_h,tile_w),-np.inf)
            for name,m in projected.items():
                color=np.array([187,68,68] if name.startswith('HW_') else [215,146,56] if name==row.get('part') else [55,107,131])
                _raster_mesh(canvas,depth,pixel(m),color,scale)
            tile=Image.fromarray(canvas);td=ImageDraw.Draw(tile)
            if row.get('offset_mm') is not None:
                for level,color in [(row['mount_face_height_mm'],'#235b78'),(row['clamping_surface_height_mm'],'#b16b16')]:
                    yy=float(pixel(np.array([0.,level-origin@z,0.]))[1]);td.line((15,yy,tile_w-15,yy),fill=color,width=2)
        # White caption bands keep imported geometry from obscuring measured text.
        td.rectangle((0,0,tile_w,47),fill='#f3f5f7');td.rectangle((0,tile_h-23,tile_w,tile_h),fill='#f3f5f7')
        if row.get('offset_mm') is None:caption=row['tag']+' | height unverified'
        else:caption=f"{row['tag']} | M {row['mount_face_height_mm']:.2f} / C {row['clamping_surface_height_mm']:.2f} mm"
        td.text((15,5),caption,font=font,fill='#203746')
        detail=f"Offset {row['offset_mm']:+.2f} mm | {row['status']}" if row.get('offset_mm') is not None else row.get('reason','Missing measurement')[:55]
        td.text((15,26),detail,font=font,fill='#203746');td.text((15,tile_h-22),'M: mounting face   C: clamping surface',font=font,fill='#404b55')
        out.paste(tile,((i%columns)*tile_w,main.height+45+(i//columns)*tile_h))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('step');p.add_argument('out');p.add_argument('--revision',required=True)
    a=p.parse_args();render(a.step,a.out,a.revision)
