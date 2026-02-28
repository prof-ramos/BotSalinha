# Integração MCP (Model Context Protocol)

## Objetivo

Adicionar suporte a servidores MCP ao BotSalinha para permitir que o bot accesses ferramentas externas e APIs através de uma interface padronizada, expandindo suas capacidades além do modelo de IA.

## Decisões de Implementação

### 1. Arquitetura de Configuração

**Decisão:** Usar Pydantic models para configuração de MCP, similar ao padrão existente em `yaml_config.py`.

**Motivos:**
- Consistencia com o codebase existente (validação de tipos, documentação inline via `Field`)
- Integração natural com o `yaml_config` singleton
- Validação em tempo de inicialização com mensagens de erro acionáveis

### 2. Transporte Suportado

**Decisão:** Suportar `stdio`, `sse` e `streamable-http`.

**Motivos:**
- `stdio`: Ideal para servidores locais (ex: filesystem, local AI services)
- `sse`/`streamable-http`: Necessário para servidores remotos e integração com APIs cloud
- Alinhado com as opções nativas do Agno MCPTools

### 3. Integração com AgentWrapper

**Decisão:** Adicionar `MCPToolsManager` como atributo privado e métodos `initialize_mcp()` e `cleanup_mcp()`.

**Motivos:**
- Inicialização lazy (sob demanda) para não impactar performance quando MCP está desabilitado
- Separação de responsabilidades (gerenciamento de lifecycle em métodos dedicados)
- Não blocking - falhas de MCP não impedem o funcionamento do bot

### 4. Prefixo de Nomes de Tools

**Decisão:** Adicionar campo opcional `tool_name_prefix` para cada servidor.

**Motivos:**
- Evita conflitos quando múltiplos servidores expõem tools com nomes iguais
- Melhora legibilidade e debugging (ex: `fs_read_file` vs `db_query`)

### 5. Recursos de Environment

**Decisão:** Suportar variáveis de ambiente por servidor via campo `env`.

**Motivos:**
- Necessário para passar API keys e secrets para servidores MCP
- Mantém separation of concerns (credenciais no env, configuração no YAML)

## Arquitetura de Arquivos

```
src/
├── config/
│   ├── mcp_config.py       # Modelos Pydantic para configuração MCP
│   └── yaml_config.py      # Adicionado campo mcp: MCPConfig
├── tools/
│   └── mcp_manager.py      # Gerenciador de conexões MCP
└── core/
    └── agent.py             # Integração com AgentWrapper
```

## Uso

### Habilitando MCP

Edite `config.yaml`:

```yaml
mcp:
  enabled: true
  servers:
    - name: filesystem
      enabled: true
      type: stdio
      command: npx -y @modelcontextprotocol/server-filesystem /caminho/para/diretorio
      tool_name_prefix: fs_
```

### Inicialização

O MCP é inicializado sob demanda via:

```python
agent = AgentWrapper()
await agent.initialize_mcp()  # Chamar durante startup do bot
```

### Cleanup

```python
await agent.cleanup_mcp()  # Chamar durante shutdown do bot
```

## Validação

- Configuração inválida falha rapidamente com mensagem clara
- Servidor MCP não conectado não impede funcionamento do bot
- Compatibilidade com provedores OpenAI e Google mantida
