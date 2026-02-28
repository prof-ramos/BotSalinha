# BotSalinha Métricas

Este diretório contém scripts para geração e análise de métricas de performance e qualidade do BotSalinha.

## 📁 Estrutura de Diretórios

```
metricas/
├── config.py                    # Configuração centralizada (Pydantic)
├── utils.py                     # Funções utilitárias organizadas por categoria
├── base_metric.py               # Classe base abstrata para scripts de métrica
├── html_generator.py            # Gerador de HTML com Jinja2
├── run_all_metrics.py           # Script consolidado
├── gerar_performance.py         # Métricas end-to-end
├── gerar_performance_acesso.py  # Métricas de acesso ao banco
├── gerar_performance_rag.py     # Métricas de componentes RAG
├── gerar_qualidade.py           # Métricas de qualidade RAG
├── static/
│   └── report.css               # CSS externo (tema jurídico, WCAG AA)
├── templates/                   # Templates Jinja2
│   ├── base.html                # Template base
│   ├── summary.html             # Componente de sumário
│   ├── section.html             # Componente de seção
│   ├── charts.html              # Componente de gráficos
│   └── report.html              # Template principal
└── tests/                       # Testes unitários
    ├── conftest.py              # Fixtures pytest
    ├── test_config.py           # Tests de config.py
    └── test_utils.py            # Tests de utils.py
```

## 🏗️ Nova Arquitetura

### Módulos Principais

#### `config.py`
Configuração centralizada com Pydantic:
- Constantes centralizadas (thresholds, paths, timeouts)
- Type hints e validação
- Singleton pattern para cache

```python
from metricas.config import get_metrics_config

config = get_metrics_config()
print(config.rag_min_similarity)  # 0.4
print(config.script_timeout_seconds)  # 300
```

#### `html_generator.py`
Gerador de HTML usando Jinja2:
- Separação de dados e apresentação
- Templates reutilizáveis
- Suporte a gráficos customizáveis

```python
from metricas.html_generator import get_html_generator

generator = get_html_generator()
generator.generate_report(results, csv_data, metadata, output_path)
```

#### `base_metric.py`
Classe base abstrata para scripts de métrica:
- Interface padronizada
- Setup, coleta, salvamento automáticos
- Reduz duplicação de código

```python
from metricas.base_metric import BaseMetric

class MyMetric(BaseMetric):
    async def collect(self, **kwargs):
        # Coleta de dados
        return results
```

#### `utils.py`
Funções utilitárias organizadas por categoria:
- **Logging**: configure_logging, get_logger
- **CLI**: get_base_parser
- **CSV**: save_results_csv, save_summary_csv, load_csv, read_csv_dict
- **HTML**: escape_html, generate_html_table
- **Time**: format_duration, format_timestamp, Timer
- **Stats**: calculate_stats, format_percentile
- **Display**: print_summary_box, print_progress

### Sistema de Templates

Templates Jinja2 modulares no diretório `templates/`:
- `base.html`: Estrutura HTML base
- `summary.html`: Cards de sumário
- `section.html`: Seções de métricas
- `charts.html`: Gráficos de barras
- `report.html`: Relatório consolidado

### CSS Externo

Arquivo `static/report.css` com:
- Variáveis CSS customizáveis
- Tema jurídico (dark com gold accents)
- WCAG AA compliant (contraste melhorado)
- Animações suaves
- Responsivo (mobile-friendly)
- Suporte a prefers-reduced-motion

### Testes Unitários

Diretório `tests/` com:
- `test_config.py`: Testes de configuração
- `test_utils.py`: Testes de utilitários
- `conftest.py`: Fixtures pytest
- Meta: >=70% cobertura

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

```text
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

## 🧪 Testes

### Executar testes unitários

```bash
# Todos os testes
pytest metricas/tests/

# Testes específicos
pytest metricas/tests/test_config.py
pytest metricas/tests/test_utils.py

# Com coverage
pytest metricas/tests/ --cov=metricas --cov-report=html

# Verbose
pytest metricas/tests/ -v
```

### Fixtures disponíveis

- `temp_dir`: Diretório temporário para testes
- `sample_metrics_data`: Dados de exemplo
- `sample_csv_data`: CSV de exemplo
- `sample_html_template`: Template HTML de exemplo

## 🔧 Troubleshooting

### Erro: "No module named 'structlog'"

**Problema:** Dependência não instalada.

**Solução:**
```bash
uv sync
```

### Erro: "Database file not found"

**Problema:** Banco de dados não inicializado.

**Solução:**
```bash
# Executar migrações
uv run alembic upgrade head
```

### Teste de qualidade retorna SEM_RAG para todas as queries

**Problema:** Threshold de similaridade muito alto ou embeddings não gerados.

**Solução:**
```bash
# Verificar configuração de min_similarity
# Valor padrão ajustado: 0.4 (baseado em dados empíricos)

# Reindexar embeddings se necessário
uv run python scripts/ingest_legal_content.py
```

### Relatório HTML não mostra estilos

**Problema:** Caminho do CSS relativo incorreto.

**Solução:**
- CSS deve estar em `metricas/static/report.css`
- HTML deve ter `<link rel="stylesheet" href="../static/report.css">`

### Timeout em scripts de métrica

**Problema:** Script demorando mais que o padrão (5 minutos).

**Solução:**
```bash
# Ajustar timeout em config.py ou passar parâmetro
uv run python metricas/gerar_performance.py --prompts 5  # Menos prompts
```

## 📊 Métricas e Interpretação

### Qualidade RAG

| Confiança | Similaridade | Interpretação |
|-----------|--------------|---------------|
| ALTA | >= 0.70 | Conteúdo muito relevante |
| MÉDIA | 0.55 - 0.70 | Conteúdo relevante |
| BAIXA | 0.40 - 0.55 | Conteúdo marginalmente relevante |
| SEM_RAG | < 0.40 | Nenhum conteúdo relevante encontrado |

### Performance

| Latência | Classificação |
|----------|---------------|
| < 1s | Excelente |
| 1s - 3s | Bom |
| 3s - 5s | Aceitável |
| > 5s | Lento |

## 🔄 Migração de Scripts Legados

Se você tem scripts antigos de métrica, migre para a nova estrutura:

**Antes:**
```python
import asyncio
import csv
from pathlib import Path

async def my_metric():
    results = []
    # ... coleta de dados ...
    with open('output.csv', 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['col1', 'col2'])
        writer.writerows(results)
```

**Depois:**
```python
from metricas.base_metric import BaseMetric, create_metric_cli
from metricas.utils import get_base_parser

class MyMetric(BaseMetric):
    def __init__(self):
        super().__init__(
            name='my_metric',
            description='Minha métrica customizada',
            output_file='my_metric.csv'
        )

    async def collect(self, **kwargs):
        results = []
        # ... coleta de dados ...
        return results

def main() -> None:
    create_metric_cli(MyMetric)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
