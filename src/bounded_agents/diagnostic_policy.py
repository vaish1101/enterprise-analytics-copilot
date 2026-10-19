"""Opt-in extractive diagnostic policy v2; never selected by the default app.

Source identity, retrieval relevance, explanation and rendered-answer support
are separate checks. This bounded English policy is not a semantic truth oracle.
Canonical evidence is never rewritten, relabeled or replaced by an excerpt.
"""
from dataclasses import dataclass, asdict
import csv
import hashlib
import json
from pathlib import Path
import re
import time

from src.bounded_agents.answer_contract import components, ComponentRole, authenticity, Authenticity
from src.bounded_agents.comparison import SingleControllerGraph, SpecializedGraph
from src.bounded_agents.completeness import documentary_required
from src.bounded_agents.models import AgentStatus, CriticFeedback
from src.bounded_agents.post_synthesis import governed_draft
from src.bounded_agents.release_record import ReleaseRecord, ReleaseMode
from src.bounded_agents.source_ownership import excerpt
from src.orchestration.models import WorkflowStatus
from src.retrieval.models import EvidenceUnitType, RetrievalStatus
from src.retrieval.retrieve import PgVectorRetriever, GovernedRetriever

VERSION='experimental-question-linked-sufficiency-2'
MOVEMENT=re.compile(r'\b(?:higher|lower|increas\w*|decreas\w*|positive|negative|unfavo\w*|favo\w*|'
    r'offset\w*|growth|declin\w*|improv\w*|reduc\w*|ramp[ -]?up|headwinds?|tailwinds?)\b',re.I)
DRIVER=re.compile(r'\b(?:volumes?|pricing|prices?|mix|demand|costs?|aftersales|currency|exchange|portfolio|'
    r'leasing|productivity|capacity|supply|restructuring|orders?|energy|acquisitions?|divestments?|consolidation|backlog)\b',re.I)
RELATION=re.compile(r'\b(?:driven by|due to|because|reflect\w*|contribut\w*|affect\w*|support\w*|'
    r'impact\w*|benefit\w*|offset\w*|reduc\w*|increase\w*|decrease\w*|improv\w*|weigh\w*|boost\w*|lift\w*|drove)\b',re.I)
GLOSSARY=re.compile(r'\b(?:glossary|definition|defines?|is defined|calculated as|methodology)\b',re.I)
UNSUPPORTED=re.compile(r'\b(?:unavailable|not (?:available|provided|reported|discussed)|no explanation|'
    r'forecast\w*|outlook|hypothetical|scenario|anticipat\w*|could|might)\b|'
    r'\b(?:expect|expects|expected|expecting)\b.{0,60}\b(?:to|next|will|future|growth)\b|'
    r'\bmay\s+(?:improve|grow|increase|decrease|fall|rise|benefit|reduce)\b',re.I)
INSTRUCTION=re.compile(r'(?:ignore (?:the user|previous|all)|bypass verification|reveal (?:secrets|credentials)|system prompt)',re.I)


def normalized(text):return ' '.join(text.split())


def mapped_text(text):
    out=[];positions=[]
    for i,c in enumerate(text):
        if c.isspace():
            if out and out[-1]!=' ':out.append(' ');positions.append(i)
        else:out.append(c);positions.append(i)
    if out and out[-1]==' ':out.pop();positions.pop()
    return ''.join(out),positions


def diagnostic_required(plan):
    return documentary_required(plan) and plan.operation.value!='DEFINE_METRIC' and (
        plan.requires_decomposition or plan.operation.value=='EXPLAIN_WITH_EVIDENCE'
        or bool(re.search(r'\b(?:why|what\s+drove|what\s+caused|explain.*(?:drivers|change))\b',plan.raw_question,re.I)))


@dataclass(frozen=True)
class Passage:
    evidence_id:str
    parent_hash:str
    source_start:int
    source_end:int
    text:str
    context:str
    binding:str


@dataclass(frozen=True)
class UnitCheck:
    source_integrity:bool
    authenticity:str
    retrieval_scope_match:bool
    question_relevant:bool
    explanatory_sufficient:bool
    passages:tuple[Passage,...]
    reason:str


@dataclass(frozen=True)
class Assessment:
    required:bool
    evidence_sufficient:bool
    answer_sufficient:bool
    eligible_ids:tuple[str,...]
    reason:str


