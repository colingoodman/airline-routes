// Self-contained viewer: compact map projection at startup, complete data on download.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {buildRuntime} from './build-runtime.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),web=path.join(root,'web');
buildRuntime(root);
const read=p=>fs.readFileSync(path.join(web,p),'utf8'),safeJson=s=>s.replaceAll('<','\\u003c');
let app=read('app.mjs').replace(/^import .*?;\n/gm,'');
const embeddedResponse=id=>`Promise.resolve({ok:true,json:async()=>JSON.parse(document.getElementById('${id}').textContent)})`;
app=app.replace("fetch('map-data.json', {cache:'no-cache'})",embeddedResponse('embedded-map')).replace("fetch('world.geojson')",embeddedResponse('embedded-world'));
app=app.replace('function persist(){',"function persist(){if(location.protocol==='file:')return;");
let html=read('index.html').replace(/<link rel="stylesheet" href="vendor\/leaflet.css">/,`<style>${read('vendor/leaflet.css')}</style>`).replace(/<link rel="stylesheet" href="style.css[^\"]*">/,`<style>${read('style.css')}</style>`);
html=html.replace('<a href="https://github.com/colingoodman/airline-routes#readme" target="_blank" rel="noopener">Project documentation</a>','<p>This portable viewer includes its complete data and map assets. The source repository contains methodology and rebuild instructions.</p>');
const inline=(code,type='')=>`<script${type?' type="'+type+'"':''}>${code.replaceAll('</script','<\\/script')}</script>`;
const jsonScript=(id,json)=>`<script id="${id}" type="application/json">${safeJson(json)}</script>`;
const modules=['geography.mjs','model.mjs','route-renderer.mjs','runtime.mjs','perf.mjs'].map(p=>read(p).replace(/^import .*?;\n/gm,'').replaceAll('export ','')).join('\n');
html=html.replace(/<script src="vendor\/leaflet.js"><\/script><script type="module" src="app.mjs[^\"]*"><\/script>/,
 jsonScript('canonical-data',JSON.stringify(JSON.parse(read('data.json'))))+jsonScript('embedded-map',read('map-data.json'))+jsonScript('embedded-world',JSON.stringify(JSON.parse(read('world.geojson'))))+inline(read('vendor/leaflet.js'))+inline(modules+'\n'+app,'module'));
const out=path.resolve(process.argv[2]||path.join(root,'work','alliance-map.html'));fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,html);console.log(out);
