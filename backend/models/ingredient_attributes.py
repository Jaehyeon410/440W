from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_CATEGORIES = {"protein", "produce", "starch", "dairy", "seasoning", "fat", "liquid", "misc"}
ALLOWED_PROPERTIES = {
    "creamy",
    "mild",
    "rich",
    "tangy",
    "savory",
    "sweet",
    "acidic",
    "spicy",
    "dry",
    "soft",
    "crunchy",
    "aromatic",
}
ALLOWED_FUNCTIONS = {
    "moisture",
    "creaminess",
    "structure",
    "protein_base",
    "sweetness",
    "acidity",
    "aroma",
    "fat_source",
    "bulk",
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


class IngredientAttributes(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ingredient: str
    category: str = "misc"
    properties: List[str] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)
    is_liquid: bool = False
    is_fat_based: bool = False
    confidence: float = 0.0
    source: str = "fallback"

    @field_validator("ingredient", "category", "source", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return str(value or "").strip().lower()

    @field_validator("properties", "functions", mode="before")
    @classmethod
    def _normalize_tags(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return _dedupe_strings([value])
        if isinstance(value, (list, tuple, set)):
            return _dedupe_strings([str(item) for item in value])
        return []

    @field_validator("properties")
    @classmethod
    def _validate_properties(cls, value: List[str]) -> List[str]:
        return [item for item in value if item in ALLOWED_PROPERTIES]

    @field_validator("functions")
    @classmethod
    def _validate_functions(cls, value: List[str]) -> List[str]:
        return [item for item in value if item in ALLOWED_FUNCTIONS]

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        return value if value in ALLOWED_CATEGORIES else "misc"

    @field_validator("is_liquid", "is_fat_based", mode="before")
    @classmethod
    def _normalize_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "y", "1"}:
                return True
            if normalized in {"false", "no", "n", "0", ""}:
                return False
        return False

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: object) -> float:
        if isinstance(value, str):
            text = value.strip().rstrip("%")
            try:
                numeric = float(text)
                if value.strip().endswith("%"):
                    numeric /= 100.0
                return max(0.0, min(1.0, numeric))
            except ValueError:
                return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, numeric))

    def role_tags(self) -> List[str]:
        return _dedupe_strings([*self.properties, *self.functions])