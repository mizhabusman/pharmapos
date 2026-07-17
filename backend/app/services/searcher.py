"""
searcher.py — Fuzzy medicine search for PharmaPOS.

Matches AI-extracted medicine names (from Gemini, already normalized to
standard naming conventions) against the pharmacy inventory.

Design notes:
- Gemini extraction is prompted to output clean, standardized drug names,
  so heavy misspelling-tolerance is not the primary concern here.
- The main real-world failure mode is generic form words ("Tab", "Cap",
  "Syrup" ...) inflating the score of completely unrelated medicines,
  since those words appear in nearly every inventory entry.
- A lightweight brand-name pass (Stage 1B) is kept as a safety net for
  the rare case where OCR genuinely misreads a handwritten brand name —
  it costs almost nothing and never reduces match quality.
"""

from typing import List, Tuple
import pandas as pd
from rapidfuzz import process, fuzz

# ─────────────────────────────────────────────────────────────────────────
# Generic pharmacy form/route words. These appear in nearly every medicine
# name and carry no brand-identifying signal — including them in token
# scoring lets unrelated medicines (e.g. "Lipaglyn Tab") score artificially
# high against a query like "Empaglyde Tab" purely because both contain "Tab".
# ─────────────────────────────────────────────────────────────────────────
_FORM_STOPWORDS = frozenset({
    "tab", "cap", "capsule", "tablet", "syrup", "syr", "oint", "ointment",
    "inj", "injection", "susp", "suspension", "drops", "drop", "solution",
    "sol", "gel", "cream", "spray", "powder", "lotion", "soap", "liquid",
    "forte", "paint", "mouthwash", "wash",
})


def _safe_tokens(text: str, min_len: int = 2) -> List[str]:
    """Lowercased, whitespace-split tokens of at least min_len characters."""
    if not text:
        return []
    return [t for t in text.lower().split() if len(t) >= min_len]


def _meaningful_tokens(tokens: List[str]) -> List[str]:
    """
    Tokens with form/route stopwords removed — these carry the actual
    brand-identifying signal. Falls back to the full token list if
    every token happened to be a stopword (rare edge case, e.g. query "Tab").
    """
    meaningful = [t for t in tokens if t not in _FORM_STOPWORDS]
    return meaningful if meaningful else tokens


def _token_partial_score(query_tokens: List[str], candidate: str) -> float:
    """
    Average partial-match score of meaningful query tokens against a
    candidate medicine string. Form words are excluded so the brand name
    drives the score rather than a word that appears in every medicine.
    """
    meaningful = _meaningful_tokens(query_tokens)
    if not meaningful:
        return 0.0

    scores = [fuzz.partial_ratio(t, candidate) for t in meaningful]
    return sum(scores) / len(scores) if scores else 0.0


