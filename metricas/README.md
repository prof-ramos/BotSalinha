# BotSalinha Métricas

Esse diretório é responsável por conter as métricas do BotSalinha.

Para executar os scripts de métricas, use o gerenciador de pacotes `uv` a partir da raiz do projeto:

```bash
uv run python metricas/<nome_do_script>.py
```

Os resultados serão salvos como arquivos CSV dentro da pasta `metricas/`.

## Métricas

### Métricas de Qualidade

O script `gerar_qualidade.py` executa consultas de teste no sistema RAG simulando requisições do usuário.
Ele avalia os chunks recuperados, calculando similaridade máxima, similaridade média e determinando as taxas de confiança do contexto.

### Métricas de Performance

O script `gerar_performance.py` testa a latência real de ponta a ponta que o Agente do BotSalinha gasta para responder prompts no chat.

#### Métricas de Performance de RAG

O script `gerar_performance_rag.py` isola os componentes do RAG para medir individualmente:

1. Tempo de resposta da OpenAI para Geração de Embeddings
2. Tempo de varredura do banco de dados vetorial local (SQLite Vector Store)

#### Métricas de Performance de Acesso

O script `gerar_performance_acesso.py` executa centenas de escritas e leituras massivas e concorrentes no banco de dados SQLite para testar a escalabilidade das operações CRUD em uso de CPU/Disco local.
