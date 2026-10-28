import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';
const pick=(value,keys)=>Object.fromEntries(keys.filter(k=>value[k]!==undefined).map(k=>[k,value[k]]));
export function projectMapData(data,sha256){
 const airlineIndex=new Map(data.airlines.map((a,i)=>[a.id,i])),airportIndex=new Map(data.airports.map((a,i)=>[a.id,i])),brandIndex=new Map(data.service_brand_models.map((b,i)=>[b.id,i])),sourceIndex=new Map(data.sources.map((s,i)=>[s.id,i]));
 return {projection_version:1,canonical_sha256:sha256,as_of:data.as_of,scope:data.scope,alliances:data.alliances,discovery_audit:{summary:data.discovery_audit.summary},issues_count:data.issues.length,
  airlines:data.airlines.map(a=>pick(a,['id','name','iata','icao','alliance_id','membership_type','low_cost','regional'])),
  airports:data.airports.map(a=>pick(a,['id','iata','icao','ident','local_code','former_iata_codes','name','city','country','latitude','longitude'])),
  service_brand_models:data.service_brand_models.map(b=>pick(b,['id','name','airline_id','low_cost','regional'])),
  sources:data.sources.map(s=>pick(s,['id','url'])),
  hubs:data.hubs.map(h=>pick(h,['airline_id','airport_id','kind','source_id','coverage','route_count','note','seasonal'])),
  routes:data.routes.map(r=>{const row=[airlineIndex.get(r.airline_id),airportIndex.get(r.hub_airport_id),airportIndex.get(r.destination_airport_id),brandIndex.get(r.service_brand_id),sourceIndex.get(r.source_id),(r.status==='seasonal'?1:0)|(r.service_type==='charter'?2:0),r.note||null,r.id];row.push(r.change_date||null,r.via_note||null,r.service_brand!==data.service_brand_models[brandIndex.get(r.service_brand_id)].name?r.service_brand:null);while(row.length>8&&row.at(-1)===null)row.pop();return row;})};
}
export function buildRuntime(root,options={}){const input=options.data||path.join(root,'web/data.json'),output=options.out||path.join(root,'web/map-data.json');const raw=fs.readFileSync(input),data=JSON.parse(raw);const projected=projectMapData(data,createHash('sha256').update(raw).digest('hex'));const packed=JSON.stringify(projected)+'\n';fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,packed);return {canonical_bytes:raw.length,runtime_bytes:Buffer.byteLength(packed)};}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const {values}=parseArgs({options:{data:{type:'string'},out:{type:'string'}}});
 console.log(buildRuntime(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),values));
}