class QuestionPolicy:
    def __init__(self,root):
        root=Path(root)
        self.metrics={r['metric_id']:r for r in csv.DictReader((root/'config/metric_catalog.csv').open())}
        self.companies=list(csv.DictReader((root/'config/company_aliases.csv').open()))
        self.scopes=list(csv.DictReader((root/'config/business_scope_aliases.csv').open()))

    def focus(self,text,plan):
        metric=self.metrics[plan.primary_target.metric_id.value]
        family=metric['canonical_family'].lower()
        text=normalized(text).lower()
        if 'organic' in family:
            return bool(re.search(r'\borganic\b.{0,220}\b(?:sales|revenue)\b.{0,40}\bgrowth\b',text))
        if 'adjusted_ebit' in family:
            return bool(re.search(r'\badjusted\s+ebit\b|\bebit\s+adjusted\b',text))
        if 'ebit' in family:return bool(re.search(r'\bebit\b|earnings before interest and tax',text))
        # Vocabulary comes from the governed family/reported name, not an issuer
        # or case-specific ID. Unrecognized families remain conservatively gated.
        names=[metric['reported_name'].lower(),family.replace('_',' ')]
        return any(re.search(r'\b'+re.escape(name)+r'\b',text) for name in names if len(name)>3)

    def context_matches(self,text,plan):
        target=plan.primary_target;lower=text.lower()
        companies={r['company_id'] for r in self.companies if len(r['alias'])>=4 and
            re.search(r'\b'+re.escape(r['alias'])+r'\b',lower)}
        if companies-{target.company.value}:return False
        scopes={r['scope_id'] for r in self.scopes if r['company_id']==target.company.value
            and len(r['alias'])>=4 and r['alias']!='group'
            and re.search(r'\b'+re.escape(r['alias'])+r'\b',lower)}
        if scopes and target.business_scope not in scopes:return False
        years=set(re.findall(r'\b20\d{2}\b',text))
        requested=set(re.findall(r'20\d{2}',target.period.value))
        if years and not years&requested:return False
        # An explicit different quarter/half is a conflict even within the same
        # year; inherited pinned metadata is sufficient when prose omits dates.
        explicit=set(re.findall(r'\b(Q[1-4]|H[12])\b',text,re.I))
        requested_grain=target.period.value.split('_')[0]
        if explicit and requested_grain not in {x.upper() for x in explicit}:return False
        return True

    def inspect(self,unit,plan,*,fixture_mode=False):
        integrity=hashlib.sha256(unit.text.encode()).hexdigest()==unit.content_hash
        origin=authenticity(unit).value
        target=plan.primary_target
        relevant=bool(target and unit.company_id==target.company.value
            and target.period.value in unit.reporting_periods
            and (not target.business_scope or target.business_scope in unit.business_scopes)
            and target.metric_id.value in unit.metric_ids)
        if not integrity:return UnitCheck(False,origin,False,False,False,(),'SOURCE_HASH_MISMATCH')
        if origin==Authenticity.SYNTHETIC_FIXTURE.value and not fixture_mode:
            return UnitCheck(True,origin,relevant,False,False,(),'SYNTHETIC_SOURCE_NOT_ALLOWED')
        if not relevant:return UnitCheck(True,origin,False,False,False,(),'TARGET_METADATA_MISMATCH')
        if unit.evidence_unit_type is EvidenceUnitType.METRIC_DEFINITION:
            return UnitCheck(True,origin,True,False,False,(),'DEFINITION_IS_NOT_RESULT_EXPLANATION')
        if INSTRUCTION.search(unit.text):return UnitCheck(True,origin,True,False,False,(),'UNTRUSTED_INSTRUCTIONS')
        text,mapping=mapped_text(unit.text)
        # Preserve decimal numbers, abbreviations and PDF line-wraps. Sentence
        # windows have strict size limits; no document-wide glossary matching.
        starts=[0]+[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])',text)]
        ends=starts[1:]+[len(text)]
        windows=[(a,b,text[a:b].strip()) for a,b in zip(starts,ends)]
        found=[];question_relevant=False
        for i,(a,b,sentence) in enumerate(windows):
            if not (12<=len(sentence)<=650) or sentence.rstrip().endswith('?') or GLOSSARY.search(sentence) or UNSUPPORTED.search(sentence):continue
            if self.focus(sentence,plan) and self.context_matches(sentence,plan):question_relevant=True
            if not DRIVER.search(sentence):continue
            binding=None;context=sentence;start=a
            if self.focus(sentence,plan) and RELATION.search(sentence):binding='LOCAL_METRIC_DRIVER_RELATION'
            elif i and re.match(r'(?:This|That|The) (?:performance|growth|result|development)\b',sentence,re.I) and RELATION.search(sentence):
                pa,pb,previous=windows[i-1]
                if len(previous)<=650 and self.focus(previous,plan) and not GLOSSARY.search(previous) and not UNSUPPORTED.search(previous):
                    binding='IMMEDIATE_RESULT_ANTECEDENT';context=previous+' '+sentence;start=pa
            if binding and self.context_matches(context,plan):
                end=min(b,len(mapping))
                if end>start:
                    found.append(Passage(unit.evidence_unit_id,unit.content_hash,mapping[start],mapping[end-1]+1,
                        normalized(unit.text[mapping[start]:mapping[end-1]+1]),context,binding))
        # Governed bridge layout explicitly connects its driver bullets to the
        # metric header. This exception is for structured bridge records, not
        # arbitrary prose containing a glossary mention somewhere else.
        if unit.evidence_unit_type is EvidenceUnitType.BRIDGE_DECOMPOSITION:
            header=' '.join(x for x in (unit.section,unit.table_title) if x)
            header_bound=self.focus(header,plan) or (bool(re.search(r'\bebit\b',header,re.I)) and self.focus(text,plan))
            if header_bound and self.context_matches(header,plan):
                question_relevant=True
                for match in re.finditer(r'[^\uf000-\uf8ff\u2013\u2014]{8,240}',text):
                    clause=match.group().strip()
                    if (DRIVER.search(clause) and MOVEMENT.search(clause) and not UNSUPPORTED.search(clause)
                        and not GLOSSARY.search(clause) and self.context_matches(clause,plan)):
                        found.append(Passage(unit.evidence_unit_id,unit.content_hash,mapping[match.start()],mapping[match.end()-1]+1,
                            normalized(unit.text[mapping[match.start()]:mapping[match.end()-1]+1]),header+' | '+clause,'GOVERNED_BRIDGE_HEADER'))
        unique=tuple({(p.source_start,p.source_end):p for p in found}.values())
        return UnitCheck(True,origin,True,question_relevant,bool(unique),unique,'QUESTION_LINKED_PASSAGES' if unique else 'NO_QUESTION_LINKED_EXPLANATION')

    def assess(self,bundle,draft=None,*,fixture_mode=False):
        if not diagnostic_required(bundle.plan):return Assessment(False,True,True,(),'NOT_APPLICABLE')
        docs={r.evidence_unit_id:r for r in bundle.retrieval.results
            if self.inspect(r,bundle.plan,fixture_mode=fixture_mode).explanatory_sufficient} if bundle.retrieval else {}
        if not docs:return Assessment(True,False,False,(),'NO_ADMITTED_QUESTION_LINKED_EXPLANATION')
        if draft is None:return Assessment(True,True,False,tuple(docs),'ANSWER_NOT_CHECKED')
        asks_rate_change=re.search(r'\b(?:growth|margin|rate)\s+chang(?:e|ed)\b|\bchange in (?:\w+\s+){0,4}(?:growth|margin|rate)\b',bundle.plan.raw_question,re.I)
        if asks_rate_change and bundle.plan.primary_target.comparison_period is None:
            return Assessment(True,True,False,tuple(docs),'COMPARISON_BASELINE_UNRESOLVED')
        typed=components(draft)
        for c in draft.claims:
            component=typed.get(c.claim_id)
            if (not component or component.role is not ComponentRole.DIRECT_ANSWER or c.value is not None
                or len(c.evidence_ids)!=1 or c.evidence_ids[0] not in docs):continue
            doc=docs[c.evidence_ids[0]]
            # Full immutable source quotation includes all context and all
            # admitted passages. Free paraphrase is not auto-certified by words.
            if (component.source_quotation and c.text==excerpt(doc.text)
                and component.evidence_ids==c.evidence_ids and component.authenticity==authenticity(doc)):
                return Assessment(True,True,True,tuple(docs),'EXTRACTIVE_ANSWER_SUPPORTED')
        return Assessment(True,True,False,tuple(docs),'ANSWER_SUPPORT_NOT_ESTABLISHED')


