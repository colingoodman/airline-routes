import test from'node:test';import assert from'node:assert/strict';import fs from'node:fs';import{createHash}from'node:crypto';
import{projectMapData,freshnessFor}from'../scripts/build-runtime.mjs';import{decodeMapData,freshnessText}from'../web/runtime.mjs';import{filterRoutes,visibleHubs,airlineOptions,indexData,routeModel}from'../web/model.mjs';
const raw=fs.readFileSync(new URL('../web/data.json',import.meta.url)),canonical=JSON.parse(raw),packed=JSON.parse(fs.readFileSync(new URL('../web/map-data.json',import.meta.url))),view=decodeMapData(packed);
test('checked-in map projection is exactly derived from the complete normalized dataset',()=>{assert.deepEqual(packed,projectMapData(canonical,createHash('sha256').update(raw).digest('hex')));});
test('every projected service preserves its ID, source, brand, flags and annotations',()=>{assert.equal(view.routes.length,canonical.routes.length);for(let i=0;i<view.routes.length;i++)assert.deepEqual(view.routes[i],canonical.routes[i],`Service ${i} must retain its exact source label and evidence`);});
test('projection preserves every filter result and model classification',()=>{
 const base={alliances:new Set(canonical.alliances.map(a=>a.id)),airlines:new Set(),airports:new Set(),seasonal:true,charter:false,lowCost:'all',regional:false};
 const states=[base,{...base,alliances:new Set(['nonaligned'])},{...base,airports:new Set(['DEN','NRT'])},{...base,airlines:new Set(['UA','AC'])},...[false,true].flatMap(regional=>['all','yes','no','unknown'].flatMap(lowCost=>[false,true].map(charter=>({...base,regional,lowCost,charter}))))];
 for(const state of states){assert.deepEqual(filterRoutes(view,state).map(r=>r.id),filterRoutes(canonical,state).map(r=>r.id));assert.deepEqual(visibleHubs(view,state).map(h=>[h.airline_id,h.airport_id]),visibleHubs(canonical,state).map(h=>[h.airline_id,h.airport_id]));assert.deepEqual(airlineOptions(view,state).map(a=>a.id),airlineOptions(canonical,state).map(a=>a.id));}
 const a=indexData(canonical),b=indexData(view);for(let i=0;i<view.routes.length;i++)assert.deepEqual(routeModel(b,view.routes[i]),routeModel(a,canonical.routes[i]));
});
test('unknown map projection versions fail explicitly',()=>{assert.throws(()=>decodeMapData({projection_version:999}),/Unsupported/);});

test('freshness uses actual source checks and never fabricates them from the snapshot date',()=>{
 assert.equal(freshnessFor(canonical),null);
 assert.match(freshnessText({as_of:'2099-01-01'}),/unavailable/);
 const summary=freshnessFor({sources:[{kind:'airport_passenger_routes',fetch:{checked_at:'2026-10-20T00:00:00Z'}},{kind:'airport_passenger_routes',fetch:{mode:'legacy_cache'}},{kind:'airport_metadata',fetch:{checked_at:'2026-10-28T00:00:00Z'}}]});
 assert.equal(summary.route_sources_known,1);assert.equal(summary.route_sources_total,2);
 assert.match(freshnessText({freshness:summary},Date.parse('2026-10-28T01:00:00Z')),/1\/2 dated/);
 assert.match(freshnessText({freshness:summary},Date.parse('2026-10-28T01:00:00Z')),/over a week old/);
});
