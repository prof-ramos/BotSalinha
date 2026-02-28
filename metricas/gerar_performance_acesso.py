"""
Script for generating Database Access Metrics.
Measures latency for SQLite write/read operations under load.
"""

import asyncio
import csv
import time
from pathlib import Path

import structlog

from src.storage.factory import create_repository

log = structlog.get_logger(__name__)


async def check_access_performance() -> None:
    """Benchmark database operations and save results to CSV."""
    log.info("db_access_performance_started")

    num_inserts = 50
    num_reads = 100
    results = []

    async with create_repository() as repo:
        inserted_ids = []

        # 1. Measure Insert Performance
        log.info("benchmarking_inserts", count=num_inserts)
        start_insert = time.perf_counter()
        try:
            for i in range(num_inserts):
                conv = await repo.get_or_create_conversation(
                    user_id="perf_test_user",
                    guild_id="perf_test_guild",
                    channel_id=f"perf_test_channel_{i}",
                )
                inserted_ids.append(conv.id)
            insert_duration = time.perf_counter() - start_insert
            avg_insert_ms = (insert_duration / num_inserts) * 1000

            results.append(
                {
                    "operation": "Insert Conversation",
                    "count": num_inserts,
                    "total_time_ms": round(insert_duration * 1000, 2),
                    "avg_time_ms": round(avg_insert_ms, 2),
                }
            )
            log.info("insert_benchmark_finished", avg_ms=round(avg_insert_ms, 2))
        except Exception as e:
            log.error("insert_benchmark_failed", error=str(e))

        # 2. Measure Read Performance
        log.info("benchmarking_reads", count=num_reads)
        start_read = time.perf_counter()
        try:
            for _ in range(num_reads):
                await repo.get_by_user_and_guild(
                    user_id="perf_test_user", guild_id="perf_test_guild"
                )
            read_duration = time.perf_counter() - start_read
            avg_read_ms = (read_duration / num_reads) * 1000

            results.append(
                {
                    "operation": "Read Conversations",
                    "count": num_reads,
                    "total_time_ms": round(read_duration * 1000, 2),
                    "avg_time_ms": round(avg_read_ms, 2),
                }
            )
            log.info("read_benchmark_finished", avg_ms=round(avg_read_ms, 2))
        except Exception as e:
            log.error("read_benchmark_failed", error=str(e))

        # 3. Cleanup
        log.info("cleaning_up_perf_data", count=len(inserted_ids))
        for conv_id in inserted_ids:
            await repo.delete_conversation(conv_id)

    # Save Results
    output_file = Path("metricas/performance_acesso.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["operation", "count", "total_time_ms", "avg_time_ms"]
        )
        writer.writeheader()
        writer.writerows(results)

    log.info("db_access_performance_completed", output_file=str(output_file))


if __name__ == "__main__":
    asyncio.run(check_access_performance())
