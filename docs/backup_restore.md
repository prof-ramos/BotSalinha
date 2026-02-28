# Backup e Restore - BotSalinha

Este guia descreve como fazer backup e restore do banco de dados e dos dados RAG do BotSalinha.

## Sumário

- [Backup do Banco de Dados](#backup-do-banco-de-dados)
- [Restore do Banco de Dados](#restore-do-banco-de-dados)
- [Backup dos Dados RAG](#backup-dos-dados-rag)
- [Restore dos Dados RAG](#restore-dos-dados-rag)
- [Automação de Backups](#automação-de-backups)
- [Recuperação de Desastres](#recuperação-de-desastres)

---

## Backup do Banco de Dados

### Localização do Banco

O banco SQLite padrão fica em:
```
data/botsalinha.db
```

### Método 1: Script de Backup (Recomendado)

```bash
# Criar backup com timestamp
uv run python scripts/backup.py backup

# Listar backups disponíveis
uv run python scripts/backup.py list
```

### Método 2: Cópia Manual

```bash
# Criar diretório de backups
mkdir -p backups/db

# Backup com timestamp
cp data/botsalinha.db backups/db/botsalinha_$(date +%Y%m%d_%H%M%S).db

# Backup comprimido
gzip -c data/botsalinha.db > backups/db/botsalinha_$(date +%Y%m%d_%H%M%S).db.gz
```

### Método 3: Backup Online (SQLite)

```bash
# Backup online sem bloquear writes
sqlite3 data/botsalinha.db ".backup 'backups/db/backup_online.db'"
```

---

## Restore do Banco de Dados

### Método 1: Script de Restore (Recomendado)

```bash
# Listar backups disponíveis
uv run python scripts/backup.py list

# Restore de backup específico
uv run python scripts/backup.py restore --restore-from backups/db/botsalinha_20250228_120000.db
```

### Método 2: Cópia Manual

```bash
# PARAR O BOT PRIMEIRO!
pkill -f bot.py

# Fazer backup do banco atual (por segurança)
cp data/botsalinha.db data/botsalinha.db.before_restore

# Restore do backup
cp backups/db/botsalinha_20250228_120000.db data/botsalinha.db

# Verificar integridade
sqlite3 data/botsalinha.db "PRAGMA integrity_check;"

# Reiniciar o bot
uv run bot.py
```

---

## Backup dos Dados RAG

O RAG armazena:
1. **Documentos** (tabela `rag_documents`)
2. **Chunks** (tabela `rag_chunks`) com embeddings BLOB
3. **Documentos originais** (arquivos DOCX/PDF)

### Backup Completo RAG

```bash
# 1. Backup do banco (inclui tabelas RAG)
uv run python scripts/backup.py backup

# 2. Backup dos documentos originais
mkdir -p backups/rag_docs
cp -r /path/to/documentos_originais/* backups/rag_docs/

# OU backup do diretório de legislação
rsync -av /Users/gabrielramos/Downloads/docs_rag/ backups/rag_docs/
```

### Backup Incremental de Documentos RAG

```bash
# Backup apenas de documentos modificados nas últimas 24h
find /path/to/docs_rag -mtime -1 -type f -exec cp {} backups/rag_docs/ \;
```

---

## Restore dos Dados RAG

### Restore Completo

```bash
# 1. Restore do banco (inclui dados RAG)
uv run python scripts/backup.py restore --restore-from backups/db/botsalinha_20250228.db

# 2. Restore dos documentos originais
cp -r backups/rag_docs/* /path/to/documentos_originais/
```

### Reindexação Após Restore

Após restore do banco, os dados RAG já estão prontos. Não é necessário reindexar.

No entanto, se quiser reindexar do zero:

```bash
# Limpar dados RAG
sqlite3 data/botsalinha.db "DELETE FROM rag_chunks; DELETE FROM rag_documents;"

# Reindexar
uv run python scripts/ingest_all_rag.py
```

---

## Automação de Backups

### Crontab (Linux/Mac)

```bash
# Editar crontab
crontab -e

# Adicionar:
# Backup diário às 2h da manhã
0 2 * * * cd /Users/gabrielramos/BotSalinha && uv run python scripts/backup.py backup

# Backup semanal aos domingos às 3h
0 3 * * 0 cd /Users/gabrielramos/BotSalinha && rsync -av --delete data/botsalinha.db /Volumes/backup_drive/botsalinha/

# Limpar backups com mais de 30 dias
0 4 * * * find /Users/gabrielramos/BotSalinha/backups -mtime +30 -delete
```

### Script de Backup Automatizado

```bash
#!/bin/bash
# scripts/auto_backup.sh

BACKUP_DIR="/Users/gabrielramos/BotSalinha/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Criar diretório
mkdir -p "$BACKUP_DIR/db"
mkdir -p "$BACKUP_DIR/rag_docs"

# Backup do banco
echo "[$(date)] Iniciando backup do banco..."
uv run python scripts/backup.py backup

# Backup comprimido
gzip -c data/botsalinha.db > "$BACKUP_DIR/db/botsalinha_$TIMESTAMP.db.gz"

# Backup dos documentos RAG
echo "[$(date)] Iniciando backup dos documentos RAG..."
rsync -av --delete /Users/gabrielramos/Downloads/docs_rag/ "$BACKUP_DIR/rag_docs/"

# Limpar backups antigos
echo "[$(date)] Limpando backups antigos..."
find "$BACKUP_DIR/db" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Backup concluído!"
```

---

## Recuperação de Desastres

### Cenário 1: Banco Corrompido

```bash
# 1. Identificar a corrupção
sqlite3 data/botsalinha.db "PRAGMA integrity_check;"

# 2. Se houver erro, restaurar backup mais recente
uv run python scripts/backup.py restore --restore-from $(ls -t backups/db/*.db | head -1)

# 3. Rodar migrações para garantir schema atualizado
uv run alembic upgrade head
```

### Cenário 2: Perda de Embeddings RAG

Se a coluna `embedding` estiver NULL em todos os chunks:

```bash
# Verificar
sqlite3 data/botsalinha.db "SELECT COUNT(*) FROM rag_chunks WHERE embedding IS NULL;"

# Se todos estiverem NULL, reindexar
uv run python scripts/ingest_all_rag.py
```

### Cenário 3: Restore em Nova Máquina

```bash
# 1. Clonar repositório
git clone <repo-url> BotSalinha
cd BotSalinha

# 2. Instalar dependências
uv sync

# 3. Configurar environment
cp .env.example .env
# Editar .env com suas credenciais

# 4. Restore do banco
mkdir -p data
cp /caminho/para/backup/botsalinha.db data/

# 5. Executar migrações
uv run alembic upgrade head

# 6. Iniciar bot
uv run bot.py
```

---

## Boas Práticas

### Retenção de Backups

| Tipo | Frequência | Retenção | Localização |
|------|-----------|----------|-------------|
| Diário | Todos os dias às 2h | 7 dias | Local |
| Semanal | Domingos às 3h | 4 semanas | Local + Cloud |
| Mensal | 1º dia do mês | 12 meses | Cloud/Armazenamento externo |

### Checklist de Backup

Antes de fazer qualquer alteração drástica:
- [ ] Backup do banco atual
- [ ] Backup dos documentos RAG
- [ ] Testar restore do backup
- [ ] Documentar versão do código (git commit)

### Monitoramento

```bash
# Verificar tamanho do banco
du -sh data/botsalinha.db

# Verificar contagem de chunks RAG
sqlite3 data/botsalinha.db "SELECT COUNT(*) FROM rag_chunks;"

# Verificar integridade
sqlite3 data/botsalinha.db "PRAGMA integrity_check;"
```

---

## Armazenamento Externo

### Google Drive

```bash
# Usar rclone para sync com Google Drive
rclone copy backups/ gdrive:botsalinha-backups/ --progress
```

### AWS S3

```bash
# Usar AWS CLI
aws s3 sync backups/ s3://botsalinha-backups/ --storage-class STANDARD_IA
```

### iCloud (Mac)

```bash
# Criar link simbólico para iCloud
ln -s ~/Library/Mobile\ Documents/com~apple~CloudDocs/BotSalinha-backups backups/icloud
```

---

## Troubleshooting

### Erro: "database is locked"

```bash
# O bot está rodando. Pare primeiro:
pkill -f bot.py

# Ou use backup online (não bloqueia)
sqlite3 data/botsalinha.db ".backup 'backups/backup_online.db'"
```

### Erro: "no such table: rag_chunks"

```bash
# Rodar migrações do RAG
uv run alembic upgrade head
```

### Restore Falha

```bash
# Verificar permissões
ls -la data/botsalinha.db

# Corrigir permissões se necessário
chmod 644 data/botsalinha.db
```

---

## Script Completo de Backup/Restore

Veja `scripts/backup.py` para implementação completa de backup e restore.

Para ver histórico de backups:
```bash
ls -lh backups/db/
```

Para fazer backup completo (DB + RAG docs):
```bash
./scripts/auto_backup.sh
```
