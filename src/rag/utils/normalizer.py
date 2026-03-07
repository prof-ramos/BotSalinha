"""Normalizador de encoding para documentos jurídicos brasileiros."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_MULTISPACE_RE = re.compile(r"\s+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")

# Legal abbreviations expansion dictionary
LEGAL_ABBREVIATIONS: dict[str, str] = {
    # Códigos
    "CP": "Código Penal",
    "CPP": "Código de Processo Penal",
    "CT": "Código Tributário",
    "CTN": "Código Tributário Nacional",
    "CDC": "Código de Defesa do Consumidor",
    "CLT": "Consolidação das Leis do Trabalho",
    "CF/88": "Constituição Federal de 1988",
    "CF": "Constituição Federal",
    "CB": "Código Brasileiro",
    "CBo": "Código Civil",
    "CC": "Código Civil",
    # Tribunais Superiores
    "STF": "Supremo Tribunal Federal",
    "STJ": "Superior Tribunal de Justiça",
    "STM": "Superior Tribunal Militar",
    "TSE": "Tribunal Superior Eleitoral",
    "TST": "Tribunal Superior do Trabalho",
    "TCU": "Tribunal de Contas da União",
    # Tribunais Regionais
    "TRF": "Tribunal Regional Federal",
    "TRT": "Tribunal Regional do Trabalho",
    "TRE": "Tribunal Regional Eleitoral",
    "TCE": "Tribunal de Contas do Estado",
    "TCM": "Tribunal de Contas do Município",
    # Recursos
    "RTF": "Recurso de Extraordinário Federal",
    "RE": "Recurso Extraordinário",
    "REsp": "Recurso Especial",
    "RExt": "Recurso Extraordinário",
    "AI": "Agravo de Instrumento",
    "AR": "Agravo Regimental",
    "AG": "Agravo",
    "ED": "Embargos de Declaração",
    "EI": "Embargos Infringentes",
    "EN": "Embargos de Divergência",
    # Ações Constitucionais
    "ADI": "Ação Direta de Inconstitucionalidade",
    "ADC": "Ação Declaratória de Constitucionalidade",
    "ADPF": "Arguição de Descumprimento de Preceito Fundamental",
    "MI": "Mandado de Injunção",
    "HC": "Habeas Corpus",
    "HD": "Habeas Data",
    "MS": "Mandado de Segurança",
    "RHC": "Recurso em Habeas Corpus",
    "RMS": "Recurso em Mandado de Segurança",
    "RMI": "Recurso em Mandado de Injunção",
    # Ações Civis
    "AC": "Ação Civil",
    "AP": "Ação Penal",
    "APn": "Ação Penal",
    "RCL": "Reclamação",
    "PET": "Petição",
    "SL": "Súmula Vinculante",
    "SV": "Súmula Vinculante",
}

LEGAL_QUERY_SYNONYMS: dict[str, str] = {
    # Improbidade Administrativa (Lei 8.429/1992)
    "lia": "Lei 8.429/1992",
    "lei de improbidade": "Lei 8.429/1992",
    "improbidade administrativa": "Lei 8.429/1992",
    "lei anti-corrupcao": "Lei 8.429/1992",
    "lei anticorrupcao": "Lei 8.429/1992",
    "acao de improbidade": "Lei 8.429/1992",

    # Licitações (Lei 14.133/2021 - nova, Lei 8.666/1993 - antiga)
    "nova lei de licitacoes": "Lei 14.133/2021",
    "lei de licitacoes nova": "Lei 14.133/2021",
    "lei de licitações nova": "Lei 14.133/2021",
    "lei 14133": "Lei 14.133/2021",
    "estatuto da licitacao": "Lei 14.133/2021",
    "estatuto da licitação": "Lei 14.133/2021",
    "lei de licitacoes": "Lei 14.133/2021",
    "lei de licitacoes antiga": "Lei 8.666/1993",
    "lei 8666": "Lei 8.666/1993",

    # Código Civil (Lei 10.406/2002)
    "codigo civil": "Lei 10.406/2002",
    "código civil": "Lei 10.406/2002",
    "cc": "Código Civil",
    "cod civil": "Código Civil",

    # Código Penal (Decreto-Lei 2.848/1940)
    "codigo penal": "Decreto-Lei 2.848/1940",
    "código penal": "Decreto-Lei 2.848/1940",
    "cp": "Código Penal",
    "cod penal": "Código Penal",
    "lei penal": "Decreto-Lei 2.848/1940",

    # CPP (Decreto-Lei 3.689/1941)
    "codigo processo penal": "Decreto-Lei 3.689/1941",
    "código de processo penal": "Decreto-Lei 3.689/1941",
    "cpp": "Código de Processo Penal",

    # CLT (Decreto-Lei 5.452/1943)
    "clt": "Consolidação das Leis do Trabalho",
    "consolidacao das leis do trabalho": "Decreto-Lei 5.452/1943",

    # CF/88
    "constituicao federal": "Constituição Federal de 1988",
    "constituição federal": "Constituição Federal de 1988",
    "cf": "Constituição Federal de 1988",
    "cf/88": "Constituição Federal de 1988",
    "cf88": "Constituição Federal de 1988",
    "constituicao de 1988": "Constituição Federal de 1988",
    "constituição de 88": "Constituição Federal de 1988",
    "constituinte": "Constituição Federal de 1988",

    # CDC (Lei 8.078/1990)
    "cdc": "Código de Defesa do Consumidor",
    "codigo defesa consumidor": "Lei 8.078/1990",
    "lei do consumidor": "Lei 8.078/1990",
    "codigo de defesa do consumidor": "Lei 8.078/1990",

    # CTN (Lei 5.172/1966)
    "codigo tributario": "Lei 5.172/1966",
    "código tributário": "Lei 5.172/1966",
    "ctn": "Código Tributário Nacional",
    "lei 5172": "Lei 5.172/1966",

    # Lei de Introdução (Lei 4.320/1964 - LICC antiga, LINDB atual)
    "licc": "Lei de Introdução às Normas do Direito Brasileiro",
    "lintro": "Lei de Introdução às Normas do Direito Brasileiro",
    "lei de introducao": "Lei de Introdução às Normas do Direito Brasileiro",
    "lei de introdução": "Lei de Introdução às Normas do Direito Brasileiro",
    "lin": "Lei de Introdução às Normas do Direito Brasileiro",
    "linb": "Lei de Introdução às Normas do Direito Brasileiro",
    "linbd": "Lei de Introdução às Normas do Direito Brasileiro",
    "lindeb": "Lei de Introdução às Normas do Direito Brasileiro",

    # Estatuto do Idoso (Lei 10.741/2003)
    "estatuto do idoso": "Lei 10.741/2003",
    "lei do idoso": "Lei 10.741/2003",

    # Estatuto da Criança (ECA - Lei 8.069/1990)
    "eca": "Estatuto da Criança e do Adolescente",
    "estatuto da crianca": "Lei 8.069/1990",
    "estatuto da criança e adolescente": "Lei 8.069/1990",
    "lei 8069": "Lei 8.069/1990",

    # Maria da Penha (Lei 11.340/2006)
    "lei maria da penha": "Lei 11.340/2006",
    "maria da penha": "Lei 11.340/2006",
    "lei da mulher": "Lei 11.340/2006",
    "lei 11340": "Lei 11.340/2006",

    # Lei Seca (Lei 11.705/2008)
    "lei seca": "Lei 11.705/2008",
    "lei 11705": "Lei 11.705/2008",
    "lei seca transito": "Lei 11.705/2008",

    # Ficha Limpa (Lei Complementar 135/2010)
    "ficha limpa": "Lei Complementar 135/2010",
    "lei ficha limpa": "Lei Complementar 135/2010",
    "lc 135": "Lei Complementar 135/2010",

    # Lei Geral de Proteção de Dados (Lei 13.709/2018)
    "lgpd": "Lei Geral de Proteção de Dados",
    "lei de protecao de dados": "Lei 13.709/2018",
    "lei de proteção de dados": "Lei 13.709/2018",
    "lei 13709": "Lei 13.709/2018",

    # Direito Civil - temas comuns
    "prescricao": "prescrição",
    "prescriçao": "prescrição",
    "decadencia": "decadência",
    "decadencia civil": "decadência civil",
    "atos civis": "atos jurídicos",
    "fatos civis": "fatos jurídicos",

    # Direito Penal - temas comuns
    "crime hediondo": "crimes hediondos",
    "crime contra a administracao publica": "crimes contra a administração pública",
    "crime contra a administracao": "crimes contra a administração pública",
    "crime contra o patrimonio": "crimes contra o patrimônio",
    "furto qualificado": "furto qualificado",
    "roubo circunstanciado": "roubo circunstanciado",

    # Direito Constitucional
    "remedio constitucional": "remédios constitucionais",
    "acao constitucional": "ações constitucionais",
    "clausulas petreas": "cláusulas pétreas",
    "clausulas ptreas": "cláusulas pétreas",

    # Direito Administrativo
    "ato administrativo": "atos administrativos",
    "licitacao": "licitação",
    "contrato administrativo": "contratos administrativos",
    "concurso publico": "concurso público",
    "servidor publico": "servidor público",
    "statu": "estatuto",
    "estatu": "estatuto",
}

ARTICLE_PATTERN = re.compile(r"\bart(?:igo)?\.?\s*(\d+(?:-[a-z])?)\b", re.IGNORECASE)
LAW_PATTERN = re.compile(
    r"\blei\s*(?:n[º°o]\.?\s*)?(\d{1,5}(?:\.\d{3})?)(?:/(\d{2,4}))?\b",
    re.IGNORECASE,
)


def normalize_encoding(text: str) -> str:
    """
    Normaliza encoding de documentos jurídicos brasileiros.
    Converte problemas comuns de latin-1 corrompido para utf-8.

    Args:
        text: Texto original possivelmente com caracteres corrompidos.

    Returns:
        Texto normalizado com caracteres corrigidos.
    """
    if not text:
        return text

    # Substituições comuns de encoding latin-1 corrompido
    replacements = {
        "Ã§": "ç",
        "Ã£": "ã",
        "Ãµ": "õ",
        "Ã¡": "á",
        "Ã©": "é",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ã¢": "â",
        "Ãª": "ê",
        "Ã´": "ô",
        "Ã\xa0": "à",
        "Ã\x81": "Á",
        "Ã‰": "É",
        "â€œ": '"',
        "â€ ": '"',
        "â€˜": "'",
        "â€™": "'",
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    return text


def expand_legal_abbreviations(text: str) -> str:
    """Expand legal abbreviations in text (case-insensitive, word-boundary aware)."""
    # Sort by length (descending) to avoid partial replacements
    abbrevs = sorted(LEGAL_ABBREVIATIONS.items(), key=lambda x: -len(x[0]))

    result = text
    for abbr, expanded in abbrevs:
        # Match word boundaries, case-insensitive
        pattern = r'\b' + re.escape(abbr) + r'\b'
        result = re.sub(pattern, expanded, result, flags=re.IGNORECASE)

    return result


def normalize_query_text(text: str) -> str:
    """
    Normaliza texto de consulta para recuperação RAG.

    Aplica NFKC, remove caracteres de controle, normaliza espaços e
    preserva marcadores jurídicos relevantes (ex.: "art.", "§", "inciso").

    Args:
        text: Texto bruto de consulta.

    Returns:
        Texto normalizado para embedding e ranking lexical.
    """
    if not text:
        return ""

    # Expand legal abbreviations
    text = expand_legal_abbreviations(text)

    normalized = normalize_encoding(text)
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = _CONTROL_CHARS_RE.sub(" ", normalized)
    normalized = normalized.replace("º", "o").replace("°", "o")
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.casefold()
    normalized = _MULTISPACE_RE.sub(" ", normalized).strip()
    return normalized


def rewrite_legal_query(text: str) -> tuple[str, dict[str, Any]]:
    """
    Reescreve consultas jurídicas com base em dicionário de sinônimos controlado.

    Returns:
        Tupla (texto_reescrito, metadata_da_reescrita)
    """
    if not text:
        return "", {"applied": False, "matches": [], "original": text, "rewritten": ""}

    rewritten = text
    matches: list[dict[str, str]] = []
    lowered = rewritten.casefold()

    for source, target in sorted(LEGAL_QUERY_SYNONYMS.items(), key=lambda item: -len(item[0])):
        source_lower = source.casefold()
        if source_lower not in lowered:
            continue
        pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
        rewritten, count = pattern.subn(target, rewritten)
        if count > 0:
            lowered = rewritten.casefold()
            matches.append({"term": source, "target": target, "count": str(count)})

    return rewritten, {
        "applied": bool(matches),
        "matches": matches,
        "original": text,
        "rewritten": rewritten,
    }


def extract_legal_filters_from_query(normalized_query: str) -> dict[str, Any]:
    """Extrai filtros jurídicos estruturados a partir da query normalizada."""
    filters: dict[str, Any] = {}
    if not normalized_query:
        return filters

    article_match = ARTICLE_PATTERN.search(normalized_query)
    if article_match:
        filters["artigo"] = article_match.group(1).upper()

    law_match = LAW_PATTERN.search(normalized_query)
    if law_match:
        law_number = law_match.group(1).replace(".", "")
        law_year = law_match.group(2)
        filters["law_number"] = (
            f"{law_number}/{law_year}" if law_year else law_number
        )

    if "stf" in normalized_query or "supremo tribunal federal" in normalized_query:
        filters["marca_stf"] = True
    if "stj" in normalized_query or "superior tribunal de justica" in normalized_query:
        filters["marca_stj"] = True

    if any(term in normalized_query for term in ("jurisprudencia", "sumula", "acordao")):
        filters["content_type"] = "jurisprudence"
        filters["source_type"] = "jurisprudence"
    elif any(term in normalized_query for term in ("concurso", "questao", "prova")):
        filters["content_type"] = "exam_question"
        filters["source_type"] = "exam_question"
        filters["is_exam_focus"] = True
    elif any(term in normalized_query for term in ("doutrina", "manual", "comentario")):
        filters["content_type"] = "doctrine"
        filters["source_type"] = "commentary"
    elif any(term in normalized_query for term in ("artigo", "lei", "caput", "inciso")):
        filters["content_type"] = "legal_text"
        filters["source_type"] = "lei_cf"

    return filters


__all__ = [
    "normalize_encoding",
    "expand_legal_abbreviations",
    "normalize_query_text",
    "rewrite_legal_query",
    "extract_legal_filters_from_query",
    "LEGAL_QUERY_SYNONYMS",
]
