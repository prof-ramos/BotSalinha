# Manual de Operações do BotSalinha

## Verificação Rápida de Saúde (60s)

1. Verifique os containers:

   ```bash
   docker-compose ps
   ```

2. Verifique os logs recentes:

   ```bash
   docker-compose logs --tail=50
   ```

3. Valide a resposta do bot no Discord com `!ping`.

## Comandos do Bot

### Comandos de Usuário

| Comando           | Descrição                                | Exemplo                    |
| ----------------- | ---------------------------------------- | -------------------------- |
| `!ask <pergunta>` | Faz uma pergunta sobre direito/concursos | `!ask O que é prescrição?` |
| `!ping`           | Verifica a latência do bot               | `!ping`                    |
| `!ajuda`          | Exibe a mensagem de ajuda                | `!ajuda`                   |
| `!info`           | Exibe informações do bot                 | `!info`                    |
| `!limpar`         | Limpa o histórico de conversa no canal   | `!limpar`                  |

### Modos de Interação Automática

O bot oferece três modos de interação:

1. **Comandos com Prefixo** - Modo tradicional (`!ask`, `!ping`, etc.)
2. **Canal IA** - Modo automático de canal dedicado
3. **DM (Direct Message)** - Modo automático de mensagens privadas

Apenas os comandos com prefixo requerem a formatação específica. Os outros dois modos respondem a qualquer mensagem imediatamente.

## Operações Diárias

### Monitoramento

**Verificar status do bot:**

```bash
docker-compose ps
docker-compose logs --tail=50
```

**Verificar estatísticas do rate limiter:**

```python
# No shell Python
from src.middleware.rate_limiter import rate_limiter
print(rate_limiter.get_stats())
```

**Verificar tamanho do banco:**

```bash
ls -lh data/botsalinha.db
```

### Manutenção

**Limpar conversas antigas:**

```bash
docker-compose exec botsalinha python -c "
import asyncio
from src.storage.factory import create_repository

async def cleanup():
    async with create_repository() as repo:
        count = await repo.cleanup_old_conversations(days=30)
        print(f'Deleted {count} old conversations')

asyncio.run(cleanup())
"
```

**Resetar rate limit de um usuário específico:**

```python
# No shell Python
from src.middleware.rate_limiter import rate_limiter
rate_limiter.reset_user(user_id="123456789", guild_id="987654321")
```

**Resetar todos os rate limits:**

```python
from src.middleware.rate_limiter import rate_limiter
rate_limiter.reset_all()
```

## Backup e Recuperação

### Backup Manual

```bash
# Usando script de backup
docker-compose exec botsalinha python scripts/backup.py backup

# Ou cópia direta do arquivo
cp data/botsalinha.db backups/botsalinha_manual_$(date +%Y%m%d_%H%M%S).db
```

### Backups Agendados

Backups diários automáticos estão configurados em `docker-compose.prod.yml`:

- Execução diária às 02:00 UTC
- Armazenamento em `./backups/`
- Retenção de 7 dias (configurável)

### Procedimento de Recuperação

1. **Pare o bot**

   ```bash
   docker-compose down
   ```

2. **Restaure o backup**

   ```bash
   cp backups/botsalinha_backup_YYYYMMDD_HHMMSS.db data/botsalinha.db
   ```

3. **Suba o bot novamente**

   ```bash
   docker-compose up -d
   ```

4. **Valide**

   ```bash
   docker-compose logs -f
   ```

## Solução de Problemas

### Bot Offline

**Sintomas:** Comandos não respondem, bot aparece offline no Discord.

**Diagnóstico:**

```bash
# Status dos containers
docker-compose ps

# Logs recentes
docker-compose logs --tail=100

# Erros
docker-compose logs | grep -i error
```

**Soluções:**

1. Reiniciar container: `docker-compose restart`
2. Verificar token do Discord no `.env`
3. Verificar se o bot está convidado ao servidor
4. Confirmar `MESSAGE_CONTENT Intent` habilitado

---

## Operação dos Modos de Interacao

### Configuração do Canal IA

Para habilitar o Canal IA:

```bash
# Adicionar ao .env
DISCORD__CANAL_IA_ID=123456789012345678

# Reiniciar bot
docker-compose restart
```

