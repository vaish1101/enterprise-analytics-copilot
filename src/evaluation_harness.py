"""Offline-testable evaluation infrastructure. No agent/provider/retrieval logic."""
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CaseStatus(str, Enum):
    RECORDED = 'RECORDED'
    HARNESS_ERROR = 'HARNESS_EXECUTION_ERROR'
    NOT_STARTED = 'NOT_STARTED'


class ReviewStatus(str, Enum):
    NOT_INVOKED = 'NOT_INVOKED'
    PASSED = 'PASSED'
    REJECTED = 'REJECTED'
    REVISED = 'REVISED'
    TIMED_OUT = 'TIMED_OUT'
    UNKNOWN = 'UNKNOWN'


class FaultStatus(str, Enum):
    NOT_APPLICABLE = 'NOT_APPLICABLE'
    INVALID_SETUP = 'INVALID_SETUP'
    PASSED = 'PASSED'
    FAILED = 'FAILED'
    UNKNOWN = 'UNKNOWN'


class HumanAdjudication(Contract):
    status: Literal['NOT_REVIEWED'] = 'NOT_REVIEWED'
    reviewer: None = None
    verdict: None = None
    notes: None = None


class Decision(Contract):
    role: str
    status: Literal['SUCCESS', 'ERROR']
    result: dict[str, Any] | None
    error_type: str | None
    latency_ms: float = Field(ge=0)

    @model_validator(mode='after')
    def shape(self):
        if self.status == 'SUCCESS' and (self.result is None or self.error_type is not None):
            raise ValueError('Successful decision requires result and no error')
        if self.status == 'ERROR' and (self.error_type is None or self.result is not None):
            raise ValueError('Failed decision requires error and no result')
        return self


def normalize_decision(raw):
    """The Observer union: absence on SUCCESS is valid, not a renamed key."""
    if 'result' in raw and 'error_type' not in raw:
        return Decision(role=raw['role'], status='SUCCESS', result=raw['result'],
                        error_type=None, latency_ms=raw['latency_ms'])
    if 'error_type' in raw and 'result' not in raw:
        return Decision(role=raw['role'], status='ERROR', result=None,
                        error_type=raw['error_type'], latency_ms=raw['latency_ms'])
    raise ValueError('Observer decision must be exactly success or error')


class Usage(Contract):
    accounting_available: bool = False
    known_input_tokens: int = Field(default=0, ge=0)
    known_output_tokens: int = Field(default=0, ge=0)
    known_estimated_cost_usd: str = '0'
    unknown_requests: int = Field(default=0, ge=0)
    unknown_reserved_exposure_usd: str = '0'
    reserved_exposure_usd: str = '0'
    committed_exposure_usd: str | None = None
    peak_reserved_exposure_usd: str | None = None


def usage_snapshot(records, *, committed=None, peak=None):
    from decimal import Decimal
    known_in = known_out = unknown = 0
    cost = unknown_cost = reserved = Decimal(0)
    for record in records:
        reservation = Decimal(record['reserved_usd'])
        reserved += reservation
        if record['status'] == 'completed':
            # Known actual usage is mandatory on a settled response.
            known_in += record['input_tokens']
            known_out += record['output_tokens']
            cost += Decimal(record['actual_usd'])
        elif record['status'] == 'unknown':
            unknown += 1
            unknown_cost += reservation
        else:
            raise ValueError('Unknown usage record status')
    return Usage(accounting_available=True,known_input_tokens=known_in, known_output_tokens=known_out,
        known_estimated_cost_usd=str(cost), unknown_requests=unknown,
        unknown_reserved_exposure_usd=str(unknown_cost), reserved_exposure_usd=str(reserved),
        committed_exposure_usd=None if committed is None else str(committed),
        peak_reserved_exposure_usd=None if peak is None else str(peak))


class CaseResult(Contract):
    schema_version: Literal['evaluation-case-1'] = 'evaluation-case-1'
    case_id: str
    category: Literal['ordinary', 'fault']
    status: CaseStatus
    route: str | None = None
    task_completion: bool | None = None
    safety: dict[str, Any] | None = None
    fault_detection: FaultStatus = FaultStatus.NOT_APPLICABLE
    fault_recovery: FaultStatus = FaultStatus.NOT_APPLICABLE
    system_reliability: dict[str, Any] | None = None
    agent_usage: dict[str, int] = Field(default_factory=dict)
    review_status: ReviewStatus = ReviewStatus.NOT_INVOKED
    verifier_status: str | None = None
    final_outcome: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    provider_calls: int | None = Field(default=None, ge=0)
    usage: Usage = Field(default_factory=Usage)
    retrieval_backend: str | None = None
    human_adjudication: HumanAdjudication = Field(default_factory=HumanAdjudication)
    decisions: tuple[Decision, ...] = ()
    failure_class: Literal['HARNESS_EXECUTION_ERROR'] | None = None
    error_type: str | None = None
    notes: tuple[str, ...] = ()
    systemic_failure: str | None = None
    schema_failure_stage: str | None = None
    release_record: dict[str, Any] | None = None
    hybrid_diagnostics: dict[str, Any] | None = None


