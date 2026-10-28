import {indexData,filterRoutes,visibleHubs,greatCircle,uniqueConnections,routeBounds,canonicalAirportIds,airlineOptions,defaultExplorerState,explorerParams,restoreExplorerState} from './model.mjs?v=20261027-performance';
import {measure,recordMetric,markReady} from './perf.mjs?v=20261027-performance';
import {createRouteLayer,projectRoutePath} from './route-renderer.mjs?v=20261027-performance';
import {decodeMapData,prepareDownload} from './runtime.mjs?v=20261027-performance';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state;
let data,ix,map,routeLayer,pins,pinRenderer,baseRenderer,worldGeo,filtered=[],connections=[],relevant=new Set(),hubIds=new Set(),servingByAirport=new Map(),eligibleAirlines=[],page=0;const PAGE_SIZE=75;const worldLayers=new Map(),routeGeometry=new Map(),pinLayers=new Map(),eligibilityCache=new Map();
const airportCode=a=>a.iata||a.icao||a.local_code||a.ident||a.id;
const airlineCode=a=>a.iata||a.icao||(a.id.startsWith('wiki:')?'':a.id.replace(/^icao:/,''));
const airportLabel=a=>`${airportCode(a)} · ${a.city||a.name}`;
const hubRole=h=>({hub:'hub',secondary_hub:'secondary hub',operating_base:'operating base',primary_base:'primary operating base',focus_city:'focus city'}[h.kind]||h.kind.replaceAll('_',' '));
const airlineColor=id=>ix.alliances.get(ix.airlines.get(id).alliance_id).color;
const sourceLink=id=>{const s=ix.sources.get(id);return s?`<a href="${esc(s.url)}" target="_blank" rel="noopener">Wikipedia ↗</a>`:'—';};
function renderAllianceOptions(){
 $('alliances').innerHTML=data.alliances.map(a=>`<label class="option"><input type="checkbox" data-alliance="${a.id}" ${state.alliances.has(a.id)?'checked':''}><span class="dot" style="background:${a.color}"></span>${esc(a.name)}<small>${a.kind==='alliance'?`${data.airlines.filter(x=>x.alliance_id===a.id&&x.membership_type==='full_member').length} members + ${data.airlines.filter(x=>x.alliance_id===a.id&&x.membership_type!=='full_member').length} related`:data.airlines.filter(x=>x.alliance_id===a.id).length}</small></label>`).join('');
}
function renderAirlines(){return measure('airlineChoices',renderAirlinesImpl);}
function renderAirlinesImpl(){
 const q=$('airline-search').value.toLowerCase(),eligible=eligibleAirlines,eligibleIds=new Set(eligible.map(a=>a.id)),available=[...eligible,...data.airlines.filter(a=>state.airlines.has(a.id)&&!eligibleIds.has(a.id))];
 $('airlines').innerHTML=available.filter(a=>(a.name+' '+a.id).toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name)).map(a=>`<label class="option"><input type="checkbox" data-airline="${a.id}" ${state.airlines.has(a.id)?'checked':''}><span class="dot" style="background:${airlineColor(a.id)}"></span>${esc(a.name)}<small>${a.membership_type==='connecting_partner'?'Partner · ':a.membership_type==='affiliate'?'Affiliate · ':''}${a.low_cost===true?'LCC · ':''}${a.regional===true?'Regional · ':''}${esc(airlineCode(a))}${eligibleIds.has(a.id)?'':' · no matching services'}</small></label>`).join('')||'<p class="hint">No matching airlines.</p>';
 $('airline-count').textContent=state.airlines.size?`${state.airlines.size} selected`:`All ${available.length}`;
}
function renderAirports(){
 const q=$('airport-search').value.trim().toLowerCase(),hubs=hubIds;
 const choices=data.airports.filter(a=>q?(a.id+' '+(a.former_iata_codes||[]).join(' ')+' '+(a.icao||'')+' '+(a.ident||'')+' '+(a.local_code||'')+' '+a.city+' '+a.name+' '+a.country).toLowerCase().includes(q):hubs.has(a.id)).sort((a,b)=>(b.id.toLowerCase()===q)-(a.id.toLowerCase()===q)||a.id.localeCompare(b.id));
 $('airports').innerHTML=choices.slice(0,60).map(a=>`<label class="option"><input type="checkbox" data-airport="${a.id}" ${state.airports.has(a.id)?'checked':''}>${esc(airportLabel(a))}<small>${hubs.has(a.id)?'hub/base':''}</small></label>`).join('')+(choices.length>60?'<p class="hint">Showing 60 results. Refine your search.</p>':'')||'<p class="hint">No matching airports.</p>';
 $('airport-search-results').hidden=!q;$('airport-search-results').innerHTML=q?choices.slice(0,12).map(a=>`<button data-inspect-airport="${a.id}">${esc(airportLabel(a))} <small>${esc(a.name)}</small></button>`).join('')||'<p>No matching airports.</p>':'';
 $('airport-selection').innerHTML=[...state.airports].map(id=>`<button class="tag" data-remove-airport="${id}" aria-label="Remove ${id} airport filter">${esc(airportCode(ix.airports.get(id)))} ×</button>`).join('');
}
function renderTable(){
 const start=page*PAGE_SIZE,rows=filtered.slice(start,start+PAGE_SIZE);
 $('route-table').innerHTML=rows.map(r=>{
  const a=ix.airlines.get(r.airline_id),o=ix.airports.get(r.hub_airport_id),d=ix.airports.get(r.destination_airport_id);
  return `<tr><td><span class="dot" style="background:${airlineColor(a.id)}"></span> ${esc(a.name)}${r.service_brand!==a.name?`<small>${esc(r.service_brand)}</small>`:''}</td><td><button data-select-airport="${o.id}" title="Filter routes touching ${o.id}">${esc(airportCode(o))}</button> ${esc(o.city||o.name)}</td><td><button data-select-airport="${d.id}" title="Filter routes touching ${d.id}">${esc(airportCode(d))}</button> ${esc(d.city||d.name)}</td><td>${r.status==='seasonal'?'Seasonal':'Listed'}${r.service_type==='charter'?' charter':''}${r.note?`<small>${esc(r.note)}</small>`:''}</td><td>${sourceLink(r.source_id)}</td></tr>`;
 }).join('');
 $('table-count').textContent=`${filtered.length.toLocaleString()} source entries`;
 $('page-label').textContent=filtered.length?`${start+1}–${Math.min(start+PAGE_SIZE,filtered.length)} of ${filtered.length.toLocaleString()}`:'0 results';
 $('previous').disabled=page===0;$('next').disabled=start+PAGE_SIZE>=filtered.length;$('empty').hidden=filtered.length>0;
}
function selectAirport(id){state.airports=new Set([id]);page=0;update();}
function renderWorld(){
 if(!worldGeo)return;
 const bounds=map.getBounds().pad(.2),first=Math.ceil((bounds.getWest()-180)/360),last=Math.floor((bounds.getEast()+180)/360),offsets=Array.from({length:last-first+1},(_,i)=>(first+i)*360);
 for(const [offset,layer] of worldLayers)if(!offsets.includes(offset)){map.removeLayer(layer);worldLayers.delete(offset);}
 for(const offset of offsets)if(!worldLayers.has(offset)){
  const layer=L.geoJSON(worldGeo,{pane:'land',renderer:baseRenderer,coordsToLatLng:c=>L.latLng(c[1],c[0]+offset),style:{color:'#b6c6d4',weight:.6,fillColor:'#f8fafb',fillOpacity:1},interactive:false}).addTo(map);
  worldLayers.set(offset,layer);
 }
}
function geometryFor(a,b){
 const key=a.id<b.id?a.id+'|'+b.id:b.id+'|'+a.id;
 if(!routeGeometry.has(key)){const paths=greatCircle(a,b);routeGeometry.set(key,{paths,projected:paths.map(projectRoutePath)});}
 return routeGeometry.get(key);
}
function routePopup(r){
 const a=ix.airports.get(r.hub_airport_id),b=ix.airports.get(r.destination_airport_id);
 return `<strong>${esc(ix.airlines.get(r.airline_id).name)}</strong><br>${esc(airportLabel(a))} — ${esc(airportLabel(b))}<br>${r.services.map(s=>`${esc(airportCode(ix.airports.get(s.hub_airport_id)))} → ${esc(airportCode(ix.airports.get(s.destination_airport_id)))} · ${esc(s.service_brand)} · ${s.status==='seasonal'?'Seasonal':'Listed'}${s.note?' · '+esc(s.note):''}<br>${sourceLink(s.source_id)}`).join('<hr>')}<p class="hint">Line joins the listed airports; exact flight path and nonstop operation are not verified.</p>`;
}
function pinPopup(id){
 const a=ix.airports.get(id),serving=servingByAirport.get(id)||[],box=document.createElement('div');
 box.innerHTML=`<strong>${esc(airportCode(a))} · ${esc(a.name)}</strong><br>${esc(a.city)}, ${esc(a.country)}${serving.length?'<hr>'+serving.map(h=>`${esc(ix.airlines.get(h.airline_id).name)} · ${esc(hubRole(h))}<br><small>${h.note?esc(h.note)+'<br>':''}${h.route_count} parsed services · ${esc(h.coverage.replaceAll('_',' '))}<br>${sourceLink(h.source_id)}</small>`).join('<br>'):''}<br>`;
 const button=document.createElement('button');button.textContent='Show routes touching '+airportCode(a);button.addEventListener('click',()=>selectAirport(id));box.append(button);return box;
}
function renderPins(reset=false){return measure('pins',()=>{
 if(reset){pins.clearLayers();pinLayers.clear();}
 const bounds=map.getBounds().pad(.2),west=bounds.getWest(),east=bounds.getEast(),south=bounds.getSouth(),north=bounds.getNorth(),wanted=new Set();
 for(const id of relevant){
  const a=ix.airports.get(id);if(a.latitude<south||a.latitude>north)continue;
  const serving=servingByAirport.get(id)||[],isHub=hubIds.has(id),colors=[...new Set(serving.map(h=>airlineColor(h.airline_id)))];
  const first=Math.ceil((west-a.longitude)/360),last=Math.floor((east-a.longitude)/360);
  for(let world=first;world<=last;world++){
   const key=id+'@'+world;wanted.add(key);if(pinLayers.has(key))continue;
   const marker=L.circleMarker([a.latitude,a.longitude+world*360],{pane:'airports',renderer:pinRenderer,bubblingMouseEvents:false,radius:isHub?4.5:2.2,color:isHub?'#fff':'#50647d',weight:isHub?1.2:.3,fillColor:isHub?(colors.length===1?colors[0]:'#293c51'):'#627c96',fillOpacity:isHub?1:.65});
   marker.bindPopup(()=>pinPopup(id)).bindTooltip(`${esc(airportCode(a))} · ${esc(a.city||a.name)}`).addTo(pins);pinLayers.set(key,marker);
  }
 }
 for(const [key,marker] of pinLayers)if(!wanted.has(key)){pins.removeLayer(marker);pinLayers.delete(key);}
 recordMetric('layers',0,{routes:0,pins:pinLayers.size});
 });}
