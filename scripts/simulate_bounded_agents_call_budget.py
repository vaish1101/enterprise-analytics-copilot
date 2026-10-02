"""Credential-free six-case virtual-clock forecast, not a live evaluation.

Measured role durations include remote count + generation. Driver synthesis
duration is censored: a floor scenario is not evidence of completed generation.
No API client, SDK request, held corpus or frozen evaluator is instantiated.
"""
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from scripts.compare_bounded_agents_dev import QUESTIONS
from scripts.evaluate_bounded_agents_dev import synthetic_units
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.models import AnalyticsInvestigationRequest, CriticFeedback
from src.bounded_agents.runtime import BoundedAgentsGraph, ROLE_PROMPT, ROLE_PROMPTS
from src.orchestration.models import SynthesisDraft
from src.retrieval.retrieve import GovernedRetriever
from src.retrieval.embeddings import LocalHashEmbeddingProvider


# Rounded measured completed durations; censored waits explicitly labelled below.
SAMPLES = (
    {"synthesis":4.792631, "critic":3.584688},
    {"synthesis":13.607909, "critic":4.209346},
    {"analytics.choose":2.023795, "evidence.choose":2.349583, "synthesis":16.457},
    {"analytics.choose":2.071976, "evidence.choose":1.750995, "synthesis":16.454},
    {"analytics.choose":5.077452, "evidence.choose":1.634966, "synthesis":13.658},
    {"evidence.choose":2.993197, "synthesis":4.307011, "critic":2.664288},
)


class VirtualClock:
    def __init__(self): self.value = time.monotonic()
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class SimulationProvider(SpikeFixtureProvider):
    def __init__(self, index, clock, *, stress=False):
        fixtures = {}
        if index in (2,3,4):
            fixtures["analytics.choose"] = AnalyticsInvestigationRequest(
                action={2:"rank_positive",3:"rank_negative",4:"lookup"}[index])
        if index == 5:
            fixtures["critic"] = CriticFeedback(decision="approve",issues=(),
                claim_ids=(),evidence_sufficient=False)
        super().__init__(fixtures)
        self.clock = clock; self.sample = dict(SAMPLES[index]); self.index = index
        self.stress = stress; self.attempts = []; self.cancelled = False
    def cancel_pending(self): self.cancelled = True
    def generate_bounded(self, *, limits, deadline, **kwargs):
        role = kwargs["role"]; started = self.clock()
        duration = self.sample.get(role,4.5)
        if role == "synthesis" and self.index in (2,3,4):
            # Optimistic censored-floor scenario: NOT observed completion time.
            duration = max(17.0,duration+.25)
        if role == "synthesis" and self.stress: duration += 8
        def encode(x):
            if hasattr(x,'model_dump'): return x.model_dump(mode='json')
            raise TypeError("Unsupported fixture value")
        payload = kwargs['payload']
        input_bytes = len((kwargs['prompt']+json.dumps(payload,default=encode,sort_keys=True)).encode())
        before = input_bytes
        if role != "synthesis":
            before += len(ROLE_PROMPT.encode())-len(ROLE_PROMPTS[role.split('.')[0]].encode())
        else:
            before_payload = {**payload,"investigation_observations":tuple(self.workflow.observations)}
            before = len((kwargs['prompt']+json.dumps(before_payload,default=encode,sort_keys=True)).encode())
        span = {"role":role,"start_s":started-self.workflow.started,
            "requested_duration_s":duration,"headroom_s":deadline-started,
            "input_bytes":input_bytes,"same_data_prior_layout_bytes":before,
            "approx_input_tokens_excluding_schema":input_bytes//4,
            "token_measurement":"byte/4 heuristic only, not SDK preflight/billing"}
        self.attempts.append(span)
        if self.cancelled or duration >= deadline-started:
            self.clock.advance(max(0,deadline-started))
            span.update(status="TIMEOUT",elapsed_s=self.clock()-started)
            raise TimeoutError("Simulated protected provider deadline")
        self.clock.advance(duration)
        result = super().generate_structured(**kwargs)
        span.update(status="COMPLETED",elapsed_s=duration)
        return result


def simulate(stress=False):
    rows=[]
    for index,question in enumerate(QUESTIONS):
        clock=VirtualClock(); provider=SimulationProvider(index,clock,stress=stress)
        retriever=GovernedRetriever(synthetic_units(),root=ROOT,embedding_provider=LocalHashEmbeddingProvider())
        workflow=BoundedAgentsGraph(ROOT,provider=provider,retriever=retriever)
        workflow.clock=clock; provider.workflow=workflow
        result=workflow.run(question,question_id=f"call_budget_sim_{index}")
        synthesis=next((x for x in provider.attempts if x['role']=='synthesis'),None)
        rows.append({"case":index,"question":question,"route":result.route.value,
            "status":result.status.value,"verification":result.verification.verdict.value if result.verification else None,
            "call_count":workflow.budget.calls,"route_ceiling":workflow.activation.max_calls,
            "synthesis_start_s":synthesis['start_s'] if synthesis else None,
            "synthesis_request_headroom_s":30-synthesis['start_s'] if synthesis else None,
            "elapsed_s":clock()-workflow.started,"attempts":provider.attempts,
            "skip_reasons":[{"role":x.role,"reason":x.action} for x in workflow.agent_trace if x.status.value=='Skipped'],
            "fallback":False})
    return {"provider":"virtual_clock_fixture","paid_calls":0,"deadline_s":30,
        "scenario":"synthesis_plus_8_seconds" if stress else "completed_role_timings_and_optimistic_driver_censored_floor",
        "warning":"Scripted decisions cannot establish agency quality. Driver synthesis durations are censored lower bounds, not observed completion times. This is not a latency SLA or held evaluation.",
        "rows":rows}


if __name__=='__main__':
    print(json.dumps({"baseline":simulate(),"slow_synthesis_stress":simulate(True)},indent=2))
