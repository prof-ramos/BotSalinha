"""Gerador de workload realista para testes de carga RAG."""

from __future__ import annotations

import random
from typing import Any


class LegalWorkloadGenerator:
    """
    Gera workload realista para concursos públicos.

    Produz queries jurídicas que simulam o comportamento
    real de estudantes de concursos buscando informações.
    """

    # Query patterns por categoria jurídica
    CONSTITUCIONAL = [
        "Quais são os direitos fundamentais previstos no art. 5º da CF/88?",
        "Explique o princípio da dignidade da pessoa humana na Constituição.",
        "O que é o princípio da legalidade no Direito Constitucional?",
        "Quais são os cláusulas pétreas da Constituição Federal?",
        "Explique a organização do Estado brasileiro na CF/88.",
        "O que é o princípio da isonomia?",
        "Quais são os direitos sociais previstos no art. 6º da CF?",
        "Explique o princípio da proporcionalidade.",
        "O que são remédios constitucionais?",
        "Qual é o papel do Supremo Tribunal Federal?",
        "Explique a estrutura do Poder Legislativo no Brasil.",
        "O que é o princípio da anterioridade tributária?",
        "Quais são as competências da União, Estados e Municípios?",
        "Explique o federalismo brasileiro.",
        "O que é o princípio da autonomia municipal?",
    ]

    ADMINISTRATIVO = [
        "O que é estágio probatório na Lei 8.112/90?",
        "Quais as formas de provimento de cargo público?",
        "Explique o princípio da publicidade na Administração Pública.",
        "O que é ato administrativo e seus elementos?",
        "Quais são os poderes da Administração Pública?",
        "Explique o princípio da impessoalidade.",
        "O que é licitação pública?",
        "Quais são as formas de desfazimento do ato administrativo?",
        "Explique a responsabilidade civil do Estado.",
        "O que são agentes públicos e suas classificações?",
        "Quais são as penalidades na Lei de Improbidade Administrativa?",
        "Explique o princípio da moralidade administrativa.",
        "O que é autoridade administrativa?",
        "Quais são os tipos de licitação?",
        "Explique o processo administrativo federal.",
    ]

    PENAL = [
        "Quais são os elementos do crime tipificado no art. 121 do CP?",
        "Qual a diferença entre crime doloso e culposo?",
        "Explique o erro de tipo e erro de proibição.",
        "Quais são as causas de exclusão da ilicitude?",
        "O que é crime consumado e tentado?",
        "Explique o concurso de pessoas no Direito Penal.",
        "Quais são as penas previstas no Código Penal?",
        "O que é regime de cumprimento de pena?",
        "Explique o princípio da legalidade penal.",
        "Quais são os crimes contra a administração pública?",
        "O que é crime hediondo?",
        "Explique a prescrição no Direito Penal.",
        "Quais são os tipos de concurso de crimes?",
        "O que é ação penal pública e privada?",
        "Explique o princípio da insignificância.",
    ]

    JURISPRUDENCIA = [
        "Qual a posição do STF sobre prisão em segunda instância?",
        "O que diz a Súmula Vinculante 11 do STF?",
        "Explique a jurisprudência sobre tema de repercussão geral.",
        "Qual o entendimento do STJ sobre prescrição retroativa?",
        "O que é a tese do tempo certo do STF?",
        "Explique a decisão sobre ADCT no STF.",
        "Qual a jurisprudência sobre crime de bagacinho?",
        "O que diz a Súmula 400 do STJ?",
        "Explique o entendimento sobre spam eletrônico no STJ.",
        "Qual a posição sobre crime de estelionato previdenciário?",
    ]

    CONCURSOS = [
        "Quais temas mais caem na prova da FCC?",
        "Perguntas sobre Direito Constitucional para concursos.",
        "Questões de Direito Administrativo da banca Cespe.",
        "Simulado de Direito Penal para concurso público.",
        "Resumo de Direito Tributário para provas.",
        "Dicas de Processo Civil para concursos.",
        "Questões comentadas de Direito do Trabalho.",
        "Temas recorrentes na banca Cebraspe.",
        "Prova anterior da banca Vunesp comentada.",
        "Questões de Direito Empresarial para concurso.",
    ]

    # Queries variadas para testar different aspectos
    GENERAL_QUERIES = CONSTITUCIONAL + ADMINISTRATIVO + PENAL + JURISPRUDENCIA + CONCURSOS

    # Queries específicas para testar filtros
    FILTER_QUERIES = {
        "artigo": [
            "O que diz o artigo 5º da Constituição?",
            "Explique o artigo 121 do Código Penal.",
            "Artigo 37 da CF sobre administração pública.",
        ],
        "jurisprudencia": [
            "Qual a posição do STF sobre?",
            "O que diz a Súmula Vinculante?",
            "Qual o entendimento do STJ?",
        ],
        "questao": [
            "Questões de concurso sobre",
            "Prova da banca",
            "Questão comentada de",
        ],
    }

    # Queries de complexidade variada (tamanho)
    SHORT_QUERIES = [
        "O que é habeas corpus?",
        "Princípio da legalidade.",
        "Tipos de penas.",
        "O que é prescrição?",
        "Cláusulas pétreas.",
    ]

    LONG_QUERIES = [
        "Explique detalhadamente o princípio da dignidade da pessoa humana no Direito Constitucional brasileiro, suas aplicações práticas e jurisprudência relevante do STF.",
        "Quais são todos os requisitos e elementos do crime conforme o Código Penal brasileiro, incluindo dolo, culpa, tipicidade, ilicitude e culpabilidade?",
        "Faça um comparativo completo entre as formas de provimento de cargo público na Lei 8.112/90, incluindo nomeação, promoção, readaptação e reversão.",
    ]

    def __init__(self, seed: int = 42) -> None:
        """
        Inicializar gerador de workload.

        Args:
            seed: Semente para geração aleatória (reprodutibilidade)
        """
        random.seed(seed)

    def get_random_query(self) -> str:
        """
        Retorna query aleatória do conjunto geral.

        Returns:
            Query jurídica aleatória
        """
        return random.choice(self.GENERAL_QUERIES)

    def get_query_by_category(self, category: str) -> str:
        """
        Retorna query de uma categoria específica.

        Args:
            category: Categoria (constitucional, administrativo, penal, jurisprudencia, concursos)

        Returns:
            Query da categoria especificada

        Raises:
            ValueError: Se categoria não existe
        """
        category_map = {
            "constitucional": self.CONSTITUCIONAL,
            "administrativo": self.ADMINISTRATIVO,
            "penal": self.PENAL,
            "jurisprudencia": self.JURISPRUDENCIA,
            "concursos": self.CONCURSOS,
        }

        queries = category_map.get(category.lower())
        if not queries:
            raise ValueError(
                f"Categoria inválida: {category}. "
                f"Use: {', '.join(category_map.keys())}"
            )

        return random.choice(queries)

    def get_query_by_length(self, length: str) -> str:
        """
        Retorna query por comprimento.

        Args:
            length: 'short', 'medium', 'long'

        Returns:
            Query do comprimento especificado
        """
        if length == "short":
            return random.choice(self.SHORT_QUERIES)
        elif length == "long":
            return random.choice(self.LONG_QUERIES)
        else:  # medium (default)
            return self.get_random_query()

    def get_query_batch(self, count: int) -> list[str]:
        """
        Gera lote de queries aleatórias.

        Args:
            count: Número de queries a gerar

        Returns:
            Lista de queries únicas (com repetição controlada)
        """
        queries = []
        for _ in range(count):
            queries.append(self.get_random_query())
        return queries

    def get_user_session_queries(self, query_count: int) -> list[str]:
        """
        Simula uma sessão de usuário com múltiplas queries.

        Args:
            query_count: Número de queries na sessão

        Returns:
            Lista de queries simulando comportamento real
        """
        queries = []

        # Usuário começa com query curta
        queries.append(self.get_query_by_length("short"))

        # Queries médias no meio
        for _ in range(max(0, query_count - 2)):
            queries.append(self.get_random_query())

        # Possível query complexa no final
        if query_count > 1 and random.random() > 0.7:
            queries[-1] = self.get_query_by_length("long")

        return queries

    def get_stress_test_queries(self, count: int) -> list[str]:
        """
        Queries otimizadas para stress testing (frases complexas).

        Args:
            count: Número de queries

        Returns:
            Lista de queries complexas
        """
        stress_queries = self.LONG_QUERIES + self.GENERAL_QUERIES
        return [random.choice(stress_queries) for _ in range(count)]

    @staticmethod
    def calculate_query_complexity(query: str) -> dict[str, Any]:
        """
        Calcula métricas de complexidade de uma query.

        Args:
            query: Texto da query

        Returns:
            Dicionário com métricas de complexidade
        """
        word_count = len(query.split())
        char_count = len(query)
        avg_word_length = char_count / word_count if word_count > 0 else 0

        # Categorias baseadas em tamanho
        if word_count <= 5:
            length_category = "short"
        elif word_count <= 15:
            length_category = "medium"
        else:
            length_category = "long"

        # Detectar palavras-chave
        keywords = {
            "artigo": "art." in query.lower() or "artigo" in query.lower(),
            "lei": "lei" in query.lower(),
            "constituição": "constituição" in query.lower() or "cf/88" in query.lower(),
            "stf": "stf" in query.lower(),
            "stj": "stj" in query.lower(),
            "concurso": "concurso" in query.lower() or "banca" in query.lower(),
            "crime": "crime" in query.lower(),
        }

        return {
            "word_count": word_count,
            "char_count": char_count,
            "avg_word_length": round(avg_word_length, 2),
            "length_category": length_category,
            "keywords": keywords,
        }


