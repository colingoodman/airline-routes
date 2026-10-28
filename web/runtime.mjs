// Generated display projection. The full normalized data.json remains the download.
export function decodeMapData(packed){
 if(packed.projection_version!==1)throw new Error('Unsupported map-data projection; regenerate it from data.json.');
 return {...packed,routes:packed.routes.map(row=>{
  const [a,o,d,b,s,flags,note,id,date,via,brandLabel]=row,brand=packed.service_brand_models[b];
  return {id,airline_id:packed.airlines[a].id,hub_airport_id:packed.airports[o].id,destination_airport_id:packed.airports[d].id,service_brand_id:brand.id,service_brand:brandLabel||brand.name,source_id:packed.sources[s].id,status:flags&1?'seasonal':'listed',service_type:flags&2?'charter':'scheduled',...(note?{note}:{}),...(date?{change_date:date}:{}),...(via?{via_note:via}:{})};
 })};
}
export function prepareDownload(anchor){
 const embedded=document.getElementById('canonical-data');if(!embedded)return;
 let url;anchor.addEventListener('click',()=>{if(!url)url=URL.createObjectURL(new Blob([embedded.textContent],{type:'application/json'}));anchor.href=url;});
}

// A dataset date is not proof of when its underlying source pages were checked.
export function freshnessText(data,now=Date.now()){
 const f=data.freshness;
 if(!f)return 'Per-source check dates unavailable for this legacy snapshot.';
 const date=value=>new Date(value).toISOString().slice(0,10);
 const parts=[];
 if(f.route_sources_known){
  const oldest=date(f.oldest_route_check),newest=date(f.newest_route_check);
  parts.push(`Route source checks: ${oldest===newest?oldest:oldest+' to '+newest} UTC (${f.route_sources_known}/${f.route_sources_total} dated)`);
  if(now-Date.parse(f.oldest_route_check)>7*86400000)parts.push('some route checks are over a week old');
 }else parts.push('Route source check dates unavailable');
 if(f.airport_metadata_check)parts.push(`airport metadata checked ${date(f.airport_metadata_check)} UTC`);
 return parts.join(' · ')+'.';
}
