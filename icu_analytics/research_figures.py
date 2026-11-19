"""Local scientific figures from the same summaries served by the dashboard."""
from itertools import groupby


def draw(result, target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter

    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    palette = ['#a2533c', '#126c65']

    def save(fig, name):
        fig.text(.99,.01,'MIMIC-IV 3.1 · Development · Restricted local research',
                 ha='right',fontsize=8,color='#516575')
        fig.tight_layout(rect=(0,.035,1,1))
        fig.savefig(target/(name+'.png'), dpi=220)
        fig.savefig(target/(name+'.svg'))
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7,4))
    risk = result['risk_audit']
    hours = [row['hour'] for row in risk]
    ax.plot(hours,[row['nominal_los_ge_h'] for row in risk],'o--',label='LOS ≥ landmark')
    ax.plot(hours,[row['saved_risk'] for row in risk],'o-',label='Frozen eligible stays')
    for row in risk:
        ax.annotate(f"−{row['difference']}",(row['hour'],row['saved_risk']),
                    xytext=(3,-12),textcoords='offset points')
    ax.set(xlabel='Hours from ICU admission',ylabel='ICU stays',xticks=hours)
    ax.legend()
    save(fig,'risk_set_sensitivity')

    fig, ax = plt.subplots(figsize=(7,3.6))
    terms = result['association']['terms']
    sensitivity = result['association_age_lt_90']['terms']
    for j, (data, label) in enumerate([(terms,'Complete cases'),(sensitivity,'Age < 90')]):
        for i, row in enumerate(data):
            ax.errorbar(row['or'],i+(j-.5)*.18,
                        xerr=[[row['or']-row['low']],[row['high']-row['or']]],
                        fmt='o',color=palette[j],label=label if i==0 else None)
    ax.axvline(1,linestyle='--',color='#89959a')
    ax.set(xscale='log',xlabel='Adjusted odds ratio (HC1 95% CI)',
           yticks=[0,1],yticklabels=['Age per 10 years','Male versus female'])
    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    ax.xaxis.set_minor_formatter(StrMethodFormatter('{x:g}'))
    ax.legend()
    save(fig,'adjusted_associations')

    fig, axes = plt.subplots(1,2,figsize=(8,3.6))
    rows = result['subgroup']
    axes[0].bar([r['group'] for r in rows],[100*r['rate'] for r in rows],color=palette[1])
    axes[0].set(ylabel='Observed 90-day label (%)',xlabel='Recorded sex · index stays')
    age = result['table1']['continuous'][0]['groups'][1:]
    axes[1].errorbar([0,1],[r['median'] for r in age],
                     yerr=[[r['median']-r['q1'] for r in age],[r['q3']-r['median'] for r in age]],
                     fmt='o',color=palette[0])
    axes[1].set(ylabel='Index ICU age (years) · median and IQR',
                xticks=[0,1],xticklabels=['Label 0','Label 1'])
    save(fig,'descriptive_comparisons')

    fig, axes = plt.subplots(1,3,figsize=(12,4))
    base = result['table1']
    sex = [row for row in base['categorical'] if row['feature']=='sex']
    units = [row for row in base['categorical'] if row['feature']=='unit']
    units.sort(key=lambda row:row['counts'][0])
    axes[0].bar([row['level'] for row in sex],[row['counts'][0] for row in sex],color=palette[1])
    axes[0].set(title='Recorded sex',ylabel='Index patients')
    axes[1].barh(range(len(units)),[row['counts'][0] for row in units],color=palette[1])
    axes[1].set(title='First ICU unit',yticks=range(len(units)),
                yticklabels=[row['level'].split('(')[-1].rstrip(')') for row in units])
    features = sorted([r for r in result['feature_missingness'] if r['hour']==1],
                      key=lambda r:r['missing_fraction'])[-10:]
    axes[2].barh([r['feature'] for r in features],[r['missing_fraction']*100 for r in features],
                 color=palette[0])
    axes[2].set(title='Highest feature missingness at 1 h',xlabel='Missing among eligible stays (%)')
    save(fig,'population_and_missingness')

    fig, axes = plt.subplots(2,2,figsize=(8,7))
    for hour, ax in zip((1,24,48,72),axes.flat):
        ax.plot([0,1],[0,1],'--',color='#89959a')
        for model,color in zip(('nested_raw','isotonic'),palette):
            bins=sorted([row for row in result['calibration'] if row['hour']==hour and row['model']==model],
                        key=lambda row:row['bin'])
            ax.plot([r['mean_probability'] for r in bins],[r['observed_fraction'] for r in bins],
                    'o-',color=color,label=model)
        ax.set(title=f'{hour} h',xlabel='Mean predicted probability',ylabel='Observed fraction')
    axes[0,0].legend()
    fig.suptitle('v04 nested calibration · matching OOF populations')
    save(fig,'v04_calibration')

    perf = sorted(result['performance'],key=lambda r:(r['experiment'],r['model'],r['hour']))
    for experiment, rows in groupby(perf,key=lambda r:r['experiment']):
        experiment_rows = list(rows)
        fig, axes = plt.subplots(2,3,figsize=(12,7))
        primary = 24 if experiment == 'v03_baseline' else 1
        for j,(model, subset) in enumerate(groupby(experiment_rows,key=lambda r:r['model'])):
            values=list(subset)
            row=next(r for r in values if r['hour']==primary)
            for ax,key,xlabel,ylabel in [(axes[0,0],'roc','False positive rate','True positive rate'),
                                         (axes[0,1],'pr','Recall','Precision')]:
                x,y=zip(*row[key]);ax.plot(x,y,color=palette[j],label=model)
                ax.set(xlabel=xlabel,ylabel=ylabel,title=f'{key.upper()} at {primary} h')
            for ax,key in zip(axes.ravel()[2:5],('auroc','brier','mcc')):
                ax.plot([r['hour'] for r in values],[r[key] for r in values],'o-',
                        color=palette[j],label=model)
                ax.set(xlabel='Hours',title=key.upper())
            axes[1,2].axis('off')
            axes[1,2].text(.03,.78-j*.35,
                           f"{model} at {primary} h\nTN {row['tn']:,} / FP {row['fp']:,}\n"
                           f"FN {row['fn']:,} / TP {row['tp']:,}",transform=axes[1,2].transAxes)
        axes[0,0].plot([0,1],[0,1],'--',color='#89959a')
        axes[0,1].axhline(row['prevalence'],linestyle='--',color='#89959a')
        axes[0,0].legend()
        axes[1,2].set_title('Fixed threshold 0.50')
        fig.suptitle(experiment)
        save(fig,experiment+'_performance')
