from fastapi import APIRouter, Request

from ..metadata import product_metadata
from ..schemas import MetadataResponse, MetricsResponse


router = APIRouter(prefix="/api/v1", tags=["metadata"])


@router.get("/metadata", response_model=MetadataResponse)
def metadata(request: Request) -> MetadataResponse:
    return product_metadata(request.app.state.settings)


@router.get("/metrics", response_model=MetricsResponse)
def metrics(request: Request) -> MetricsResponse:
    if request.app.state.settings.is_demo:
        from ..errors import ProductError
        raise ProductError(404, "NOT_FOUND", "This endpoint is disabled in demo mode.")
    return MetricsResponse(**request.app.state.metrics.snapshot())
