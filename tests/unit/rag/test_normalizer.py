"""Testes unitários para o normalizador de textos jurídicos."""

from __future__ import annotations

from src.rag.utils.normalizer import (
    LEGAL_ABBREVIATIONS,
    expand_legal_abbreviations,
    normalize_encoding,
    normalize_query_text,
)


class TestExpandLegalAbbreviations:
    """Testes para expansão de abreviações legais."""

    def test_expand_common_abbreviations(self):
        """Testa expansão de abreviações comuns."""
        # Códigos
        assert expand_legal_abbreviations("CP") == "Código Penal"
        assert expand_legal_abbreviations("CT") == "Código Tributário"
        assert expand_legal_abbreviations("CDC") == "Código de Defesa do Consumidor"
        assert expand_legal_abbreviations("CLT") == "Consolidação das Leis do Trabalho"
        assert expand_legal_abbreviations("CF") == "Constituição Federal"
        assert expand_legal_abbreviations("CF/88") == "Constituição Federal de 1988"

        # Tribunais
        assert expand_legal_abbreviations("STF") == "Supremo Tribunal Federal"
        assert expand_legal_abbreviations("STJ") == "Superior Tribunal de Justiça"
        assert expand_legal_abbreviations("STM") == "Superior Tribunal Militar"
        assert expand_legal_abbreviations("TSE") == "Tribunal Superior Eleitoral"

        # Outros
        assert expand_legal_abbreviations("RTF") == "Recurso de Extraordinário Federal"
        assert expand_legal_abbreviations("REsp") == "Recurso Especial"

    def test_case_insensitive_matching(self):
        """Testa que a correspondência é insensível a maiúsculas/minúsculas."""
        assert expand_legal_abbreviations("cp") == "Código Penal"
        assert expand_legal_abbreviations("Cp") == "Código Penal"
        assert expand_legal_abbreviations("CP") == "Código Penal"
        assert expand_legal_abbreviations("stf") == "Supremo Tribunal Federal"
        assert expand_legal_abbreviations("STJ") == "Superior Tribunal de Justiça"
        assert expand_legal_abbreviations("resp") == "Recurso Especial"

    def test_word_boundary_respect(self):
        """Testa que substituições respeitam limites de palavras."""
        # Não deve substituir substrings no meio de palavras
        assert "CP" in expand_legal_abbreviations("SCP12345")  # CP no meio
        assert "STF" in expand_legal_abbreviations("ESTF123")  # STF no meio

        # Deve substituir quando é uma palavra completa
        assert expand_legal_abbreviations("O CP prevê") == "O Código Penal prevê"
        assert expand_legal_abbreviations("STF decide") == "Supremo Tribunal Federal decide"

    def test_multiple_abbreviations_in_text(self):
        """Testa expansão de múltiplas abreviações no mesmo texto."""
        text = "O STF e o STJ decidiram sobre o CP"
        expected = "O Supremo Tribunal Federal e o Superior Tribunal de Justiça decidiram sobre o Código Penal"
        assert expand_legal_abbreviations(text) == expected

    def test_abbreviations_with_special_chars(self):
        """Testa abreviações com caracteres especiais."""
        assert expand_legal_abbreviations("CF/88") == "Constituição Federal de 1988"
        assert expand_legal_abbreviations("cf/88") == "Constituição Federal de 1988"

    def test_no_abbreviation_returns_original(self):
        """Testa que texto sem abreviações é retornado inalterado."""
        text = "Este é um texto jurídico sem abreviações conhecidas"
        assert expand_legal_abbreviations(text) == text

    def test_empty_string(self):
        """Testa tratamento de string vazia."""
        assert expand_legal_abbreviations("") == ""

    def test_longer_abbreviations_first(self):
        """Testa que abreviações mais longas têm prioridade."""
        # CF/88 deve ser expandido antes de CF
        text = "CF/88 e CF"
        result = expand_legal_abbreviations(text)
        assert "Constituição Federal de 1988" in result
        assert "Constituição Federal" in result


