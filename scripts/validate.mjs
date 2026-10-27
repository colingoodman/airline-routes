import fs from 'node:fs';
import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url),d=JSON.parse(fs.readFileSync(new URL('web/data.json',root),'utf8'));
function index(rows,label){const ids=new Set();for(const r of rows){assert.ok(r.id,`${label} id missing`);assert.ok(!ids.has(r.id),`Duplicate ${label}: ${r.id}`);ids.add(r.id);}return ids;}
const al=index(d.alliances,'alliance'),air=index(d.airlines,'airline'),ap=index(d.airports,'airport'),src=index(d.sources,'source'),routes=index([...d.routes,...d.excluded_routes],'route');
assert.equal(d.airlines.length,60);assert.equal(d.airlines.filter(a=>a.alliance_id==='star').length,26);assert.equal(d.airlines.filter(a=>a.alliance_id==='skyteam').length,18);assert.equal(d.airlines.filter(a=>a.alliance_id==='oneworld').length,16);
for(const a of d.airlines){assert.ok(al.has(a.alliance_id));assert.ok(src.has(a.membership_source_id));assert.ok(d.hubs.some(h=>h.airline_id===a.id),`No hubs: ${a.id}`);}
const hubkeys=new Set();for(const h of d.hubs){assert.ok(air.has(h.airline_id));assert.ok(ap.has(h.airport_id));assert.ok(src.has(h.source_id));const k=h.airline_id+'|'+h.airport_id;assert.ok(!hubkeys.has(k),'Duplicate hub '+k);hubkeys.add(k);assert.equal(h.route_count,d.routes.filter(r=>r.airline_id===h.airline_id&&r.hub_airport_id===h.airport_id).length);}
for(const a of d.airport_aliases){assert.ok(ap.has(a.airport_id));assert.ok(src.has(a.source_id));}
for(const a of d.airports){assert.equal(a.id,a.iata);assert.match(a.iata,/^[A-Z]{3}$/);assert.ok(Number.isFinite(a.latitude)&&a.latitude>=-90&&a.latitude<=90);assert.ok(Number.isFinite(a.longitude)&&a.longitude>=-180&&a.longitude<=180);assert.ok(src.has(a.source_id));}
for(const r of [...d.routes,...d.excluded_routes]){assert.ok(air.has(r.airline_id));assert.ok(ap.has(r.hub_airport_id));assert.ok(ap.has(r.destination_airport_id));assert.ok(src.has(r.source_id));assert.ok(hubkeys.has(r.airline_id+'|'+r.hub_airport_id));assert.notEqual(r.hub_airport_id,r.destination_airport_id);const s=d.sources.find(s=>s.id===r.source_id);assert.ok(s.revision_id,'Unpinned route source');}
for(const r of d.routes){assert.ok(['scheduled','charter'].includes(r.service_type));assert.ok(!/\bsuspended\b/i.test(r.note||''),'Suspended service in active dataset');assert.ok(['listed','seasonal'].includes(r.status));assert.ok(!(r.change_date>d.as_of && /begin|start|commenc|resum/i.test(r.note||'')),'Future start in active dataset');}
for(const id of ['UA','AF'])assert.ok(d.routes.some(r=>r.airline_id===id),`No routes for example airline ${id}`);
for(const dest of ['MCI','COS','FRA'])assert.ok(d.routes.some(r=>r.airline_id==='UA'&&r.hub_airport_id==='DEN'&&r.destination_airport_id===dest),`Missing user example UA DEN ${dest}`);
for(const dest of ['BOM','JFK'])assert.ok(d.routes.some(r=>r.airline_id==='AF'&&r.hub_airport_id==='CDG'&&r.destination_airport_id===dest),`Missing user example AF CDG ${dest}`);
const missing=d.hubs.filter(h=>h.coverage==='fetch_failed'||h.coverage==='no_matching_airline_rows');console.log(JSON.stringify({airlines:d.airlines.length,hubs:d.hubs.length,airports:d.airports.length,services:d.routes.length,excluded:d.excluded_routes.length,issues:d.issues.length,hubGaps:missing},null,2));

assert.equal(d.issues.length,0,'Resolve all extraction issues before releasing the snapshot');
assert.ok(d.hubs.every(h=>h.coverage==='parsed'),'Every hub must have a parsed source row');
assert.ok(d.airlines.every(a=>d.routes.some(r=>r.airline_id===a.id)),'Every member must have source-listed routes');
