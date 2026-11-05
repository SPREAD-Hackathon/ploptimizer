"""Publication-ready aggregate figures from saved scalar measurements only."""
import hashlib
import math
import os
from .common import ROOT, save, digest

COLORS = {'pass': '#0072B2', 'fail': '#D55E00', 'error': '#6B7280', 'unscored': '#C3C8D0'}
TOOL_COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']


def write_aggregate_plots(data, output):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
    from matplotlib import rc_context
    from matplotlib.figure import Figure
    from matplotlib.ticker import LogLocator, FuncFormatter
    output.mkdir(parents=True, exist_ok=True)
    figures = []
    tools = [t['id'] for t in data['tools']]
    labels = [t['label'] for t in data['tools']]

    def canvas(title, columns=1, height=4.7):
        fig = Figure(figsize=(12, height), facecolor='white')
        axes = fig.subplots(1, columns, squeeze=False)[0]
        fig.subplots_adjust(left=.13, right=.97, bottom=.20, top=.78, wspace=.36)
        fig.suptitle(title, x=.05, y=.97, ha='left', fontsize=17, weight='bold')
        return fig, axes

    def style(axis):
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(axis='y', alpha=.16)
        axis.set_axisbelow(True)

    def strip(axis, rows, key, scale=1, logarithmic=False):
        valid = []
        for index, tool in enumerate(tools):
            values = [r for r in rows if r['tool'] == tool and r.get(key) is not None and (r[key] > 0 or not logarithmic)]
            for row in values:
                token = ':'.join(str(row.get(k, '')) for k in ('batch', 'scenario_id', 'tool', 'run_id', 'accession'))
                jitter = (int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) / 0xffffffff - .5) * .38
                axis.scatter(index+jitter, row[key]*scale, s=22, alpha=.65, color=TOOL_COLORS[index], linewidths=0, rasterized=False)
                valid.append(row)
        axis.set_xticks(range(len(tools)), labels, rotation=20, ha='right', fontsize=8)
        if logarithmic and valid:
            axis.set_yscale('log')
            values = [r[key]*scale for r in valid]
            low, high = 10**math.floor(math.log10(min(values))), 10**math.ceil(math.log10(max(values)))
            axis.set_ylim(low/10 if low == high else low, high*10 if low == high else high)
            axis.yaxis.set_major_locator(LogLocator(base=10, subs=(1,2,5), numticks=12))
            axis.yaxis.set_major_formatter(FuncFormatter(lambda value,_: f'{value:g}'))
            axis.yaxis.set_minor_formatter(FuncFormatter(lambda value,_: ''))
        style(axis)
        return len(valid)

    def emit(fig, group, kind, title, caption, available, total):
        stem = group['id'] + '-' + kind
        fig.text(.05, .045, f"{group['family']} · {group['cohort_role']} · {caption}", fontsize=8, wrap=True)
        for extension in ('svg', 'png'):
            fig.savefig(output / (stem + '.' + extension), format=extension, dpi=170,
                        metadata={'Date': None, 'Creator': 'Ploptimizer aggregate reporting'} if extension == 'svg' else {'Software': 'Ploptimizer aggregate reporting'})
        figures.append({'group_id': group['id'], 'kind': kind, 'title': title, 'caption': caption,
                        'svg': stem+'.svg', 'png': stem+'.png', 'svg_sha256': digest(output/(stem+'.svg')), 'png_sha256': digest(output/(stem+'.png')), 'measured_observations': available, 'candidate_observations': total})

    with rc_context({'svg.hashsalt': 'ploptimizer-aggregate-v1', 'svg.fonttype': 'none', 'font.family': ['DejaVu Sans', 'sans-serif'], 'font.size': 10}):
        for group in data['groups']:
            rows = [r for r in data['executions'] if r['group_id'] == group['id']]
            molecules = [r for r in data['molecules'] if r['group_id'] == group['id'] and r['required_by_endpoint']]
            if group['family'] == 'S3':
                groups = [g for g in data['repeatability'] if g['group_id'] == group['id'] and g['comparison'] == 'within_thread']
                fig, (ax,) = canvas('Repeatability of normalised assembly sequences')
                left = [0]*len(tools)
                for key, label in [('identical', 'Identical'), ('different', 'Different'), ('not_assessed', 'Not assessed')]:
                    vals = []
                    for tool in tools:
                        count = 0
                        for g in groups:
                            if g['tool'] != tool: continue
                            assessed = g.get('complete') is True and g.get('inputs_identical') is True and type(g.get('normalised_sequence_identical')) is bool
                            state = ('identical' if g['normalised_sequence_identical'] else 'different') if assessed else 'not_assessed'
                            count += state == key
                        vals.append(count)
                    color = COLORS[{'identical':'pass','different':'fail','not_assessed':'error'}[key]]
                    ax.barh(labels, vals, left=left, label=label, color=color)
                    left = [a+b for a,b in zip(left,vals)]
                ax.set_xlabel('Saved input × mode × thread comparison groups'); ax.legend(loc='upper left', bbox_to_anchor=(0, 1.25), ncol=3, frameon=False); style(ax)
                emit(fig, group, 'repeatability', 'Repeatability', 'Within-setting groups; reference recovery is a separate endpoint.', len(groups), len(groups))
                continue

            fig, (ax,) = canvas('Exact assembly outcomes')
            left = [0]*len(tools)
            for state, label in [('pass','Exact pass'),('fail','Exact fail'),('error','Execution error'),('unscored','Unscored')]:
                vals = [sum((r['execution_status'] if r['execution_status'] in {'pass','fail'} else 'error' if r['execution_status'] in {'error','timeout','invalid_input'} else 'unscored') == state for r in rows if r['tool']==t) for t in tools]
                ax.barh(labels, vals, left=left, color=COLORS[state], label=label)
                for i, v in enumerate(vals):
                    if v: ax.text(left[i]+v/2, i, str(v), va='center', ha='center', color='white' if state not in {'unscored','fail'} else '#111111', fontsize=9)
                left = [a+b for a,b in zip(left, vals)]
            ax.set_xlabel('Executions');ax.legend(loc='upper left', bbox_to_anchor=(0,1.24), ncol=4, frameon=False, fontsize=9);style(ax)
            emit(fig, group, 'outcomes', 'Exact outcomes', 'Saved execution outcomes; no alignment-completion threshold substituted.', len(rows), len(rows))

            plasmids = [r for r in molecules if r['molecule_type']=='plasmid']
            fig, axes = canvas('Plasmid size and achieved input depth', columns=len(tools), height=4.8)
            available = 0
            depths = [r['achieved_depth'] for r in plasmids if r.get('achieved_depth') and r.get('length_bp')]
            bounds = (10**math.floor(math.log10(min(depths))), 10**math.ceil(math.log10(max(depths)))) if depths else (1, 100)
            if bounds[0] == bounds[1]: bounds = (bounds[0]/10, bounds[1]*10)
            for ax, tool, label in zip(axes, tools, labels):
                selected = [r for r in plasmids if r['tool']==tool and r.get('length_bp') and r.get('achieved_depth') and r['exact_status'] in {'pass','fail'}]
                for state in ('pass','fail'):
                    points = [r for r in selected if r['exact_status']==state]
                    ax.scatter([r['length_bp'] for r in points], [r['achieved_depth'] for r in points], s=45, facecolors=COLORS[state] if state=='pass' else 'none', edgecolors=COLORS[state], alpha=.7, linewidths=1.2)
                ax.set_title(f'{label}\n{sum(r["exact_status"]=="pass" for r in selected)}/{len(selected)} exact',fontsize=9)
                if selected:
                    ax.set_xscale('log');ax.set_yscale('log');ax.set_ylim(*bounds)
                    ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1,2,5), numticks=4))
                    ax.xaxis.set_major_formatter(FuncFormatter(lambda value,_: f'{value/1000:g}'))
                    ax.xaxis.set_minor_formatter(FuncFormatter(lambda value,_: ''))
                    ax.yaxis.set_major_formatter(FuncFormatter(lambda value,_: f'{value:g}'))
                    ax.yaxis.set_minor_formatter(FuncFormatter(lambda value,_: ''))
                else:
                    ax.set_xticks([]);ax.set_yticks([])
                ax.set_xlabel('Plasmid length (kb)',fontsize=9);style(ax)
                if tool != tools[0]: ax.tick_params(axis='y',labelleft=False)
                if not selected: ax.text(.5,.5,'No measured plasmids',transform=ax.transAxes,ha='center',fontsize=8)
                available += len(selected)
            axes[0].set_ylabel('Achieved read depth (×)')
            emit(fig, group, 'size-depth', 'Plasmid size × depth', 'Filled blue: exact pass; open orange: exact fail. Coincident observations overlap; TSV retains every row.', available, len(plasmids))

            for kind, key, title, ylabel in [('breadth','aligned_reference_fraction','Mapped reference breadth','Retained reference coverage (%)'),('identity','alignment_identity','Recorded alignment identity','Retained alignment identity (%)')]:
                fig, axes = canvas(title, columns=2)
                available = 0
                for ax, molecule_type in zip(axes, ('chromosome','plasmid')):
                    selected = [r for r in molecules if r['molecule_type']==molecule_type]
                    n = strip(ax,selected,key,scale=100); available += n
                    ax.set_title(f'{molecule_type.title()} · {n}/{len(selected)} measured',fontsize=11);ax.set_ylabel(ylabel)
                    if kind=='breadth': ax.set_ylim(-2,102)
                    else: ax.yaxis.set_major_formatter(FuncFormatter(lambda value,_: f'{value:.5f}'))
                    if not n: ax.text(.5,.5,'No recorded measurements',transform=ax.transAxes,ha='center')
                emit(fig, group, kind, title, 'Endpoint-required molecules only. '+('Union breadth is not Wick contiguity.' if kind=='breadth' else 'Alignment-weighted identity; not Wick longest-alignment identity.'), available, len(molecules))

            fig, axes = canvas('Recorded computing resources',columns=2)
            measured = strip(axes[0],rows,'elapsed_seconds',logarithmic=True)
            strip(axes[1],rows,'peak_memory_kib',scale=1/(1024*1024),logarithmic=True)
            axes[0].set_ylabel('Elapsed wall time (seconds)');axes[1].set_ylabel('Peak resident memory (GiB)')
            for ax,key in zip(axes,('elapsed_seconds','peak_memory_kib')):
                n = sum(r.get(key) is not None and r[key]>0 for r in rows)
                ax.set_title(f'{n}/{len(rows)} recorded',fontsize=11)
            threads = ', '.join(str(v) for v in sorted({r['threads'] for r in rows if r.get('threads') is not None}))
            emit(fig, group, 'resources', 'Runtime and RAM', f'Recorded threads: {threads or "unknown"}. Workflow scopes differ; no speed ranking. Log scales.', measured, len(rows))

            selected = [r for r in data['inputs'] if r['group_id']==group['id']]
            fig, axes = canvas('Saved input distributions',columns=3)
            specs = [('length_bp','Plasmid size (bp)',True),('achieved_depth','Achieved depth (×)',False),('mean_read_length_bp','Mean read length (bp)',False)]
            for ax,(key,label,plasmid_only) in zip(axes,specs):
                values = [r[key] for r in selected if r.get(key) is not None and r[key]>0 and (not plasmid_only or r['molecule_type']=='plasmid')]
                if values:
                    ax.hist([math.log10(v) for v in values],bins=min(12,max(1,len(set(values)))),color=COLORS['pass'],alpha=.85)
                else: ax.text(.5,.5,'No recorded inputs',transform=ax.transAxes,ha='center',fontsize=9)
                ax.set_xlabel('log₁₀ '+label,fontsize=9);ax.set_ylabel('Input/replicon records');ax.set_title(f'n = {len(values)}',fontsize=10);style(ax)
            emit(fig, group, 'inputs', 'Input distributions', 'One row per saved read hash and replicon within this cohort; read length is a mean, not N50.', len(selected), len(selected))
    save(output/'index.json', {'schema_version':1,'figures':figures,'groups':data['groups']})
    return figures
