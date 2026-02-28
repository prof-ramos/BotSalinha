"""
Script for generating Database Access Metrics.
Measures latency for SQLite write/read operations under load.
"""

import asyncio
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
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

async def check_access_performance(
    output_file: str = "metricas/performance_acesso.csv",
    num_inserts: int = 50,
    num_reads: int = 100,
) -> None:
    """Benchmark database operations and save results to CSV."""
    log.info("db_access_performance_started", inserts=num_inserts, reads=num_reads)

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
    output_path = Path(output_file)
    save_results_csv(output_path, results, ["operation", "count", "total_time_ms", "avg_time_ms"])

    # Calculate and print statistical summary
    if len(results) >= 2:
        insert_result = next((r for r in results if "Insert" in r["operation"]), None)
        read_result = next((r for r in results if "Read" in r["operation"]), None)

        if insert_result and read_result:
            total_ops = insert_result["count"] + read_result["count"]
            total_time_sec = (insert_result["total_time_ms"] + read_result["total_time_ms"]) / 1000
            throughput = total_ops / total_time_sec if total_time_sec > 0 else 0
            ratio = read_result["avg_time_ms"] / insert_result["avg_time_ms"] if insert_result["avg_time_ms"] > 0 else 0

            metrics = [
                ("Throughput:", f"{throughput:.2f} ops/segundo"),
                (None, None), # Spacer
                ("Comparação Insert vs Read:", None),
                ("  Insert:", f"{insert_result['avg_time_ms']:.2f}ms avg ({insert_result['count']} ops)"),
                ("  Read:", f"{read_result['avg_time_ms']:.2f}ms avg ({read_result['count']} ops)"),
                ("  Ratio (Read/Insert):", f"{ratio:.2f}x"),
                (None, None), # Spacer
                ("Total de operações:", total_ops),
                ("Tempo total:", f"{total_time_sec:.3f}s"),
            ]
            print_summary_box("PERFORMANCE ACESSO DB", metrics)

            summary_data = [
                {"metric": "throughput_ops_per_second", "value": f"{throughput:.2f}"},
                {"metric": "insert_avg_ms", "value": f"{insert_result['avg_time_ms']:.2f}"},
                {"metric": "read_avg_ms", "value": f"{read_result['avg_time_ms']:.2f}"},
                {"metric": "read_insert_ratio", "value": f"{ratio:.2f}"},
                {"metric": "total_operations", "value": total_ops},
                {"metric": "total_time_seconds", "value": f"{total_time_sec:.3f}"},
            ]
            save_summary_csv(output_path, summary_data)

if __name__ == "__main__":
    parser = get_base_parser("Generate database access performance metrics")
    parser.add_argument("-i", "--inserts", type=int, default=50, help="Number of insert operations")
    parser.add_argument("-r", "--reads", type=int, default=100, help="Number of read operations")
    args = parser.parse_args()
    
    output_file = args.output or "metricas/performance_acesso.csv"
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_access_performance(output_file=output_file, num_inserts=args.inserts, num_reads=args.reads))