def release_stop_reason(record):
    """Only normalized fields; success records never require an error key."""
    if record.safety and record.safety['unsupported_claim_released']:
        return 'UNSUPPORTED_CONTENT_RELEASED'
    if record.safety and not record.safety['released_verified']:
        return 'UNVERIFIED_CONTENT_RELEASED'
    if any(x.status=='ERROR' and x.error_type in {'BadRequestError','ToolAuthorizationError'} for x in record.decisions):
        return 'CONTRACT_OR_AUTHORIZATION_FAILURE'
    return None


class SystemicStopPolicy:
    """Explicit invariant breaches stop immediately; schema recurrence stops at 2.

    One malformed model answer is not evidence of global incompatibility.
    Explicit incompatibility is supplied by the evaluation adapter, not inferred
    from a successful provider decision. State is local to one gate execution.
    """
    def __init__(self):
        self.schema_failures = {}

    def observe(self, record):
        if record.systemic_failure:
            return record.systemic_failure
        if record.safety and record.safety.get('unsupported_claim_released'):
            return 'UNSUPPORTED_CONTENT_RELEASED'
        if record.safety and not record.safety.get('released_verified', True):
            return 'UNVERIFIED_CONTENT_RELEASED'
        if record.schema_failure_stage:
            stage = record.schema_failure_stage
            self.schema_failures[stage] = self.schema_failures.get(stage, 0) + 1
            if self.schema_failures[stage] >= 2:
                return 'SYSTEMIC_SCHEMA_FAILURE'
        return None


def render_report(report):
    """Report from canonical checkpoints only, never raw provider unions."""
    records=[CaseResult.model_validate(x) for x in report['cases']]
    lines=['# Evaluation evidence','',f"Status: {report['status']}",
        f"Failure class: {report['failure_class'] or 'NONE'}",
        f"Recorded cases: {report['completed_case_count']}",f"Unstarted cases: {report['unstarted_case_count']}",
        'Human adjudication: NOT_REVIEWED','', '| Case | Category | Recording status | Outcome | Review | Latency ms |',
        '| --- | --- | --- | --- | --- | --- |']
    for item in records:
        lines.append(f'| {item.case_id} | {item.category} | {item.status.value} | {item.final_outcome or "UNKNOWN"} | {item.review_status.value} | {item.latency_ms if item.latency_ms is not None else "UNKNOWN"} |')
    lines += ['', 'Known usage and conservative exposure (estimates, not invoices):','',
        '```json',json.dumps(report['usage'],indent=2),'```','',
        'Missing accounting case IDs: '+', '.join(report['missing_accounting_case_ids']),
        '', 'Preflight evidence is separate from end-to-end live validation.']
    return '\n'.join(lines)+'\n'


def fault_status(setup, value):
    if setup == 'NOT_APPLIED': return FaultStatus.NOT_APPLICABLE
    if setup == 'INVALID': return FaultStatus.INVALID_SETUP
    if setup != 'VALID': raise ValueError('Invalid fault setup status')
    return FaultStatus.UNKNOWN if value is None else FaultStatus.PASSED if value else FaultStatus.FAILED


def normalize_case(raw, category):
    """Consume the established row contract; output every structural key."""
    machine = raw['score']['machine_result']
    review = raw['review']
    decisions = tuple(normalize_decision(x) for x in raw['decisions'])
    roles = {}
    for decision in decisions: roles[decision.role] = roles.get(decision.role, 0) + 1
    critic = [x for x in decisions if x.role == 'critic' and x.status == 'SUCCESS']
    if review['timed_out']: review_status = ReviewStatus.TIMED_OUT
    elif not review['invoked']: review_status = ReviewStatus.NOT_INVOKED
    elif critic:
        review_status = {'approve': ReviewStatus.PASSED, 'reject': ReviewStatus.REJECTED,
                         'revise': ReviewStatus.REVISED}[critic[-1].result['decision']]
    else: review_status = ReviewStatus.UNKNOWN
    verification = raw['verification']
    return CaseResult(case_id=raw['case'], category=category, status=CaseStatus.RECORDED,
        route=raw['route'], task_completion=machine['task_completion'], safety=machine['safety'],
        fault_detection=fault_status(machine['fault_setup'], machine['fault_detection']),
        fault_recovery=fault_status(machine['fault_setup'], machine['fault_recovery']),
        system_reliability=machine['system_reliability'], agent_usage=roles, review_status=review_status,
        verifier_status=None if verification is None else verification['verdict'],
        final_outcome=raw['refusal_reason'] or raw['status'], latency_ms=raw['latency_ms'],
        provider_calls=raw['provider_calls'], decisions=decisions,
        usage=usage_snapshot(raw['records'], committed=raw['committed_exposure_usd'], peak=raw['peak_reserved_exposure_usd']),
        retrieval_backend=raw['retrieval']['backend'],
        systemic_failure=raw.get('systemic_failure'),
        schema_failure_stage=raw.get('schema_failure_stage'),
        release_record=raw.get('release_record'),hybrid_diagnostics=raw.get('hybrid_diagnostics'))


