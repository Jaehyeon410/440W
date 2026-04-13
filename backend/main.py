from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import RecommendRequest, RemixRequest, RewritePreviewRequest, SubstitutionsRequest
from gemini_client import get_text_model, load_backend_env
from recipe_utils import load_recipes_from_json, normalize_ingredient_list
from services.recommendation_service import build_recipe_response, rank_recipes
from services.remix_service import build_remix_response
from services.substitutions_service import build_substitutions_response


app = FastAPI(title="Recipe Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


RECIPES: List[Dict] = []
RECIPE_BY_ID: Dict[str, Dict] = {}
_RUNTIME_INIT_LOCK = Lock()


def _load_runtime_state() -> None:
    global RECIPES, RECIPE_BY_ID

    load_backend_env()

    data_path = Path(__file__).resolve().parent.parent / "data" / "western_5000.json"
    RECIPES = load_recipes_from_json(data_path)
    RECIPE_BY_ID = {recipe["id"]: recipe for recipe in RECIPES}

    print(f"Recipes loaded: {len(RECIPES)}")
    print(f"Gemini text model: {get_text_model()}")


def ensure_runtime_initialized() -> None:
    # Supports both normal startup and manual/lifespan-off uvicorn runs.
    if RECIPES:
        return
    with _RUNTIME_INIT_LOCK:
        if RECIPES:
            return
        _load_runtime_state()


@app.on_event("startup")
def startup_load_dataset() -> None:
    ensure_runtime_initialized()


@app.post("/api/recommend")
def recommend(payload: RecommendRequest):
    ensure_runtime_initialized()
    user_ingredient_set = set(normalize_ingredient_list(payload.ingredients))
    return {"recipes": rank_recipes(RECIPES, user_ingredient_set)}


@app.get("/api/recipe/{id}")
def get_recipe(id: str, user_ingredients: Optional[str] = Query(default=None)):
    ensure_runtime_initialized()
    recipe = RECIPE_BY_ID.get(id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return build_recipe_response(recipe, user_ingredients)


@app.post("/api/substitutions")
def substitutions(payload: SubstitutionsRequest):
    ensure_runtime_initialized()
    recipe = RECIPE_BY_ID.get(payload.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return build_substitutions_response(payload, recipe)


@app.post("/api/remix")
def remix(payload: RemixRequest):
    ensure_runtime_initialized()
    recipe = RECIPE_BY_ID.get(payload.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    result = build_remix_response(payload, recipe)

    # Debug-only: attach v2 shadow pipeline preview when explicitly requested.
    # This block requires both the request flag and a server-side env gate so
    # debug payloads cannot be exposed accidentally in normal usage.
    if payload.debug_v2:
        from services.shadow_pipeline import build_shadow_rewrite_preview, is_shadow_debug_enabled  # lazy import
        if not is_shadow_debug_enabled(payload.debug_v2):
            return result
        debug_payload = build_shadow_rewrite_preview(payload, recipe)
        result.update(debug_payload)

    return result


@app.post("/api/rewrite-preview")
def rewrite_preview(payload: RewritePreviewRequest):
    """Shadow pipeline analysis endpoint (read-only).

    Performs detailed analysis of the Step 3-7 shadow pipeline without
    modifying production state. Returns structured analysis with role
    inference, candidate generation, ranking, adjustment metadata, and
    step rewrite preview.
    """
    ensure_runtime_initialized()
    recipe = RECIPE_BY_ID.get(payload.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    from services.rewrite_preview_service import build_rewrite_preview_analysis

    return build_rewrite_preview_analysis(payload, recipe)
