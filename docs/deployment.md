# Guia de Deploy do BotSalinha

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

3. **Edite o `.env` com suas credenciais**

   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   # Opcional ao usar provider Google:
   # GOOGLE_API_KEY=your_google_api_key_here
   ```

   > O provider/modelo ativo é definido no `config.yaml`.

4. **Build e start do bot**

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
- uv

## Configuração Local (Sem Docker)

1. **Instale dependências**

   ```bash
   uv sync
   ```

2. **Crie o arquivo de ambiente**

   ```bash
   cp .env.example .env
   # Edite o .env com suas credenciais
   ```

3. **Execute o bot**

   ```bash
   uv run bot.py
   ```

## Operações com Docker

### Build da imagem

```bash
docker-compose build
```

### Subir o bot

```bash
# Desenvolvimento
docker-compose up -d

# Produção
docker-compose -f docker-compose.prod.yml up -d
```

### Parar o bot

```bash
docker-compose down
```

### Ver logs

```bash
# Seguir logs
docker-compose logs -f

# Últimas 100 linhas
docker-compose logs --tail=100

# Serviço específico
docker-compose logs -f botsalinha
```

### Reiniciar o bot

```bash
docker-compose restart
```

### Atualizar o bot

```bash
# Buscar código mais recente
git pull

# Rebuild e restart
docker-compose up -d --build
```

## Operações de Banco

### Rodar migrações

```bash
docker-compose exec botsalinha uv run alembic upgrade head
```

### Criar backup

```bash
# Usando script de backup
docker-compose exec botsalinha python scripts/backup.py backup

# Ou copiando arquivo do banco
docker cp botsalinha:/app/data/botsalinha.db ./backups/
```

### Listar backups

```bash
docker-compose exec botsalinha python scripts/backup.py list
```

### Restaurar backup

```bash
docker-compose exec botsalinha python scripts/backup.py restore --restore-from /app/backups/botsalinha_backup_20260225_120000.db
```

## Monitoramento

### Health check

```bash
docker-compose ps
```

### Uso de recursos

```bash
docker stats botsalinha
```

### Localização do banco

- **Docker**: `./data/botsalinha.db` (volume montado)
- **Local**: `data/botsalinha.db`

## Solução de Problemas

### Bot não responde aos comandos

1. Verifique se o bot está online

   ```bash
   docker-compose logs | grep "bot_ready"
   ```

2. Verifique token do Discord

   ```bash
   docker-compose exec botsalinha env | grep DISCORD_BOT_TOKEN
   ```

3. Confirme `MESSAGE_CONTENT Intent` habilitado no Discord Developer Portal

### Erros de conexão com banco

1. Verifique se o diretório de dados existe

   ```bash
   ls -la data/
   ```

2. Verifique permissões

   ```bash
   chmod 750 data/
   ```

   > **Nota:** Se o bot roda como um usuário específico (ex: dentro do Docker),
   > ajuste a propriedade do diretório para garantir que apenas o processo
   > correto tenha acesso:
   >
   > ```bash
   > chown -R 1000:1000 data/
   > ```

3. Reinicie o bot

   ```bash
   docker-compose restart
   ```

### Problemas de rate limit

1. Verifique configurações no `.env`

   ```env
   RATE_LIMIT_REQUESTS=10
   RATE_LIMIT_WINDOW_SECONDS=60
   ```

2. Reinicie com novas configurações

   ```bash
   docker-compose up -d
   ```

## Boas Práticas de Segurança

1. **Nunca commitar `.env`** (já está no `.gitignore`)

2. **Use token forte de Discord** gerado no Developer Portal

3. **Restrinja permissões do bot** ao mínimo necessário

4. **Faça backups regulares** com automação no `docker-compose.prod.yml`

5. **Mantenha dependências atualizadas**

   ```bash
   docker-compose build --no-cache
   ```

## Considerações de Produção

1. **Use o compose de produção**

   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Configure rotação de logs** (já previsto no `docker-compose.prod.yml`)

3. **Monitore espaço em disco** (banco cresce com o tempo)

4. **Faça limpeza periódica** (conversas antigas são removidas automaticamente)

5. **Defina estratégia de backup** (backups diários em produção)

## Suporte

Para dúvidas e incidentes:

- Verifique logs: `docker-compose logs -f`
- Consulte [PRD.md](../PRD.md) para contexto de produto
- Consulte [README.md](../README.md) para troubleshooting geral
- Siga [docs/operations.md](operations.md) para runbook e escalonamento
- Consulte [docs/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) para fluxo de desenvolvimento