Obtenha o ID do canal:
1. No Discord, clique com botão direito no canal → "Copiar ID do Canal"
2. (Ou use botões de desenvolvedor se necessário)

### Verificação de Funcionamento

```bash
# Enviar mensagem de teste no canal IA
# Verificar logs para confirmar processamento
docker-compose logs --tail=50 | grep "message_handled"

# Verificar por tipo de interação
docker-compose logs | grep "is_dm=true"      # DMs
docker-compose logs | grep "is_dm=false"     # Canal IA
```

### Troubleshooting de Modos de Interação

**Problema:** Bot não responde no canal IA

**Possíveis causas:**
- ID do canal incorreto
- Bot não tem permissões no canal
- `DISCORD__CANAL_IA_ID` não configurado
- Canal não existe ou foi deletado

**Soluções:**
```bash
# Verificar configuração
docker-compose exec botsalinha env | grep CANAL_IA

# Verificar permissões do bot
# No Discord: Bot → Configurações → Permissões do Servidor
```

**Problema:** Bot não responde DMs

**Possíveis causas:**
- `MESSAGE_CONTENT_INTENT` não habilitado
- Bot foi bloqueado pelo usuário

**Soluções:**
```bash
# Verificar MESSAGE_CONTENT_INTENT
docker-compose exec botsalinha env | grep MESSAGE_CONTENT

# Habilitar no Discord Developer Portal
# App Settings → Bot → Message Content Intent
```

**Problema:** Rate limit muito agressivo

**Soluções:**
```bash
# Ajustar no .env
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60

# Reiniciar
docker-compose up -d
```

### Monitoramento de Modos de Interação

```bash
# Verificar mensagens processadas por modo
docker-compose logs | grep "is_dm=true"  # DMs
docker-compose logs | grep "is_dm=false" # Canal IA

# Estatísticas de uso por modo
docker-compose logs | jq 'select(.message_handled) | .is_dm'

# Monitorar rate limits específicos
docker-compose logs | grep "rate_limit"
```

### Backup e Restauracao de Conversas

```bash
# Backup específico de conversas do canal IA/DM
docker-compose exec botsalinha python -c "
from src.storage.factory import create_repository
import asyncio

async def backup_conversations():
    async with create_repository() as repo:
        # Conversas do canal IA
        convs = await repo.get_conversations_by_guild(guild_id='123')
        # Conversas em DM
        dms = await repo.get_dm_conversations()
        print(f'Canal IA: {len(convs)} conversas')
        print(f'DMs: {len(dms)} conversas')

asyncio.run(backup_conversations())
"
```

**Note:** Para backups completos, continue usando o script `scripts/backup.py`.

### Validação Funcional

```bash
# Testar Canal IA
docker-compose logs --tail=10 | grep -E "(message_handled|canal_ia)"

# Testar DMs
docker-compose logs --tail=10 | grep -E "(message_handled|is_dm=true)"

# Verificar rate limits
docker-compose logs --tail=10 | grep "rate_limit_exceeded"
```

### Banco Bloqueado

**Sintomas:** Erros "database is locked".

**Diagnóstico:**

```bash
# Verificar múltiplas instâncias
docker-compose ps
```

**Soluções:**

1. Garantir apenas uma instância rodando
2. Conferir WAL habilitado: `docker-compose exec botsalinha python -c "from src.storage.factory import create_repository; import asyncio; asyncio.run(create_repository().__aenter__())"` (diagnóstico apenas)
3. Reiniciar bot: `docker-compose restart`

### Alto Uso de Memória

**Sintomas:** Container consumindo memória excessiva.

**Diagnóstico:**

```bash
docker stats botsalinha
```

**Soluções:**

1. Limpar conversas antigas
2. Reiniciar bot: `docker-compose restart`
3. Verificar possíveis vazamentos nos logs

### Problemas de Rate Limit

**Sintomas:** Usuários sendo limitados cedo demais.

**Diagnóstico:**

```bash
# Configurações atuais
docker-compose exec botsalinha env | grep RATE_LIMIT
```

**Soluções:**

