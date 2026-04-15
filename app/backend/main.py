"""FastAPI application factory with lifespan for resource management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.router import api_router
from .models.schemas import HealthResponse, ReadinessResponse
from .services.config import get_settings
from .services.database import dispose_engine, get_engine, init_db
from .services.qdrant_client import close_qdrant, ensure_collection, get_qdrant_client

logger = logging.getLogger(__name__)


async def _run_alembic_upgrade() -> None:
    """Run Alembic migrations on startup to ensure schema is current.

    For production with multiple API instances, run migrations separately
    via ``alembic upgrade head`` before deploying. The auto-upgrade runs
    Alembic in a subprocess to avoid event-loop conflicts (Alembic's
    async env.py calls ``asyncio.run()`` internally).

    The create_all fallback is only for local development without Alembic
    and is gated behind the CREATE_ALL_FALLBACK env var to prevent
    accidental use in production.
    """
    import os
    import subprocess
    import sys

    try:
        # Run Alembic in a subprocess to avoid asyncio.run() conflicts.
        # This is safe for both sync and async Alembic env.py configurations.
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        ini_path = os.path.join(backend_dir, "alembic.ini")

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", ini_path, "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("alembic_migrations_applied")
        else:
            logger.warning(
                "alembic_upgrade_returned_nonzero rc=%d stdout=%s stderr=%s",
                result.returncode, result.stdout[:200], result.stderr[:200],
            )
            raise RuntimeError(f"alembic upgrade failed: {result.stderr[:200]}")
    except Exception as e:
        logger.warning("alembic_migration_skipped error=%s", e)

        # create_all fallback: only allowed when explicitly enabled.
        if os.environ.get("CREATE_ALL_FALLBACK", "").lower() not in ("1", "true", "yes"):
            logger.error(
                "alembic_migration_failed_and_no_fallback. "
                "Set CREATE_ALL_FALLBACK=1 for local dev, or run "
                "'alembic upgrade head' manually before starting the API."
            )
            raise

        from .models import Base
        from .services.database import get_engine
        engine = get_engine()
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("tables_created_via_create_all")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, clean up on shutdown."""
    settings = get_settings()
    init_db(settings)
    app.state.settings = settings
    logger.info("database_initialized")

    # Run schema migrations
    await _run_alembic_upgrade()

    try:
        await ensure_collection()
        logger.info("qdrant_collection_ready")
    except Exception as e:
        logger.warning("qdrant_init_failed error=%s", e)

    yield

    await close_qdrant()
    logger.info("qdrant_closed")
    await dispose_engine()
    logger.info("database_disposed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="RAG Knowledge Base",
        description="Modular RAG knowledge base platform with grounded answers and citations",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router)

    # Health endpoints
    _register_health_endpoints(app)

    # Metrics endpoint
    _register_metrics_endpoints(app)

    return app


def _register_health_endpoints(app: FastAPI) -> None:
    """Register health and readiness endpoints."""

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness check."""
        return HealthResponse(status="healthy", version="0.1.0")

    @app.get("/health/ready", response_model=ReadinessResponse)
    async def readiness() -> JSONResponse:
        """Readiness check verifying postgres and qdrant connectivity."""
        pg_ok = False
        qdrant_ok = False

        try:
            engine = get_engine()
            if engine is not None:
                async with engine.connect() as conn:
                    await conn.execute(
                        __import__("sqlalchemy").text("SELECT 1")
                    )
                pg_ok = True
        except Exception as e:
            logger.warning("postgres_health_check_failed error=%s", e)

        try:
            client = await get_qdrant_client()
            await client.get_collections()
            qdrant_ok = True
        except Exception as e:
            logger.warning("qdrant_health_check_failed error=%s", e)

        status = "healthy" if (pg_ok and qdrant_ok) else "unhealthy"
        response = ReadinessResponse(
            status=status, postgres=pg_ok, qdrant=qdrant_ok
        )

        if status == "unhealthy":
            return JSONResponse(
                content=response.model_dump(), status_code=503
            )
        return JSONResponse(content=response.model_dump(), status_code=200)


def _register_metrics_endpoints(app: FastAPI) -> None:
    """Register metrics and monitoring endpoints."""
    from fastapi import Response

    from .services.metrics import get_metrics

    @app.get("/metrics")
    async def metrics() -> Response:
        """Prometheus-compatible metrics endpoint."""
        metrics_collector = get_metrics()
        content = metrics_collector.get_prometheus_metrics()
        return Response(content=content, media_type="text/plain")

    @app.get("/health/detailed")
    async def health_detailed() -> JSONResponse:
        """Detailed health status with metrics."""
        metrics_collector = get_metrics()

        pg_ok = False
        qdrant_ok = False
        qdrant_points = 0

        # Check PostgreSQL
        try:
            engine = get_engine()
            if engine is not None:
                async with engine.connect() as conn:
                    await conn.execute(
                        __import__("sqlalchemy").text("SELECT 1")
                    )
                pg_ok = True
        except Exception as e:
            logger.warning("postgres_health_check_failed error=%s", e)

        # Check Qdrant
        try:
            client = await get_qdrant_client()
            await client.get_collections()
            qdrant_ok = True
            # Get point count if collection exists
            try:
                collection_info = await client.get_collection("rag_kb_chunks")
                qdrant_points = collection_info.points_count
            except Exception:
                pass
        except Exception as e:
            logger.warning("qdrant_health_check_failed error=%s", e)

        return JSONResponse(content={
            "status": "healthy" if (pg_ok and qdrant_ok) else "unhealthy",
            "postgres": pg_ok,
            "qdrant": qdrant_ok,
            "qdrant_points": qdrant_points,
            "uptime_seconds": int(metrics_collector.get_uptime_seconds()),
            "requests": metrics_collector.get_request_summary(),
            "jobs": metrics_collector.get_job_summary(),
        })


app = create_app()