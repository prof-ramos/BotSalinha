"""
Script for generating Database Access Metrics.
Measures latency for SQLite write/read operations under load.
"""

import argparse
import asyncio
import csv
import logging
import sys
import time
from pathlib import Path

import structlog

from src.storage.factory import create_repository

log = structlog.get_logger(__name__)


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
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["operation", "count", "total_time_ms", "avg_time_ms"]
        )
        writer.writeheader()
        writer.writerows(results)

    # Calculate and print statistical summary
    if len(results) >= 2:
        insert_result = next((r for r in results if "Insert" in r["operation"]), None)
        read_result = next((r for r in results if "Read" in r["operation"]), None)

        if insert_result and read_result:
            total_ops = insert_result["count"] + read_result["count"]
            total_time_sec = (insert_result["total_time_ms"] + read_result["total_time_ms"]) / 1000
            throughput = total_ops / total_time_sec if total_time_sec > 0 else 0
            ratio = 0.0

            print("\n" + "=" * 60)
            print("SUMÁRIO ESTATÍSTICO - PERFORMANCE ACESSO DB")
            print("=" * 60)
            print(f"Throughput:                    {throughput:.2f} ops/segundo")
            print("\nComparação Insert vs Read:")
            print(
                f"  Insert: {insert_result['avg_time_ms']:.2f}ms avg ({insert_result['count']} ops)"
            )
            print(f"  Read:   {read_result['avg_time_ms']:.2f}ms avg ({read_result['count']} ops)")
            if insert_result["avg_time_ms"] > 0:
                ratio = read_result["avg_time_ms"] / insert_result["avg_time_ms"]
                print(f"  Ratio (Read/Insert):         {ratio:.2f}x")
            print(f"\nTotal de operações:            {total_ops}")
            print(f"Tempo total:                   {total_time_sec:.3f}s")
            print("=" * 60)

            # Also save summary to CSV
            summary_path = output_path.parent / f"{output_path.stem}_summary{output_path.suffix}"
            with open(summary_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["metric", "value"])
                writer.writeheader()
                writer.writerow(
                    {"metric": "throughput_ops_per_second", "value": f"{throughput:.2f}"}
                )
                writer.writerow(
                    {"metric": "insert_avg_ms", "value": f"{insert_result['avg_time_ms']:.2f}"}
                )
                writer.writerow(
                    {"metric": "read_avg_ms", "value": f"{read_result['avg_time_ms']:.2f}"}
                )
                writer.writerow({"metric": "read_insert_ratio", "value": f"{ratio:.2f}"})
                writer.writerow({"metric": "total_operations", "value": total_ops})
                writer.writerow({"metric": "total_time_seconds", "value": f"{total_time_sec:.3f}"})

            log.info("access_performance_summary_saved", summary_file=str(summary_path))

    log.info("db_access_performance_completed", output_file=str(output_path))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate database access performance metrics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        default="metricas/performance_acesso.csv",
        help="Path to the output CSV file",
    )
    parser.add_argument(
        "-i",
        "--inserts",
        type=int,
        default=50,
        help="Number of insert operations to perform",
    )
    parser.add_argument(
        "-r",
        "--reads",
        type=int,
        default=100,
        help="Number of read operations to perform",
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
    asyncio.run(
        check_access_performance(
            output_file=args.output,
            num_inserts=args.inserts,
            num_reads=args.reads,
        )
    )
