from fastapi import APIRouter, Request, Response

from ..schemas import HealthResponse, ReadinessCheck, ReadinessResponse


router = APIRouter(tags=["operations"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(status="healthy", version=request.app.state.settings.system_version)


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request, response: Response) -> ReadinessResponse:
    checks = [ReadinessCheck(**item) for item in request.app.state.graph_service.readiness()]
    is_ready = all(item.ready for item in checks)
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if is_ready else "not_ready", checks=checks)
