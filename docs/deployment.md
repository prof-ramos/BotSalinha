# Guia de Deploy BotSalinha

## Início Rápido (Docker)

### Pré-requisitos

- Docker Engine 20.10+
- Docker Compose 2.0+

### Configuração Inicial

1. **Clone o repositório**
   ```bash
   git clone <repository-url>
   cd BotSalinha
   ```

2. **Crie o arquivo de ambiente**
   ```bash
   cp .env.example .env
   ```

3. **Edite `.env` com suas credenciais**
   ```env
   # Configuração Discord (obrigatório)
   BOTSALINHA_DISCORD__TOKEN=seu_discord_bot_token_aqui

   # Configuração Google AI (obrigatório)
   BOTSALINHA_GOOGLE__API_KEY=sua_google_api_key_aqui

   # Configuração OpenAI (obrigatório para embeddings RAG)
   BOTSALINHA_OPENAI__API_KEY=sua_openai_api_key_aqui

   # Configuração RAG (opcional)
   BOTSALINHA_RAG__ENABLED=true
   BOTSALINHA_RAG__TOP_K=5
   BOTSALINHA_RAG__MIN_SIMILARITY=0.4
   BOTSALINHA_RAG__DOCUMENTS_PATH=data/documents
   ```

4. **Construa e inicie o bot**
   ```bash
   docker-compose up -d
   ```

5. **Verifique os logs**
   ```bash
   docker-compose logs -f
   ```

## Desenvolvimento Local (sem Docker)

### Pré-requisitos

- Python 3.12+
- Gerenciador de pacotes uv

### Configuração

1. **Instale as dependências**
   ```bash
   uv sync
   ```

2. **Crie o arquivo de ambiente**
   ```bash
   cp .env.example .env
   # Edite .env com suas credenciais
   ```

3. **Execute o bot**
   ```bash
   uv run bot.py
   ```

## Operações Docker

### Construindo a imagem
```bash
docker-compose build
```

### Iniciando o bot
```bash
# Desenvolvimento
docker-compose up -d

# Produção
docker-compose -f docker-compose.prod.yml up -d
```

### Parando o bot
```bash
docker-compose down
```

### Visualizando logs
```bash
# Acompanhar logs
docker-compose logs -f

# Últimas 100 linhas
docker-compose logs --tail=100

# Serviço específico
docker-compose logs -f botsalinha
```

### Reiniciando o bot
```bash
docker-compose restart
```

### Atualizando o bot
```bash
# Obter código mais recente
git pull

# Reconstruir e reiniciar
docker-compose up -d --build
```

## Operações de Banco de Dados

### Executando migrações
```bash
docker-compose exec botsalinha uv run alembic upgrade head
```

### Criando um backup
```bash
# Usando o script de backup
docker-compose exec botsalinha python scripts/backup.py backup

# Ou copiar o arquivo de banco de dados
docker cp botsalinha:/app/data/botsalinha.db ./backups/
```

### Listando backups
```bash
docker-compose exec botsalinha python scripts/backup.py list
```

### Restaurando do backup
```bash
docker-compose exec botsalinha python scripts/backup.py restore --restore-from /app/backups/botsalinha_backup_20260225_120000.db
```

## Monitoramento

### Verificação de saúde
```bash
docker-compose ps
```

### Uso de recursos
```bash
docker stats botsalinha
```

### Localização do banco de dados
- **Docker**: `./data/botsalinha.db` (volume montado)
- **Local**: `data/botsalinha.db`

## Solução de Problemas

### Bot não responde aos comandos

1. Verifique se o bot está online
   ```bash
   docker-compose logs | grep "bot_ready"
   ```

2. Verifique o token do Discord
   ```bash
   docker-compose exec botsalinha env | grep BOTSALINHA_DISCORD__TOKEN
   ```

3. Verifique se MESSAGE_CONTENT Intent está habilitado no Discord Developer Portal

### Erros de conexão com banco de dados

1. Verifique se o diretório data existe
   ```bash
   ls -la data/
   ```

2. Verifique as permissões
   ```bash
   chmod 777 data/
   ```

3. Reinicie o bot
   ```bash
   docker-compose restart
   ```

### Problemas de rate limiting

1. Verifique as configurações de rate limit no `.env`
   ```env
   BOTSALINHA_RATE_LIMIT__REQUESTS=10
   BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS=60
   ```

2. Reinicie com as novas configurações
   ```bash
   docker-compose up -d
   ```

## Melhores Práticas de Segurança

1. **Nunca faça commit do arquivo `.env`** - Já está no `.gitignore`

2. **Use um token forte do bot Discord** - Gere no Discord Developer Portal

3. **Restrinja as permissões do bot** - Conceda apenas permissões necessárias no Discord

