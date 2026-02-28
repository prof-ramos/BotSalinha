"""
Script for generating end-to-end bot performance metrics.
Measures latency of the Agent's response generation including RAG.
"""

import asyncio
import statistics
import time
from pathlib import Path

import structlog

from metricas.utils import (
    configure_logging,
    get_base_parser,
    print_summary_box,
    save_results_csv,
    save_summary_csv,
)
from src.core.agent import AgentWrapper
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

DEFAULT_PROMPTS = [
    "Olá, tudo bem?",
    "Me explique o artigo 5 da constituição.",
    "Quais as regras de vacância na lei 8112?",
    "Quais os fundamentos da República Federativa do Brasil?",
]

async def check_performance(
    output_file: str = "metricas/performance_geral.csv",
    num_prompts: int | None = None,
) -> None:
    """Execute end-to-end performance tests and save results to CSV."""
    prompts_to_test = DEFAULT_PROMPTS[:num_prompts] if num_prompts else DEFAULT_PROMPTS
    log.info("performance_check_started", prompts_count=len(prompts_to_test))

    output_path = Path(output_file)
    results = []

    async with create_repository() as repo, repo.async_session_maker() as session:
        agent = AgentWrapper(repository=repo, db_session=session)

        for prompt in prompts_to_test:
            log.info("testing_prompt", prompt=prompt)
            start_time = time.perf_counter()

            try:
                conversation = await repo.get_or_create_conversation(
                    user_id="perf_bot_user",
                    guild_id="perf_bot_guild",
                    channel_id="perf_bot_channel",
                )

                response, rag_context = await agent.generate_response_with_rag(
                    prompt=prompt,
                    conversation_id=conversation.id,
                    user_id="perf_bot_user",
                )
                duration = time.perf_counter() - start_time

                results.append(
                    {
                        "prompt": prompt,
                        "response_length": len(response),
                        "used_rag": rag_context is not None and len(rag_context.chunks_usados) > 0,
                        "duration_seconds": round(duration, 3),
                        "status": "success",
                    }
                )
                log.info("prompt_test_finished", duration=round(duration, 3))

            except Exception as e:
                log.error("prompt_test_failed", prompt=prompt, error=str(e))
                results.append(
                    {
                        "prompt": prompt,
                        "response_length": 0,
                        "used_rag": False,
                        "duration_seconds": 0.0,
                        "status": f"error: {str(e)}",
                    }
                )

    # Save results
    fieldnames = ["prompt", "response_length", "used_rag", "duration_seconds", "status"]
    save_results_csv(output_path, results, fieldnames)

    # Calculate and print statistical summary
    successful_results = [r for r in results if r["status"] == "success"]
    durations = [r["duration_seconds"] for r in successful_results]

    if durations:
        avg_duration = statistics.mean(durations)
        total_duration = sum(durations)
        success_rate = (len(successful_results) / len(results)) * 100
        p95_latency = (
            statistics.quantiles(durations, n=20)[18]
            if len(durations) >= 20
            else max(durations)
            if durations
            else 0
        )

        metrics = [
            ("Tempo médio de resposta:", f"{avg_duration:.3f}s"),
            ("Tempo total de execução:", f"{total_duration:.3f}s"),
            ("Taxa de sucesso:", f"{success_rate:.1f}%"),
            ("Percentil 95 de latência:", f"{p95_latency:.3f}s"),
            ("Total de requisições:", len(results)),
            ("Requisições com sucesso:", len(successful_results)),
        ]
        print_summary_box("PERFORMANCE GERAL", metrics)

        summary_data = [
            {"metric": "avg_duration_seconds", "value": f"{avg_duration:.3f}"},
            {"metric": "total_duration_seconds", "value": f"{total_duration:.3f}"},
            {"metric": "success_rate_percent", "value": f"{success_rate:.1f}"},
            {"metric": "p95_latency_seconds", "value": f"{p95_latency:.3f}"},
            {"metric": "total_requests", "value": len(results)},
            {"metric": "successful_requests", "value": len(successful_results)},
        ]
        save_summary_csv(output_path, summary_data)

if __name__ == "__main__":
    parser = get_base_parser("Generate end-to-end bot performance metrics")
    parser.add_argument(
        "-p", "--prompts", type=int, default=None,
        help="Number of prompts to test (default: all available prompts)",
    )
    args = parser.parse_args()
    
    output_file = args.output or "metricas/performance_geral.csv"
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_performance(output_file=output_file, num_prompts=args.prompts))
