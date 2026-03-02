# Convex Integration - BotSalinha (ARCHIVED)

> **⚠️ NOTICE: This integration is EXPERIMENTAL and not actively maintained.**
>
> **Status:** Archived
> **Date Archived:** 2026-03-01
> **Reason:** Experimental feature not ready for production. The integration is incomplete and the Convex backend is disabled by default.
>
> **Alternative:** Use SQLite (default) or contribute to complete the Convex integration.
>
> If you want to revive this integration, see the "Próximos Passos" section below for remaining work.

---

Este documento descreve a integração do Convex como backend para o BotSalinha.

## Status

- ✅ Convex SDK instalado (convex 0.7.0)
- ✅ ConvexRepository implementado
- ✅ ConvexConfig criado
- ✅ .env.example atualizado
- ✅ Exemplo de uso criado
- ✅ Backend deployado (beaming-mongoose-330)
- ⚠️ **NÃO está em produção** - SQLite é o padrão
- ⚠️ **Integração incompleta** - ver "Próximos Passos"

## Configuração

### 1. Variáveis de Ambiente

Adicione ao `.env`:

```bash
# Convex Backend
BOTSALINHA_CONVEX__ENABLED=true
BOTSALINHA_CONVEX__URL=https://beaming-mongoose-330.convex.cloud
BOTSALINHA_CONVEX__DEPLOY_KEY=prod:beaming-mongoose-330|...
```

### 2. Usar ConvexRepository

```python
from src.config.convex_config import ConvexConfig
from src.storage.convex_repository import ConvexRepository

# Configurar
config = ConvexConfig(
    url="https://beaming-mongoose-330.convex.cloud",
    enabled=True,
)

# Inicializar
repo = ConvexRepository(config.url)

# Usar
conversation = await repo.get_or_create_conversation(
    user_id="123",
    guild_id="456",
    channel_id="789",
)
```

### 3. Híbrido SQLite + Convex (Recomendado)

```python
from src.config.convex_config import convex_config
from src.storage.sqlite_repository import SQLiteRepository
from src.storage.convex_repository import ConvexRepository

# Escolher backend baseado na configuração
if convex_config.enabled and convex_config.is_configured:
    repo = ConvexRepository(convex_config.url)
else:
    repo = SQLiteRepository()
```

## Schema Convex

### Tabelas

- **conversations**: Conversas do Discord
- **messages**: Mensagens + embeddings
- **documents**: Documentos para RAG
- **embeddingCache**: Cache de embeddings

### Functions

#### conversations
- `create` - Criar conversa
- `getById` - Buscar por ID
- `getByUserAndGuild` - Buscar por usuário/guild
- `getOrCreate` - Buscar ou criar
- `update` - Atualizar
- `remove` - Deletar
- `cleanupOld` - Limpar antigas

#### messages
- `create` - Criar mensagem
- `getById` - Buscar por ID
- `getByConversation` - Buscar por conversa
- `getHistory` - Histórico para LLM
- `update` - Atualizar
- `remove` - Deletar
- `deleteByConversation` - Deletar todas da conversa

#### documents
- `create` - Criar documento
- `list` - Listar documentos
- `search` - Busca textual
- `vectorSearch` - Busca vetorial (RAG)
- `stats` - Estatísticas

## Exemplo Completo

Veja `examples/convex_example.py` para um exemplo completo de uso.

## Testar

```bash
# Ativar ambiente virtual
cd /root/projetos/BotSalinha
source .venv/bin/activate

# Executar exemplo
python examples/convex_example.py
```

## Próximos Passos (Para reviver esta integração)

1. **Integrar no BotSalinhaBot**
   - Modificar `src/core/discord.py` para usar ConvexRepository
   - Adicionar fallback para SQLite

2. **Implementar RAG**
   - Indexar documentos jurídicos
   - Configurar embeddings
   - Usar vector search

3. **Sincronização**
   - Migrar dados do SQLite para Convex
   - Manter sincronização bidirecional

4. **Monitoramento**
   - Adicionar logs
   - Métricas de performance
   - Alertas de erro

5. **Testes**
   - Escrever testes unitários para ConvexRepository
   - Testes de integração com backend Convex
   - Testes de fallback para SQLite

## Links

- **Convex Dashboard**: https://dashboard.convex.dev
- **Projeto**: beaming-mongoose-330 (test deployment)
- **Documentação Convex**: https://docs.convex.dev
- **SDK Python**: https://pypi.org/project/convex/

## Troubleshooting

### Erro de conexão

```python
# Verificar se Convex está acessível
import requests
response = requests.get("https://beaming-mongoose-330.convex.cloud")
print(response.status_code)
```

### Erro de autenticação

```bash
# Verificar deploy key
echo $BOTSALINHA_CONVEX__DEPLOY_KEY
```

### Fallback para SQLite

```python
try:
    repo = ConvexRepository(config.url)
    # Testar conexão
    await repo.get_conversation_by_id("test")
except Exception as e:
    print(f"Convex error: {e}, falling back to SQLite")
    repo = SQLiteRepository()
```
