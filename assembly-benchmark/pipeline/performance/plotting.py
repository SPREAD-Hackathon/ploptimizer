"""Compact scientific broad-benchmark plots from frozen scalar records only."""
import csv
import hashlib
import math
import os
from pathlib import Path
from ..common import ROOT, digest, save
from .assessment import ELAPSED_SCOPE, MEMORY_SCOPE

LABELS = {'flye':'Flye', 'raven':'Raven', 'plassembler':'Plassembler',
          'miniasm-plus':'Miniasm + Minipolish'}
COLORS = ['#0072B2','#D55E00','#009E73','#CC79A7']
OUTCOMES = [('fully_complete','All replicons complete','#0072B2'),
    ('chromosome_complete','Chromosome complete only','#56B4E9'),
    ('incomplete','Incomplete','#D55E00'),('empty','Empty output','#E69F00'),
    ('did_not_complete','Did not complete','#666666'),('execution_error','Execution error','#999999')]


def _table(output, name, rows, columns):
    with (output/name).open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=columns,delimiter='\t',extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    return {'title':name.removesuffix('.tsv').replace('-',' ').title(),
            'file':name,'path':name,'sha256':digest(output/name),'rows':len(rows)}


def write_performance_plots(snapshot, output):
    """Return a plot index; pending datasets never become invented observations."""
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    tools = [value['id'] if isinstance(value,dict) else value for value in snapshot.get('tools',list(LABELS))]
    datasets = snapshot.get('datasets',[])
    if isinstance(datasets,dict): datasets=list(datasets.values())
    by_id = {value['id']:value for value in datasets}
    # Describe historical worker timing consistently without changing measurements.
    results = [dict(record, elapsed_scope=ELAPSED_SCOPE +
        (' Sum of raw assembly and polishing worker times.' if record.get('tool')=='miniasm-plus' else ''),
        memory_scope=MEMORY_SCOPE +
        (' Larger peak from the two sequential phases.' if record.get('tool')=='miniasm-plus' else ''))
        for record in snapshot.get('results',[])]
    completed = [r for r in results if r.get('status')=='complete' and r.get('genome_outcome')]
    replicons = [dict(m,dataset_id=r['dataset_id'],tool=r['tool'])
                 for r in completed for m in r.get('replicons',[])]
    summary=[]
    for tool in tools:
        rows=[r for r in completed if r['tool']==tool]
        summary.append({'tool':tool,'assessed':len(rows),
            **{key:sum(r['genome_outcome']==key for r in rows) for key,_,_ in OUTCOMES},
            'assessment_errors':sum(r.get('status')=='error' for r in results if r.get('tool')==tool)})
    tables=[_table(output,'outcomes.tsv',summary,
        ['tool','assessed']+[row[0] for row in OUTCOMES]+['assessment_errors']),
        _table(output,'replicon-metrics.tsv',replicons,
        ['dataset_id','tool','accession','molecule_type','length_bp','contiguity','complete',
         'identity','identity_measured','max_indel_bp','published_achieved_depth']),
        _table(output,'execution-metrics.tsv',results,
        ['dataset_id','tool','status','genome_outcome','elapsed_seconds','elapsed_scope','peak_memory_kb','memory_scope'])]
    index={'schema_version':1,'track':'broad-performance','figures':[], 'tables':tables,
           'tool_summary':summary,'dataset_count':len(datasets),
           'assessed_executions':len(completed),
           'method':'Wick longest-alignment contiguity; 99% completion threshold.'}
    if not completed:
        index['state']='awaiting_results'; save(output/'index.json',index); return index
    _draw(snapshot,output,tools,completed,replicons,by_id,index)
    save(output/'index.json',index)
    return index


