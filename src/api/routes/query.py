import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from ..errors import ProductError
from ..schemas import QueryRequest, QueryResponse


router = APIRouter(prefix="/api/v1", tags=["query"])
# Route structured product telemetry through Uvicorn's configured logger tree so
# container runtimes receive the record without enabling noisy third-party logs.
LOGGER = logging.getLogger("uvicorn.error.enterprise_analytics.query")


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, request: Request) -> QueryResponse:
    settings = request.app.state.settings
    if len(payload.question) > settings.max_question_length:
        raise ProductError(413, "QUESTION_TOO_LONG", f"Questions are limited to {settings.max_question_length} characters.")
    request_id = getattr(request.state, "request_id", f"request_{uuid4().hex[:20]}")
    result = await request.app.state.graph_service.query(payload.question, request_id, payload.session_id)
    request.app.state.metrics.record(result)
    LOGGER.info(json.dumps({
        "event": "governed_query", "request_id": result.request_id, "route": result.route,
        "status": result.status, "provider": result.provider, "model": result.model,
        "duration_ms": result.latency_ms,
        "verifier_verdict": result.verification.verdict if result.verification else None,
        "provider_calls": result.execution.provider_calls,
        "revision_used": result.execution.revision_used,
        "input_tokens": result.execution.input_tokens,
        "output_tokens": result.execution.output_tokens,
        "estimated_cost_usd": result.execution.cost_usd,
    }, sort_keys=True))
    return result
