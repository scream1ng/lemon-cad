export function viewportFrustum(extent:number,width:number,height:number){
  const aspect=Math.max(1,width)/Math.max(1,height);
  const halfHeight=extent*.6/Math.min(1,aspect);
  return {left:-halfHeight*aspect,right:halfHeight*aspect,top:halfHeight,bottom:-halfHeight};
}

export function visibleLabelCenter(point:[number,number],width:number,height:number,labelWidth:number,ratio:number):[number,number]{
  return [Math.max(labelWidth/2+8*ratio,Math.min(width-labelWidth/2-8*ratio,point[0])),Math.max(24*ratio,Math.min(height-12*ratio,point[1]))];
}
