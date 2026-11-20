import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from swagger_ui_bundle import swagger_ui_path

from app.api import ingestion, monitoring, stations
from app.core.config import Settings
from app.core.logging import log
from app.core.public import ReadCache, RequestBudget
from app.core.security import check_peer
from app.db.session import build_engine, check_database, get_session
from app.schemas import PublicError

Role = Literal["development", "ingest", "public"]


def create_app(settings: Settings | None = None, *, role: Role | None = None) -> FastAPI:
    settings = settings or Settings()
    if role is None:
        role = "public" if settings.app_env == "production" else "development"
    public = role == "public"
    development = role == "development"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = build_engine(settings.database_url, busy_timeout_ms=settings.sqlite_busy_timeout_ms,
                              read_only=public, existing_only=not development)
        app.state.engine = engine
        log("server_started", service=role, database=engine.dialect.name)
        try:
            with Session(engine) as db:
                check_database(db)
            log("database_ready")
        except SQLAlchemyError as exc:
            log("database_unavailable", level=logging.ERROR, error=type(exc).__name__)
        try:
            yield
        finally:
            engine.dispose()

    errors = {
        404: {"model": PublicError, "description": "Recurso ausente"},
        422: {"model": PublicError, "description": "Parâmetros ou limites inválidos"},
        429: {"model": PublicError, "description": "Limite de requisições por minuto atingido"},
        503: {"model": PublicError, "description": "Banco indisponível"},
    }
    app = FastAPI(title="API meteorológica WS-2000", version="0.2.0", lifespan=lifespan,
                  responses=errors if public else None,
                  docs_url=None, redoc_url=None, openapi_url="/openapi.json" if development else None)
    app.state.settings = settings
    app.state.public = public
    if development:
        app.mount("/docs-assets", StaticFiles(directory=swagger_ui_path), name="swagger_assets")

        @app.get("/docs", include_in_schema=False)
        def swagger():
            return get_swagger_ui_html(
                openapi_url="/openapi.json", title=app.title,
                swagger_js_url="/docs-assets/swagger-ui-bundle.js",
                swagger_css_url="/docs-assets/swagger-ui.css",
                swagger_favicon_url="/docs-assets/favicon-32x32.png",
                swagger_ui_parameters={"validatorUrl": None},
            )

    logging.getLogger("uvicorn.access").disabled = True
    if public:
        app.state.cache = ReadCache()
        budget = RequestBudget(settings.public_requests_per_minute, settings.public_total_per_minute)

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        if public and not budget.allow(request.client.host if request.client else "unknown"):
            response = JSONResponse({"detail": "Limite de requisições atingido"}, status_code=429,
                                    headers={"Retry-After": "60"})
        elif public and len(request.scope["query_string"]) > settings.max_query_bytes:
            response = JSONResponse({"detail": "Query excede o limite"}, status_code=414)
        else:
            response = await call_next(request)
        if public:
            response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        log("http_request", service=role, method=request.method, route=getattr(route, "path", None),
            status=response.status_code)
        return response

    if role != "ingest":
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"],
                           expose_headers=["Retry-After", "Content-Disposition"])

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        log("database_error", level=logging.ERROR, error=type(exc).__name__)
        return JSONResponse({"detail": "Banco de dados indisponível"}, status_code=503)

    if public:
        @app.exception_handler(RequestValidationError)
        async def invalid_request(request: Request, exc: RequestValidationError):
            return JSONResponse({"detail": "Parâmetros de consulta inválidos"}, status_code=422)

        @app.exception_handler(Exception)
        async def unexpected_error(request: Request, exc: Exception):
            log("service_error", level=logging.ERROR, error=type(exc).__name__)
            return JSONResponse({"detail": "Falha interna no serviço"}, status_code=500)

        app.include_router(monitoring.public)
        app.include_router(stations.public_exports)
    else:
        internal_access = [Depends(check_peer)] if role == "ingest" else []

        @app.get("/health", tags=["Serviço"], dependencies=internal_access)
        def health():
            return {"status": "ok"}

        @app.get("/ready", tags=["Serviço"], dependencies=internal_access)
        def ready(db: Annotated[Session, Depends(get_session)]):
            check_database(db)
            return {"status": "ready"}

        app.include_router(ingestion.router)
        app.include_router(monitoring.internal, dependencies=internal_access)

    if development:
        app.include_router(stations.router)
    if role != "ingest":
        app.include_router(stations.observations)
    return app


def create_ingest_app() -> FastAPI:
    return create_app(role="ingest")


def create_public_app() -> FastAPI:
    return create_app(role="public")


app = create_app()
