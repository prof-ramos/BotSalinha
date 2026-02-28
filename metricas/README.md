# BotSalinha Métricas

Este diretório contém scripts para geração e análise de métricas de performance e qualidade do BotSalinha.

## 🚀 Uso Rápido

### Executar um script individual

```bash
# Usar configurações padrão
uv run python metricas/gerar_performance.py

# Com argumentos personalizados
uv run python metricas/gerar_performance.py --prompts 10 --output meus_resultados.csv --quiet
```

### Executar todas as métricas (relatório consolidado)

```bash
# Executar todos os testes
uv run python metricas/run_all_metrics.py

# Pular testes específicos
uv run python metricas/run_all_metrics.py --skip-performance --skip-quality
```

---

## 📊 Scripts Disponíveis

### 1. Métricas de Qualidade RAG

**Script:** `gerar_qualidade.py`

Executa consultas de teste no sistema RAG simulando requisições reais de usuários.

**Métricas geradas:**
- Similaridade média e máxima por query
- Distribuição de confiança (ALTA, MÉDIA, BAIXA, SEM_RAG)
- Chunks recuperados por query
- Latência de busca

**Argumentos CLI:**
```bash
uv run python metricas/gerar_qualidade.py [OPTIONS]

Options:
  --output, -o PATH      Caminho do CSV de saída (default: metricas/qualidade_rag.csv)
  --queries, -q INT      Número de queries a testar (default: 6)
  --verbose, -v          Modo verbose de logging
  --quiet, -q            Suprimir logs informativos
  --help                 Mostrar mensagem de ajuda
```

**Arquivos gerados:**
- `qualidade_rag.csv` - Dados brutos
- `qualidade_rag_summary.csv` - Métricas agregadas

---

### 2. Métricas de Performance End-to-End

**Script:** `gerar_performance.py`

Testa a latência real de ponta a ponta do AgentWrapper para responder prompts no chat.

**Métricas geradas:**
- Tempo de resposta por prompt
- Comprimento da resposta gerada
- Uso de RAG (sim/não)
- Taxa de sucesso
- Percentil 95 de latência

**Argumentos CLI:**
```bash
uv run python metricas/gerar_performance.py [OPTIONS]

Options:
  --output, -o PATH      Caminho do CSV de saída (default: metricas/performance_geral.csv)
  --prompts, -p INT      Número de prompts a testar (default: 4)
  --verbose, -v          Modo verbose de logging
  --quiet, -q            Suprimir logs informativos
  --help                 Mostrar mensagem de ajuda
```

**Arquivos gerados:**
- `performance_geral.csv` - Dados brutos
- `performance_geral_summary.csv` - Métricas agregadas

---

### 3. Métricas de Performance de RAG (Componentes)

**Script:** `gerar_performance_rag.py`

Isola os componentes do RAG para medição individual.

**Métricas geradas:**
- Tempo de geração de embedding (OpenAI API)
- Tempo de busca vetorial (SQLite)
- Correlação tamanho do texto → tempo de embedding
- Chunks encontrados por busca

**Argumentos CLI:**
```bash
uv run python metricas/gerar_performance_rag.py [OPTIONS]

Options:
  --output, -o PATH      Caminho do CSV de saída (default: metricas/performance_rag_componentes.csv)
  --texts, -t INT        Número de textos a testar (default: 6)
  --verbose, -v          Modo verbose de logging
  --quiet, -q            Suprimir logs informativos
  --help                 Mostrar mensagem de ajuda
```

**Arquivos gerados:**
- `performance_rag_componentes.csv` - Dados brutos
- `performance_rag_componentes_summary.csv` - Métricas agregadas

---

### 4. Métricas de Performance de Acesso ao Banco

**Script:** `gerar_performance_acesso.py`

Executa operações massivas de escrita e leitura no SQLite para testar escalabilidade CRUD.

**Métricas geradas:**
- Throughput (operações/segundo)
- Latência média de insert
- Latência média de read
- Ratio insert vs read

**Argumentos CLI:**
```bash
uv run python metricas/gerar_performance_acesso.py [OPTIONS]

Options:
  --output, -o PATH      Caminho do CSV de saída (default: metricas/performance_acesso.csv)
  --inserts, -i INT      Número de operações de insert (default: 50)
  --reads, -r INT        Número de operações de read (default: 100)
  --verbose, -v          Modo verbose de logging
  --quiet, -q            Suprimir logs informativos
  --help                 Mostrar mensagem de ajuda
```

**Arquivos gerados:**
- `performance_acesso.csv` - Dados brutos
- `performance_acesso_summary.csv` - Métricas agregadas

---

### 5. Script Consolidado (Todas as Métricas)

**Script:** `run_all_metrics.py`

Executa todos os scripts de métricas em sequência e gera um relatório HTML consolidado.

**Funcionalidades:**
- Execução sequencial dos 4 scripts
- Relatório HTML com:
  - Cards de sumário (total/sucesso/falha)
  - Gráficos de barras CSS
  - Tabelas com dados
  - Status badges

**Argumentos CLI:**
```bash
uv run python metricas/run_all_metrics.py [OPTIONS]

Options:
  --skip-performance     Pular teste de performance end-to-end
  --skip-quality         Pular teste de qualidade RAG
  --skip-access          Pular teste de acesso ao banco
  --skip-rag             Pular teste de componentes RAG
  --help                 Mostrar mensagem de ajuda
```

**Arquivo gerado:**
- `relatorio_consolidado_<timestamp>.html` - Relatório visual completo

---

## 📈 Formato dos Arquivos de Saída

### CSV Principal (dados brutos)
Contém uma linha por medição com todos os campos coletados.

### CSV Summary (`_summary.csv`)
Contém métricas agregadas calculadas:
- Médias, medianas, percentis
- Distribuições (porcentagens)
- Correlações
- Throughput

### Console Output
Cada script exibe um sumário estatístico formatado no console ao final da execução:

```
============================================================
SUMÁRIO ESTATÍSTICO - PERFORMANCE ACESSO DB
============================================================
Throughput:                    792.18 ops/segundo

Comparação Insert vs Read:
  Insert: 2.74ms avg (10 ops)
  Read:   0.52ms avg (20 ops)
  Ratio (Read/Insert):         0.19x

Total de operações:            30
Tempo total:                   0.038s
============================================================
```

---

## 🎯 Exemplos de Uso

### Teste rápido (defaults)
```bash
uv run python metricas/run_all_metrics.py --skip-performance
```

### Teste completo com customização
```bash
# Acesso ao banco - mais operações
uv run python metricas/gerar_performance_acesso.py --inserts 100 --reads 500

# RAG qualidade - mais queries
uv run python metricas/gerar_qualidade.py --queries 20 --output qualidade_extenso.csv
```

### Modo silencioso (para CI/CD)
```bash
uv run python metricas/run_all_metrics.py --quiet
```

### Ver detalhes com verbose
```bash
uv run python metricas/gerar_performance.py --verbose --prompts 2
```

---

## 📋 Notas Técnicas

- Todos os scripts usam `asyncio` para operações assíncronas
- O banco de dados usa modo WAL para melhor concorrência
- Embeddings são gerados via OpenAI API (text-embedding-3-small)
- Testes limpeza após execução (delete de dados de teste)
- Formato de data/hora nos relatórios: `YYYYMMDD_HHMMSS`
