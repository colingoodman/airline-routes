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
