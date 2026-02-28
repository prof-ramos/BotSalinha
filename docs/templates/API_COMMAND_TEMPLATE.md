# API Template (Comandos Discord)

Template para documentar comandos do bot no padrão usado em `docs/api.md`.

````md
## `!<comando> <arg1> [arg2]`

Descrição curta do comando.

### Parâmetros

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| arg1 | string | Sim | Descrição do argumento |
| arg2 | string | Não | Descrição opcional |

### Respostas

- ✅ Sucesso: resultado esperado
- ⚠️ Erro de validação: erro de validação
- 🚫 Limite atingido: limite de uso atingido
- ❌ Erro: erro interno

### Exemplo

```text
!<comando> exemplo
```

### Observações de implementação

- Aplicar rate limiting por usuário/guild quando aplicável
- Exibir typing indicator para operações longas
- Tratar respostas com chunking quando ultrapassar limite de caracteres do Discord
````

