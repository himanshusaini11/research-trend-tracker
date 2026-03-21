from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import close_redis
from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.core.metrics import setup_metrics
from app.api.routers import graph, health, papers, summarize, trends

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("startup", app_env=settings.app_env, version=app.version)
    yield
    await close_redis()
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="arXiv research trend tracker with time-series analytics and LLM summarization",
    debug=settings.debug,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
origins = (
    ["*"]
    if settings.app_env == "development"
    else ["http://localhost:3001"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
setup_metrics(app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/health")
app.include_router(papers.router, prefix="/api/v1/papers")
app.include_router(trends.router, prefix="/api/v1/trends")
app.include_router(summarize.router, prefix="/api/v1/summarize")
app.include_router(graph.router, prefix="/graph")
