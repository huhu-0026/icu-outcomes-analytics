'use strict';

function overviewCards(cards) {
    return '<div class="picots">' + cards.map(([name, detail]) =>
        `<div><strong>${name}</strong><p>${detail}</p></div>`).join('') + '</div>';
}

function studyCards() {
    return overviewCards([
        ['P · Population', '符合条件的 MIMIC-IV 3.1 ICU Development 队列'],
        ['I · Index model', '利用已报告的临床轨迹生成动态风险概率'],
        ['C · Comparator', '同一时点的 Logistic 基准'],
        ['O · Outcome', '自入 ICU 日起 90 天死亡标签'],
        ['T · Timing', '入科后 1、24、48、72 小时'],
        ['S · Setting', '单中心回顾性队列，患者级内部验证'],
    ]);
}

function workflow() {
    return '<div class="entity-map"><span>定义队列与结局</span><b>→</b><span>确定各时点可评价的停留</span><b>→</b><span>按患者分组验证</span></div>' +
        '<div class="entity-map"><span>研究队列</span><b>→</b><span>每人首个合格 ICU 停留</span><b>→</b><span>描述基线特征</span></div>';
}

function studyOverview() {
    return '<div class="study-hero"><p>个人临床研究与医学 AI 实践</p>' +
        '<h2>ICU 入科后的死亡风险预测</h2>' +
        '<p>在入科后 1、24、48、72 小时，用当时已报告的信息，估计从入科日起 90 天内有记录的死亡风险。</p></div>' +
        panel('三个研究问题','',overviewCards([
            ['比较模型', '重点看入科后 24 小时。比较逻辑回归的时点快照与 LSTM 的历史序列，观察两者区分高低风险的能力。'],
            ['检查概率校准', '重点看入科后 1 小时。用 Brier 分数比较同一个 LSTM 校准前后的概率误差。'],
            ['解释模型输出', '把历史特征按临床概念分组，查看各组对预测输出的贡献大小。'],
        ])) +
        panel('研究分析流程','预测评价与基线描述使用各自的分析人群',workflow()) +
        panel('PICOTS 研究框架','预测模型比较采用同一时点及人群',studyCards()) +
        panel('数据到演示','真实研究在授权环境运行，公开看板计算独立模拟汇总',
              '<div class="entity-map"><span>冻结研究数据与已有产物</span><b>→</b><span>Python ETL 与 SQL</span><b>→</b><span>本地看板与报告</span></div>' +
              '<div class="entity-map"><span>独立模拟库</span><b>→</b><span>白名单静态构建</span><b>→</b><span>公开看板</span></div>');
}

function studyCohort() {
    const synthetic = data.meta.mode === 'demo';
    const cohortDetails = synthetic
        ? '独立模拟队列 → 患者、住院、ICU 停留 → 各时点有评分记录的停留'
        : 'MIMIC ICU → 有效入出科、年龄 >16、停留 >1h → 患者分区 → 冻结 Development → 时点风险集';
    const coverage = table(['入科后','ICU 停留','患者'], [1,24,48,72].map(h=>{
        const row=data.coverage.find(r=>r.hour===h);
        return [h+' h',num(row?.n??0),num(row?.patients??0)];
    }));
    const audit=research?.risk_audit;
    return panel('队列纳入与数据关系','使用当前数据模式对应的队列口径',
        `<p class="study-detail">${cohortDetails}</p><div class="entity-map"><span>患者</span><b>1 : N</b><span>住院</span><b>1 : N</b><span>ICU 停留</span></div>`) +
        overview() + panel('预测时间轴与统计分母','各时点从入 ICU 起算 · 按当前筛选汇总',coverage) +
        (audit?panel('风险集定义敏感性','冻结 Development 全队列 · 样本口径比较',
         table(['时点','LOS≥时点','出科边界','精确死亡','仅死亡日','保留'],
            audit.map(r=>[r.hour+' h',num(r.nominal_los_ge_h),num(r.exit_equal_boundary),
            num(r.exact_death_on_or_before),num(r.date_only_death),num(r.saved_risk)]))):'');
}

const featureLabels = {age:'年龄（岁）',pre_icu_los_days:'入 ICU 前住院天数',
    hr_median:'1h 心率中位数（次/分）',sbp_median:'1h 收缩压中位数（mmHg）',
    gcs_median:'1h GCS 中位数',creatinine_median:'1h 肌酐中位数（μmol/L）',
    sex:'记录性别',unit:'首次 ICU 科室'};

