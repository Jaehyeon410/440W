import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from ingredient_normalizer_v2 import normalize_ingredient_list_v2
from ingredient_parser import parse_ingredient_line, parse_ingredient_list

MAIN_INGREDIENTS = {
    "chicken",
    "beef",
    "pork",
    "turkey",
    "shrimp",
    "salmon",
    "tuna",
    "fish",
    "tofu",
    "mushroom",
    "mushrooms",
    "sausage",
    "bacon",
    "ham",
    "lamb",
}

SEASONING_INGREDIENTS = {
    "salt",
    "pepper",
    "olive oil",
    "oil",
    "butter",
    "garlic",
    "onion",
    "lemon",
    "vinegar",
    "mustard",
    "ketchup",
    "mayonnaise",
    "mayo",
    "soy sauce",
    "tomato",
    "tomato sauce",
    "cream",
    "milk",
    "cheese",
    "parmesan",
    "basil",
    "oregano",
    "parsley",
    "thyme",
    "paprika",
    "chili",
    "chili flakes",
    "cayenne",
    "sugar",
    "honey",
}

KNOWN_MULTIWORD_INGREDIENTS = {
    "olive oil",
    "soy sauce",
    "tomato sauce",
    "heavy cream",
    "chili flakes",
    "red pepper",
    "black pepper",
    "green onion",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "about",
    "approximately",
    "at",
    "or",
    "for",
    "from",
    "the",
    "to",
    "taste",
    "plus",
    "room",
    "temperature",
    "fresh",
    "minced",
    "chopped",
    "diced",
    "sliced",
    "thinly",
    "thick",
    "trimmed",
    "large",
    "small",
    "medium",
    "extra",
    "virgin",
    "ground",
    "crushed",
    "boneless",
    "skinless",
    "halves",
    "pieces",
    "package",
    "packages",
        "purchased",
        "prepared",
    "can",
    "cans",
    "jar",
    "jars",
    "stick",
    "sticks",
    "cup",
    "cups",
    "tablespoon",
    "tablespoons",
    "tbsp",
    "teaspoon",
    "teaspoons",
    "tsp",
    "ounce",
    "ounces",
    "oz",
    "pound",
    "pounds",
    "lb",
    "lbs",
    "gram",
    "grams",
    "g",
    "kg",
    "pinch",
    "dash",
    "clove",
    "cloves",
    "bunch",
    "sprig",
    "sprigs",
    "slice",
    "slices",
}

FRACTIONS_PATTERN = re.compile(r"[\u00BC-\u00BE\u2150-\u215E]")
NUMBER_PATTERN = re.compile(r"\b\d+(?:[./]\d+)?\b")
NON_ALPHA_PATTERN = re.compile(r"[^a-z\s]")
PARENS_PATTERN = re.compile(r"\([^)]*\)")
WHITESPACE_PATTERN = re.compile(r"\s+")


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_recipe_id(title: str, ingredients_raw: List[str]) -> str:
    first_ingredient = ingredients_raw[0] if ingredients_raw else ""
    stable_source = f"{title.strip()}|{first_ingredient.strip()}"
    return hashlib.sha1(stable_source.encode("utf-8")).hexdigest()[:12]


def normalize_ingredient(raw_ingredient: str) -> str:
    text = (raw_ingredient or "").lower().strip()
    if not text:
        return ""

    text = PARENS_PATTERN.sub(" ", text)
    text = text.split(",")[0]
    text = text.replace("-", " ").replace("/", " ")
    text = FRACTIONS_PATTERN.sub(" ", text)
    text = NUMBER_PATTERN.sub(" ", text)
    text = NON_ALPHA_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()

    if " of " in text:
        text = text.split(" of ")[-1].strip()

    tokens = [token for token in text.split() if token not in STOPWORDS]
    if not tokens:
        return ""

    # Canonicalize common trailing part-words so pantry/base ingredients match
    # recipe variants (e.g., "basil leaves" -> "basil", "green onion tops" -> "green onion").
    while len(tokens) >= 2 and tokens[-1] in {"leaf", "leaves", "tops"}:
        tokens = tokens[:-1]

    if not tokens:
        return ""

    if len(tokens) >= 3:
        last_three = " ".join(tokens[-3:])
        if last_three in KNOWN_MULTIWORD_INGREDIENTS:
            return last_three

    if len(tokens) >= 2:
        last_two = " ".join(tokens[-2:])
        if last_two in KNOWN_MULTIWORD_INGREDIENTS:
            return last_two

    # Preserve the full normalized ingredient phrase instead of truncating to one token.
    return " ".join(tokens)