function renderMap(){return measure('map',()=>{
 routeLayer.setData(connections.map(r=>({connection:r,geometry:geometryFor(ix.airports.get(r.hub_airport_id),ix.airports.get(r.destination_airport_id)),color:airlineColor(r.airline_id),seasonal:r.services.every(s=>s.status==='seasonal')})));
 renderPins(true);
 $('counts').textContent=`${connections.length.toLocaleString()} connections · ${new Set(filtered.map(r=>r.airline_id)).size} airlines · ${[...relevant].filter(x=>hubIds.has(x)).length} hubs/bases · ${relevant.size} airports`;
 });}
function prepareView(){
 const eligibilityKey=[...state.alliances].sort().join(',')+'|'+[state.lowCost,state.regional,state.seasonal,state.charter].join('|');
 if(!eligibilityCache.has(eligibilityKey)){if(eligibilityCache.size>=16)eligibilityCache.delete(eligibilityCache.keys().next().value);eligibilityCache.set(eligibilityKey,airlineOptions(data,state));}
 eligibleAirlines=eligibilityCache.get(eligibilityKey);
 connections=uniqueConnections(filtered);servingByAirport=new Map();const hubs=visibleHubs(data,state);hubIds=new Set(hubs.map(h=>h.airport_id));
 for(const h of hubs){if(!servingByAirport.has(h.airport_id))servingByAirport.set(h.airport_id,[]);servingByAirport.get(h.airport_id).push(h);}
 relevant=new Set();for(const r of filtered){relevant.add(r.hub_airport_id);relevant.add(r.destination_airport_id);}if(!state.airports.size)for(const h of hubs)relevant.add(h.airport_id);
}
function update(){return measure('update',updateImpl);}
function updateImpl(){filtered=filterRoutes(data,state);prepareView();page=Math.min(page,Math.max(0,Math.ceil(filtered.length/PAGE_SIZE)-1));renderAirlines();renderAirports();renderMap();renderTable();renderChips();persist();}
function fit(){
 const pts=[...new Set(filtered.flatMap(r=>[r.hub_airport_id,r.destination_airport_id]))].map(id=>{const a=ix.airports.get(id);return[a.latitude,a.longitude];});
 if(!pts.length)return;
 const paths=[];
 for(const r of connections)paths.push(...geometryFor(ix.airports.get(r.hub_airport_id),ix.airports.get(r.destination_airport_id)).paths);
 map.fitBounds(routeBounds(pts,paths,map.getCenter().lng),{padding:[30,30],maxZoom:7});
}
function persist(){const p=explorerParams(state,data);if(new URLSearchParams(location.search).has('audit'))p.set('audit','1');history.replaceState(null,'',location.pathname+(p.size?'?'+p:'')+location.hash);}
function restore(){state=restoreExplorerState(data,location.search);}
function syncControls(){for(const key of ['seasonal','charter','regional'])$(key).checked=state[key];$('low-cost-filter').value=state.lowCost;$('airport-mode').value=state.airportMode;}
function clearFilters(resetView=false){
 const previous=state;state=defaultExplorerState(data);if(!resetView)for(const key of ['colorBy','labels','unit','airlineSort','destinationSort','view'])state[key]=previous[key];
 for(const id of ['airline-search','airport-search'])$(id).value='';page=0;syncControls();renderAllianceOptions();update();if(resetView)map.fitBounds([[-60,-180],[80,180]],{padding:[10,10]});
}
function renderChips(){
 const chips=[];const chip=(key,value,label)=>chips.push(`<button class="tag" data-chip-key="${key}" data-chip-value="${esc(value)}" aria-label="Remove ${esc(label)} filter">${esc(label)} ×</button>`);
 if(state.alliances.size!==data.alliances.length){chip('alliances','',state.alliances.size?[...state.alliances].map(id=>ix.alliances.get(id).name).join(', '):'No alliances');}
 for(const id of state.airlines)chip('airlines',id,ix.airlines.get(id).name);for(const id of state.airports)chip('airports',id,airportCode(ix.airports.get(id)));
 if(state.airportMode!=='touches')chip('airportMode','',state.airportMode==='between'?'Between airports':'Listed from hubs/bases');
 if(!state.seasonal)chip('seasonal','','Exclude seasonal');if(state.charter)chip('charter','','Include charter');if(state.lowCost!=='all')chip('lowCost','',`Airline model: ${state.lowCost}`);if(state.regional)chip('regional','','Regional only');
 $('filter-chips').innerHTML=chips.join('')||'<span class="hint">All networks · default service filters</span>';
 $('airport-mode-help').textContent=state.airportMode==='between'&&state.airports.size<2?'Select at least two airports to see connections between them.':state.airportMode==='hub'?'Matches the source hub/base endpoint; flight direction is not verified.':'';
}
async function init(){const dataStart=performance.now();
 const response=await fetch('map-data.json', {cache:'no-cache'});if(!response.ok)throw new Error(`Dataset request failed (${response.status})`);data=decodeMapData(await response.json());recordMetric('data',performance.now()-dataStart);ix=indexData(data);restore();prepareDownload(document.querySelector('header a'));
 map=L.map('map',{preferCanvas:true,minZoom:0,maxZoom:10,zoomSnap:.25,worldCopyJump:true}).fitBounds([[-60,-180],[80,180]],{padding:[10,10]});map.attributionControl.addAttribution('Basemap: Natural Earth / geo-countries · Airport data: OurAirports · Routes: Wikipedia');
 for(const [name,z] of [['land',220],['routes',420],['airports',620]])map.createPane(name).style.zIndex=z;
 map.getPane('land').style.pointerEvents='none';
 baseRenderer=L.canvas({pane:'land',padding:.2});pinRenderer=L.canvas({pane:'airports',padding:.2});
 pins=L.layerGroup().addTo(map);routeLayer=createRouteLayer(L,{popup:routePopup,onDraw:(ms,details)=>recordMetric('routeDraw',ms,details),onReuse:()=>recordMetric('routeReuse',0)}).addTo(map);
 // Wait for Leaflet's canvas bounds before adding/removing viewport pins.
 let viewportFrame;map.on('moveend',()=>{if(!viewportFrame)viewportFrame=requestAnimationFrame(()=>{viewportFrame=null;renderWorld();renderPins();});});
 fetch('world.geojson').then(r=>{if(!r.ok)throw new Error('Basemap unavailable');return r.json();}).then(geo=>{worldGeo=geo;renderWorld();}).catch(()=>{$('loading').textContent='Basemap unavailable. Airport pins and route filters still work.';});
 $('snapshot').textContent=`Snapshot: ${data.as_of} · ${data.airlines.length} airlines · ${data.hubs.length} airline–hub/base records · ${data.hubs.filter(h=>h.coverage==='parsed_with_unresolved').length} with partial mapping`;
 const gaps=data.hubs.filter(h=>!['parsed'].includes(h.coverage));
 $('methodology').innerHTML=`<p>${data.discovery_audit?.summary?.directory_entries||0} directory entries reviewed; ${data.discovery_audit?.summary?.rejected_carriers||0} proposed carriers had no origin with usable passenger-route evidence. The complete admission audit is embedded in the JSON.</p><p>${esc(data.scope.routes)}</p><p>${esc(data.scope.seasonality)}</p><p>${data.issues_count} extraction issues; ${gaps.length} airline–hub/base records need source or mapping review. “Parsed” describes extraction, not schedule completeness. Inspect the JSON issues and per-hub coverage fields.</p><p>Future and suspended/ended entries are retained in <code>excluded_routes</code> and omitted from this map.</p><p>Non-aligned covers documented current passenger carriers outside the three global alliances. Explicit affiliate and connecting-partner status is retained; suspended members have a separate category. Alaska remains in oneworld. Airport pins include source-labeled operating bases and focus cities for point-to-point carriers.</p><p>Enumerated regional and group service brands are grouped under their selected airline or brand group; operating carrier is not independently verified. This is a research snapshot, not a booking schedule.</p><p>Low-cost and regional filters use explicit source classifications. Unknown is not “no.” A documented service brand takes precedence over its parent, so Rouge services can be low-cost without labeling all Air Canada services low-cost. The JSON includes classification evidence and the discovery/admission audit.</p><p>Source: Wikipedia (CC BY-SA); airport metadata: OurAirports (public domain); verified airport aliases: Wikipedia and Wikidata (CC0). Pinned source revisions are linked from the service table.</p>`;
 syncControls();renderAllianceOptions();$('seasonal').checked=state.seasonal;$('charter').checked=state.charter;$('low-cost-filter').value=state.lowCost;$('regional').checked=state.regional;
 $('alliances').addEventListener('change',e=>{const id=e.target.dataset.alliance;if(!id)return;e.target.checked?state.alliances.add(id):state.alliances.delete(id);page=0;update();});
 $('airlines').addEventListener('change',e=>{const id=e.target.dataset.airline;if(!id)return;e.target.checked?state.airlines.add(id):state.airlines.delete(id);page=0;update();});
 $('airports').addEventListener('change',e=>{const id=e.target.dataset.airport;if(!id)return;e.target.checked?state.airports.add(id):state.airports.delete(id);page=0;update();});
 $('airport-selection').addEventListener('click',e=>{const id=e.target.closest('[data-remove-airport]')?.dataset.removeAirport;if(id){state.airports.delete(id);page=0;update();}});
 $('route-table').addEventListener('click',e=>{const id=e.target.closest('[data-select-airport]')?.dataset.selectAirport;if(id)selectAirport(id);});
 $('airline-search').addEventListener('input',renderAirlines);$('airport-search').addEventListener('input',renderAirports);
 $('airlines-clear').addEventListener('click',()=>{state.airlines.clear();page=0;update();});
 for(const key of ['seasonal','charter'])$(key).addEventListener('change',()=>{state[key]=$(key).checked;page=0;update();});
 function changeModel(){state.lowCost=$('low-cost-filter').value;state.regional=$('regional').checked;page=0;update();}
 $('low-cost-filter').addEventListener('change',changeModel);$('regional').addEventListener('change',changeModel);
 $('fit').addEventListener('click',fit);$('reset').addEventListener('click',()=>clearFilters(true));$('clear-filters').addEventListener('click',()=>clearFilters());
 $('airport-mode').addEventListener('change',()=>{state.airportMode=$('airport-mode').value;page=0;update();});
 $('airport-search-results').addEventListener('click',e=>{const id=e.target.closest('[data-inspect-airport]')?.dataset.inspectAirport;if(id){selectAirport(id);$('airport-search').value='';renderAirports();}});
 $('airport-search').addEventListener('keydown',e=>{if(e.key==='Escape'){$('airport-search').value='';renderAirports();}if(e.key==='Enter')$('airport-search-results').querySelector('button')?.click();});
 $('filter-chips').addEventListener('click',e=>{const button=e.target.closest('[data-chip-key]');if(!button)return;const key=button.dataset.chipKey;if(key==='alliances')state.alliances=new Set(data.alliances.map(a=>a.id));else if(state[key] instanceof Set)state[key].delete(button.dataset.chipValue);else state[key]=defaultExplorerState(data)[key];page=0;syncControls();renderAllianceOptions();update();});
 $('previous').addEventListener('click',()=>{page--;renderTable();});$('next').addEventListener('click',()=>{page++;renderTable();});
 $('loading').textContent='';update();markReady();
}
init().catch(e=>{$('loading').textContent=`Unable to load the map: ${e.message}. Serve this project over HTTP (see README).`;$('loading').className='error';$('counts').textContent='Data unavailable';console.error(e);});
