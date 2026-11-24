'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>v==null?'—':Number(v).toLocaleString('en-US',{maximumFractionDigits:0});
const dec=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
const pct=v=>v==null?'—':(100*v).toFixed(1)+'%';
let data,research=null,page='overview',hour=24,requestId=0,pending=false;
const offline=location.protocol==='file:';
const staticMode=offline||document.querySelector('meta[name="icu-runtime"]')?.content==='static';
const clientFiltering=staticMode&&Boolean(window.ICUClient&&window.ICU_CLIENT_DATA);
function panel(title,sub,body,chip=''){return `<section class="panel"><div class="panel-head"><div><h2>${title}</h2><div class="panel-sub">${sub}</div></div>${chip?`<span class="chip">${chip}</span>`:''}</div>${body}</section>`}
function kpi(label,value,note,primary=false,symbol='↗'){return `<article class="kpi ${primary?'primary':''}"><div class="kpi-label">${label}<span class="kpi-symbol">${symbol}</span></div><div class="kpi-number">${value}</div><div class="kpi-note">${note}</div></article>`}
function bars(rows,percent=false){if(!rows.length)return '<div class="empty">当前筛选无可展示记录</div>';let max=Math.max(...rows.map(r=>r.n),1);return `<div class="bars">${rows.map(r=>`<div class="bar-row"><span class="bar-label" title="${esc(r.label)}">${esc(r.label)}</span><div class="track"><div class="fill" style="width:${(r.n/max*100).toFixed(2)}%"></div></div><span class="bar-value">${percent?dec(r.n,2):num(r.n)}</span></div>`).join('')}</div>`}
function table(headers,rows){return `<div class="table-wrap"><table><thead><tr>${headers.map((h,i)=>`<th class="${i?'num':''}">${h}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map((v,i)=>`<td class="${i?'num':'table-title'}">${v}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}">当前筛选无记录</td></tr>`}</tbody></table></div>`}
function line(series,labels,ymax=1,percent=true){let W=520,H=210,L=40,R=18,T=16,B=32,w=W-L-R,h=H-T-B;let sx=i=>L+(labels.length===1?w/2:i*w/(labels.length-1)),sy=v=>T+h*(1-v/ymax);return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(series.map(s=>s.name).join('、'))}">${[0,.25,.5,.75,1].map(f=>`<line class="gridline" x1="${L}" x2="${W-R}" y1="${sy(f*ymax)}" y2="${sy(f*ymax)}"/><text x="${L-9}" y="${sy(f*ymax)+4}" text-anchor="end">${percent==='decimal'?dec(f*ymax,2):percent?Math.round(f*ymax*100)+'%':num(f*ymax)}</text>`).join('')}${labels.map((l,i)=>`<text x="${sx(i)}" y="${H-6}" text-anchor="middle">${esc(l)}</text>`).join('')}${series.map(s=>`<polyline points="${s.values.map((v,i)=>`${sx(i)},${sy(v)}`).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2.5"/>${s.values.map((v,i)=>`<circle cx="${sx(i)}" cy="${sy(v)}" r="4" fill="white" stroke="${s.color}" stroke-width="2"><title>${esc(s.name)} · ${esc(labels[i])}: ${percent==='decimal'?dec(v):percent?pct(v):num(v)}</title></circle>`).join('')}`).join('')}</svg><div class="legend">${series.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('')}</div>`}
function checks(){return data.checks.map(r=>`<div class="check"><span class="check-icon">${r.passed?'✓':'!'}</span><div><b>${esc(r.rule)}</b><small>${esc(r.detail)}</small></div><span>${num(r.checked)} checked</span></div>`).join('')}
function overview(){let s=data.summary,base=data.coverage[0]?.n||0;return `<div class="kpis">${kpi('独立患者',num(s.patients),'DISTINCT PATIENTS · 当前筛选',true,'◎')}${kpi('符合条件的住院',num(s.admissions),'DISTINCT HOSPITAL ADMISSIONS',false,'↗')}${kpi('ICU 停留',num(s.stays),'ELIGIBLE ICU STAYS',false,'◫')}${kpi('90 天结局率',pct(s.mortality),'按 ICU 停留计 · 自入 ICU 起 90 天',false,'⌁')}</div><div class="grid">${panel('ICU 科室分布','按每次 ICU 停留首次科室计 · 当前筛选',bars(data.units.slice(0,7)),'COHORT MIX')}${panel('预测时点覆盖','每个预测时点仍符合条件的 ICU 停留',`<div class="mini-stats"><div><strong>${num(data.coverage.find(r=>r.hour===hour)?.n||0)}</strong><small>${hour}h 可评价停留</small></div><div><strong>${pct(base?(data.coverage.find(r=>r.hour===hour)?.n||0)/base:0)}</strong><small>相对 1h 覆盖</small></div></div>${line([{name:'符合条件的 ICU 停留',color:'#46795e',values:[1,24,48,72].map(h=>data.coverage.find(r=>r.hour===h)?.n||0)}],['1h','24h','48h','72h'],Math.max(base,1),false)}`,'LANDMARK COVERAGE')}</div><div class="grid equal">${panel('年龄结构','首次符合条件的 ICU 时年龄 · 每位患者仅计一次',bars(data.ages),'PATIENT PROFILE')}${panel('分析解读','清楚说明每张图能回答什么',`<div class="prose"><p>该队列包含 <strong>${num(s.patients)}</strong> 位患者、<strong>${num(s.admissions)}</strong> 次住院与 <strong>${num(s.stays)}</strong> 次 ICU 停留。三者是不同的统计单位。</p><div class="split-note">后续时点样本减少，时点比较应使用对应的风险集。</div><p>诊断与处方页用于回顾性描述；模型页读取已验证的折外评价，避免把出院信息作为预测特征。</p></div>`,'ANALYST NOTE')}</div>`}
function cohort(){return `<div class="kpis">${kpi('独立患者',num(data.summary.patients),'以患者为统计单位',true)}${kpi('平均年龄',dec(data.summary.age,1)+'<small>years</small>','已知年龄 · 首次符合条件时')}${kpi('平均 ICU 时长',dec(data.summary.los,1)+'<small>days</small>','完整停留时长 · 回顾性描述')}${kpi('每位患者 ICU 次数',data.summary.patients?dec(data.summary.stays/data.summary.patients,2):'—','ICU 次数 / 独立患者')}</div><div class="grid equal">${panel('患者年龄分布','保留 Unknown 类别，不把缺失年龄归入高龄组',bars(data.ages))}${panel('患者性别分布','源表性别标签 · 每位患者仅计一次',bars(data.sexes))}</div>${panel('科室结构与 90 天结局','按停留计；病例组合不同，不能作因果解释或医院质量排名',table(['首次科室','ICU 停留','结局率'],data.units.map(r=>[esc(r.label),num(r.n),pct(r.mortality)])))}`}
function clinical(){return `<div class="grid equal">${panel('常见诊断','ICD-9 / ICD-10 联合字典 · 每住院/编码/版本去重',bars(data.diagnoses),'TOP 10')}${panel('常见处方','原始处方记录条数 · 药品名称统一大小写',bars(data.drugs),'TOP 10')}</div><div class="grid equal">${panel('诊断频次明细','同一次住院可以有多个诊断；同名不同编码可能分别计数',table(['诊断名称','住院-编码记录'],data.diagnoses.map(r=>[esc(r.label),num(r.n)])))}${panel('处方频次明细','处方记录不等于实际给药；未跨剂量单位汇总',table(['药品名称','处方记录','涉及住院'],data.drugs.map(r=>[esc(r.label),num(r.n),num(r.admissions)])))}</div><div class="notice">这些诊断和处方可能包含预测时点之后的信息。本页只用于描述性分析，不能直接拿来训练早期预测模型。</div>`}
function quality(){return `<div class="grid equal">${panel('数据质量与一致性检查','ETL 本次检查 + 明确标注的上游冻结核验',checks(),'VALIDATION')}${panel('数据契约','先约定粒度和口径，再设计分析',`<div class="prose"><h3>三种实体，三种主键</h3><p>患者 patient_id → 住院 admission_id → ICU stay_id。诊断、处方与预测保持独立事实表，避免多对多连接导致数量膨胀。</p><h3>预测可用性</h3><p>临床特征同时约束测量时间与报告时间。</p><h3>时间与缺失</h3><p>日期经过患者级偏移，不把跨患者年月当作真实运营趋势。缺失率表示记录可得性，不等同数据错误率。</p></div>`,'DATA CONTRACT')}</div>${panel(`${hour}h 特征缺失情况`,'冻结全队列的特征统计 · 分母是该时点可评价停留 · 不随人口筛选变化',`<div class="quality-table">${table(['特征','可评价停留','已知','缺失率','分布'],data.missingness.map(r=>[esc(r.feature),num(r.risk_stays),num(r.known),pct(r.missing_fraction),`<div class="quality-meter"><span style="width:${(100*r.missing_fraction).toFixed(2)}%"></span></div>`]))}</div>`,'MISSINGNESS')}`}

