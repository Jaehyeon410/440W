import json
from typing import Any, Dict, List, Optional, Tuple

from gemini_client import generate_json_with_retry
from models.ingredient_attributes import ALLOWED_CATEGORIES, ALLOWED_FUNCTIONS, ALLOWED_PROPERTIES, IngredientAttributes
from recipe_utils import normalize_ingredient


COMMON_PRODUCE_ITEMS = {
    "bell pepper",
    "broccoli",
    "carrot",
    "celery",
    "cucumber",
    "lettuce",
    "mushroom",
    "mushrooms",
    "onion",
    "spinach",
    "tomato",
    "zucchini",
}
COMMON_STARCH_ITEMS = {"pasta", "potato", "rice"}
COMMON_DAIRY_ITEMS = {"cheese", "cream", "milk", "yogurt"}
COMMON_FAT_ITEMS = {"butter", "mayo", "mayonnaise", "oil", "olive oil"}
COMMON_LIQUID_ITEMS = {"broth", "stock", "water", "wine"}
COMMON_SEASONING_ITEMS = {"garlic", "lemon", "mustard", "pepper", "salt", "soy sauce", "vinegar"}
COMMON_PROTEIN_ITEMS = {"beef", "chicken", "fish", "pork", "shrimp", "tofu", "turkey"}

