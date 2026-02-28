"""Fixtures específicas para testes de carga RAG."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.models.rag_models import ChunkORM, DocumentORM
from src.rag import EmbeddingService, QueryService

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def load_test_config() -> dict[str, Any]:
    """Configurações para testes de carga."""
    return {
        "concurrent_users": 50,
        "ramp_up_time": 10,  # segundos
        "test_duration": 60,  # segundos
        "queries_per_user": 10,
        "baseline_queries": 100,
        "sustained_load_users": 20,
        "sustained_load_duration": 300,  # 5 minutos
        "spike_start_users": 10,
        "spike_peak_users": 200,
        "spike_duration": 60,
    }


@pytest.fixture
def load_test_markers():
    """Marcadores para categorização dos testes de carga."""
    return {
        "baseline": "Teste de performance baseline",
        "concurrent": "Teste de usuários concorrentes",
        "sustained": "Teste de carga sustentada",
        "spike": "Teste de pico de usuários",
        "limit": "Teste de limites do sistema",
    }


@pytest_asyncio.fixture
async def load_test_engine():
    """
    Create test database engine for load testing.

    Uses a larger in-memory database for load tests.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all RAG tables
    async with engine.begin() as conn:
        await conn.run_sync(DocumentORM.metadata.create_all)
        await conn.run_sync(ChunkORM.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(DocumentORM.metadata.drop_all)
        await conn.run_sync(ChunkORM.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def load_test_session(load_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create test database session for load testing.

    Provides a clean session with optimized connection pool
    for load tests.
    """
    async_session_maker = sessionmaker(
        load_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def rag_query_service_with_mock_data(
    load_test_session,
    rag_api_key,
) -> AsyncGenerator[QueryService, None]:
    """
    Create QueryService with pre-populated test data.

    This fixture creates a realistic set of legal chunks
    for load testing, avoiding the need for real embeddings.
    """
    import json
    import random

    from src.rag.storage.vector_store import serialize_embedding

    # Create test documents
    documents = []
    random.seed(42)  # Para reprodutibilidade
    for i in range(1, 11):  # 10 documents
        chunks_per_doc = random.randint(50, 150)
        doc = DocumentORM(
            nome=f"Documento Jurídico {i}",
            arquivo_origem=f"doc_{i}.txt",
            chunk_count=chunks_per_doc,
            token_count=random.randint(50000, 150000),
        )
        load_test_session.add(doc)
        documents.append(doc)

    await load_test_session.commit()

    # Create test chunks with mock embeddings in smaller batches
    chunk_count = 0

    for doc in documents:

        for j in range(chunks_per_doc):
            # Create realistic metadata
            meta = {
                "documento": doc.nome,
                "artigo": f"art_{random.randint(1, 100)}" if random.random() > 0.3 else None,
                "tipo": random.choice(["caput", "inciso", "paragrafo", None]),
                "marca_stf": random.random() > 0.8,
                "marca_stj": random.random() > 0.8,
                "marca_concurso": random.random() > 0.7,
            }

            # Create mock embedding (normalized random vector)
            embedding = [random.uniform(-0.1, 0.1) for _ in range(1536)]
            # Normalize
            norm = sum(x**2 for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]

            chunk = ChunkORM(
                id=f"chunk_{doc.id}_{chunk_count}",
                documento_id=doc.id,
                texto=f"Texto jurídico exemplo {chunk_count}. " * 10,
                metadados=json.dumps(meta),
                token_count=random.randint(100, 500),
                embedding=serialize_embedding(embedding),
            )
            load_test_session.add(chunk)
            chunk_count += 1

            # Commit every 50 chunks to avoid SQLite limits
            if chunk_count % 50 == 0:
                await load_test_session.commit()

    # Final commit
    await load_test_session.commit()

    # Create query service with mock embedding service
    from unittest.mock import AsyncMock, patch

    embedding_service = EmbeddingService(api_key=rag_api_key)

    # Mock embed_text to return predictable embeddings
    async def mock_embed_text(text: str) -> list[float]:
        # Deterministic mock embedding based on text hash
        import hashlib

        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        embedding = [random.uniform(-0.1, 0.1) for _ in range(1536)]
        norm = sum(x**2 for x in embedding) ** 0.5
        return [x / norm for x in embedding] if norm > 0 else embedding

    with patch.object(
        embedding_service,
        "embed_text",
        new=AsyncMock(side_effect=mock_embed_text),
    ):
        query_service = QueryService(
            session=load_test_session,
            embedding_service=embedding_service,
        )
        yield query_service


@pytest.fixture
def load_test_report_dir(tmp_path):
    """
    Create temporary directory for load test reports.

    Reports are saved in CSV and JSON formats for analysis.
    """
    report_dir = tmp_path / "load_test_reports"
    report_dir.mkdir(exist_ok=True)
    return report_dir


# Configure pytest markers for load tests
def pytest_configure(config):
    """Add custom marker for load tests."""
    config.addinivalue_line(
        "markers", "load: Load and performance tests (may take > 1 minute)"
    )
    config.addinivalue_line(
        "markers", "rag_load: RAG-specific load tests"
    )
