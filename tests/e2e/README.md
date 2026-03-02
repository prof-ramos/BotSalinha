# Testes E2E - Fast Path Optimization

## Visão Geral
Descrição dos testes e2e para Fast Path.

## Testes Disponíveis

### test_e2e_fast_path.py
Testes end-to-end para validação da otimização Fast Path.

#### Testes Implementados
1. **test_fast_path_cache_hit_skips_history_load**
   - Valida: Histórico NÃO carregado em cache hit
   - SLO: N/A (comportamental)

2. **test_fast_path_cache_miss_loads_history**
   - Valida: Histórico É carregado em cache miss
   - SLO: N/A (comportamental)

3. **test_fast_path_latency_slo_cache_hit**
   - Valida: Latência ≤100ms em cache hit
   - SLO: ≤100ms

4. **test_fast_path_multiple_cache_hits**
   - Valida: Múltiplos hits consecutivos
   - SLO: ≤100ms cada

5. **test_fast_path_cache_invalidation**
   - Valida: Comportamento após expiração TTL
   - SLO: N/A (comportamental)

## Como Executar
```bash
# Executar todos os testes e2e de Fast Path
pytest tests/e2e/test_e2e_fast_path.py -v -m "e2e and slow"

# Executar com coverage
pytest tests/e2e/test_e2e_fast_path.py --cov=src.core.agent --cov-report=term-missing

# Executar apenas testes de latência
pytest tests/e2e/test_e2e_fast_path.py -k "latency" -v
```

## Requisitos
- Banco de produção com documentos indexados (data/botsalinha.db)
- OPENAI_API_KEY configurado em .env
- 4637 chunks indexados de 16 documentos jurídicos

## SLOs (Service Level Objectives)
- Cache hit latência: ≤100ms
- Cache miss latência: ≤30s

## Referências
- Implementação: src/core/agent.py
- Plano: .omc/plans/fast-path-e2e-tests.md