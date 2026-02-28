"""Unit tests for AgentWrapper prompt building with RAG augmentation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.agent import AgentWrapper
from src.rag.models import Chunk, ChunkMetadata, ConfiancaLevel, RAGContext
from src.rag.utils.confianca_calculator import ConfiancaCalculator


def _build_wrapper(should_augment: bool) -> AgentWrapper:
    wrapper = AgentWrapper.__new__(AgentWrapper)
    wrapper._query_service = SimpleNamespace(
        should_augment_prompt=lambda _context: should_augment
    )
    wrapper._confianca_calculator = ConfiancaCalculator()
    return wrapper


def _build_context(confidence: ConfiancaLevel, chunk_text: str) -> RAGContext:
    chunk = Chunk(
        chunk_id="chunk_1",
        documento_id=1,
        texto=chunk_text,
        metadados=ChunkMetadata(documento="CF/88", artigo="5"),
        token_count=120,
        posicao_documento=0.1,
    )
    return RAGContext(
        chunks_usados=[chunk],
        similaridades=[0.91],
        confianca=confidence,
        fontes=["CF/88, Art. 5"],
        retrieval_meta={"retrieval_mode": "hybrid_lite"},
        query_normalized="art. 5 direitos fundamentais",
    )


@pytest.mark.unit
def test_build_prompt_includes_rag_block_when_enabled() -> None:
    wrapper = _build_wrapper(should_augment=True)
    rag_context = _build_context(ConfiancaLevel.ALTA, "Direitos fundamentais e garantias.")

    full_prompt = wrapper._build_prompt(
        "Explique o art. 5 da CF.",
        history=[
            {"role": "user", "content": "Pergunta anterior"},
            {"role": "assistant", "content": "Resposta anterior"},
        ],
        rag_context=rag_context,
    )

    assert "=== BLOCO_RAG_INICIO ===" in full_prompt
    assert "RAG_STATUS: ALTA" in full_prompt
    assert "RAG_QUERY_NORMALIZED: art. 5 direitos fundamentais" in full_prompt
    assert "Fonte: CF/88, Art. 5" in full_prompt
    assert full_prompt.index("=== BLOCO_RAG_INICIO ===") < full_prompt.index("=== Nova Mensagem ===")
    assert "=== BLOCO_RAG_FIM ===" in full_prompt


@pytest.mark.unit
def test_build_prompt_skips_rag_block_when_query_service_disables_augmentation() -> None:
    wrapper = _build_wrapper(should_augment=False)
    rag_context = _build_context(ConfiancaLevel.ALTA, "Texto jurídico")

    full_prompt = wrapper._build_prompt(
        "Pergunta atual",
        history=[],
        rag_context=rag_context,
    )

    assert "=== BLOCO_RAG_INICIO ===" not in full_prompt
    assert "RAG_STATUS:" not in full_prompt
    assert "Usuário: Pergunta atual" in full_prompt


@pytest.mark.unit
def test_build_rag_augmentation_for_low_confidence_truncates_chunk_and_signals_partial_use() -> None:
    wrapper = _build_wrapper(should_augment=True)
    long_chunk = "x" * 520
    rag_context = _build_context(ConfiancaLevel.BAIXA, long_chunk)

    augmentation = wrapper._build_rag_augmentation(rag_context)

    assert "RAG_STATUS: BAIXA" in augmentation
    assert "referência parcial" in augmentation
    assert "=== BLOCO_RAG_FIM ===" in augmentation
    assert long_chunk not in augmentation
    assert "Texto: " in augmentation
    assert "..." in augmentation
