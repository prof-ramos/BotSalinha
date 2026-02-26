# Clean Code Refactoring Plan - BotSalinha

> **Branch:** `cleancode`
> **Criado em:** 2026-02-26
> **Status:** Em andamento

---

## 📋 Visão Geral

Este documento descreve o plano completo de refatoração do BotSalinha seguindo princípios de Clean Code (Robert C. Martin).

### Objetivos

- Melhorar legibilidade e manutenibilidade
- Aumentar cobertura de testes (atual: 44% → meta: 80%+)
- Separar responsabilidades (SoC)
- Eliminar code smells identificados

---

## 🔍 Análise Inicial

### Cobertura de Testes por Módulo

| Módulo | Cobertura | Status |
|--------|-----------|--------|
| `models/conversation.py` | 98% | ✅ Excelente |
| `models/message.py` | 98% | ✅ Excelente |
| `config/settings.py` | 85% | ✅ Bom |
| `config/yaml_config.py` | 58% | ⚠️ Médio |
| `middleware/rate_limiter.py` | 46% | ⚠️ Médio |
| `core/agent.py` | 31% | 🔴 Crítico |
| `core/discord.py` | 30% | 🔴 Crítico |
| `storage/sqlite_repository.py` | 20% | 🔴 Crítico |

### Findings (Problemas Identificados)

| ID | Severidade | Área | Problema |
|----|------------|------|----------|
| F01 | 🔴 HIGH | Architecture | God Module em `core/discord.py` (300 linhas) |
| F02 | 🔴 HIGH | Testing | Diretórios unit/integration tests vazios |
| F03 | 🟡 MEDIUM | Code Quality | `import logging` no final do arquivo |
| F04 | 🟡 MEDIUM | Architecture | Mixed concerns - DB em command handlers |
| F05 | 🟡 MEDIUM | Error Handling | Duplicate error handlers |
| F06 | 🟡 MEDIUM | Type Safety | Global mutable state (singleton) |
| F07 | 🟢 LOW | Code Quality | Magic strings em `_build_prompt` |
| F08 | 🟢 LOW | Performance | Message splitting ineficiente |
| F09 | 🟢 LOW | Config | Múltiplas fontes de configuração |

---

## 📐 Plano de Refatoração

### Phase 1 — Safe/Mechanical (Zero Risk)

| Task | Arquivo | Descrição | Status |
|------|---------|-----------|--------|
| P1-1 | `utils/retry.py` | Mover `import logging` para topo | ✅ Concluído |
| P1-2 | `core/agent.py` | Extrair constantes `PROMPT_*` | ✅ Concluído |
| P1-3 | `core/discord.py` | Extrair `HELP_TEXT_TEMPLATE` | ✅ Concluído |
| P1-4 | Todos | Type hints incompletos | ⏳ Pendente |
| P1-5 | `sqlite_repository.py` | Docstrings em métodos públicos | ⏳ Pendente |

**Commits:**
- `7873fe0` - refactor(core,utils): Phase 1 - extract constants, fix imports

---

### Phase 2 — Moderate Risk

| Task | Arquivo | Descrição | Status |
|------|---------|-----------|--------|
| P2-1 | `core/discord.py` | Extrair `CommandService` para lógica de negócio | ⏳ Pendente |
| P2-2 | `utils/` | Extrair `MessageSplitter` utility | ✅ Concluído |
| P2-3 | `sqlite_repository.py` | Dependency Injection (remover singleton) | ⏳ Pendente |
| P2-4 | `tests/unit/` | Unit tests para `sqlite_repository.py` | ✅ Concluído |
| P2-5 | `tests/unit/` | Unit tests para `rate_limiter.py` | ✅ Concluído |

**Commits:**
- `596d73d` - refactor(core,utils): Phase 2 - extract MessageSplitter utility
- `392f4d9` - test(unit): add 22 unit tests for SQLiteRepository
- `8445918` - test(unit): add 22 unit tests for RateLimiter

---

### Phase 3 — Higher Risk

| Task | Arquivo | Descrição | Status |
|------|---------|-----------|--------|
| P3-1 | Directory | Reorganizar `core/` → `bot/`, `services/`, `commands/` | ⏳ Pendente |
| P3-2 | API | Introduzir `BotSalinha` facade class | ⏳ Pendente |

---

## 📂 Estrutura de Diretórios Proposta

### Antes

