# 🛠️ Features

Este documento cataloga as funcionalidades do BotSalinha, detalhando seu estado atual, capacidades técnicas e critérios de verificação.

## 📊 Visão Geral de Estabilidade

| Funcionalidade           | Estado       | Categoria | Descrição                                           |
| :----------------------- | :----------- | :-------- | :-------------------------------------------------- |
| **Comando !ask**         | ✅ Estável   | Core      | Interface principal de conversação via Discord      |
| **Multi-Model Provider** | ✅ Estável   | Core      | Suporte a OpenAI (padrão) e Google Gemini           |
| **Histórico Contextual** | ✅ Estável   | Memória   | Retenção de até 3 pares de mensagens via SQLite     |
| **Rate Limiting**        | ✅ Estável   | Segurança | Algoritmo Token Bucket para proteção da API         |
| **CLI Developer**        | 🛠️ Beta      | Tooling   | Interface rica para gestão de DB, Sessões e Prompts |
| **RAG Local**            | 🔭 Planejado | IA/RAG    | Busca semântica em ~1.000 documentos jurídicos      |
| **Citação de Fontes**    | 🔭 Planejado | IA/RAG    | Referenciamento automático de leis e jurisprudência |

---

## 💎 Execução Core

### 1. Comando `!ask`

- **Descrição**: Processa perguntas em linguagem natural sobre direito brasileiro.
- **Capacidades**:
  - Respostas formatadas em Markdown.
  - Injeção de data/hora no contexto.
  - Suporte a mensagens longas (com divisão automática no Discord).
- **Verificação**: `uv run pytest tests/test_bot.py`

### 2. Multi-Model (Agno Framework)

- **Descrição**: Abstração que permite troca rápida de LLMs.
- **Provedores**:
  - `openai`: GPT-4o-mini (padrão).
  - `google`: Gemini 2.0 Flash.
- **Configuração**: Definido via `config.yaml`.
- **Verificação**: `uv run botsalinha config check`

---

## 🧠 Inteligência e Contexto

### 1. Persistência de Histórico

- **Tecnologia**: SQLAlchemy + SQLite.
- **Capacidade**: Mantém o contexto de conversas mesmo após reinicialização do bot.
- **Configuração**: `HISTORY_RUNS` no `.env`.

### 2. Rate Limiter (Token Bucket)

- **Descrição**: Previne custos excessivos e abusos.
- **Capacidade**: 10 requisições por minuto (configurável).
- **Verificação**: `tests/test_middleware.py`.

---

## 🔭 Próximas Features (Future Features)

### 1. 📚 RAG Local (Retrieval-Augmented Generation)

- **Status**: Planejado (Q2 2026).
- **Objetivo**: Permitir que o bot responda com base em documentos internos (PDF/TXT) sem enviá-los para um Vector DB externo.
- **Stack Prevista**:
  - ChromaDB (Local).
  - Sentence Transformers (`multilingual-e5-large`).
- **Capacidade**: ~1.000 documentos em 2-4GB RAM.

### 2. 🏛️ Citação de Fontes Jurídicas

- **Status**: Planejado.
- **Objetivo**: Garantir que cada resposta mencione o artigo da lei ou o número do processo correspondente.
- **Mecanismo**: Metadados estruturados no RAG.

### 3. 📊 Dashboard de Analytics

- **Status**: Planejado.
- **Objetivo**: Interface web para visualizar volume de uso, tokens gastos e tópicos mais perguntados.

---

## 📝 Como testar uma Feature?

Cada feature nova deve acompanhar:

1. Um teste unitário em `tests/`.
2. Uma entrada neste `FEATURES.md`.
3. Atualização no `ROADMAP.md` caso altere a visão de longo prazo.
