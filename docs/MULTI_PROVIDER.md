# Multi-Provider Fallback Architecture

BotSalinha implements a sophisticated multi-provider AI system with automatic fallback, circuit breaker pattern, and provider rotation for maximum reliability and performance.

## Overview

The ProviderManager (`src/core/provider_manager.py`) manages multiple AI providers (OpenAI, Google Gemini) with:

- **Health checks**: Test API calls on initialization
- **Automatic fallback**: Switch to backup provider on failure
- **Circuit breaker**: Temporarily disable failing providers
- **Provider rotation**: Round-robin between healthy providers
- **Metrics tracking**: Success rate, latency, error counts per provider

## Architecture

### Provider States

Each provider has a circuit breaker state:

- **CLOSED**: Normal operation, requests flow through
- **OPEN**: Failed, temporarily disabled (3 consecutive failures)
- **HALF_OPEN**: Testing if recovered after timeout

### Circuit Breaker Pattern

```
Provider Failure → Consecutive Failures ≥ 3 → OPEN State
                                                    ↓
                                            60 second timeout
                                                    ↓
                                              HALF_OPEN State
                                                    ↓
                                    Next successful request → CLOSED State
```

### Provider Selection Flow

1. Get current provider from provider manager
2. Check circuit breaker state
3. If OPEN, check if recovery timeout elapsed → HALF_OPEN
4. If healthy providers available, rotate based on priority
5. Return provider model for request

### Fallback Logic

```
Request → Primary Provider
           ↓
        Success?
           ↓
          Yes → Record Success → Return Response
           ↓
          No → Record Failure → Circuit Breaker Check
                                   ↓
                            Backup Provider Available?
                                   ↓
                              Yes → Switch Provider → Retry
                                   ↓
                              No → Raise Error
```

## Configuration

### Environment Variables

Set API keys in `.env`:

```bash
# OpenAI (primary by default)
BOTSALINHA_OPENAI__API_KEY=sk-...
# Legacy format also supported: OPENAI_API_KEY=sk-...

# Google (fallback by default)
BOTSALINHA_GOOGLE__API_KEY=...
# Legacy format also supported: GOOGLE_API_KEY=...
```

### YAML Configuration

Configure provider priorities in `config.yaml`:

```yaml
model:
  provider: openai  # Default primary provider
  id: gpt-4o-mini
  temperature: 0.7
  # Optional: explicit provider priorities
  provider_priorities:
    - provider: openai
      priority: 0  # Lower = higher priority
    - provider: google
      priority: 1
```

## Usage

### Basic Usage

```python
from src.core.provider_manager import ProviderManager

# Initialize with auto-detected providers
manager = ProviderManager()
await manager.initialize()

# Get healthy provider model
model = manager.get_model()

# Use in agent
agent = Agent(model=model)
response = await agent.arun("Hello")
```

### Provider Statistics

```python
# Get stats for all providers
stats = manager.get_stats()
# {
#   "openai": {
#     "state": "closed",
#     "total_requests": 100,
#     "successful_requests": 98,
#     "failed_requests": 2,
#     "consecutive_failures": 0,
#     "success_rate": 0.98,
#     "avg_latency_ms": 1250.5
#   },
#   "google": {...}
# }

# Get stats for specific provider
openai_stats = manager.get_stats("openai")
```

### Manual Provider Selection

```python
# Get current active provider
current = manager.get_current_provider()
print(f"Using: {current}")  # "openai" or "google"

# Get next healthy provider (rotates if enabled)
provider_config = manager.get_healthy_provider()
```

## Circuit Breaker Configuration

Adjust circuit breaker thresholds in `ProviderManager`:

```python
manager = ProviderManager(
    providers=[...],
    enable_rotation=True,
)

# Circuit breaker thresholds
manager.FAILURE_THRESHOLD = 3  # Consecutive failures before OPEN
manager.RECOVERY_TIMEOUT_MS = 60_000  # Milliseconds before HALF_OPEN
manager.HEALTH_CHECK_TIMEOUT_SECONDS = 10.0  # Health check timeout
```

## Metrics Integration

The ProviderManager integrates with the observability system:

- **Provider request metrics**: Tracked via `track_provider_request()`
- **Error tracking**: Automatic via `track_error()`
- **Latency tracking**: Recorded per request

View provider metrics:

```bash
python scripts/view_metrics.py --provider
```

## Error Handling

### Transient Errors

Provider automatically retries on transient errors (timeout, rate limit):
- TimeoutError → Retry with same provider
- RateLimitError → Immediate fallback to backup
- APIError → Fallback after circuit breaker opens

### Permanent Errors

Permanent errors immediately trigger fallback:
- AuthenticationError → Provider disabled
- ConfigurationError → Provider disabled
- InvalidRequestError → Fallback without retry

### No Healthy Providers

If all providers are unhealthy:

```python
try:
    model = manager.get_model()
except ConfigurationError as e:
    # "No healthy AI providers available"
    # Check API keys and network connectivity
    pass
```

## Best Practices

1. **Configure both providers**: Always have OpenAI and Gemini configured
2. **Monitor provider stats**: Check success rates and latency regularly
3. **Set appropriate priorities**: Use lower priority for backup/expensive providers
4. **Enable rotation**: Distributes load and detects failures early
5. **Handle fallbacks gracefully**: Log provider switches for monitoring

## Troubleshooting

### All Providers Unhealthy

```bash
# Check API keys are set
echo $BOTSALINHA_OPENAI__API_KEY
echo $BOTSALINHA_GOOGLE__API_KEY

# Check provider stats
python -c "
from src.core.provider_manager import ProviderManager
import asyncio
async def check():
    m = ProviderManager()
    await m.initialize()
    print(m.get_stats())
asyncio.run(check())
"
```

### Circuit Breaker Not Recovering

```python
# Manually reset circuit breaker
manager.provider_stats["openai"].state = ProviderState.CLOSED
manager.provider_stats["openai"].consecutive_failures = 0
```

### Provider Not Switching

```python
# Check if rotation is enabled
manager.enable_rotation = True

# Check provider priorities
for p in manager.providers:
    print(f"{p.provider}: priority={p.priority}")
```

## Future Enhancements

- [ ] Weighted round-robin based on latency
- [ ] Predictive pre-warming of backup providers
- [ ] Provider-specific retry policies
- [ ] Cost-aware routing (cheapest healthy provider)
- [ ] Geographic routing (lowest latency provider)
- [ ] Multi-region deployment for disaster recovery
