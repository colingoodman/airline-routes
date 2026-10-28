// Batched route drawing: no per-route Leaflet layers or event handlers.
// Coordinates use the same spherical Mercator projection as Leaflet's default CRS.
export function projectRoutePath(path){
 const points=[];let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
 for(const [lat,lon] of path){const sine=Math.sin(Math.max(-85.0511287798,Math.min(85.0511287798,lat))*Math.PI/180),x=(lon+180)/360*256,y=(.5-Math.log((1+sine)/(1-sine))/(4*Math.PI))*256;points.push([x,y]);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
 return {points,minX,maxX,minY,maxY};
}
export function segmentDistanceSquared(x,y,ax,ay,bx,by){
 const dx=bx-ax,dy=by-ay,t=dx||dy?Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))):0;
 return (x-ax-t*dx)**2+(y-ay-t*dy)**2;
}
export function simplifyRoutePath(points,tolerance){
 if(points.length<=2)return points;
 const keep=new Uint8Array(points.length),stack=[[0,points.length-1]],limit=tolerance*tolerance;keep[0]=keep[points.length-1]=1;
 while(stack.length){const [first,last]=stack.pop();let max=limit,at=-1;const a=points[first],b=points[last];for(let i=first+1;i<last;i++){const p=points[i],d=segmentDistanceSquared(p[0],p[1],a[0],a[1],b[0],b[1]);if(d>max){max=d;at=i;}}if(at>=0){keep[at]=1;stack.push([first,at],[at,last]);}}
 return points.filter((_,i)=>keep[i]);
}
export function clipRouteSegment(ax,ay,bx,by,width,height){
 let t0=0,t1=1;const dx=bx-ax,dy=by-ay;
 for(const [p,q] of [[-dx,ax],[dx,width-ax],[-dy,ay],[dy,height-ay]]){if(p===0){if(q<0)return null;}else{const t=q/p;if(p<0){if(t>t1)return null;t0=Math.max(t0,t);}else{if(t<t0)return null;t1=Math.min(t1,t);}}}
 return [ax+t0*dx,ay+t0*dy,ax+t1*dx,ay+t1*dy];
}
export function routeWorldCopies(path,scale,left,right){
 const world=256*scale,first=Math.ceil((left-path.maxX*scale)/world),last=Math.floor((right-path.minX*scale)/world);
 return Array.from({length:Math.max(0,last-first+1)},(_,i)=>(first+i)*world);
}
export function buildRouteHitIndex(pieces,width,height,cell=32){
 const grid=new Map(),segments=[];
 for(let piece=0;piece<pieces.length;piece++){
  const points=pieces[piece].points;
  for(let i=1;i<points.length;i++){
   const segment=clipRouteSegment(...points[i-1],...points[i],width,height);if(!segment)continue;
   const id=segments.length;segments.push([...segment,piece]);const [ax,ay,bx,by]=segment,steps=Math.max(1,Math.ceil(Math.max(Math.abs(bx-ax),Math.abs(by-ay))/(cell/2)));let previous='';
   for(let step=0;step<=steps;step++){const key=Math.floor((ax+(bx-ax)*step/steps)/cell)+','+Math.floor((ay+(by-ay)*step/steps)/cell);if(key===previous)continue;previous=key;if(!grid.has(key))grid.set(key,[]);grid.get(key).push(id);}
  }
 }
 return {grid,segments,pieces,cell};
}
export function nearestRoute(index,x,y,radius=6){
 if(!index)return null;
 const cx=Math.floor(x/index.cell),cy=Math.floor(y/index.cell),reach=Math.ceil(radius/index.cell),visited=new Set();let distance=radius*radius,result=null;
 for(let dx=-reach;dx<=reach;dx++)for(let dy=-reach;dy<=reach;dy++)for(const id of index.grid.get((cx+dx)+','+(cy+dy))||[]){if(visited.has(id))continue;visited.add(id);const [ax,ay,bx,by,piece]=index.segments[id],d=segmentDistanceSquared(x,y,ax,ay,bx,by);if(d<=distance){distance=d;result=index.pieces[piece];}}
 return result;
}
export function routeBufferOffset(view,bounds,zoom){
 if(!view||view.zoom!==zoom||bounds.min.x<view.left||bounds.min.y<view.top||bounds.max.x>view.left+view.width||bounds.max.y>view.top+view.height)return null;
 return {x:bounds.min.x-view.left,y:bounds.min.y-view.top};
}
export function createRouteLayer(L,{popup,onHover=()=>{},onDraw=()=>{},onReuse=()=>{}}){
 return new (L.Layer.extend({
  options:{pane:'routes',padding:.2},
  initialize(){this.entries=[];this.simplified=new WeakMap();},
  onAdd(map){
   this.map=map;this.canvas=L.DomUtil.create('canvas','leaflet-route-batch leaflet-zoom-hide');this.hoverCanvas=L.DomUtil.create('canvas','leaflet-route-hover leaflet-zoom-hide');
   for(const canvas of [this.canvas,this.hoverCanvas]){canvas.style.position='absolute';canvas.style.pointerEvents='none';this.getPane().appendChild(canvas);}
   map.on('moveend zoomend resize',this.redraw,this);map.on('mousemove',this.mousemove,this);map.on('click',this.click,this);map.on('movestart zoomstart',this.startMove,this);map.on('mouseout',this.clearHover,this);this.redraw();
  },
  onRemove(map){this.popup?.remove();cancelAnimationFrame(this.frame);cancelAnimationFrame(this.hoverFrame);map.off('moveend zoomend resize',this.redraw,this);map.off('mousemove',this.mousemove,this);map.off('click',this.click,this);map.off('movestart zoomstart',this.startMove,this);map.off('mouseout',this.clearHover,this);this.canvas.remove();this.hoverCanvas.remove();this.index=null;},
  setData(entries){this.popup?.remove();this.popup=null;this.entries=entries;this.index=null;this.viewport=null;this.clearHover();this.redraw();return this;},
  redraw(event){if(event?.type==='moveend'&&!this.frame){const offset=routeBufferOffset(this.viewport,this.map.getPixelBounds(),this.map.getZoom());if(offset){this.px=offset.x;this.py=offset.y;this.moving=false;onReuse();return;}}if(this.frame)return;this.frame=requestAnimationFrame(()=>{this.frame=null;this.draw();});},
  draw(){
   const start=performance.now(),map=this.map,size=map.getSize(),px=Math.ceil(size.x*this.options.padding),py=Math.ceil(size.y*this.options.padding),width=size.x+2*px,height=size.y+2*py,dpr=Math.min(devicePixelRatio||1,2),zoom=map.getZoom(),scale=2**zoom,bounds=map.getPixelBounds(),left=bounds.min.x-px,top=bounds.min.y-py,position=map.containerPointToLayerPoint(L.point(-px,-py));
   this.px=px;this.py=py;this.viewport={left,top,width,height,zoom};
   for(const canvas of [this.canvas,this.hoverCanvas]){L.DomUtil.setPosition(canvas,position);canvas.style.width=width+'px';canvas.style.height=height+'px';const w=Math.ceil(width*dpr),h=Math.ceil(height*dpr);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);}
   if(this.zoom!==zoom){this.zoom=zoom;this.simplified=new WeakMap();}
   const pieces=[],batches=new Map();let vertices=0;
   for(const entry of this.entries)for(const path of entry.geometry.projected){
    if(path.maxY*scale<top||path.minY*scale>top+height)continue;
    let simple=this.simplified.get(path);if(!simple){simple=simplifyRoutePath(path.points,.65/scale);this.simplified.set(path,simple);}
    for(const offset of routeWorldCopies(path,scale,left,left+width)){
     const points=simple.map(([x,y])=>[x*scale+offset-left,y*scale-top]),piece={points,entry};pieces.push(piece);vertices+=points.length;
     const key=entry.color+'|'+entry.seasonal+'|'+!!entry.emphasis;if(!batches.has(key))batches.set(key,{color:entry.color,seasonal:entry.seasonal,emphasis:entry.emphasis,pieces:[]});batches.get(key).pieces.push(piece);
    }
   }
   const ctx=this.canvas.getContext('2d');ctx.lineWidth=1.15;ctx.globalAlpha=.36;
   for(const batch of [...batches.values()].sort((a,b)=>!!a.emphasis-!!b.emphasis)){ctx.lineWidth=batch.emphasis?1.6:1.15;ctx.globalAlpha=batch.emphasis?.6:.32;ctx.beginPath();ctx.strokeStyle=batch.color;ctx.setLineDash(batch.seasonal?[4,5]:[]);for(const piece of batch.pieces){piece.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));}ctx.stroke();}
   this.index=buildRouteHitIndex(pieces,width,height);this.hovered=null;this.moving=false;
   onDraw(performance.now()-start,{pieces:pieces.length,vertices,segments:this.index.segments.length,batches:batches.size,canvas_pixels:[this.canvas,this.hoverCanvas].reduce((n,c)=>n+c.width*c.height,0)});
  },
  startMove(){this.moving=true;this.clearHover();},
  mousemove(event){if(this.moving)return;this.pointer=event.containerPoint;if(this.hoverFrame)return;this.hoverFrame=requestAnimationFrame(()=>{this.hoverFrame=null;if(!this.index)return;const piece=nearestRoute(this.index,this.pointer.x+this.px,this.pointer.y+this.py);if(piece?.entry===this.hovered)return;this.clearHover();if(!piece)return;this.hovered=piece.entry;onHover(piece.entry.connection);const ctx=this.hoverCanvas.getContext('2d');ctx.strokeStyle=piece.entry.color;ctx.lineWidth=3;ctx.globalAlpha=.9;ctx.setLineDash(piece.entry.seasonal?[4,5]:[]);ctx.beginPath();for(const path of this.index.pieces)if(path.entry===piece.entry)path.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();});},
  highlight(predicate){this.clearHover();if(!this.index)return;const ctx=this.hoverCanvas.getContext('2d');ctx.lineWidth=3;ctx.globalAlpha=.95;for(const piece of this.index.pieces)if(predicate(piece.entry)){ctx.beginPath();ctx.strokeStyle=piece.entry.color;ctx.setLineDash(piece.entry.seasonal?[4,5]:[]);piece.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();}},
  clearHover(){onHover(null);this.hovered=null;cancelAnimationFrame(this.hoverFrame);this.hoverFrame=null;if(this.hoverCanvas){const ctx=this.hoverCanvas.getContext('2d');ctx.clearRect(0,0,this.hoverCanvas.width,this.hoverCanvas.height);}},
  click(event){if(this.moving)return;const piece=nearestRoute(this.index,event.containerPoint.x+this.px,event.containerPoint.y+this.py);if(piece)this.popup=L.popup().setLatLng(event.latlng).setContent(popup(piece.entry.connection)).openOn(this.map);}
 }))();
}
