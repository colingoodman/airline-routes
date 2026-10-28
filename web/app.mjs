import {airportRegion,regionNames} from './geography.mjs';
import {indexData,filterRoutes,visibleHubs,greatCircle,uniqueConnections,routeBounds,canonicalAirportIds,airlineOptions,defaultExplorerState,explorerParams,restoreExplorerState,destinationGroups,sortDestinations,airlineNetworkStats,airportDistanceKm,routeDistanceKm,stableAirlineColor,compareNetworks,comparisonConnections} from './model.mjs?v=20261027-performance';
import {measure,recordMetric,markReady} from './perf.mjs?v=20261027-performance';
import {createRouteLayer,projectRoutePath} from './route-renderer.mjs?v=20261027-performance';
import {decodeMapData,prepareDownload} from './runtime.mjs?v=20261027-performance';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state;
const comparisonColors={shared:'#7b3fb5',a:'#007c91',b:'#b35800'};
let comparison={active:false};
let data,ix,map,routeLayer,pins,pinRenderer,baseRenderer,worldGeo,labelLayer,filtered=[],connections=[],relevant=new Set(),hubIds=new Set(),servingByAirport=new Map(),eligibleAirlines=[],airlineStats=new Map(),destinations=[],resultRows=[],page=0;const PAGE_SIZE=75;const worldLayers=new Map(),routeGeometry=new Map(),pinLayers=new Map(),eligibilityCache=new Map();
const airportCode=a=>a.iata||a.icao||a.local_code||a.ident||a.id;
const countryNames=new Intl.DisplayNames(['en'],{type:'region'});
const countryName=code=>{try{return countryNames.of(code)||code||'Unknown';}catch{return code||'Unknown';}};
const formatDistance=km=>`${Math.round(km*(state.unit==='mi'?.621371:1)).toLocaleString()} ${state.unit}`;
const airlineCode=a=>a.iata||a.icao||(a.id.startsWith('wiki:')?'':a.id.replace(/^icao:/,''));
const airportLabel=a=>`${airportCode(a)} · ${a.city||a.name}`;
const hubRole=h=>({hub:'hub',secondary_hub:'secondary hub',operating_base:'operating base',primary_base:'primary operating base',focus_city:'focus city'}[h.kind]||h.kind.replaceAll('_',' '));
const airlineColor=id=>state.colorBy==='airline'?stableAirlineColor(id):(ix.airlines.get(id).alliance_id==='nonaligned'?'#708090':ix.alliances.get(ix.airlines.get(id).alliance_id).color);
const sourceLink=id=>{const s=ix.sources.get(id);return s?`<a href="${esc(s.url)}" target="_blank" rel="noopener">Wikipedia ↗</a>`:'—';};
function renderAllianceOptions(){
 $('alliances').innerHTML=data.alliances.map(a=>`<label class="option"><input type="checkbox" data-alliance="${a.id}" ${state.alliances.has(a.id)?'checked':''}><span class="dot" style="background:${a.color}"></span>${esc(a.name)}<small>${a.kind==='alliance'?`${data.airlines.filter(x=>x.alliance_id===a.id&&x.membership_type==='full_member').length} members + ${data.airlines.filter(x=>x.alliance_id===a.id&&x.membership_type!=='full_member').length} related`:data.airlines.filter(x=>x.alliance_id===a.id).length}</small></label>`).join('');
}
function renderAirlines(){return measure('airlineChoices',renderAirlinesImpl);}
function renderAirlinesImpl(){
 const q=$('airline-search').value.toLowerCase(),eligible=eligibleAirlines,eligibleIds=new Set(eligible.map(a=>a.id)),available=[...eligible,...data.airlines.filter(a=>state.airlines.has(a.id)&&!eligibleIds.has(a.id))];
 $('airlines').innerHTML=available.filter(a=>(a.name+' '+a.id).toLowerCase().includes(q)).sort((a,b)=>(state.airlineSort==='destinations'?(airlineStats.get(b.id)?.airports.size||0)-(airlineStats.get(a.id)?.airports.size||0):state.airlineSort==='hubs'?(airlineStats.get(b.id)?.hubs.size||0)-(airlineStats.get(a.id)?.hubs.size||0):0)||a.name.localeCompare(b.name)).map(a=>`<label class="option"><input type="checkbox" data-airline="${a.id}" ${state.airlines.has(a.id)?'checked':''}><span class="dot" style="background:${airlineColor(a.id)}"></span>${esc(a.name)}<small>${a.membership_type==='connecting_partner'?'Partner · ':a.membership_type==='affiliate'?'Affiliate · ':''}${a.low_cost===true?'LCC · ':''}${a.regional===true?'Regional · ':''}${esc(airlineCode(a))}${eligibleIds.has(a.id)?` · ${airlineStats.get(a.id)?.airports.size||0} airports`:' · no matching services'}</small></label>`).join('')||'<p class="hint">No matching airlines.</p>';
 $('airline-count').textContent=state.airlines.size?`${state.airlines.size} selected`:`All ${available.length}`;
}
function renderAirports(){
 const q=$('airport-search').value.trim().toLowerCase(),hubs=hubIds;
 const choices=data.airports.filter(a=>q?(a.id+' '+(a.former_iata_codes||[]).join(' ')+' '+(a.icao||'')+' '+(a.ident||'')+' '+(a.local_code||'')+' '+a.city+' '+a.name+' '+a.country).toLowerCase().includes(q):hubs.has(a.id)).sort((a,b)=>(b.id.toLowerCase()===q)-(a.id.toLowerCase()===q)||a.id.localeCompare(b.id));
 $('airports').innerHTML=choices.slice(0,60).map(a=>`<label class="option"><input type="checkbox" data-airport="${a.id}" ${state.airports.has(a.id)?'checked':''}>${esc(airportLabel(a))}<small>${hubs.has(a.id)?'hub/base':''}</small><button type="button" data-inspect-airport="${a.id}" aria-label="Inspect ${esc(airportCode(a))}">Details</button></label>`).join('')+(choices.length>60?'<p class="hint">Showing 60 results. Refine your search.</p>':'')||'<p class="hint">No matching airports.</p>';
 $('airport-search-results').hidden=!q;$('airport-search-results').innerHTML=q?choices.slice(0,12).map(a=>`<button data-inspect-airport="${a.id}">${esc(airportLabel(a))} <small>${esc(a.name)}</small></button>`).join('')||'<p>No matching airports.</p>':'';
 $('airport-selection').innerHTML=[...state.airports].map(id=>`<button class="tag" data-remove-airport="${id}" aria-label="Remove ${id} airport filter">${esc(airportCode(ix.airports.get(id)))} ×</button>`).join('');
}
function renderTable(){
 const evidence=state.view==='evidence',q=$('destination-search').value.trim().toLowerCase();
 const searchable=a=>`${airportLabel(a)} ${a.name} ${countryName(a.country)} ${a.country}`.toLowerCase();
 if(evidence){
  resultRows=filtered.filter(r=>(!state.focus||r.hub_airport_id===state.focus||r.destination_airport_id===state.focus)&&(!q||[searchable(ix.airports.get(r.hub_airport_id)),searchable(ix.airports.get(r.destination_airport_id)),ix.airlines.get(r.airline_id).name.toLowerCase(),r.service_brand.toLowerCase()].some(s=>s.includes(q))));
  const sort=$('evidence-sort').value;
  resultRows.sort((a,b)=>(sort==='distance'?airportDistanceKm(ix.airports.get(a.hub_airport_id),ix.airports.get(a.destination_airport_id))-airportDistanceKm(ix.airports.get(b.hub_airport_id),ix.airports.get(b.destination_airport_id)):sort==='hub'?airportLabel(ix.airports.get(a.hub_airport_id)).localeCompare(airportLabel(ix.airports.get(b.hub_airport_id))):sort==='destination'?airportLabel(ix.airports.get(a.destination_airport_id)).localeCompare(airportLabel(ix.airports.get(b.destination_airport_id))):ix.airlines.get(a.airline_id).name.localeCompare(ix.airlines.get(b.airline_id).name))||a.id.localeCompare(b.id));
 }else resultRows=sortDestinations(destinations.filter(g=>!q||searchable(g.airport).includes(q)||[...g.airlines].some(id=>ix.airlines.get(id).name.toLowerCase().includes(q))),state.destinationSort);
 page=Math.min(page,Math.max(0,Math.ceil(resultRows.length/PAGE_SIZE)-1));const start=page*PAGE_SIZE,rows=resultRows.slice(start,start+PAGE_SIZE);
 $('result-columns').innerHTML=evidence?'<tr><th>Airline / brand</th><th>Hub / base</th><th>Destination</th><th>Service / distance</th><th>Evidence</th></tr>':'<tr><th>Airport</th><th>Country</th><th>Airlines</th><th>Attributes</th><th>Approx. distance</th></tr>';
 $('route-table').innerHTML=rows.map(r=>{
  if(!evidence){const a=r.airport,category=comparison.active?comparison.groups.get(state.focus?r.id:r.routes[0]&&[r.routes[0].hub_airport_id,r.routes[0].destination_airport_id].sort().join('|'))?.category:null;return `<tr data-highlight-airport="${a.id}"><td><button data-inspect-airport="${a.id}">${esc(airportLabel(a))}</button><small>${esc(a.name)}</small></td><td>${esc(countryName(a.country))}</td><td>${[...r.airlines].sort().map(id=>`<span class="airline-badge"><span class="dot" style="background:${airlineColor(id)}"></span>${esc(ix.airlines.get(id).name)}</span>`).join(' ')}</td><td>${[comparison.active?(state.focus?category==='shared'?'Shared':category==='a'?'A only':'B only':'Comparison airport'):'',r.seasonalOnly?'Seasonal only':'Listed',r.charterOnly?'Charter only':'',r.lowCost?'Includes low-cost':'',r.regional?'Includes regional':''].filter(Boolean).join(' · ')}</td><td>${r.distanceKm===null?'Choose a focused airport':formatDistance(r.distanceKm)}</td></tr>`;}
  const a=ix.airlines.get(r.airline_id),o=ix.airports.get(r.hub_airport_id),d=ix.airports.get(r.destination_airport_id);
  return `<tr data-highlight-route="${r.id}"><td><span class="dot" style="background:${airlineColor(a.id)}"></span> ${esc(a.name)}${r.service_brand!==a.name?`<small>${esc(r.service_brand)}</small>`:''}</td><td><button data-inspect-airport="${o.id}">${esc(airportCode(o))}</button> ${esc(o.city||o.name)}</td><td><button data-inspect-airport="${d.id}">${esc(airportCode(d))}</button> ${esc(d.city||d.name)}</td><td>${r.status==='seasonal'?'Seasonal':'Listed'}${r.service_type==='charter'?' charter':''}<small>${formatDistance(airportDistanceKm(o,d))}</small>${r.note?`<small>${esc(r.note)}</small>`:''}</td><td>${sourceLink(r.source_id)}</td></tr>`;
 }).join('');
 $('results-title').textContent=evidence?'Service evidence':state.focus?`Destinations connected to ${airportCode(ix.airports.get(state.focus))}`:'Connected airports';
 $('table-count').textContent=`${resultRows.length.toLocaleString()} ${evidence?'source entries':'airports'}`;
 $('result-help').textContent=(comparison.active&&!state.focus?'Comparison counts refer to airport pairs; this list groups their airports. ':'')+(state.focus?'Results touching the focused airport, within current filters. ':'All airports in the matching network. ')+(evidence?'Source endpoints do not establish flight direction.':'Hover or focus a row to highlight routes. Select an airport to inspect it.');
 $('page-label').textContent=resultRows.length?`${start+1}–${Math.min(start+PAGE_SIZE,resultRows.length)} of ${resultRows.length.toLocaleString()}`:'0 results';
 $('previous').disabled=page===0;$('next').disabled=start+PAGE_SIZE>=resultRows.length;$('empty').hidden=resultRows.length>0;
 $('destinations-tab').setAttribute('aria-pressed',String(!evidence));$('evidence-tab').setAttribute('aria-pressed',String(evidence));$('destination-sort').hidden=evidence;$('evidence-sort').hidden=!evidence;
}
function focusAirport(id){state.focus=id;page=0;update();}
function selectAirport(id){state.focus=id;state.airports=new Set([id]);state.airportMode='touches';$('airport-search').value='';page=0;syncControls();update();fit();}
function renderAirportDetail(){
 const panel=$('airport-detail');panel.hidden=!state.focus;if(!state.focus)return;
 const a=ix.airports.get(state.focus),routes=filtered.filter(r=>r.hub_airport_id===a.id||r.destination_airport_id===a.id),groups=destinationGroups(data,routes,a.id),airlines=[...new Set(routes.map(r=>r.airline_id))],hubs=data.hubs.filter(h=>h.airport_id===a.id&&airlines.includes(h.airline_id));
 panel.innerHTML=`<div class="detail-heading"><h2>${esc(airportCode(a))} · ${esc(a.name)}</h2><div><button data-explore-airport="${a.id}">Explore this airport</button> <button id="close-airport">Close details</button></div></div><p>${esc(a.city||'')} · ${esc(countryName(a.country))} · ${esc(regionNames[airportRegion(a)])}</p><p><strong>${groups.length} connected airports · ${new Set(groups.map(g=>g.airport.country)).size} countries · ${airlines.length} airlines</strong> within current filters</p><div class="airline-badges">${airlines.sort((x,y)=>ix.airlines.get(x).name.localeCompare(ix.airlines.get(y).name)).map(id=>`<button data-only-airline="${id}" title="Filter to this airline"><span class="dot" style="background:${airlineColor(id)}"></span> ${esc(ix.airlines.get(id).name)} · ${esc(ix.alliances.get(ix.airlines.get(id).alliance_id).name)}</button>`).join(' ')||'No recorded services match these filters.'}</div><details><summary>Hub/base roles, coverage and sources (${hubs.length})</summary>${hubs.map(h=>`<p>${esc(ix.airlines.get(h.airline_id).name)} · ${esc(hubRole(h))} · ${esc(h.coverage.replaceAll('_',' '))} · ${sourceLink(h.source_id)}${h.note?'<br>'+esc(h.note):''}</p>`).join('')||'<p>No matching documented hub/base role. Destination connections are still included above.</p>'}<p>Counts describe this dataset, which may have incomplete source coverage. Low-cost and regional attributes appear in the destination list where documented.</p></details>`;
}
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
 const a=ix.airports.get(r.hub_airport_id),b=ix.airports.get(r.destination_airport_id),services=filtered.filter(s=>s.hub_airport_id===a.id&&s.destination_airport_id===b.id||s.hub_airport_id===b.id&&s.destination_airport_id===a.id);
 return `<strong>${esc(airportLabel(a))} ↔ ${esc(airportLabel(b))}</strong><br>Approx. ${formatDistance(airportDistanceKm(a,b))}<hr>${services.map(s=>`${esc(ix.airlines.get(s.airline_id).name)} · ${esc(s.service_brand)}<br>${esc(airportCode(ix.airports.get(s.hub_airport_id)))} → ${esc(airportCode(ix.airports.get(s.destination_airport_id)))} · ${s.status==='seasonal'?'Seasonal':'Listed'}${s.service_type==='charter'?' charter':''}${s.note?' · '+esc(s.note):''}<br>${sourceLink(s.source_id)}`).join('<hr>')}<p class="hint">Line joins the listed airports; exact flight path and nonstop operation are not verified.</p>`;
}
function pinPopup(id){
 const a=ix.airports.get(id),serving=servingByAirport.get(id)||[],box=document.createElement('div');
 box.innerHTML=`<strong>${esc(airportCode(a))} · ${esc(a.name)}</strong><br>${esc(a.city)}, ${esc(a.country)}${serving.length?'<hr>'+serving.map(h=>`${esc(ix.airlines.get(h.airline_id).name)} · ${esc(hubRole(h))}<br><small>${h.note?esc(h.note)+'<br>':''}${h.route_count} parsed services · ${esc(h.coverage.replaceAll('_',' '))}<br>${sourceLink(h.source_id)}</small>`).join('<br>'):''}<br>`;
 const button=document.createElement('button');button.textContent='Explore '+airportCode(a);button.addEventListener('click',()=>selectAirport(id));box.append(button);return box;
}
function renderPins(reset=false){return measure('pins',()=>{
 if(reset){pins.clearLayers();pinLayers.clear();}
 const bounds=map.getBounds().pad(.2),west=bounds.getWest(),east=bounds.getEast(),south=bounds.getSouth(),north=bounds.getNorth(),wanted=new Set();
 for(const id of relevant){
  const a=ix.airports.get(id);if(a.latitude<south||a.latitude>north)continue;
  const serving=servingByAirport.get(id)||[],isHub=hubIds.has(id),colors=[...new Set(serving.map(h=>airlineColor(h.airline_id)))];
  const first=Math.ceil((west-a.longitude)/360),last=Math.floor((east-a.longitude)/360);
  for(let world=first;world<=last;world++){
   const key=id+'@'+world;wanted.add(key);if(pinLayers.has(key)){pinLayers.get(key).setRadius((isHub?4.5:2.2)+Math.max(0,map.getZoom()-3)*.65+(id===state.focus?2:0));continue;}
   const radius=(isHub?4.5:2.2)+Math.max(0,map.getZoom()-3)*.65+(id===state.focus?2:0);
   const marker=L.circleMarker([a.latitude,a.longitude+world*360],{pane:'airports',renderer:pinRenderer,bubblingMouseEvents:false,radius,color:id===state.focus?'#152c47':isHub?'#fff':'#50647d',weight:id===state.focus?2.5:isHub?1.2:.3,fillColor:isHub?(colors.length===1?colors[0]:'#293c51'):'#627c96',fillOpacity:isHub?1:.65});
   marker.on('click',()=>{if(state.focus!==id)focusAirport(id);});marker.bindPopup(()=>pinPopup(id)).bindTooltip(`${esc(airportCode(a))} · ${esc(a.city||a.name)}`).addTo(pins);pinLayers.set(key,marker);
  }
 }
 for(const [key,marker] of pinLayers)if(!wanted.has(key)){pins.removeLayer(marker);pinLayers.delete(key);}
 renderLabels();recordMetric('layers',0,{routes:0,pins:pinLayers.size});
 });}
