const perfEnabled=typeof location!=='undefined'&&new URLSearchParams(location.search).has('audit');
const perfSamples={};
export function recordMetric(name,ms,details={}){
 if(!perfEnabled)return;
 const previous=perfSamples[name]||{count:0,samples:[]};
 perfSamples[name]={count:previous.count+1,last_ms:+ms.toFixed(2),max_ms:Math.max(previous.max_ms||0,+ms.toFixed(2)),samples:[...previous.samples.slice(-19),+ms.toFixed(2)],...details};
 document.documentElement.dataset.performance=JSON.stringify(perfSamples);
}
export function measure(name,fn){if(!perfEnabled)return fn();const start=performance.now();try{return fn();}finally{recordMetric(name,performance.now()-start);}}
export function markReady(){if(perfEnabled)requestAnimationFrame(()=>requestAnimationFrame(()=>recordMetric('ready',performance.now(),{canvas_pixels:[...document.querySelectorAll('.leaflet-routes-pane canvas,.leaflet-airports-pane canvas')].reduce((n,c)=>n+c.width*c.height,0)})));}
