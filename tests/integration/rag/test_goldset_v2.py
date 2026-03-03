"""Tests for legal goldset v2 fixtures and loader."""

from metricas.integrated_evaluation import load_goldset_v2_cases


def test_load_goldset_v2_cases_has_required_scenarios() -> None:
    cases = load_goldset_v2_cases()

    case_ids = {case.case_id for case in cases}
    assert {"GS-REV-001", "GS-VETO-001", "GS-TEMP-001", "GS-CIT-001"}.issubset(case_ids)


def test_load_goldset_v2_maps_query_types() -> None:
    cases = {case.case_id: case for case in load_goldset_v2_cases()}

    assert cases["GS-REV-001"].tipo == "artigo"
    assert cases["GS-VETO-001"].tipo == "artigo"
    assert cases["GS-TEMP-001"].tipo == "jurisprudencia"
