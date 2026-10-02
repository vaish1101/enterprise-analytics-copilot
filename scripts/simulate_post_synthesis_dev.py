"""Offline third-run timing/payload audit; never instantiates an API client."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from openai.lib._parsing._responses import type_to_text_format_param
from scripts.compare_bounded_agents_dev import QUESTIONS
from scripts.evaluate_bounded_agents_dev import synthetic_units
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.runtime import BoundedAgentsGraph
from src.bounded_agents.post_synthesis import CompactSynthesis,ContextStatement,ActionableCritic
from src.retrieval.retrieve import GovernedRetriever
from src.retrieval.embeddings import LocalHashEmbeddingProvider


class Clock:
    def __init__(self):self.value=time.monotonic()
    def __call__(self):return self.value
    def advance(self,s):self.value+=s


class TimedGraph(BoundedAgentsGraph):
    def _verify(self,state):
        result=super()._verify(state);self.clock.advance(.001);return result
    def _revise(self,state):
        result=super()._revise(state);self.clock.advance(.1);return result


class Replay(SpikeFixtureProvider):
    def __init__(self,index,clock,scenario):
        super().__init__();self.index=index;self.clock=clock;self.scenario=scenario;self.spans=[]
        self.cancelled=False
    def cancel_pending(self):self.cancelled=True
    def generate_bounded(self,limits,deadline,**kw):
        role=kw['role'];i=self.index
        duration=(5.916,11.991,11.5,11.5,11.5,4.380)[i] if role=='synthesis' else (6.366 if i!=5 else 2.732) if role=='critic' else {2:2.270,3:3.056,4:5.186}.get(i,0) if role=='analytics.choose' else {2:3.181,3:2.433,4:3.034,5:2.766}.get(i,0)
        if role=='synthesis' and self.scenario=='old_slow_stress' and i in (2,3,4):duration={2:17.717,3:9.733,4:17.028}[i]
        start=self.clock();span={'role':role,'start_s':start-self.workflow.started,'duration_s':duration,
            'protected_headroom_s':deadline-start,'output_cap':limits.max_output_tokens_per_call}
        self.spans.append(span)
        if duration>=deadline-start:
            self.clock.advance(max(0,deadline-start));span['status']='timeout'
            raise TimeoutError('Virtual protected deadline')
        self.clock.advance(duration);span['status']='completed'
        if role=='synthesis' and i in (2,3,4) and self.scenario in ('semantic','surgical'):
            self.fixtures['synthesis']=CompactSynthesis(context=(ContextStatement(kind='interpretation',
                text='This caused the reported outcome.' if self.scenario=='surgical' else 'The source discusses reporting context.',
                evidence_ids=(synthetic_units()[2].evidence_unit_id,)),))
        if role=='critic' and self.scenario=='surgical' and i in (2,3,4):
            self.fixtures['critic']=ActionableCritic(decision='revise',issues=('causal_overclaim',),
                claim_ids=('claim_009',),evidence_sufficient=True,
                corrections=({'claim_id':'claim_009','issue':'causal_overclaim','operation':'drop_claim','evidence_id':None},))
        return super().generate_structured(**kw)


def simulate(scenario='canonical', *, bridge_probe=False):
    rows=[]
    for i,q in enumerate(QUESTIONS):
        if bridge_probe and i == 2:
            q = 'Inspect the reported Mercedes-Benz Cars adjusted EBIT bridge for Q2 2026.'
        clock=Clock();p=Replay(i,clock,scenario)
        g=TimedGraph(ROOT,provider=p,retriever=GovernedRetriever(synthetic_units(),root=ROOT,embedding_provider=LocalHashEmbeddingProvider()))
        g.clock=clock;p.workflow=g
        b=g.run(q,question_id=f'post_synthesis_sim_{i}')
        s=next((s for s in p.spans if s['role']=='synthesis'),None)
        rows.append({'case':i,'status':b.status.value,'verdict':b.verification.verdict.value if b.verification else None,
            'pre_synthesis_s':s['start_s'] if s else next((e.elapsed_ms/1000 for e in g.agent_trace if e.role=='synthesis' and e.status.value=='Skipped'),None),
            'synthesis_provider_invoked':s is not None,'total_s':clock()-g.started,
            'remaining_s':30-(clock()-g.started),'calls':g.budget.calls,'release_mode':g.release_mode,
            'provider_spans':p.spans,'surgical_revision':any(e.role=='surgical_revision' for e in g.agent_trace)})
    return {'scenario':scenario,'paid_calls':0,'rows':rows,
        'assumption':'Rank-selection routes skip synthesis; measured third-run investigation timings are replayed. Supplemental full-bridge compact synthesis at 11.5 s is conditional, not observed performance. No linear token-to-latency claim.'}


def payloads():
    rows=[]
    class Capture(SpikeFixtureProvider):
        def generate_structured(self,**kw):
            if kw['role']=='synthesis':
                raw=kw['payload']
                encode=lambda v:json.dumps(v,default=lambda x:x.model_dump(mode='json'),sort_keys=True)
                self.audit={'payload':json.loads(encode(raw)),'component_bytes':{k:len(encode(v).encode()) for k,v in raw.items()},
                    'prompt_bytes':len(kw['prompt'].encode()),'schema_bytes':len(encode(type_to_text_format_param(kw['output_model'])).encode()),
                    'payload_bytes':len(encode(raw).encode())}
            out=super().generate_structured(**kw)
            if kw['role']=='synthesis':self.audit['visible_output_bytes']=len(out.value.model_dump_json().encode())
            return out
    for q in QUESTIONS:
        p=Capture();g=BoundedAgentsGraph(ROOT,provider=p,retriever=GovernedRetriever(synthetic_units(),root=ROOT,embedding_provider=LocalHashEmbeddingProvider()))
        g.run(q);rows.append(p.audit if hasattr(p,'audit') else {'provider_skipped':True,'reason':'deterministic_numeric_selection'})
    return rows


def reconstruct(path):
    data=json.loads(Path(path).read_text());rows=[]
    for row in data['rows']:
        if row['mode']!='bounded_agents_v2':continue
        stages=[]
        for c in row['observed_calls']:
            if c['role'] not in ('synthesis','critic'):continue
            record=next(r for r in row['provider_records'] if r['role']==c['role'])
            stages.append({'role':c['role'],'start_ms':c['start_ms'],'end_ms':c['end_ms'],
                'input_tokens':record['input_tokens_counted'],'output_tokens':record.get('output_tokens'),
                'visible_output_bytes':len(json.dumps(c['result']).encode()) if c.get('result') else None,
                'status':record['status'],'error':c.get('error_type'),'result':c.get('result')})
        rows.append({'case':row['case'],'latency_ms':row['latency_ms'],'stages':stages,
            'verification':row['verification_observations'],'release_status':row['brief']['status'],
            'release_reason':row['brief']['refusal_reason']})
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--third-run');parser.add_argument('--output');args=parser.parse_args()
    out={'simulations':[simulate(x) for x in ('canonical','semantic','surgical','old_slow_stress')],
        'full_bridge_probes':[simulate(x,bridge_probe=True)['rows'][2] for x in ('canonical','semantic','surgical','old_slow_stress')],
        'payload_audit':payloads(),'tokens_note':'Component bytes/4 are approximations, not additive billed token counts.'}
    if args.third_run:out['third_run_timeline']=reconstruct(args.third_run)
    encoded=json.dumps(out,indent=2)
    if args.output:
        dest=Path(args.output)
        if dest.exists():raise SystemExit('Refusing to overwrite audit evidence')
        dest.write_text(encoded)
        print('Saved offline audit; no API requests')
    else:print(encoded)
