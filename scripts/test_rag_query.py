#!/usr/bin/env python
"""Script para testar consultas RAG no banco de dados.

Uso:
    uv run python scripts/test_rag_query.py

Este script irá:
1. Conectar ao banco SQLite
2. Executar uma consulta RAG de exemplo
3. Mostrar os chunks recuperados e scores de similaridade
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
from src.rag.services.query_service import QueryService
from src.rag.services.embedding_service import EmbeddingService


async def main() -> None:
    """Executa teste de consulta RAG."""
    import structlog

    log = structlog.get_logger(__name__)

    settings = get_settings()

    # Verificar se OPENAI_API_KEY está configurada
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.startswith("sk-"):
        print(f"❌ OPENAI_API_KEY não configurada ou inválida")
        sys.exit(1)

    # Conectar ao banco
    db_url = str(settings.database.url)
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Inicializar serviços
        embedding_service = EmbeddingService(api_key=api_key)
        query_service = QueryService(
            session=session,
            embedding_service=embedding_service,
        )

        # Consultas de teste
        queries = [
            "Quais são os direitos fundamentais previstos na Constituição?",
            "O que diz a Lei 8.112 sobre a posse do servidor?",
            "Quais são as causas de advertência segundo as súmulas?",
            "Qual o prazo de prescrição para ações disciplinares?",
        ]

        print("🔍 Testando Consultas RAG")
        print("=" * 80)

        for query_text in queries:
            print(f"\n📝 Consulta: {query_text}")
            print("-" * 80)

            try:
                result = await query_service.query(
                    query_text=query_text,
                    top_k=3,
                    min_similarity=0.6,
                )

                print(f"Confiança: {result.confianca}")
                print(f"Chunks encontrados: {len(result.chunks_usados)}")

                for i, (chunk, similarity) in enumerate(
                    zip(result.chunks_usados, result.similaridades)
                ):
                    print(f"\n  [{i+1}] Similaridade: {similarity:.4f}")
                    print(f"      Documento: {chunk.metadados.documento}")
                    print(f"      Texto: {chunk.texto[:100]}...")

                if result.fontes:
                    print(f"\n  📎 Fontes:")
                    for fonte in result.fontes:
                        print(f"      • {fonte}")

            except Exception as e:
                print(f"❌ Erro: {e}")
                log.error(
                    "query_failed",
                    query=query_text,
                    error=str(e),
                    exc_info=True,
                )

        print("\n" + "=" * 80)
        print("✅ Teste concluído")


if __name__ == "__main__":
    asyncio.run(main())
