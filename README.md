# 🤖 BotSalinha

<!-- markdownlint-disable MD033 -->
<div align="center">
<!-- markdownlint-enable MD033 -->

**Bot do Discord especializado em direito brasileiro e concursos públicos**
_Alimentado por Agno e Gemini 2.0 Flash_

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.4+-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-D7FFDB?style=for-the-badge)](https://docs.astral.sh/ruff/)

[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)

<!-- markdownlint-disable MD033 -->
</div>
<!-- markdownlint-enable MD033 -->

---

## 📖 Sobre

BotSalinha é um assistente inteligente para Discord que responde perguntas sobre **direito brasileiro**, **legislação**, **jurisprudência** e **preparação para concursos públicos**.

### ✨ Destaques

- 🧠 **IA Avançada**: Powered by Google Gemini 2.0 Flash via framework Agno
- 💬 **Conversas Contextuais**: Memória de até 3 pares de mensagens por conversa
- 🗃️ **Persistência**: Banco de dados SQLite para histórico de conversas
- 🛡️ **Rate Limiting**: Proteção contra abuso com algoritmo token bucket
- 🔄 **Resiliência**: Retentativa automática com backoff exponencial
- 📊 **Observabilidade**: Logs estruturados JSON com rastreamento de requisições
- 🐳 **DevOps Ready**: Dockerfile multi-stage e docker compose

---

<!-- markdownlint-disable MD033 -->
<div align="center">
<!-- markdownlint-enable MD033 -->

**Desenvolvido com ❤️ usando [Agno](https://github.com/agno-agi/agno) + [Gemini 2.0 Flash](https://ai.google.dev/)**

[⬆️ Voltar ao topo](#-botsalinha)

<!-- markdownlint-disable MD033 -->
</div>
<!-- markdownlint-enable MD033 -->

---

## 🚀 Início Rápido

### Pré-requisitos

| Requisito         | Versão | Link                                                                    |
| ----------------- | ------ | ----------------------------------------------------------------------- |
| Python            | 3.12+  | [python.org](https://www.python.org/)                                   |
| uv                | latest | [astral.sh/uv](https://github.com/astral-sh/uv)                         |
| Discord Bot Token | -      | [Discord Developer Portal](https://discord.com/developers/applications) |
| Google API Key    | -      | [AI Studio](https://ai.google.dev/)                                     |

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/prof-ramos/BotSalinha.git
cd BotSalinha

# 2. Instale as dependências com uv
uv sync

# 3. Configure as variáveis de ambiente
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```env
DISCORD_BOT_TOKEN=seu_discord_bot_token_aqui
GOOGLE_API_KEY=sua_google_api_key_aqui
```

```bash
# 4. Execute o bot
uv run bot.py
```

---

## 💻 Comandos

| Comando           | Descrição                                    | Exemplo                       |
| ----------------- | -------------------------------------------- | ----------------------------- |
| `!ask <pergunta>` | Faça uma pergunta sobre direito ou concursos | `!ask O que é habeas corpus?` |
| `!ping`           | Verifique a latência do bot                  | `!ping`                       |
| `!ajuda`          | Mostra mensagem de ajuda                     | `!ajuda`                      |
| `!info`           | Mostra informações do bot                    | `!info`                       |
| `!limpar`         | Limpa o histórico da conversa                | `!limpar`                     |

---

## ⚙️ Configuração

Toda a configuração é feita através de variáveis de ambiente.

### Variáveis Principais

| Variável                    | Padrão                         | Descrição                                  |
| --------------------------- | ------------------------------ | ------------------------------------------ |
| `DISCORD_BOT_TOKEN`         | _obrigatório_                  | Token do bot Discord                       |
| `GOOGLE_API_KEY`            | _obrigatório_                  | Chave da API Google Gemini                 |
| `HISTORY_RUNS`              | `3`                            | Pares de mensagens no histórico            |
| `RATE_LIMIT_REQUESTS`       | `10`                           | Máximo de requisições por janela           |
| `RATE_LIMIT_WINDOW_SECONDS` | `60`                           | Janela de tempo (segundos)                 |
| `DATABASE_URL`              | `sqlite:///data/botsalinha.db` | URL de conexão do banco                    |
| `LOG_LEVEL`                 | `INFO`                         | Nível de log (DEBUG, INFO, WARNING, ERROR) |

> 📄 Veja [`.env.example`](.env.example) para todas as opções disponíveis.

---

## 🏗️ Arquitetura

BotSalinha segue uma arquitetura modular com separação clara de responsabilidades:

```text
┌─────────────┐     ┌─────────────────┐     ┌────────────────┐
│   Discord   │────▶│  BotSalinhaBot  │────▶│   RateLimiter  │
└─────────────┘     └─────────────────┘     └───────┬────────┘
                                                    │
                    ┌───────────────────────────────┘
                    ▼
            ┌───────────────┐     ┌──────────────────────┐
            │ AgentWrapper  │────▶│   Gemini 2.0 Flash   │
            └───────┬───────┘     └──────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │ SQLiteRepo    │
            └───────────────┘
```

### Componentes

| Componente             | Tecnologia          | Descrição              |
| ---------------------- | ------------------- | ---------------------- |
| **Integração Discord** | `discord.py`        | Framework de comandos  |
| **Limitação de Taxa**  | Token Bucket        | Algoritmo em memória   |
| **Agente IA**          | Agno + Gemini       | Contexto de conversa   |
| **Persistência**       | SQLAlchemy + SQLite | ORM com backend SQLite |
| **Logging**            | structlog           | Logs estruturados JSON |

### Estrutura do Projeto

```text
botsalinha/
├── bot.py                 # Ponto de entrada
├── src/
│   ├── config/            # Configurações Pydantic
│   ├── core/              # Wrappers do bot e agente
│   ├── models/            # Modelos de dados
│   ├── storage/           # Camada de repositório
│   ├── utils/             # Logs, erros, retry
│   └── middleware/        # Rate limiting
├── tests/                 # Testes pytest
├── migrations/            # Migrações Alembic
├── scripts/               # Utilitários de backup
├── docs/                  # Documentação
└── data/                  # Banco SQLite (gitignore)
```

---

## 🔧 Desenvolvimento

### Executar Testes

```bash
# Executar todos os testes com cobertura
uv run pytest

# Executar com verbose
uv run pytest -v

# Executar arquivo específico
uv run pytest tests/test_settings.py
```

### Qualidade do Código

```bash
# Linting
uv run ruff check src/

# Formatação
uv run ruff format src/

# Verificação de tipos
uv run mypy src/

# Executar todas as verificações
uv run ruff check src/ && uv run ruff format src/ && uv run mypy src/
```

### Migrações do Banco de Dados

```bash
# Criar nova migração
uv run alembic revision --autogenerate -m "descrição da mudança"

# Aplicar migrações
uv run alembic upgrade head

# Reverter última migração
uv run alembic downgrade -1
```

### Backup e Restore

```bash
# Criar backup
uv run python scripts/backup.py backup

# Listar backups
uv run python scripts/backup.py list

# Restaurar do backup
uv run python scripts/backup.py restore --restore-from backups/arquivo.db
```

---

## 🐳 Implantação Docker

### Desenvolvimento

```bash
docker compose up -d
```

### Produção

```bash
docker compose -f docker compose.prod.yml up -d
```

> 📖 Veja [docs/deployment.md](docs/deployment.md) para instruções detalhadas.

---

## 🐛 Solução de Problemas

### O bot não responde aos comandos

1. ✅ Verifique se **MESSAGE_CONTENT Intent** está habilitado no [Discord Developer Portal](https://discord.com/developers/applications)
2. ✅ Confirme que o bot tem as permissões necessárias (`Send Messages`, `Read Message History`)
3. ✅ Certifique-se de que o bot está online no seu servidor

### Erros de banco de dados

```bash
# Verifique se o diretório existe
mkdir -p data/

# Aplique migrações
uv run alembic upgrade head
```

### Problemas de limitação de taxa

Ajuste as configurações no `.env`:

```env
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60
```

---

## 🗺️ Roadmap

- [ ] Suporte para modelos LLM adicionais (Claude, GPT)
- [ ] Sistema de citação de fontes jurídicas
- [ ] Índice de legislação e jurisprudência
- [ ] Interface web para gerenciamento de conversas
- [ ] Dashboard de analytics
- [ ] Suporte a múltiplos idiomas

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, siga estas etapas:

1. **Fork** o repositório
2. **Crie** uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. **Faça** commit das suas mudanças (`git commit -m 'feat: adiciona nova funcionalidade'`)
4. **Push** para a branch (`git push origin feature/nova-funcionalidade`)
5. **Abra** um Pull Request

### Padrões de Commit

Este projeto segue [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - Nova funcionalidade
- `fix:` - Correção de bug
- `docs:` - Documentação
- `style:` - Formatação
- `refactor:` - Refatoração
- `test:` - Testes
- `chore:` - Tarefas de manutenção

---

## 📚 Documentação

| Documento                                          | Descrição                          |
| -------------------------------------------------- | ---------------------------------- |
| [PRD.md](PRD.md)                                   | Documento de Requisitos do Produto |
| [docs/deployment.md](docs/deployment.md)           | Guia de Implantação                |
| [docs/operations.md](docs/operations.md)           | Manual de Operações                |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Guia do Desenvolvedor              |

---

## 📄 Licença

Este projeto está licenciado sob a **MIT License** - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 📞 Suporte

Encontrou um problema? Tem uma sugestão?

- 🐛 **Bugs**: [Abra uma issue](https://github.com/prof-ramos/BotSalinha/issues)
- 💡 **Sugestões**: [Discussions](https://github.com/prof-ramos/BotSalinha/discussions)
- 📧 **Contato**: Via GitHub

---

<!-- markdownlint-disable MD033 -->
<div align="center">
<!-- markdownlint-enable MD033 -->

**Desenvolvido com ❤️ usando [Agno](https://github.com/agno-agi/agno) + [Gemini 2.0 Flash](https://ai.google.dev/)**

[⬆️ Voltar ao topo](#-botsalinha)

<!-- markdownlint-disable MD033 -->
</div>
<!-- markdownlint-enable MD033 -->
