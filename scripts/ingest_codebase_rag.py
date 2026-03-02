#!/usr/bin/env python
"""Script para ingerir código do repositório no RAG.

Uso:
    uv run python scripts/ingest_codebase_rag.py repomix-output.xml

Este script irá:
1. Parsear arquivo XML gerado pelo repomix
2. Ingerir o código no banco RAG
3. Gerar embeddings usando OpenAI API
4. Salvar chunks e embeddings no banco
"""

import asyncio
import sys
from argparse import ArgumentParser
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings  # noqa: E402
from src.models.rag_models import DocumentORM  # noqa: E402
from src.rag.parser.xml_parser import RepomixXMLParser  # noqa: E402
from src.rag.services.code_ingestion_service import CodeIngestionService  # noqa: E402
from src.rag.services.embedding_service import EmbeddingService  # noqa: E402

log = structlog.get_logger(__name__)


async def main() -> None:
    """Executa a ingestão de codebase no RAG."""
    # Parse arguments
    parser = ArgumentParser(description="Ingest codebase into RAG")
    parser.add_argument("xml_file", help="Path to repomix-output.xml")
    parser.add_argument("--name", default="botsalinha-codebase", help="Document name")
    parser.add_argument("--dry-run", action="store_true", help="Parse without ingesting")
    parser.add_argument("--replace", action="store_true", help="Replace existing document")
    args = parser.parse_args()

    # Verificar se OPENAI_API_KEY está configurada
    settings = get_settings()
    api_key = settings.get_openai_api_key()
    if not api_key:
        print("❌ BOTSALINHA_OPENAI__API_KEY não configurada")
        print("💡 Defina BOTSALINHA_OPENAI__API_KEY no .env")
        print("   (ou use OPENAI_API_KEY para compatibilidade legada)")
        sys.exit(1)

    # Conectar ao banco
    settings = get_settings()
    db_url = str(settings.database.url)
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    try:
        engine = create_async_engine(db_url)
    except Exception as exc:
        log.error("codebase_ingest_db_engine_error", db_url=db_url, error=str(exc))
        print("❌ Failed to initialize database engine")
        print(f"💡 Details: {exc}")
        sys.exit(1)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        # Parse XML early for dry-run and fast failure feedback
        try:
            parser_obj = RepomixXMLParser(args.xml_file)
            parsed_files = await parser_obj.parse()
        except Exception as exc:
            log.error("codebase_ingest_parse_error", xml_file=args.xml_file, error=str(exc))
            print("❌ Failed to parse XML input")
            print(f"💡 Details: {exc}")
            sys.exit(1)

        print("📚 Codebase RAG Ingestion")
        print(f"📄 XML: {args.xml_file}")
        print(f"📦 Document: {args.name}")
        print()

        if args.dry_run:
            print(f"📋 Files found: {len(parsed_files)}")
            print("⚠️  Dry run - not ingesting")
            return

        try:
            async with session_factory() as session:
                # Delete and ingest MUST use the same session for atomicity
                if args.replace:
                    # Direct database operation for delete within the same session
                    stmt = select(DocumentORM).where(DocumentORM.nome == args.name)
                    doc_result = await session.execute(stmt)
                    existing = doc_result.scalar_one_or_none()
                    if existing:
                        # Cascade delete handles chunks automatically
                        await session.delete(existing)
                        print("🗑️  Deleted existing document")
                        print()

                # Ingest using the SAME session - if this fails, rollback undoes delete too
                embedding_service = EmbeddingService(api_key=api_key)
                ingestion_service = CodeIngestionService(
                    session=session,
                    embedding_service=embedding_service,
                )
                result = await ingestion_service.ingest_codebase(args.xml_file, args.name)

                # Single commit at the end - atomic operation
                await session.commit()
        except Exception as exc:
            log.error(
                "codebase_ingest_execution_error",
                xml_file=args.xml_file,
                document=args.name,
                error=str(exc),
            )
            print("❌ Ingestion failed")
            print(f"💡 Details: {exc}")
            sys.exit(1)

        print(f"Files:    {result.files_processed}")
        print(f"Chunks:   {result.chunks_created}")
        print(f"Tokens:   {result.total_tokens:,}")
        print(f"Cost:     ${result.estimated_cost_usd:.4f}")
        print()
        print("✅ Ingestion complete!")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
