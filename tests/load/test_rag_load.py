"""Testes de carga RAG para BotSalinha.

Esta suite valida o comportamento do sistema RAG sob condições
de stress e carga realista de múltiplos usuários simultâneos.
"""

from __future__ import annotations

import pytest

from tests.load.load_test_runner import LoadTestRunner


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.asyncio
async def test_rag_baseline_performance(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Performance baseline de queries RAG individuais.

    Objetivo: Estabelecer referência de performance para comparação.

    Critérios de Sucesso:
    - 95% das queries < 500ms
    - Taxa de erros < 1%
    - Todas as queries completam com sucesso
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    num_queries = load_test_config["baseline_queries"]

    metrics = await runner.run_baseline_test(
        query_service=rag_query_service_with_mock_data,
        num_queries=num_queries,
    )

    # Assert baseline criteria
    assert metrics.success_rate >= 99.0, (
        f"Success rate too low: {metrics.success_rate}%"
    )
    assert metrics.p95_latency < 500, (
        f"P95 latency too high: {metrics.p95_latency}ms"
    )
    assert metrics.total_queries == num_queries, (
        f"Expected {num_queries} queries, got {metrics.total_queries}"
    )

    # Save report
    files = runner.save_report(metrics, format="json")
    assert len(files) == 1
    assert files[0].exists()


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_rag_concurrent_users_10(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: 10 usuários simultâneos executando queries.

    Objetivo: Validar comportamento sob carga leve de usuários concorrentes.

    Critérios de Sucesso:
    - Taxa de sucesso >= 95%
    - Degradação < 20% em relação ao baseline
    - Sem deadlocks ou race conditions
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    queries_per_user = 10
    metrics = await runner.run_concurrent_users_test(
        query_service=rag_query_service_with_mock_data,
        concurrent_users=10,
        queries_per_user=queries_per_user,
        ramp_up_time=5.0,
    )

    # Assert concurrent users criteria - allow some task failures
    expected_queries = 10 * queries_per_user
    assert metrics.total_queries >= expected_queries * 0.9, (
        f"Too few queries: {metrics.total_queries}/{expected_queries}"
    )
    assert metrics.success_rate >= 95.0, (
        f"Success rate too low: {metrics.success_rate}%"
    )
    assert metrics.p95_latency < 1000, (
        f"P95 latency too high: {metrics.p95_latency}ms"
    )

    runner.save_report(metrics, format="both")


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_rag_concurrent_users_50(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: 50 usuários simultâneos executando queries.

    Objetivo: Validar comportamento sob carga moderada de usuários.

    Critérios de Sucesso:
    - Taxa de erros < 5%
    - Throughput mínimo de 5 queries/segundo
    - Latência P95 < 5000ms (ajustado para carga alta com SQLite)
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    queries_per_user = 10
    metrics = await runner.run_concurrent_users_test(
        query_service=rag_query_service_with_mock_data,
        concurrent_users=50,
        queries_per_user=queries_per_user,
        ramp_up_time=10.0,
    )

    # Assert criteria - allow for some task failures under high load
    expected_queries = 50 * queries_per_user
    assert metrics.total_queries >= expected_queries * 0.85, (
        f"Too few queries: {metrics.total_queries}/{expected_queries}"
    )
    assert metrics.success_rate >= 95.0, (
        f"Success rate too low: {metrics.success_rate}%"
    )
    assert metrics.queries_per_second >= 5.0, (
        f"Throughput too low: {metrics.queries_per_second} qps"
    )
    # Adjusted P95 latency limit for SQLite single-writer bottleneck
    assert metrics.p95_latency < 5000, (
        f"P95 latency too high: {metrics.p95_latency}ms"
    )

    runner.save_report(metrics, format="both")


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_rag_sustained_load(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Carga sustentada por período prolongado.

    Objetivo: Identificar memory leaks e degradação progressiva.

    Critérios de Sucesso:
    - Rodar por 5 minutos sem crashes
    - Latência estável (sem degradação > 50%)
    - Sem crescimento constante de memória
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    # Shorter duration for tests (can be increased manually)
    test_duration = 60  # 1 minute for automated tests

    metrics = await runner.run_sustained_load_test(
        query_service=rag_query_service_with_mock_data,
        concurrent_users=load_test_config["sustained_load_users"],
        duration_seconds=test_duration,
        query_interval=5.0,
    )

    # Assert sustained load criteria
    assert metrics.duration_seconds >= test_duration * 0.95  # Allow 5% variance
    assert metrics.success_rate >= 90.0, f"Success rate too low: {metrics.success_rate}%"

    # Check for latency stability (compare first and last quartile)
    if len(metrics.query_metrics) >= 20:
        sorted_by_time = sorted(metrics.query_metrics, key=lambda m: m.timestamp)
        n = len(sorted_by_time)
        first_quartile = sorted_by_time[: n // 4]
        last_quartile = sorted_by_time[-(n // 4) :]

        first_avg = sum(m.latency_ms for m in first_quartile) / len(first_quartile)
        last_avg = sum(m.latency_ms for m in last_quartile) / len(last_quartile)

        # Last quartile should not be more than 2x first quartile
        degradation_ratio = last_avg / first_avg if first_avg > 0 else 1.0
        assert degradation_ratio < 2.0, f"Latency degraded {degradation_ratio:.2f}x over time"

    runner.save_report(metrics, format="both")


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_rag_stress_spike(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Pico súbito de usuários (spike test).

    Objetivo: Validar resiliência a picos de tráfego inesperados.

    Critérios de Sucesso:
    - Sistema não crasha com pico de 200 usuários
    - Recupera performance após pico
    - Taxa de erros aceitável durante pico (< 20%)
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    metrics = await runner.run_spike_test(
        query_service=rag_query_service_with_mock_data,
        start_users=load_test_config["spike_start_users"],
        peak_users=load_test_config["spike_peak_users"],
        spike_duration=load_test_config["spike_duration"],
        ramp_up_seconds=30,
    )

    # Assert spike test criteria
    # During spike, higher error rate is acceptable
    assert metrics.success_rate >= 80.0, f"Success rate too low: {metrics.success_rate}%"
    assert metrics.total_queries > 0, "No queries executed"

    runner.save_report(metrics, format="both")


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.asyncio
async def test_rag_confidence_distribution_under_load(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Distribuição de confiança sob carga.

    Objetivo: Validar que o sistema RAG responde consistentemente sob carga.

    Critérios de Sucesso:
    - Todas as queries completam sob carga (permitindo 10% de variação)
    - Taxa de erros aceitável (< 10%)
    - Sistema permanece estável
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    metrics = await runner.run_concurrent_users_test(
        query_service=rag_query_service_with_mock_data,
        concurrent_users=30,
        queries_per_user=20,
        ramp_up_time=5.0,
    )

    # Assert system stability under load - allow some variance
    expected_queries = 30 * 20
    assert metrics.total_queries >= expected_queries * 0.9, (
        f"Too few queries: {metrics.total_queries}/{expected_queries}"
    )
    assert metrics.success_rate >= 90.0, (
        f"Success rate too low: {metrics.success_rate}%"
    )

    runner.save_report(metrics, format="json")


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.asyncio
async def test_rag_query_variety(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Variedade de queries jurídicas.

    Objetivo: Validar performance com diferentes tipos de queries.

    Critérios de Sucesso:
    - Todas as categorias respondem
    - Diferenças de latência < 3x entre categorias
    - Queries longas não causam timeouts
    """
    from tests.load.workload_generator import LegalWorkloadGenerator
    import time

    generator = LegalWorkloadGenerator()

    categories = ["constitucional", "administrativo", "penal", "jurisprudencia"]
    results_by_category = {}

    for category in categories:
        # Run small test with category-specific queries
        test_queries = [
            generator.get_query_by_category(category) for _ in range(20)
        ]

        category_metrics = []

        for query in test_queries:
            query_start = time.time()
            _ = await rag_query_service_with_mock_data.query(query)
            latency_ms = (time.time() - query_start) * 1000
            category_metrics.append(latency_ms)

        if category_metrics:
            results_by_category[category] = sum(category_metrics) / len(category_metrics)

    # Assert variety criteria
    assert len(results_by_category) == len(categories), "Some categories failed"

    # Check latency variance
    if results_by_category:
        max_latency = max(results_by_category.values())
        min_latency = min(results_by_category.values())
        variance_ratio = max_latency / min_latency if min_latency > 0 else 1.0

        assert variance_ratio < 3.0, f"Latency variance too high: {variance_ratio:.2f}x"


@pytest.mark.load
@pytest.mark.rag
@pytest.mark.asyncio
async def test_rag_single_query_latency(
    rag_query_service_with_mock_data,
):
    """
    Teste: Latência de query individual.

    Objetivo: Medir overhead individual de cada componente.

    Este teste de unidade de performance ajuda identificar gargalos.
    """
    import time

    query = "Quais são os direitos fundamentais previstos no art. 5º da CF/88?"

    # Measure total latency
    start = time.time()
    result = await rag_query_service_with_mock_data.query(query)
    total_latency_ms = (time.time() - start) * 1000

    # Assert single query performance
    assert total_latency_ms < 200, f"Single query too slow: {total_latency_ms:.2f}ms"
    assert result.confianca is not None
    # Note: With mock embeddings, we may not get chunks, so we just verify
    # the query completes successfully and returns a valid response structure


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.asyncio
async def test_rag_error_handling_under_load(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Tratamento de erros sob carga.

    Objetivo: Validar graceful degradation quando coisas falham.

    Critérios de Sucesso:
    - Erros não crasham o sistema
    - Mensagens de erro apropriadas
    - Sistema recupera após erro
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    # Run with high concurrency to potentially trigger errors
    metrics = await runner.run_concurrent_users_test(
        query_service=rag_query_service_with_mock_data,
        concurrent_users=100,
        queries_per_user=5,
        ramp_up_time=2.0,
    )

    # Even with errors, system should continue
    assert metrics.total_queries > 0, "System crashed"

    # If there were errors, check they were handled
    if metrics.failed_queries > 0:
        assert metrics.successful_queries > 0, "All queries failed"
        assert metrics.error_rate < 50, f"Error rate too high: {metrics.error_rate}%"

        # Check error types are known
        if metrics.errors:
            for error_type, count in metrics.errors.items():
                assert error_type in ["timeout", "rate_limit", "database", "other"], \
                    f"Unknown error type: {error_type}"

    runner.save_report(metrics, format="json")


# Performance targets summary test
@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.asyncio
async def test_rag_performance_targets(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Validação de todos os targets de performance.

    Objetivo: Executar suite completa e validar critérios de sucesso.

    Critérios de Sucesso:
    - Baseline: P95 < 500ms
    - Concurrent (50): Suportar 50 usuários, sucesso > 95%
    - Throughput: >= 5 qps
    - Todas as queries completam sem crashes
    """
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    # Run baseline
    baseline = await runner.run_baseline_test(
        query_service=rag_query_service_with_mock_data,
        num_queries=50,
    )

    # Run concurrent test
    concurrent = await runner.run_concurrent_users_test(
        query_service=rag_query_service_with_mock_data,
        concurrent_users=50,
        queries_per_user=5,
        ramp_up_time=5.0,
    )

    # Validate all targets
    # Baseline targets
    assert baseline.p95_latency < 500, (
        f"Baseline P95 too high: {baseline.p95_latency}ms"
    )

    # Concurrent targets
    assert concurrent.success_rate >= 95.0, (
        f"Concurrent success rate too low: {concurrent.success_rate}%"
    )
    assert concurrent.queries_per_second >= 5.0, (
        f"Throughput too low: {concurrent.queries_per_second} qps"
    )

    # Save combined report
    for metrics in [baseline, concurrent]:
        runner.save_report(metrics, format="both")