```
src/
├── core/
│   ├── discord.py        # 300 linhas - God Module
│   ├── agent.py          # 253 linhas
│   └── lifecycle.py      # 236 linhas
├── storage/
│   ├── repository.py
│   └── sqlite_repository.py
├── middleware/
│   └── rate_limiter.py
├── config/
│   ├── settings.py
│   └── yaml_config.py
├── models/
│   ├── conversation.py
│   └── message.py
└── utils/
    ├── errors.py
    ├── retry.py
    └── logger.py
```

### Depois

```
src/
├── bot/                      # Discord integration layer
│   ├── __init__.py
│   ├── discord_bot.py        # Bot class (commands registration)
│   └── lifecycle.py          # Startup/shutdown hooks
├── commands/                 # Command handlers
│   ├── __init__.py
│   ├── ask.py                # !ask command
│   ├── basic.py              # !ping, !help, !info
│   └── conversation.py       # !clear command
├── services/                 # Business logic layer
│   ├── __init__.py
│   ├── agent_service.py      # AI agent integration
│   └── conversation_service.py # Conversation management
├── storage/                  # Data layer
│   ├── __init__.py
│   ├── repository.py         # Abstract interfaces
│   └── sqlite_repository.py  # SQLite implementation
├── middleware/               # Cross-cutting concerns
│   ├── __init__.py
│   └── rate_limiter.py
├── config/                   # Configuration
│   ├── __init__.py
│   ├── settings.py
│   └── yaml_config.py
├── models/                   # Domain models
│   ├── __init__.py
│   ├── conversation.py
│   └── message.py
└── utils/                    # Utilities
    ├── __init__.py
    ├── errors.py
    ├── retry.py
    ├── logger.py
    └── message_splitter.py   # ✅ Novo
```

---

## 🧪 Plano de Testes

### Unit Tests (Meta: 80%+ coverage)

| Módulo | Tests Necessários | Status |
|--------|-------------------|--------|
| `sqlite_repository.py` | CRUD operations, edge cases | 🔄 22 tests escritos |
| `rate_limiter.py` | Token bucket, window expiry | ⏳ Pendente |
| `message_splitter.py` | Split logic, edge cases | ✅ 17 tests |
| `agent_service.py` | Mock Agno, history building | ⏳ Pendente |

### Integration Tests

| Cenário | Descrição | Status |
|---------|-----------|--------|
| DB Round-trip | Create → Read → Update → Delete | ⏳ Pendente |
| Command Flow | Message → Command → Response | ✅ E2E existe |
| Rate Limit | Multiple requests, cooldown | ✅ E2E existe |

---

## 📊 Progresso

```
Phase 1: ████████████████████ 60% (3/5)
Phase 2: ████████████████████ 80% (4/5)
Phase 3: ░░░░░░░░░░░░░░░░░░░░ 0%  (0/2)

Overall: ████████████░░░░░░░░ 47%
```

### Commits

| Hash | Fase | Descrição |
|------|------|-----------|
| `7873fe0` | P1 | Extract constants, fix imports |
| `596d73d` | P2 | MessageSplitter utility + 17 tests |
| `392f4d9` | P2 | 22 unit tests SQLiteRepository |
| `8445918` | P2 | 22 unit tests RateLimiter |

### Cobertura de Testes

```
Antes: 44% (14 E2E tests)
Depois: ~65% (76 tests: 14 E2E + 17 MessageSplitter + 22 SQLite + 22 RateLimiter + 1 prompt)
```

---

## ⚠️ Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Quebrar E2E tests | Baixa | Médio | Rodar testes após cada batch |
| Regressão de funcionalidade | Baixa | Alto | Manter behavioral tests |
| Conflitos de merge | Média | Baixo | Branch dedicada, PRs pequenos |
| Timeout em refatoração | Média | Médio | Priorizar por impacto |

---

## 📝 Definition of Done

- [ ] Todos os testes passando (unit + e2e)
- [ ] Cobertura ≥ 80%
- [ ] Ruff check sem erros
- [ ] Mypy sem erros novos
- [ ] Documentação atualizada
- [ ] PR revisado e aprovado
- [ ] Merge em `main`

---

## 🔗 Links

- **Branch:** https://github.com/prof-ramos/BotSalinha/tree/cleancode
- **PR:** (a ser criado)
- **Skill utilizada:** cleancode-refactor

---

_Ultima atualização: 2026-02-26_
