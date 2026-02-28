"""Executor de testes de carga para RAG."""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.rag.services.query_service import QueryService
from src.rag.models import ConfiancaLevel

from tests.load.metrics import (
    LoadTestMetrics,
    QueryMetrics,
    calculate_percentiles,
)
from tests.load.workload_generator import LegalWorkloadGenerator


class LoadTestRunner:
    """
    Executor de testes de carga para RAG.

    Orquestra execução concorrente de queries, coleta métricas
    e gera relatórios de performance.
    """

    def __init__(self, report_dir: Path | None = None) -> None:
        """
        Inicializar executor de testes.

        Args:
            report_dir: Diretório para salvar relatórios
        """
        self._report_dir = report_dir or Path("tests/load/reports")
        self._report_dir.mkdir(parents=True, exist_ok=True)
        self._generator = LegalWorkloadGenerator()

    async def run_baseline_test(
        self,
        query_service: QueryService,
        num_queries: int = 100,
    ) -> LoadTestMetrics:
        """
        Teste de performance baseline.

        Executa queries sequencialmente para estabelecer referência.

        Args:
            query_service: QueryService configurado
            num_queries: Número de queries a executar

        Returns:
            Métricas agregadas do teste
        """
        test_name = "rag_baseline_performance"
        start_time = time.time()

        query_metrics = []
        queries = self._generator.get_query_batch(num_queries)

        for i, query in enumerate(queries):
            query_start = time.time()
            try:
                result = await query_service.query(query)
                latency_ms = (time.time() - query_start) * 1000

                # Extrair métricas RAG
                similaridades = result.similaridades if result.similaridades else [0.0]
                confidence = result.confianca

                metric = QueryMetrics(
                    query_id=str(uuid.uuid4()),
                    timestamp=query_start,
                    latency_ms=latency_ms,
                    success=True,
                    chunks_retrieved=len(result.chunks_usados),
                    min_similarity=min(similaridades) if similaridades else 0.0,
                    max_similarity=max(similaridades) if similaridades else 0.0,
                    avg_similarity=sum(similaridades) / len(similaridades) if similaridades else 0.0,
                    confidence=confidence,
                )
                query_metrics.append(metric)

            except Exception as e:
                latency_ms = (time.time() - query_start) * 1000
                metric = QueryMetrics(
                    query_id=str(uuid.uuid4()),
                    timestamp=query_start,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(e),
                )
                query_metrics.append(metric)

        end_time = time.time()

        return self._aggregate_metrics(
            test_name=test_name,
            query_metrics=query_metrics,
            start_time=start_time,
            end_time=end_time,
        )

    async def run_concurrent_users_test(
        self,
        query_service: QueryService,
        concurrent_users: int = 50,
        queries_per_user: int = 10,
        ramp_up_time: float = 10.0,
    ) -> LoadTestMetrics:
        """
        Teste de usuários concorrentes.

        Simula múltiplos usuários executando queries em paralelo.

        Args:
            query_service: QueryService configurado
            concurrent_users: Número de usuários simultâneos
            queries_per_user: Queries por usuário
            ramp_up_time: Tempo para atingir carga máxima (segundos)

        Returns:
            Métricas agregadas do teste
        """
        test_name = f"rag_concurrent_users_{concurrent_users}"
        start_time = time.time()

        query_metrics: list[QueryMetrics] = []
        tasks = []

        # Create semaphores for controlled ramp-up
        user_delay = ramp_up_time / concurrent_users if concurrent_users > 0 else 0

        async def user_session(user_id: str) -> list[QueryMetrics]:
            """Simula sessão de um usuário."""
            metrics = []
            queries = self._generator.get_user_session_queries(queries_per_user)

            # Ramp-up delay
            await asyncio.sleep(random.uniform(0, user_delay))

            for query in queries:
                query_start = time.time()
                try:
                    result = await query_service.query(query)
                    latency_ms = (time.time() - query_start) * 1000

                    similaridades = result.similaridades if result.similaridades else [0.0]

                    metric = QueryMetrics(
                        query_id=str(uuid.uuid4()),
                        timestamp=query_start,
                        latency_ms=latency_ms,
                        success=True,
                        chunks_retrieved=len(result.chunks_usados),
                        min_similarity=min(similaridades) if similaridades else 0.0,
                        max_similarity=max(similaridades) if similaridades else 0.0,
                        avg_similarity=sum(similaridades) / len(similaridades) if similaridades else 0.0,
                        confidence=result.confianca,
                        user_id=user_id,
                    )
                    metrics.append(metric)

                    # Small delay between queries
                    await asyncio.sleep(random.uniform(0.05, 0.2))

                except Exception as e:
                    latency_ms = (time.time() - query_start) * 1000
                    metric = QueryMetrics(
                        query_id=str(uuid.uuid4()),
                        timestamp=query_start,
                        latency_ms=latency_ms,
                        success=False,
                        error_message=str(e),
                        user_id=user_id,
                    )
                    metrics.append(metric)

            return metrics

        # Launch all users concurrently
        for i in range(concurrent_users):
            user_id = f"user_{i:04d}"
            task = asyncio.create_task(user_session(user_id))
            tasks.append(task)

        # Wait for all users to complete
        user_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect metrics
        for result in user_results:
            if isinstance(result, Exception):
                continue
            query_metrics.extend(result)

        end_time = time.time()

        return self._aggregate_metrics(
            test_name=test_name,
            query_metrics=query_metrics,
            start_time=start_time,
            end_time=end_time,
        )

    async def run_sustained_load_test(
        self,
        query_service: QueryService,
        concurrent_users: int = 20,
        duration_seconds: int = 300,
        query_interval: float = 10.0,
    ) -> LoadTestMetrics:
        """
        Teste de carga sustentada.

        Mantém carga constante por período prolongado para detectar
        memory leaks e degradação progressiva.

        Args:
            query_service: QueryService configurado
            concurrent_users: Número de usuários constantes
            duration_seconds: Duração do teste (segundos)
            query_interval: Intervalo entre queries por usuário

        Returns:
            Métricas agregadas do teste
        """
        test_name = f"rag_sustained_load_{duration_seconds}s"
        start_time = time.time()

        query_metrics: list[QueryMetrics] = []
        active_tasks: list[asyncio.Task] = []
        stop_event = asyncio.Event()

        async def sustained_user(user_id: str) -> list[QueryMetrics]:
            """Usuário executando queries continuamente."""
            metrics = []
            generator = LegalWorkloadGenerator(seed=int(user_id.split("_")[1]))

            while not stop_event.is_set():
                query_start = time.time()
                query = generator.get_random_query()

                try:
                    result = await query_service.query(query)
                    latency_ms = (time.time() - query_start) * 1000

                    similaridades = result.similaridades if result.similaridades else [0.0]

                    metric = QueryMetrics(
                        query_id=str(uuid.uuid4()),
                        timestamp=query_start,
                        latency_ms=latency_ms,
                        success=True,
                        chunks_retrieved=len(result.chunks_usados),
                        min_similarity=min(similaridades) if similaridades else 0.0,
                        max_similarity=max(similaridades) if similaridades else 0.0,
                        avg_similarity=sum(similaridades) / len(similaridades) if similaridades else 0.0,
                        confidence=result.confianca,
                        user_id=user_id,
                    )
                    metrics.append(metric)

                except Exception as e:
                    latency_ms = (time.time() - query_start) * 1000
                    metric = QueryMetrics(
                        query_id=str(uuid.uuid4()),
                        timestamp=query_start,
                        latency_ms=latency_ms,
                        success=False,
                        error_message=str(e),
                        user_id=user_id,
                    )
                    metrics.append(metric)

                # Wait for query interval or stop event
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=query_interval,
                    )
                    break
                except asyncio.TimeoutError:
                    continue

            return metrics

        # Start sustained users
        for i in range(concurrent_users):
            user_id = f"sustained_user_{i:04d}"
            task = asyncio.create_task(sustained_user(user_id))
            active_tasks.append(task)

        # Run for specified duration
        await asyncio.sleep(duration_seconds)

        # Signal all users to stop
        stop_event.set()

        # Wait for all tasks to complete
        user_results = await asyncio.gather(*active_tasks, return_exceptions=True)

        # Collect metrics
        for result in user_results:
            if isinstance(result, Exception):
                continue
            query_metrics.extend(result)

        end_time = time.time()

        return self._aggregate_metrics(
            test_name=test_name,
            query_metrics=query_metrics,
            start_time=start_time,
            end_time=end_time,
        )

    async def run_spike_test(
        self,
        query_service: QueryService,
        start_users: int = 10,
        peak_users: int = 200,
        spike_duration: int = 60,
        ramp_up_seconds: int = 30,
    ) -> LoadTestMetrics:
        """
        Teste de pico (spike).

        Simula aumento súbito de tráfego para testar resiliência.

        Args:
            query_service: QueryService configurado
            start_users: Usuários iniciais
            peak_users: Pico de usuários
            spike_duration: Duração do pico (segundos)
            ramp_up_seconds: Tempo para atingir o pico

        Returns:
            Métricas agregadas do teste
        """
        test_name = f"rag_spike_test_{peak_users}users"
        start_time = time.time()

        query_metrics: list[QueryMetrics] = []
        all_tasks: list[asyncio.Task] = []
        spike_event = asyncio.Event()

        async def spike_user(user_id: str, is_spike: bool) -> list[QueryMetrics]:
            """Usuário que executa durante o pico."""
            metrics = []
            generator = LegalWorkloadGenerator(seed=int(user_id.split("_")[1]))

            # Spike users wait for event
            if is_spike:
                await spike_event.wait()

            # Execute queries
            queries_to_run = random.randint(3, 8)
            for _ in range(queries_to_run):
                query_start = time.time()
                query = generator.get_random_query()

                try:
                    result = await query_service.query(query)
                    latency_ms = (time.time() - query_start) * 1000

                    similaridades = result.similaridades if result.similaridades else [0.0]

                    metric = QueryMetrics(
                        query_id=str(uuid.uuid4()),
                        timestamp=query_start,
                        latency_ms=latency_ms,
                        success=True,
                        chunks_retrieved=len(result.chunks_usados),
                        min_similarity=min(similaridades) if similaridades else 0.0,
                        max_similarity=max(similaridades) if similaridades else 0.0,
                        avg_similarity=sum(similaridades) / len(similaridades) if similaridades else 0.0,
                        confidence=result.confianca,
                        user_id=user_id,
                    )
                    metrics.append(metric)

                except Exception as e:
                    latency_ms = (time.time() - query_start) * 1000
                    metric = QueryMetrics(
                        query_id=str(uuid.uuid4()),
                        timestamp=query_start,
                        latency_ms=latency_ms,
                        success=False,
                        error_message=str(e),
                        user_id=user_id,
                    )
                    metrics.append(metric)

                await asyncio.sleep(random.uniform(0.1, 0.5))

            return metrics

        # Start initial users
        for i in range(start_users):
            user_id = f"base_user_{i:04d}"
            task = asyncio.create_task(spike_user(user_id, is_spike=False))
            all_tasks.append(task)

        # Wait a bit, then ramp up
        await asyncio.sleep(5)

        # Launch spike users gradually
        spike_tasks = []
        for i in range(peak_users - start_users):
            user_id = f"spike_user_{i:04d}"
            task = asyncio.create_task(spike_user(user_id, is_spike=True))
            spike_tasks.append(task)
            all_tasks.append(task)

            # Gradual ramp-up
            if ramp_up_seconds > 0:
                await asyncio.sleep(ramp_up_seconds / (peak_users - start_users))

        # Trigger spike
        spike_event.set()

        # Let spike run
        await asyncio.sleep(spike_duration)

        # Wait for all to complete
        user_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Collect metrics
        for result in user_results:
            if isinstance(result, Exception):
                continue
            query_metrics.extend(result)

        end_time = time.time()

        return self._aggregate_metrics(
            test_name=test_name,
            query_metrics=query_metrics,
            start_time=start_time,
            end_time=end_time,
        )

    def _aggregate_metrics(
        self,
        test_name: str,
        query_metrics: list[QueryMetrics],
        start_time: float,
        end_time: float,
    ) -> LoadTestMetrics:
        """
        Agrega métricas de queries em métricas de teste.

        Args:
            test_name: Nome do teste
            query_metrics: Lista de métricas individuais
            start_time: Timestamp de início
            end_time: Timestamp de fim

        Returns:
            Métricas agregadas
        """
        successful = [m for m in query_metrics if m.success]
        failed = [m for m in query_metrics if not m.success]

        # Latência percentiles
        latencies = [m.latency_ms for m in successful] if successful else [0.0]
        p50, p95, p99 = calculate_percentiles(latencies, [50, 95, 99])

        # Similaridade stats
        similarities = [m.avg_similarity for m in successful if m.avg_similarity > 0]
        min_sim = min(similarities) if similarities else 0.0
        avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
        max_sim = max(similarities) if similarities else 0.0

        # Confidence distribution
        confidence_counts = defaultdict(int)
        for m in successful:
            confidence_counts[m.confidence] += 1

        # Error summary
        errors = defaultdict(int)
        for m in failed:
            error_type = m.error_message or "unknown"
            # Simplify error type
            if "timeout" in error_type.lower():
                errors["timeout"] += 1
            elif "rate limit" in error_type.lower():
                errors["rate_limit"] += 1
            elif "database" in error_type.lower():
                errors["database"] += 1
            else:
                errors["other"] += 1

        duration = end_time - start_time

        return LoadTestMetrics(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            total_queries=len(query_metrics),
            successful_queries=len(successful),
            failed_queries=len(failed),
            avg_latency=sum(latencies) / len(latencies) if latencies else 0.0,
            p50_latency=p50,
            p95_latency=p95,
            p99_latency=p99,
            min_latency=min(latencies) if latencies else 0.0,
            max_latency=max(latencies) if latencies else 0.0,
            queries_per_second=len(query_metrics) / duration if duration > 0 else 0.0,
            duration_seconds=duration,
            min_similarity=min_sim,
            avg_similarity=avg_sim,
            max_similarity=max_sim,
            confidence_alta=confidence_counts.get(ConfiancaLevel.ALTA, 0),
            confidence_media=confidence_counts.get(ConfiancaLevel.MEDIA, 0),
            confidence_baixa=confidence_counts.get(ConfiancaLevel.BAIXA, 0),
            confidence_sem_rag=confidence_counts.get(ConfiancaLevel.SEM_RAG, 0),
            avg_chunks_per_query=(
                sum(m.chunks_retrieved for m in successful) / len(successful)
                if successful else 0.0
            ),
            query_metrics=query_metrics,
            errors=dict(errors),
        )

    def save_report(
        self,
        metrics: LoadTestMetrics,
        format: str = "both",  # json, csv, both
    ) -> list[Path]:
        """
        Salva relatório do teste em arquivo.

        Args:
            metrics: Métricas do teste
            format: Formato do relatório (json, csv, both)

        Returns:
            Lista de caminhos dos arquivos criados
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files_created = []

        if format in ("json", "both"):
            json_path = self._report_dir / f"{metrics.test_name}_{timestamp}.json"
            with open(json_path, "w") as f:
                import json

                json.dump(metrics.to_dict(), f, indent=2, default=str)
            files_created.append(json_path)

        if format in ("csv", "both"):
            csv_path = self._report_dir / f"{metrics.test_name}_{timestamp}.csv"
            with open(csv_path, "w") as f:
                import csv

                # Write summary
                writer = csv.DictWriter(f, fieldnames=[
                    "test_name", "timestamp", "duration_s", "total_queries",
                    "success", "failed", "error_rate_pct", "qps",
                    "avg_latency_ms", "p95_latency_ms", "p99_latency_ms",
                    "avg_similarity", "alta_confidence_pct",
                    "min_similarity", "max_similarity",
                ], extrasaction='ignore')
                writer.writeheader()
                writer.writerow(metrics.to_csv_row())

                # Write detailed queries
                f.write("\n# Detailed query metrics\n")
                detail_writer = csv.DictWriter(f, fieldnames=[
                    "query_id", "timestamp", "latency_ms", "success",
                    "chunks_retrieved", "avg_similarity", "confidence",
                    "user_id", "error_message", "min_similarity", "max_similarity",
                ], extrasaction='ignore')
                detail_writer.writeheader()
                for qm in metrics.query_metrics:
                    detail_writer.writerow(qm.to_dict())

            files_created.append(csv_path)

        return files_created


__all__ = ["LoadTestRunner"]
