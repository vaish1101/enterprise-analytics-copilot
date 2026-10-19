from __future__ import annotations

import asyncio
from collections import Counter
import os
from pathlib import Path
import re
from threading import Lock
import time
from typing import Callable

from src.llm.fake_provider import DeterministicFakeProvider
from src.llm.provider import provider_from_environment
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import ClaimSupport, WorkflowStatus
from src.persistence.checkpoint_store import CheckpointStore
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import GovernedRetriever, build_default_retriever, build_pgvector_retriever
from src.retrieval.embeddings import SEMANTIC_EMBEDDING_MODEL
from src.retrieval.vector_store import PgVectorStore

from .errors import ProductError
from .catalog import product_catalog
from .presentation import governed_numbers
from .schemas import (
    CitationResponse, ClaimResponse, ExecutionStage, ExecutionSummary, ProvenanceCount,
    QueryResponse, VerificationResponse,
)
from .sessions import SessionStore
from .settings import AppSettings, ROOT
from .v2_product import project_v2


STAGE_LABELS = {
    "supervisor.plan": "Question classified",
    "supervisor.route": "Governed route selected",
    "analytics_agent": "Deterministic analytics executed",
    "knowledge_agent": "Document evidence retrieved",
    "evidence_assembly": "Evidence assembled",
    "synthesis_agent": "Structured draft generated",
    "synthesis_agent.revise": "Draft revised after verification",
    "verifier_agent": "Independent verification completed",
    "safe_failure": "Workflow failed safely",
}


