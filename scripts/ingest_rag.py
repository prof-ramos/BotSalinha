#!/usr/bin/env python
"""Script para ingerir documentos RAG no banco de dados.

Uso:
    uv run python scripts/ingest_rag.py

Este script irá:
1. Conectar ao banco SQLite
2. Ingerir todos os documentos DOCX em docs/plans/RAG/
3. Gerar embeddings usando OpenAI API
4. Salvar chunks e embeddings no banco
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.models.rag_models import DocumentORM, ChunkORM
from src.rag.services.ingestion_service import IngestionService
from src.rag.services.embedding_service import EmbeddingService
from src.storage.sqlite_repository import SQLiteRepository


async def main() -> None:
    """Executa a ingestão de documentos RAG."""
    import structlog

    log = structlog.get_logger(__name__)

    settings = get_settings()

    # Verificar se OPENAI_API_KEY está configurada (ler diretamente do ambiente)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.startswith("sk-"):
        print(f"❌ OPENAI_API_KEY não configurada ou inválida")
        print(f"💡 Defina OPENAI_API_KEY no .env ou export OPENAI_API_KEY=...")
        print(f"   Valor atual: {api_key[:20] if api_key else 'None'}...")
        sys.exit(1)

    # Conectar ao banco
    db_url = str(settings.database.url)
    # Garantir que usa driver assíncrono
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Inicializar serviços com API key explícita
        embedding_service = EmbeddingService(api_key=api_key)
        ingestion_service = IngestionService(
            session=session,
            embedding_service=embedding_service,
        )

        # Encontrar documentos DOCX
        rag_dir = Path(__file__).parent.parent / "docs" / "plans" / "RAG"
        docx_files = list(rag_dir.glob("**/*.docx"))

        if not docx_files:
            log.warning(
                "ingest_no_files",
                error="Nenhum arquivo DOCX encontrado",
                directory=str(rag_dir),
            )
            print(f"❌ Nenhum arquivo DOCX encontrado em {rag_dir}")
            sys.exit(1)

        print(f"📚 Encontrados {len(docx_files)} documentos DOCX")
        print()
        print(f"{'Documento':<60} {'Chunks':>10} {'Tokens':>10}")
        print("-" * 85)

        # Ingerir cada documento
        total_chunks = 0
        total_tokens = 0
        success_count = 0

        for docx_file in sorted(docx_files):
            # Usar nome relativo como nome do documento
            rel_path = docx_file.relative_to(rag_dir)
            doc_name = rel_path.stem

            # Substituir underscores por espaços
            doc_name = doc_name.replace("_", " ")

            try:
                print(f"{doc_name:<60}", end="", flush=True)

                # Ingerir documento
                document = await ingestion_service.ingest_document(
                    file_path=str(docx_file),
                    document_name=doc_name,
                )

                print(f"{document.chunk_count:>10} {document.token_count:>10} ✅")

                total_chunks += document.chunk_count
                total_tokens += document.token_count
                success_count += 1

            except Exception as e:
                print(f"{'ERRO':>22} ❌")
                log.error(
                    "ingest_document_failed",
                    document=doc_name,
                    file=str(docx_file),
                    error=str(e),
                    exc_info=True,
                )

        print("-" * 85)
        print(f"{'TOTAL':<60} {total_chunks:>10} {total_tokens:>10}")
        print()
        print(f"✅ {success_count}/{len(docx_files)} documentos ingeridos com sucesso")
        print()
        print(f"📊 Estatísticas:")
        print(f"   • Total de chunks: {total_chunks}")
        print(f"   • Total de tokens: {total_tokens:,}")
        print(f"   • Custo estimado: ${total_tokens * 0.02 / 1_000_000:.4f} USD")


if __name__ == "__main__":
    asyncio.run(main())
