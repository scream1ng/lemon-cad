import {viewportFrustum,visibleLabelCenter} from './viewportFit';
import {useEffect, useRef, useImperativeHandle, forwardRef} from 'react';
import * as THREE from 'three';
import {TrackballControls} from 'three/addons/controls/TrackballControls.js';
import {cylinderRims, pickCadEntity, pickSketchFace, type Rim} from './picking';
import {dimensionClick,cursorLabelPosition,offsetDimension,anchorDimension,visiblePlanarDimension,projectOntoLine,calloutTip,separateLabels,type Point2,type Placement} from './dimensionPlacement';
import {pickEdge,type CadEdge} from './edgePicking';
import {STLLoader} from 'three/addons/loaders/STLLoader.js';
import {PDFDocument, StandardFonts, rgb} from 'pdf-lib';
import type {SketchFrame} from './cadDocument';
import {planeEdge,type PlaneEdge,type SketchView} from './sketchGeometry';
import type {MeasureFeature} from './quickMeasure';
import {fileURL, dimensionValue, type Model, type Dimension} from './api';

export type ViewerHandle = {pickSketchEdge:(x:number,y:number,frame:SketchFrame)=>PlaneEdge|null;sketchView: () => SketchView|null; panSketch:(dx:number,dy:number)=>void; zoomSketch:(factor:number)=>void; focus: () => void; fit: (view?: string) => void; camera: () => any; normalTo: (frame:SketchFrame) => void; restoreCamera: (camera:any) => boolean; export: (format: 'png'|'pdf') => Promise<void>};
type Props = {model: Model; dimensions: Dimension[]; preview: Dimension|null; pending:boolean; onPlace:(placement:Placement)=>void; unit: string; stlUnit: string; selected: number[]; measuring: boolean; edgePicking:boolean; selecting?:boolean; editable:boolean; onSelectFace?:(selection:{id:number;point:number[]}|null)=>void; wire: boolean; labels: boolean; onPick: (id: number, point: number[]) => void; onReady: (faces: any[],features:Record<string,MeasureFeature>) => void; onLabelMove: (id:string,placement:Placement) => void; onLabelDelete:(id:string)=>void; onViewChange:(view:string|null)=>void; onError: (message: string) => void};
const labelFont=(ratio:number)=>`600 ${13*ratio}px ui-sans-serif, system-ui, sans-serif`;
function download(blob: Blob, name: string) {const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);}

