export function indexData(data) {
 return { airports: new Map(data.airports.map(a=>[a.id,a])), airlines:new Map(data.airlines.map(a=>[a.id,a])), alliances:new Map(data.alliances.map(a=>[a.id,a])) };
}
export function filterRoutes(data,state) {
 const ix=indexData(data);
 return data.routes.filter(r=>{
  const a=ix.airlines.get(r.airline_id);
  return state.alliances.has(a.alliance_id) && (!state.airlines.size || state.airlines.has(a.id)) && (!state.airports.size || state.airports.has(r.hub_airport_id)||state.airports.has(r.destination_airport_id)) && (state.seasonal || r.status!=='seasonal') && (state.charter || r.service_type!=='charter');
 });
}
export function visibleHubs(data,state) {
 const ix=indexData(data);
 return data.hubs.filter(h=>{
  const a=ix.airlines.get(h.airline_id);
  return state.alliances.has(a.alliance_id)&&(!state.airlines.size||state.airlines.has(a.id));
 });
}
// Spherical interpolation avoids misleading straight lat/lon lines and splits at the dateline.
export function greatCircle(a,b,steps=48) {
 const rad=Math.PI/180, av=[Math.cos(a.latitude*rad)*Math.cos(a.longitude*rad),Math.cos(a.latitude*rad)*Math.sin(a.longitude*rad),Math.sin(a.latitude*rad)],bv=[Math.cos(b.latitude*rad)*Math.cos(b.longitude*rad),Math.cos(b.latitude*rad)*Math.sin(b.longitude*rad),Math.sin(b.latitude*rad)];
 const omega=Math.acos(Math.max(-1,Math.min(1,av.reduce((s,x,i)=>s+x*bv[i],0)))),sin=Math.sin(omega),segments=[[]];
 for(let i=0;i<=steps;i++){
  const t=i/steps,aa=sin>1e-8?Math.sin((1-t)*omega)/sin:1-t,bb=sin>1e-8?Math.sin(t*omega)/sin:t,v=av.map((x,j)=>aa*x+bb*bv[j]);
  const lat=Math.atan2(v[2],Math.hypot(v[0],v[1]))/rad,lon=Math.atan2(v[1],v[0])/rad;
  const seg=segments.at(-1),prev=seg.at(-1);
  if(prev && Math.abs(lon-prev[1])>180){
   const unwrapped=lon+(lon<prev[1]?360:-360),edge=prev[1]>0?180:-180,frac=(edge-prev[1])/(unwrapped-prev[1]),cross=prev[0]+frac*(lat-prev[0]);
   seg.push([cross,edge]);segments.push([[cross,-edge]]);
  }
  segments.at(-1).push([lat,lon]);
 }
 return segments.filter(s=>s.length>1);
}
export function uniqueConnections(routes) {
 const result=new Map();
 for(const r of routes){const pair=[r.hub_airport_id,r.destination_airport_id].sort();const k=r.airline_id+'|'+pair.join('|');if(!result.has(k))result.set(k,{...r,services:[]});result.get(k).services.push(r);}
 return [...result.values()];
}

// Include adjacent worlds during dragging; recompute after every completed pan.
export function worldOffsets(west,east) {
 const margin=Math.max(1,Math.ceil((east-west)/360));
 const first=Math.floor((west+180)/360)-margin,last=Math.floor((east+180)/360)+margin;
 return Array.from({length:last-first+1},(_,i)=>(first+i)*360);
}
export function shiftedPaths(paths,offset,west,east) {
 return paths.filter(p=>Math.max(...p.map(x=>x[1]))+offset>=west && Math.min(...p.map(x=>x[1]))+offset<=east).map(p=>p.map(([lat,lon])=>[lat,lon+offset]));
}
// The complement of the largest gap is the tightest circular airport extent.
export function fitPositions(points,center=0) {
 if(!points.length)return [];
 const longs=[...new Set(points.map(([,lon])=>((lon%360)+360)%360))].sort((a,b)=>a-b);
 let gap=-1,start=longs[0];
 for(let i=0;i<longs.length;i++){
  const next=longs[(i+1)%longs.length]+(i===longs.length-1?360:0),size=next-longs[i];
  if(size>gap){gap=size;start=next%360;}
 }
 const shifted=points.map(([lat,lon])=>{let x=((lon%360)+360)%360;if(x<start)x+=360;return[lat,x];});
 const middle=(Math.min(...shifted.map(x=>x[1]))+Math.max(...shifted.map(x=>x[1])))/2,offset=360*Math.round((center-middle)/360);
 return shifted.map(([lat,lon])=>[lat,lon+offset]);
}
export function routeBounds(points,paths,center=0) {
 const fitted=fitPositions(points,center);if(!fitted.length)return [];
 let south=Infinity,north=-Infinity,west=Infinity,east=-Infinity;
 for(const [lat,lon] of fitted){south=Math.min(south,lat);north=Math.max(north,lat);west=Math.min(west,lon);east=Math.max(east,lon);}
 const middle=(west+east)/2;
 for(const path of paths)for(const [lat,lon] of path){const x=lon+360*Math.round((middle-lon)/360);south=Math.min(south,lat);north=Math.max(north,lat);west=Math.min(west,x);east=Math.max(east,x);}
 return [[south,west],[north,east]];
}
export function canonicalAirportIds(airports,ids) {
 const lookup=new Map();
 for(const airport of airports){lookup.set(airport.id,airport.id);for(const former of airport.former_iata_codes||[])lookup.set(former,airport.id);}
 return ids.map(id=>lookup.get(id)).filter(Boolean);
}
