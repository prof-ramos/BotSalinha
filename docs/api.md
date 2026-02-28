# Referência de API

BotSalinha não expõe API HTTP pública nesta versão. A interface principal é via comandos do Discord.

## Modos de Interação

BotSalinha oferece três modos de interação com os usuários:

1. **Comandos com Prefixo (`!ask`, `!ping`, etc.)** - Modo tradicional
2. **Canal IA** - Modo automático de canal dedicado
3. **DM (Direct Message)** - Modo automático de mensagens privadas

### Modo Canal IA

Ao configurar `DISCORD__CANAL_IA_ID`, qualquer mensagem enviada no canal específico dispara uma resposta automática do bot.

**Características:**

- Resposta imediata a qualquer mensagem no canal configurado
- Mantém histórico de conversa por usuário
- Aplica rate limiting por usuário/guild
- Mostra indicador "digitando..." durante processamento
- Respostas longas são divididas automaticamente em chunks de 2000 caracteres

### Modo DM (Direct Message)

Qualquer mensagem direta (DM) para o bot dispara uma resposta automática.

**Características:**

- Resposta imediata a mensagens privadas
- Mantém histórico de conversa isolado por usuário
- Aplica rate limiting específico para DMs
- Mostra indicador "digitando..." durante processamento
- Respostas longas são divididas automaticamente

### Comportamento Simultâneo

Ambos os modos (Canal IA e DM) podem operar simultaneamente:

- Canal IA: Habilitado apenas com configuração explícita
- DM: Sempre habilitado
- Comandos com prefixo: Continuam funcionando normalmente em canais

## Configuração de Modos de Interação

| Variável               | Tipo           | Default | Descrição                                         |
| ---------------------- | -------------- | ------- | ------------------------------------------------- |
| `DISCORD__CANAL_IA_ID` | string \| None | None    | ID do canal dedicado para interação IA (opcional) |

### Exemplo: Canal IA

Qualquer mensagem enviada no canal configurado gera resposta automática.

**Exemplo:**

```text
Usuario no canal #chat-ia:
  "Qual é o prazo de prescrição trabalhista?"

Bot (responde automaticamente):
  "De acordo com a CLT... [resposta completa]"
```

### Fluxo DM

Mensagens privadas são processadas automaticamente.

**Exemplo:**

```text
Usuario em DM:
  "O que é crime doloso?"

Bot (responde automaticamente):
  "Crime doloso ocorre quando há intenção..."
```

## Rate Limiting

Ambos os modos de interação automática respeitam o sistema de rate limiting:

- **Limites:** Máximo de 10 requisições por janela de 60 segundos
- **Por usuário:** Cada usuário tem seu próprio contador
- **Por guild:** No Canal IA, limites são aplicados por guild
- **Em DMs:** Limite é aplicado usando `user_id:dm` como chave
- **Mensagens de erro:** Exibem tempo estimado para nova tentativa

**Configuração:**

```env
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW_SECONDS=60
```

## Diferenças entre Modos

| Característica     | Comandos Prefixo | Canal IA  | DM        |
| ------------------ | ---------------- | --------- | --------- |
| Requer prefixo     | ✅               | ❌        | ❌        |
| Resposta imediata  | ❌               | ✅        | ✅        |
| Mantém histórico   | ✅               | ✅        | ✅        |
| Rate limiting      | ✅               | ✅        | ✅        |
| Typing indicator   | ✅               | ✅        | ✅        |
| Limites de tamanho | 10k chars        | 10k chars | 10k chars |

## Interface de Comandos Discord

### `!ask <pergunta>`

Faz uma pergunta ao assistente sobre direito brasileiro e concursos.

**Parâmetros:**

| Nome       | Tipo   | Obrigatório | Descrição                    |
| ---------- | ------ | ----------- | ---------------------------- |
| `pergunta` | string | Sim         | Texto da pergunta do usuário |

