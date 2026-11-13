const fs=require('fs'),assert=require('assert');
require('../web/client-analytics.js');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
function equal(a,b,path='root'){
 if(typeof a==='number'&&typeof b==='number')assert(Math.abs(a-b)<=1e-10*Math.max(1,Math.abs(a),Math.abs(b)),path);
 else if(Array.isArray(a)&&Array.isArray(b)){assert.equal(a.length,b.length,path);a.forEach((v,i)=>equal(v,b[i],path+'['+i+']'));}
 else if(a&&b&&typeof a==='object'&&typeof b==='object'){
  assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),path);
  for(const k of Object.keys(a))equal(a[k],b[k],path+'.'+k);
 }else assert.strictEqual(a,b,path);
}
for(const c of fixture.cases){
 const actual=globalThis.ICUClient.dashboard(fixture.bases[String(c.filters.hour||24)],fixture.records,c.filters);
 equal(actual,c.expected,JSON.stringify(c.filters));
}
console.log(JSON.stringify({passed:true,sql_comparison_cases:fixture.cases.length}));