4. **Backups regulares** - Configure backups automatizados via docker-compose.prod.yml

5. **Mantenha as dependências atualizadas**
   ```bash
   docker-compose build --no-cache
   ```

## Considerações de Produção

1. **Use o arquivo compose de produção**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Configure rotação de logs** - Configurado em docker-compose.prod.yml

3. **Monitore espaço em disco** - O banco de dados cresce com o tempo

4. **Limpeza regular** - Conversas antigas são limpas automaticamente

5. **Estratégia de backup** - Backups automatizados diários em produção

## Referência de Variáveis de Ambiente

Todas as variáveis de ambiente usam o prefixo `BOTSALINHA_`. Configurações aninhadas usam separador de duplo sublinhado (`__`).

### Variáveis Obrigatórias

| Variável | Descrição | Exemplo |
|---|---|---|
| `BOTSALINHA_DISCORD__TOKEN` | Token do bot Discord | `seu_discord_bot_token_aqui` |
| `BOTSALINHA_GOOGLE__API_KEY` | Chave de API do Google Gemini | `sua_google_api_key_aqui` |

### Configuração RAG (Opcional)

| Variável | Descrição | Padrão |
|---|---|---|
| `BOTSALINHA_RAG__ENABLED` | Habilitar funcionalidade RAG | `true` |
| `BOTSALINHA_RAG__TOP_K` | Número de documentos para recuperar | `5` |
| `BOTSALINHA_RAG__MIN_SIMILARITY` | Limiar mínimo de similaridade (0.0-1.0) | `0.4` |
| `BOTSALINHA_RAG__MIN_SIMILARITY_FLOOR` | Piso mínimo de similaridade para fallback | `0.2` |
| `BOTSALINHA_RAG__MIN_SIMILARITY_FALLBACK_DELTA` | Delta para limiar de similaridade de fallback | `0.1` |
| `BOTSALINHA_RAG__MAX_CONTEXT_TOKENS` | Máximo de tokens de contexto | `2000` |
| `BOTSALINHA_RAG__DOCUMENTS_PATH` | Caminho para diretório de documentos | `data/documents` |
| `BOTSALINHA_RAG__EMBEDDING_MODEL` | Modelo de embedding OpenAI | `text-embedding-3-small` |
| `BOTSALINHA_RAG__CONFIDENCE_THRESHOLD` | Limiar de confiança (0.0-1.0) | `0.70` |
| `BOTSALINHA_RAG__RETRIEVAL_MODE` | Estratégia de recuperação | `hybrid_lite` |
| `BOTSALINHA_RAG__RERANK_ENABLED` | Habilitar reranking | `true` |
| `BOTSALINHA_RAG__RETRIEVAL_CANDIDATE_MULTIPLIER` | Multiplicador de candidatos | `12` |
| `BOTSALINHA_RAG__RETRIEVAL_CANDIDATE_MIN` | Mínimo de candidatos | `60` |
| `BOTSALINHA_RAG__RETRIEVAL_CANDIDATE_CAP` | Máximo de candidatos | `240` |
| `BOTSALINHA_OPENAI__API_KEY` | Chave de API OpenAI (obrigatório para embeddings) | `sua_openai_api_key_aqui` |

### Configuração Opcional

| Variável | Descrição | Padrão |
|---|---|---|
| `BOTSALINHA_LOG_LEVEL` | Nível de log (DEBUG/INFO/WARNING/ERROR/CRITICAL) | `INFO` |
| `BOTSALINHA_LOG_FORMAT` | Formato de log (json/text) | `json` |
| `BOTSALINHA_HISTORY__RUNS` | Execuções de conversa no contexto | `3` |
| `BOTSALINHA_RATE_LIMIT__REQUESTS` | Máximo de requisições por janela | `10` |
| `BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS` | Janela de rate limit em segundos | `60` |
| `BOTSALINHA_DATABASE__URL` | URL de conexão do banco de dados | `sqlite:///data/botsalinha.db` |
| `BOTSALINHA_DATABASE__MAX_CONVERSATION_AGE_DAYS` | Idade máxima de conversa em dias | `30` |
| `BOTSALINHA_RETRY__MAX_RETRIES` | Máximo de tentativas de retry | `3` |
| `BOTSALINHA_RETRY__DELAY_SECONDS` | Delay inicial de retry em segundos | `1.0` |
| `BOTSALINHA_APP_ENV` | Ambiente da aplicação | `development` |

Para uma lista completa de todas as variáveis de ambiente, veja `.env.example`.

## Suporte

Para problemas e dúvidas:
- Verifique os logs: `docker-compose logs -f`
- Revise PRD.md para documentação de funcionalidades
- Verifique a seção de solução de problemas em README.md
