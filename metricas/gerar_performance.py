"""
Script for generating general bot performance metrics.
Measures latency of the Agent's response generation.
"""

import asyncio
import csv
import structlog
import time
from pathlib import Path

from src.core.agent import AgentWrapper
from src.storage.sqlite_repository import get_repository

TEST_PROMPTS = [
    "Olá, tudo bem?",
    "Me explique o artigo 5 da constituição.",
    "Quais as regras de vacância na lei 8112?",
]

log = structlog.get_logger(__name__)


async def check_performance() -> None:
    log.info("performance_check_started")

    repository = get_repository()
    await repository.initialize_database()

    async with repository.async_session_maker() as session:
        agent = AgentWrapper(repository=repository, db_session=session)

        results = []
        for prompt in TEST_PROMPTS:
            print(f"Testando prompt: '{prompt}'")
            start_time = time.perf_counter()
            try:
                # We use a dummy conversation ID representing a metric test
                conversation = await repository.get_or_create_conversation(
                    str(999999), None, str(999999)
                )

                response, rag_context = await agent.generate_response_with_rag(
                    prompt=prompt, conversation_id=conversation.id, user_id=str(999999)
                )
                duration = time.perf_counter() - start_time

                results.append(
                    {
                        "prompt": prompt,
                        "response_length": len(response),
                        "used_rag": rag_context is not None and len(rag_context.chunks_usados) > 0,
                        "duration_seconds": round(duration, 2),
                    }
                )
            except Exception as e:
                print(f"Erro no prompt '{prompt}': {e}")
                results.append(
                    {
                        "prompt": prompt,
                        "response_length": 0,
                        "used_rag": False,
                        "duration_seconds": 0.0,
                    }
                )

        output_file = Path("metricas/performance_geral.csv")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["prompt", "response_length", "used_rag", "duration_seconds"]
            )
            writer.writeheader()
            writer.writerows(results)

        print(f"Métricas de performance salvas em {output_file}")


if __name__ == "__main__":
    asyncio.run(check_performance())
