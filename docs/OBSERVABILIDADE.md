# Observabilidade e Métricas

BotSalinha inclui observabilidade abrangente com métricas Prometheus para monitoramento de saúde do sistema, performance e padrões de uso.

## Recursos

### 1. Métricas de Provedor
Rastreie performance de provedores de IA across OpenAI e Google Gemini:

- **Contadores de requisição**: Total de requisições por provedor, modelo e status (sucesso/erro/timeout)
- **Histogramas de latência**: P50, P95, P99 de duração de requisição
- **Uso de tokens**: Contagem de tokens de prompt e conclusão
- **Estimativa de custos**: Rastreamento de custos em USD baseado no uso de tokens
- **Requisições ativas**: Requisições concorrentes atuais

### 2. Métricas do Pipeline RAG
Monitore performance de geração aumentada com recuperação:

- **Latência de query**: Duração de embedding, busca vetorial, reranking e duração total
- **Performance de cache**: Taxas de hit/miss para caches semânticos e de embedding
- **Performance do vector store**: Duração da busca por tipo de armazenamento (SQLite, ChromaDB, Supabase)
- **Métricas de ingestão**: Documentos ingeridos, chunks criados, taxas de erro
- **Métricas de qualidade**: Distribuição de nível de confiança, scores de similaridade

### 3. Métricas de Domínio Legal
Rastreie padrões de consultas legais e efetividade:

- **Distribuição de tipo de query**: artigo, jurisprudência, concurso, geral, código
- **Extração de metadados**: Taxas de sucesso para extração de artigo, lei, banca
- **Efetividade de normalização**: Operações de reescrita de query e impacto

### 4. Métricas do Bot Discord
Monitore saúde do bot e padrões de uso:

- **Uso de comandos**: Contagem de execução de comandos por tipo e status
- **Rate limiting**: Hits de rate limit por usuário/guild
- **Status de conexão**: Conectividade do bot, contagem de guilds, contagem de usuários

### 5. Métricas do Sistema
Saúde geral do sistema:

- **Latência E2E**: Duração de requisição end-to-end por tipo
- **Rastreamento de erros**: Contagem de erros por tipo e componente

## Instalação

Métricas são incluídas na instalação padrão do BotSalinha. Para habilitar:

```bash
# Instalar dependências
uv sync

# Opcional: Instalar FastAPI/uvicorn para endpoint HTTP de métricas
uv add fastapi uvicorn
```

## Uso

### Visualizador de Métricas por Linha de Comando

Visualize métricas atuais no terminal:

```bash
# Ver todas as métricas
python scripts/view_metrics.py

# Ver apenas métricas de provedor
python scripts/view_metrics.py --provider

# Ver apenas métricas RAG
python scripts/view_metrics.py --rag
```

### Endpoint HTTP de Métricas

Inicie o servidor de métricas junto com o bot Discord:

```bash
# Iniciar bot com métricas habilitadas (porta padrão: 9090)
uv run botsalinha --enable-metrics --metrics-port 9090
```

Então acesse:
- **Métricas**: http://localhost:9090/metrics (formato de exposição Prometheus)
- **Health check**: http://localhost:9090/health (retorna "OK")
- **Saúde do database**: http://localhost:9090/health/db (status JSON)

### Integração Prometheus

Configure o Prometheus para raspar métricas do BotSalinha:

```yaml
scrape_configs:
  - job_name: 'botsalinha'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
```

Queries de exemplo do Grafana:

- **Taxa de requisição**: `rate(botsalinha_provider_requests_total[5m])`
- **Latência P95**: `histogram_quantile(0.95, rate(botsalinha_provider_request_duration_seconds_bucket[5m]))`
- **Taxa de cache hit**: `rate(botsalinha_rag_cache_hits_total[5m]) / (rate(botsalinha_rag_cache_hits_total[5m]) + rate(botsalinha_rag_cache_misses_total[5m]))`
- **Taxa de erro**: `rate(botsalinha_system_errors_total[5m])`

## Integração no Código

### Rastreamento de Requisições de Provedor

