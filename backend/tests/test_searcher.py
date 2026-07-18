"""Unit tests for fuzzy medicine search (builds its own in-memory index)."""

import pandas as pd

from app.services.preprocessor import create_search_index
from app.services.searcher import search_medicine


def _inventory():
    df = pd.DataFrame([
        {"item_code": 1, "product_name": "Pantop Tab 40mg", "pack_name": "15s"},
        {"item_code": 2, "product_name": "Aciloc Tab 150mg", "pack_name": "10s"},
        {"item_code": 3, "product_name": "Crocin Tab 500mg", "pack_name": "10s"},
    ])
    return create_search_index(df)


def test_finds_exact_brand_match_first():
    results = search_medicine("Pantop Tab", _inventory())
    assert results, "expected at least one match"
    assert "pantop" in results[0][0].lower()


def test_empty_query_returns_no_results():
    assert search_medicine("", _inventory()) == []


def test_gibberish_below_threshold_returns_nothing():
    # A string unrelated to any brand should not falsely match.
    results = search_medicine("zzzzzzq", _inventory())
    assert results == []


def test_partial_prefix_surfaces_medicine():
    # Typing a partial brand prefix should already surface the medicine
    # (e.g. "panto" -> "Pantop"), not require the full name.
    results = search_medicine("panto", _inventory())
    assert results and "pantop" in results[0][0].lower()


def test_substring_fragment_matches():
    # A fragment inside the name should match too (e.g. "cin" in "Crocin").
    results = search_medicine("cin", _inventory())
    assert any("crocin" in r[0].lower() for r in results)


def test_single_typo_still_matches():
    # A one-character misspelling of the brand should still find the medicine
    # (Jaro-Winkler brand-token matching), not return nothing.
    inv = _inventory()
    assert search_medicine("crocine", inv)[0][0].lower().startswith("crocin")   # extra letter
    assert any("pantop" in r[0].lower() for r in search_medicine("pantpo", inv))  # transposition
    assert any("aciloc" in r[0].lower() for r in search_medicine("acilok", inv))  # substitution
