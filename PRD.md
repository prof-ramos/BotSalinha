# PRD - BotSalinha v1.0

## 1. Visão Geral

BotSalinha é um assistente virtual para Discord especializado em direito e concursos, utilizando o framework Agno com o modelo Gemini Flash 2.0. A v1.0 foca em execução local com resposta contextual, histórico de conversação e formatação em markdown.

### 1.1 Objetivo Principal
Fornecer respostas contextualizadas a perguntas sobre direito e concursos através do comando `!ask`, mantendo histórico de conversação e entregando respostas formatadas em português brasileiro.

### 1.2 Escopo v1.0
- Execução local (sem Docker/VPS)
- Comando único `!ask`
- Histórico de 3 interações
- Logs em modo debug
- Sem persistência de dados (memória volátil)

## 2. Funcionalidades

### 2.1 Comando !ask
| Descrição | Detalhes |
|-----------|----------|
| **Trigger** | `!ask <pergunta>` |
| **Resposta** | Gemini 2.0 Flash com contexto |
| **Histórico** | 3 runs anteriores (memória volátil) |
| **Formatação** | Markdown + data/hora |
| **Idioma** | Português-BR |
| **Domínio** | Direito e concursos públicos |

### 2.2 Configuração Discord
- Token via variável de ambiente
- MESSAGE_CONTENT Intent habilitado
- Permissões: Send Messages, Read Message History

### 2.3 Debug Mode
Logs detalhados habilitados para desenvolvimento e troubleshooting.

## 3. Instalação e Execução Local

### 3.1 Pré-requisitos
- macOS M3 (ou compatível)
- Python 3.12+
- uv (package manager)
- Conta Discord com Developer Portal acessível
- Google API Key (Gemini)

### 3.2 Passo a Passo

#### 1. Criar o projeto
```bash
mkdir botsalinha && cd botsalinha
uv init
```

#### 2. Instalar dependências
```bash
uv add agno google-generativeai discord.py python-dotenv
```

#### 3. Criar arquivo `.env`
```env
GOOGLE_API_KEY=your_google_api_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

#### 4. Criar `bot.py`
```python
import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.integrations.discord import DiscordClient
from agno.models.google import Gemini

load_dotenv()

agent = Agent(
    name="BotSalinha",
    model=Gemini(id="gemini-2.0-flash"),
    instructions="Você é BotSalinha, assistente em PT-BR para direito/concursos. Responda só a !ask, use histórico.",
    add_history_to_context=True,
    num_history_runs=3,
    add_datetime_to_context=True,
    markdown=True,
    debug_mode=True,
)

client = DiscordClient(agent)

if __name__ == "__main__":
    client.serve()
```

#### 5. Executar
```bash
uv run bot.py
```

#### 6. Testar
- Convide o bot ao servidor Discord
- Use `!ask Olá` para verificar resposta

## 4. Configuração Discord

### 4.1 Criar Aplicação Discord
1. Acesse [Discord Developer Portal](https://discord.com/developers/applications)
2. Clique em "New Application"
3. Dê um nome ao bot (ex: "BotSalinha")
4. Clique em "Create"

### 4.2 Configurar Bot
1. Navegue para **Bot** > **Token**
2. Clique em "Reset Token" para gerar novo token
3. **Copie o token imediatamente** (não será exibido novamente)
4. Adicione ao `.env` como `DISCORD_BOT_TOKEN`

### 4.3 Configurar Intents
Em **Bot** > **Privileged Gateway Intents**:
- ✅ **MESSAGE_CONTENT** (obrigatório para ler mensagens)

### 4.4 Gerar URL de Convite
1. Navegue para **OAuth2** > **URL Generator**
2. Selecione scope:
   - ✅ **bot**
3. Selecione permissões:
   - ✅ Send Messages
   - ✅ Read Message History
4. Copie a URL gerada e acesse no navegador
5. Selecione o servidor e autorize

## 5. Requisitos Não-Funcionais

### 5.1 Plataforma e Ambiente
| Aspecto | Especificação |
|---------|---------------|
| Plataforma | macOS M3 (ou compatível) |
| Runtime | Python 3.12+ |
| Package Manager | uv |
| Execução | Local (`uv run`) |

### 5.2 Persistência
- **v1.0**: Memória volátil (histório perdido ao reiniciar)
- **Futuro**: SQLite para persistência de histórico

### 5.3 Segurança
- `.env` adicionado ao `.gitignore`
- Tokens nunca commitados ao repositório
- GOOGLE_API_KEY mantida privada
- DISCORD_BOT_TOKEN mantido privado

### 5.4 Performance e Disponibilidade
- Latência: dependente de resposta Gemini Flash (~1-3s)
- Disponibilidade: apenas quando executado localmente
- Escalabilidade: v1.0 não escalável (single instance)

### 5.5 Idioma e Localização
- Idioma primário: Português-BR
- Formatação de datas: PT-BR
- Domínio de conhecimento: Direito brasileiro e concursos públicos

## 6. Arquitetura Técnica

### 6.1 Componentes
```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Discord   │────▶│ Agno Agent  │────▶│ Gemini Flash │
│   Client    │     │  (Discord)  │     │   2.0 API    │
└─────────────┘     └─────────────┘     └──────────────┘
                            ▲
                            │
                     ┌──────┴──────┐
                     │  Context    │
                     │  (3 runs)   │
                     └─────────────┘
