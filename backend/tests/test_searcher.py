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
