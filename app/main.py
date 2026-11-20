import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from swagger_ui_bundle import swagger_ui_path

from app.api import ingestion, stations
from app.core.config import Settings
from app.core.logging import log
from app.db.session import build_engine, check_database, get_session


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = build_engine(settings.database_url)
        app.state.engine = engine
        log("server_started", database=engine.dialect.name)
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

    app = FastAPI(title="API meteorológica WS-2000", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.settings = settings
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

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"])

    # Uvicorn's access logger includes the entire query. Log the route template instead.
    logging.getLogger("uvicorn.access").disabled = True

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        log("http_request", method=request.method, route=getattr(route, "path", None),
            status=response.status_code)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        log("database_error", level=logging.ERROR, error=type(exc).__name__)
        return JSONResponse({"detail": "Banco de dados indisponível"}, status_code=503)

    @app.get("/health", tags=["Serviço"])
    def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["Serviço"])
    def ready(db: Annotated[Session, Depends(get_session)]):
        check_database(db)
        return {"status": "ready"}

    app.include_router(ingestion.router)
    app.include_router(stations.router)
    return app


app = create_app()