class QuestionView:
    def __init__(self,target,graph):self.target=target;self.graph=graph;self.audit=[];self.cache={}
    def __getattr__(self,key):return getattr(self.target,key)
    @property
    def supported_methods(self):return self.target.supported_methods
    def retrieve(self,query,*,method='dense'):
        plan=self.graph._question_plan;active=diagnostic_required(plan)
        scoped=query
        if active:
            kinds={u.evidence_unit_type for u in self.target.candidate_units(query)}
            preferred=(EvidenceUnitType.NARRATIVE_SECTION,EvidenceUnitType.BRIDGE_DECOMPOSITION,EvidenceUnitType.FOOTNOTE)
            if EvidenceUnitType.BRIDGE_DECOMPOSITION not in kinds:
                preferred=(EvidenceUnitType.NARRATIVE_SECTION,EvidenceUnitType.TABLE,EvidenceUnitType.FOOTNOTE)
            scoped=query.model_copy(update={'preferred_evidence_types':preferred})
        key=(method,scoped.model_dump_json());cached=key in self.cache;start=time.perf_counter()
        if cached:response=self.cache[key]
        else:
            response=self.target.retrieve(scoped,method=method)
            self.cache[key]=response
        self.graph._validate_retrieval(scoped,response,self.target)
        checks={r.evidence_unit_id:self.graph.question_policy.inspect(r,plan,fixture_mode=self.graph.fixture_mode)
            for r in response.results} if active else {}
        rows=tuple(r for r in response.results if not active or checks[r.evidence_unit_id].explanatory_sufficient)
        self.audit.append({'version':VERSION,'cache_hit':cached,'method':method,'top_k':scoped.top_k,
            'filters':response.trace.plan_derived_filters,'raw_ids':[r.evidence_unit_id for r in response.results],
            'accepted_ids':[r.evidence_unit_id for r in rows],
            'checks':{k:asdict(v) for k,v in checks.items()},'elapsed_ms':(time.perf_counter()-start)*1000})
        return response.model_copy(update={'results':rows,'status':RetrievalStatus.SUCCESS if rows else RetrievalStatus.NO_RELEVANT_EVIDENCE,
            'reason':None if rows else 'No retrieved passage passed question-linked explanation checks.',
            'trace':response.trace.model_copy(update={'final_evidence_ids':tuple(r.evidence_unit_id for r in rows)})})