class GraphService:
    def __init__(self, settings: AppSettings, *, graph_factory: Callable[[], EnterpriseAnalyticsGraph] | None = None,
                 session_store: SessionStore | None = None,
                 request_scoped_graph_factory: Callable[[], EnterpriseAnalyticsGraph] | None = None):
        if graph_factory is not None and request_scoped_graph_factory is not None:
            raise ValueError("Choose cached or request-scoped graph factory, not both")
        self.settings = settings
        self.graph_factory = graph_factory
        self.request_scoped_graph_factory = request_scoped_graph_factory
        self.sessions = session_store or SessionStore(None if settings.is_test else settings.session_db_path)
        self._graph: EnterpriseAnalyticsGraph | None = None
        self._checkpoint: CheckpointStore | None = None
        self._lock = Lock()

    def _build_graph(self) -> EnterpriseAnalyticsGraph:
        if self.graph_factory:
            return self.graph_factory()
        units = [] if self.settings.public_demo else [
            EvidenceUnit.model_validate_json(line)
            for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        if self.settings.public_demo:
            # Explicit numerical-only demo: no substituted documentary authority.
            retriever = GovernedRetriever([], root=ROOT)
        elif self.settings.retrieval_backend == "pgvector":
            if not self.settings.database_url:
                raise RuntimeError("DATABASE_URL is required when RETRIEVAL_BACKEND=pgvector")
            retriever = build_pgvector_retriever(units, dsn=self.settings.database_url, root=ROOT)
        elif self.settings.retrieval_backend == "local":
            retriever = build_default_retriever(units, root=ROOT)
        else:
            raise RuntimeError("RETRIEVAL_BACKEND must be local or pgvector")
        provider = DeterministicFakeProvider() if self.settings.is_test or self.settings.public_demo else provider_from_environment(allow_fake=False)
        if self._checkpoint is None:
            self._checkpoint = CheckpointStore(mode=self.settings.checkpoint_backend, uri=self.settings.checkpoint_uri)
        return EnterpriseAnalyticsGraph(
            ROOT, provider=provider, retriever=retriever, retrieval_method="dense",
            max_provider_attempts=int(os.getenv("LLM_MAX_RETRIES", "2")), checkpoint_store=self._checkpoint,
        )

    @property
    def graph(self) -> EnterpriseAnalyticsGraph:
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    async def query(self, question: str, request_id: str, session_id: str | None) -> QueryResponse:
        sid = session_id or self.sessions.new_id()
        effective_question = self._resolve_followup(question, sid)
        started = time.perf_counter()
        try:
            execution_result = await asyncio.wait_for(
                asyncio.to_thread(self._run_locked, effective_question, request_id, sid),
                timeout=self.settings.request_timeout_seconds,
            )
        except TimeoutError as error:
            raise ProductError(504, "REQUEST_TIMEOUT", "The governed workflow exceeded its bounded request timeout.") from error
        except ProductError:
            raise
        except Exception as error:
            raise ProductError(503, "WORKFLOW_UNAVAILABLE", "The governed workflow is temporarily unavailable.") from error
        result, evidence = execution_result[:2]
        v2 = execution_result[2] if len(execution_result) == 3 else None
        response = self._response(result, evidence, request_id, sid, (time.perf_counter() - started) * 1000, v2=v2)
        self.sessions.append(sid, {
            "request_id": request_id, "question": question, "status": response.status,
            "resolved_question": effective_question, "route": response.route, "answer": response.answer,
        })
        return response

    def _resolve_followup(self, question: str, session_id: str) -> str:
        """Resolve only a narrow, explicit Mercedes scope follow-up.

        This product-layer helper never infers a metric, period, company, or
        analytical operation. It reuses a previously governed complete question
        and swaps one explicitly named supported scope. Everything else goes to
        the locked planner unchanged for clarification/refusal.
        """
        match = re.fullmatch(
            r"\s*(?:(?:what|how)\s+(?:about|abt)|and)\s+"
            r"(cars|vans|financial\s+services|mobility)\s*[?.!]*\s*",
            question, flags=re.IGNORECASE,
        )
        if not match:
            return question
        history = self.sessions.get(session_id)
        if not history or history[-1].get("status") != "COMPLETED":
            return question
        previous = history[-1].get("resolved_question") or history[-1].get("question", "")
        if "mercedes" not in previous.lower():
            return question
        replacement = {
            "cars": "Cars", "vans": "Vans",
            "financial services": "Financial Services", "mobility": "Mobility",
        }[re.sub(r"\s+", " ", match.group(1).lower())]
        scope_pattern = re.compile(r"\b(Cars|Vans|Financial\s+Services|Mobility)\b", re.IGNORECASE)
        if not scope_pattern.search(previous):
            return question
        return scope_pattern.sub(replacement, previous, count=1)

    def _run_locked(self, question: str, request_id: str, session_id: str):
        with self._lock:
            # A session groups safe interaction history. Each question receives a
            # fresh graph checkpoint thread so a completed state can never be
            # resumed for a different question in that session.
            graph = self.request_scoped_graph_factory() if self.request_scoped_graph_factory else self.graph
            result = graph.run(question, question_id=request_id, thread_id=request_id)
            state = getattr(graph, "last_state", {}) or getattr(graph, "last_observed_state", {})
            evidence = state.get("evidence")
            projection = project_v2(graph, result)
            # Preserve the existing default helper contract. Experimental
            # request-scoped results carry their own projection, never shared state.
            return (result, evidence, projection) if projection else (result, evidence)

    def _response(self, result, evidence, request_id: str, session_id: str, latency_ms: float, *, v2=None) -> QueryResponse:
        claims = [ClaimResponse(
            claim_id=item.claim_id, provenance=item.claim_type.value, text=item.text,
            company_id=item.company_id, metric_id=item.metric_id, business_scope=item.business_scope,
            periods=list(item.periods), value=str(item.value) if item.value is not None else None,
            unit=item.unit, fact_ids=list(item.fact_ids), calculation_run_ids=list(item.calculation_run_ids),
            evidence_ids=list(item.evidence_ids),
        ) for item in result.claims]
        retrieved = {
            item.evidence_unit_id: item
            for item in (evidence.retrieval.results if evidence and evidence.retrieval else ())
        }
        citations = []
        for item in result.citations:
            source = retrieved.get(item.evidence_unit_id)
            citations.append(CitationResponse(
                evidence_unit_id=item.evidence_unit_id, source_id=item.source_id,
                source_title=item.source_title, official_url=item.official_url,
                page_number=item.page_number, citation=item.citation,
                company_id=source.company_id if source else None,
                evidence_type=source.evidence_unit_type.value if source else None,
                section=source.section if source else None,
            ))
        counts = Counter(item.provenance for item in claims)
        verification = None
        product = v2["product"] if v2 else None
        if result.verification:
            supported = sum(check.support is ClaimSupport.SUPPORTED for check in result.verification.claim_checks)
            partial = product.release_mode == "PARTIAL" if product else result.status is WorkflowStatus.COMPLETED and supported < len(result.verification.claim_checks)
            label = "Supported subset returned" if partial else (
                "Verified" if result.verification.verdict.value == "PASS" else "Verified with limitations"
            )
            errors = sorted({error for check in result.verification.claim_checks for error in check.errors} | set(result.verification.errors))
            verification = VerificationResponse(
                verdict=result.verification.verdict.value, label=label,
                supported_claims=supported, total_claims=len(result.verification.claim_checks), errors=errors,
            )
        stages = [ExecutionStage(
            order=index, label=STAGE_LABELS.get(event.node, "Governed step completed"),
            status="failed" if event.event == "failed" else "completed",
            duration_ms=round(event.duration_ms, 2),
        ) for index, event in enumerate(result.trace, start=1) if event.node in STAGE_LABELS]
        provider_events = [event for event in result.trace if event.provider_call]
        verifier_events = [event for event in result.trace if event.node == "verifier_agent"]
        analytics_used = any(event.node == "analytics_agent" for event in result.trace)
        retrieval_used = any(event.node == "knowledge_agent" for event in result.trace)
        execution = ExecutionSummary(
            analytics_used=analytics_used, retrieval_used=retrieval_used,
            revision_used=any(event.node == "synthesis_agent.revise" for event in result.trace),
            provider_calls=len(provider_events), verifier_interventions=max(0, len(verifier_events) - 1),
            input_tokens=result.total_usage.input_tokens, output_tokens=result.total_usage.output_tokens,
            cost_usd=str(result.total_usage.estimated_cost_usd),
            stages=stages,
        )
        analytics, fact_sources = governed_numbers(result, evidence, claims, product_catalog(ROOT))
        # A checked numerical seed is not a release certificate for a refused answer.
        if result.status is not WorkflowStatus.COMPLETED and verification and verification.verdict == 'PASS':
            verification = None
        if product:
            if product.release_mode == "WITHHELD" and verification:
                verification = verification.model_copy(update={"label": "Answer withheld"})
            execution = execution.model_copy(update={
                "provider_calls": product.provider_generation_count,
                "retrieval_used": product.retrieval_used, "analytics_used": v2["analytics_used"],
                "revision_used": v2["revision_used"], "verifier_interventions": v2["verifier_interventions"],
                "stages": v2["stages"],
            })
            if verification:
                verification = verification.model_copy(update={"errors": ["VERIFICATION_FAILURE"] if verification.errors else []})
        return QueryResponse(
            request_id=request_id, session_id=session_id, status=result.status.value,
            route=result.route.value, answer=result.answer, claims=claims, citations=citations,
            limitations=list(result.limitations), verification=verification,
            provenance_summary=[ProvenanceCount(provenance=key, count=value) for key, value in sorted(counts.items())],
            execution=execution, latency_ms=round(latency_ms, 2), provider=result.provider_name,
            model=result.provider_model, clarification_question=result.clarification_question,
            refusal_reason=",".join(product.reason_codes) or None if product else result.refusal_reason,
            product=product,
            analytics=analytics, fact_sources=fact_sources,
        )

    def readiness(self) -> list[dict]:
        model_cache = ROOT / "data/retrieval/local/model_cache"
        model_files = list(model_cache.glob("models--sentence-transformers--all-MiniLM-L6-v2/snapshots/*/model.safetensors"))
        provider_ready = self.settings.is_test or self.settings.public_demo or self._provider_configured()
        checkpoint_ready, checkpoint_detail = self._checkpoint_ready()
        session_ready, session_detail = self.sessions.ready()
        vector_ready, vector_detail = self._vector_ready()
        return [
            {"name": "catalog", "ready": (ROOT / "config/metric_catalog.csv").is_file(), "detail": "governed metric catalog"},
            {"name": "facts", "ready": (ROOT / "data/normalized/facts.csv").is_file(), "detail": "normalized numerical authority"},
            {"name": "retrieval", "ready": self.settings.public_demo or ((ROOT / "data/retrieval/local/evidence_units.jsonl").is_file() and bool(model_files)), "detail": "disabled: public numerical-only demo; document questions refuse" if self.settings.public_demo else "MiniLM dense top-5 assets"},
            {"name": "vector_store", "ready": vector_ready, "detail": vector_detail},
            {"name": "provider", "ready": provider_ready, "detail": "deterministic fake provider; no live LLM" if self.settings.public_demo else "configured without making a paid call"},
            {"name": "checkpoint", "ready": checkpoint_ready, "detail": checkpoint_detail},
            {"name": "session", "ready": session_ready, "detail": session_detail},
        ]

    def _vector_ready(self) -> tuple[bool, str]:
        if self.settings.public_demo:
            return True, "disabled: public numerical-only demo"
        if self.settings.retrieval_backend == "local":
            return True, "local MiniLM cosine store"
        if self.settings.retrieval_backend != "pgvector" or not self.settings.database_url:
            return False, "pgvector backend invalid or DATABASE_URL missing"
        try:
            status = PgVectorStore(
                self.settings.database_url, embedding_model=SEMANTIC_EMBEDDING_MODEL,
            ).readiness()
            expected = sum(
                1 for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            )
            ready = bool(
                status["pgvector_version"] and status["hnsw_present"]
                and status["evidence_count"] == expected
                and status["embedding_count"] == expected
            )
            return ready, (
                f"pgvector {status['pgvector_version']}; evidence={status['evidence_count']}; "
                f"embeddings={status['embedding_count']}; hnsw={status['hnsw_present']}"
            )
        except Exception:
            return False, "pgvector unavailable"

    def _provider_configured(self) -> bool:
        required = ("LLM_PROVIDER", "LLM_MODEL", "OPENAI_API_KEY", "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES")
        if not all(os.getenv(name) for name in required) or os.getenv("LLM_PROVIDER") != "openai":
            return False
        try:
            return float(os.environ["LLM_TIMEOUT_SECONDS"]) > 0 and int(os.environ["LLM_MAX_RETRIES"]) >= 0
        except ValueError:
            return False

    def _checkpoint_ready(self) -> tuple[bool, str]:
        mode = self.settings.checkpoint_backend
        if mode == "memory":
            return self.settings.is_test, "memory (test-only)" if self.settings.is_test else "memory is not production-ready"
        if mode == "sqlite":
            try:
                path = Path(self.settings.checkpoint_uri)
                return path.parent.is_dir() and os.access(path.parent, os.W_OK), "sqlite writable path"
            except (OSError, TypeError):
                return False, "sqlite unavailable"
        if mode == "postgres" and self.settings.checkpoint_uri:
            try:
                import psycopg
                with psycopg.connect(self.settings.checkpoint_uri, connect_timeout=2) as connection:
                    connection.execute("SELECT 1").fetchone()
                return True, "postgres reachable"
            except Exception:
                return False, "postgres unavailable"
        return False, "checkpoint backend invalid or unconfigured"

    def close(self) -> None:
        self.sessions.close()
        if self._checkpoint:
            self._checkpoint.close()