```

### 6.2 Fluxo de Dados
1. Usuário envia `!ask <pergunta>` no Discord
2. DiscordClient (Agno) recebe mensagem
3. Agent recupera contexto (3 runs anteriores)
4. Request enviada ao Gemini Flash 2.0
5. Resposta processada com formatação markdown
6. Resposta enviada ao Discord

### 6.3 Limitações Técnicas v1.0
- Sem persistência de dados
- Sem tratamento de erros robusto
- Sem rate limiting explícito
- Sem métricas ou monitoramento
- Histório limitado a 3 runs

## 7. Estrutura de Arquivos

```
botsalinha/
├── bot.py              # Código principal do bot
├── .env                # Variáveis de ambiente (gitignore)
├── .gitignore          # Arquivos ignorados pelo git
├── pyproject.toml      # Dependências uv
└── README.md           # Documentação do projeto
```

## 8. Roadmap

### v1.0 (Atual) - MVP Local
- ✅ Comando `!ask` funcional
- ✅ Histórico de 3 interações
- ✅ Respostas em markdown
- ✅ Execução local

### v1.1 - Dockerização
- Dockerfile multi-plataforma
- docker-compose para orquestração
- Portainer para gerenciamento
- Traefik para reverse proxy

### v1.2 - Melhorias de Funcionalidade
- Persistência SQLite para histórico
- Comando adicional `!limpar` (reset contexto)
- Comando `!ajuda` (help)
- Tratamento de erros robusto
- Rate limiting

### v2.0 - Deploy em VPS
- Deploy em VPS com autoscaling
- Métricas e monitoramento
- Logging estruturado
- Testes automatizados

## 9. Considerações Futuras

### 9.1 Melhorias Possíveis
- Adicionar mais modelos LLM (opção do usuário)
- Sistema de citações de fontes jurídicas
- Index de legislação e jurisprudência
- Multi-servidor com contexto isolado
- Webhooks para notificações

### 9.2 Decisões Arquiteturais Pendentes
- Estratégia de persistência (SQLite vs PostgreSQL)
- Cache de respostas frequentes
- Rate limiting por usuário/servidor
- Estratégia de backup de dados

## 10. Apêndice

### 10.1 Comandos Úteis
```bash
# Instalar dependências
uv sync

# Executar bot
uv run bot.py

# Atualizar dependências
uv add <package>

# Ver logs (se implementado)
tail -f botsalinha.log
```

### 10.2 Troubleshooting

#### Bot não responde
1. Verifique se `DISCORD_BOT_TOKEN` está correto no `.env`
2. Confirme que MESSAGE_CONTENT Intent está habilitado
3. Verifique se o bot foi convidado com permissões corretas
4. Confirme que o bot está online (no Discord Developer Portal)

#### Erro de API Gemini
1. Verifique `GOOGLE_API_KEY` no `.env`
2. Confirme que a API key tem quota disponível
3. Verifique conectividade com a internet

#### Histório não funciona
1. Comportamento esperado na v1.0 (volátil)
2. Reiniciar o bot limpa todo o histórico
3. Aguarde v1.2 para persistência

### 10.3 Links Úteis
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Agno Framework](https://github.com/agno-ai/agno)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [uv Documentation](https://github.com/astral-sh/uv)

### 10.4 Glossário
| Termo | Descrição |
|-------|-----------|
| Agno | Framework Python para agentes AI |
| Gemini Flash | Modelo LLM rápido do Google |
| Intent | Permissão para receber eventos do Discord |
| Message Content | Permissão para ler conteúdo de mensagens |
| uv | Package manager Python moderno e rápido |
| .env | Arquivo com variáveis de ambiente |

---

**Documento Versão**: 1.0
**Última Atualização**: 2026-02-25
**Status**: Pronto para implementação

### 9.1 Melhorias Possíveis
- Adicionar mais modelos LLM (opção do usuário)
- Sistema de citações de fontes jurídicas
- Index de legislação e jurisprudência
- Multi-servidor com contexto isolado
- Webhooks para notificações

### 9.2 Decisões Arquiteturais Pendentes
- Estratégia de persistência (SQLite vs PostgreSQL)
- Cache de respostas frequentes
- Rate limiting por usuário/servidor
- Estratégia de backup de dados
