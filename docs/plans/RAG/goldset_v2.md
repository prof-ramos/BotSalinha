# Gold Set RAG Juridico v2

## Versao
- `2026-03-03`

## Objetivo
Dataset de regressao para validar:
- revogacao;
- veto;
- conflito temporal (pre/pós alteracao legislativa);
- citacao normativa minima (Lei + Artigo).

## Estrutura
- Arquivo de casos: `tests/fixtures/rag/goldset_v2.json`
- Schema do dataset: `metricas/goldset/rag_goldset_v2_schema.json`

## Criterios de Aceitacao
- Cada resposta deve conter ao menos uma citacao juridica no formato equivalente a `Lei X, Art. Y` quando aplicavel.
- Casos de revogacao/veto devem sinalizar explicitamente status normativo.
- Casos com conflito temporal devem distinguir entendimento anterior e posterior a alteracao legislativa.
- Nao deve haver afirmacoes categoricas sem lastro nos cenarios marcados como sensiveis.