def _draw(snapshot,output,tools,results,replicons,datasets,index):
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    from matplotlib import rc_context
    from matplotlib.figure import Figure
    from matplotlib.ticker import MaxNLocator
    labels=[LABELS.get(tool,tool) for tool in tools]

    def canvas(title,rows=1,columns=1,height=5):
        fig=Figure(figsize=(11,height),facecolor='white')
        axes=fig.subplots(rows,columns,squeeze=False)
        fig.subplots_adjust(left=.09,right=.98,bottom=.18,top=.81,hspace=.54,wspace=.35)
        fig.suptitle(title,x=.035,y=.97,ha='left',fontsize=15,weight='bold')
        return fig,axes

    def style(axis):
        axis.spines[['top','right']].set_visible(False)
        axis.grid(axis='y',alpha=.16);axis.set_axisbelow(True)

    def emit(fig,kind,title,caption,count):
        fig.text(.035,.035,caption,fontsize=7,wrap=True)
        stem='broad-'+kind
        for extension in ('svg','png'):
            fig.savefig(output/(stem+'.'+extension),format=extension,dpi=115,
                metadata={'Date':None,'Creator':'Ploptimizer broad performance'} if extension=='svg'
                else {'Software':'Ploptimizer broad performance'})
        index['figures'].append({'kind':kind,'title':title,'caption':caption,
            'svg':stem+'.svg','png':stem+'.png','svg_sha256':digest(output/(stem+'.svg')),
            'png_sha256':digest(output/(stem+'.png')),'measured_observations':count})

    def strip(axis,rows,key,scale=1):
        measured=0
        for i,tool in enumerate(tools):
            selected=[r for r in rows if r['tool']==tool and isinstance(r.get(key),(int,float))
                      and not isinstance(r[key],bool) and math.isfinite(r[key])]
            for row in selected:
                token=f"{row['dataset_id']}:{tool}:{row.get('accession','')}"
                jitter=(int(hashlib.sha256(token.encode()).hexdigest()[:8],16)/0xffffffff-.5)*.35
                axis.scatter(i+jitter,row[key]*scale,s=15,alpha=.65,color=COLORS[i%len(COLORS)],linewidths=0)
            measured+=len(selected)
        axis.set_xticks(range(len(tools)),labels,rotation=16,ha='right',fontsize=7)
        style(axis)
        if not measured:axis.text(.5,.5,'Not measured',transform=axis.transAxes,ha='center')
        return measured

    with rc_context({'svg.hashsalt':'ploptimizer-broad-v1','svg.fonttype':'none',
                     'font.family':['DejaVu Sans','sans-serif'],'font.size':9}):
        fig,axes=canvas('Broad benchmark: assembly completion',height=4.8)
        fig.subplots_adjust(left=.23)
        axis=axes[0,0];left=[0]*len(tools)
        for outcome,label,color in OUTCOMES:
            values=[sum(r['tool']==tool and r['genome_outcome']==outcome for r in results) for tool in tools]
            axis.barh(labels,values,left=left,label=label,color=color)
            for i,value in enumerate(values):
                if value:axis.text(left[i]+value/2,i,str(value),ha='center',va='center',fontsize=8)
            left=[a+b for a,b in zip(left,values)]
        axis.set_xlabel('Assessed executions');axis.xaxis.set_major_locator(MaxNLocator(integer=True));style(axis)
        axis.legend(loc='lower left',bbox_to_anchor=(0,1.01),ncol=3,frameon=False,fontsize=7)
        emit(fig,'outcomes','Assembly completion',
            'Longest single reference alignment ≥99% defines completion. Pending results are excluded; execution failures remain separate.',len(results))

        fig,axes=canvas('Broad benchmark: contiguity and sequence accuracy',2,3,7)
        for row,molecule_type in enumerate(('chromosome','plasmid')):
            selected=[r for r in replicons if r['molecule_type']==molecule_type]
            for column,(key,label,scale) in enumerate([
                ('contiguity','Longest alignment / reference length',1),
                ('identity','Longest-alignment identity (%)',100),
                ('max_indel_bp','Maximum indel (bp)',1)]):
                axis=axes[row,column];count=strip(axis,selected,key,scale)
                axis.set_title(f'{molecule_type.title()} · n={count}',fontsize=9);axis.set_ylabel(label,fontsize=8)
                if key=='contiguity':axis.axhline(.99,color='#666666',ls='--',lw=.7)
                if key=='max_indel_bp' and count:
                    axis.set_yscale('symlog',linthresh=1);axis.margins(y=.15)
        emit(fig,'replicons','Contiguity, identity and indels',
            'Contiguity can exceed 1. Identity/indels require span >100 kb or >¼ reference length; unmeasured values are omitted. Indel scale is symmetric-log.',len(replicons))

        fig,axes=canvas('Broad benchmark: computing resources',columns=2,height=4.8)
        for axis,key,label,scale in zip(axes[0],('elapsed_seconds','peak_memory_kb'),
                ('Workflow wall time (minutes)','Assembler peak resident memory (GiB)'),(1/60,1/(1024*1024))):
            count=strip(axis,results,key,scale);axis.set_ylabel(label)
            if count:axis.set_yscale('symlog',linthresh=1)
        emit(fig,'resources','Runtime and RAM',
            'Workflow wall time includes verification and exact assessment; excludes downloads/queueing. Miniasm + Minipolish sums both workers; RAM is the larger GNU process-tree peak.',len(results))
        _draw_inputs_and_associations(output,tools,results,replicons,datasets,index,canvas,style,emit)


