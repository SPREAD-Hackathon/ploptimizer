"""Standard plotting of saved coordinates; no new alignment or sequence work."""
import io
import os
from .common import ROOT


def alignment_svg(plot):
    if plot.get('source_kind') in ('recorded_paf','recorded_show_coords'):
        return coordinate_panel_svg(plot)
    if plot.get('status') != 'available':
        raise ValueError('A plot requires saved coordinates')
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    try:
        from matplotlib import rc_context
        from matplotlib.figure import Figure
        from matplotlib.ticker import FuncFormatter, MaxNLocator
    except ImportError as error:
        raise ValueError('Saved-coordinate plots require requirements-reporting.txt') from error

    with rc_context({'svg.hashsalt':'ploptimizer-saved-coordinates-v1','svg.fonttype':'none',
                     'font.family':['DejaVu Sans','sans-serif'],'font.size':10,'axes.titlesize':11}):
        figure=Figure(figsize=(11,9),facecolor='white')
        grid=figure.add_gridspec(2,2,height_ratios=[1.15,1],hspace=.55,wspace=.48)
        figure.subplots_adjust(top=.85,bottom=.16,left=.12,right=.97)
        figure.suptitle('Saved alignment dot plot',fontsize=19,y=.98,x=.12,ha='left')
        figure.text(.12,.925,'Reviewed coordinates · not a NUCmer run · 0-based interval boundaries',fontsize=11)

        def panel(axis, title, reference_window, query_window, terminal=None):
            axis.set_title(title,loc='left',pad=12)
            axis.set_facecolor('#f8fafc')
            axis.grid(color='#e0e5ec',linewidth=.8)
            axis.set_axisbelow(True)
            if terminal is not None:
                reference=plot['detail']['reference_interval_0based_half_open']
                axis.axvspan(*reference,color='#d8974e',alpha=.25)
                axis.axhspan(*terminal,color='#d8974e',alpha=.25)
            for row in plot['alignments']:
                query=row['query_interval']
                if row['strand']=='-':query=list(reversed(query))
                axis.plot(row['reference_interval'],query,color='#326eae',linewidth=1.8)
            axis.set_xlim(*reference_window);axis.set_ylim(*query_window)
            axis.set_xlabel('Reference boundary (bp)',labelpad=8)
            axis.set_ylabel('Output boundary (bp)',labelpad=8)
            for coordinate in (axis.xaxis,axis.yaxis):
                coordinate.set_major_locator(MaxNLocator(4,integer=True))
                coordinate.set_major_formatter(FuncFormatter(lambda value,_:f'{value:,.0f}'))
            axis.tick_params(labelsize=8)
            for spine in axis.spines.values():spine.set_edgecolor('#8a94a3')

        panel(figure.add_subplot(grid[0,:]),'Whole recorded reference and output',
              (0,plot['reference_length']),(0,plot['query_length']))
        detail=plot.get('detail',{});reference=detail.get('reference_interval_0based_half_open')
        intervals=detail.get('query_intervals_0based_half_open',[])
        if reference and len(intervals)==2:
            xr=(max(0,reference[0]-50),min(plot['reference_length'],reference[1]+50))
            for index,query in enumerate(intervals):
                yr=(max(0,query[0]-50),min(plot['query_length'],query[1]+50))
                panel(figure.add_subplot(grid[1,index]),'Saved terminal interval · '+('output start' if index==0 else 'output end'),xr,yr,terminal=query)
            figure.text(.12,.075,'Orange bands: terminal intervals already identified in the saved review; windows add 50 bp of context.',fontsize=9)
        figure.text(.12,.035,'Lines show recorded spans, not individual changed bases. The software-internal cause remains unresolved.',fontsize=9)
        buffer=io.StringIO()
        figure.savefig(buffer,format='svg',metadata={'Date':None,'Creator':'Ploptimizer saved-coordinate renderer',
            'Title':'Saved reviewed alignment coordinates','Description':'Recorded reference/output alignment intervals with separate terminal windows; no new alignment performed.'})
        return buffer.getvalue()


