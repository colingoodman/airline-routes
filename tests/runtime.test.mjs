import test from'node:test';import assert from'node:assert/strict';import fs from'node:fs';import{createHash}from'node:crypto';
import{projectMapData}from'../scripts/build-runtime.mjs';import{decodeMapData}from'../web/runtime.mjs';import{filterRoutes,visibleHubs,airlineOptions,indexData,routeModel}from'../web/model.mjs';
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
