# ANÁLISE DE CÓDIGO: BOTSALINHA

## RESUMO EXECUTIVO

- **Tipo de projeto:** Bot de Discord (IA/RAG) para Direito e Concursos.
- **Linguagem/Framework:** Python 3.12, `discord.py`, `agno`, `sqlalchemy` (Async), `pydantic`.
- **Estado Geral:** O código é de alta qualidade, seguindo padrões modernos de assincronia e tipagem. A arquitetura em camadas é bem definida, mas há pontos de atenção em segurança e transição de padrões.
- **Top 3 Prioridades:**
  1. **Segurança:** Proteção contra DoS via Unicode no sanitizador.
  2. **Performance:** Precisão na contagem de tokens para evitar quebras no LLM.
  3. **Arquitetura:** Centralização do tratamento de erros de UI e conclusão da migração para DI.

---

## 1. REVISÃO DE ARQUITETURA

### [ALTA] Centralização de Mapeamento de Erros de UI

- **Contexto:** Mapeamento de erros está disperso.
- **Impacto:** Risco de vazamento de logs técnicos para o usuário e inconsistência de UX.
- **Recomendação:** Criar um `ErrorRegistry` que mapeie `BotSalinhaError` para mensagens em PT-BR.

---

## 2. REVISÃO DE SEGURANÇA

### [CRÍTICA] Vulnerabilidade de DoS via Unicode

- **Contexto:** iteração caractere por caractere no `input_sanitizer.py` sem timeouts.
- **Impacto:** Atacante pode travar o bot enviando strings maliciosas.
- **Recomendação:** Limitar o comprimento da string _antes_ de processar e usar regex otimizada para categorias Unicode.

---

## 3. REVISÃO DE PERFORMANCE

### [MÉDIA] Estimativa de Tokens Imprecisa no RAG

- **Contexto:** Heurística `len(text) // 4` no `ChunkExtractor`.
- **Impacto:** Erros de Context Window no LLM ou perda de contexto.
- **Recomendação:** Usar `tiktoken` ou o tokenizador do Agno.

---

## 4. ANÁLISE DE DEPENDÊNCIAS

### [MÉDIA] Manutenção de Versões

- **Contexto:** Dependências como `pydantic` e `numpy` com ranges largos.
- **Ação:** Fixar versões minor e executar `uv lock --upgrade`.

---

## 5. REVISÃO DE TESTES

### [ALTA] Fragilidade em Testes de Integração de IA

- **Contexto:** Mocks de IA escondem erros de construção de prompt.
- **Recomendação:** Validar o prompt gerado e considerar Golden Tests para RAG.

---

## 6. QUALIDADE DE CÓDIGO E MANUTENIBILIDADE

### [MÉDIA] Transição de Padrão (Singleton vs DI)

- **Contexto:** Uso misto de `get_repository` e `create_repository`.
- **Ação:** Padronizar para Injeção de Dependência via construtores.

---

## 7. DOCUMENTAÇÃO

### [BAIXA] Exemplos de Metadados RAG

- **Recomendação:** Adicionar exemplos de metadados para diferentes tipos de leis no `DEVELOPER_GUIDE.md`.

---

## PLANO DE AÇÃO CONSOLIDADO (PRIORIZADO)

1. **Imediato:** Corrigir vulnerabilidade de DoS no sanitizador.
2. **Curto Prazo:** Implementar contagem precisa de tokens e centralizar mensagens de erro.
3. **Médio Prazo:** Refatorar Singletons remanescentes e evoluir suite de testes de RAG.
