# Referência de API (Discord)

BotSalinha não expõe API HTTP pública nesta versão.
A interface principal é via comandos do Discord e mensagens automáticas.

## 1. Modos de interação

O bot suporta três modos:

1. Comandos com prefixo (`!ask`, `!ping`, etc.)
2. Canal IA dedicado (quando `DISCORD__CANAL_IA_ID` está configurado)
3. DM (mensagem direta)

### Configuração do Canal IA

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `DISCORD__CANAL_IA_ID` | string \| None | `None` | Canal dedicado para resposta automática |

## 2. Comportamento comum

- Histórico por conversa (usuário + guild/canal, ou DM)
- Limite de mensagem de entrada: 10.000 caracteres
- Respostas longas são divididas em chunks (limite do Discord: 2.000 chars)
- Typing indicator em operações de processamento
- Rate limiting por usuário/contexto

### Rate Limiting

| Variável | Default | Descrição |
|----------|---------|-----------|
| `RATE_LIMIT_REQUESTS` | `10` | Máximo de requisições por janela |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Tamanho da janela em segundos |

## 3. Comandos Discord

### `!ask <pergunta>`

Faz uma pergunta ao assistente sobre direito brasileiro e concursos públicos.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| `pergunta` | string | Sim | Pergunta do usuário (até 10.000 caracteres) |

### Respostas

- 200 (mensagem Discord): resposta gerada pelo provider ativo
- 429-like (cooldown Discord): aviso para aguardar antes de novo uso
- 500-like (mensagem Discord): erro amigável de processamento

### Exemplo

```text
!ask O que é habeas corpus?
```

### Observações de implementação

- Comando com `commands.cooldown(rate=1, per=60, user)`
- Salva mensagem do usuário e do assistente no histórico
- Pode anexar indicadores de confiança/fontes do RAG na resposta

### `!buscar <termo> [tipo]`

Executa busca vetorial no RAG e retorna trechos mais similares.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| `termo` | string | Sim | Termo de busca |
| `tipo` | string | Não | Um de: `artigo`, `jurisprudencia`, `questao`, `nota`, `todos` |

### Respostas

- 200 (mensagem Discord): resultados com similaridade e fonte
- 400-like (mensagem Discord): tipo inválido ou termo vazio
- 500-like (mensagem Discord): erro na busca

### Exemplo

```text
!buscar "competência originária" artigo
```

### Observações de implementação

- Depende de RAG habilitado e query service disponível
- Usa `query_by_tipo` para filtros semânticos por categoria

### `!fontes`

Lista os documentos jurídicos indexados no RAG.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| _nenhum_ | - | - | Não recebe parâmetros |

### Respostas

- 200 (embed Discord): lista de documentos, chunks e tokens
- 200 (mensagem Discord): RAG desabilitado ou base vazia
- 500-like (mensagem Discord): erro ao consultar base

### Exemplo

```text
!fontes
```

### Observações de implementação

- Consulta `rag_documents` e monta embed com metadados resumidos

### `!reindexar`

Reindexa todos os documentos RAG (uso administrativo).

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| _nenhum_ | - | - | Não recebe parâmetros |

### Respostas

- 200 (mensagem Discord): status da reindexação
- 403-like (controle Discord): comando restrito ao owner do bot
- 500-like (mensagem Discord): erro de ingestão/reindexação

### Exemplo

```text
!reindexar
```

### Observações de implementação

- Usa `commands.is_owner()`
- Recria índice com `IngestionService.reindex()`

### `!ping`

Retorna latência atual do bot.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| _nenhum_ | - | - | Não recebe parâmetros |

### Respostas

- 200 (mensagem Discord): `🏓 Pong! <latência>ms`

### Exemplo

```text
!ping
```

### `!ajuda` (alias: `!help`)

Exibe instruções e lista de comandos disponíveis.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| _nenhum_ | - | - | Não recebe parâmetros |

### Respostas

- 200 (mensagem Discord): texto de ajuda com comandos e limitações

### Exemplo

```text
!ajuda
```

### `!info`

Exibe informações operacionais do bot (versão, modelo e servidores).

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| _nenhum_ | - | - | Não recebe parâmetros |

### Respostas

- 200 (embed Discord): informações resumidas do bot

### Exemplo

```text
!info
```

### `!limpar` (alias: `!clear`)

Limpa o histórico de conversa do usuário no canal atual.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| _nenhum_ | - | - | Não recebe parâmetros |

### Respostas

- 200 (mensagem Discord): confirmação de limpeza
- 200 (mensagem Discord): aviso quando não há conversa para limpar

### Exemplo

```text
!limpar
```

## 4. Contrato de configuração do provider

- Arquivo: `config.yaml`
- Campo: `model.provider`
- Valores aceitos: `openai`, `google`

Credenciais esperadas no `.env`:

- `BOTSALINHA_OPENAI__API_KEY` (quando provider = `openai`) - formato canônico
  - `OPENAI_API_KEY` também funciona via fallback (compatibilidade legada)
- `BOTSALINHA_GOOGLE__API_KEY` (quando provider = `google`) - formato canônico
  - `GOOGLE_API_KEY` também funciona via fallback (compatibilidade legada)
