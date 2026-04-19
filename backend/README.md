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

## Data files

| File | Committed | Purpose |
|---|---|---|
| `ingredient_metadata.json` | ✅ | Hand-curated ingredient metadata |
| `substitute_pools.json` | ✅ | Role-based substitution candidate pools |
| `ingredient_metadata.generated.json` | ❌ | Auto-generated via Gemini at runtime |
| `unknown_log.json` | ❌ | Runtime log of unrecognized ingredients |
