"""
Script for generating Database Access Metrics.
Measures latency for SQLite concurrent read/write operations.
"""

import asyncio
import csv
import time
from pathlib import Path

from src.storage.sqlite_repository import get_repository


async def check_access_performance():
    print("Iniciando avaliação de performance de acesso ao DB...")

    repository = get_repository()
    await repository.initialize_database()
    await repository.create_tables()

    results = []

    # Measure Insert Performance
    start_insert = time.perf_counter()
    num_inserts = 50
    inserted_ids = []
    try:
        for i in range(num_inserts):
            conv = await repository.get_or_create_conversation(
                user_id="perf_test_user",
                guild_id="perf_test_guild",
                channel_id=f"perf_test_channel_{i}",
            )
            inserted_ids.append(conv.id)
        insert_duration = time.perf_counter() - start_insert
        avg_insert_ms = (insert_duration / num_inserts) * 1000
    except Exception as e:
        print(f"Erro durante inserções: {e}")
        avg_insert_ms = 0.0

    results.append(
        {
            "operation": "Insert Conversation",
            "count": num_inserts,
            "total_time_ms": round(insert_duration * 1000, 2),
            "avg_time_ms": round(avg_insert_ms, 2),
        }
    )

    # Measure Read Performance
    start_read = time.perf_counter()
    num_reads = 100
    try:
        for _ in range(num_reads):
            await repository.get_by_user_and_guild(
                user_id="perf_test_user", guild_id="perf_test_guild"
            )
        read_duration = time.perf_counter() - start_read
        avg_read_ms = (read_duration / num_reads) * 1000
    except Exception as e:
        print(f"Erro durante leituras: {e}")
        read_duration = 0.0
        avg_read_ms = 0.0

    results.append(
        {
            "operation": "Read Conversations",
            "count": num_reads,
            "total_time_ms": round(read_duration * 1000, 2),
            "avg_time_ms": round(avg_read_ms, 2),
        }
    )

    # Cleanup performance testing data
    for conv_id in inserted_ids:
        await repository.delete_conversation(conv_id)

    output_file = Path("metricas/performance_acesso.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["operation", "count", "total_time_ms", "avg_time_ms"]
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"Métricas de acesso salvas em {output_file}")


if __name__ == "__main__":
    asyncio.run(check_access_performance())
