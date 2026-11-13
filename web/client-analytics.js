/* Browser aggregation of independently generated synthetic records only.
   Model metrics, missingness and importance retain the full synthetic cohort. */
(function(scope){
 'use strict';
 const labels=(a,b)=>a<b?-1:a>b?1:0;
 const frequencySort=(a,b)=>b.n-a.n||labels(a.label,b.label);
 function group(records,key){const result=new Map();for(const r of records){let k=key(r);if(!result.has(k))result.set(k,[]);result.get(k).push(r);}return result;}
 function average(values){return values.length?values.reduce((a,b)=>a+b,0)/values.length:null;}
 function dashboard(base,records,filters={}){
  if(records.mode!=='demo'||base.meta.mode!=='demo')throw Error('Synthetic browser analytics only');
  let hour=Number(filters.hour||24);if(![1,24,48,72].includes(hour))throw Error('Invalid landmark');
  const selected=records.stays.filter(s=>(!filters.sex||filters.sex==='all'||s.sex===filters.sex)&&(!filters.age||filters.age==='all'||s.age_band===filters.age)&&(!filters.unit||filters.unit==='all'||s.unit===filters.unit));
  const patient=new Map(selected.map(s=>[s.patient_id,s]));
  const admissions=new Set(selected.map(s=>s.admission_id));
  const stays=new Map(selected.map(s=>[s.stay_id,s]));
  const out=JSON.parse(JSON.stringify(base));
  out.filters={hour,sex:filters.sex||'all',age:filters.age||'all',unit:filters.unit||'all'};
  out.summary={patients:patient.size,admissions:admissions.size,stays:selected.length,los:average(selected.map(s=>s.los_days)),mortality:average(selected.map(s=>s.outcome)),age:average([...patient.values()].map(s=>s.age).filter(a=>a!==null))};
  out.units=[...group(selected,s=>s.unit)].map(([label,rs])=>({label,n:rs.length,mortality:average(rs.map(s=>s.outcome))})).sort(frequencySort);
  out.ages=[...group([...patient.values()],s=>s.age_band)].map(([label,rs])=>({label,n:rs.length})).sort((a,b)=>labels(a.label,b.label));
  out.sexes=[...group([...patient.values()],s=>s.sex)].map(([label,rs])=>({label,n:rs.length})).sort(frequencySort);
  out.diagnoses=[...group(records.diagnoses.filter(r=>admissions.has(r.admission_id)),r=>r.diagnosis)].map(([label,rs])=>({label,n:rs.length})).sort(frequencySort).slice(0,10);
  out.drugs=[...group(records.prescriptions.filter(r=>admissions.has(r.admission_id)),r=>r.drug)].map(([label,rs])=>({label,n:rs.reduce((sum,r)=>sum+r.orders,0),admissions:rs.length})).sort(frequencySort).slice(0,10);
  const predictions=records.predictions.filter(r=>stays.has(r.stay_id));
  out.coverage=[...group(predictions,r=>r.hour)].map(([h,rs])=>({hour:h,n:rs.length,patients:new Set(rs.map(r=>stays.get(r.stay_id).patient_id)).size})).sort((a,b)=>a.hour-b.hour);
  out.risk=[...group(predictions.filter(r=>r.hour===hour),r=>Math.min(9,Math.floor(r.probability_cal*10)))].map(([bucket,rs])=>({bucket,n:rs.length})).sort((a,b)=>a.bucket-b.bucket);
  return out;
 }
 scope.ICUClient={dashboard};
})(typeof window==='undefined'?globalThis:window);