class TestNormalizeEncoding:
    """Testes para normalização de encoding."""

    def test_common_encoding_issues(self):
        """Testa correção de problemas comuns de encoding latin-1 corrompido."""
        assert normalize_encoding("Ã§") == "ç"
        assert normalize_encoding("Ã£") == "ã"
        assert normalize_encoding("Ã¡") == "á"
        assert normalize_encoding("Ã©") == "é"
        assert normalize_encoding("Ã­") == "í"
        assert normalize_encoding("Ã³") == "ó"
        assert normalize_encoding("Ãº") == "ú"

    def test_empty_string(self):
        """Testa tratamento de string vazia."""
        assert normalize_encoding("") == ""
        assert normalize_encoding(None) is None


class TestNormalizeQueryText:
    """Testes para normalização de texto de consulta."""

    def test_abbreviation_expansion_integration(self):
        """Testa que abreviações são expandidas durante normalização."""
        # A função expand_legal_abbreviations é chamada antes de outras normalizações
        query = "O que diz o STF sobre o CP?"
        result = normalize_query_text(query)
        # Verifica que as expansões ocorreram (antes da casefold)
        assert "supremo tribunal federal" in result
        assert "codigo penal" in result

    def test_casefold_after_expansion(self):
        """Testa que o texto é convertido para minúsculas após expansão."""
        query = "STF e CP"
        result = normalize_query_text(query)
        assert result == result.lower()

    def test_full_normalization_pipeline(self):
        """Testa o pipeline completo de normalização."""
        query = "O STF decide sobre o   CP  e  CDC"
        result = normalize_query_text(query)
        # Espaços múltiplos normalizados
        assert "  " not in result
        # Abreviações expandidas e em minúsculas
        assert "supremo tribunal federal" in result
        assert "codigo penal" in result
        assert "codigo de defesa do consumidor" in result

    def test_empty_query(self):
        """Testa tratamento de query vazia."""
        assert normalize_query_text("") == ""
        assert normalize_query_text(None) == ""

    def test_preserves_accents_after_expansion(self):
        """Testa que acentos são preservados/apropriadamente tratados."""
        query = "Constituição Federal"
        result = normalize_query_text(query)
        # NFKC normalization + casefold deve preservar acentos
        # mas remover diacríticos com NFD
        assert "constituicao" in result


class TestLegalAbbreviationsDictionary:
    """Testes para o dicionário de abreviações."""

    def test_dictionary_is_complete(self):
        """Testa que o dicionário contém as abreviações esperadas."""
        assert "CP" in LEGAL_ABBREVIATIONS
        assert "CT" in LEGAL_ABBREVIATIONS
        assert "CDC" in LEGAL_ABBREVIATIONS
        assert "CLT" in LEGAL_ABBREVIATIONS
        assert "CF" in LEGAL_ABBREVIATIONS
        assert "CF/88" in LEGAL_ABBREVIATIONS
        assert "STF" in LEGAL_ABBREVIATIONS
        assert "STJ" in LEGAL_ABBREVIATIONS
        assert "STM" in LEGAL_ABBREVIATIONS
        assert "TSE" in LEGAL_ABBREVIATIONS
        assert "RTF" in LEGAL_ABBREVIATIONS
        assert "REsp" in LEGAL_ABBREVIATIONS

    def test_dictionary_values_are_strings(self):
        """Testa que todos os valores são strings."""
        for abbr, expanded in LEGAL_ABBREVIATIONS.items():
            assert isinstance(abbr, str)
            assert isinstance(expanded, str)
            assert len(expanded) > len(abbr)  # Expandido deve ser maior

    def test_no_empty_abbreviations(self):
        """Testa que não há abreviações ou expansões vazias."""
        for abbr, expanded in LEGAL_ABBREVIATIONS.items():
            assert abbr
            assert expanded