class UserSimulator:
    """
    Simula comportamento de usuário real para testes de carga.

    Implementa delays e padrões de uso realistas.
    """

    def __init__(self, user_id: str, generator: LegalWorkloadGenerator | None = None) -> None:
        """
        Inicializar simulador de usuário.

        Args:
            user_id: Identificador do usuário simulado
            generator: Gerador de workload (usa default se não fornecido)
        """
        self.user_id = user_id
        self.generator = generator or LegalWorkloadGenerator()
        self.query_count = 0

    async def simulate_user_session(
        self,
        query_service,
        queries_per_session: int = 10,
        min_delay: float = 0.5,
        max_delay: float = 2.0,
    ) -> list[dict[str, Any]]:
        """
        Simula uma sessão completa de usuário.

        Args:
            query_service: QueryService para executar queries
            queries_per_session: Número de queries na sessão
            min_delay: Delay mínimo entre queries (segundos)
            max_delay: Delay máximo entre queries (segundos)

        Returns:
            Lista de resultados das queries
        """
        import asyncio
        import time

        results = []
        queries = self.generator.get_user_session_queries(queries_per_session)

        for query in queries:
            # Random delay entre queries
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            # Executar query
            start_time = time.time()
            try:
                result = await query_service.query(query)
                elapsed_ms = (time.time() - start_time) * 1000
                results.append({
                    "success": True,
                    "query": query,
                    "latency_ms": elapsed_ms,
                    "result": result,
                })
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                results.append({
                    "success": False,
                    "query": query,
                    "latency_ms": elapsed_ms,
                    "error": str(e),
                })

            self.query_count += 1

        return results


__all__ = [
    "LegalWorkloadGenerator",
    "UserSimulator",
]