def normalize_ingredient_list(ingredients: List[str]) -> List[str]:
    normalized = [normalize_ingredient(item) for item in ingredients]
    return _unique_preserve_order([item for item in normalized if item])


def split_missing_ingredients(missing_items: List[str]) -> Tuple[List[str], List[str]]:
    missing_main: List[str] = []
    missing_seasoning: List[str] = []

    for item in missing_items:
        if item in MAIN_INGREDIENTS:
            missing_main.append(item)
        elif item in SEASONING_INGREDIENTS:
            missing_seasoning.append(item)
        else:
            missing_seasoning.append(item)

    return _unique_preserve_order(missing_main), _unique_preserve_order(missing_seasoning)


def load_recipes_from_json(file_path: Path) -> List[Dict]:
    with file_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    recipes: List[Dict] = []
    for row in raw_data:
        if not isinstance(row, dict):
            continue

        title = (row.get("title") or "").strip()
        ingredients_raw = row.get("ingredients") or []
        directions = row.get("directions") or []

        if not title or not isinstance(ingredients_raw, list):
            continue

        ingredients_raw_clean = [item for item in ingredients_raw if isinstance(item, str) and item.strip()]

        # Use pre-computed parsed_ingredients from the dataset if present.
        # Falls back to runtime parsing so the backend works even on datasets that
        # have not yet been run through preprocess_dataset.py.
        raw_parsed = row.get("parsed_ingredients")
        if isinstance(raw_parsed, list):
            parsed_ingredients = [item for item in raw_parsed if isinstance(item, str) and item.strip()]
        else:
            parsed_ingredients = parse_ingredient_list(ingredients_raw_clean)

        # ingredients_norm: used for overlap matching and missing categorization.
        # Derived from parsed_ingredients so equipment rows and trailing noise
        # never enter matching.
        ingredients_norm = normalize_ingredient_list(parsed_ingredients)

        # ingredients_raw_norm: per-raw-item normalization for display status in
        # build_recipe_response (zipped with ingredients_raw).
        # Uses parse_ingredient_line so denoised form is normalised where possible;
        # falls back to raw for non-ingredient rows (they show as "missing" in display,
        # which preserves backward-compatible API response shape).
        ingredients_raw_norm = [
            normalize_ingredient(parse_ingredient_line(item) or item)
            for item in ingredients_raw_clean
        ]

        ingredients_v2 = normalize_ingredient_list_v2(parsed_ingredients)
        directions_clean = [step for step in directions if isinstance(step, str)]
        # Keep recipe load fast: inferred_roles_v1 is currently not used by runtime APIs.
        inferred_roles_v1 = []

        if not ingredients_raw_clean:
            continue

        # Build per-norm-ingredient importance weights from pre-computed scores.
        raw_importance = row.get("ingredient_importance")
        importance_norm: Dict[str, float] = {}
        if isinstance(raw_importance, dict):
            lower_scores = {k.lower(): v for k, v in raw_importance.items()}
            for parsed, normed in zip(parsed_ingredients, ingredients_norm):
                score = lower_scores.get(parsed.lower())
                if score is not None:
                    try:
                        importance_norm[normed] = float(score)
                    except (ValueError, TypeError):
                        pass

        recipes.append(
            {
                "id": build_recipe_id(title, ingredients_raw_clean),
                "title": title,
                "ingredients_raw": ingredients_raw_clean,
                "parsed_ingredients": parsed_ingredients,
                "ingredients_raw_norm": ingredients_raw_norm,
                "ingredients_norm": ingredients_norm,
                "importance_norm": importance_norm,
                "ingredients_v2": ingredients_v2,
                "inferred_roles_v1": inferred_roles_v1,
                "directions": directions_clean,
                "categories": row.get("categories") if isinstance(row.get("categories"), list) else [],
                "desc": row.get("desc") or "",
                "rating": row.get("rating"),
            }
        )

    return recipes
