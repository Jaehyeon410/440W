# Backend

FastAPI backend for Fridge Remix. Handles recipe recommendation, ingredient
substitution reasoning, and recipe remix via Google Gemini.

See the root [README.md](../README.md) for full setup instructions.

## Quick start

```bash
# From the project root
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

cd backend
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/recommend` | Recommend recipes from inventory |
| GET | `/api/recipe/{id}` | Recipe detail with ingredient status |
| POST | `/api/substitutions` | AI substitution options for missing ingredients |
| POST | `/api/remix` | Apply substitutions and rewrite cooking steps |
| POST | `/api/rewrite-preview` | Shadow pipeline analysis (read-only) |

Interactive docs: http://127.0.0.1:8000/docs

## Environment variables

Copy `.env.example` to `.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_TEXT_MODEL=gemini-2.0-flash
ENABLE_GEMINI_METADATA=0
```

## Recommendation behavior

`/api/recommend` uses local keyword overlap only:

1. normalize user ingredients
2. compare with each recipe's `ingredients_norm`
3. compute `match_percent`
4. infer missing buckets and rank
5. return top results

## Scripts

| Script | Purpose |
|---|---|
| `scripts/preprocess_dataset.py` | Parse and normalize raw recipe JSON |
| `scripts/smoke_test_api.py` | Basic API smoke test |
| `scripts/run_user_inventory_demo.py` | CLI demo of the recommendation flow |
| `scripts/compare_inventory_scenarios.py` | Compare results for different inventories |
| `scripts/validate_recommendation_quality.py` | Recommendation quality checks |