def _draw_inputs_and_associations(output,tools,results,replicons,datasets,index,canvas,style,emit):
    fig,axes=canvas('Broad benchmark: plasmid size and input depth',columns=len(tools),height=4.8)
    plasmids=[r for r in replicons if r['molecule_type']=='plasmid']
    for axis,tool in zip(axes[0],tools):
        selected=[r for r in plasmids if r['tool']==tool and r.get('length_bp',0)>0
                  and isinstance(r.get('published_achieved_depth'),(int,float))
                  and r['published_achieved_depth']>0]
        for complete,color,fill in [(True,'#0072B2','#0072B2'),(False,'#D55E00','none')]:
            points=[r for r in selected if r['complete'] is complete]
            axis.scatter([r['length_bp']/1000 for r in points],
                [r['published_achieved_depth'] for r in points],s=22,edgecolors=color,facecolors=fill,alpha=.7)
        if selected:axis.set_xscale('log');axis.set_yscale('log')
        else:axis.text(.5,.5,'Not measured',transform=axis.transAxes,ha='center',fontsize=8)
        axis.set_title(f'{LABELS.get(tool,tool)}\nn={len(selected)}',fontsize=8)
        axis.set_xlabel('Plasmid length (kb)',fontsize=8);style(axis)
    axes[0,0].set_ylabel('Published achieved depth (×)',fontsize=8)
    emit(fig,'plasmid-size-depth','Plasmid size × depth',
        'Filled blue: ≥99% contiguity; open orange: incomplete. Depth is the original study’s achieved per-replicon depth.',len(plasmids))
    _draw_associations(tools,replicons,datasets,canvas,style,emit)
    _draw_distributions(output,datasets,index,canvas,style,emit)


def _draw_associations(tools,replicons,datasets,canvas,style,emit):
    fig,axes=canvas('Broad benchmark: contiguity against input properties',2,3,7)
    properties=[('read_n50_bp','Published read N50 (kb)',1000),
                ('identity_mean','Target read identity (%)',1),('depth','Target read depth (×)',1)]
    for row,molecule_type in enumerate(('chromosome','plasmid')):
        for column,(key,label,divisor) in enumerate(properties):
            axis=axes[row,column]
            measured=0
            for i,tool in enumerate(tools):
                points=[]
                for molecule in replicons:
                    if molecule['tool']!=tool or molecule['molecule_type']!=molecule_type:continue
                    dataset=datasets.get(molecule['dataset_id'],{})
                    source=dataset.get('published_read_statistics',{}) if key=='read_n50_bp' else dataset.get('badread_parameters',{})
                    value=source.get(key)
                    if isinstance(value,(int,float)) and value>0:
                        points.append((value/divisor,molecule['contiguity']))
                axis.scatter([p[0] for p in points],[p[1] for p in points],s=13,alpha=.5,
                             color=COLORS[i%len(COLORS)],label=LABELS.get(tool,tool),linewidths=0)
                measured+=len(points)
            if measured:axis.axhline(.99,color='#666666',ls='--',lw=.7)
            else:
                axis.text(.5,.5,'Not measured',transform=axis.transAxes,ha='center')
                axis.set_xticks([]);axis.set_yticks([])
            axis.set_xlabel(label,fontsize=8);axis.set_ylabel(f'{molecule_type.title()} contiguity',fontsize=8)
            style(axis)
    axes[0,0].legend(loc='lower left',bbox_to_anchor=(0,1.02),ncol=2,fontsize=7,frameon=False)
    emit(fig,'input-associations','Contiguity × input properties',
        'Target identity/depth are frozen simulation settings; read N50 is the published achieved statistic.',len(replicons))


def _draw_distributions(output,datasets,index,canvas,style,emit):
    inputs=[]
    for dataset in datasets.values():
        stats,parameters=dataset.get('published_read_statistics',{}),dataset.get('badread_parameters',{})
        inputs.append({'dataset_id':dataset['id'],'plasmid_count':dataset.get('plasmid_count'),
            'read_n50_bp':stats.get('read_n50_bp'),'total_read_bases':stats.get('total_read_bases'),
            'read_count':stats.get('read_count'),'target_depth':parameters.get('depth'),
            'target_identity':parameters.get('identity_mean'),'junk_percent':parameters.get('junk_percent'),
            'chimera_percent':parameters.get('chimera_percent')})
    index['tables'].append(_table(output,'input-properties.tsv',inputs,
        ['dataset_id','plasmid_count','read_n50_bp','total_read_bases','read_count','target_depth',
         'target_identity','junk_percent','chimera_percent']))
    fig,axes=canvas('Broad benchmark: frozen input distributions',2,3,6.8)
    specifications=[('read_n50_bp','Published read N50 (kb)',1000),
        ('target_depth','Target depth (×)',1),('target_identity','Target identity (%)',1),
        ('plasmid_count','Plasmids per genome',1),('junk_percent','Target junk reads (%)',1),
        ('chimera_percent','Target chimeric reads (%)',1)]
    for axis,(key,label,divisor) in zip(axes.flat,specifications):
        values=[r[key]/divisor for r in inputs if isinstance(r.get(key),(int,float))]
        if values:axis.hist(values,bins=min(12,max(1,len(set(values)))),color='#0072B2',alpha=.8)
        axis.set_xlabel(label,fontsize=8);axis.set_ylabel('Datasets');axis.set_title(f'n={len(values)}',fontsize=9)
        style(axis)
    emit(fig,'inputs','Input distributions',
        'Each frozen dataset appears once. Values are from the original published workbook; outcomes do not determine selection.',len(inputs))
