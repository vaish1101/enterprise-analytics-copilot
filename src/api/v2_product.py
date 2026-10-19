"""Public v2 projection. No legacy traces, prompts, decisions, or exceptions escape."""
from src.retrieval.retrieve import GovernedRetriever, PgVectorRetriever
from .schemas import ExecutionStage, V2ProductSummary

ROLES = {"analytics": "Analytics Agent", "evidence": "RAG Evidence Agent",
         "synthesis": "Insight Synthesis Agent", "critic": "Semantic Review Agent"}
STAGES = {"plan": "Question classified", "route": "Governed route selected",
          "investigate": "Bounded investigation completed", "assemble": "Evidence assembled",
          "synthesize": "Source-bound draft generated", "critic": "Semantic review policy",
          "verify": "Deterministic release checks", "revise": "Bounded revision",
          "finalize": "Release decision", "short_circuit": "Governed boundary applied"}


def safe_reason(code, mode):
    """Closed public categories; unknown private exception strings are never echoed."""
    code = str(code).upper()
    if "REVIEW" in code and ("UNAVAILABLE" in code or "TIMEOUT" in code):
        return "REQUIRED_REVIEW_UNAVAILABLE" if mode != "FULL" else "SEMANTIC_REVIEW_UNAVAILABLE"
    if "VERIF" in code: return "VERIFICATION_FAILURE"
    if "SEMANTIC" in code or "CRITIC" in code: return "SEMANTIC_SAFETY"
    if "EVIDENCE" in code or "COMPLETENESS" in code or "INCOMPLETE" in code: return "INSUFFICIENT_EVIDENCE"
    if "SUBSET" in code or "PARTIAL" in code: return "SUPPORTED_SUBSET"
    if "WORKFLOW" in code or "PROVIDER" in code or "BUDGET" in code: return "WORKFLOW_UNAVAILABLE"
    return "CLARIFICATION_REQUIRED" if mode == "CLARIFICATION" else "WORKFLOW_UNAVAILABLE"


def project_v2(graph, brief):
    if getattr(graph, "mode", None) != "bounded_agents_v2": return None
    record = graph.release_record
    if record is None: raise ValueError("Missing authoritative v2 release record")
    mode = record.release_mode.value
    ids = [c.claim_id for c in brief.claims]
    if ids != list(record.released_claim_ids): raise ValueError("Release identities disagree")
    if mode in {"FULL", "PARTIAL"} and (brief.verification is None or
        brief.verification.verdict.value != "PASS" or brief.verification.verification_id != record.verification_id):
        raise ValueError("Release verification disagrees")
    state = getattr(graph, "last_state", {}) or graph.last_observed_state
    trace = graph.agent_trace
    provider = graph.provider
    rows = getattr(provider, "records", None)
    if isinstance(rows, list) and all(isinstance(r.get("generation_started"), bool) for r in rows):
        invoked = [r["role"] for r in rows if r["generation_started"]]
        count, basis = len(invoked), "PROVIDER_REQUESTS"
    elif provider.name == "deterministic_fake":
        # Fixture invocation has no network/preflight; count simulated role dispatches,
        # including injected generation failures, not successful-output count alone.
        invoked = [e.role for e in trace if e.status.value == "Running" and e.tool_requested is None and e.role.split('.')[0] in ROLES]
        count, basis = len(invoked), "OFFLINE_SIMULATION"
    else:
        invoked, count, basis = [], None, "UNKNOWN"
    roles = list(dict.fromkeys(ROLES[r.split('.')[0]] for r in invoked if r.split('.')[0] in ROLES))
    cached = any(e.role == "evidence" and e.action == "existing_eligible_documentary_coverage" for e in trace)
    executed = any(e.role == "evidence" and e.status.value == "Running" and e.tool_requested == "governed.retrieve" for e in trace)
    retriever = graph.knowledge_tool.retriever
    backend = "PGVECTOR" if isinstance(retriever, PgVectorRetriever) else "LOCAL" if isinstance(retriever, GovernedRetriever) else "UNKNOWN"
    embedding = getattr(retriever, "embedding_provider", None) or getattr(getattr(retriever, "vector", None), "provider", None)
    outcome = next((e.critic_outcome.value for e in reversed(trace) if e.role == "critic" and e.critic_outcome), None)
    review = "UNAVAILABLE" if graph.review_unavailable else {"approve": "PASS", "revise": "REVISE", "reject": "BLOCK"}.get(
        outcome, "NOT_INVOKED" if not graph.roles.get("critic") else "UNKNOWN")
    codes = list(dict.fromkeys(safe_reason(c, mode) for c in record.reason_codes))
    if any(e.failure_kind and e.failure_kind.value == "INSUFFICIENT_EVIDENCE" for e in trace):
        codes = ["INSUFFICIENT_EVIDENCE"]
    if graph.review_unavailable:
        code = "REQUIRED_REVIEW_UNAVAILABLE" if graph.critic_needed else "SEMANTIC_REVIEW_UNAVAILABLE"
        if code not in codes: codes.append(code)
    if not codes and mode in {"WITHHELD", "CLARIFICATION"}:
        codes = [safe_reason(brief.refusal_reason or "", mode)]
    if mode == "WITHHELD" and brief.route.value == "UNSUPPORTED": codes = ["UNSUPPORTED_REQUEST"]
    draft = graph.verified_draft or state.get("draft")
    withheld = [c for c in draft.claims if c.claim_id in record.withheld_claim_ids] if draft else []
    components = list(dict.fromkeys("Analytical findings" if c.value is not None else
        "Semantic interpretation" if c.claim_type.value == "INTERPRETATION" else "Documentary explanation" for c in withheld))
    if mode == "PARTIAL" and not components:
        components = ["Documentary explanation"] if graph.review_unavailable and brief.claims and all(c.value is not None for c in brief.claims) else ["Supported findings"]
    product = V2ProductSummary(release_mode=mode, verification_status=record.verification_status,
        review_status=review, review_required=graph.critic_needed, provider_generation_count=count,
        generation_count_basis=basis, retrieval_used=executed, retrieval_backend=backend if executed or cached else "NONE",
        retrieval_mode="EXECUTED" if executed else "CACHED" if cached else "NONE",
        embedding_model=getattr(embedding, "model_name", None) if executed or cached else None,
        fixture_mode=graph.fixture_mode, agent_roles_used=roles, limitations=list(brief.limitations),
        reason_codes=codes, released_claim_ids=ids, withheld_components=components)
    terminal = [e for e in trace if e.role.startswith("stage.") and e.role[6:] in STAGES and e.status.value not in {"Running", "Planned"}]
    stages = [ExecutionStage(order=i+1, label=STAGES[e.role[6:]],
        status="skipped" if e.role == "stage.critic" and review == "NOT_INVOKED" else
        "failed" if e.role == "stage.critic" and review == "UNAVAILABLE" else
        "completed" if e.status.value == "Completed" else "skipped" if e.status.value == "Skipped" else "failed",
        duration_ms=e.duration_ms) for i, e in enumerate(terminal)]
    return {"product": product, "stages": stages, "analytics_used": bool(graph.observations),
            "revision_used": any(e.role in {"stage.revise", "completion.repair"} and e.status.value == "Completed" for e in trace),
            "verifier_interventions": sum((e.role in {"stage.revise", "release.subset", "completion.repair"} and e.status.value == "Completed") or
                (e.role == "release" and e.status.value == "Blocked") for e in trace)}
