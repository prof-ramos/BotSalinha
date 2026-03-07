# Arquitetura de Multi-Provider com Fallback

BotSalinha implementa um sistema sofisticado de múltiplos provedores de IA com fallback automático, padrão circuit breaker e rotação de provedores para máxima confiabilidade e performance.

## Visão Geral

O ProviderManager (`src/core/provider_manager.py`) gerencia múltiplos provedores de IA (OpenAI, Google Gemini) com:

- **Health checks**: Testes de chamada de API ao inicializar
- **Fallback automático**: Alterna para provedor de backup em caso de falha
- **Circuit breaker**: Desabilita temporariamente provedores com falhas
- **Rotação de provedores**: Round-robin entre provedores saudáveis
- **Tracking de métricas**: Taxa de sucesso, latência, contagem de erros por provedor

## Arquitetura

### Estados do Provedor

Cada provedor tem um estado de circuit breaker:

- **CLOSED**: Operação normal, requisições fluem normalmente
- **OPEN**: Falhou, temporariamente desabilitado (3 falhas consecutivas)
- **HALF_OPEN**: Testando se recuperou após timeout

### Padrão Circuit Breaker

```
Falha do Provedor → Falhas Consecutivas ≥ 3 → Estado OPEN
                                                    ↓
                                            Timeout de 60 segundos
                                                    ↓
                                              Estado HALF_OPEN
                                                    ↓
                                    Próximo request bem-sucedido → Estado CLOSED
```

### Fluxo de Seleção de Provedor

1. Obter provedor atual do provider manager
2. Verificar estado do circuit breaker
3. Se OPEN, verificar se timeout de recuperação passou → HALF_OPEN
4. Se provedores saudáveis disponíveis, rotacionar baseado em prioridade
5. Retornar modelo de provedor para requisição

### Lógica de Fallback

```
Requisição → Provedor Primário
           ↓
        Sucesso?
           ↓
          Sim → Registrar Sucesso → Retornar Resposta
           ↓
          Não → Registrar Falha → Verificar Circuit Breaker
                                   ↓
                            Provedor de Backup Disponível?
                                   ↓
                              Sim → Trocar Provedor → Retentar
                                   ↓
                              Não → Lançar Erro
```

## Configuração

### Variáveis de Ambiente

Configure chaves de API no `.env`:

```bash
# OpenAI (primário por padrão)
BOTSALINHA_OPENAI__API_KEY=sk-...
# Formato legado também suportado: OPENAI_API_KEY=sk-...

# Google (fallback por padrão)
BOTSALINHA_GOOGLE__API_KEY=...
# Formato legado também suportado: GOOGLE_API_KEY=...
```

### Configuração YAML

Configure prioridades de provedores em `config.yaml`:

```yaml
model:
  provider: openai  # Provedor primário padrão
  id: gpt-4o-mini
  temperature: 0.7
  # Opcional: prioridades explícitas de provedores
  provider_priorities:
    - provider: openai
      priority: 0  # Menor = maior prioridade
    - provider: google
      priority: 1
```

## Uso

### Uso Básico

```python
from src.core.provider_manager import ProviderManager

# Inicializar com provedores auto-detectados
manager = ProviderManager()
await manager.initialize()

# Obter modelo de provedor saudável
model = manager.get_model()

# Usar no agente
agent = Agent(model=model)
response = await agent.arun("Olá")
```

### Estatísticas do Provedor

```python
# Obter estatísticas de todos os provedores
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

# Obter estatísticas de provedor específico
openai_stats = manager.get_stats("openai")
```

### Seleção Manual de Provedor

```python
# Obter provedor ativo atual
current = manager.get_current_provider()
print(f"Usando: {current}")  # "openai" ou "google"

# Obter próximo provedor saudável (rotaciona se habilitado)
provider_config = manager.get_healthy_provider()
```

## Configuração do Circuit Breaker

Ajuste limites do circuit breaker no `ProviderManager`:

```python
manager = ProviderManager(
    providers=[...],
    enable_rotation=True,
)

# Limites do circuit breaker
manager.FAILURE_THRESHOLD = 3  # Falhas consecutivas antes de OPEN
manager.RECOVERY_TIMEOUT_MS = 60_000  # Milissegundos antes de HALF_OPEN
manager.HEALTH_CHECK_TIMEOUT_SECONDS = 10.0  # Timeout de health check
```

## Integração com Métricas

O ProviderManager integra com o sistema de observabilidade:

- **Métricas de requisição**: Rastreadas via `track_provider_request()`
- **Rastreamento de erros**: Automático via `track_error()`
- **Rastreamento de latência**: Registrado por requisição

Ver métricas de provedor:

```bash
python scripts/view_metrics.py --provider
```

## Tratamento de Erros

### Erros Transientes

Provedor retoma automaticamente em erros transientes (timeout, rate limit):
- TimeoutError → Tenta novamente com mesmo provedor
- RateLimitError → Fallback imediato para backup
- APIError → Fallback após circuit breaker abrir

### Erros Permanentes

Erros permanentes acionam fallback imediatamente:
- AuthenticationError → Provedor desabilitado
- ConfigurationError → Provedor desabilitado
- InvalidRequestError → Fallback sem retry

### Nenhum Provedor Saudável

Se todos os provedores não estiverem saudáveis:

```python
try:
    model = manager.get_model()
except ConfigurationError as e:
    # "Nenhum provedor de IA saudável disponível"
    # Verifique chaves de API e conectividade de rede
    pass
```

## Melhores Práticas

1. **Configure ambos provedores**: Tenha sempre OpenAI e Gemini configurados
2. **Monitore estatísticas do provedor**: Verifique taxas de sucesso e latência regularmente
3. **Defina prioridades apropriadas**: Use prioridade menor para provedores de backup/mais caros
4. **Habilite rotação**: Distribui carga e detecta falhas mais cedo
5. **Trate fallbacks graciosamente**: Registre trocas de provedor para monitoramento

## Solução de Problemas

### Todos os Provedores Não Saudáveis

```bash
# Verificar se chaves de API estão configuradas
echo $BOTSALINHA_OPENAI__API_KEY
echo $BOTSALINHA_GOOGLE__API_KEY

# Verificar estatísticas do provedor
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

### Circuit Breaker Não Recupera

```python
# Resetar manualmente o circuit breaker
manager.provider_stats["openai"].state = ProviderState.CLOSED
manager.provider_stats["openai"].consecutive_failures = 0
```

### Provedor Não Troca

```python
# Verificar se rotação está habilitada
manager.enable_rotation = True

# Verificar prioridades dos provedores
for p in manager.providers:
    print(f"{p.provider}: priority={p.priority}")
```

## Melhorias Futuras

- [ ] Round-robin ponderado baseado em latência
- [ ] Pré-aquecimento preditivo de provedores de backup
- [ ] Políticas de retry específicas por provedor
- [ ] Roteamento consciente de custos (provedor saudável mais barato)
- [ ] Roteamento geográfico (provedor de menor latência)
- [ ] Deploy multi-regional para recuperação de desastres
