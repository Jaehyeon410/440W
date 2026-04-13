"""Ingredient line parser for the preprocessing pipeline.

Filters and cleans raw ingredient strings from recipe data before they reach
the backend matching/recommendation/substitution logic:
  - removes non-ingredient metadata rows (Special equipment, Accompaniment, Note, etc.)
  - strips trailing noise phrases (for garnish, plus additional for dusting, optional, to taste...)

This module runs at data-load time inside load_recipes_from_json so the rest of
the backend always operates on clean ingredient text.
"""

from __future__ import annotations

import re
from typing import List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Non-ingredient line detection
# ──────────────────────────────────────────────────────────────────────────────

# Keywords that, when followed by a colon, mark a metadata row instead of an
# ingredient.  All values are lowercase.
_NON_INGREDIENT_PREFIXES: frozenset[str] = frozenset(
    {
        "special equipment",
        "equipment",
        "accompaniment",
        "accompaniments",
        "for serving",
        "to serve",
        "serve with",
        "garnish",
        "garnishes",
        "note",
        "notes",
        "special note",
        "serving suggestion",
        "serving suggestions",
        "make ahead",
        "do ahead",
    }
)

# Matches "<keyword>:" at the very start of a line (case-insensitive).
# Group 1 captures the keyword so it can be looked up in _NON_INGREDIENT_PREFIXES.
_METADATA_PREFIX_PATTERN = re.compile(
    r"^\s*([a-z][a-z\s]{0,30}):\s*",
    re.IGNORECASE,
)


def is_non_ingredient_line(raw: str) -> bool:
    """Return True if the line is a metadata / equipment / note row, not an ingredient."""
    stripped = (raw or "").strip()
    if not stripped:
        return True

    match = _METADATA_PREFIX_PATTERN.match(stripped)
    if match:
        prefix = match.group(1).strip().lower()
        if prefix in _NON_INGREDIENT_PREFIXES:
            return True

    return False


# ──────────────────────────────────────────────────────────────────────────────
# Trailing noise stripping
# ──────────────────────────────────────────────────────────────────────────────

# Ordered list of tail-phrase patterns.  Applied left-to-right; each strips its
# match from the end of the string.  Quantity phrases ("plus 1 tablespoon") are
# intentionally NOT matched so they survive for the V2 quantity parser.
_TRAILING_NOISE_PATTERNS: List[re.Pattern[str]] = [
    # "plus additional for X" / "plus more for X" / "plus additional" alone
    re.compile(r"\s+plus\s+(additional|more)\b.*$", re.IGNORECASE),
    # "(for serving)" / "(for garnish)" / "(for garnish, optional)" — parens at end
    # Allow commas inside parens to catch patterns like "(for garnish, optional)".
    re.compile(r"\s*\(\s*for\s+[\w\s,]+\)\s*$", re.IGNORECASE),
    # "(optional)" at end
    re.compile(r"\s*\(\s*optional\s*\)\s*$", re.IGNORECASE),
    # "(or more to taste)" / "(or to taste)" at end
    re.compile(r"\s*\(\s*or\s+(?:more\s+)?to\s+taste\s*\)\s*$", re.IGNORECASE),
    # ", for garnish/decoration/dusting/serving/drizzling/pressing/rolling" at end
    re.compile(
        r",\s*for\s+(garnish|decoration|dusting|serving|drizzling|pressing|rolling|coating)\s*$",
        re.IGNORECASE,
    ),
    # " for garnish/decoration/dusting/serving" without leading comma
    re.compile(
        r"\s+for\s+(garnish|decoration|dusting|serving|drizzling)\s*$",
        re.IGNORECASE,
    ),
    # ", optional" at end
    re.compile(r",\s*optional\s*$", re.IGNORECASE),
    # ", to taste" / "to taste" at end (with or without leading comma)
    re.compile(r",?\s*to\s+taste\s*$", re.IGNORECASE),
    # "or more to taste" / "or to taste" at end
    re.compile(r",?\s*or\s+(?:more\s+)?to\s+taste\s*$", re.IGNORECASE),
    # ", or as needed" / "or as needed" / "as needed" at end
    re.compile(r",?\s*(or\s+)?as\s+needed\s*$", re.IGNORECASE),
    # ", seeded if desired" / ", minced if desired" etc. — must run before plain "if desired"
    re.compile(r",\s*\w+\s+if\s+desired\s*$", re.IGNORECASE),
    # ", if desired" / "if desired" at end
    re.compile(r",?\s*if\s+desired\s*$", re.IGNORECASE),
]


def strip_trailing_noise(text: str) -> str:
    """Remove trailing serving / optional / noise phrases from an ingredient line.

    Preserves quantity expressions such as "1/3 cup plus 1 tablespoon" so the
    V2 quantity parser can handle them intact.
    """
    result = text
    for pattern in _TRAILING_NOISE_PATTERNS:
        result = pattern.sub("", result)
    # Strip any trailing comma/whitespace left after noise removal (e.g. "salt,").
    return result.rstrip(",").strip()


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def parse_ingredient_line(raw: str) -> Optional[str]:
    """Return the cleaned ingredient text, or None if the line is not an ingredient.

    Quantity and unit are kept intact so downstream normalizers (normalize_ingredient,
    normalize_ingredient_v2) can process them.  Only metadata rows and trailing
    noise phrases are removed.
    """
    if is_non_ingredient_line(raw):
        return None
    cleaned = strip_trailing_noise(raw)
    return cleaned if cleaned.strip() else None


def parse_ingredient_list(raws: List[str]) -> List[str]:
    """Return cleaned ingredient lines, excluding non-ingredient metadata rows.

    Preserves order.  Deduplication is handled later by normalize_ingredient_list.
    """
    result: List[str] = []
    for raw in raws:
        parsed = parse_ingredient_line(raw)
        if parsed is not None:
            result.append(parsed)
    return result