def search_medicine(
    query: str,
    inventory: pd.DataFrame,
    limit: int = 5,
    min_score: float = 65.0,
) -> List[Tuple[str, float, int]]:
    """
    Two-stage fuzzy medicine search against pharmacy inventory.

    Stage 1 — Broad candidate retrieval (two merged passes):
        Pass A  token_set_ratio on the full query
                (handles token-order variation and partial overlap;
                this is the primary, high-recall pass)
        Pass B  WRatio on the brand token only
                (safety net for rare OCR misreads where a long dosage
                string in the candidate would otherwise dilute Pass A's
                score below the retrieval cutoff; near-zero cost)

    Stage 2 — Deep reranking:
        - Meaningful-token fragment matching (brand name only, with form
          words like "Tab"/"Cap" excluded so they can't inflate unrelated
          medicines)
        - Full-string WRatio similarity
        - Weighted blend, taking the higher of the two as final score

    Args:
        query:      Medicine name extracted from the prescription (string).
        inventory:  DataFrame with a "search_index" column and a
                    `.attrs["search_list"]` cache (see preprocessor.py).
        limit:      Max number of results to return.
        min_score:  Minimum confidence (0-100) for a result to be included.

    Returns:
        List of (matched_text, score, row_index) tuples, sorted by score
        descending. Empty list if no confident match or invalid input.
    """
    # ── Input validation — never raise, always return a usable result ──────
    if not isinstance(query, str) or not query.strip():
        return []

    if not isinstance(inventory, pd.DataFrame) or inventory.empty:
        return []

    if "search_index" not in inventory.columns:
        return []

    query        = query.lower().strip()
    query_tokens = _safe_tokens(query)

    if not query_tokens:
        return []

    # Cached flat list is far faster than re-deriving it from the DataFrame
    # on every call; fall back gracefully if the cache wasn't built.
    search_list = inventory.attrs.get("search_list")
    if not search_list:
        search_list = inventory["search_index"].fillna("").astype(str).tolist()

    if not search_list:
        return []

    safe_limit = min(50, len(search_list))

    # ── STAGE 1A: broad retrieval — token_set_ratio on full query ──────────
    initial_matches = list(process.extract(
        query,
        search_list,
        scorer=fuzz.token_set_ratio,
        limit=safe_limit,
    ))

    # Indices retrieved so far — shared across the remaining retrieval passes.
    seen_indices = {idx for _, _, idx in initial_matches}

    # ── STAGE 1B: brand-name safety net — WRatio on brand token only ───────
    # Brand token = first meaningful (non-form-word, non-numeric) token.
    brand_tokens = [
        t for t in _meaningful_tokens(query_tokens)
        if not any(ch.isdigit() for ch in t)
    ]
    if brand_tokens:
        brand_query  = brand_tokens[0]
        for text, score, idx in process.extract(
            brand_query,
            search_list,
            scorer=fuzz.WRatio,
            limit=min(30, len(search_list)),
        ):
            if idx not in seen_indices:
                initial_matches.append((text, score, idx))
                seen_indices.add(idx)

    # ── STAGE 1C: literal substring retrieval ──────────────────────────────
    # Guarantees partial-name matches reach the reranker (e.g. "minima" ->
    # "Minimalist ..."), which the fuzzy scorers can rank too low to retrieve
    # for a short query against long candidate strings. Cheap plain-string
    # scan; capped so a very common fragment can't blow up the rerank pool.
    substring_added = 0
    for idx, cand in enumerate(search_list):
        if substring_added >= 60:
            break
        if idx not in seen_indices and query in cand:
            initial_matches.append((cand, 100, idx))
            seen_indices.add(idx)
            substring_added += 1

    if not initial_matches:
        return []

    # ── STAGE 2: deep reranking ──────────────────────────────────────────
    reranked: List[Tuple[str, float, int]] = []
    for _, _, idx in initial_matches:
        candidate = search_list[idx]
        if not candidate:
            continue

        token_score = _token_partial_score(query_tokens, candidate)
        # NOTE: token_set_ratio (not WRatio) is used here deliberately.
        # WRatio's internal length-adjustment heuristics can produce a flat,
        # non-discriminating ~85% score for genuinely unrelated medicines
        # (verified: "Pant D Tab 40mg" vs "Empaglyde M Tab 12.5mg/500mg 10s"
        # scored 85.5 on WRatio but only 42.6 on token_set_ratio — the latter
        # correctly identifies these as unrelated).
        full_score  = fuzz.token_set_ratio(query, candidate)

        # 65% weight on brand-fragment match, 35% on full-string similarity;
        # take the higher of the blended score or the raw full-string score
        # so a near-exact full match is never penalised by token weighting.
        weighted_score = (token_score * 0.65) + (full_score * 0.35)
        combined_score = max(weighted_score, full_score)

        # Literal partial-name match is a strong, human-intuitive signal the
        # blended fuzzy score under-weights for a short query against a long
        # candidate (e.g. "minima" inside "minimalist ... serum"). A word that
        # *starts* with the query is stronger still (prefix typing).
        if any(word.startswith(query) for word in candidate.split()):
            combined_score = max(combined_score, 96.0)
        elif query in candidate:
            combined_score = max(combined_score, 88.0)

        reranked.append((candidate, min(combined_score, 100.0), idx))

    reranked.sort(key=lambda m: m[1], reverse=True)

    # ── FINAL OUTPUT: Map the index back to the clean inventory strings ────
    final_results = []
    for _, score, index in reranked[:limit]:
        if score >= min_score:
            # Look up the exact row in the DataFrame using the matching index
            row = inventory.iloc[index]
            
            # Grab the clean names straight from the original data
            clean_product = str(row.get("product_name", ""))
            
            # Combine them for the frontend
            display_name = clean_product.strip()
            
            final_results.append((display_name, round(score, 1), index))

    return final_results