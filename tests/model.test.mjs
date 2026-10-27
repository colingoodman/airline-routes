import test from 'node:test';
import assert from 'node:assert/strict';
import {filterRoutes,visibleHubs,greatCircle,uniqueConnections,worldOffsets,shiftedPaths,fitPositions,routeBounds} from '../web/model.mjs';
const data={airlines:[{id:'UA',alliance_id:'star'},{id:'AF',alliance_id:'skyteam'}],airports:[],alliances:[],hubs:[{airline_id:'UA',airport_id:'DEN'},{airline_id:'AF',airport_id:'CDG'}],routes:[{airline_id:'UA',hub_airport_id:'DEN',destination_airport_id:'MCI',status:'listed',service_type:'scheduled'},{airline_id:'UA',hub_airport_id:'DEN',destination_airport_id:'FRA',status:'seasonal',service_type:'scheduled'},{airline_id:'AF',hub_airport_id:'CDG',destination_airport_id:'JFK',status:'listed',service_type:'scheduled'},{airline_id:'AF',hub_airport_id:'CDG',destination_airport_id:'NCE',status:'listed',service_type:'charter'}]};
const state=()=>({alliances:new Set(['star','skyteam']),airlines:new Set(),airports:new Set(),seasonal:true,charter:false});
test('alliance, airline and destination filters compose without adding routes',()=>{const s=state();s.alliances=new Set(['star']);assert.equal(filterRoutes(data,s).length,2);s.airlines.add('AF');assert.equal(filterRoutes(data,s).length,0);s.airlines=new Set(['UA']);s.airports.add('MCI');assert.deepEqual(filterRoutes(data,s),[data.routes[0]]);});
test('multiple airports are a union and disabled alliance set means no routes',()=>{const s=state();s.airports=new Set(['MCI','JFK']);assert.equal(filterRoutes(data,s).length,2);s.alliances.clear();assert.equal(filterRoutes(data,s).length,0);assert.equal(visibleHubs(data,s).length,0);});
test('seasonal and charter toggles work independently',()=>{const s=state();s.seasonal=false;assert.equal(filterRoutes(data,s).length,2);s.charter=true;assert.equal(filterRoutes(data,s).length,3);});
test('a shared hub remains only for selected airlines',()=>{const s=state();s.airlines.add('AF');assert.deepEqual(visibleHubs(data,s),[data.hubs[1]]);});
test('reciprocal hub records become one map connection, preserving service evidence',()=>{const a=data.routes[0],b={...a,hub_airport_id:'MCI',destination_airport_id:'DEN'};const result=uniqueConnections([a,b]);assert.equal(result.length,1);assert.equal(result[0].services.length,2);});
test('Pacific arcs split at the dateline without a world-spanning segment',()=>{const paths=greatCircle({latitude:35,longitude:140},{latitude:38,longitude:-122});assert.equal(paths.length,2);for(const p of paths)for(let i=1;i<p.length;i++){assert.ok(Math.abs(p[i][1]-p[i-1][1])<180);assert.ok(p[i].every(Number.isFinite));}assert.ok(Math.abs(paths[0].at(-1)[1])===180);});
test('coincident airports produce finite coordinates',()=>{const a={latitude:40,longitude:-75};for(const p of greatCircle(a,a))for(const x of p)assert.ok(x.every(Number.isFinite));});
test('world copies follow views multiple revolutions east or west',()=>{
 assert.ok(worldOffsets(160,560).includes(360));
 assert.ok(worldOffsets(160,560).includes(720));
 assert.ok(worldOffsets(-2000,-1600).includes(-1800));
 assert.ok(worldOffsets(1960,2360).includes(2160));
});
test('Pacific arc pieces meet exactly in adjacent world copies',()=>{
 const paths=greatCircle({latitude:35,longitude:140},{latitude:38,longitude:-122});
 const east=shiftedPaths(paths,0,120,250),west=shiftedPaths(paths,360,120,250);
 assert.deepEqual(east[0].at(-1),west[0][0]);
 assert.ok(Math.abs(west[0].at(-1)[1]-238)<1e-8);
 assert.ok(paths[1].at(-1)[1]<0,'Canonical geometry must remain unchanged');
});

test('fit routes uses the Pacific rather than a 262-degree longitude span',()=>{
 const points=[[35,140],[38,-122]],fit=fitPositions(points,180);
 assert.ok(Math.abs(fit[0][1]-fit[1][1])<100);
 assert.deepEqual(fitPositions([[35,140],[38,-122]],-180).map(p=>p[1]),[-220,-122]);
 assert.deepEqual(points,[[35,140],[38,-122]]);
 assert.deepEqual(fitPositions([],180),[]);
 assert.deepEqual(fitPositions([[40,-75]],-75),[[40,-75]]);
});

test('fit bounds include the northern arc, not only the endpoint airports',()=>{
 const a={latitude:35.77,longitude:140.39},b={latitude:40.69,longitude:-74.17},paths=greatCircle(a,b);
 const bounds=routeBounds([[a.latitude,a.longitude],[b.latitude,b.longitude]],paths,180);
 assert.ok(bounds[1][0]>60);
 assert.ok(bounds[1][1]-bounds[0][1]<180);
 for(const path of paths)for(const [lat,lon] of path){const x=lon+360*Math.round((180-lon)/360);assert.ok(lat>=bounds[0][0]&&lat<=bounds[1][0]);assert.ok(x>=bounds[0][1]&&x<=bounds[1][1]);}
});
