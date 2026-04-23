# Fridge Remix 🥘

**Fridge Remix** is an AI-powered recipe recommendation app that takes your available ingredients and suggests recipes you can actually make — complete with smart substitution suggestions and step-by-step cooking guidance.

Built with a **React + Vite** frontend and a **FastAPI** backend, powered by **Google Gemini** for LLM-driven substitution reasoning.

---

## Features

- **Inventory-first discovery** — add what's in your fridge and get matching recipes ranked by ingredient coverage
- **Smart substitutions** — AI suggests ingredient swaps for what you're missing
- **Remix mode** — apply substitutions and get fully rewritten step-by-step cooking instructions
- **Cook-now filter** — one-tap filter to show only recipes you can make right now with zero missing ingredients
- **Dietary/preference filters** — time limit, spicy/lighter preference, cuisine style, dairy-free, gluten-free

---

## Project Structure

```
Fridge Remix/
├── app-react/            # React + Vite + Tailwind frontend
│   ├── src/
│   │   ├── api/          # API client calling the backend
│   │   ├── app/
│   │   │   ├── screens/  # Page-level components (Home, Results, RecipeDetail, etc.)
│   │   │   ├── components/ # Shared UI components
│   │   │   └── lib/      # Utilities and local state helpers
│   │   └── styles/
│   └── .env.example      # Frontend environment config template
│
├── backend/              # FastAPI Python backend
│   ├── main.py           # Server entrypoint and API routes
│   ├── services/         # Core logic (recommendation, substitutions, remix, role inference)
│   ├── api/              # Pydantic request/response schemas
│   ├── utils/            # Text processing helpers
│   ├── requirements.txt
│   └── .env.example      # Backend environment config template
│
├── data/
│   ├── 5000_recipes_western.py   # Script to generate western_5000.json from raw data
│   └── western_5000.json         # Processed recipe dataset (runtime required)
│
├── .gitignore
└── README.md
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 or 3.12 | 3.14 also works |
| Node.js | 18+ | LTS recommended |
| npm | 9+ | Bundled with Node |
| Google Gemini API key | — | Required for substitution/remix features |

Get a free Gemini API key at: https://aistudio.google.com/app/apikey

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Jaehyeon410/440W.git
cd 440W
```

### 2. Backend setup

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

### 3. Configure backend environment

```bash
# From the backend/ directory
cp .env.example .env
```

Edit `backend/.env` and add your Gemini API key:

```env
$env:GEMINI_API_KEY="your_actual_key_here"
```


### 4. Run the backend

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at: http://127.0.0.1:8000  
Swagger docs: http://127.0.0.1:8000/docs

### 5. Frontend setup

```bash
cd app-react
npm install
```

### 6. Configure frontend environment

```bash
cp .env.example .env
```

The default `.env` points to `http://127.0.0.1:8000` which works for local development.

### 7. Run the frontend

```bash
npm run dev
```

Open: http://127.0.0.1:3000

---

## Environment Variables Reference

### `backend/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key |
| `GEMINI_TEXT_MODEL` | No | `gemini-2.0-flash` | Text generation model |
| `ENABLE_GEMINI_METADATA` | No | `0` | Set to `1` to generate missing ingredient metadata via Gemini |

### `app-react/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_URL` | No | `http://127.0.0.1:8000` | Backend API base URL |

---

## Recommendation Pipeline

Recommendations are intentionally simple and deterministic:

1. Normalize `user_ingredients`
2. Compare against each recipe's `ingredients_norm`
3. Compute overlap-based `match_percent`
4. Infer missing buckets (`missing_main`, `missing_seasoning`, `missing_other`)
5. Sort by match quality and return top results

This project no longer uses FAISS/vector retrieval for `/api/recommend`.

---

## What's Committed vs Generated

| File/Folder | Committed | How to Generate |
|---|---|---|
| `backend/requirements.txt` | ✅ | — |
| `backend/ingredient_metadata.json` | ✅ | — (hand-curated metadata) |
| `backend/substitute_pools.json` | ✅ | — (hand-curated pools) |
| `data/western_5000.json` | ✅ | `python data/5000_recipes_western.py` |
| `backend/ingredient_metadata.generated.json` | ❌ | auto-created when `ENABLE_GEMINI_METADATA=1` |
| `backend/unknown_log.json` | ❌ | auto-created at runtime |
| `app-react/dist/` | ❌ | `npm run build` |
| `app-react/.env` | ❌ | copy from `.env.example` |
| `backend/.env` | ❌ | copy from `.env.example` |

---

## Troubleshooting

### "No recipes found" after entering ingredients
- Make sure the backend is running and fully initialized (wait for the `Recipes loaded: 5000` log line)
- Check that `data/western_5000.json` exists
- Confirm the frontend `.env` points to the correct backend URL

### Backend startup hangs on "Waiting for application startup"
Run with `--lifespan off` to skip the startup hook. Dataset loading moves to the first request:
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --lifespan off
```

### Substitutions / Remix return an error
- Verify `GEMINI_API_KEY` is set correctly in `backend/.env`
- Check your Gemini API quota at https://aistudio.google.com

### CORS errors in the browser
The backend CORS allowlist includes `localhost:3000` and `127.0.0.1:3000`. If you run the frontend on a different port, add it to `app.add_middleware(CORSMiddleware, ...)` in `backend/main.py`.

### Recommendation setup error after pull
Reinstall backend dependencies to match the simplified pipeline:
```bash
cd backend
pip install -r requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 6, TypeScript, Tailwind CSS v4, shadcn/ui |
| Backend | Python, FastAPI, Uvicorn |
| AI / LLM | Google Gemini (`gemini-2.0-flash`) |
| State / Routing | React Router v7, localStorage/sessionStorage |

---

## License

See [app-react/ATTRIBUTIONS.md](app-react/ATTRIBUTIONS.md) for third-party component licenses (shadcn/ui, Unsplash).
