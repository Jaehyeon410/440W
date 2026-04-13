import json, random, re

IN_PATH = "full_format_recipes.json"
OUT_PATH = "western_5000.json"

WESTERN_KEYWORDS = [
    # cuisines / dishes
    "italian","french","greek","spanish","american","british",
    "pasta","risotto","pizza","lasagna","alfredo","carbonara",
    "burger","steak","roast","casserole","sandwich","salad",
    # typical western ingredients
    "parmesan","mozzarella","cheddar","butter","cream","bacon",
    "olive oil","wine","thyme","rosemary","basil"
]

def looks_western(recipe):
    title = (recipe.get("title") or "").lower()
    ings = " ".join(recipe.get("ingredients") or []).lower()
    text = title + " " + ings
    return any(k in text for k in WESTERN_KEYWORDS)

with open(IN_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# 유효 레시피 + western 후보
cand = []
seen = set()
for r in data:
    title = (r.get("title") or "").strip()
    ing = r.get("ingredients") or []
    direc = r.get("directions") or []
    if not title or not ing or not direc:
        continue
    key = title.lower()
    if key in seen:
        continue
    seen.add(key)
    if looks_western(r):
        cand.append(r)

print("western candidates:", len(cand))

k = min(5000, len(cand))
sample = random.sample(cand, k)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(sample, f, ensure_ascii=False, indent=2)

print("saved:", OUT_PATH, "count:", len(sample))