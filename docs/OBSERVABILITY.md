# Observability and Metrics

BotSalinha includes comprehensive observability with Prometheus metrics for monitoring system health, performance, and usage patterns.

## Features

### 1. Provider Metrics
Track AI provider performance across OpenAI and Google Gemini:

- **Request counters**: Total requests by provider, model, and status (success/error/timeout)
- **Latency histograms**: P50, P95, P99 request duration
- **Token usage**: Prompt and completion token counts
- **Cost estimation**: USD cost tracking based on token usage
- **Active requests**: Current concurrent requests

### 2. RAG Pipeline Metrics
Monitor retrieval-augmented generation performance:

- **Query latency**: Embedding, vector search, reranking, and total duration
- **Cache performance**: Hit/miss rates for semantic and embedding caches
- **Vector store performance**: Search duration by store type (SQLite, ChromaDB, Supabase)
- **Ingestion metrics**: Documents ingested, chunks created, error rates
- **Quality metrics**: Confidence level distribution, similarity scores

### 3. Legal Domain Metrics
Track legal query patterns and effectiveness:

- **Query type distribution**: artigo, jurisprudencia, concurso, geral, codigo
- **Metadata extraction**: Success rates for artigo, lei, banca extraction
- **Normalization effectiveness**: Query rewrite operations and impact

### 4. Discord Bot Metrics
Monitor bot health and usage:

- **Command usage**: Command execution counts by type and status
- **Rate limiting**: Rate limit hits by user/guild
- **Connection status**: Bot connectivity, guild count, user count

### 5. System Metrics
Overall system health:

- **E2E latency**: End-to-end request duration by type
- **Error tracking**: Error counts by type and component

## Installation

Metrics are included in the default BotSalinha installation. To enable:

```bash
# Install dependencies
uv sync

# Optional: Install FastAPI/uvicorn for HTTP metrics endpoint
uv add fastapi uvicorn
```

## Usage

### Command-Line Metrics Viewer

View current metrics in the terminal:

```bash
# View all metrics
python scripts/view_metrics.py

# View only provider metrics
python scripts/view_metrics.py --provider

# View only RAG metrics
python scripts/view_metrics.py --rag
```

### HTTP Metrics Endpoint

Start the metrics server with the Discord bot:

```bash
# Start bot with metrics enabled (default port: 9090)
uv run botsalinha --enable-metrics --metrics-port 9090
```

Then access:
- **Metrics**: http://localhost:9090/metrics (Prometheus exposition format)
- **Health check**: http://localhost:9090/health (returns "OK")
- **Database health**: http://localhost:9090/health/db (JSON status)

### Prometheus Integration

Configure Prometheus to scrape BotSalinha metrics:

```yaml
scrape_configs:
  - job_name: 'botsalinha'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
```

Example Grafana queries:

- **Request rate**: `rate(botsalinha_provider_requests_total[5m])`
- **P95 latency**: `histogram_quantile(0.95, rate(botsalinha_provider_request_duration_seconds_bucket[5m]))`
- **Cache hit rate**: `rate(botsalinha_rag_cache_hits_total[5m]) / (rate(botsalinha_rag_cache_hits_total[5m]) + rate(botsalinha_rag_cache_misses_total[5m]))`
- **Error rate**: `rate(botsalinha_system_errors_total[5m])`

## Integration in Code

### Tracking Provider Requests

```python
from src.utils.metrics import track_provider_request, track_tokens

with track_provider_request("openai", "gpt-4o-mini"):
    response = await openai_client.chat(...)
    track_tokens("openai", "gpt-4o-mini", prompt_tokens=100, completion_tokens=200)
```

### Tracking RAG Operations

```python
from src.utils.metrics import track_rag_query, track_confidence, track_similarity

with track_rag_query("embedding"):
    embedding = await embed_service.embed_text(...)

track_confidence("alta")
track_similarity(0.85)
```

### Tracking Cache Performance

```python
from src.utils.metrics import track_cache_hit, track_cache_miss

if cached:
    track_cache_hit("semantic")
else:
    track_cache_miss("semantic")
```

### Tracking Errors

```python
from src.utils.metrics import track_error

try:
    ...
except APIError as e:
    track_error("APIError", "agent")
```

## Metric Names Reference

### Provider Metrics
- `botsalinha_provider_requests_total{provider, model, status}`
- `botsalinha_provider_request_duration_seconds{provider, model}`
- `botsalinha_provider_tokens_total{provider, model, token_type}`
- `botsalinha_provider_cost_usd_total{provider, model}`
- `botsalinha_provider_requests_active{provider, model}`

### RAG Metrics
- `botsalinha_rag_query_duration_seconds{component}`
- `botsalinha_rag_cache_hits_total{cache_type}`
- `botsalinha_rag_cache_misses_total{cache_type}`
- `botsalinha_rag_vector_search_duration_seconds{vector_store}`
- `botsalinha_rag_documents_ingested_total{source_type, status}`
- `botsalinha_rag_chunks_created_total{source_type}`
- `botsalinha_rag_confidence_total{confidence}`
- `botsalinha_rag_similarity_score`

### Legal Domain Metrics
- `botsalinha_legal_query_type_total{query_type}`
- `botsalinha_legal_metadata_extraction_success_total{metadata_field, status}`
- `botsalinha_legal_query_rewrite_total{rewrite_type, applied}`

### Discord Metrics
- `botsalinha_discord_commands_total{command, status}`
- `botsalinha_discord_rate_limit_hits_total{scope}`
- `botsalinha_discord_bot_connected`
- `botsalinha_discord_guild_count`
- `botsalinha_discord_user_count`

### System Metrics
- `botsalinha_system_request_duration_seconds{request_type}`
- `botsalinha_system_errors_total{error_type, component}`

## Best Practices

1. **Start with key metrics**: Focus on latency, error rate, and throughput first
2. **Set up alerts**: Configure alerts on high error rates or latency P99
3. **Correlate metrics**: Use request IDs to trace requests across components
4. **Dashboard**: Create Grafana dashboards for visualization
5. **Retention**: Configure Prometheus retention based on storage capacity

## Troubleshooting

### Metrics Not Available

If metrics show as unavailable:

```bash
# Install prometheus-client
uv add prometheus-client

# Verify installation
uv run python -c "from prometheus_client import Counter; print('OK')"
```

### Metrics Server Not Starting

If the metrics server fails to start:

```bash
# Install FastAPI and uvicorn
uv add fastapi uvicorn

# Check port availability
netstat -tuln | grep 9090

# Use a different port
uv run botsalinha --enable-metrics --metrics-port 9091
```

### High Memory Usage

Prometheus metrics can accumulate in memory. To reset:

```python
from src.utils.metrics import REGISTRY
REGISTRY.clear()
```

## Future Enhancements

- [ ] Distributed tracing with OpenTelemetry
- [ ] Custom dashboards for legal domain metrics
- [ ] Automated alerting rules
- [ ] Metrics export to CloudWatch/GCP Monitoring
- [ ] Real-time anomaly detection
