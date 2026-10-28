import test from 'node:test';
import assert from 'node:assert/strict';
import {airportMatches,defaultExplorerState,explorerParams,restoreExplorerState,filterRoutes} from '../web/model.mjs';
const data={alliances:[{id:'star'},{id:'sky'}],airlines:[{id:'UA',alliance_id:'star'},{id:'AF',alliance_id:'sky'}],airports:[{id:'DEN',country:'US'},{id:'NRT',country:'JP'},{id:'ALY',country:'EG',former_iata_codes:['HBE']}],routes:[{airline_id:'UA',hub_airport_id:'DEN',destination_airport_id:'NRT',service_type:'scheduled',status:'listed'}]};
test('airport modes distinguish union, both endpoints and the documented hub endpoint',()=>{
 const r=data.routes[0],s=defaultExplorerState(data);s.airports.add('NRT');assert.equal(airportMatches(r,s),true);s.airportMode='hub';assert.equal(airportMatches(r,s),false);s.airportMode='between';assert.equal(airportMatches(r,s),false);s.airports.add('DEN');assert.equal(airportMatches(r,s),true);s.airportMode='hub';assert.equal(airportMatches(r,s),true);
});
test('state round trips empty sets, incompatible selections, modes and display preferences',()=>{
 const s=defaultExplorerState(data);s.alliances.clear();s.airlines.add('UA');s.airports.add('NRT');s.airportMode='between';s.colorBy='airline';s.labels='on';s.regional=true;s.seasonal=false;s.charter=true;s.lowCost='unknown';s.focus='DEN';s.compareShow.clear();s.minKm=100;s.maxKm=9000;
 assert.deepEqual(restoreExplorerState(data,explorerParams(s,data)),s);assert.equal(filterRoutes(data,s).length,0);
});
test('old airport aliases and malformed URLs restore safely',()=>{
 const s=restoreExplorerState(data,'airports=HBE,NONSENSE&airport_mode=invalid&min_km=20000&max_km=10&focus=BAD&compare_a=BAD&labels=evil');assert.deepEqual([...s.airports],['ALY']);assert.equal(s.airportMode,'touches');assert.equal(s.labels,'auto');assert.equal(s.focus,'');assert.equal(s.compareA,'');assert.equal(s.minKm,10);assert.equal(s.maxKm,20000);
});

import {destinationGroups,sortDestinations,airlineNetworkStats,airportDistanceKm} from '../web/model.mjs';
const located={...data,airports:[{id:'DEN',country:'US',city:'Denver',latitude:39.86,longitude:-104.67},{id:'NRT',country:'JP',city:'Tokyo',latitude:35.77,longitude:140.39},{id:'ALY',country:'EG',city:'Alexandria',latitude:30.92,longitude:29.7}]};
test('focused destinations deduplicate reciprocal and multiple airline evidence',()=>{
 const r=data.routes[0],routes=[r,{...r,airline_id:'AF'},{...r,hub_airport_id:'NRT',destination_airport_id:'DEN'}],groups=destinationGroups(located,routes,'NRT');assert.equal(groups.length,1);assert.equal(groups[0].id,'DEN');assert.equal(groups[0].airlines.size,2);assert.equal(groups[0].routes.length,3);assert.ok(groups[0].distanceKm>9000);assert.equal(groups[0].seasonalOnly,false);assert.equal(destinationGroups(located,routes,'ALY').length,0);assert.equal(destinationGroups(located,routes).length,2);
});
test('distance is symmetric across the date line and destination sorting is stable',()=>{
 const a={latitude:0,longitude:179},b={latitude:0,longitude:-179};assert.ok(Math.abs(airportDistanceKm(a,b)-222.39)<.1);assert.equal(airportDistanceKm(a,a),0);assert.equal(airportDistanceKm(a,b),airportDistanceKm(b,a));
 const groups=destinationGroups(located,data.routes);assert.equal(sortDestinations(groups,'name')[0].id,'DEN');assert.equal(sortDestinations(groups,'country')[0].id,'NRT');assert.equal(airlineNetworkStats(data.routes).get('UA').airports.size,2);
});

import {geographyMatches,indexData,routeDistanceKm,stableAirlineColor} from '../web/model.mjs';
import {airportRegion} from '../web/geography.mjs';
test('geography endpoint modes compose country and region on the same airport',()=>{
 const s=defaultExplorerState(located),ix=indexData(located),r=data.routes[0];s.countries.add('US');assert.equal(geographyMatches(ix,r,s),true);s.geoMode='both';assert.equal(geographyMatches(ix,r,s),false);s.geoMode='destination';assert.equal(geographyMatches(ix,r,s),false);s.geoMode='hub';assert.equal(geographyMatches(ix,r,s),true);s.geoMode='either';s.regions.add('AS');assert.equal(geographyMatches(ix,r,s),false);s.countries.clear();assert.equal(geographyMatches(ix,r,s),true);
});
test('distance boundaries are inclusive, cached per physical airport pair and dataset',()=>{
 const ix=indexData(located),r=data.routes[0],distance=routeDistanceKm(ix,r),s=defaultExplorerState(located);s.minKm=distance;s.maxKm=distance;assert.equal(geographyMatches(ix,r,s),true);s.maxKm=distance-1;assert.equal(geographyMatches(ix,r,s),false);assert.equal(routeDistanceKm(ix,{...r,hub_airport_id:r.destination_airport_id,destination_airport_id:r.hub_airport_id}),distance);assert.equal(ix.distances.size,1);assert.equal(airportRegion({country:'US'}),'NA');assert.equal(airportRegion({country:'XX'}),'unknown');assert.equal(stableAirlineColor('UA'),stableAirlineColor('UA'));assert.notEqual(stableAirlineColor('UA'),stableAirlineColor('AF'));
});