function tableOne() {
    const t = research?.table1;
    if (!t) return panel('Table 1','按完整队列的每位患者一个索引 ICU 停留',
        '<div class="empty">本地研究汇总尚未加载。可运行 review-research 后指定 --research-dir。</div>');
    const c = t.continuous.map(row => [esc(featureLabels[row.feature]||row.feature),
        ...row.groups.map(g=>g.n?
            `${dec(g.median,1)} [${dec(g.q1,1)}, ${dec(g.q3,1)}] · 缺失 ${g.missing}`:
            `— · 缺失 ${g.missing}`),dec(row.smd,2)]);
    const k = t.categorical.map(row => [esc(featureLabels[row.feature]+ ' · '+row.level),
        ...row.counts.map((n,i)=>`${num(n)} (${pct(row.proportions[i])})`),dec(row.smd,2)]);
    const model = data.meta.mode==='demo'?'模拟索引停留（最小生成编号）':'首个合格停留（入科时刻、stay_id）';
    return panel('Table 1 · 索引 ICU 停留',model+' · 全队列 · 当前人群筛选不改变该表',
        table(['变量',...['总体','标签 0','标签 1'].map((name,i)=>name+' n='+num(t.counts[i])),'SMD'],[...c,...k]) +
        '<p class="chart-note">连续量为中位数［IQR］，SMD 用均值和两组平均方差计算。分类量逐水平报告。标签 0 指日期规则窗口内无已记录事件。</p>');
}

function studyBaseline() {
    return cohort()+tableOne();
}

function studyStatistics() {
    const rows=research?.table1?.continuous.filter(r=>r.smd!==null)??[];
    const model=research?.association;
    const group=research?.subgroup;
    const lines=model?.terms.map((r,i)=>{
        const sensitivity=research.association_age_lt_90.terms[i];
        const format=x=>`${dec(x.or,2)} [${dec(x.low,2)}, ${dec(x.high,2)}]`;
        return [r.term==='age_per_10_years'?'年龄每 10 岁':'M 相对 F',format(r),format(sensitivity)];
    });
    return panel('按结局分层的组间差异','全队列索引停留 · 方向为标签 1 减标签 0',
        rows.length ? table(['变量','带符号 SMD'],rows.map(r=>[esc(featureLabels[r.feature]||r.feature),dec(r.smd,3)])) :
        '<div class="empty">尚无可展示的分组统计</div>') +
        (model?panel('年龄与记录性别的调整关联',
             `完整病例 n=${num(model.n)} · 年龄 <90 岁敏感性 n=${num(research.association_age_lt_90.n)} · 探索性`,
             table(['变量','调整 OR [95% CI]','敏感性 OR [95% CI]'],lines)):
             panel('调整分析','真实研究汇总支持调整 OR、区间和年龄边界敏感性',
                 '<div class="empty">当前数据模式不提供真实调整回归结果</div>')) +
        (group?panel('按记录性别描述结局','索引停留 · 事件数／组内人数',
            table(['来源性别','分母','事件','率'],group.map(r=>[esc(r.group),num(r.n),num(r.events),pct(r.rate)]))):'') +
        clinical();
}

const modelNames={logistic:'Logistic',lstm:'LSTM',nested_raw:'LSTM 原概率',isotonic:'同网络 Isotonic'};
const experimentTitles = {
    synthetic_simulation: '模拟评分对照',
    v03_baseline: '模型比较 · 逻辑回归与 LSTM',
    v04_nested: '概率校准 · 同一 LSTM 校准前后',
};
const palette=['#1b766b','#b35037'];
function nameFor(row) {
    return data.meta.mode==='demo' ? (row.model==='nested_raw'?'模拟评分 A':'模拟评分 B') :
        modelNames[row.model]||row.model;
}