function renderComparison(){
 const q=$('comparison-search').value.toLowerCase(),airlines=data.airlines.filter(a=>a.id===state.compareA||a.id===state.compareB||(a.id+' '+a.name).toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name));
 for(const [id,key,other] of [['compare-a','compareA','compareB'],['compare-b','compareB','compareA']]){$(id).innerHTML=`<option value="">Choose airline ${id==='compare-a'?'A':'B'}…</option>`+airlines.map(a=>`<option value="${a.id}" ${a.id===state[key]?'selected':''} ${a.id===state[other]?'disabled':''}>${esc(a.name)} (${esc(airlineCode(a))})</option>`).join('');}
 for(const input of $('comparison-toggles').querySelectorAll('input'))input.checked=state.compareShow.has(input.dataset.compareCategory);
 const panel=$('comparison-summary');panel.hidden=!state.compareA&&!state.compareB;
 panel.innerHTML=comparison.active?`<strong>${esc(ix.airlines.get(state.compareA).name)} versus ${esc(ix.airlines.get(state.compareB).name)}</strong><p>${comparison.counts.shared} shared · ${comparison.counts.a} A only · ${comparison.counts.b} B only ${state.focus?'destinations connected to '+esc(airportCode(ix.airports.get(state.focus))):'airport pairs'}. Counts precede category visibility toggles.</p><p class="hint">Differences reflect recorded source coverage. All other filters apply equally to both airlines.</p>`:'Choose two different airlines to compare their networks.';
 $('color-by').disabled=comparison.active;$('color-by').title=comparison.active?'Comparison uses shared / A only / B only colors':'';
}
function syncDistance(active){
 const factor=state.unit==='mi'?.621371192237334:1,max=Math.round(20020*factor);
 for(const side of ['min','max'])for(const suffix of ['','-number']){const input=$('distance-'+side+suffix);input.max=max;input.step=suffix?'1':state.unit==='mi'?'5':'10';if(input!==active)input.value=Math.round(state[side==='min'?'minKm':'maxKm']*factor);}
 $('distance-summary').textContent=`${formatDistance(state.minKm)}–${formatDistance(state.maxKm)}`;
}
function renderGeography(){
 const q=$('country-search').value.toLowerCase();$('countries').innerHTML=[...new Set(data.airports.map(a=>a.country))].sort((a,b)=>countryName(a).localeCompare(countryName(b))).filter(id=>(id+' '+countryName(id)).toLowerCase().includes(q)).map(id=>`<label class="option"><input type="checkbox" data-country="${id}" ${state.countries.has(id)?'checked':''}>${esc(countryName(id))}<small>${esc(id)}</small></label>`).join('')||'<p class="hint">No matching countries.</p>';
 $('region-selection').innerHTML=[...state.regions].map(id=>`<button data-remove-region="${id}" class="tag">${regionNames[id]} ×</button>`).join('');
}
function renderColorLegend(){
 if(comparison.active){$('color-legend').innerHTML=[['shared','Shared'],['a',ix.airlines.get(state.compareA).name+' only'],['b',ix.airlines.get(state.compareB).name+' only']].map(([id,name])=>`<span><i class="dot" style="background:${comparisonColors[id]}"></i> ${esc(name)}</span>`).join('');return;}
 const ids=state.colorBy==='airline'?[...new Set(filtered.map(r=>r.airline_id))].sort((a,b)=>ix.airlines.get(a).name.localeCompare(ix.airlines.get(b).name)):data.alliances.filter(a=>state.alliances.has(a.id)).map(a=>a.id);
 $('color-legend').innerHTML=ids.slice(0,16).map(id=>`<span><i class="dot" style="background:${state.colorBy==='airline'?airlineColor(id):id==='nonaligned'?'#708090':ix.alliances.get(id).color}"></i> ${esc(state.colorBy==='airline'?ix.airlines.get(id).name:ix.alliances.get(id).name)}</span>`).join('')+(ids.length>16?`<span class="hint">+ ${ids.length-16} airlines; select fewer for easier comparison. Colors may be similar.</span>`:'');
}
function showRouteHover(connection){
 if(!connection){$('route-hover').textContent='Hover a route or destination to highlight it.';for(const [key,marker] of pinLayers){const id=key.split('@')[0];marker.setStyle({weight:id===state.focus?2.5:hubIds.has(id)?1.2:.3});}return;}
 const a=ix.airports.get(connection.hub_airport_id),b=ix.airports.get(connection.destination_airport_id),airlines=[...new Set(filtered.filter(r=>(r.hub_airport_id===a.id&&r.destination_airport_id===b.id)||(r.hub_airport_id===b.id&&r.destination_airport_id===a.id)).map(r=>r.airline_id))];
 $('route-hover').textContent=`${airportCode(a)} ↔ ${airportCode(b)} · ${airlines.map(id=>ix.airlines.get(id).name).join(', ')} · approx. ${formatDistance(airportDistanceKm(a,b))} · ${connection.services.every(s=>s.status==='seasonal')?'Seasonal':'Listed service'}${connection.services.some(s=>s.service_type==='charter')?' · includes charter':''}`;
 for(const [key,marker] of pinLayers){const id=key.split('@')[0];if(id===a.id||id===b.id)marker.setStyle({weight:3});}
}
function renderLabels(){
 labelLayer.clearLayers();if(state.labels==='off')return;
 const candidates=[...pinLayers].map(([key,marker])=>({key,id:key.split('@')[0],marker})).sort((a,b)=>(b.id===state.focus)-(a.id===state.focus)||state.airports.has(b.id)-state.airports.has(a.id)||hubIds.has(b.id)-hubIds.has(a.id)||a.id.localeCompare(b.id)),occupied=new Set(),size=map.getSize();
 for(const {id,marker} of candidates){const selected=id===state.focus||state.airports.has(id);if(state.labels==='auto'&&!selected&&map.getZoom()<4)continue;const point=map.latLngToContainerPoint(marker.getLatLng());if(point.x<0||point.x>size.x||point.y<0||point.y>size.y)continue;
  const code=airportCode(ix.airports.get(id)),width=Math.max(38,code.length*8+8),left=point.x+7,top=point.y-12,cells=[];for(let x=Math.floor(left/24);x<=Math.floor((left+width)/24);x++)for(let y=Math.floor(top/20);y<=Math.floor((top+20)/20);y++)cells.push(x+','+y);if(!selected&&cells.some(cell=>occupied.has(cell)))continue;for(const cell of cells)occupied.add(cell);
  L.marker(marker.getLatLng(),{pane:'airportLabels',interactive:false,icon:L.divIcon({className:'airport-code-label',html:esc(code),iconSize:[width,20],iconAnchor:[-7,12]})}).addTo(labelLayer);
 }
}
function renderMap(){return measure('map',()=>{
 routeLayer.setData(connections.map(r=>({connection:r,geometry:geometryFor(ix.airports.get(r.hub_airport_id),ix.airports.get(r.destination_airport_id)),color:comparison.active?comparisonColors[comparison.categories.get(r.id)]:airlineColor(r.airline_id),seasonal:r.services.every(s=>s.status==='seasonal'),emphasis:comparison.active||state.airlines.size>0||!!state.focus&&(r.hub_airport_id===state.focus||r.destination_airport_id===state.focus)})));
 renderPins(true);
 $('counts').textContent=`${connections.length.toLocaleString()} connections · ${new Set(filtered.map(r=>r.airline_id)).size} airlines · ${[...relevant].filter(x=>hubIds.has(x)).length} hubs/bases · ${relevant.size} airports`;
 });}
