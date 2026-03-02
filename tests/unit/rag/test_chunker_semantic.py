"""Unit tests for legal semantic chunking."""

from __future__ import annotations

from statistics import pstdev

from src.rag.parser.chunker import ChunkExtractor
from src.rag.utils.metadata_extractor import MetadataExtractor


def _paragraph(text: str, *, is_heading: bool = False, heading_level: int | None = None) -> dict:
    return {
        "text": text,
        "style": "Normal",
        "is_heading": is_heading,
        "heading_level": heading_level,
        "is_bold": False,
        "is_italic": False,
        "runs": [{"text": text, "is_bold": False, "is_italic": False}],
    }


def _baseline_chunk_texts(
    parsed_doc: list[dict], chunker: ChunkExtractor, *, max_tokens: int
) -> list[str]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in parsed_doc:
        text = paragraph.get("text", "")
        if not text:
            continue
        paragraph_tokens = chunker._estimate_tokens(text)
        if current and current_tokens + paragraph_tokens > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(text)
        current_tokens += paragraph_tokens

    if current:
        chunks.append(current)

    return ["\n\n".join(block) for block in chunks]


def test_semantic_chunker_does_not_split_inciso_or_paragrafo() -> None:
    parsed_doc = [
        _paragraph("CAPITULO I - Disposicoes Gerais", is_heading=True, heading_level=1),
        _paragraph("Art. 1o Esta lei define o regime juridico."),
        _paragraph("I - A administracao publica deve observar a legalidade e a impessoalidade."),
        _paragraph("Complemento do inciso I com regra adicional relevante."),
        _paragraph("II - O servidor deve atuar com eficiencia e transparencia."),
        _paragraph("§ 1o O disposto neste artigo aplica-se a todos os orgaos."),
        _paragraph("Complemento do paragrafo primeiro com detalhamento operacional."),
        _paragraph("Art. 2o Os deveres funcionais sao obrigatorios."),
    ]
    chunker = ChunkExtractor(config={"max_tokens": 55, "overlap_tokens": 15, "min_chunk_size": 20})
    chunks = chunker.extract_chunks(
        parsed_doc=parsed_doc,
        metadata_extractor=MetadataExtractor(),
        document_name="LeiX",
        documento_id=10,
    )

    assert len(chunks) >= 2

    inciso_i_chunk = next(
        c for c in chunks if "I - A administracao publica" in c.texto
    )
    assert "Complemento do inciso I" in inciso_i_chunk.texto

    paragrafo_chunk = next(
        c for c in chunks if "§ 1o O disposto neste artigo" in c.texto
    )
    assert "Complemento do paragrafo primeiro" in paragrafo_chunk.texto


def test_semantic_chunker_applies_overlap_and_normative_hierarchy() -> None:
    parsed_doc = [
        _paragraph("TITULO I", is_heading=True, heading_level=1),
        _paragraph("Art. 10 Esta norma trata do procedimento administrativo."),
        _paragraph("I - O processo comeca por requerimento formal."),
        _paragraph("II - O prazo para resposta e de trinta dias."),
        _paragraph("III - A autoridade pode prorrogar o prazo por motivacao."),
        _paragraph("§ 1o A prorrogacao depende de justificativa tecnica."),
        _paragraph("§ 2o A decisao deve ser publicada em diario oficial."),
        _paragraph("Art. 11 A revisao pode ser solicitada em cinco dias."),
        _paragraph("I - O pedido deve apontar erro material."),
        _paragraph("II - A decisao revisional e definitiva."),
    ]
    chunker = ChunkExtractor(config={"max_tokens": 60, "overlap_tokens": 18, "min_chunk_size": 20})
    chunks = chunker.extract_chunks(
        parsed_doc=parsed_doc,
        metadata_extractor=MetadataExtractor(),
        document_name="LeiY",
        documento_id=11,
    )

    assert len(chunks) >= 2

    has_overlap = False
    for idx in range(1, len(chunks)):
        previous_paragraphs = {p.strip() for p in chunks[idx - 1].texto.split("\n\n") if p.strip()}
        current_paragraphs = {p.strip() for p in chunks[idx].texto.split("\n\n") if p.strip()}
        if previous_paragraphs.intersection(current_paragraphs):
            has_overlap = True
            break
    assert has_overlap

    for chunk in chunks:
        hierarchy = chunk.metadados.hierarquia_normativa
        assert hierarchy
        assert any(item.startswith("artigo:") for item in hierarchy)


def test_semantic_chunker_improves_context_coverage_over_baseline() -> None:
    parsed_doc = [
        _paragraph("TITULO II", is_heading=True, heading_level=1),
        _paragraph("Art. 20 O servidor tem direito a licenca."),
        _paragraph("I - Licenca para tratamento de saude."),
        _paragraph("Detalhamento do inciso I em paragrafo autonomo."),
        _paragraph("II - Licenca por motivo de doenca em pessoa da familia."),
        _paragraph("Detalhamento do inciso II em paragrafo autonomo."),
        _paragraph("§ 1o O prazo de licenca depende de pericia medica."),
        _paragraph("Detalhamento do paragrafo primeiro com condicoes adicionais."),
        _paragraph("§ 2o O retorno antecipado depende de alta medica."),
        _paragraph("Detalhamento do paragrafo segundo com requisitos de registro."),
        _paragraph("Art. 21 A licenca pode ser interrompida por interesse publico."),
        _paragraph("I - A interrupcao exige motivacao escrita."),
        _paragraph("Detalhamento do inciso do artigo 21."),
    ]
    config = {"max_tokens": 52, "overlap_tokens": 16, "min_chunk_size": 18}
    chunker = ChunkExtractor(config=config)
    metadata_extractor = MetadataExtractor()
    semantic_chunks = chunker.extract_chunks(
        parsed_doc=parsed_doc,
        metadata_extractor=metadata_extractor,
        document_name="LeiZ",
        documento_id=12,
    )

    baseline_texts = _baseline_chunk_texts(parsed_doc, chunker, max_tokens=config["max_tokens"])
    baseline_metadata = [metadata_extractor.extract(text, {"documento": "LeiZ"}) for text in baseline_texts]

    semantic_coverage = sum(1 for chunk in semantic_chunks if chunk.metadados.artigo) / len(semantic_chunks)
    baseline_coverage = sum(1 for md in baseline_metadata if md.artigo) / len(baseline_metadata)
    assert semantic_coverage > baseline_coverage

    semantic_sizes = [chunk.token_count for chunk in semantic_chunks]
    baseline_sizes = [chunker._estimate_tokens(text) for text in baseline_texts]
    semantic_cv = pstdev(semantic_sizes) / max(1.0, (sum(semantic_sizes) / len(semantic_sizes)))
    baseline_cv = pstdev(baseline_sizes) / max(1.0, (sum(baseline_sizes) / len(baseline_sizes)))

    assert semantic_cv <= baseline_cv + 0.15
