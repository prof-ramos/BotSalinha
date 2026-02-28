# RAG

O projeto consiste em criar uma feature de RAG para o BotSalinha.
Diferente de chatbots convencionais, o BotSalinha incorporará RAG e memória, por isso responderá sobre assuntos jurídicos com qualidade e sem alucinações.
O BOT, caso não encontre em sua base documental a resposta, será sincero, e por isso o usuário precisará verificar a resposta.
Caso tenha encontrado no RAG, ele irá citar explicitamente a lei, jurisprudência, etc.
Para alimentar usaremos DOCX e PDF (Digitais nativos, não precisaremos de OCR).

## Segurança e Privacidade

- **LGPD:** Dados anonimizados quando necessário antes de vectorização.
- **Controles de Acesso:** Definição clara de roles (admin vs common user).
- **Criptografia:** Transit e Data-at-Rest garantidos.
- **Política de Retenção:** TTL ou descarte das consultas e indexações.

## Determinação de Confiança

- **Similaridade Cosine:** Threshold mínimo para aceite do contexto.
- **Top-K:** Quantidade dinâmica baseada na relevância da busca.
- **Score de Confiança:** Metrificação explícita de cada retrieval.
- **Fallback:** Resposta de "não encontrada" caso confidence < threshold.

## Arquitetura Técnica

- **Banco Vetorial:** Pinecone (ou Chroma/LanceDB local).
- **Modelo de Embeddings:** OpenAI (`text-embedding-3-small` / `text-embedding-3-large`).
- **LLM Alvo:** GPT-4o / Minit.
- **Estratégia de Chunking:** Tamanhos de 1000-2000 tokens com overlap razoável.
- **Pipeline de Ingestão:** Conversores customizados para DOCX/PDF nativos.

## Mecanismo de Citações

- **Formato da Fonte:** Respostas com blockquotes indicando a fonte do conhecimento.
- **Fragment Linking:** Referência exata à página, parágrafo e metadado do embasamento.
- **Metadados Auxiliares:** (lei, artigo, jurisprudência).

## Critérios de Qualidade e Métricas

- **Testes Automatizados:** PyTest e validações CI/CD.
- **Avaliações Humanas:** Feedback de usuários (thumbs up/down) pra fine-tuning do bot.
- **SLAs:** Tempo de resposta e acurácia.

## Estrutura de Implementação

- **Milestones:** Ingestão de documentos -> Geração de Embeddings -> Implementação RAG na cadeia de resposta.
- **Riscos:** Token limit exceeded, Injeção de Prompt no RAG.
- **Responsabilidades:** Equipe mantenedora para validação do parse e refino dos chunks.
