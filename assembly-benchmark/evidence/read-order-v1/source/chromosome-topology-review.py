import sys,shutil,json,datetime
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pipeline.common import ROOT,load,save,digest
from pipeline.read_order import output_signature,summarise
from pipeline.read_order_report import render
batch=ROOT/'runs/20261106T134415'
updates=[]
for task in load(batch/'tasks.json')['assemble']:
 if task['tool']!='plassembler':continue
 directory=batch/'results'/task['scenario']/task['tool']
 execution=directory/'execution.json';record=load(execution)
 old=load(directory/'read_order_signature.json');assert old['status']=='complete' and old['execution_sha256']==digest(execution)
 updated=output_signature(directory,record)
 assert updated['end_sensitive_sha256']==old['signature']['end_sensitive_sha256']
 assert updated['contig_count']==old['signature']['contig_count'] and updated['total_length_bp']==old['signature']['total_length_bp']
 assert updated['circular_representation_sha256'] and updated['circularity_source_evidence']
 updates.append((directory,old,updated))
for directory,old,updated in updates:
 p=directory/'read_order_signature.json';backup=directory/'read_order_signature.before-chromosome-topology.json'
 assert not backup.exists();shutil.copy2(p,backup)
 old['signature']=updated
 old['topology_review']={'original_signature_sha256':digest(backup),'producer_sha256':digest(ROOT/'pipeline/read_order.py'),'review_script_sha256':digest(Path(__file__)),'reason':'Associate retained chromosome with its saved initial Flye topology by exact whole-sequence identity, independent of reference.'}
 save(p,old)
result=summarise(batch);assert result['complete'];save(batch/'summary.json',result);render(result,batch/'report')
print(json.dumps({'complete':result['complete'],'tools':[{k:t[k] for k in ['tool','end_sensitive','circular_representation']} for t in result['tools']]}))
