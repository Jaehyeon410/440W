import re
from typing import Any, List, Tuple


STEP_TIP_RULES: List[Tuple[str, str]] = [
    (r"\bgarlic\b", "Garlic burns quickly - keep the heat moderate and stir often."),
    (r"\bonion\b", "Cook onions until fully translucent before adding other ingredients for a sweeter, less sharp flavor."),
    (r"\bsimmer\b", "Keep the heat low enough for a gentle simmer - a rapid boil can make sauces separate or become bitter."),
    (r"\bsalt\b", "Taste before adding more salt, especially if your stock or broth is already salted."),
    (r"\bseason\b", "Season gradually and taste as you go; it's easy to add more but impossible to remove."),
    (r"\boven\b|\bpreheat\b", "Give the oven 10-15 minutes to fully reach temperature before putting food in."),
    (r"\bbake\b|\broast\b", "Rotate the pan halfway through cooking for more even browning."),
    (r"\bfry\b|\bsaut(?:e|\u00e9)\b", "Pat ingredients dry before frying - surface moisture steams instead of browns."),
    (r"\bboil\b|\bpasta\b", "Salt the boiling water generously - it should taste like lightly seasoned broth."),
    (r"\bchicken\b|\bbeef\b|\bpork\b|\bsteak\b", "Let cooked meat rest for 2-3 minutes off the heat so the juices redistribute before serving."),
    (r"\bfish\b|\bsalmon\b|\bshrimp\b|\bseafood\b", "Seafood cooks fast - remove it from the heat as soon as it turns opaque to avoid overcooking."),
    (r"\blemon\b|\blime\b|\bvinegar\b", "Add acid near the end of cooking to keep the flavor bright and fresh."),
    (r"\bbasil\b|\bcilantro\b|\bparsley\b", "Stir in fresh herbs just before serving to preserve their color and aroma."),
    (r"\bcheese\b", "Add cheese off the heat or on very low heat so it melts smoothly without becoming grainy."),
    (r"\bcream\b|\bmilk\b", "Warm dairy gently - high heat can cause it to scorch or separate."),
    (r"\bcover\b|\blid\b", "Keep the lid slightly ajar when simmering to control evaporation and prevent boil-overs."),
    (r"\boil\b", "Let the oil heat fully before adding ingredients to prevent sticking."),
    (r"\bstir\b", "Stir occasionally to prevent sticking, especially as the mixture thickens."),
    (r"\breduce\b|\breduction\b", "Reduce uncovered so steam escapes and the liquid can concentrate."),
    (r"\begg\b", "Bring eggs to room temperature first for more even cooking."),
    (r"\bknead\b|\bdough\b", "Stop kneading when the dough is smooth and springs back slowly when poked."),
    (r"\bdrains?\b", "Reserve a cup of the cooking liquid before draining - it can help loosen a thick sauce."),
]


def generate_fallback_tip(step_text: str) -> str:
    lowered = (step_text or "").lower()
    for pattern, tip in STEP_TIP_RULES:
        if re.search(pattern, lowered):
            return tip
    return ""


def clean_step_text(text: str) -> str:
    cleaned = re.sub(r"^\s*(?:step\s*)?\d+\s*[:.)-]?\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*[-*]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_original_steps(raw_steps: Any) -> List[str]:
    if isinstance(raw_steps, list):
        normalized = [clean_step_text(str(step)) for step in raw_steps]
    elif isinstance(raw_steps, str):
        normalized = [clean_step_text(raw_steps)]
    else:
        normalized = []

    out = [step for step in normalized if step]
    if out:
        return out
    return ["Follow the original recipe directions in order and adjust seasoning to taste."]


def normalize_edited_steps(raw_steps: Any, original_steps: List[str]) -> List[str]:
    if not isinstance(raw_steps, list):
        return list(original_steps)

    edited_steps = [clean_step_text(str(step)) for step in raw_steps]
    if len(edited_steps) != len(original_steps):
        return list(original_steps)
    if any(not step for step in edited_steps):
        return list(original_steps)
    return edited_steps
