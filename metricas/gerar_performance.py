"""
Script for generating end-to-end bot performance metrics.
Measures latency of the Agent's response generation including RAG.
"""

import argparse
import asyncio
import csv
import logging
import statistics
import sys
import time
from pathlib import Path

import structlog

from src.core.agent import AgentWrapper
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

DEFAULT_PROMPTS = [
    "Olá, tudo bem?",
    "Me explique o artigo 5 da constituição.",
    "Quais as regras de vacância na lei 8112?",
    "Quais os fundamentos da República Federativa do Brasil?",
]


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging level based on verbosity flags."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


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
                # Create a dummy conversation for testing purposes
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["prompt", "response_length", "used_rag", "duration_seconds", "status"]
        )
        writer.writeheader()
        writer.writerows(results)

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

        print("\n" + "=" * 60)
        print("SUMÁRIO ESTATÍSTICO - PERFORMANCE GERAL")
        print("=" * 60)
        print(f"Tempo médio de resposta:      {avg_duration:.3f}s")
        print(f"Tempo total de execução:       {total_duration:.3f}s")
        print(f"Taxa de sucesso:               {success_rate:.1f}%")
        print(f"Percentil 95 de latência:      {p95_latency:.3f}s")
        print(f"Total de requisições:          {len(results)}")
        print(f"Requisições com sucesso:       {len(successful_results)}")
        print("=" * 60)

        # Also save summary to CSV
        summary_path = output_path.parent / f"{output_path.stem}_summary{output_path.suffix}"
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerow({"metric": "avg_duration_seconds", "value": f"{avg_duration:.3f}"})
            writer.writerow({"metric": "total_duration_seconds", "value": f"{total_duration:.3f}"})
            writer.writerow({"metric": "success_rate_percent", "value": f"{success_rate:.1f}"})
            writer.writerow({"metric": "p95_latency_seconds", "value": f"{p95_latency:.3f}"})
            writer.writerow({"metric": "total_requests", "value": len(results)})
            writer.writerow({"metric": "successful_requests", "value": len(successful_results)})

        log.info("performance_summary_saved", summary_file=str(summary_path))

    log.info("performance_check_completed", output_file=str(output_path))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate end-to-end bot performance metrics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        default="metricas/performance_geral.csv",
        help="Path to the output CSV file",
    )
    parser.add_argument(
        "-p",
        "--prompts",
        type=int,
        default=None,
        help="Number of prompts to test (default: all available prompts)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress info logs (only errors will be shown)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_performance(output_file=args.output, num_prompts=args.prompts))
