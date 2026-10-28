const dataIndexes=new WeakMap();
export function indexData(data) {
 if(dataIndexes.has(data))return dataIndexes.get(data);
 const index={ models:new WeakMap(), sources:new Map((data.sources||[]).map(s=>[s.id,s])), airports: new Map(data.airports.map(a=>[a.id,a])), airlines:new Map(data.airlines.map(a=>[a.id,a])), alliances:new Map(data.alliances.map(a=>[a.id,a])), brands:new Map((data.service_brand_models||[]).map(b=>[b.id,b])) };
 dataIndexes.set(data,index);return index;
}
export function routeModel(index,route) {
 if(index.models.has(route))return index.models.get(route);
 const airline=index.airlines.get(route.airline_id),brand=index.brands.get(route.service_brand_id);
 const value={low_cost:typeof brand?.low_cost==='boolean'?brand.low_cost:typeof airline?.low_cost==='boolean'?airline.low_cost:null,regional:typeof brand?.regional==='boolean'?brand.regional:typeof airline?.regional==='boolean'?airline.regional:null};index.models.set(route,value);return value;
}
function modelMatches(model,state) {
 const lowCost=state.lowCost||'all';
 return (lowCost==='all'||lowCost==='yes'&&model.low_cost===true||lowCost==='no'&&model.low_cost===false||lowCost==='unknown'&&model.low_cost===null) && (!state.regional||model.regional===true);
}
export function filterRoutes(data,state) {
 const ix=indexData(data),typed=state.regional||(state.lowCost&&state.lowCost!=='all');
 return data.routes.filter(r=>{
  const a=ix.airlines.get(r.airline_id);
  return state.alliances.has(a.alliance_id) && (!state.airlines.size || state.airlines.has(a.id)) && airportMatches(r,state) && (state.seasonal || r.status!=='seasonal') && (state.charter || r.service_type!=='charter') && (!typed||modelMatches(routeModel(ix,r),state));
 });
}
export function airlineOptions(data,state) {
 const ids=new Set(filterRoutes(data,{...state,airlines:new Set(),airports:new Set()}).map(r=>r.airline_id));
 return data.airlines.filter(a=>ids.has(a.id));
}
export function visibleHubs(data,state) {
 const ix=indexData(data),typed=state.regional||(state.lowCost&&state.lowCost!=='all');
 const keys=typed?new Set(filterRoutes(data,{...state,airports:new Set()}).map(r=>r.airline_id+'|'+r.hub_airport_id)):null;
 return data.hubs.filter(h=>{
  const a=ix.airlines.get(h.airline_id);
  return state.alliances.has(a.alliance_id)&&(!state.airlines.size||state.airlines.has(a.id))&&(!keys||keys.has(h.airline_id+'|'+h.airport_id));
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
 for(const r of routes){const a=r.hub_airport_id,b=r.destination_airport_id;const k=r.airline_id+'|'+(a<b?a+'|'+b:b+'|'+a);if(!result.has(k))result.set(k,{...r,services:[]});result.get(k).services.push(r);}
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

// Airport modes describe source-record endpoints, not independently verified flight direction.
export function airportMatches(route,state){
 const ids=state.airports;if(!ids.size)return true;
 const hub=ids.has(route.hub_airport_id),destination=ids.has(route.destination_airport_id);
 return state.airportMode==='between'?ids.size>=2&&hub&&destination:state.airportMode==='hub'?hub:hub||destination;
}
export function defaultExplorerState(data){
 return {alliances:new Set(data.alliances.map(a=>a.id)),airlines:new Set(),airports:new Set(),airportMode:'touches',seasonal:true,charter:false,lowCost:'all',regional:false,focus:'',colorBy:'alliance',labels:'auto',airlineSort:'name',destinationSort:'name',view:'destinations',countries:new Set(),regions:new Set(),geoMode:'either',minKm:0,maxKm:20020,unit:'km',compareA:'',compareB:'',compareShow:new Set(['shared','a','b'])};
}
export function explorerParams(state,data){
 const p=new URLSearchParams();
 for(const key of ['alliances','airlines','airports','countries','regions','compareShow']){
  const ids=[...state[key]].sort();if(key==='alliances'?ids.length!==data.alliances.length:key==='compareShow'?ids.join(',')!=='a,b,shared':ids.length)p.set(key,ids.join(','));
 }
 for(const [key,param,def] of [['airportMode','airport_mode','touches'],['focus','focus',''],['colorBy','color','alliance'],['labels','labels','auto'],['airlineSort','airline_sort','name'],['destinationSort','destination_sort','name'],['view','view','destinations'],['geoMode','geo_mode','either'],['unit','unit','km'],['compareA','compare_a',''],['compareB','compare_b','']])if(state[key]!==def)p.set(param,state[key]);
 if(!state.seasonal)p.set('seasonal','0');if(state.charter)p.set('charter','1');if(state.lowCost!=='all')p.set('low_cost',state.lowCost);if(state.regional)p.set('regional','1');if(state.minKm)p.set('min_km',state.minKm);if(state.maxKm!==20020)p.set('max_km',state.maxKm);return p;
}
export function restoreExplorerState(data,query){
 const s=defaultExplorerState(data),p=new URLSearchParams(query);
 for(const [key,valid] of [['alliances',data.alliances.map(a=>a.id)],['airlines',data.airlines.map(a=>a.id)],['countries',data.airports.map(a=>a.country)],['regions',['AF','AN','AS','EU','NA','OC','SA','unknown']],['compareShow',['shared','a','b']]])if(p.has(key)){const allowed=new Set(valid);s[key]=new Set(p.get(key).split(',').filter(x=>allowed.has(x)));}
 if(p.has('airports'))s.airports=new Set(canonicalAirportIds(data.airports,p.get('airports').split(',')));
 for(const [key,param,allowed] of [['airportMode','airport_mode',['touches','between','hub']],['colorBy','color',['alliance','airline']],['labels','labels',['off','auto','on']],['airlineSort','airline_sort',['name','destinations','hubs']],['destinationSort','destination_sort',['name','code','country','distance','airlines']],['view','view',['destinations','evidence']],['geoMode','geo_mode',['either','both','hub','destination']],['unit','unit',['km','mi']]])if(allowed.includes(p.get(param)))s[key]=p.get(param);
 const airports=new Set(data.airports.map(a=>a.id)),airlines=new Set(data.airlines.map(a=>a.id));if(airports.has(p.get('focus')))s.focus=p.get('focus');for(const key of ['compareA','compareB']){const id=p.get(key==='compareA'?'compare_a':'compare_b');if(airlines.has(id))s[key]=id;}
 s.seasonal=p.get('seasonal')!=='0';s.charter=p.get('charter')==='1';s.regional=p.get('regional')==='1';if(['yes','no','unknown'].includes(p.get('low_cost')))s.lowCost=p.get('low_cost');
 for(const [key,param] of [['minKm','min_km'],['maxKm','max_km']])if(p.has(param)&&Number.isFinite(Number(p.get(param))))s[key]=Math.max(0,Math.min(20020,Number(p.get(param))));if(s.minKm>s.maxKm)[s.minKm,s.maxKm]=[s.maxKm,s.minKm];return s;
}