function xyChart(series, xLabel, yLabel, reference) {
    if (!series.some(s=>s.points.length)) return '<div class="empty">此组无可用曲线</div>';
    const x=v=>56+360*v, y=v=>215-177*v;
    return `<svg class="chart" viewBox="0 0 450 263" role="img" aria-label="${esc(yLabel+' 对 '+xLabel)}">
        ${[0,.25,.5,.75,1].map(p=>`<line class="gridline" x1="56" x2="416" y1="${y(p)}" y2="${y(p)}"/>
        <text x="48" y="${y(p)+4}" text-anchor="end">${p}</text>
        <text x="${x(p)}" y="234" text-anchor="middle">${p}</text>`).join('')}
        <path d="M56 38V215H416" stroke="#91a4ad" fill="none"/>
        ${reference?`<polyline points="${reference.map(p=>x(p[0])+','+y(p[1])).join(' ')}" stroke="#a5afb3" stroke-dasharray="4 4" fill="none"/>`:''}
        ${series.map((s,i)=>`<polyline points="${s.points.map(p=>x(p[0])+','+y(p[1])).join(' ')}" fill="none" stroke="${palette[i]}" stroke-width="2.4"/>`).join('')}
        <text x="236" y="255" text-anchor="middle">${esc(xLabel)}</text><text x="56" y="20">${esc(yLabel)}</text>
        </svg><div class="legend">${series.map((s,i)=>`<span><i style="background:${palette[i]}"></i>${esc(s.name)}</span>`).join('')}</div>`;
}

function modelStudy() {
    const performance=research?.performance??[];
    const experiments=[...new Set(data.metrics.map(r=>r.experiment))];
    if(!experiments.length) return panel('预测评价','按实验及预测时点查看','<div class="empty">当前无评价结果</div>');
    return experiments.map(experiment=>{
        const matching=performance.filter(r=>r.experiment===experiment);
        const current=matching.filter(r=>r.hour===hour);
        const available=current.length?current:data.metrics.filter(r=>r.experiment===experiment);
        const tableRows=available.map(r=>[esc(nameFor(r)),num(r.stays),dec(r.auroc),dec(r.ap),dec(r.brier),dec(r.mcc),
            r.tn==null?'—':[r.tn,r.fp,r.fn,r.tp].map(num).join(' / ')]);
        const charts=current.length?'<div class="grid equal">' +
          panel('ROC','同一实验 · 当前时点',xyChart(current.map(r=>({name:nameFor(r),points:r.roc})),
                '假阳性率','真阳性率',[[0,0],[1,1]])) +
          panel('PR','虚线是当前时点阳性比例',xyChart(current.map(r=>({name:nameFor(r),points:r.pr})),
                '召回率','精确率',[[0,current[0].prevalence],[1,current[0].prevalence]])) + '</div>':'';
        const trend=matching.length?'<div class="grid equal">'+['auroc','brier'].map(key=>{
            const series=current.map((r,i)=>({name:nameFor(r),color:palette[i],
                values:matching.filter(x=>x.model===r.model).sort((a,b)=>a.hour-b.hour).map(x=>x[key])}));
            const max=key==='brier'?Math.max(.05,Math.ceil(20*Math.max(...series.flatMap(x=>x.values)))/20):1;
            return panel('四时点 '+key.toUpperCase(),'每个时点使用相应风险集',
                line(series,['1h','24h','48h','72h'],max,'decimal'));
        }).join('')+'</div>':'';
        const bins=experiment==='v03_baseline'?[]:data.calibration.filter(b=>['nested_raw','isotonic'].includes(b.model));
        const calibrationPlot=bins.length?panel('概率校准','分箱平均预测概率与分箱实际事件率',
            xyChart(['nested_raw','isotonic'].map(model=>({name:nameFor({model}),
                points:bins.filter(r=>r.model===model).map(r=>[r.mean_probability,r.observed_fraction])})),
            '平均预测概率','观察事件率',[[0,0],[1,1]])):'';
        return panel(esc(experimentTitles[experiment] ?? experiment)+' · 入科后 '+hour+' 小时','全队列固定评价 · AP 按阶梯积分 · 分类阈值 0.50',
                table(['模型','停留数','AUROC','AP','Brier','MCC','TN / FP / FN / TP'],tableRows))+
                charts+trend+calibrationPlot;
    }).join('');
}

function studyExplanation() {
    const synthetic=data.meta.mode==='demo';
    return panel(synthetic?'模拟贡献展示（示意）':'13 组历史特征贡献',
        hour+' h · 平均绝对贡献（概率百分点）',
        bars(data.importance.map(r=>({label:r.group_label,n:r.importance_pp})),true)+
        `<p class="chart-note">${synthetic?'示意贡献用于检查看板。':'在折外患者的样本中计算分组历史 Shapley，参照来自相应网络训练患者。贡献大小受参照与变量相关性影响。'}</p>`);
}
