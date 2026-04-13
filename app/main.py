from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import close_redis
from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.core.metrics import setup_metrics
from app.api.routers import admin, auth, graph, health, papers, summarize, trends, upload, user_graph
from app.api.search import router as search_router

from importlib.metadata import version, PackageNotFoundError

setup_logging()
log = get_logger(__name__)

try:
    __version__ = version("research-trend-tracker")  # must match [project] name in pyproject.toml
except PackageNotFoundError:
    __version__ = "0.0.0"

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("startup", app_env=settings.app_env, version=app.version)
    yield
    await close_redis()
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
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
app.include_router(admin.router,   prefix="/api/admin")
app.include_router(auth.router,    prefix="/api/auth")
app.include_router(health.router,  prefix="/health")
app.include_router(papers.router, prefix="/api/v1/papers")
app.include_router(trends.router, prefix="/api/v1/trends")
app.include_router(summarize.router, prefix="/api/v1/summarize")
app.include_router(graph.router,      prefix="/graph")
app.include_router(upload.router,     prefix="/api/upload")
app.include_router(user_graph.router, prefix="/api/user/graph")
app.include_router(search_router)
