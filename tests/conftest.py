from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.api.deps import get_db, get_rate_limiter
from app.core.models import Base
from app.core.security import create_access_token
from app.ingestion.schemas import ArxivPaper
from app.main import app


# ---------------------------------------------------------------------------
# Database — session-scoped container + engine, function-scoped session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def test_db_engine():
    with PostgresContainer("postgres:16") as postgres:
        url = postgres.get_connection_url(driver="asyncpg")
        engine = create_async_engine(url, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    conn = await test_db_engine.connect()
    await conn.begin()
    session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()
        await conn.rollback()
        await conn.close()


# ---------------------------------------------------------------------------
# HTTP test client — overrides get_db and get_rate_limiter
# ---------------------------------------------------------------------------

class _AlwaysAllow:
    async def is_allowed(self, _: str) -> bool:
        return True


@pytest_asyncio.fixture(scope="function")
async def test_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db

    async def _override_rate_limiter() -> _AlwaysAllow:
        return _AlwaysAllow()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_rate_limiter] = _override_rate_limiter

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def auth_headers() -> dict[str, str]:
    token = create_access_token({"sub": "test-user"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def sample_paper() -> ArxivPaper:
    return ArxivPaper(
        arxiv_id="2401.00001",
        title="Attention Transformers Deep Learning Neural Networks",
        abstract=(
            "We propose a novel neural network architecture based on attention mechanisms. "
            "The transformer model achieves state-of-the-art results on machine translation tasks. "
            "Our experiments demonstrate superior performance over recurrent neural networks "
            "using gradient descent optimization methods for deep learning applications. "
            "The model leverages multi-head self-attention with positional encodings to capture "
            "long-range dependencies in sequential data representations across multiple domains."
        ),
        authors=["Author One", "Author Two"],
        categories=["cs.AI", "cs.LG"],
        published_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        pdf_url="https://arxiv.org/pdf/2401.00001",
        abs_url="https://arxiv.org/abs/2401.00001",
    )


@pytest.fixture(scope="function")
def sample_papers() -> list[ArxivPaper]:
    categories_cycle = [["cs.AI"], ["cs.LG"], ["cs.CL"], ["stat.ML"], ["cs.AI"]]
    return [
        ArxivPaper(
            arxiv_id=f"2401.{i:05d}",
            title=f"Research Paper {i} neural network deep learning transformer",
            abstract=(
                f"This paper presents research on machine learning models. "
                f"We evaluate transformer architectures and attention mechanisms. "
                f"Paper index {i} covers graph neural network embedding methods "
                f"using gradient descent optimization and backpropagation algorithms "
                f"with convolutional layers for image recognition classification tasks."
            ),
            authors=[f"Author {i}"],
            categories=categories_cycle[i],
            published_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            pdf_url=f"https://arxiv.org/pdf/2401.{i:05d}",
            abs_url=f"https://arxiv.org/abs/2401.{i:05d}",
        )
        for i in range(5)
    ]