```python
from src.utils.metrics import track_provider_request, track_tokens

with track_provider_request("openai", "gpt-4o-mini"):
    response = await openai_client.chat(...)
    track_tokens("openai", "gpt-4o-mini", prompt_tokens=100, completion_tokens=200)
```

### Rastreamento de Operações RAG

```python
from src.utils.metrics import track_rag_query, track_confidence, track_similarity

with track_rag_query("embedding"):
    embedding = await embed_service.embed_text(...)

track_confidence("alta")
track_similarity(0.85)
```

### Rastreamento de Performance de Cache

```python
from src.utils.metrics import track_cache_hit, track_cache_miss

if cached:
    track_cache_hit("semantic")
else:
    track_cache_miss("semantic")
```

### Rastreamento de Erros

```python
from src.utils.metrics import track_error

try:
    ...
except APIError as e:
    track_error("APIError", "agent")
```

## Referência de Nomes de Métricas

### Métricas de Provedor
- `botsalinha_provider_requests_total{provider, model, status}`
- `botsalinha_provider_request_duration_seconds{provider, model}`
- `botsalinha_provider_tokens_total{provider, model, token_type}`
- `botsalinha_provider_cost_usd_total{provider, model}`
- `botsalinha_provider_requests_active{provider, model}`

### Métricas RAG
- `botsalinha_rag_query_duration_seconds{component}`
- `botsalinha_rag_cache_hits_total{cache_type}`
- `botsalinha_rag_cache_misses_total{cache_type}`
- `botsalinha_rag_vector_search_duration_seconds{vector_store}`
- `botsalinha_rag_documents_ingested_total{source_type, status}`
- `botsalinha_rag_chunks_created_total{source_type}`
- `botsalinha_rag_confidence_total{confidence}`
- `botsalinha_rag_similarity_score`

### Métricas de Domínio Legal
- `botsalinha_legal_query_type_total{query_type}`
- `botsalinha_legal_metadata_extraction_success_total{metadata_field, status}`
- `botsalinha_legal_query_rewrite_total{rewrite_type, applied}`

### Métricas Discord
- `botsalinha_discord_commands_total{command, status}`
- `botsalinha_discord_rate_limit_hits_total{scope}`
- `botsalinha_discord_bot_connected`
- `botsalinha_discord_guild_count`
- `botsalinha_discord_user_count`

### Métricas do Sistema
- `botsalinha_system_request_duration_seconds{request_type}`
- `botsalinha_system_errors_total{error_type, component}`

## Melhores Práticas

1. **Comece com métricas chave**: Foque em latência, taxa de erro e throughput primeiro
2. **Configure alertas**: Configure alertas em taxas altas de erro ou latência P99
3. **Correlacione métricas**: Use IDs de requisição para rastrear requisições através de componentes
4. **Dashboard**: Crie dashboards do Grafana para visualização
5. **Retenção**: Configure retenção do Prometheus baseado na capacidade de armazenamento

## Solução de Problemas

### Métricas Não Disponíveis

Se métricas mostram como indisponíveis:

```bash
# Instalar prometheus-client
uv add prometheus-client

# Verificar instalação
uv run python -c "from prometheus_client import Counter; print('OK')"
```

### Servidor de Métricas Não Inicia

Se o servidor de métricas falhar ao iniciar:

```bash
# Instalar FastAPI e uvicorn
uv add fastapi uvicorn

# Verificar disponibilidade de porta
netstat -tuln | grep 9090

# Usar porta diferente
uv run botsalinha --enable-metrics --metrics-port 9091
```

### Alto Uso de Memória

Métricas Prometheus podem acumular na memória. Para resetar:

```python
from src.utils.metrics import REGISTRY
REGISTRY.clear()
```

## Melhorias Futuras

- [ ] Rastreamento distribuído com OpenTelemetry
- [ ] Dashboards personalizados para métricas de domínio legal
- [ ] Regras de alerta automatizadas
- [ ] Exportação de métricas para CloudWatch/GCP Monitoring
- [ ] Detecção de anomalias em tempo real
