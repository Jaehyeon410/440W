"""Ingredient normalization V2.

This module keeps richer ingredient structure than the legacy flat-string normalizer.
The initial implementation is intentionally conservative and additive so existing
application behavior can stay unchanged while V2 data is populated.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple


FRACTION_CHAR_MAP = {
    "\u00bc": "1/4",
    "\u00bd": "1/2",
    "\u00be": "3/4",
    "\u2150": "1/7",
    "\u2151": "1/9",
    "\u2152": "1/10",
    "\u2153": "1/3",
    "\u2154": "2/3",
    "\u2155": "1/5",
    "\u2156": "2/5",
    "\u2157": "3/5",
    "\u2158": "4/5",
    "\u2159": "1/6",
    "\u215a": "5/6",
    "\u215b": "1/8",
    "\u215c": "3/8",
    "\u215d": "5/8",
    "\u215e": "7/8",
}

PARENS_PATTERN = re.compile(r"\([^)]*\)")
WHITESPACE_PATTERN = re.compile(r"\s+")
LEADING_QTY_UNIT_PATTERN = re.compile(
    r"^\s*"
    r"(?P<qty>(?:\d+\s+\d+/\d+)|(?:\d+/\d+)|(?:\d+(?:\.\d+)?))"
    r"(?:\s*(?:-|to)\s*(?:\d+(?:\.\d+)?|\d+/\d+))?"
    r"(?:\s+(?P<unit>[a-zA-Z][a-zA-Z\-.]*))?"
    r"\b"
)

UNIT_ALIASES = {
    "c": "cup",
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "ml": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "clove": "clove",
    "cloves": "clove",
    "can": "can",
    "cans": "can",
    "package": "package",
    "packages": "package",
}

ALIASES = {
    "scallion": "green onions",
    "scallions": "green onions",
    "confectioners sugar": "powdered sugar",
    "confectioners' sugar": "powdered sugar",
    "whipping cream": "heavy cream",
    "corn starch": "cornstarch",
}

DESCRIPTOR_WORDS = {
    "all",
    "all purpose",
    "black",
    "chopped",
    "diced",
    "extra",
    "extra virgin",
    "fresh",
    "freshly",
    "greek",
    "ground",
    "heavy",
    "plain",
    "powdered",
    "sliced",
    "toasted",
    "virgin",
}

PREPARATION_WORDS = {
    "chilled",
    "chopped",
    "diced",
    "freshly",
    "ground",
    "minced",
    "roasted",
    "sliced",
    "toasted",
}

COMPOUND_CANONICALS = {
    "all purpose flour",
    "black pepper",
    "extra virgin olive oil",
    "green onions",
    "greek yogurt",
    "heavy cream",
    "olive oil",
    "powdered sugar",
    "tomato paste",
}

BASE_OVERRIDES = {
    "all purpose flour": "flour",
    "black pepper": "pepper",
    "cube steaks": "beef",
    "cube steak": "beef",
    "extra virgin olive oil": "oil",
    "green onions": "onion",
    "greek yogurt": "yogurt",
    "greens": "greens",
    "half half": "half and half",
    "heavy cream": "cream",
    "powdered sugar": "sugar",
    "tomato paste": "tomato",
}

SUBTYPE_PRIORITY = [
    "all purpose",
    "extra virgin",
    "greek",
    "heavy",
    "powdered",
    "black",
    "green",
]

# Trailing tokens that describe shape/form/cut, not the actual ingredient.
# _extract_base skips these to reach the real food word.
FORM_TAIL_WORDS = {
    "ball", "balls",
    "chunk", "chunks",
    "chip", "chips",
    "cube", "cubes",
    "curl", "curls",
    "cutlet", "cutlets",
    "drop", "drops",
    "dusting",
    "fillet", "fillets", "filet", "filets",
    "flake", "flakes",
    "floret", "florets",
    "half", "halves",
    "head", "heads",
    "leaf", "leaves",
    "log", "logs",
    "nugget", "nuggets",
    "piece", "pieces",
    "portion", "portions",
    "quarter", "quarters",
    "ring", "rings",
    "round", "rounds",
    "segment", "segments",
    "serving", "servings",
    "shaving", "shavings",
    "sheet", "sheets",
    "slab", "slabs",
    "slice", "slices",
    "sprig", "sprigs",
    "stalk", "stalks",
    "steak", "steaks",
    "stick", "sticks",
    "strip", "strips",
    "wedge", "wedges",
    "zest", "zests",
}

# Trailing tokens that are descriptors/adjectives, not food words.
DESCRIPTOR_TAIL_WORDS = {
    "bitter", "bitters",
    "brown",
    "canned",
    "coarse",
    "cold",
    "cooked",
    "dried",
    "dry",
    "frozen",
    "green", "greens",
    "hot",
    "raw",
    "red",
    "salted",
    "soft",
    "sweet",
    "thin",
    "unsalted",
    "warm",
    "white", "whites",
    "whole",
    "yellow",
    "black",
    "inch",
}


@dataclass
class NormalizedIngredientV2:
    raw: str
    canonical: str
    base: str
    descriptors: List[str]
    quantity: Optional[float]
    unit: Optional[str]
    preparation: List[str]
    subtype: Optional[str]
    normalized_text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _to_ascii_fraction_text(text: str) -> str:
    for char, replacement in FRACTION_CHAR_MAP.items():
        text = text.replace(char, f" {replacement} ")
    return text


def _normalize_text(raw_text: str) -> str:
    text = (raw_text or "").strip().lower()
    text = _to_ascii_fraction_text(text)
    text = PARENS_PATTERN.sub(" ", text)
    text = text.replace("-", " ").replace("_", " ")
    text = text.replace(";", ",")
    text = re.sub(r"[^a-z0-9\s,/'\.]+", " ", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def _parse_quantity_text(quantity_text: str) -> Optional[float]:
    text = (quantity_text or "").strip()
    if not text:
        return None

    # Mixed fractions like "1 1/2".
    if " " in text and "/" in text:
        parts = text.split()
        if len(parts) == 2:
            whole, frac = parts
            try:
                return float(int(whole) + Fraction(frac))
            except (ValueError, ZeroDivisionError):
                return None

    if "/" in text:
        try:
            return float(Fraction(text))
        except (ValueError, ZeroDivisionError):
            return None

    try:
        return float(text)
    except ValueError:
        return None


def parse_quantity_and_unit(raw_text: str) -> Tuple[Optional[float], Optional[str], str]:
    """Parse leading quantity and unit, returning remaining ingredient phrase."""
    text = _normalize_text(raw_text)
    if not text:
        return None, None, ""

    matched = LEADING_QTY_UNIT_PATTERN.match(text)
    if not matched:
        return None, None, text

    quantity = _parse_quantity_text(matched.group("qty") or "")
    unit_raw = (matched.group("unit") or "").strip(".").lower()

    # Avoid consuming ingredient tokens as units (e.g., "3 green onions").
    if unit_raw and unit_raw not in UNIT_ALIASES:
        remainder = text[matched.start("unit") :].strip()
        if remainder.startswith("of "):
            remainder = remainder[3:].strip()
        return quantity, None, remainder

    unit = UNIT_ALIASES.get(unit_raw, unit_raw or None)
    remainder = text[matched.end() :].strip()
    if remainder.startswith("of "):
        remainder = remainder[3:].strip()

    return quantity, unit, remainder


def _normalize_phrase_for_alias(text: str) -> str:
    cleaned = re.sub(r"[^a-z\s']", " ", text.lower())
    cleaned = WHITESPACE_PATTERN.sub(" ", cleaned).strip()
    return cleaned


def resolve_alias(base_candidate: str) -> str:
    normalized = _normalize_phrase_for_alias(base_candidate)
    if not normalized:
        return ""
    return ALIASES.get(normalized, normalized)


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _to_singular(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _extract_compound_descriptors(text: str) -> List[str]:
    found: List[str] = []
    for phrase in ["all purpose", "extra virgin"]:
        if phrase in text:
            found.append(phrase)
    return found


def extract_descriptors(raw_text: str) -> Tuple[List[str], List[str], str]:
    """Extract descriptors and preparation markers from ingredient text."""
    text = _normalize_text(raw_text)
    if not text:
        return [], [], ""

    parts = [part.strip() for part in text.split(",") if part.strip()]
    core = parts[0] if parts else text
    trailing = " ".join(parts[1:])

    descriptors: List[str] = []
    preparation: List[str] = []

    descriptors.extend(_extract_compound_descriptors(core))
    if trailing:
        descriptors.extend(_extract_compound_descriptors(trailing))

    for source in [core, trailing]:
        if not source:
            continue
        for token in source.split():
            if token in DESCRIPTOR_WORDS:
                descriptors.append(token)
            if token in PREPARATION_WORDS:
                preparation.append(token)

    descriptors = _unique_preserve_order(descriptors)
    preparation = _unique_preserve_order(preparation)
    cleaned_core = WHITESPACE_PATTERN.sub(" ", core).strip()

    return descriptors, preparation, cleaned_core


def _extract_canonical_from_core(core_text: str, descriptors: List[str]) -> str:
    if not core_text:
        return ""

    core_text = core_text.replace("'", " ")
    core_text = WHITESPACE_PATTERN.sub(" ", core_text).strip()

    if core_text in COMPOUND_CANONICALS:
        return resolve_alias(core_text)

    # Keep known multi-word canonical identities when they appear with extra modifiers.
    for phrase in sorted(COMPOUND_CANONICALS, key=len, reverse=True):
        if phrase in core_text:
            return resolve_alias(phrase)

    tokens = [token for token in core_text.split() if token not in {"of"}]
    descriptor_token_set = {token for token in descriptors for token in token.split()}
    candidate_tokens = [token for token in tokens if token not in descriptor_token_set]

    if not candidate_tokens:
        candidate_tokens = tokens

    if len(candidate_tokens) >= 2:
        last_two = " ".join(candidate_tokens[-2:])
        if last_two in COMPOUND_CANONICALS:
            return resolve_alias(last_two)

    candidate = " ".join(candidate_tokens).strip()
    candidate = resolve_alias(candidate)

    if not candidate and tokens:
        candidate = resolve_alias(" ".join(tokens[-2:]) if len(tokens) >= 2 else tokens[-1])

    return candidate


def _extract_base(canonical: str) -> str:
    if not canonical:
        return ""

    if canonical in BASE_OVERRIDES:
        return BASE_OVERRIDES[canonical]

    tokens = canonical.split()
    if not tokens:
        return ""

    # Walk backwards past trailing form/shape/descriptor words to find the
    # actual food token.  E.g. "salmon fillets" -> "salmon",
    # "parmesan cheese shavings" -> "cheese", "collard greens" -> "collard".
    skip_words = FORM_TAIL_WORDS | DESCRIPTOR_TAIL_WORDS
    idx = len(tokens) - 1
    while idx > 0 and (tokens[idx] in skip_words or _to_singular(tokens[idx]) in skip_words):
        idx -= 1

    return _to_singular(tokens[idx])


def _extract_subtype(canonical: str, descriptors: List[str]) -> Optional[str]:
    searchable = " ".join([canonical, *descriptors]).strip()
    if not searchable:
        return None

    for subtype in SUBTYPE_PRIORITY:
        if subtype in searchable:
            return subtype
    return None


def normalize_ingredient_v2(raw_text: str) -> NormalizedIngredientV2:
    """Normalize an ingredient string into a structured V2 representation."""
    raw_value = str(raw_text or "")
    quantity, unit, without_qty = parse_quantity_and_unit(raw_value)
    descriptors, preparation, core_text = extract_descriptors(without_qty)

    canonical = _extract_canonical_from_core(core_text, descriptors)
    base = _extract_base(canonical)
    subtype = _extract_subtype(canonical, descriptors)
    normalized_text = canonical or core_text or _normalize_text(raw_value)

    return NormalizedIngredientV2(
        raw=raw_value,
        canonical=canonical,
        base=base,
        descriptors=descriptors,
        quantity=quantity,
        unit=unit,
        preparation=preparation,
        subtype=subtype,
        normalized_text=normalized_text,
    )


def normalize_ingredient_list_v2(items: List[str]) -> List[Dict[str, Any]]:
    """Normalize a list of ingredient strings into serializable V2 payloads."""
    result: List[Dict[str, Any]] = []
    for item in items:
        normalized = normalize_ingredient_v2(item)
        if normalized.normalized_text:
            result.append(normalized.to_dict())
    return result
