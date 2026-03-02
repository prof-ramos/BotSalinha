#!/usr/bin/env python3
"""Test RAG query with real indexed data."""

import asyncio
import sys
from dotenv import load_dotenv

from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config.settings import get_settings
from src.rag import QueryService
from src.rag.services.embedding_service import EmbeddingService


async def main() -> None:
    """Test RAG query with real indexed data."""

    # Query de teste
    query = sys.argv[1] if len(sys.argv) > 1 else "Quais são os direitos fundamentais previstos na Constituição?"

    print(f"🔍 Query: {query}")
    print("=" * 80)

    # Configuração
    settings = get_settings()

    # Criar engine do banco (garantir driver aiosqlite)
    db_url = settings.database.url
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url)

    # Criar sessão
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        # Criar serviços
        embedding_service = EmbeddingService(
            api_key=settings.get_openai_api_key(),
            model=settings.rag.embedding_model,
        )

        query_service = QueryService(
            session=session,
            embedding_service=embedding_service,
        )

        # Executar query
        print("\n⏳ Executando busca RAG...\n")

        context = await query_service.query(
            query_text=query,
            top_k=5,
            min_similarity=0.4,
        )

        # Exibir resultados
        print(f"📊 Resultados: {len(context.chunks_usados)} chunks encontrados")
        print(f"🎯 Confiança: {context.confianca.value.upper()}")

        # Metadata da busca
        meta = context.retrieval_meta
        budget_tokens = meta.get("context_tokens_used", "N/A")
        print(f"💰 Tokens usados: {budget_tokens}")
        print("\n" + "=" * 80)

        for idx, (chunk, similarity, fonte) in enumerate(zip(
            context.chunks_usados,
            context.similaridades,
            context.fontes,
        ), 1):
            print(f"\n📌 Chunk #{idx} (similaridade: {similarity:.4f})")
            print(f"   Fonte: {fonte}")
            print(f"   Texto: {chunk.texto[:200]}...")

        # Exibir texto de aumento
        print("\n" + "=" * 80)
        print("\n📝 Texto de Aumento:\n")
        augmentation = query_service.get_augmentation_text(context)
        print(augmentation)

        # Verificar se deve aumentar prompt
        should_augment = query_service.should_augment_prompt(context)
        print(f"\n🤖 Deve aumentar prompt? {should_augment}")

    # Fechar engine
    await engine.dispose()

    print("\n" + "=" * 80)
    print("✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(main())