EXAMPLE_ATTRIBUTES: Dict[str, Dict[str, Any]] = {
    "milk": {
        "category": "dairy",
        "properties": ["mild"],
        "functions": ["moisture", "creaminess"],
        "is_liquid": True,
        "is_fat_based": False,
    },
    "cream": {
        "category": "dairy",
        "properties": ["creamy", "rich"],
        "functions": ["creaminess", "fat_source", "moisture"],
        "is_liquid": True,
        "is_fat_based": True,
    },
    "yogurt": {
        "category": "dairy",
        "properties": ["creamy", "tangy"],
        "functions": ["creaminess", "acidity", "moisture"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "butter": {
        "category": "fat",
        "properties": ["rich", "savory"],
        "functions": ["fat_source"],
        "is_liquid": False,
        "is_fat_based": True,
    },
    "broth": {
        "category": "liquid",
        "properties": ["savory"],
        "functions": ["moisture", "bulk"],
        "is_liquid": True,
        "is_fat_based": False,
    },
    "chicken": {
        "category": "protein",
        "properties": ["savory", "mild", "soft"],
        "functions": ["protein_base", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "tofu": {
        "category": "protein",
        "properties": ["mild", "soft"],
        "functions": ["protein_base", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "spinach": {
        "category": "produce",
        "properties": ["mild", "soft"],
        "functions": ["moisture", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "zucchini": {
        "category": "produce",
        "properties": ["mild", "soft"],
        "functions": ["moisture", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "onion": {
        "category": "produce",
        "properties": ["aromatic", "savory"],
        "functions": ["aroma", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "garlic": {
        "category": "seasoning",
        "properties": ["aromatic", "savory"],
        "functions": ["aroma"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "rice": {
        "category": "starch",
        "properties": ["mild", "soft"],
        "functions": ["structure", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "pasta": {
        "category": "starch",
        "properties": ["mild", "soft"],
        "functions": ["structure", "bulk"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "mushroom": {
        "category": "produce",
        "properties": ["savory", "soft"],
        "functions": ["bulk", "moisture"],
        "is_liquid": False,
        "is_fat_based": False,
    },
    "tomato": {
        "category": "produce",
        "properties": ["acidic", "soft"],
        "functions": ["moisture", "acidity"],
        "is_liquid": False,
        "is_fat_based": False,
    },
}

PROPERTY_HINTS = {
    "acidic": {"lemon", "lime", "tomato", "vinegar", "yogurt"},
    "aromatic": {"garlic", "onion", "pepper", "shallot", "spice"},
    "creamy": {"cream", "milk", "yogurt"},
    "mild": {"milk", "pasta", "rice", "spinach", "tofu", "zucchini"},
    "rich": {"butter", "cream", "mayo", "oil"},
    "savory": {"broth", "butter", "chicken", "garlic", "mushroom", "onion"},
    "soft": {"mushroom", "pasta", "spinach", "tomato", "tofu", "zucchini"},
    "sweet": {"carrot", "milk", "onion"},
    "tangy": {"vinegar", "yogurt"},
}

FUNCTION_HINTS = {
    "acidity": {"lemon", "lime", "tomato", "vinegar", "yogurt"},
    "aroma": {"garlic", "onion", "pepper", "shallot", "soy sauce"},
    "bulk": {"broccoli", "carrot", "celery", "chicken", "mushroom", "onion", "pasta", "rice", "spinach", "tofu", "tomato", "zucchini"},
    "creaminess": {"cream", "milk", "yogurt"},
    "fat_source": {"butter", "cream", "mayo", "oil", "olive oil"},
    "moisture": {"broth", "cucumber", "milk", "spinach", "stock", "tomato", "water", "wine", "yogurt", "zucchini"},
    "protein_base": {"beef", "chicken", "fish", "pork", "shrimp", "tofu", "turkey"},
    "structure": {"pasta", "potato", "rice"},
    "sweetness": {"carrot", "milk", "onion", "sugar"},
}


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        normalized = str(value).strip().lower().replace("-", " ")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _category_from_tokens(ingredient: str) -> str:
    tokens = set(ingredient.split())
    if ingredient in EXAMPLE_ATTRIBUTES:
        return str(EXAMPLE_ATTRIBUTES[ingredient]["category"])
    if ingredient in COMMON_FAT_ITEMS:
        return "fat"
    if ingredient in COMMON_LIQUID_ITEMS:
        return "liquid"
    if ingredient in COMMON_DAIRY_ITEMS:
        return "dairy"
    if ingredient in COMMON_PROTEIN_ITEMS or tokens.intersection({"beef", "chicken", "fish", "meat", "pork", "protein", "shrimp", "tofu", "turkey"}):
        return "protein"
    if ingredient in COMMON_PRODUCE_ITEMS or tokens.intersection({"broccoli", "carrot", "celery", "cucumber", "greens", "lettuce", "mushroom", "spinach", "tomato", "vegetable", "zucchini"}):
        return "produce"
    if ingredient in COMMON_STARCH_ITEMS or tokens.intersection({"grain", "noodle", "pasta", "potato", "rice", "starch"}):
        return "starch"
    if tokens.intersection({"broth", "stock", "water", "wine"}):
        return "liquid"
    if tokens.intersection({"butter", "mayo", "mayonnaise", "oil"}):
        return "fat"
    if tokens.intersection({"cream", "creme", "dairy", "milk", "yogurt", "cheese"}):
        return "dairy"
    if ingredient in COMMON_SEASONING_ITEMS or tokens.intersection({"garlic", "herb", "mustard", "pepper", "salt", "sauce", "soy", "spice", "vinegar"}):
        return "seasoning"
    return "misc"


def _tag_list_from_hints(ingredient: str, hint_map: Dict[str, set[str]]) -> List[str]:
    tokens = set(ingredient.split())
    result: List[str] = []
    for tag, hints in hint_map.items():
        if ingredient in hints or tokens.intersection(hints):
            result.append(tag)
    return result


def _fallback_profile(ingredient: str) -> Tuple[List[str], List[str], bool, bool]:
    if ingredient in EXAMPLE_ATTRIBUTES:
        example = EXAMPLE_ATTRIBUTES[ingredient]
        return (
            list(example["properties"]),
            list(example["functions"]),
            bool(example["is_liquid"]),
            bool(example["is_fat_based"]),
        )

    properties = _tag_list_from_hints(ingredient, PROPERTY_HINTS)
    functions = _tag_list_from_hints(ingredient, FUNCTION_HINTS)
    category = _category_from_tokens(ingredient)

    if not functions:
        default_functions = {
            "protein": ["protein_base", "bulk"],
            "produce": ["moisture", "bulk"],
            "starch": ["structure", "bulk"],
            "dairy": ["creaminess", "moisture"],
            "seasoning": ["aroma"],
            "fat": ["fat_source"],
            "liquid": ["moisture"],
            "misc": [],
        }
        functions = default_functions.get(category, [])

    if not properties:
        default_properties = {
            "protein": ["savory", "mild"],
            "produce": ["mild", "soft"],
            "starch": ["mild", "soft"],
            "dairy": ["creamy"],
            "seasoning": ["aromatic"],
            "fat": ["rich"],
            "liquid": ["savory"],
            "misc": [],
        }
        properties = default_properties.get(category, [])

    is_liquid = category == "liquid" or ingredient in {"milk", "cream", "olive oil", "oil", "vinegar", "soy sauce"}
    is_fat_based = category == "fat" or ingredient in {"cream", "olive oil", "oil"}
    return properties, functions, is_liquid, is_fat_based


def fallback_ingredient_attributes(ingredient_name: str) -> IngredientAttributes:
    normalized = normalize_ingredient(ingredient_name or "")
    if not normalized:
        return IngredientAttributes(ingredient="", category="misc", source="fallback", confidence=0.0)

    category = _category_from_tokens(normalized)
    properties, functions, is_liquid, is_fat_based = _fallback_profile(normalized)

    return IngredientAttributes(
        ingredient=normalized,
        category=category,
        properties=_dedupe_strings(properties),
        functions=_dedupe_strings(functions),
        is_liquid=is_liquid,
        is_fat_based=is_fat_based,
        confidence=0.25,
        source="fallback",
    )


def _sanitize_category(value: Any, fallback: str) -> str:
    category = str(value or "").strip().lower()
    return category if category in ALLOWED_CATEGORIES else fallback


def _sanitize_tags(value: Any, fallback: List[str], allowed_tags: set[str]) -> List[str]:
    if isinstance(value, str):
        sanitized = [item for item in _dedupe_strings([value])[:8] if item in allowed_tags]
        return sanitized or [item for item in fallback if item in allowed_tags]
    if isinstance(value, (list, tuple, set)):
        sanitized = [item for item in _dedupe_strings([str(item) for item in value])[:8] if item in allowed_tags]
        return sanitized or [item for item in fallback if item in allowed_tags]
    return [item for item in fallback if item in allowed_tags]


def _sanitize_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "y"}:
            return True
        if normalized in {"false", "no", "0", "n"}:
            return False
    return fallback


def _sanitize_confidence(value: Any, fallback: float) -> float:
    try:
        if isinstance(value, str) and value.strip().endswith("%"):
            return max(0.0, min(1.0, float(value.strip().rstrip("%")) / 100.0))
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def _sanitize_source(value: Any, fallback: str) -> str:
    source = str(value or "").strip().lower()
    if source in {"llm", "fallback", "generated_cache", "manual"}:
        return source
    return fallback


def _sanitize_payload(raw_payload: Dict[str, Any], ingredient_name: str) -> IngredientAttributes:
    fallback = fallback_ingredient_attributes(ingredient_name)
    category = _sanitize_category(raw_payload.get("category"), fallback.category)
    properties = _sanitize_tags(raw_payload.get("properties"), fallback.properties, ALLOWED_PROPERTIES)
    functions = _sanitize_tags(raw_payload.get("functions"), fallback.functions, ALLOWED_FUNCTIONS)

    inferred_liquid = fallback.is_liquid or category == "liquid" or "moisture" in functions
    inferred_fat = fallback.is_fat_based or category == "fat" or "fat_source" in functions

    return IngredientAttributes(
        ingredient=normalize_ingredient(raw_payload.get("ingredient") or ingredient_name or "") or fallback.ingredient,
        category=category,
        properties=properties,
        functions=functions,
        is_liquid=_sanitize_bool(raw_payload.get("is_liquid"), inferred_liquid),
        is_fat_based=_sanitize_bool(raw_payload.get("is_fat_based"), inferred_fat),
        confidence=_sanitize_confidence(raw_payload.get("confidence"), 0.7),
        source=_sanitize_source(raw_payload.get("source"), "llm"),
    )


def _few_shot_examples() -> List[Dict[str, Any]]:
    examples: List[Dict[str, Any]] = []
    for ingredient, attributes in EXAMPLE_ATTRIBUTES.items():
        examples.append(
            {
                "input": {"original_ingredient_text": ingredient, "normalized_ingredient": ingredient},
                "output": {
                    "ingredient": ingredient,
                    "category": attributes["category"],
                    "properties": attributes["properties"],
                    "functions": attributes["functions"],
                    "is_liquid": attributes["is_liquid"],
                    "is_fat_based": attributes["is_fat_based"],
                    "confidence": 0.95,
                    "source": "llm",
                },
            }
        )
    return examples


def build_classifier_prompt_payload(
    ingredient_name: str,
    original_ingredient_text: Optional[str] = None,
    recipe_title: Optional[str] = None,
    nearby_ingredients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    normalized = normalize_ingredient(ingredient_name or "")
    return {
        "task": "Classify exactly one ingredient. Do not choose substitute ingredients.",
        "classification_target": {
            "original_ingredient_text": (original_ingredient_text or ingredient_name or "").strip(),
            "normalized_ingredient": normalized,
            "recipe_title": (recipe_title or "").strip() or None,
            "nearby_ingredients": [normalize_ingredient(item) for item in (nearby_ingredients or []) if normalize_ingredient(item)][:8],
        },
        "rules": {
            "return_json_only": True,
            "single_ingredient_only": True,
            "never_use_free_form_text": True,
            "never_choose_substitutes": True,
            "use_misc_if_uncertain": True,
            "allowed_categories": ["protein", "produce", "starch", "dairy", "seasoning", "fat", "liquid", "misc"],
            "allowed_properties": ["creamy", "mild", "rich", "tangy", "savory", "sweet", "acidic", "spicy", "dry", "soft", "crunchy", "aromatic"],
            "allowed_functions": ["moisture", "creaminess", "structure", "protein_base", "sweetness", "acidity", "aroma", "fat_source", "bulk"],
            "confidence_range": [0, 1],
        },
        "required_output_schema": {
            "ingredient": normalized,
            "category": "protein|produce|starch|dairy|seasoning|fat|liquid|misc",
            "properties": ["creamy|mild|rich|tangy|savory|sweet|acidic|spicy|dry|soft|crunchy|aromatic"],
            "functions": ["moisture|creaminess|structure|protein_base|sweetness|acidity|aroma|fat_source|bulk"],
            "is_liquid": False,
            "is_fat_based": False,
            "confidence": 0.0,
            "source": "llm",
        },
        "few_shot_examples": _few_shot_examples(),
    }


def build_classifier_prompts(
    ingredient_name: str,
    original_ingredient_text: Optional[str] = None,
    recipe_title: Optional[str] = None,
    nearby_ingredients: Optional[List[str]] = None,
) -> Tuple[str, str]:
    prompt_payload = build_classifier_prompt_payload(
        ingredient_name,
        original_ingredient_text=original_ingredient_text,
        recipe_title=recipe_title,
        nearby_ingredients=nearby_ingredients,
    )
    base_prompt = (
        "You are a strict ingredient attribute classifier for a recipe backend. "
        "Classify exactly one ingredient at a time. Return JSON only. "
        "Never explain your answer. Never suggest substitutes, alternatives, or recipe edits. "
        "Use category only from the allowed enum. Use properties/functions only from the allowed enums. "
        "Set is_liquid and is_fat_based as booleans. Set confidence as a number from 0 to 1. "
        "If uncertain, use category misc and conservative tags.\n\n"
        f"INPUT_JSON:\n{json.dumps(prompt_payload, ensure_ascii=True)}"
    )
    strict_prompt = (
        "Return exactly one valid JSON object and nothing else. "
        "Do not wrap in markdown. Do not output prose. Do not choose substitutes. "
        "Output keys must be exactly: ingredient, category, properties, functions, is_liquid, is_fat_based, confidence, source. "
        "category must be one of [protein, produce, starch, dairy, seasoning, fat, liquid, misc]. "
        "properties must only use [creamy, mild, rich, tangy, savory, sweet, acidic, spicy, dry, soft, crunchy, aromatic]. "
        "functions must only use [moisture, creaminess, structure, protein_base, sweetness, acidity, aroma, fat_source, bulk]. "
        "If uncertain, use misc with low confidence.\n\n"
        f"INPUT_JSON:\n{json.dumps(prompt_payload, ensure_ascii=True)}"
    )
    return base_prompt, strict_prompt


def classify_ingredient_attributes(
    ingredient_name: str,
    original_ingredient_text: Optional[str] = None,
    recipe_title: Optional[str] = None,
    nearby_ingredients: Optional[List[str]] = None,
) -> IngredientAttributes:
    normalized = normalize_ingredient(ingredient_name or "")
    fallback = fallback_ingredient_attributes(normalized)
    if not normalized:
        return fallback

    base_prompt, strict_prompt = build_classifier_prompts(
        normalized,
        original_ingredient_text=original_ingredient_text,
        recipe_title=recipe_title,
        nearby_ingredients=nearby_ingredients,
    )

    raw_payload = generate_json_with_retry(base_prompt, strict_prompt)
    if not isinstance(raw_payload, dict):
        return fallback

    try:
        sanitized = _sanitize_payload(raw_payload, normalized)
    except Exception:
        return fallback

    if sanitized.ingredient != normalized:
        sanitized = sanitized.model_copy(update={"ingredient": normalized})
    return sanitized