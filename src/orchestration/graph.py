"""Actual LangGraph workflow for governed analytics, retrieval, synthesis and verification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import hashlib
from pathlib import Path
import time
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.llm.base import StructuredLLMProvider
from src.llm.base import ProviderMalformedOutputError, ProviderRetryableError
from src.llm.fake_provider import DeterministicFakeProvider
from src.planning.models import PlanOperation, PlanningStatus, QuestionType
from src.planning.planner import QuestionPlanner
from src.retrieval.models import EvidenceUnit, RetrievalStatus
from src.retrieval.retrieve import GovernedRetriever
from src.evaluation.contradiction_detector import ContradictionDetector
from src.persistence.checkpoint_store import CheckpointStore

from .models import (
    ClaimSupport,
    CitationRecord,
    DecisionBrief,
    EvidenceBundle,
    SynthesisDraft,
    TokenUsage,
    ToolId,
    TraceEvent,
    VerificationVerdict,
    WorkflowRoute,
    WorkflowStatus,
)
from .prompts import PROMPT_VERSIONS, load_prompt
from .state import GraphState
from .tools import GovernedAnalyticsTool, GovernedKnowledgeTool
from .verifier import DeterministicVerifier


def _trace(sequence: int, node: str, started: float, *, event: str = "completed", tool_id=None,
           inputs=(), outputs=(), usage=None, error_code=None, **metadata) -> TraceEvent:
    return TraceEvent(
        sequence=sequence, node=node, event=event, started_at=datetime.now(UTC),
        duration_ms=(time.perf_counter() - started) * 1000, tool_id=tool_id,
        input_ids=tuple(inputs), output_ids=tuple(outputs), usage=usage, error_code=error_code,
        **metadata,
    )


class EnterpriseAnalyticsGraph:
    """Bounded, checkpointed workflow. No node can execute an untyped general tool."""

    def __init__(self, root: Path | str | None = None, *, provider: StructuredLLMProvider | None = None,
                 retriever: GovernedRetriever | None = None, retrieval_method: str = "dense",
                 max_provider_attempts: int = 2, checkpoint_store: CheckpointStore | None = None):
        self.root = Path(root) if root else Path(__file__).resolve().parents[2]
        self.planner = QuestionPlanner(self.root)
        self.provider = provider or DeterministicFakeProvider()
        self.max_provider_attempts = max(1, max_provider_attempts)
        if retriever is None:
            corpus = self.root / "data/retrieval/local/evidence_units.jsonl"
            units = [EvidenceUnit.model_validate_json(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line]
            retriever = GovernedRetriever(units, root=self.root)
        self.analytics_tool = GovernedAnalyticsTool(self.root)
        self.knowledge_tool = GovernedKnowledgeTool(retriever, method=retrieval_method)
        self.verifier = DeterministicVerifier()
        self.contradiction_detector = ContradictionDetector()
        self.checkpoint_store = checkpoint_store or CheckpointStore(mode="memory")
        self.checkpointer = self.checkpoint_store.saver
        self.graph = self._build().compile(checkpointer=self.checkpointer)

    @staticmethod
    def _route(plan) -> WorkflowRoute:
        if plan.status is PlanningStatus.NEEDS_CLARIFICATION:
            return WorkflowRoute.NEEDS_CLARIFICATION
        if plan.status is PlanningStatus.UNSUPPORTED or plan.operation is PlanOperation.COMPARE:
            return WorkflowRoute.UNSUPPORTED
        if plan.operation in {PlanOperation.DEFINE_METRIC, PlanOperation.RETRIEVE_CONTEXT}:
            return WorkflowRoute.KNOWLEDGE_ONLY
        if plan.question_type is QuestionType.HYBRID_ANALYSIS:
            return WorkflowRoute.HYBRID
        if plan.requires_decomposition:
            return WorkflowRoute.DECOMPOSITION_EXPLANATION
        return WorkflowRoute.ANALYTICS_ONLY

    def _build(self) -> StateGraph:
        builder = StateGraph(GraphState)
        builder.add_node("plan", self._plan)
        builder.add_node("route", self._route_node)
        builder.add_node("analytics_only", self._analytics)
        builder.add_node("knowledge_only", self._knowledge)
        builder.add_node("fanout", lambda state: {})
        builder.add_node("analytics_branch", self._analytics)
        builder.add_node("knowledge_branch", self._knowledge)
        builder.add_node("assemble", self._assemble)
        builder.add_node("synthesize", self._synthesize)
        builder.add_node("verify", self._verify)
        builder.add_node("revise", self._revise)
        builder.add_node("finalize", self._finalize)
        builder.add_node("short_circuit", self._short_circuit)
        builder.add_edge(START, "plan")
        builder.add_edge("plan", "route")
        builder.add_conditional_edges("route", lambda s: s["route"], {
            WorkflowRoute.ANALYTICS_ONLY: "analytics_only",
            WorkflowRoute.KNOWLEDGE_ONLY: "knowledge_only",
            WorkflowRoute.HYBRID: "fanout",
            WorkflowRoute.DECOMPOSITION_EXPLANATION: "fanout",
            WorkflowRoute.NEEDS_CLARIFICATION: "short_circuit",
            WorkflowRoute.UNSUPPORTED: "short_circuit",
        })
        builder.add_edge("analytics_only", "assemble")
        builder.add_edge("knowledge_only", "assemble")
        builder.add_edge("fanout", "analytics_branch")
        builder.add_edge("fanout", "knowledge_branch")
        builder.add_edge(["analytics_branch", "knowledge_branch"], "assemble")
        builder.add_edge("assemble", "synthesize")
        builder.add_edge("synthesize", "verify")
        builder.add_conditional_edges("verify", self._after_verify, {
            "pass": "finalize", "revise": "revise", "refuse": "finalize",
        })
        builder.add_edge("revise", "verify")
        builder.add_edge("finalize", END)
        builder.add_edge("short_circuit", END)
        return builder

    def run(self, question: str, *, question_id: str | None = None, thread_id: str | None = None) -> DecisionBrief:
        qid = question_id or f"q_{hashlib.sha256(question.encode()).hexdigest()[:12]}"
        rid = f"run_{hashlib.sha256((qid + question).encode()).hexdigest()[:16]}"
        initial: GraphState = {
            "run_id": rid, "question": question, "question_id": qid,
            "status": WorkflowStatus.INITIALIZED, "revision_count": 0,
            "traces": [], "prompt_versions": [], "errors": [],
        }
        checkpoint_config = {"configurable": {"thread_id": thread_id or rid}}
        try:
            existing = self.graph.get_state(checkpoint_config)
            if existing.values and existing.values.get("run_id") == rid and existing.values.get("final"):
                self.last_state = existing.values
                saved = existing.values["final"]
                payload = dict(saved.__dict__) if isinstance(saved, DecisionBrief) else saved
                return DecisionBrief.model_validate(payload, strict=False)
            result = self.graph.invoke(initial, config=checkpoint_config)
            self.last_state = result
            return result["final"]
        except Exception as error:
            plan = self.planner.plan(question, question_id=qid)
            route = self._route(plan)
            failure_trace = TraceEvent(
                sequence=99, node="safe_failure", event="failed", started_at=datetime.now(UTC),
                duration_ms=0.0, input_ids=(qid,), error_code=type(error).__name__,
            )
            return DecisionBrief(
                run_id=rid, question_id=qid, status=WorkflowStatus.REFUSED, route=route,
                answer="I cannot provide a verified answer because the governed workflow failed safely.",
                refusal_reason=f"WORKFLOW_FAILURE:{type(error).__name__}", trace=(failure_trace,),
                provider_name=self.provider.name, provider_model=self.provider.model,
                prompt_versions=(), total_usage=TokenUsage(input_tokens=0, output_tokens=0, estimated_cost_usd=Decimal("0")),
            )

    def _plan(self, state: GraphState) -> dict[str, Any]:
        started = time.perf_counter()
        plan = self.planner.plan(state["question"], question_id=state["question_id"])
        return {"plan": plan, "status": WorkflowStatus.PLANNED,
                "traces": [_trace(1, "supervisor.plan", started, inputs=(state["question_id"],), outputs=(plan.question_id,))]}

    def _route_node(self, state: GraphState) -> dict[str, Any]:
        started = time.perf_counter(); route = self._route(state["plan"])
        return {"route": route, "status": WorkflowStatus.ROUTED,
                "traces": [_trace(2, "supervisor.route", started, inputs=(state["plan"].question_id,), outputs=(route.value,))],
                "prompt_versions": [PROMPT_VERSIONS["supervisor"]]}

    def _analytics(self, state: GraphState) -> dict[str, Any]:
        started = time.perf_counter(); plan = state["plan"]
        tool = {
            PlanOperation.LOOKUP: ToolId.ANALYTICS_LOOKUP,
            PlanOperation.CALCULATE_CHANGE: ToolId.ANALYTICS_CHANGE,
            PlanOperation.DECOMPOSE_VARIANCE: ToolId.ANALYTICS_DECOMPOSE,
            PlanOperation.RANK_CONTRIBUTIONS: ToolId.ANALYTICS_RANK,
            PlanOperation.RECONCILE: ToolId.ANALYTICS_RECONCILE,
            PlanOperation.EXPLAIN_WITH_EVIDENCE: ToolId.ANALYTICS_DECOMPOSE,
        }[plan.operation]
        execution_plan = plan
        if plan.operation is PlanOperation.EXPLAIN_WITH_EVIDENCE:
            execution_plan = plan.model_copy(update={"operation": PlanOperation.DECOMPOSE_VARIANCE})
        result = self.analytics_tool.invoke(execution_plan, tool)
        fact_ids = tuple(dict.fromkeys(
            fact.fact_id for fact in (
                result.primary_result, result.comparison_result,
                *result.supporting_results, *result.decomposition_components,
            ) if fact is not None
        ))
        return {"analytics": result, "traces": [_trace(3, "analytics_agent", started, tool_id=tool,
                inputs=(plan.question_id,), outputs=(result.execution_id, *result.calculation_run_ids),
                fact_ids=fact_ids, calculation_run_ids=result.calculation_run_ids)],
                "prompt_versions": [PROMPT_VERSIONS["analytics"]]}

    def _knowledge(self, state: GraphState) -> dict[str, Any]:
        started = time.perf_counter(); plan = state["plan"]
        result = self.knowledge_tool.invoke(plan, ToolId.KNOWLEDGE_RETRIEVE)
        outputs = tuple(item.evidence_unit_id for item in result.results)
        return {"retrieval": result, "traces": [_trace(3, "knowledge_agent", started,
                tool_id=ToolId.KNOWLEDGE_RETRIEVE, inputs=(plan.question_id,), outputs=outputs)],
                "prompt_versions": [PROMPT_VERSIONS["knowledge"]]}

    def _assemble(self, state: GraphState) -> dict[str, Any]:
        started = time.perf_counter(); retrieval = state.get("retrieval")
        selected = tuple(item.evidence_unit_id for item in retrieval.results[:5]) if retrieval and retrieval.status is RetrievalStatus.SUCCESS else ()
        conflicts = self.contradiction_detector.detect(
            state.get("analytics"), tuple(retrieval.results) if retrieval else ()
        )
        conflict_notes = tuple(
            f"{item.conflict_type}:{item.fact_id}:{item.evidence_unit_id}" for item in conflicts
        )
        bundle = EvidenceBundle(question_id=state["question_id"], plan=state["plan"],
                                analytics=state.get("analytics"), retrieval=retrieval,
                                selected_evidence_ids=selected, conflict_notes=conflict_notes)
        return {"evidence": bundle, "status": WorkflowStatus.EVIDENCE_READY,
                "traces": [_trace(4, "evidence_assembly", started, outputs=selected)]}

    def _generate(self, state: GraphState, *, revision: bool) -> dict[str, Any]:
        started = time.perf_counter(); prompt = load_prompt(self.root, "synthesis")
        last_error = None
        attempt = 0
        for attempt in range(1, self.max_provider_attempts + 1):
            try:
                result = self.provider.generate_structured(
                    role="synthesis", prompt=prompt,
                    payload={"question": state["question"], "evidence_bundle": state["evidence"],
                             "verification_feedback": state.get("verification") if revision else None},
                    output_model=SynthesisDraft, prompt_version=PROMPT_VERSIONS["synthesis"], revision=revision,
                )
                break
            except (TimeoutError, ProviderRetryableError, ProviderMalformedOutputError, ValueError) as error:
                last_error = error
        else:
            raise RuntimeError("structured provider failed after bounded retries") from last_error
        draft = result.value if isinstance(result.value, SynthesisDraft) else SynthesisDraft.model_validate(result.value)
        return {"draft": draft, "status": WorkflowStatus.REVISING if revision else WorkflowStatus.DRAFTED,
                "revision_count": 1 if revision else state.get("revision_count", 0),
                "traces": [_trace(5 if not revision else 7, "synthesis_agent.revise" if revision else "synthesis_agent",
                                   started, inputs=(state["evidence"].question_id,), outputs=(draft.draft_id,), usage=result.usage,
                                   provider_call=True, provider_name=result.provider_name,
                                   provider_model=result.provider_model, prompt_version=result.prompt_version,
                                   retry_number=attempt)],
                "prompt_versions": [result.prompt_version]}

    def _synthesize(self, state: GraphState) -> dict[str, Any]: return self._generate(state, revision=False)
    def _revise(self, state: GraphState) -> dict[str, Any]: return self._generate(state, revision=True)

    def _verify(self, state: GraphState) -> dict[str, Any]:
        started = time.perf_counter(); result = self.verifier.verify(state["draft"], state["evidence"])
        return {"verification": result, "status": WorkflowStatus.VERIFYING,
                "traces": [_trace(6 if state.get("revision_count", 0) == 0 else 8, "verifier_agent", started,
                                   inputs=(state["draft"].draft_id,), outputs=(result.verification_id,),
                                   verifier_verdict=result.verdict)],
                "prompt_versions": [PROMPT_VERSIONS["verifier"]]}

    @staticmethod
    def _after_verify(state: GraphState) -> str:
        verdict = state["verification"].verdict
        if verdict is VerificationVerdict.PASS: return "pass"
        if verdict is VerificationVerdict.NEEDS_REVISION and state.get("revision_count", 0) < 1: return "revise"
        return "refuse"

    def _brief(self, state: GraphState, status: WorkflowStatus, answer: str, claims=(), *, clarification=None, refusal=None) -> DecisionBrief:
        usages = [event.usage for event in state.get("traces", []) if event.usage]
        usage = TokenUsage(input_tokens=sum(x.input_tokens for x in usages), output_tokens=sum(x.output_tokens for x in usages),
                           estimated_cost_usd=sum((x.estimated_cost_usd for x in usages), Decimal("0")))
        evidence = state.get("evidence")
        analytics = evidence.analytics if evidence else None
        citations = ()
        if evidence and evidence.retrieval:
            selected = set(evidence.selected_evidence_ids)
            citations = tuple(CitationRecord(
                evidence_unit_id=item.evidence_unit_id, source_id=item.source_id,
                source_title=item.source_title, official_url=item.official_url,
                page_number=item.page_number, citation=item.citation,
            ) for item in evidence.retrieval.results if item.evidence_unit_id in selected)
        return DecisionBrief(
            run_id=state["run_id"], question_id=state["question_id"], status=status, route=state["route"],
            answer=answer, claims=tuple(claims), verification=state.get("verification"),
            clarification_question=clarification, refusal_reason=refusal,
            limitations=state.get("draft").limitations if state.get("draft") else (),
            evidence_ids=evidence.selected_evidence_ids if evidence else (),
            citations=citations,
            fact_ids=tuple(dict.fromkeys(fid for claim in claims for fid in claim.fact_ids)),
            calculation_run_ids=analytics.calculation_run_ids if analytics else (),
            trace=tuple(state.get("traces", [])), provider_name=self.provider.name,
            provider_model=self.provider.model, prompt_versions=tuple(dict.fromkeys(state.get("prompt_versions", []))),
            total_usage=usage,
        )

    def _finalize(self, state: GraphState) -> dict[str, Any]:
        verification = state["verification"]; draft = state["draft"]
        retrieval_required = state["route"] in {
            WorkflowRoute.KNOWLEDGE_ONLY,
            WorkflowRoute.HYBRID,
            WorkflowRoute.DECOMPOSITION_EXPLANATION,
        }
        retrieval = state["evidence"].retrieval
        if retrieval_required and (retrieval is None or retrieval.status is not RetrievalStatus.SUCCESS):
            status = WorkflowStatus.REFUSED; claims = ()
            answer = "I cannot provide the requested documentary context because no governed evidence was available."
            refusal = "REQUIRED_DOCUMENT_EVIDENCE_UNAVAILABLE"
        elif state["evidence"].conflict_notes:
            status = WorkflowStatus.EVIDENCE_CONFLICT; claims = (); answer = "The governed sources conflict, so no consolidated answer is provided."
            refusal = "EVIDENCE_CONFLICT"
        elif verification.verdict is VerificationVerdict.PASS:
            status = WorkflowStatus.COMPLETED; claims = draft.claims; answer = " ".join(claim.text for claim in claims); refusal = None
        else:
            supported_ids = set(verification.supported_claim_ids)
            claims = tuple(claim for claim in draft.claims if claim.claim_id in supported_ids)
            if claims:
                status = WorkflowStatus.COMPLETED
                answer = " ".join(claim.text for claim in claims)
                refusal = "Unsupported claims were removed after the bounded revision cycle."
            else:
                status = WorkflowStatus.REFUSED; answer = "I cannot provide a verified answer from the available governed evidence."
                refusal = "The draft failed independent verification after one revision."
        if claims:
            # Numeric language is rendered from verified structured fields, not
            # unrestricted model prose (which may swap labels or comparisons).
            bound = []
            analytics = state["evidence"].analytics
            facts = [analytics.primary_result, analytics.comparison_result, *analytics.supporting_results, *analytics.decomposition_components] if analytics else []
            names = {fact.fact_id: fact.reported_name for fact in facts if fact is not None}
            calculation_labels = {run.run_id: run.output_field.value.replace("_", " ").lower() for run in analytics.calculation_runs} if analytics else {}
            for claim in claims:
                if claim.value is not None:
                    prefix = "Management reported" if claim.claim_type.value == "MANAGEMENT_ATTRIBUTED" else "Calculated" if claim.claim_type.value == "CALCULATED" else "Reported"
                    if claim.claim_type.value == "CALCULATED":
                        prefix += " " + ", ".join(dict.fromkeys(calculation_labels[rid] for rid in claim.calculation_run_ids if rid in calculation_labels))
                    name = names.get(claim.fact_ids[0], claim.metric_id) if claim.fact_ids else claim.metric_id
                    text = f"{prefix}: {name}, {claim.business_scope}, {', '.join(claim.periods)}: {claim.value} {claim.unit}."
                    claim = claim.model_copy(update={"text": text})
                bound.append(claim)
            claims = tuple(bound)
            answer = " ".join(claim.text for claim in claims)
        return {"final": self._brief(state, status, answer, claims, refusal=refusal), "status": status}

    def _short_circuit(self, state: GraphState) -> dict[str, Any]:
        plan = state["plan"]
        if state["route"] is WorkflowRoute.NEEDS_CLARIFICATION:
            status = WorkflowStatus.NEEDS_CLARIFICATION; answer = plan.clarification_question or "Clarification is required."
            final = self._brief(state, status, answer, clarification=answer)
        else:
            status = WorkflowStatus.REFUSED; answer = plan.unsupported_reason or "The request is outside governed scope."
            final = self._brief(state, status, answer, refusal=answer)
        return {"final": final, "status": status}