function prepareView(){
 const eligibilityKey=[...state.alliances].sort().join(',')+'|'+[state.lowCost,state.regional,state.seasonal,state.charter].join('|');
 if(!eligibilityCache.has(eligibilityKey)){if(eligibilityCache.size>=16)eligibilityCache.delete(eligibilityCache.keys().next().value);eligibilityCache.set(eligibilityKey,airlineOptions(data,state));}
 eligibleAirlines=eligibilityCache.get(eligibilityKey);
 destinations=destinationGroups(data,filtered,state.focus);airlineStats=airlineNetworkStats(filtered);connections=comparison.active?comparisonConnections(filtered):uniqueConnections(filtered);servingByAirport=new Map();const constrained=comparison.active||state.airports.size||state.countries.size||state.regions.size||state.minKm||state.maxKm!==20020,hubKeys=constrained?new Set(filtered.map(r=>r.airline_id+'|'+r.hub_airport_id)):null;const hubs=visibleHubs(data,comparison.active?{...state,airlines:new Set([state.compareA,state.compareB])}:state).filter(h=>!constrained||hubKeys.has(h.airline_id+'|'+h.airport_id));hubIds=new Set(hubs.map(h=>h.airport_id));
 for(const h of hubs){if(!servingByAirport.has(h.airport_id))servingByAirport.set(h.airport_id,[]);servingByAirport.get(h.airport_id).push(h);}
 relevant=new Set();for(const r of filtered){relevant.add(r.hub_airport_id);relevant.add(r.destination_airport_id);}if(!constrained)for(const h of hubs)relevant.add(h.airport_id);
}
function update(){return measure('update',updateImpl);}
function updateImpl(){comparison=compareNetworks(data,state);filtered=comparison.routes;prepareView();page=Math.min(page,Math.max(0,Math.ceil(filtered.length/PAGE_SIZE)-1));renderAirlines();renderAirports();renderMap();renderTable();renderAirportDetail();renderChips();renderGeography();renderColorLegend();renderComparison();persist();}
function fit(){
 const pts=[...new Set(filtered.flatMap(r=>[r.hub_airport_id,r.destination_airport_id]))].map(id=>{const a=ix.airports.get(id);return[a.latitude,a.longitude];});
 if(!pts.length)return;
 const paths=[];
 for(const r of connections)paths.push(...geometryFor(ix.airports.get(r.hub_airport_id),ix.airports.get(r.destination_airport_id)).paths);
 map.fitBounds(routeBounds(pts,paths,map.getCenter().lng),{padding:[30,30],maxZoom:7});
}
function persist(){const p=explorerParams(state,data);if(new URLSearchParams(location.search).has('audit'))p.set('audit','1');history.replaceState(null,'',location.pathname+(p.size?'?'+p:'')+location.hash);}
function restore(){state=restoreExplorerState(data,location.search);}
function syncControls(){for(const key of ['seasonal','charter','regional'])$(key).checked=state[key];$('low-cost-filter').value=state.lowCost;$('airport-mode').value=state.airportMode;$('airline-sort').value=state.airlineSort;$('destination-sort').value=state.destinationSort;$('color-by').value=state.colorBy;$('airport-labels').value=state.labels;$('geo-mode').value=state.geoMode;$('distance-unit').value=state.unit;syncDistance();}
function clearFilters(resetView=false){
 const previous=state;state=defaultExplorerState(data);if(!resetView)for(const key of ['colorBy','labels','unit','airlineSort','destinationSort','view'])state[key]=previous[key];
 for(const id of ['airline-search','airport-search','destination-search','country-search','comparison-search'])$(id).value='';page=0;syncControls();renderAllianceOptions();update();if(resetView)map.fitBounds([[-60,-180],[80,180]],{padding:[10,10]});
}
function renderChips(){
 const chips=[];const chip=(key,value,label)=>chips.push(`<button class="tag" data-chip-key="${key}" data-chip-value="${esc(value)}" aria-label="Remove ${esc(label)} filter">${esc(label)} ×</button>`);
 if(state.alliances.size!==data.alliances.length){chip('alliances','',state.alliances.size?[...state.alliances].map(id=>ix.alliances.get(id).name).join(', '):'No alliances');}
 if(!comparison.active)for(const id of state.airlines)chip('airlines',id,ix.airlines.get(id).name);for(const id of state.airports)chip('airports',id,airportCode(ix.airports.get(id)));
 if(state.airportMode!=='touches')chip('airportMode','',state.airportMode==='between'?'Between airports':'Listed from hubs/bases');
 if(!state.seasonal)chip('seasonal','','Exclude seasonal');if(state.charter)chip('charter','','Include charter');if(state.lowCost!=='all')chip('lowCost','',`Airline model: ${state.lowCost}`);if(state.regional)chip('regional','','Regional only');for(const id of state.countries)chip('countries',id,countryName(id));for(const id of state.regions)chip('regions',id,regionNames[id]);if(state.geoMode!=='either')chip('geoMode','',`Geography: ${state.geoMode}`);if(state.minKm||state.maxKm!==20020)chip('distance','',`${formatDistance(state.minKm)}–${formatDistance(state.maxKm)}`);if(state.compareA||state.compareB)chip('comparison','',`Compare: ${state.compareA?ix.airlines.get(state.compareA).name:'choose A'} / ${state.compareB?ix.airlines.get(state.compareB).name:'choose B'}`);if(comparison.active&&state.compareShow.size!==3)chip('compareShow','',state.compareShow.size?[...state.compareShow].map(x=>x==='shared'?'Shared':x==='a'?'A only':'B only').join(', '):'No comparison categories');if(state.focus)chip('focus','',`Focused: ${airportCode(ix.airports.get(state.focus))}`);
 $('filter-chips').innerHTML=chips.join('')||'<span class="hint">All networks · default service filters</span>';
 $('airport-mode-help').textContent=state.airportMode==='between'&&state.airports.size<2?'Select at least two airports to see connections between them.':state.airportMode==='hub'?'Matches the source hub/base endpoint; flight direction is not verified.':'';
}
async function init(){const dataStart=performance.now();
 const response=await fetch('map-data.json', {cache:'no-cache'});if(!response.ok)throw new Error(`Dataset request failed (${response.status})`);data=decodeMapData(await response.json());recordMetric('data',performance.now()-dataStart);ix=indexData(data);restore();prepareDownload(document.querySelector('header a'));
 map=L.map('map',{preferCanvas:true,minZoom:0,maxZoom:10,zoomSnap:.25,worldCopyJump:true}).fitBounds([[-60,-180],[80,180]],{padding:[10,10]});map.attributionControl.addAttribution('Basemap: Natural Earth / geo-countries · Airport data: OurAirports · Routes: Wikipedia');
 for(const [name,z] of [['land',220],['routes',420],['airports',620],['airportLabels',640]])map.createPane(name).style.zIndex=z;
 map.getPane('land').style.pointerEvents='none';map.getPane('airportLabels').style.pointerEvents='none';
 baseRenderer=L.canvas({pane:'land',padding:.2});pinRenderer=L.canvas({pane:'airports',padding:.2,tolerance:5});labelLayer=L.layerGroup().addTo(map);
 pins=L.layerGroup().addTo(map);routeLayer=createRouteLayer(L,{popup:routePopup,onHover:showRouteHover,onDraw:(ms,details)=>recordMetric('routeDraw',ms,details),onReuse:()=>recordMetric('routeReuse',0)}).addTo(map);
 // Wait for Leaflet's canvas bounds before adding/removing viewport pins.
 let viewportFrame;map.on('moveend',()=>{if(!viewportFrame)viewportFrame=requestAnimationFrame(()=>{viewportFrame=null;renderWorld();renderPins();});});
 fetch('world.geojson').then(r=>{if(!r.ok)throw new Error('Basemap unavailable');return r.json();}).then(geo=>{worldGeo=geo;renderWorld();}).catch(()=>{$('loading').textContent='Basemap unavailable. Airport pins and route filters still work.';});
 $('snapshot').textContent=`Snapshot: ${data.as_of} · ${data.airlines.length} airlines · ${data.hubs.length} airline–hub/base records · ${data.hubs.filter(h=>h.coverage==='parsed_with_unresolved').length} with partial mapping`;
 const gaps=data.hubs.filter(h=>!['parsed'].includes(h.coverage));
 $('methodology').innerHTML=`<p>${data.discovery_audit?.summary?.directory_entries||0} directory entries reviewed; ${data.discovery_audit?.summary?.rejected_carriers||0} proposed carriers had no origin with usable passenger-route evidence. The complete admission audit is embedded in the JSON.</p><p>${esc(data.scope.routes)}</p><p>${esc(data.scope.seasonality)}</p><p>${data.issues_count} extraction issues; ${gaps.length} airline–hub/base records need source or mapping review. “Parsed” describes extraction, not schedule completeness. Inspect the JSON issues and per-hub coverage fields.</p><p>Future and suspended/ended entries are retained in <code>excluded_routes</code> and omitted from this map.</p><p>Non-aligned covers documented current passenger carriers outside the three global alliances. Explicit affiliate and connecting-partner status is retained; suspended members have a separate category. Alaska remains in oneworld. Airport pins include source-labeled operating bases and focus cities for point-to-point carriers.</p><p>Enumerated regional and group service brands are grouped under their selected airline or brand group; operating carrier is not independently verified. This is a research snapshot, not a booking schedule.</p><p>Low-cost and regional filters use explicit source classifications. Unknown is not “no.” A documented service brand takes precedence over its parent, so Rouge services can be low-cost without labeling all Air Canada services low-cost. The JSON includes classification evidence and the discovery/admission audit.</p><p>Source: Wikipedia (CC BY-SA); airport metadata: OurAirports (public domain); verified airport aliases: Wikipedia and Wikidata (CC0). Pinned source revisions are linked from the service table.</p>`;
 syncControls();renderAllianceOptions();$('seasonal').checked=state.seasonal;$('charter').checked=state.charter;$('low-cost-filter').value=state.lowCost;$('regional').checked=state.regional;
 $('alliances').addEventListener('change',e=>{const id=e.target.dataset.alliance;if(!id)return;e.target.checked?state.alliances.add(id):state.alliances.delete(id);page=0;update();});
 $('airlines').addEventListener('change',e=>{const id=e.target.dataset.airline;if(!id)return;state.compareA='';state.compareB='';e.target.checked?state.airlines.add(id):state.airlines.delete(id);page=0;update();});
 $('airports').addEventListener('change',e=>{const id=e.target.dataset.airport;if(!id)return;e.target.checked?state.airports.add(id):state.airports.delete(id);page=0;update();});
 $('airport-selection').addEventListener('click',e=>{const id=e.target.closest('[data-remove-airport]')?.dataset.removeAirport;if(id){state.airports.delete(id);page=0;update();}});
 $('route-table').addEventListener('click',e=>{const id=e.target.closest('[data-inspect-airport]')?.dataset.inspectAirport;if(id)focusAirport(id);});
 $('airports').addEventListener('click',e=>{const button=e.target.closest('[data-inspect-airport]');if(button){e.preventDefault();focusAirport(button.dataset.inspectAirport);}});
 $('airport-detail').addEventListener('click',e=>{const explore=e.target.closest('[data-explore-airport]'),airline=e.target.closest('[data-only-airline]');if(explore)selectAirport(explore.dataset.exploreAirport);if(airline){state.compareA='';state.compareB='';state.airlines=new Set([airline.dataset.onlyAirline]);page=0;update();}if(e.target.id==='close-airport'){state.focus='';page=0;update();}});
 for(const [id,view] of [['destinations-tab','destinations'],['evidence-tab','evidence']])$(id).addEventListener('click',()=>{state.view=view;page=0;renderTable();persist();});
 $('destination-search').addEventListener('input',()=>{page=0;renderTable();});$('destination-sort').addEventListener('change',()=>{state.destinationSort=$('destination-sort').value;page=0;renderTable();persist();});$('evidence-sort').addEventListener('change',()=>{page=0;renderTable();});
 for(const [id,key] of [['color-by','colorBy'],['airport-labels','labels']])$(id).addEventListener('change',()=>{state[key]=$(id).value;update();});
 $('comparison-search').addEventListener('input',renderComparison);for(const [id,key] of [['compare-a','compareA'],['compare-b','compareB']])$(id).addEventListener('change',()=>{state[key]=$(id).value;page=0;update();});
 $('comparison-toggles').addEventListener('change',e=>{const category=e.target.dataset.compareCategory;if(category){e.target.checked?state.compareShow.add(category):state.compareShow.delete(category);page=0;update();}});$('comparison-clear').addEventListener('click',()=>{state.compareA='';state.compareB='';state.compareShow=new Set(['shared','a','b']);page=0;update();});
 $('countries').addEventListener('change',e=>{const id=e.target.dataset.country;if(id){e.target.checked?state.countries.add(id):state.countries.delete(id);page=0;update();}});$('country-search').addEventListener('input',renderGeography);
 $('region-filter').innerHTML+=Object.entries(regionNames).map(([id,name])=>`<option value="${id}">${name}</option>`).join('');$('region-filter').addEventListener('change',()=>{if($('region-filter').value)state.regions.add($('region-filter').value);$('region-filter').value='';page=0;update();});$('region-selection').addEventListener('click',e=>{const id=e.target.closest('[data-remove-region]')?.dataset.removeRegion;if(id){state.regions.delete(id);page=0;update();}});
 $('geo-mode').addEventListener('change',()=>{state.geoMode=$('geo-mode').value;page=0;update();});$('distance-unit').addEventListener('change',()=>{state.unit=$('distance-unit').value;syncDistance();renderTable();renderChips();persist();});
 for(const side of ['min','max'])for(const suffix of ['','-number'])$('distance-'+side+suffix).addEventListener('input',()=>{const input=$('distance-'+side+suffix);if(input.value===''||!Number.isFinite(input.valueAsNumber))return;const km=Math.max(0,Math.min(20020,input.valueAsNumber*(state.unit==='mi'?1.609344:1)));if(side==='min')state.minKm=Math.min(km,state.maxKm);else state.maxKm=Math.max(km,state.minKm);syncDistance(input);clearTimeout(distanceTimer);distanceTimer=setTimeout(()=>{page=0;update();},120);});
 $('airline-sort').addEventListener('change',()=>{state.airlineSort=$('airline-sort').value;renderAirlines();persist();});
 let distanceTimer;
 const highlightRow=e=>{const row=e.target.closest('tr');if(!row)return;const airport=row.dataset.highlightAirport,route=row.dataset.highlightRoute;routeLayer.highlight(entry=>airport?(entry.connection.hub_airport_id===airport||entry.connection.destination_airport_id===airport)&&(!state.focus||entry.connection.hub_airport_id===state.focus||entry.connection.destination_airport_id===state.focus):entry.connection.services.some(s=>s.id===route));if(airport){$('route-hover').textContent=`${airportLabel(ix.airports.get(airport))}${state.focus?' · connected to '+airportCode(ix.airports.get(state.focus)):''}`;for(const [key,marker] of pinLayers)if(key.split('@')[0]===airport||key.split('@')[0]===state.focus)marker.setStyle({weight:3});}};
 $('route-table').addEventListener('mouseover',highlightRow);$('route-table').addEventListener('focusin',highlightRow);$('route-table').addEventListener('mouseleave',()=>routeLayer.clearHover());$('route-table').addEventListener('focusout',()=>routeLayer.clearHover());
 $('airline-search').addEventListener('input',renderAirlines);$('airport-search').addEventListener('input',renderAirports);
 $('airlines-clear').addEventListener('click',()=>{state.compareA='';state.compareB='';state.airlines.clear();page=0;update();});
 for(const key of ['seasonal','charter'])$(key).addEventListener('change',()=>{state[key]=$(key).checked;page=0;update();});
 function changeModel(){state.lowCost=$('low-cost-filter').value;state.regional=$('regional').checked;page=0;update();}
 $('low-cost-filter').addEventListener('change',changeModel);$('regional').addEventListener('change',changeModel);
 $('fit').addEventListener('click',fit);$('reset').addEventListener('click',()=>clearFilters(true));$('clear-filters').addEventListener('click',()=>clearFilters());
 $('airport-mode').addEventListener('change',()=>{state.airportMode=$('airport-mode').value;page=0;update();});
 $('airport-search-results').addEventListener('click',e=>{const id=e.target.closest('[data-inspect-airport]')?.dataset.inspectAirport;if(id){focusAirport(id);$('airport-search').value='';renderAirports();}});
 $('airport-search').addEventListener('keydown',e=>{if(e.key==='Escape'){$('airport-search').value='';renderAirports();}if(e.key==='Enter')$('airport-search-results').querySelector('button')?.click();});
 $('filter-chips').addEventListener('click',e=>{const button=e.target.closest('[data-chip-key]');if(!button)return;const key=button.dataset.chipKey;if(key==='comparison'){state.compareA='';state.compareB='';state.compareShow=new Set(['shared','a','b']);}else if(key==='compareShow')state.compareShow=new Set(['shared','a','b']);else if(key==='distance'){state.minKm=0;state.maxKm=20020;}else if(key==='alliances')state.alliances=new Set(data.alliances.map(a=>a.id));else if(state[key] instanceof Set)state[key].delete(button.dataset.chipValue);else state[key]=defaultExplorerState(data)[key];page=0;syncControls();renderAllianceOptions();update();});
 $('previous').addEventListener('click',()=>{page--;renderTable();});$('next').addEventListener('click',()=>{page++;renderTable();});
 $('loading').textContent='';update();markReady();
}
init().catch(e=>{$('loading').textContent=`Unable to load the map: ${e.message}. Serve this project over HTTP (see README).`;$('loading').className='error';$('counts').textContent='Data unavailable';console.error(e);});
