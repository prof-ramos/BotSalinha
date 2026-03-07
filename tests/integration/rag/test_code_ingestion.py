"""Integration tests for code ingestion in RAG pipeline.

Tests the complete flow from parsing Repomix XML to storing chunks
with embeddings in the database.
"""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_models import ChunkORM, DocumentORM
from src.rag import CodeIngestionService, QueryService
from src.rag.models import Chunk, ChunkMetadata, Document
from src.rag.parser.code_chunker import CodeChunkExtractor
from src.rag.parser.xml_parser import RepomixXMLParser
from src.rag.services.embedding_service import EMBEDDING_DIM
from src.rag.storage.rag_repository import RagRepository

# Test random seed for reproducibility
TEST_RANDOM_SEED = 42

# Sample Repomix XML content with 3 code files
SAMPLE_REPOMIX_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<repomix>
    <file path="src/core/agent.py">
import structlog
from agno.agent import Agent

class AgentWrapper:
    """Wrapper for Agno Agent with conversation history."""

    def __init__(self, repository=None):
        self.agent = Agent(name="BotSalinha")
        self.repository = repository

    def generate_response(self, prompt, conversation_id=None, user_id=None):
        return "Response"
</file>
    <file path="src/storage/sqlite_repository.py">
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

class SQLiteRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    async def create_conversation(self, data):
        pass
</file>
    <file path="src/utils/logger.py">
import structlog

def setup_logging():
    structlog.configure()