export const Viewer = forwardRef<ViewerHandle, Props>(function Viewer(props, ref) {
  const host = useRef<HTMLDivElement>(null), current = useRef(props), runtime = useRef<any>(null);
  current.current = props;
  useImperativeHandle(ref, () => ({
    pickSketchEdge(x,y,frame) {return runtime.current?.pickSketchEdge(x,y,frame)??null;},
    sketchView() {const r=runtime.current;if(!r?.ready)return null;return {matrix:new THREE.Matrix4().multiplyMatrices(r.camera.projectionMatrix,r.camera.matrixWorldInverse).toArray(),width:host.current!.clientWidth,height:host.current!.clientHeight};},
    panSketch(dx,dy) {const r=runtime.current;if(!r?.ready)return;const c=r.camera,w=host.current!.clientWidth,h=host.current!.clientHeight;const shift=new THREE.Vector3().setFromMatrixColumn(c.matrixWorld,0).multiplyScalar(-dx*(c.right-c.left)/c.zoom/w).addScaledVector(new THREE.Vector3().setFromMatrixColumn(c.matrixWorld,1),dy*(c.top-c.bottom)/c.zoom/h);c.position.add(shift);r.controls.target.add(shift);r.controls.update();r.render();},
    zoomSketch(factor) {const r=runtime.current;if(!r?.ready)return;r.camera.zoom=Math.max(.01,Math.min(100,r.camera.zoom*factor));r.camera.updateProjectionMatrix();r.render();},
    focus() {host.current?.focus();},
    fit(view) {runtime.current?.fit(view);},
    normalTo(frame) {runtime.current?.normalTo(frame);},
    restoreCamera(saved) {const r=runtime.current;if(!r?.ready||!saved)return false;r.camera.position.fromArray(saved.position);r.camera.up.fromArray(saved.up||[0,0,1]);r.controls.target.fromArray(saved.target);r.camera.zoom=saved.zoom;r.camera.updateProjectionMatrix();r.controls.update();r.render();return true;},
    camera() {const r = runtime.current; return r ? {position:r.camera.position.toArray(), target:r.controls.target.toArray(), zoom:r.camera.zoom,up:r.camera.up.toArray()} : null;},
    async export(format) {
      const r = runtime.current;
      if (!r?.ready) throw new Error('Wait for the model to finish loading.');
      if(current.current.preview)throw new Error('Place or cancel the dimension before exporting.');
      r.render();
      const p = current.current, canvas = document.createElement('canvas');
      canvas.width = 1600; canvas.height = 1100;
      const c = canvas.getContext('2d')!;
      c.fillStyle = '#FFFEFA'; c.fillRect(0,0,canvas.width,canvas.height);
      c.fillStyle = '#29352B'; c.font = 'bold 28px sans-serif'; c.fillText('LemonCAD / ' + p.model.name.slice(0,70),40,50);
      const scale = Math.min(1520 / r.renderer.domElement.width, 910 / r.renderer.domElement.height);
      const w = r.renderer.domElement.width * scale, h = r.renderer.domElement.height * scale;
      c.drawImage(r.renderer.domElement, (1600-w)/2,85,w,h);
      c.drawImage(r.overlay, (1600-w)/2,85,w,h);
      c.font = '18px sans-serif';
      c.fillText(p.model.format === 'stl' ? `Mesh measurements · source units ${p.stlUnit} · approximate` : 'STEP geometry measurements · verify suitability before manufacture',40,1030);
      if (format === 'png') {canvas.toBlob(blob => blob && download(blob, p.model.name + '.png')); return;}
      const pdf = await PDFDocument.create(), font = await pdf.embedFont(StandardFonts.Helvetica);
      const img = await pdf.embedPng(canvas.toDataURL('image/png'));
      const page = pdf.addPage([1191,842]);
      const s = Math.min(1131/img.width,752/img.height);
      page.drawImage(img,{x:(1191-img.width*s)/2,y:50,width:img.width*s,height:img.height*s});
      page.drawText('LemonCAD | Annotated model view | Not a tolerance-controlled drawing',{x:30,y:22,size:9,font,color:rgb(.16,.21,.17)});
      download(new Blob([new Uint8Array(await pdf.save())],{type:'application/pdf'}),p.model.name+'.pdf');
    }
  }),[]);
  useEffect(() => {runtime.current?.render();},[props.dimensions,props.preview,props.selected,props.unit,props.wire,props.labels,props.measuring,props.edgePicking,props.selecting]);
  useEffect(()=>{if(props.measuring)host.current?.focus();},[props.measuring]);
  useEffect(() => {
    const container = host.current!;
    const scene = new THREE.Scene(); scene.background = new THREE.Color('#F3F5EE');
    const renderer = new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
    renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    const camera = new THREE.OrthographicCamera(-100,100,100,-100,0.01,100000);
    camera.up.set(0,0,1); camera.position.set(300,-300,240);
    const controls = new TrackballControls(camera,renderer.domElement); controls.staticMoving=true; controls.rotateSpeed=3; controls.zoomSpeed=1.2; controls.panSpeed=0.5; controls.keys=['','',''];
    const overlay = document.createElement('canvas'); overlay.className='dimension-overlay';
    container.append(renderer.domElement,overlay);
    scene.add(new THREE.HemisphereLight(0xffffff,0x77816d,2.5)); scene.add(new THREE.AmbientLight(0xffffff,0.7));
    const light = new THREE.DirectionalLight(0xffffff,3); light.position.set(100,50,200); scene.add(light);
    let mesh: THREE.Mesh | undefined, edge: THREE.LineSegments | undefined, cadLines: THREE.LineSegments | undefined, ids: number[] = [], geometry: THREE.BufferGeometry | undefined;
    let faceMetadata:any[]=[],rims:Rim[]=[],cadEdges:CadEdge[]=[],features:Record<string,MeasureFeature>={};
    let viewHeight=1;let pointer:Point2|null=null;
    function project(p:number[]){const v=new THREE.Vector3(...p).project(camera);return [(v.x+1)*overlay.width/2,(1-v.y)*viewHeight*renderer.getPixelRatio()/2];}
    let extent=100, center=new THREE.Vector3(), stopped=false;
    const abort = new AbortController();
    let viewQuaternion:THREE.Quaternion|null=null,viewName:string|null=null;
    function fit(view='iso') {
      if (!mesh) return;
      const dir = view === 'front' ? new THREE.Vector3(0,-1,0) : view === 'top' ? new THREE.Vector3(0,0,1) : view === 'right' ? new THREE.Vector3(1,0,0) : new THREE.Vector3(1,-1,0.8).normalize();
      camera.up.set(0,view==='top'?1:0,view==='top'?0:1);
      camera.position.copy(center).addScaledVector(dir,extent*3); camera.zoom=1; controls.target.copy(center); resize(); controls.update();viewQuaternion=camera.quaternion.clone();viewName=view;current.current.onViewChange(view);
    }
    function normalTo(frame:SketchFrame){
      if(!mesh)return;
      const normal=new THREE.Vector3(...frame.u).cross(new THREE.Vector3(...frame.v));
      camera.up.fromArray(frame.v);camera.position.copy(center).addScaledVector(normal,extent*3);
      controls.target.copy(center);camera.zoom=1;resize();controls.update();viewQuaternion=null;current.current.onViewChange(null);
    }
    function resize() {
      const w=Math.max(1,container.clientWidth),h=Math.max(1,container.clientHeight);
      renderer.setSize(w,h); overlay.width=renderer.domElement.width; overlay.height=renderer.domElement.height;
      viewHeight=h;
      Object.assign(camera,viewportFrustum(extent,w,viewHeight));
      camera.near=Math.max(extent/10000,0.001);camera.far=extent*1000;camera.updateProjectionMatrix(); controls.handleResize(); render();
    }
    const observer = new ResizeObserver(resize); observer.observe(container);
    const ray = new THREE.Raycaster(); let down=[0,0];
    let labelBoxes:{id:string;x:number;y:number;width:number}[]=[],dragLabel:string|null=null,downCamera:{position:THREE.Vector3;up:THREE.Vector3;target:THREE.Vector3;view:THREE.Quaternion|null;name:string|null}|null=null,selectedLabel:string|null=null,draggedLabel=false;
    function placement(position:number[]):Placement{return {position,matrix:new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).toArray(),viewport:[container.clientWidth,container.clientHeight]};}
    function previewPoint(position:Point2):Point2{
      const preview=current.current.preview;if(!preview)return position;
      const ratio=renderer.getPixelRatio(),c=overlay.getContext('2d')!;
      c.font=labelFont(ratio);
      const width=c.measureText(dimensionValue(preview,current.current.unit)).width+8*ratio;
      const center=cursorLabelPosition(position,overlay.width,overlay.height,width,ratio);
      return [center[0]/overlay.width,center[1]/overlay.height];
    }
    function pointerDown(e: PointerEvent) {down=[e.clientX,e.clientY];controls.handleResize();
      const rect=container.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
      dragLabel=(e.button===0&&!current.current.preview&&!current.current.pending?labelBoxes:[]).find(b=>x>=b.x&&x<=b.x+b.width&&y>=b.y-20&&y<=b.y+8)?.id||null;
      if(dragLabel){draggedLabel=false;container.focus();e.stopImmediatePropagation();controls.enabled=false;renderer.domElement.setPointerCapture(e.pointerId);}
      // Left click also rotates; remember the view so a click (≤5px jitter) can undo the accidental nudge.
      downCamera=e.button===0&&!dragLabel?{position:camera.position.clone(),up:camera.up.clone(),target:controls.target.clone(),view:viewQuaternion?.clone()||null,name:viewName}:null;
    }
    function hitAt(e:PointerEvent){
      if(!mesh)return;
      const rect=container.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;if(y<0)return;
      ray.setFromCamera(new THREE.Vector2(x/rect.width*2-1,-y/viewHeight*2+1),camera);
      if(current.current.selecting){
        return pickSketchFace(ray,mesh,ids);
      }
      return pickCadEntity(ray,mesh,ids,rims,cadEdges,camera,rect.width,viewHeight,x,y,e.altKey||current.current.edgePicking);
    }
    function pointerUp(e: PointerEvent) {
      if(dragLabel){selectedLabel=dragLabel;render();dragLabel=null;controls.enabled=true;renderer.domElement.releasePointerCapture(e.pointerId);return;}
      if(selectedLabel){selectedLabel=null;render();}
      controls.update();
      if(downCamera&&e.button===0&&Math.hypot(e.clientX-down[0],e.clientY-down[1])<=5){camera.position.copy(downCamera.position);camera.up.copy(downCamera.up);controls.target.copy(downCamera.target);viewQuaternion=downCamera.view;controls.update();if(viewQuaternion)current.current.onViewChange(downCamera.name);render();}
      downCamera=null;
      if(e.button!==0||!mesh)return;
      if(current.current.selecting){if(Math.hypot(e.clientX-down[0],e.clientY-down[1])<=5)current.current.onSelectFace?.(hitAt(e)||null);return;}
      if(!current.current.measuring)return;
      const rect=container.getBoundingClientRect();pointer=[(e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height];
      const hit=hitAt(e),action=dimensionClick(!!hit,current.current.selected.length,!!current.current.preview||current.current.pending,Math.hypot(e.clientX-down[0],e.clientY-down[1])>5);
      if(action==='place')current.current.onPlace(placement(previewPoint(pointer)));
      else if(action==='select'&&hit)current.current.onPick(hit.id,hit.point);
    }
    function keyDown(e:KeyboardEvent){
      if(selectedLabel&&current.current.editable&&(e.key==='Delete'||e.key==='Backspace')){e.preventDefault();current.current.onLabelDelete(selectedLabel);selectedLabel=null;render();return;}
      if(!current.current.measuring&&!current.current.selecting)return;
      if(!faceMetadata.length)return;
      if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
        e.preventDefault();const index=faceMetadata.findIndex(f=>f.id===hovered),step=e.key==='ArrowRight'?1:-1;
        hovered=faceMetadata[(index+step+faceMetadata.length)%faceMetadata.length].id;render();
      }else if(e.key==='Enter'&&current.current.preview&&pointer){e.preventDefault();current.current.onPlace(placement(previewPoint(pointer)));
      }else if(e.key==='Enter'&&hovered&&!current.current.preview){e.preventDefault();const f=faceMetadata.find(f=>f.id===hovered);if(current.current.selecting)current.current.onSelectFace?.({id:hovered,point:f.centroid});else current.current.onPick(hovered,f.centroid);}
    }
    container.addEventListener('keydown',keyDown);
    renderer.domElement.addEventListener('pointerdown',pointerDown,true);renderer.domElement.addEventListener('pointerup',pointerUp);
    renderer.domElement.addEventListener('pointercancel',()=>{dragLabel=null;controls.enabled=true;});
    let previousSelection='', hovered=0;
    function pointerMove(e:PointerEvent){
      const rect=container.getBoundingClientRect();pointer=[(e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height];
      if(dragLabel){if(Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)draggedLabel=true;if(draggedLabel&&current.current.editable){const rect=container.getBoundingClientRect();current.current.onLabelMove(dragLabel,placement([(e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height]));}return;}
      controls.update();
      if(!mesh||(!current.current.measuring&&!current.current.selecting)){hovered=0;return;}
      const hit=hitAt(e),previousHovered=hovered;hovered=hit?.id||0;container.style.cursor=hit||current.current.preview||current.current.pending?'crosshair':'grab';
      if(hovered!==previousHovered||current.current.preview||current.current.pending)render();
    }
    renderer.domElement.addEventListener('pointermove',pointerMove);renderer.domElement.addEventListener('pointerleave',()=>{hovered=0;render();});
    function render() {
      if(selectedLabel&&(!current.current.labels||!current.current.dimensions.some(d=>d.id===selectedLabel)))selectedLabel=null;
      if(!current.current.measuring&&!current.current.selecting)hovered=0;
      if (mesh) {
        const selected=current.current.selected.join(',')+':'+hovered;
        if (selected!==previousSelection && geometry) {
          const colors=geometry.getAttribute('color');
          const selectedIds=new Set(current.current.selected);
          const base=new THREE.Color('#687F91'),active=new THREE.Color('#F3DF38'),hover=new THREE.Color('#D9DB89');
          for(let t=0;t<ids.length;t++) {const color=selectedIds.has(ids[t])?active:hovered===ids[t]?hover:base;for(let k=0;k<3;k++) colors.setXYZ(t*3+k,color.r,color.g,color.b);}
          colors.needsUpdate=true;previousSelection=selected;
        }
        mesh.visible=!current.current.wire;
        if(edge)edge.visible=!current.current.wire||!cadLines;
        if(cadLines)cadLines.visible=current.current.wire;
      }
      renderer.render(scene,camera);
      const c=overlay.getContext('2d')!;c.clearRect(0,0,overlay.width,overlay.height);
      if(hovered&&current.current.measuring){
        c.strokeStyle='#9A8A16';c.lineWidth=3*renderer.getPixelRatio();c.beginPath();
        for(const rim of rims.filter(r=>r.faceId===hovered)){
          const a=rim.a.clone().project(camera),b=rim.b.clone().project(camera);
          if(a.z < -1||a.z > 1||b.z < -1||b.z > 1)continue;
          c.moveTo(...project(rim.a.toArray()) as [number,number]);c.lineTo(...project(rim.b.toArray()) as [number,number]);
        }c.stroke();
      }
      const ratio=renderer.getPixelRatio();labelBoxes=[];
      for(const e of cadEdges.filter(e=>hovered===-e.id||current.current.selected.includes(-e.id))){
        c.strokeStyle='#A68E05';c.lineWidth=3*ratio;c.beginPath();e.points.forEach((p,i)=>{const v=project(p);if(i)c.lineTo(v[0],v[1]);else c.moveTo(v[0],v[1]);});c.stroke();
      }
      const layouts:{d:Dimension;pending:boolean;width:number;center:Point2;dir:Point2;draw:(center:Point2)=>void}[]=[];
      c.font=labelFont(ratio);
      [...(current.current.labels?current.current.dimensions:[]),...(current.current.preview?[current.current.preview]:[])].forEach((d,i)=>{
        const [a,b]=[d.p1,d.p2].map(project) as Point2[];
        if(d.reference_plane&&!visiblePlanarDimension(a,b,ratio))return;
        const pending=d===current.current.preview;
        const labelPlacement=pending&&pointer?pointer:d.labelPosition;
        const text=dimensionValue(d,current.current.unit);
        const width=c.measureText(text).width+8*ratio;
        const labelCenter:Point2=pending&&pointer?cursorLabelPosition(pointer,overlay.width,overlay.height,width,ratio):!pending&&d.annotation?visibleLabelCenter(project(d.annotation.label) as Point2,overlay.width,overlay.height,width,ratio):[Math.max(width/2+8*ratio,Math.min(overlay.width-width/2-8*ratio,labelPlacement?labelPlacement[0]*overlay.width:(a[0]+b[0])/2)),Math.max(24*ratio,Math.min(overlay.height-12*ratio,labelPlacement?labelPlacement[1]*overlay.height:Math.min(a[1],b[1])-45*ratio-i*30*ratio))];
        const color=pending||d.id===selectedLabel?'#A68E05':'#52633D';
        const stroke=(...segments:Point2[][])=>{c.lineWidth=(d.id===selectedLabel?2:1.2)*ratio;c.strokeStyle=color;c.beginPath();for(const [p,q] of segments){c.moveTo(p[0],p[1]);c.lineTo(q[0],q[1]);}c.stroke();};
        const arrow=(tip:Point2,from:Point2)=>{const angle=Math.atan2(tip[1]-from[1],tip[0]-from[0]),size=10*ratio;c.fillStyle=color;c.beginPath();c.moveTo(tip[0],tip[1]);for(const sign of [-1,1])c.lineTo(tip[0]-size*Math.cos(angle+sign*.28),tip[1]-size*Math.sin(angle+sign*.28));c.closePath();c.fill();};
        const label=(center:Point2)=>{
          c.textAlign='center';c.textBaseline='middle';c.lineJoin='round';
          if(pending||d.id===selectedLabel){c.fillStyle='#FFF9CB';c.fillRect(center[0]-width/2,center[1]-10*ratio,width,20*ratio);}
          else{c.lineWidth=4*ratio;c.strokeStyle='#F3F5EE';c.strokeText(text,center[0],center[1]);}
          c.fillStyle='#29352B';c.fillText(text,center[0],center[1]);c.textAlign='start';c.textBaseline='alphabetic';
        };
        if(d.type==='dia'||d.type==='rad'){
          // Leader callout: arrow on the rim, slanted leader, horizontal shoulder under the text.
          let tip=b;
          if(d.type==='dia'){
            const middle=d.p1.map((v,k)=>(v+d.p2[k])/2),centre=project(middle) as Point2;
            const feature=d.entities?.map(e=>features[String(e.kind==='edge'?-e.id:e.id)]).find(f=>f?.type==='circle'&&f.axis&&f.center&&f.radius);
            let rim:Point2[];
            if(feature){
              const axis=new THREE.Vector3(...feature.axis!).normalize(),u=new THREE.Vector3(Math.abs(axis.x)<.9?1:0,Math.abs(axis.x)<.9?0:1,0).cross(axis).normalize(),v=axis.clone().cross(u);
              rim=Array.from({length:96},(_,k)=>{const t=k/96*Math.PI*2;return project(new THREE.Vector3(...middle).addScaledVector(u,Math.cos(t)*feature.radius!).addScaledVector(v,Math.sin(t)*feature.radius!).toArray()) as Point2;});
            }else{
              const r=Math.hypot(b[0]-a[0],b[1]-a[1])/2;
              rim=Array.from({length:96},(_,k)=>{const t=k/96*Math.PI*2;return [centre[0]+Math.cos(t)*r,centre[1]+Math.sin(t)*r] as Point2;});
            }
            tip=calloutTip(centre,labelCenter,rim);
          }
          layouts.push({d,pending,width,center:labelCenter,dir:[0,labelCenter[1]<tip[1]?-1:1],draw:center=>{
            const right=center[0]>=tip[0],y=center[1]+10*ratio,elbow:Point2=[center[0]+(right?-1:1)*width/2,y],end:Point2=[center[0]+(right?1:-1)*width/2,y];
            stroke([tip,elbow],[elbow,end]);arrow(tip,elbow);label(center);
          }});
        }else if(d.type==='angle'){
          const middle:Point2=[(a[0]+b[0])/2,(a[1]+b[1])/2];
          layouts.push({d,pending,width,center:labelCenter,dir:[0,-1],draw:center=>{stroke([a,b],[middle,center]);arrow(a,b);arrow(b,a);label(center);}});
        }else{
          const annotation=pending&&d.reference_plane&&pointer?anchorDimension(d,placement(previewPoint(pointer))):d.annotation;
          const offset=annotation?{a:project(d.p1.map((v,k)=>v+annotation.offset[k])) as Point2,b:project(d.p2.map((v,k)=>v+annotation.offset[k])) as Point2}:offsetDimension(a,b,labelCenter);
          const along=[offset.b[0]-offset.a[0],offset.b[1]-offset.a[1]],length=Math.hypot(along[0],along[1]),unit:Point2=length>1e-6?[along[0]/length,along[1]/length]:[0,-1];
          const onLine=visibleLabelCenter(projectOntoLine(labelCenter,offset.a,offset.b),overlay.width,overlay.height,width,ratio),side=(onLine[0]-(offset.a[0]+offset.b[0])/2)*unit[0]+(onLine[1]-(offset.a[1]+offset.b[1])/2)*unit[1]>=0?1:-1;
          layouts.push({d,pending,width,center:onLine,dir:[unit[0]*side,unit[1]*side],draw:center=>{
            // Extension lines leave a gap at the part and overshoot the dimension line.
            const extensions=[[a,offset.a],[b,offset.b]].flatMap(([p,q])=>{const dx=q[0]-p[0],dy=q[1]-p[1],l=Math.hypot(dx,dy),gap=3*ratio,over=4*ratio;return l>gap?[[[p[0]+dx/l*gap,p[1]+dy/l*gap],[q[0]+dx/l*over,q[1]+dy/l*over]] as Point2[]]:[];});
            const t=((center[0]-offset.a[0])*along[0]+(center[1]-offset.a[1])*along[1])/(length*length||1);
            const tail:Point2[][]=t<0?[[offset.a,center]]:t>1?[[offset.b,center]]:[];
            stroke(...extensions,[offset.a,offset.b],...tail);arrow(offset.a,offset.b);arrow(offset.b,offset.a);label(center);
          }});
        }
      });
      const settled=layouts.filter(l=>!l.pending),shifts=separateLabels(settled.map(l=>({x:l.center[0]-l.width/2,y:l.center[1]-10*ratio,width:l.width,height:20*ratio,dir:l.dir})),4*ratio);
      for(const l of layouts){
        const shift=l.pending?[0,0]:shifts[settled.indexOf(l)],center:Point2=[l.center[0]+shift[0],l.center[1]+shift[1]];
        if(!l.pending)labelBoxes.push({id:l.d.id,x:(center[0]-l.width/2)/ratio,y:center[1]/ratio+10,width:l.width/ratio});
        l.draw(center);
      }
    }
    controls.addEventListener('change',()=>{if(viewQuaternion&&1-Math.abs(camera.quaternion.dot(viewQuaternion))>1e-8){viewQuaternion=null;current.current.onViewChange(null);}render();});
    controls.addEventListener('end',()=>controls.update());
    function pickSketchEdge(x:number,y:number,frame:SketchFrame):PlaneEdge|null{
      if(!mesh)return null;
      const eligible=cadEdges.filter(e=>planeEdge(e,frame));
      const hit=pickEdge(ray,mesh,eligible,camera,container.clientWidth,container.clientHeight,x,y);
      const found=hit&&eligible.find(e=>e.id===-hit.id);
      return found?planeEdge(found,frame):null;
    }
    runtime.current={pickSketchEdge,camera,controls,renderer,overlay,fit,normalTo,render,ready:false};
    async function load() {
      let faces: any[]=[],measureFeatures:Record<string,MeasureFeature>={};
      if(current.current.model.format==='stl') {
        const response=await fetch(fileURL(current.current.model.file_id),{signal:abort.signal});if(!response.ok) throw new Error('STL file unavailable.');
        geometry=new STLLoader().parse(await response.arrayBuffer());
        geometry.scale(current.current.stlUnit==='in'?25.4:1,current.current.stlUnit==='in'?25.4:1,current.current.stlUnit==='in'?25.4:1);
      } else {
        const response=await fetch(fileURL(current.current.model.result.mesh),{signal:abort.signal});if(!response.ok) throw new Error('Model unavailable. Reload or check sharing access.');
        const data=await response.json(); const indexed=new THREE.BufferGeometry();indexed.setAttribute('position',new THREE.Float32BufferAttribute(data.positions,3));indexed.setIndex(data.indices);geometry=indexed.toNonIndexed(); indexed.dispose();ids=data.tri_face;faces=data.faces;cadEdges=data.edges||[];measureFeatures=data.measure_features||{};faceMetadata=faces;rims=cylinderRims(geometry,ids,faces);
      }
      if(stopped) {geometry.dispose();return;}
      const positions=geometry.getAttribute('position');
      if(!positions.count || positions.count > 6000000) throw new Error('Mesh is empty, too large or contains invalid coordinates.');
      for(const coordinate of positions.array)if(!Number.isFinite(coordinate))throw new Error('Mesh is empty, too large or contains invalid coordinates.');
      geometry.computeBoundingBox();const box=geometry.boundingBox!;box.getCenter(center);extent=box.getSize(new THREE.Vector3()).length();
      if(!Number.isFinite(extent)||extent<=0) throw new Error('Model has no measurable extent.');
      const colors=new Float32Array(positions.count*3), base=new THREE.Color('#687F91');for(let i=0;i<positions.count;i++){const offset=i*3;colors[offset]=base.r;colors[offset+1]=base.g;colors[offset+2]=base.b;}
      geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));geometry.computeVertexNormals();
      mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({vertexColors:true,metalness:.15,roughness:.65,side:THREE.DoubleSide}));scene.add(mesh);
      edge=new THREE.LineSegments(new THREE.EdgesGeometry(geometry,30),new THREE.LineBasicMaterial({color:0x000000}));scene.add(edge);
      if(cadEdges.length){
        const segments:number[]=[];
        for(const e of cadEdges)for(let i=1;i<e.points.length;i++)segments.push(...e.points[i-1],...e.points[i]);
        if(segments.length){const lines=new THREE.BufferGeometry();lines.setAttribute('position',new THREE.Float32BufferAttribute(segments,3));cadLines=new THREE.LineSegments(lines,new THREE.LineBasicMaterial({color:0x29352B,depthTest:false}));cadLines.renderOrder=1;scene.add(cadLines);}
      }
      fit();const saved=current.current.model.state?.camera;
      if(saved?.position?.length===3 && saved?.target?.length===3 && [...saved.position,...saved.target,saved.zoom].every(Number.isFinite)){camera.position.fromArray(saved.position);if(saved.up?.length===3&&saved.up.every(Number.isFinite))camera.up.fromArray(saved.up);controls.target.fromArray(saved.target);camera.zoom=Math.max(.01,Math.min(100,saved.zoom));camera.updateProjectionMatrix();controls.update();viewQuaternion=null;current.current.onViewChange(null);}
      features=measureFeatures;runtime.current.ready=true;current.current.onReady(faces,measureFeatures); render();
    }
    load().catch(e=>{if(!stopped) current.current.onError(e.message);});
    return()=>{stopped=true;abort.abort();observer.disconnect();container.removeEventListener('keydown',keyDown);controls.dispose();geometry?.dispose();if(mesh)(mesh.material as THREE.Material).dispose();if(edge){edge.geometry.dispose();(edge.material as THREE.Material).dispose();}if(cadLines){cadLines.geometry.dispose();(cadLines.material as THREE.Material).dispose();}renderer.dispose();container.replaceChildren();runtime.current=null;};
  },[props.model.file_id,props.stlUnit]);
  return <div className="canvas-host" ref={host} tabIndex={0} role="application" aria-label={`Interactive model of ${props.model.name}. Drag to orbit, scroll to zoom. ${props.selecting?'Click a planar face to sketch.':'Click inside a hole or on a face to measure; use Pick edge or hold Option or Alt for an edge.'} Move the mouse and click empty space to place the dimension. Click a dimension and press Delete to remove it. Keyboard: left and right arrows highlight faces; Enter selects; Escape clears selection.`}/>;
});
