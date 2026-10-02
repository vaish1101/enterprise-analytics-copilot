from fastapi import APIRouter, Request

from ..errors import ProductError
from ..schemas import SessionSummary


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionSummary)
def get_session(session_id: str, request: Request) -> SessionSummary:
    interactions = request.app.state.graph_service.sessions.get(session_id)
    if not interactions:
        raise ProductError(404, "SESSION_NOT_FOUND", "No safe session history exists for this identifier.")
    return SessionSummary(
        session_id=session_id, created_at=interactions[0]["created_at"],
        updated_at=interactions[-1]["created_at"], interaction_count=len(interactions),
        interactions=interactions,
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, request: Request) -> None:
    request.app.state.graph_service.sessions.delete(session_id)
