from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .errors import ProductError, product_error_handler, safe_exception_handler
from .observability import MetricsStore
from .rate_limit import SlidingWindowLimiter
from .routes.health import router as health_router
from .routes.metadata import router as metadata_router
from .routes.query import router as query_router
from .routes.sessions import router as sessions_router
from .service import GraphService
from .settings import AppSettings, ROOT


LOGGER = logging.getLogger("enterprise_analytics.api")


def create_app(*, settings: AppSettings | None = None, graph_service: GraphService | None = None) -> FastAPI:
    selected = settings or AppSettings.from_environment()
    service = graph_service or GraphService(selected)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        service.close()

    app = FastAPI(
        title="Enterprise Analytics Copilot API", version=selected.system_version,
        description="Governed KPI analysis with deterministic numerical authority and verified evidence.",
        docs_url=None if selected.is_demo else "/docs", redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = selected
    app.state.graph_service = service
    app.state.metrics = MetricsStore()
    app.state.rate_limiter = SlidingWindowLimiter(selected.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware, allow_origins=list(selected.cors_origins), allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-Session-ID"],
    )
    app.add_exception_handler(ProductError, product_error_handler)
    app.add_exception_handler(Exception, safe_exception_handler)

    @app.middleware("http")
    async def request_controls(request: Request, call_next):
        request.state.request_id = f"request_{uuid4().hex[:20]}"
        started = time.perf_counter()
        response = None
        if request.url.path == "/api/v1/query" and request.method == "POST":
            client = request.client.host if request.client else "unknown"
            # Transport peer only: session IDs and forwarding headers are not identities.
            if not app.state.rate_limiter.allow(client):
                response = JSONResponse(
                    status_code=429,
                    content={"error": {"code": "RATE_LIMITED", "message": "The demo request limit has been reached. Try again shortly.", "request_id": request.state.request_id}},
                )
        if response is None:
            response = await call_next(request)
        if request.url.path == "/api/v1/query" and response.status_code >= 400:
            app.state.metrics.record_error()
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        if selected.is_demo:
            response.headers["Cache-Control"] = "no-store"
        LOGGER.info(json.dumps({
            "event": "http_request", "request_id": request.state.request_id,
            "method": request.method, "path": request.url.path, "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }, sort_keys=True))
        return response

    app.include_router(health_router)
    app.include_router(query_router)
    app.include_router(metadata_router)
    app.include_router(sessions_router)

    frontend = ROOT / "frontend/dist"
    if frontend.is_dir():
        assets = frontend / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/", include_in_schema=False)
        def product_home():
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