1. Ajustar no `.env`:
   ```env
   RATE_LIMIT_REQUESTS=20
   RATE_LIMIT_WINDOW_SECONDS=60
   ```
2. Reiniciar:

   ```bash
   docker-compose up -d
   ```

3. Resetar limites de usuários afetados, se necessário

## Troca de Provider de IA (OpenAI ↔ Google)

BotSalinha suporta dois providers de IA: **OpenAI** (padrão) e **Google AI**.
O provider ativo é definido exclusivamente no `config.yaml`.

### Procedimento

1. **Garanta que a API key está configurada** no `.env`:

   ```env
   # Para OpenAI:
   OPENAI_API_KEY=sk-...
   # Para Google AI:
   GOOGLE_API_KEY=AIza...
   ```

2. **Edite o `config.yaml`** alterando `model.provider` e `model.id`:

   ```yaml
   # Para OpenAI (padrão):
   model:
     provider: openai
     id: gpt-4o-mini

   # Para Google AI:
   model:
     provider: google
     id: gemini-2.0-flash
   ```

3. **Reinicie o bot**:

   ```bash
   docker-compose restart
   # ou localmente:
   uv run python -m src.main
   ```

4. **Valide** enviando `!info` no Discord e conferindo provider/modelo ativo.

### Validação Pós-Troca

```bash
# Rodar testes relacionados a provider:
uv run pytest -k "provider or config" -v

# Checar logs de inicialização:
docker-compose logs --tail=20 | grep "agent_wrapper_initialized"
```

### Problemas Comuns

| Sintoma                         | Causa                                 | Correção                  |
| ------------------------------- | ------------------------------------- | ------------------------- |
| Bot não sobe                    | API key ausente para o provider ativo | Adicionar chave no `.env` |
| `ConfigurationError` no startup | Provider inválido no `config.yaml`    | Usar `openai` ou `google` |
| Erros 401/403                   | API key expirada ou inválida          | Regenerar chave           |

> **Nota:** O provider **nunca** é definido por variável de ambiente. Apenas `config.yaml` controla o provider ativo.

## Verificações de Saúde

### Verificação Automatizada

```bash
# Verificar processo do bot
docker-compose exec botsalinha pgrep -f bot.py

# Verificar acesso ao banco
docker-compose exec botsalinha python -c "
from src.storage.factory import create_repository
import asyncio

async def check_db():
    async with create_repository() as repo:
        print('Database OK')

asyncio.run(check_db())
"

# Verificar conexão com Discord
docker-compose logs | grep "bot_ready"
```

### Verificação Manual

1. Envie o comando `!ping` no Discord
2. Verifique o tempo de resposta
3. Confirme que o bot está online

## Métricas para Monitorar

| Métrica           | Descrição                            | Limite de Alerta |
| ----------------- | ------------------------------------ | ---------------- |
| Uptime do bot     | Tempo desde último restart           | < 24h            |
| Tempo de resposta | Latência do `!ping`                  | > 5s             |
| Tamanho do banco  | Tamanho do arquivo SQLite            | > 1GB            |
| Taxa de erro      | Erros em logs / total de requisições | > 5%             |
| Usuários ativos   | Usuários com conversas em 24h        | -                |

## Procedimentos de Escalonamento

### Incidentes Críticos (Bot fora do ar)

1. Checar logs: `docker-compose logs --tail=200`
2. Reiniciar bot: `docker-compose restart`
3. Se falhar, rebuild: `docker-compose up -d --build`
4. Escalar para administrador se persistir por mais de 15 minutos

### Incidentes de Dados

1. Parar bot: `docker-compose down`
2. Backup emergencial: `cp data/botsalinha.db data/emergency_backup.db`
3. Restaurar último backup válido
4. Subir bot: `docker-compose up -d`
5. Validar funcionamento

## Contato

- **Repositório**: [https://github.com/prof-ramos/BotSalinha](https://github.com/prof-ramos/BotSalinha)
- **Documentação**: [README.md](../README.md), [PRD.md](../PRD.md), [Guia de Deploy](deployment.md)
- **Issues**: [https://github.com/prof-ramos/BotSalinha/issues](https://github.com/prof-ramos/BotSalinha/issues)
