# Referência do CLI BotSalinha

O BotSalinha agora possui uma Interface de Linha de Comando (CLI) rica e iterativa, desenvolvida com `Typer` e `Rich` para proporcionar a melhor experiência de desenvolvimento e operação.

## Instalação e Autocompletar

Para habilitar o autocompletar de comandos no seu terminal:

```bash
# Para Bash
uv run botsalinha --install-completion bash

# Para Zsh
uv run botsalinha --install-completion zsh
```

## Opções Globais

Essas opções podem ser usadas com qualquer comando:

- `--version` / `-V`: Mostra a versão do CLI.
- `--verbose` / `-v`: Ativa o modo verboso para logs detalhados.
- `--debug` / `-d`: Ativa o modo de depuração.

## Comandos Principais

### Execução do Bot

- `botsalinha run` (ou `start`): Inicia o bot no modo Discord (Padrão).
- `botsalinha stop`: Interrompe a execução do processo do bot baseando-se no PID.
- `botsalinha restart`: Reinicia o processo do bot de forma limpa.
- `botsalinha chat`: Inicia um chat interativo no terminal utilizando histórico persistente. Retira a dependência do Discord para testar as respostas do LLM e o fluxo completo do Agno.

### Gerenciamento de Banco de Dados (`db`)

Operações relativas ao armazenamento em SQLite de mensagens e conversas.

- `botsalinha db status`: Exibe estatísticas gerais como total de conversas e mensagens cadastradas.
- `botsalinha db clear`: Remove permanentemente todo o histórico de conversas e mensagens do banco após pedir confirmação.

### Gerenciamento de Configuração (`config`)

Permite inspecionar e manipular o `config.yaml` e as variáveis carregadas do arquivo `.env`.

- `botsalinha config show`: Exibe um print syntax-highlighted de todas as propriedades de configuração carregadas.
- `botsalinha config set <chave> <valor>`: Permite editar as configurações na hora, por exemplo `botsalinha config set model.temperature 0.5`.
- `botsalinha config export`: Exporta toda a visão de configuração local para um `.json` seguro, ideal para depuração em ticket de suporte.

### Gerenciamento de Prompts (`prompt`)

Permite injetar diferentes fluxos de pensamento de maneira flexível.

- `botsalinha prompt list`: Exibe uma matriz formatada constando arquivos de prompt disponíveis comparando com o arquivo ativo.
- `botsalinha prompt show`: Renderiza no terminal com `Rich` o conteúdo integral do prompt ativo.
- `botsalinha prompt use <nome>`: Habilita um novo _system prompt_ através do nome do arquivo (ex.: `prompt_v2.json`).

### Gerenciamento de Logs (`logs`)

Auxilia a navegar os rastros deixados pelos `structlogs`.

- `botsalinha logs show`: Lista pelo terminal as tail lines do arquivo de log mais recente gerado no diretório `data/logs`.
- `botsalinha logs export`: Exporta o compilado de logs mais recentes para um arquivo fácil de anexar em Issues.

### Gerenciamento de Integrações MCP (`mcp`)

- `botsalinha mcp list`: Lista e valida as extensões Model Context Protocol que estão localmente inicializadas junto à IA do BotSalinha.

### Utilitários Diversos (`backup`)

- `botsalinha backup [action]`: Wrapper que interage de maneira limpa com os scripts de backup criados nativamente operando (backup, restore, e list) acima das pastas `backups/`.
