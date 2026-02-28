# ADR-001: Multi-Model Provider Source of Truth

## Status

Accepted

## Context

BotSalinha passou a suportar múltiplos providers de IA (`openai` e `google`), mas houve inconsistências históricas entre código, `.env` e documentação sobre quem define o provider ativo.

Isso gerava ambiguidade operacional e erros de configuração em runtime.

## Decision

O provider ativo será definido exclusivamente em `config.yaml` no campo `model.provider`.

- Valores válidos: `openai`, `google`
- Valor padrão: `openai`
- Credenciais ficam apenas no `.env`:
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`
- Não haverá variável de ambiente para escolher provider.

## Consequences

### Positive

- Contrato de configuração simples e previsível
- Menor chance de conflito entre ambiente e configuração versionada
- Troca de provider com impacto controlado e rastreável em arquivo único

### Trade-offs

- Mudanças de provider exigem edição de `config.yaml` (não apenas env override)
- Deploys automatizados precisam garantir sincronia entre `config.yaml` e segredos do ambiente