def atomic_json(path, value):
    """Same-filesystem replacement; fsync data and directory before returning."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.'+path.name+'.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


class GateStore:
    def __init__(self, root, schedule, *, preflight=None):
        self.root = Path(root)
        self.schedule = list(schedule)
        ids = [x['case_id'] for x in self.schedule]
        if len(ids) != len(set(ids)) or any(not x or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in x) for x in ids):
            raise ValueError('Unique safe case IDs required')
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError('New empty run directory required; never overwrite history')
        self.root.mkdir(parents=True, exist_ok=True)
        self.preflight = preflight
        self.records = {}
        self.provider_usage = {}
        self.provider_sequence=0;self.provider_last=None
        self.journal_lock=RLock()
        self.started = set()
        atomic_json(self.root/'manifest.json', {'schedule':self.schedule, 'preflight':preflight,
            'human_adjudication':HumanAdjudication().model_dump(mode='json')})

    def provider_checkpoint(self, case_id, snapshot):
        # Independent of result/report normalization; called as usage is known.
        if case_id not in {x['case_id'] for x in self.schedule}:raise ValueError('Unknown case journal identity')
        with self.journal_lock:
            self.provider_sequence+=1
            atomic_json(self.root/'provider'/f'{case_id}.json', {**snapshot,'sequence':self.provider_sequence})
            self.provider_usage[case_id] = snapshot['usage']
            self.provider_last=case_id

    def _write_case(self, record):
        atomic_json(self.root/'cases'/f'{record.case_id}.json', record.model_dump(mode='json'))
        self.records[record.case_id] = record

    def summary(self, *, aborted=False, error=None):
        from decimal import Decimal
        with self.journal_lock:
            provider_usage=dict(self.provider_usage);provider_last=self.provider_last
        usages = [Usage.model_validate(x) for x in provider_usage.values()]
        # Prefer durable provider journals; use normalized usage where no journal exists.
        usages += [x.usage for k,x in self.records.items() if k not in provider_usage]
        recorded = sum(x.status is CaseStatus.RECORDED for x in self.records.values())
        return {'status':'EVALUATION_ABORTED' if aborted else 'EVALUATION_COMPLETED' if recorded==len(self.schedule) else 'EVALUATION_RUNNING',
            'failure_class':'HARNESS_EXECUTION_ERROR' if aborted else None,
            'error_type':error, 'completed_case_count':recorded,
            'unstarted_case_count':len(self.schedule)-len(self.started),
            'started_case_count':len(self.started), 'preflight':self.preflight,
            'cases':[self.records.get(x['case_id'],CaseResult(case_id=x['case_id'], category=x['category'],
                status=CaseStatus.NOT_STARTED)).model_dump(mode='json') for x in self.schedule],
            'usage':{'known_input_tokens':sum(x.known_input_tokens for x in usages),
                'known_output_tokens':sum(x.known_output_tokens for x in usages),
                'known_estimated_cost_usd':str(sum((Decimal(x.known_estimated_cost_usd) for x in usages),Decimal(0))),
                'unknown_requests':sum(x.unknown_requests for x in usages),
                'unknown_reserved_exposure_usd':str(sum((Decimal(x.unknown_reserved_exposure_usd) for x in usages),Decimal(0))),
                'reserved_exposure_usd':str(sum((Decimal(x.reserved_exposure_usd) for x in usages),Decimal(0))),
                'committed_exposure_usd':provider_usage[provider_last]['committed_exposure_usd'] if provider_last else next((x.committed_exposure_usd for x in reversed(usages) if x.committed_exposure_usd is not None),None),
                'peak_reserved_exposure_usd':str(max((Decimal(x.peak_reserved_exposure_usd) for x in usages if x.peak_reserved_exposure_usd is not None),default=Decimal(0))) if usages else None},
            'missing_accounting_case_ids':[k for k in sorted(self.started) if k not in provider_usage and
                (k not in self.records or not self.records[k].usage.accounting_available)],
            'human_adjudication':HumanAdjudication().model_dump(mode='json')}

    def run(self, execute, *, normalize=normalize_case, aggregate=None,stop_after=None):
        aggregate = aggregate or (lambda store: store.summary())
        systemic_policy = SystemicStopPolicy()
        stage = 'initial_report'; current = None
        try:
            atomic_json(self.root/'aggregate.json', self.summary())
            for spec in self.schedule:
                current = spec; case_id = spec['case_id']; self.started.add(case_id)
                atomic_json(self.root/'started.json', sorted(self.started))
                stage = 'request'
                raw = execute(spec, lambda snapshot:self.provider_checkpoint(case_id,snapshot))
                stage = 'raw_checkpoint'
                atomic_json(self.root/'raw'/f'{case_id}.json', raw)
                stage = 'normalization'
                result = normalize(raw,spec['category'])
                if result.case_id != case_id: raise ValueError('Case identity mismatch')
                stage = 'case_checkpoint'
                self._write_case(result)
                stage = 'aggregation'
                atomic_json(self.root/'aggregate.json', aggregate(self))
                systemic_reason = systemic_policy.observe(result)
                if systemic_reason or stop_after:
                    stage='stop_policy'
                    reason=systemic_reason or stop_after(result)
                    if reason:
                        stopped=self.summary();stopped.update(
                            status='EVALUATION_ABORTED' if systemic_reason else 'EVALUATION_STOPPED',
                            failure_class='SYSTEMIC_FAILURE' if systemic_reason else None,
                            stop_reason=reason)
                        atomic_json(self.root/'stop.json',{'case_id':case_id,'reason':reason,
                            'systemic':bool(systemic_reason)})
                        for pending in self.schedule:
                            if pending['case_id'] not in self.started:
                                self._write_case(CaseResult(case_id=pending['case_id'],
                                    category=pending['category'],status=CaseStatus.NOT_STARTED))
                        atomic_json(self.root/'aggregate.json',stopped)
                        return stopped
            return self.summary()
        except Exception as error:
            if current and current['case_id'] not in self.records:
                usage = Usage.model_validate(self.provider_usage[current['case_id']]) if current['case_id'] in self.provider_usage else Usage()
                self._write_case(CaseResult(case_id=current['case_id'], category=current['category'],
                    status=CaseStatus.HARNESS_ERROR, failure_class='HARNESS_EXECUTION_ERROR',
                    fault_detection=FaultStatus.UNKNOWN if current['category']=='fault' else FaultStatus.NOT_APPLICABLE,
                    fault_recovery=FaultStatus.UNKNOWN if current['category']=='fault' else FaultStatus.NOT_APPLICABLE,
                    error_type=type(error).__name__, usage=usage, notes=(f'Evaluator stage: {stage}; no backend outcome inferred.',)))
            partial = self.summary(aborted=True,error=type(error).__name__)
            partial['failure_stage'] = stage
            atomic_json(self.root/'aggregate.json',partial)
            return partial

    @classmethod
    def recover(cls, root):
        """Rebuild aborted reporting from disk only, never resume execution."""
        root=Path(root); manifest=json.loads((root/'manifest.json').read_text())
        store=cls.__new__(cls);store.root=root;store.schedule=manifest['schedule'];store.preflight=manifest['preflight']
        store.started=set(json.loads((root/'started.json').read_text())) if (root/'started.json').exists() else set()
        store.records={p.stem:CaseResult.model_validate_json(p.read_text()) for p in (root/'cases').glob('*.json')}
        journals={p.stem:json.loads(p.read_text()) for p in (root/'provider').glob('*.json')}
        store.provider_usage={k:v['usage'] for k,v in journals.items()}
        store.provider_last=max(journals,key=lambda k:journals[k]['sequence']) if journals else None
        store.provider_sequence=max((x['sequence'] for x in journals.values()),default=0)
        store.journal_lock=RLock()
        for spec in store.schedule:
            if spec['case_id'] in store.started and spec['case_id'] not in store.records:
                store._write_case(CaseResult(case_id=spec['case_id'],category=spec['category'],status=CaseStatus.HARNESS_ERROR,
                    failure_class='HARNESS_EXECUTION_ERROR',error_type='InterruptedExecution',
                    usage=Usage.model_validate(store.provider_usage[spec['case_id']]) if spec['case_id'] in store.provider_usage else Usage(),
                    notes=('Recovered evidence only; no request was resumed.',)))
        report=store.summary(aborted=True,error='InterruptedExecution')
        if (root/'stop.json').exists():
            stop=json.loads((root/'stop.json').read_text())
            report.update(status='EVALUATION_ABORTED' if stop['systemic'] else 'EVALUATION_STOPPED',
                failure_class='SYSTEMIC_FAILURE' if stop['systemic'] else None,
                error_type=None,stop_reason=stop['reason'])
        atomic_json(root/'aggregate.json',report)
        return report