**Resposta:**

- 200 (mensagem Discord): Resposta gerada pelo provider ativo (`openai` ou `google`)
- 429 (cooldown Discord): Mensagem de espera quando limite de comando é atingido
- 500 (mensagem Discord): Mensagem amigável de erro interno

**Exemplo:**

```text
!ask O que é habeas corpus?
```

### `!buscar <termo> [tipo]`

Realiza uma busca vetorial direta no RAG baseada em similaridade semântica e filtros e retorna os chunks sem inferência da IA.

**Parâmetros:**

| Nome    | Tipo   | Obrigatório | Descrição                                                                                                   |
| ------- | ------ | ----------- | ----------------------------------------------------------------------------------------------------------- |
| `termo` | string | Sim         | O termo a ser buscado nas leis/documentos                                                                   |
| `tipo`  | string | Não         | Filtro de metadado opcional (ex: `artigo`, `jurisprudencia`, `questao`, `nota`, `todos`). Padrão é `todos`. |

**Resposta:**

- 200 (mensagem Discord): Lista de trechos encontrados com indicadores visuais e sua pontuação de similaridade.

**Exemplo:**

```text
!buscar "competência originária" artigo
```

### `!fontes`

Lista os documentos de conhecimento indexados no banco de dados vetorial.

**Parâmetros:**

| Nome     | Tipo | Obrigatório | Descrição             |
| -------- | ---- | ----------- | --------------------- |
| _nenhum_ | -    | -           | Não recebe parâmetros |

**Resposta:**

- 200 (embed Discord): Lista com o nome, tamanho de token e quantidade de chunks de cada fonte.

### `!reindexar`

Recria imediatamente todo o índice RAG (limpa tabela e realiza novo parse/embedding de todos os docs) - _Apenas Admin_

**Parâmetros:**

| Nome     | Tipo | Obrigatório | Descrição             |
| -------- | ---- | ----------- | --------------------- |
| _nenhum_ | -    | -           | Não recebe parâmetros |

**Resposta:**

- 200 (mensagem Discord): Log de progresso e mensagem de sucesso da Ingestão.

### `!ping`

Verifica a latência atual do bot.

**Parâmetros:**

| Nome     | Tipo | Obrigatório | Descrição             |
| -------- | ---- | ----------- | --------------------- |
| _nenhum_ | -    | -           | Não recebe parâmetros |

**Resposta:**

- 200 (mensagem Discord): `🏓 Pong! <latência>ms`

**Exemplo:**

```text
!ping
```

### `!ajuda` (alias: `!help`)

Exibe os comandos disponíveis e limitações.

**Parâmetros:**

| Nome     | Tipo | Obrigatório | Descrição             |
| -------- | ---- | ----------- | --------------------- |
| _nenhum_ | -    | -           | Não recebe parâmetros |

**Resposta:**

- 200 (mensagem Discord): Texto de ajuda

### `!info`

Mostra informações do bot (versão, modelo ativo, número de servidores).

**Parâmetros:**

| Nome     | Tipo | Obrigatório | Descrição             |
| -------- | ---- | ----------- | --------------------- |
| _nenhum_ | -    | -           | Não recebe parâmetros |

**Resposta:**

- 200 (embed Discord): Informações operacionais do bot

### `!limpar` (alias: `!clear`)

Limpa o histórico de conversa do usuário no canal atual.

**Parâmetros:**

| Nome     | Tipo | Obrigatório | Descrição             |
| -------- | ---- | ----------- | --------------------- |
| _nenhum_ | -    | -           | Não recebe parâmetros |

**Resposta:**

- 200 (mensagem Discord): Confirmação de histórico limpo
- 404-like (mensagem Discord): Nenhuma conversa encontrada

## Contrato de Configuração de Provider

- Provider ativo: `config.yaml` (`model.provider`)
- Valores aceitos: `openai`, `google`
- Credenciais: `.env`
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`
