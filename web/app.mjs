import {indexData,filterRoutes,visibleHubs,greatCircle,uniqueConnections,worldOffsets,shiftedPaths,routeBounds,canonicalAirportIds,airlineOptions,routeModel} from './model.mjs?v=20261027-global';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={alliances:new Set(),airlines:new Set(),airports:new Set(),seasonal:true,charter:false,lowCost:'all',regional:false};
let data,ix,map,lines,pins,renderer,pinRenderer,baseRenderer,worldGeo,filtered=[],page=0;const PAGE_SIZE=75;const worldLayers=new Map(),routeGeometry=new Map();
const airportCode=a=>a.iata||a.icao||a.local_code||a.ident||a.id;
const airlineCode=a=>a.iata||a.icao||(a.id.startsWith('wiki:')?'':a.id.replace(/^icao:/,''));
const airportLabel=a=>`${airportCode(a)} · ${a.city||a.name}`;
const hubRole=h=>({hub:'hub',secondary_hub:'secondary hub',operating_base:'operating base',primary_base:'primary operating base',focus_city:'focus city'}[h.kind]||h.kind.replaceAll('_',' '));
const airlineColor=id=>ix.alliances.get(ix.airlines.get(id).alliance_id).color;
const sourceLink=id=>{const s=ix.sources.get(id);return s?`<a href="${esc(s.url)}" target="_blank" rel="noopener">Wikipedia ↗</a>`:'—';};
function renderAllianceOptions(){
 $('alliances').innerHTML=data.alliances.map(a=>`<label class="option"><input type="checkbox" data-alliance="${a.id}" ${state.alliances.has(a.id)?'checked':''}><span class="dot" style="background:${a.color}"></span>${esc(a.name)}<small>${a.kind==='alliance'?`${data.airlines.filter(x=>x.alliance_id===a.id&&x.membership_type==='full_member').length} members + ${data.airlines.filter(x=>x.alliance_id===a.id&&x.membership_type!=='full_member').length} related`:data.airlines.filter(x=>x.alliance_id===a.id).length}</small></label>`).join('');
}
function renderAirlines(){
 const q=$('airline-search').value.toLowerCase(),eligible=airlineOptions(data,state),eligibleIds=new Set(eligible.map(a=>a.id)),available=[...eligible,...data.airlines.filter(a=>state.airlines.has(a.id)&&state.alliances.has(a.alliance_id)&&!eligibleIds.has(a.id))];
 $('airlines').innerHTML=available.filter(a=>(a.name+' '+a.id).toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name)).map(a=>`<label class="option"><input type="checkbox" data-airline="${a.id}" ${state.airlines.has(a.id)?'checked':''}><span class="dot" style="background:${airlineColor(a.id)}"></span>${esc(a.name)}<small>${a.membership_type==='connecting_partner'?'Partner · ':a.membership_type==='affiliate'?'Affiliate · ':''}${a.low_cost===true?'LCC · ':''}${a.regional===true?'Regional · ':''}${esc(airlineCode(a))}${eligibleIds.has(a.id)?'':' · no matching services'}</small></label>`).join('')||'<p class="hint">No matching airlines.</p>';
 $('airline-count').textContent=state.airlines.size?`${state.airlines.size} selected`:`All ${available.length}`;
}
function renderAirports(){
 const q=$('airport-search').value.trim().toLowerCase(),hubs=new Set(visibleHubs(data,state).map(h=>h.airport_id));
 const choices=data.airports.filter(a=>q?(a.id+' '+(a.former_iata_codes||[]).join(' ')+' '+(a.icao||'')+' '+(a.ident||'')+' '+(a.local_code||'')+' '+a.city+' '+a.name+' '+a.country).toLowerCase().includes(q):hubs.has(a.id)).sort((a,b)=>(b.id.toLowerCase()===q)-(a.id.toLowerCase()===q)||a.id.localeCompare(b.id));
 $('airports').innerHTML=choices.slice(0,60).map(a=>`<label class="option"><input type="checkbox" data-airport="${a.id}" ${state.airports.has(a.id)?'checked':''}>${esc(airportLabel(a))}<small>${hubs.has(a.id)?'hub/base':''}</small></label>`).join('')+(choices.length>60?'<p class="hint">Showing 60 results. Refine your search.</p>':'')||'<p class="hint">No matching airports.</p>';
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
 const offsets=worldOffsets(map.getBounds().getWest(),map.getBounds().getEast());
 for(const [offset,layer] of worldLayers)if(!offsets.includes(offset)){map.removeLayer(layer);worldLayers.delete(offset);}
 for(const offset of offsets)if(!worldLayers.has(offset)){
  const layer=L.geoJSON(worldGeo,{pane:'land',renderer:baseRenderer,coordsToLatLng:c=>L.latLng(c[1],c[0]+offset),style:{color:'#b6c6d4',weight:.6,fillColor:'#f8fafb',fillOpacity:1},interactive:false}).addTo(map);
  worldLayers.set(offset,layer);
 }
}
function renderMap(){
 lines.clearLayers();pins.clearLayers();
 const bounds=map.getBounds(),padding=Math.max(90,bounds.getEast()-bounds.getWest()),west=bounds.getWest()-padding,east=bounds.getEast()+padding,offsets=worldOffsets(bounds.getWest(),bounds.getEast());
 const connections=uniqueConnections(filtered),relevant=new Set(filtered.flatMap(r=>[r.hub_airport_id,r.destination_airport_id]));
 const vh=visibleHubs(data,state),hubIds=new Set(vh.map(h=>h.airport_id));
 if(!state.airports.size)vh.forEach(h=>relevant.add(h.airport_id));
 for(const r of connections){
  const a=ix.airports.get(r.hub_airport_id),b=ix.airports.get(r.destination_airport_id),onlySeasonal=r.services.every(x=>x.status==='seasonal');
  const geometryKey=[a.id,b.id].join('|');
  if(!routeGeometry.has(geometryKey))routeGeometry.set(geometryKey,greatCircle(a,b));
  for(const offset of offsets){
  const paths=shiftedPaths(routeGeometry.get(geometryKey),offset,west,east);if(!paths.length)continue;
  const line=L.polyline(paths,{pane:'routes',renderer,color:airlineColor(r.airline_id),weight:1.15,opacity:.36,dashArray:onlySeasonal?'4 5':null});
  line.bindPopup(()=>`<strong>${esc(ix.airlines.get(r.airline_id).name)}</strong><br>${esc(airportLabel(a))} — ${esc(airportLabel(b))}<br>${r.services.map(s=>`${s.hub_airport_id} → ${s.destination_airport_id} · ${esc(s.service_brand)} · ${s.status==='seasonal'?'Seasonal':'Listed'}${s.note?' · '+esc(s.note):''}<br>${sourceLink(s.source_id)}`).join('<hr>')}<p class="hint">Line joins the listed airports; exact flight path and nonstop operation are not verified.</p>`);
  line.on('mouseover',()=>line.setStyle({weight:3,opacity:.9})).on('mouseout',()=>line.setStyle({weight:1.15,opacity:.36}));line.addTo(lines);
  }
 }
 for(const id of relevant){
  const a=ix.airports.get(id),isHub=hubIds.has(id),serving=vh.filter(h=>h.airport_id===id),colors=[...new Set(serving.map(h=>airlineColor(h.airline_id)))];
  for(const offset of offsets){
  const longitude=a.longitude+offset;if(longitude<west||longitude>east)continue;
  const marker=L.circleMarker([a.latitude,longitude],{pane:'airports',renderer:pinRenderer,radius:isHub?4.5:2.2,color:isHub?'#fff':'#50647d',weight:isHub?1.2:.3,fillColor:isHub?(colors.length===1?colors[0]:'#293c51'):'#627c96',fillOpacity:isHub?1:.65});
  marker.bindPopup(()=>{const box=document.createElement('div');box.innerHTML=`<strong>${esc(airportCode(a))} · ${esc(a.name)}</strong><br>${esc(a.city)}, ${esc(a.country)}${serving.length?'<hr>'+serving.map(h=>`${esc(ix.airlines.get(h.airline_id).name)} · ${esc(hubRole(h))}<br><small>${h.note?esc(h.note)+'<br>':''}${h.route_count} parsed services · ${esc(h.coverage.replaceAll('_',' '))}<br>${sourceLink(h.source_id)}</small>`).join('<br>'):''}<br>`;
  const btn=document.createElement('button');btn.textContent='Show routes touching '+airportCode(a);btn.addEventListener('click',()=>selectAirport(id));box.append(btn);
  return box;}).bindTooltip(`${esc(airportCode(a))} · ${esc(a.city||a.name)}`);marker.addTo(pins);
  }
 }
 $('counts').textContent=`${connections.length.toLocaleString()} connections · ${new Set(filtered.map(r=>r.airline_id)).size} airlines · ${[...relevant].filter(x=>hubIds.has(x)).length} hubs/bases · ${relevant.size} airports`;
}
function update(){filtered=filterRoutes(data,state);page=Math.min(page,Math.max(0,Math.ceil(filtered.length/PAGE_SIZE)-1));renderAirlines();renderAirports();renderMap();renderTable();persist();}
function fit(){
 const pts=[...new Set(filtered.flatMap(r=>[r.hub_airport_id,r.destination_airport_id]))].map(id=>{const a=ix.airports.get(id);return[a.latitude,a.longitude];});
 if(!pts.length)return;
 const paths=[];
 for(const r of uniqueConnections(filtered)){
  const key=[r.hub_airport_id,r.destination_airport_id].join('|');
  if(!routeGeometry.has(key))routeGeometry.set(key,greatCircle(ix.airports.get(r.hub_airport_id),ix.airports.get(r.destination_airport_id)));
  paths.push(...routeGeometry.get(key));
 }
 map.fitBounds(routeBounds(pts,paths,map.getCenter().lng),{padding:[30,30],maxZoom:7});
}
function persist(){const p=new URLSearchParams();if(state.alliances.size!==data.alliances.length)p.set('alliances',[...state.alliances].join(','));if(state.airlines.size)p.set('airlines',[...state.airlines].join(','));if(state.airports.size)p.set('airports',[...state.airports].join(','));if(!state.seasonal)p.set('seasonal','0');if(state.charter)p.set('charter','1');if(state.lowCost!=='all')p.set('low_cost',state.lowCost);if(state.regional)p.set('regional','1');history.replaceState(null,'',location.pathname+(p.size?'?'+p:'')+location.hash);}
function restore(){state.alliances=new Set(data.alliances.map(a=>a.id));const p=new URLSearchParams(location.search);for(const [key,ids] of [['alliances',new Set(data.alliances.map(a=>a.id))],['airlines',new Set(data.airlines.map(a=>a.id))],['airports',new Set(data.airports.map(a=>a.id))]])if(p.has(key))state[key]=new Set(key==='airports'?canonicalAirportIds(data.airports,p.get(key).split(',')):p.get(key).split(',').filter(x=>ids.has(x)));state.seasonal=p.get('seasonal')!=='0';state.charter=p.get('charter')==='1';state.lowCost=['yes','no','unknown'].includes(p.get('low_cost'))?p.get('low_cost'):'all';state.regional=p.get('regional')==='1';}
async function init(){
 const response=await fetch('data.json', {cache:'no-store'});if(!response.ok)throw new Error(`Dataset request failed (${response.status})`);data=await response.json();ix=indexData(data);restore();document.querySelector('header a').href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
 map=L.map('map',{preferCanvas:true,minZoom:0,maxZoom:10,zoomSnap:.25,worldCopyJump:true}).fitBounds([[-60,-180],[80,180]],{padding:[10,10]});map.attributionControl.addAttribution('Basemap: Natural Earth / geo-countries · Airport data: OurAirports · Routes: Wikipedia');
 for(const [name,z] of [['land',220],['routes',420],['airports',620]])map.createPane(name).style.zIndex=z;
 map.getPane('land').style.pointerEvents='none';
 baseRenderer=L.canvas({pane:'land',padding:1});renderer=L.canvas({pane:'routes',padding:1});pinRenderer=L.canvas({pane:'airports',padding:1});
 lines=L.layerGroup().addTo(map);pins=L.layerGroup().addTo(map);
 // Leaflet updates canvas clipping bounds in its moveend listeners. Rebuild
 // copied routes on the next frame, after those bounds reflect the new view.
 map.on('moveend',()=>requestAnimationFrame(()=>{renderWorld();renderMap();}));
 fetch('world.geojson').then(r=>{if(!r.ok)throw new Error('Basemap unavailable');return r.json();}).then(geo=>{worldGeo=geo;renderWorld();}).catch(()=>{$('loading').textContent='Basemap unavailable. Airport pins and route filters still work.';});
 $('snapshot').textContent=`Snapshot: ${data.as_of} · ${data.airlines.length} airlines · ${data.hubs.length} airline–hub/base records · ${data.hubs.filter(h=>h.coverage==='parsed_with_unresolved').length} with partial mapping`;
 const gaps=data.hubs.filter(h=>!['parsed'].includes(h.coverage));
 $('methodology').innerHTML=`<p>${data.discovery_audit?.summary?.directory_entries||0} directory entries reviewed; ${data.discovery_audit?.summary?.rejected_carriers||0} proposed carriers had no origin with usable passenger-route evidence. The complete admission audit is embedded in the JSON.</p><p>${esc(data.scope.routes)}</p><p>${esc(data.scope.seasonality)}</p><p>${data.issues.length} extraction issues; ${gaps.length} airline–hub/base records need source or mapping review. “Parsed” describes extraction, not schedule completeness. Inspect the JSON issues and per-hub coverage fields.</p><p>Future and suspended/ended entries are retained in <code>excluded_routes</code> and omitted from this map.</p><p>Non-aligned covers documented current passenger carriers outside the three global alliances. Explicit affiliate and connecting-partner status is retained; suspended members have a separate category. Alaska remains in oneworld. Airport pins include source-labeled operating bases and focus cities for point-to-point carriers.</p><p>Enumerated regional and group service brands are grouped under their selected airline or brand group; operating carrier is not independently verified. This is a research snapshot, not a booking schedule.</p><p>Low-cost and regional filters use explicit source classifications. Unknown is not “no.” A documented service brand takes precedence over its parent, so Rouge services can be low-cost without labeling all Air Canada services low-cost. The JSON includes classification evidence and the discovery/admission audit.</p><p>Source: Wikipedia (CC BY-SA); airport metadata: OurAirports (public domain); verified airport aliases: Wikipedia and Wikidata (CC0). Pinned source revisions are linked from the service table.</p>`;
 renderAllianceOptions();$('seasonal').checked=state.seasonal;$('charter').checked=state.charter;$('low-cost-filter').value=state.lowCost;$('regional').checked=state.regional;
 $('alliances').addEventListener('change',e=>{const id=e.target.dataset.alliance;if(!id)return;e.target.checked?state.alliances.add(id):state.alliances.delete(id);state.airlines=new Set([...state.airlines].filter(x=>state.alliances.has(ix.airlines.get(x).alliance_id)));page=0;update();});
 $('airlines').addEventListener('change',e=>{const id=e.target.dataset.airline;if(!id)return;e.target.checked?state.airlines.add(id):state.airlines.delete(id);page=0;update();});
 $('airports').addEventListener('change',e=>{const id=e.target.dataset.airport;if(!id)return;e.target.checked?state.airports.add(id):state.airports.delete(id);page=0;update();});
 $('airport-selection').addEventListener('click',e=>{const id=e.target.closest('[data-remove-airport]')?.dataset.removeAirport;if(id){state.airports.delete(id);page=0;update();}});
 $('route-table').addEventListener('click',e=>{const id=e.target.closest('[data-select-airport]')?.dataset.selectAirport;if(id)selectAirport(id);});
 $('airline-search').addEventListener('input',renderAirlines);$('airport-search').addEventListener('input',renderAirports);
 $('airlines-clear').addEventListener('click',()=>{state.airlines.clear();page=0;update();});
 for(const key of ['seasonal','charter'])$(key).addEventListener('change',()=>{state[key]=$(key).checked;page=0;update();});
 function changeModel(){state.lowCost=$('low-cost-filter').value;state.regional=$('regional').checked;page=0;update();}
 $('low-cost-filter').addEventListener('change',changeModel);$('regional').addEventListener('change',changeModel);
 $('fit').addEventListener('click',fit);$('reset').addEventListener('click',()=>{state.alliances=new Set(data.alliances.map(a=>a.id));state.airlines.clear();state.airports.clear();state.seasonal=true;state.charter=false;state.lowCost='all';state.regional=false;$('low-cost-filter').value='all';$('regional').checked=false;$('seasonal').checked=true;$('charter').checked=false;$('airline-search').value='';$('airport-search').value='';page=0;renderAllianceOptions();update();map.fitBounds([[-60,-180],[80,180]],{padding:[10,10]});});
 $('previous').addEventListener('click',()=>{page--;renderTable();});$('next').addEventListener('click',()=>{page++;renderTable();});
 $('loading').textContent='';update();
}
init().catch(e=>{$('loading').textContent=`Unable to load the map: ${e.message}. Serve this project over HTTP (see README).`;$('loading').className='error';$('counts').textContent='Data unavailable';console.error(e);});
