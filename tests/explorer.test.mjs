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