class QuestionPgView(QuestionView,PgVectorRetriever):pass
class QuestionLocalView(QuestionView,GovernedRetriever):pass


class QuestionGateMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.question_policy=QuestionPolicy(self.root)
        target=self.knowledge_tool.retriever
        cls=QuestionPgView if isinstance(target,PgVectorRetriever) else QuestionLocalView if isinstance(target,GovernedRetriever) else QuestionView
        self.knowledge_tool.retriever=cls(target,self)
        self.diagnostic_assessment=None;self._question_gap=None
    def _route_node(self,state):
        result=super()._route_node(state);self._question_plan=state['plan'];return result
    def _generate(self,state,*,revision):
        check=self.question_policy.assess(state['evidence'],fixture_mode=self.fixture_mode)
        if check.required and not check.evidence_sufficient:
            self._question_gap=check
            self._event('synthesis',AgentStatus.SKIPPED,action='question_linked_explanation_missing')
            return {'draft':governed_draft(state['evidence']),'revision_count':int(revision),'status':WorkflowStatus.DRAFTED}
        return super()._generate(state,revision=revision)
    def _critic(self,state):
        check=self.question_policy.assess(state['evidence'],state['draft'],fixture_mode=self.fixture_mode)
        self.diagnostic_assessment=check
        if (check.required and check.evidence_sufficient and not check.answer_sufficient
            and check.reason=='ANSWER_SUPPORT_NOT_ESTABLISHED' and not self.completion_repair_attempted
            and self._deadline()>self.reserves.revision+self.reserves.verification):
            # Preserve the candidate's existing one-attempt source-only repair.
            # Only newly admitted evidence can be used; repair is not approval.
            from src.bounded_agents.release_policy import repair_component
            self.completion_repair_attempted=True;started=time.perf_counter()
            repaired=repair_component(state['draft'],state['evidence'],reserved_claim_ids=self.withheld_claim_ids)
            if time.perf_counter()-started>=self.reserves.revision:raise TimeoutError('Completion repair window exceeded')
            if repaired is not None and self.question_policy.assess(state['evidence'],repaired,fixture_mode=self.fixture_mode).answer_sufficient:
                self._event('completion.repair',AgentStatus.COMPLETED,action='question_supported_canonical_source_completion')
                update=self._critic({**state,'draft':repaired,'revision_count':1})
                return {**update,'draft':update.get('draft',repaired),'revision_count':1}
        if check.required and not check.answer_sufficient:
            self._question_gap=check
            self._event('question_support',AgentStatus.BLOCKED,decision=asdict(check))
            return {'draft':governed_draft(state['evidence']),
                'critic':CriticFeedback(decision='reject',issues=('incomplete_answer',),claim_ids=(),evidence_sufficient=False)}
        self._question_gap=None
        return super()._critic(state)
    def _after_verify(self,state):
        if self._question_gap:return 'pass' if state['verification'].verdict.value=='PASS' and state['draft'].claims else 'refuse'
        return super()._after_verify(state)
    def _finalize(self,state):
        check=self.question_policy.assess(state['evidence'],state['draft'],fixture_mode=self.fixture_mode)
        self.diagnostic_assessment=check
        if not check.required or check.answer_sufficient:return super()._finalize(state)
        self._deadline();seed=governed_draft(state['evidence'])
        limitation='Partial numerical answer: no retrieved passage was admitted as a supported explanation of this question.' if not check.evidence_sufficient else 'Partial numerical answer: documentary answer support was not established.'
        if check.reason=='COMPARISON_BASELINE_UNRESOLVED':
            limitation='Partial numerical answer: the comparison period for the requested change in growth or margin must be clarified.'
        seed=seed.model_copy(update={'limitations':tuple(dict.fromkeys((*seed.limitations,limitation)))})
        verification=self.verifier.verify(seed,state['evidence']);self._deadline()
        ids={c.claim_id for c in seed.claims};useful=bool(ids) and all(c.value is not None for c in seed.claims)
        if verification.verdict.value!='PASS' or not useful:
            self.release_record=ReleaseRecord(release_mode=ReleaseMode.WITHHELD,verification_status=verification.verdict.value,
                verification_id=verification.verification_id,reason_codes=(check.reason,))
            brief=self._brief({**state,'verification':verification},WorkflowStatus.REFUSED,
                'The available evidence does not establish a supported explanation.',refusal=check.reason)
            return {'final':brief,'status':WorkflowStatus.REFUSED,'verification':verification}
        self.release_mode='question_support_incomplete_numeric_subset'
        self.release_record=ReleaseRecord(release_mode=ReleaseMode.PARTIAL,verification_status='PASS',
            verification_id=verification.verification_id,parent_verification_id=state['verification'].verification_id,
            released_claim_ids=tuple(c.claim_id for c in seed.claims),
            withheld_claim_ids=tuple(sorted(self.withheld_claim_ids|{c.claim_id for c in state['draft'].claims if c.claim_id not in ids})),
            reason_codes=(check.reason,'DOCUMENTARY_COMPONENT_WITHHELD'),useful=True)
        brief=self._brief({**state,'draft':seed,'verification':verification},WorkflowStatus.COMPLETED,
            seed.answer,seed.claims,refusal=self.release_mode)
        used={e for c in seed.claims for e in c.evidence_ids}
        brief=brief.model_copy(update={'limitations':seed.limitations,'citations':tuple(c for c in brief.citations if c.evidence_unit_id in used),
            'evidence_ids':tuple(sorted(used))})
        return {'final':brief,'draft':seed,'verification':verification,'status':WorkflowStatus.COMPLETED}


class QuestionController(QuestionGateMixin,SingleControllerGraph):pass
class QuestionSpecialists(QuestionGateMixin,SpecializedGraph):pass
ARMS={'B':QuestionController,'C':QuestionSpecialists}