</file>
</repomix>
'''


class MockEmbeddingService:
    """Mock embedding service for testing without API calls."""

    def __init__(self, seed: int = TEST_RANDOM_SEED) -> None:
        """Initialize mock embedding service."""
        self._call_count = 0
        self._last_texts: list[str] = []
        self._rng = np.random.default_rng(seed)

    async def embed_text(self, text: str) -> list[float]:
        """Generate consistent fake embedding based on text hash."""
        self._call_count += 1
        # Generate consistent pseudo-random embedding based on text content
        text_seed = hash(text) % (2**32)
        text_rng = np.random.default_rng(text_seed)
        return text_rng.random(EMBEDDING_DIM).tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate batch of fake embeddings."""
        self._last_texts = texts
        self._call_count += 1
        return [await self.embed_text(text) for text in texts]


@pytest.fixture
def mock_embedding_service():
    """Provide mock embedding service for tests."""
    return MockEmbeddingService()


@pytest.fixture
def sample_xml_file(tmp_path):
    """Create a sample Repomix XML file for testing."""
    xml_file = tmp_path / "repomix-output.xml"
    xml_file.write_text(SAMPLE_REPOMIX_XML, encoding="utf-8")
    return str(xml_file)


@pytest.mark.integration
@pytest.mark.rag
@pytest.mark.database
class TestCodeIngestionEndToEnd:
    """Test end-to-end code ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_code_ingestion_end_to_end(
        self,
        db_session: AsyncSession,
        sample_xml_file: str,
        mock_embedding_service: MockEmbeddingService,
    ) -> None:
        """Test complete codebase ingestion from XML to database."""
        # Create RAG tables
        async with db_session.bind.begin() as conn:
            await conn.run_sync(DocumentORM.metadata.create_all)

        # Initialize service with mock embeddings
        ingestion_service = CodeIngestionService(
            session=db_session,
            embedding_service=mock_embedding_service,
        )

        # Ingest the codebase
        result = await ingestion_service.ingest_codebase(
            xml_file_path=sample_xml_file,
            document_name="test-codebase",
        )

        # Verify result metadata
        assert result.files_processed == 3
        assert result.chunks_created == 3
        assert result.total_tokens > 0
        assert result.estimated_cost_usd >= 0
        assert result.document.nome == "test-codebase"
        assert result.document.arquivo_origem == sample_xml_file

        # Verify document was created in database
        from sqlalchemy import select

        doc_stmt = select(DocumentORM).where(DocumentORM.nome == "test-codebase")
        doc_result = await db_session.execute(doc_stmt)
        document_orm = doc_result.scalar_one_or_none()

        assert document_orm is not None
        assert document_orm.chunk_count == 3
        assert document_orm.token_count == result.total_tokens

        # Verify chunks were created
        chunk_stmt = select(ChunkORM).where(ChunkORM.documento_id == document_orm.id)
        chunk_result = await db_session.execute(chunk_stmt)
        chunks_orm = chunk_result.scalars().all()

        assert len(chunks_orm) == 3

        # Verify chunk properties
        for chunk_orm in chunks_orm:
            assert chunk_orm.texto
            assert chunk_orm.embedding is not None
            assert chunk_orm.token_count > 0
            assert chunk_orm.metadados

            # Verify embedding can be deserialized
            embedding_bytes = chunk_orm.embedding
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
            assert len(embedding) == EMBEDDING_DIM

            # Verify metadata contains code-specific fields
            import json

            metadata = json.loads(chunk_orm.metadados)
            assert "file_path" in metadata
            assert "language" in metadata
            assert "layer" in metadata
            assert "module" in metadata
            assert metadata["documento"] == "test-codebase"

        # Verify specific files were processed
        file_paths = [json.loads(c.metadados)["file_path"] for c in chunks_orm]
        assert "src/core/agent.py" in file_paths
        assert "src/storage/sqlite_repository.py" in file_paths
        assert "src/utils/logger.py" in file_paths

        # Cleanup: delete document
        await db_session.delete(document_orm)
        await db_session.commit()

        # Verify deletion cascaded to chunks
        chunk_result_after = await db_session.execute(chunk_stmt)
        chunks_after = chunk_result_after.scalars().all()
        assert len(chunks_after) == 0

    @pytest.mark.asyncio
    async def test_query_code_with_filters(
        self,
        db_session: AsyncSession,
        sample_xml_file: str,
        mock_embedding_service: MockEmbeddingService,
        monkeypatch,
    ) -> None:
        """Test query_code() method with various filters."""
        # Disable ChromaDB for this test to avoid production data interference
        monkeypatch.setenv("BOTSALINHA_RAG__CHROMA__ENABLED", "false")
        from src.config.settings import get_settings
        get_settings.cache_clear()

        # Create RAG tables
        async with db_session.bind.begin() as conn:
            await conn.run_sync(DocumentORM.metadata.create_all)

        # Ingest codebase
        ingestion_service = CodeIngestionService(
            session=db_session,
            embedding_service=mock_embedding_service,
        )
        await ingestion_service.ingest_codebase(
            xml_file_path=sample_xml_file,
            document_name="test-codebase-filters",
        )

        # Get document ID for filtering
        from sqlalchemy import select

        doc_stmt = select(DocumentORM).where(DocumentORM.nome == "test-codebase-filters")
        doc_result = await db_session.execute(doc_stmt)
        document_orm = doc_result.scalar_one()

        # Test query with language filter
        query_service = QueryService(
            session=db_session,
            embedding_service=mock_embedding_service,
        )

        # Query for Python code only
        context_python = await query_service.query_code(
            query_text="agent wrapper",
            language="python",
            top_k=5,
        )

        assert len(context_python.chunks_usados) > 0
        # All returned chunks should have language=python in metadata
        for chunk in context_python.chunks_usados:
            assert chunk.metadados.model_dump().get("language") == "python"

        # Query with layer filter (core layer)
        context_core = await query_service.query_code(
            query_text="agent",
            layer="core",
            top_k=5,
        )

        assert len(context_core.chunks_usados) > 0
        # All returned chunks should be from core layer
        for chunk in context_core.chunks_usados:
            metadata = chunk.metadados.model_dump()
            assert metadata.get("layer") == "core"

        # Query with module filter
        context_module = await query_service.query_code(
            query_text="repository",
            module="sqlite_repository",
            top_k=5,
        )

        assert len(context_module.chunks_usados) > 0
        # All returned chunks should be from sqlite_repository module
        for chunk in context_module.chunks_usados:
            metadata = chunk.metadados.model_dump()
            assert "sqlite_repository" in metadata.get("module", "")

        # Query without filters (should return all matches)
        context_all = await query_service.query_code(
            query_text="class or function",
            top_k=5,
        )

        assert len(context_all.chunks_usados) > 0

        # Cleanup
        await db_session.delete(document_orm)
        await db_session.commit()

        # Restore settings cache
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_ingestion_reuses_existing_document_by_content_hash(
        self,
        db_session: AsyncSession,
        sample_xml_file: str,
        mock_embedding_service: MockEmbeddingService,
    ) -> None:
        """Should reuse existing document when content_hash already exists."""
        async with db_session.bind.begin() as conn:
            await conn.run_sync(DocumentORM.metadata.create_all)

        ingestion_service = CodeIngestionService(
            session=db_session,
            embedding_service=mock_embedding_service,
        )

        first = await ingestion_service.ingest_codebase(
            xml_file_path=sample_xml_file,
            document_name="test-codebase-dedupe",
        )
        second = await ingestion_service.ingest_codebase(
            xml_file_path=sample_xml_file,
            document_name="test-codebase-dedupe",
        )

        from sqlalchemy import delete, select

        doc_stmt = select(DocumentORM).where(DocumentORM.nome == "test-codebase-dedupe")
        doc_result = await db_session.execute(doc_stmt)
        documents = doc_result.scalars().all()

        assert len(documents) == 1
        assert first.document.id == second.document.id
        assert first.document.content_hash == second.document.content_hash

        # Cleanup: delete test document to prevent pollution
        delete_stmt = delete(DocumentORM).where(DocumentORM.nome == "test-codebase-dedupe")
        await db_session.execute(delete_stmt)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_chunk_positions_use_actual_created_chunks(
        self,
        db_session: AsyncSession,
        mock_embedding_service: MockEmbeddingService,
    ) -> None:
        """Should compute posicao_documento using only chunks that were actually created."""
        ingestion_service = CodeIngestionService(
            session=db_session,
            embedding_service=mock_embedding_service,
        )

        parsed_files = [
            {
                "file_path": "src/core/a.py",
                "language": "python",
                "text": "def a():\n    return 1\n",
            },
            {
                "file_path": "src/core/empty.py",
                "language": "python",
                "text": "   ",
            },
            {
                "file_path": "src/core/b.py",
                "language": "python",
                "text": "def b():\n    return 2\n",
            },
        ]

        chunks = await ingestion_service._extract_chunks_from_files(
            parsed_files=parsed_files,
            document_name="position-test",
            documento_id=1,
        )

        assert len(chunks) == 2
        assert chunks[0].posicao_documento == 0.0
        assert chunks[1].posicao_documento == 1.0

    @pytest.mark.asyncio
    async def test_large_file_is_split_with_function_and_class_metadata(
        self,
        db_session: AsyncSession,
        mock_embedding_service: MockEmbeddingService,
    ) -> None:
        """Should split large code files into multiple chunks with line/function/class metadata."""
        ingestion_service = CodeIngestionService(
            session=db_session,
            embedding_service=mock_embedding_service,
        )
        ingestion_service._code_chunker = CodeChunkExtractor(
            config={"max_tokens": 80, "overlap_tokens": 0, "min_chunk_size": 20}
        )

        large_file_text = """
class BigService:
    def run(self):
        return "ok"

def helper_0():
    return 0

def helper_1():
    return 1

def helper_2():
    return 2

def helper_3():
    return 3

def helper_4():
    return 4

def helper_5():
    return 5

def helper_6():
    return 6

def helper_7():
    return 7

def helper_8():
    return 8

def helper_9():
    return 9
""".strip()

        parsed_files = [
            {
                "file_path": "src/core/large_module.py",
                "language": "python",
                "text": large_file_text,
                "line_start": 1,
                "line_end": len(large_file_text.splitlines()),
            }
        ]

        chunks = await ingestion_service._extract_chunks_from_files(
            parsed_files=parsed_files,
            document_name="large-file-test",
            documento_id=1,
        )

        assert len(chunks) > 1

        extracted_functions: set[str] = set()
        extracted_classes: set[str] = set()

        for chunk in chunks:
            metadata = chunk.metadados.model_dump()
            assert metadata.get("file_path") == "src/core/large_module.py"
            assert metadata.get("language") == "python"
            assert metadata.get("module") == "large_module"
            assert isinstance(metadata.get("line_start"), int)
            assert isinstance(metadata.get("line_end"), int)
            assert metadata["line_start"] <= metadata["line_end"]

            extracted_functions.update(metadata.get("functions", []))
            extracted_classes.update(metadata.get("classes", []))

        assert "helper_0" in extracted_functions
        assert "BigService" in extracted_classes


@pytest.mark.integration
@pytest.mark.rag
class TestRepomixXMLParser:
    """Test Repomix XML parser integration."""

    @pytest.mark.asyncio
    async def test_parse_repomix_xml(
        self,
        sample_xml_file: str,
    ) -> None:
        """Test parsing Repomix XML file."""
        parser = RepomixXMLParser(sample_xml_file)
        files = await parser.parse()

        assert len(files) == 3

        # Verify file structure
        for file_data in files:
            assert "file_path" in file_data
            assert "language" in file_data
            assert "text" in file_data
            assert "line_start" in file_data
            assert "line_end" in file_data

        # Verify specific files
        file_paths = [f["file_path"] for f in files]
        assert "src/core/agent.py" in file_paths
        assert "src/storage/sqlite_repository.py" in file_paths
        assert "src/utils/logger.py" in file_paths

        # Verify language detection
        for file_data in files:
            if file_data["file_path"].endswith(".py"):
                assert file_data["language"] == "python"

        # Verify text content
        agent_file = next(f for f in files if f["file_path"] == "src/core/agent.py")
        assert "class AgentWrapper" in agent_file["text"]
        assert agent_file["line_start"] == 1
        assert agent_file["line_end"] > 1


@pytest.mark.integration
@pytest.mark.rag
@pytest.mark.database
class TestRagRepositoryCode:
    """Test RagRepository with code metadata."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_code_chunk(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test saving and retrieving code chunks with metadata."""
        # Create RAG tables
        async with db_session.bind.begin() as conn:
            await conn.run_sync(DocumentORM.metadata.create_all)

        # Create session maker
        from sqlalchemy.orm import sessionmaker

        async_session_maker = sessionmaker(
            db_session.bind, class_=AsyncSession, expire_on_commit=False
        )

        repo = RagRepository(async_session_maker)

        # Create a test document first
        document = Document(
            id=1,  # Use fixed ID for testing
            nome="test-doc",
            arquivo_origem="/test/path.xml",
            chunk_count=0,
            token_count=0,
        )

        # Create code chunk with metadata
        code_metadata = ChunkMetadata(
            documento="test-doc",
            titulo="src/core/agent.py",
            tipo="code",
            file_path="src/core/agent.py",
            language="python",
            layer="core",
            module="agent",
            functions=["generate_response"],
            classes=["AgentWrapper"],
            imports=["structlog", "agno"],
            is_test=False,
        )

        chunk = Chunk(
            chunk_id="test-chunk-001",
            documento_id=document.id,
            texto="def test_function(): pass",
            metadados=code_metadata,
            token_count=5,
            posicao_documento=0.0,
        )

        # Create fake embedding
        rng = np.random.default_rng(TEST_RANDOM_SEED)
        fake_embedding = rng.random(EMBEDDING_DIM).tolist()

        # Save chunk
        saved_chunk = await repo.save_chunk(chunk, fake_embedding)

        assert saved_chunk.chunk_id == "test-chunk-001"
        assert saved_chunk.texto == chunk.texto
        assert saved_chunk.metadados.language == "python"
        assert saved_chunk.metadados.layer == "core"

        # Retrieve chunk
        retrieved_chunk = await repo.get_by_id("test-chunk-001")

        assert retrieved_chunk is not None
        assert retrieved_chunk.chunk_id == chunk.chunk_id
        assert retrieved_chunk.metadados.language == "python"
        assert retrieved_chunk.metadados.layer == "core"
        assert len(retrieved_chunk.metadados.functions) == 1
        assert "generate_response" in retrieved_chunk.metadados.functions

        # Test search with filters
        query_embedding = rng.random(EMBEDDING_DIM).tolist()

        # Search without filters
        results_all = await repo.search(query_embedding, limit=10)
        assert len(results_all) > 0

        # Search with language filter
        results_filtered = await repo.search(
            query_embedding, limit=10, filters={"language": "python"}
        )
        assert len(results_filtered) > 0

        # Verify metadata is preserved in search results
        for result_chunk, _score in results_filtered:
            assert result_chunk.metadados.language == "python"

        # Delete chunk
        deleted = await repo.delete("test-chunk-001")
        assert deleted is True

        # Verify deletion
        retrieved_after = await repo.get_by_id("test-chunk-001")
        assert retrieved_after is None

        # Delete non-existent chunk should return False
        deleted_again = await repo.delete("test-chunk-001")
        assert deleted_again is False

    @pytest.mark.asyncio
    async def test_search_with_metadata_filters(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test searching with multiple metadata filters."""
        # Create seeded RNG for reproducibility
        rng = np.random.default_rng(TEST_RANDOM_SEED)

        # Create RAG tables
        async with db_session.bind.begin() as conn:
            await conn.run_sync(DocumentORM.metadata.create_all)

        from sqlalchemy.orm import sessionmaker

        async_session_maker = sessionmaker(
            db_session.bind, class_=AsyncSession, expire_on_commit=False
        )

        repo = RagRepository(async_session_maker)

        # Create multiple chunks with different metadata
        chunks_to_create = [
            {
                "chunk_id": "test-001",
                "file_path": "src/core/agent.py",
                "language": "python",
                "layer": "core",
                "module": "agent",
            },
            {
                "chunk_id": "test-002",
                "file_path": "src/storage/repository.py",
                "language": "python",
                "layer": "storage",
                "module": "repository",
            },
            {
                "chunk_id": "test-003",
                "file_path": "src/utils/logger.py",
                "language": "python",
                "layer": "utils",
                "module": "logger",
            },
        ]

        for chunk_spec in chunks_to_create:
            metadata = ChunkMetadata(
                documento="test-doc",
                titulo=chunk_spec["file_path"],
                tipo="code",
                file_path=chunk_spec["file_path"],
                language=chunk_spec["language"],
                layer=chunk_spec["layer"],
                module=chunk_spec["module"],
                is_test=False,
            )

            chunk = Chunk(
                chunk_id=chunk_spec["chunk_id"],
                documento_id=1,
                texto=f"# Code from {chunk_spec['file_path']}",
                metadados=metadata,
                token_count=10,
                posicao_documento=0.0,
            )

            fake_embedding = rng.random(EMBEDDING_DIM).tolist()
            await repo.save_chunk(chunk, fake_embedding)

        # Test filtering by layer
        query_embedding = rng.random(EMBEDDING_DIM).tolist()

        results_core = await repo.search(
            query_embedding, limit=10, filters={"layer": "core"}
        )
        assert len(results_core) == 1
        assert results_core[0][0].chunk_id == "test-001"

        results_storage = await repo.search(
            query_embedding, limit=10, filters={"layer": "storage"}
        )
        assert len(results_storage) == 1
        assert results_storage[0][0].chunk_id == "test-002"

        # Test filtering by module
        results_logger = await repo.search(
            query_embedding, limit=10, filters={"module": "logger"}
        )
        assert len(results_logger) == 1
        assert results_logger[0][0].chunk_id == "test-003"

        # Test filtering by language
        results_python = await repo.search(
            query_embedding, limit=10, filters={"language": "python"}
        )
        assert len(results_python) == 3  # All three are Python

        # Test combined filters
        results_combined = await repo.search(
            query_embedding, limit=10, filters={"language": "python", "layer": "core"}
        )
        assert len(results_combined) == 1
        assert results_combined[0][0].chunk_id == "test-001"

        # Cleanup
        for chunk_spec in chunks_to_create:
            await repo.delete(chunk_spec["chunk_id"])


@pytest.mark.integration
@pytest.mark.rag
class TestCodeMetadataExtraction:
    """Test code metadata extraction integration."""

    @pytest.mark.asyncio
    async def test_extract_python_metadata(
        self,
    ) -> None:
        """Test metadata extraction for Python code."""
        from src.rag.utils.code_metadata_extractor import CodeMetadataExtractor

        extractor = CodeMetadataExtractor()

        python_code = """
\"\"\"Agent wrapper module.\"\"\"

import structlog
from agno.agent import Agent
from typing import Optional

class AgentWrapper:
    \"\"\"Wrapper for Agno Agent.\"\"\"

    def __init__(self, repository=None):
        self.agent = Agent(name="Test")
        self.repository = repository

    async def generate_response(self, prompt: str) -> str:
        \"\"\"Generate a response.\"\"\"
        return "Response"

def create_agent():
    \"\"\"Factory function.\"\"\"
    return AgentWrapper()
"""

        metadata = extractor.extract_code_metadata(
            text=python_code,
            context={"file_path": "src/core/agent.py"},
        )

        assert metadata["language"] == "python"
        assert metadata["layer"] == "core"
        assert metadata["module"] == "agent"
        assert metadata["is_test"] is False

        # Check extracted functions
        assert "generate_response" in metadata["functions"]
        assert "create_agent" in metadata["functions"]

        # Check extracted classes
        assert "AgentWrapper" in metadata["classes"]

        # Check imports (Note: import parsing may include entire statement)
        # At minimum, verify imports were extracted
        assert len(metadata["imports"]) > 0

    @pytest.mark.asyncio
    async def test_detect_test_files(
        self,
    ) -> None:
        """Test test file detection."""
        from src.rag.utils.code_metadata_extractor import CodeMetadataExtractor

        extractor = CodeMetadataExtractor()

        # Test various test file patterns
        test_cases = [
            ("tests/unit/test_agent.py", True),
            ("tests/integration/test_rag.py", True),
            ("src/core/test_agent.py", True),
            ("src/core/agent_test.py", True),
            ("src/core/agent.py", False),
            ("src/core/conftest.py", True),  # conftest is a test file
            ("tests/__init__.py", True),  # in tests directory
        ]

        for file_path, expected_is_test in test_cases:
            metadata = extractor.extract_code_metadata(
                text="# test file",
                context={"file_path": file_path},
            )
            assert metadata["is_test"] == expected_is_test, f"Failed for {file_path}"

    @pytest.mark.asyncio
    async def test_layer_classification(
        self,
    ) -> None:
        """Test architectural layer classification."""
        from src.rag.utils.code_metadata_extractor import CodeMetadataExtractor

        extractor = CodeMetadataExtractor()

        layer_cases = [
            ("src/core/agent.py", "core"),
            ("src/storage/sqlite_repository.py", "storage"),
            ("src/rag/services/query_service.py", "rag"),
            ("src/middleware/rate_limiter.py", "middleware"),
            ("src/utils/logger.py", "utils"),
            ("src/models/conversation.py", "models"),
            ("src/config/settings.py", "config"),
            ("tests/unit/test_agent.py", "tests"),
            ("scripts/run_tests.sh", "scripts"),
            ("docs/DEVELOPER_GUIDE.md", "docs"),
            ("migrations/versions/001_initial.py", "migrations"),
            ("unknown/path/file.py", "unknown"),
        ]

        for file_path, expected_layer in layer_cases:
            metadata = extractor.extract_code_metadata(
                text="# code",
                context={"file_path": file_path},
            )
            assert metadata["layer"] == expected_layer, f"Failed for {file_path}"
