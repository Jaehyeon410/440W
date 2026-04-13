function cleanStepText(value: string): string {
  return value
    .replace(/^\s*(?:step\s*)?\d+\s*[:.)-]?\s*/i, "")
    .replace(/^\s*[-*]\s*/, "")
    .replace(/\s+/g, " ")
    .trim();
}

const STEP_TIP_RULES: Array<[RegExp, string]> = [
  [/\bgarlic\b/i, "Garlic burns quickly \u2014 keep the heat moderate and stir often."],
  [/\bonion\b/i, "Cook onions until fully translucent before adding other ingredients for a sweeter, less sharp flavor."],
  [/\bsimmer\b/i, "Keep the heat low enough for a gentle simmer \u2014 a rapid boil can make sauces separate or bitter."],
  [/\bsalt\b/i, "Taste before adding more salt, especially if your stock or broth is already salted."],
  [/\bseason\b/i, "Season gradually and taste as you go; it\u2019s easy to add more but impossible to remove."],
  [/\boven\b|\bpreheat\b/i, "Give the oven 10\u201315 minutes to fully reach temperature before putting food in."],
  [/\bbake\b|\broast\b/i, "Rotate the pan halfway through cooking for more even browning."],
  [/\bfry\b|\bsaut\u00e9\b|\bsaute\b/i, "Pat ingredients dry before frying \u2014 surface moisture steams instead of browns."],
  [/\bboil\b|\bpasta\b/i, "Salt the boiling water generously \u2014 it should taste like lightly seasoned broth."],
  [/\bchicken\b|\bbeef\b|\bpork\b|\bsteak\b/i, "Let cooked meat rest for 2\u20133 minutes off the heat so the juices redistribute before serving."],
  [/\bfish\b|\bsalmon\b|\bshrimp\b|\bseafood\b/i, "Seafood cooks fast \u2014 remove it from heat as soon as it turns opaque to avoid overcooking."],
  [/\blemon\b|\blime\b|\bvinegar\b/i, "Add acid near the end of cooking to keep the flavor bright and fresh."],
  [/\bbasil\b|\bcilantro\b|\bparsley\b/i, "Stir in fresh herbs just before serving to preserve their color and aroma."],
  [/\bcheese\b/i, "Add cheese off the heat or on very low heat so it melts smoothly without becoming grainy."],
  [/\bcream\b|\bmilk\b/i, "Warm dairy gently \u2014 high heat can cause it to scorch or separate."],
  [/\bcover\b|\blid\b/i, "Keep the lid slightly ajar when simmering to control evaporation and prevent boil-overs."],
  [/\boil\b/i, "Let the oil heat fully before adding ingredients to prevent sticking."],
  [/\bstir\b/i, "Stir occasionally to prevent sticking, especially as the mixture thickens."],
  [/\breduce\b|\breduction\b/i, "Reduce uncovered so steam escapes and the liquid can concentrate."],
  [/\begg\b/i, "Bring eggs to room temperature first for more even cooking."],
  [/\bdough\b|\bknead\b/i, "Stop kneading when the dough is smooth and springs back slowly when poked."],
  [/\bdrain\b/i, "Reserve a cup of the cooking liquid before draining \u2014 it can loosen a thick sauce later."],
];

export function getFallbackTip(stepText: string): string {
  for (const [pattern, tip] of STEP_TIP_RULES) {
    if (pattern.test(stepText)) {
      return tip;
    }
  }
  return "";
}

export function normalizeStepList(primary: unknown, fallback: unknown = []): string[] {
  const source: string[] = [];

  if (Array.isArray(primary)) {
    source.push(...primary.map((item) => String(item ?? "")));
  } else if (typeof primary === "string") {
    source.push(primary);
  }

  if (source.length === 0) {
    if (Array.isArray(fallback)) {
      source.push(...fallback.map((item) => String(item ?? "")));
    } else if (typeof fallback === "string") {
      source.push(fallback);
    }
  }

  const normalizedSource = source.map((step) => cleanStepText(step)).filter(Boolean);
  if (normalizedSource.length > 0) {
    return normalizedSource;
  }

  return ["Follow the recipe directions in order and adjust seasoning to taste."];
}
