# Supabase Ingestion Runbook

## Objetivo

Executar a carga de documentos DOCX para Supabase de forma resiliente e contínua, sem depender do terminal aberto.

## Scripts

- Start (background persistente via `tmux`):
  - `scripts/start_supabase_ingest_tmux.sh`
- Status:
  - `scripts/status_supabase_ingest_tmux.sh`
- Stop:
  - `scripts/stop_supabase_ingest_tmux.sh`
- Worker:
  - `scripts/ingest_docs_to_supabase.py`

## Pré-requisitos

1. Banco local SQLite acessível em `BOTSALINHA_DATABASE__URL`.
2. Credenciais válidas:
   - `OPENAI_API_KEY`
   - `BOTSALINHA_RAG__SUPABASE__URL`
   - `BOTSALINHA_RAG__SUPABASE__SERVICE_KEY`
3. Tabelas no Supabase já criadas:
   - `rag_documents`
   - `rag_chunks`
   - `content_links`

## Start

```bash
cd /root/BotSalinha

export OPENAI_API_KEY='...'
export BOTSALINHA_RAG__SUPABASE__URL='https://supabase.proframos.com'
export BOTSALINHA_RAG__SUPABASE__SERVICE_KEY='...'
export BOTSALINHA_DATABASE__URL='sqlite:////root/BotSalinha/data/botsalinha.db'

# opcionais
export SUPABASE_BATCH_SIZE=100
export MAX_DOCS=0
export INGEST_CHECKPOINT_FILE='/root/BotSalinha/data/ingest_supabase_checkpoint.jsonl'
export INGEST_ERROR_LOG_FILE='/root/BotSalinha/data/ingest_supabase_errors.log'

/root/BotSalinha/scripts/start_supabase_ingest_tmux.sh
```

## Monitoramento

```bash
# status da sessão tmux
SESSION_NAME=supabase_ingest /root/BotSalinha/scripts/status_supabase_ingest_tmux.sh

# log em tempo real
tail -f /root/BotSalinha/data/ingest_supabase_tmux.log

# anexar sessão
tmux attach -t supabase_ingest
```

## Stop

```bash
SESSION_NAME=supabase_ingest /root/BotSalinha/scripts/stop_supabase_ingest_tmux.sh
```

## Retomada automática

O worker grava checkpoint por arquivo em:
- `/root/BotSalinha/data/ingest_supabase_checkpoint.jsonl`

Ao reiniciar o start, arquivos já marcados como `ok` no checkpoint são pulados automaticamente.

## Arquivos operacionais

- Log principal:
  - `/root/BotSalinha/data/ingest_supabase_tmux.log`
- Checkpoint:
  - `/root/BotSalinha/data/ingest_supabase_checkpoint.jsonl`
- Log de erros:
  - `/root/BotSalinha/data/ingest_supabase_errors.log`
- PID da pane tmux:
  - `/root/BotSalinha/data/ingest_supabase_tmux.pid`

## Estratégia de robustez

O `ingest_docs_to_supabase.py` inclui:
1. Retry de upsert por lote no Supabase.
2. Continuação após erro por arquivo (não aborta carga inteira).
3. Checkpoint incremental por documento.
4. Flush de log para observabilidade em tempo real.

## Troubleshooting

1. Sessão não sobe:
   - Verifique se variáveis obrigatórias foram exportadas.
   - Execute `tmux ls` para checar conflito de nome da sessão.

2. Processo parou no meio:
   - Leia `ingest_supabase_tmux.log` e `ingest_supabase_errors.log`.
   - Reinicie com o script de start (retoma via checkpoint).

3. Erro de embedding por contexto:
   - Confirmar versão atual de `src/rag/services/embedding_service.py` (split automático de textos longos).

4. Erro de tabela ausente no Supabase:
   - Reaplicar schema SQL em `docs/plans/RAG/supabase_rag_schema.sql`.

## Validação pós-carga

Sugestão de validação por contagem no Supabase:
- `rag_documents` > 0
- `rag_chunks` > 0
- `content_links` >= 0

E validação funcional:
- consulta RAG de artigo conhecido retornando fonte esperada.