def coordinate_panel_svg(plot):
    """Draw existing coordinate spans, separating references so small ones stay visible."""
    if plot.get('status')!='available':
        raise ValueError('A coordinate panel needs verified saved records')
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    try:
        from matplotlib import rc_context
        from matplotlib.figure import Figure
        from matplotlib.ticker import FuncFormatter, MaxNLocator
    except ImportError as error:
        raise ValueError('Saved-coordinate plots require requirements-reporting.txt') from error
    references=plot['references']
    source_name='PAF' if plot.get('source_kind')=='recorded_paf' else 'show-coords table'
    columns=min(2,max(1,len(references)));rows=max(1,(len(references)+columns-1)//columns)
    height=rows*3.1+1.9
    with rc_context({'svg.hashsalt':'ploptimizer-recorded-spans-v1','svg.fonttype':'none',
                     'font.family':['DejaVu Sans','sans-serif'],'font.size':9}):
        figure=Figure(figsize=(12,height),facecolor='white')
        grid=figure.add_gridspec(rows,columns,hspace=.65,wspace=.36)
        figure.subplots_adjust(top=1-1.2/height,bottom=1.2/height,left=.10,right=.97)
        figure.suptitle('Recorded alignment spans',fontsize=18,y=1-.18/height,x=.10,ha='left')
        figure.text(.10,1-.52/height,plot['method'],fontsize=9)
        figure.text(.10,1-.80/height,f'0-based interval boundaries · all saved {source_name} rows · exact checks and filtered measurements remain separate',fontsize=9)
        for index,reference in enumerate(references):
            axis=figure.add_subplot(grid[index//columns,index%columns])
            alignments=[r for r in plot['alignments'] if r['reference_id']==reference['id']]
            query_ids=list(dict.fromkeys(r['query_id'] for r in alignments))
            lengths={q['id']:q['length_bp'] for q in plot['queries']}
            offsets={};total=0
            for query in query_ids:offsets[query]=total;total+=lengths[query]
            axis.set_facecolor('#f8fafc');axis.grid(color='#e0e5ec',linewidth=.7);axis.set_axisbelow(True)
            for row in alignments:
                query=row['query_interval']
                if row['strand']=='-':query=list(reversed(query))
                axis.plot(row['reference_interval'],[value+offsets[row['query_id']] for value in query],
                          color='#326eae' if row['strand']=='+' else '#b97121',linewidth=1.1)
            for query in query_ids[1:]:axis.axhline(offsets[query],color='#8a94a3',linewidth=.6)
            axis.set_xlim(0,reference['length_bp']);axis.set_ylim(0,total or 1)
            axis.set_title(reference['name']+' · '+reference['id'],loc='left',fontsize=10,pad=10)
            axis.set_xlabel('Reference boundary (bp)',labelpad=7)
            axis.set_ylabel('Query boundary (cumulative bp)',labelpad=7)
            for coordinate in (axis.xaxis,axis.yaxis):
                coordinate.set_major_locator(MaxNLocator(4,integer=True))
                coordinate.set_major_formatter(FuncFormatter(lambda value,_:f'{value:,.0f}'))
            axis.tick_params(labelsize=7)
            if not alignments:
                axis.set_yticks([])
                axis.set_ylabel('No query coordinates recorded',labelpad=7)
                axis.text(.5,.5,f'No rows for this reference in the saved {source_name}\nThis does not establish sequence absence.',
                          transform=axis.transAxes,ha='center',va='center',fontsize=9)
            elif len(query_ids)<=4:
                axis.text(.01,.99,'Queries: '+', '.join(query_ids),transform=axis.transAxes,va='top',fontsize=7,
                          bbox={'facecolor':'white','edgecolor':'none','alpha':.8})
            for spine in axis.spines.values():spine.set_edgecolor('#8a94a3')
        if not references:
            axis=figure.add_subplot(grid[0,0]);axis.set_axis_off()
            axis.text(.5,.5,'No expected reference inventory was recorded.',ha='center',va='center')
        figure.text(.10,.42/height,'Blue: + strand · orange: − strand. Query axes include only identifiers present in the saved coordinate rows.',fontsize=9)
        figure.text(.10,.15/height,'Plots do not identify individual changed bases or establish an assembly-internal cause.',fontsize=9)
        buffer=io.StringIO()
        figure.savefig(buffer,format='svg',metadata={'Date':None,'Creator':'Ploptimizer recorded-coordinate renderer',
            'Title':'Recorded alignment spans','Description':'Existing source-bound alignment coordinate columns, separated by expected reference; no new alignment or sequence analysis.'})
        return buffer.getvalue()