const pages = {
    overview: ['研究总览','基于 MIMIC-IV 的临床数据研究与智能预测分析平台',studyOverview],
    cohort: ['临床队列构建','每个预测时点有哪些 ICU 停留可纳入？',studyCohort],
    baseline: ['患者基线特征','谁进入了队列？索引 ICU 停留的患者特征如何？',studyBaseline],
    clinical: ['临床统计分析','结局组特征相差多少？调整关联如何解释？',studyStatistics],
    models: ['动态预测模型','模型排序、概率质量和阈值表现如何？',modelStudy],
    explanation: ['模型解释性','哪些临床概念历史影响模型输出？',studyExplanation],
    quality: ['数据质量与研究可复现性','如何追溯变量、检查和实验？',quality],
};
function selectedPage() {
    const key=location.hash.slice(1);
    return Object.hasOwn(pages,key)?key:'overview';
}
function render() {
    if (pending || !data) return;
    const [title,subtitle,body]=pages[page];
    const demo=data.meta.mode==='demo';
    const filtersActive=['cohort','baseline','clinical'].includes(page);
    const hourActive=['cohort','models','explanation','quality'].includes(page);
    $('.filterbar').hidden=!filtersActive&&!hourActive;
    $$('.filter').forEach(wrapper=>wrapper.hidden=!filtersActive);
    $('.landmark').hidden=!hourActive;
    $('#page-title').textContent=title;
    $('#page-subtitle').textContent=subtitle;
    for (const button of $$('nav button')) {
        const active=button.dataset.page===page;
        button.classList.toggle('active',active);
        button.setAttribute('aria-current',active?'page':'false');
    }
    for (const button of $$('[data-hour]')) {
        const active=Number(button.dataset.hour)===hour;
        button.classList.toggle('active',active);
        button.setAttribute('aria-pressed',String(active));
    }
    $('#filter-scope').textContent=filtersActive?
        (staticMode&&!clientFiltering?'离线快照固定人群。':'人群筛选作用于队列计数、画像及诊断处方汇总。')+' Table 1、调整分析及预测评价使用完整队列。':
        hourActive?'时点切换使用对应的全队列评价。':'';
    $('#content').innerHTML=(demo?'<div class="figure-provenance">以下图表数据 · 独立模拟 SYNTHETIC</div>':
        '<div class="figure-provenance">以下图表数据 · MIMIC-IV 3.1 Development · 本地授权分析</div>')+body();
}
async function readResearch() {
    if(staticMode) return window.ICU_RESEARCH||null;
    const response=await fetch('/api/research');
    if(response.status===404) return null;
    if(!response.ok) throw Error('研究汇总不可用');
    return response.json();
}
let researchLoad;
async function load() {
    const id=++requestId;
    pending=true;
    $('#export').disabled=true;
    $('#content').innerHTML='<div class="loading">正在计算当前汇总…</div>';
    try {
        const filters={hour,sex:$('#sex').value,age:$('#age').value,unit:$('#unit').value};
        let result;
        if(staticMode) {
            const snapshot=window.ICU_PREVIEW[String(hour)];
            result=clientFiltering?window.ICUClient.dashboard(snapshot,window.ICU_CLIENT_DATA,filters):snapshot;
        } else {
            const response=await fetch('/api/dashboard?'+new URLSearchParams(filters));
            if(!response.ok) {
                const failure = await response.json().catch(() => ({}));
                throw Error(failure.error || '分析库读取失败');
            }
            result=await response.json();
        }
        researchLoad??=readResearch().catch(error=>{researchLoad=null;throw error;});
        const material=await researchLoad;
        if(id!==requestId) return;
        if(material&&material.mode!==result.meta.mode) throw Error('数据模式不一致');
        data=result;
        research=material;
        const demo=data.meta.mode==='demo';
        $('#notice').classList.toggle('demo',demo);
        $('#notice').textContent=demo?'独立模拟数据 SYNTHETIC · 用于演示筛选与研究流程':
            '本地研究数据 · MIMIC-IV 3.1 Development · 单中心回顾性内部验证';
        $('#mode-label').textContent=demo?'模拟演示':'本地授权';
        $('#footer-info').textContent=demo?'SYNTHETIC DEMO':'RESTRICTED LOCAL RESEARCH';
        for(const key of ['sex','age','unit']) {
            const select=$('#'+key);
            if(select.options.length===1) for(const label of data.options[key]) select.add(new Option(label,label));
            select.disabled=staticMode&&!clientFiltering;
        }
        pending=false;
        $('#export').disabled=false;
        render();
    } catch(error) {
        if(id!==requestId) return;
        pending=false;
        $('#content').innerHTML=`<div class="error">${esc(error.message)}。请检查数据模式或启动入口。<button id="retry">重新加载</button></div>`;
        $('#retry').onclick=load;
    }
}
for(const button of $$('nav button')) button.onclick=()=>{location.hash=button.dataset.page;};
window.addEventListener('hashchange',()=>{page=selectedPage();render();});
for(const button of $$('[data-hour]')) button.onclick=()=>{hour=Number(button.dataset.hour);load();};
for(const key of ['sex','age','unit']) $('#'+key).onchange=load;
$('#reset').onclick=()=>{for(const key of ['sex','age','unit']) $('#'+key).value='all';hour=24;load();};
$('#export').onclick=()=>{
    if(!data||pending) return;
    const mode=data.meta.mode==='demo'?'SYNTHETIC':'RESTRICTED_LOCAL';
    const documentData={classification:mode,page,cohort_summary:data,full_cohort_analysis:research};
    const url=URL.createObjectURL(new Blob([JSON.stringify(documentData,null,2)],{type:'application/json'}));
    const link=document.createElement('a');
    link.href=url;link.download=`icu-${mode}-${page}-${hour}h.json`;
    link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
};
page=selectedPage();
load();
