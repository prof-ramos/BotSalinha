"""Unit tests for explicit content links created during ingestion."""

from unittest.mock import MagicMock

from src.rag.models import Chunk, ChunkMetadata
from src.rag.services.ingestion_service import IngestionService


def _chunk(
    chunk_id: str,
    *,
    content_type: str,
    source_type: str,
    parent_chunk_id: str | None = None,
    updated_by_law: str | None = None,
) -> Chunk:
    metadata = ChunkMetadata(
        documento="CF/88",
        content_type=content_type,
        source_type=source_type,
        parent_chunk_id=parent_chunk_id,
        updated_by_law=updated_by_law,
    )
    return Chunk(
        chunk_id=chunk_id,
        documento_id=1,
        texto=f"texto-{chunk_id}",
        metadados=metadata,
        token_count=10,
        posicao_documento=0.1,
    )


def test_build_content_links_maps_link_types() -> None:
    service = IngestionService(session=MagicMock(), embedding_service=MagicMock(model="test-model"))

    parent = _chunk("parent-1", content_type="legal_text", source_type="lei_cf")
    exam = _chunk(
        "child-exam",
        content_type="exam_question",
        source_type="exam_question",
        parent_chunk_id="parent-1",
    )
    juris = _chunk(
        "child-juris",
        content_type="jurisprudence",
        source_type="jurisprudence",
        parent_chunk_id="parent-1",
    )
    update = _chunk(
        "child-update",
        content_type="legal_text",
        source_type="emenda_constitucional",
        parent_chunk_id="parent-1",
        updated_by_law="EC 138",
    )

    links = service._build_content_links([parent, exam, juris, update])  # noqa: SLF001
    normalized = {(link.article_chunk_id, link.linked_chunk_id, link.link_type) for link in links}

    assert ("parent-1", "child-exam", "charged_in") in normalized
    assert ("parent-1", "child-juris", "interprets") in normalized
    assert ("parent-1", "child-update", "updates") in normalized

