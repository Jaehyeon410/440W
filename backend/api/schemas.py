from typing import Dict, List, Optional

from pydantic import BaseModel


class Preferences(BaseModel):
    time_limit: int
    spicy: bool
    lighter: bool
    cuisine: str


class RecommendRequest(BaseModel):
    ingredients: List[str]
    preferences: Preferences


class Dietary(BaseModel):
    dairy_free: bool = False
    gluten_free: bool = False


class RemixRequest(BaseModel):
    recipe_id: str
    user_ingredients: List[str]
    selected_main_subs: Dict[str, str]
    selected_seasoning_subs: Dict[str, str]
    selected_other_subs: Optional[Dict[str, str]] = None
    preferences: Preferences
    dietary: Optional[Dietary] = None
    allergies: Optional[List[str]] = None
    # Shadow pipeline debug flag (Step 7 preview). Front-end clients that do not
    # send this field receive the original production response unchanged.
    debug_v2: bool = False


class SubstitutionsRequest(BaseModel):
    recipe_id: str
    user_ingredients: List[str]
    missing_main: List[str]
    missing_seasoning: List[str]
    missing_other: List[str]
    preferences: Optional[Preferences] = None
    dietary: Optional[Dietary] = None
    allergies: Optional[List[str]] = None


class RewritePreviewRequest(BaseModel):
    """Request for shadow pipeline analysis endpoint.

    Similar to remix but does not require Gemini LLM; just runs shadow analysis.
    selected_main_subs and selected_seasoning_subs are optional; if provided,
    analysis will focus on those substitutions.
    """

    recipe_id: str
    user_ingredients: List[str]
    selected_main_subs: Optional[Dict[str, str]] = None
    selected_seasoning_subs: Optional[Dict[str, str]] = None
    preferences: Optional[Preferences] = None
    dietary: Optional[Dietary] = None
    allergies: Optional[List[str]] = None
