/**
 * Maps an ingredient name to a user-friendly display group for the pantry UI.
 *
 * This is a pure UI helper — it does NOT affect backend substitution logic,
 * scoring, ranking, or recommendation behaviour.
 */

// ---- ordered list of display groups (also controls render order) ----
export const DISPLAY_GROUP_ORDER = [
  "Produce",
  "Proteins",
  "Dairy & Fats",
  "Baking & Grains",
  "Sweeteners",
  "Seasonings & Spices",
  "Liquids & Condiments",
  "Nuts & Toppings",
  "Other",
] as const;

export type DisplayGroup = (typeof DISPLAY_GROUP_ORDER)[number];

// ---- keyword → group rules (checked in order, first match wins) ----
// Each entry is [group, patterns[]] where patterns are tested against the
// lowercased ingredient name.  Keep patterns broad enough to catch common
// phrasing but specific enough to avoid false positives.

const KEYWORD_RULES: Array<[DisplayGroup, RegExp[]]> = [
  // Proteins — check before produce so "chicken" doesn't accidentally hit
  // a produce rule.
  [
    "Proteins",
    [
      /\b(?:chicken|beef|pork|lamb|turkey|duck|veal|bison|venison|rabbit)\b/,
      /\b(?:bacon|ham|sausage|prosciutto|pancetta|chorizo|salami|pepperoni)\b/,
      /\b(?:fish|salmon|tuna|cod|tilapia|trout|anchov|sardine|mackerel|halibut|swordfish|catfish|bass|mahi)\b/,
      /\b(?:shrimp|prawn|crab|lobster|clam|mussel|oyster|scallop|squid|calamari|octopus)\b/,
      /\b(?:tofu|tempeh|seitan)\b/,
      /\b(?:egg|eggs)\b/,
    ],
  ],

  // Dairy & Fats
  [
    "Dairy & Fats",
    [
      /\b(?:milk|cream|half[\s-]and[\s-]half|buttermilk|evaporated milk|condensed milk|whipping cream)\b/,
      /\b(?:butter|margarine|ghee|lard|shortening|suet)\b/,
      /\b(?:cheese|parmesan|cheddar|mozzarella|ricotta|feta|gouda|brie|gruyere|goat cheese|cream cheese|mascarpone|provolone|swiss|blue cheese|cottage cheese)\b/,
      /\b(?:yogurt|yoghurt|sour cream|crème fraîche|creme fraiche|kefir)\b/,
      /\b(?:olive oil|vegetable oil|canola oil|coconut oil|avocado oil|sesame oil|peanut oil|sunflower oil|corn oil|grapeseed oil|walnut oil|truffle oil)\b/,
      /\boil\b/,
      /\b(?:mayo|mayonnaise)\b/,
    ],
  ],

  // Sweeteners — check before baking so "sugar" doesn't end up in grains
  [
    "Sweeteners",
    [
      /\b(?:sugar|honey|maple syrup|agave|molasses|corn syrup|stevia|splenda)\b/,
      /\b(?:brown sugar|powdered sugar|confectioner|granulated sugar|cane sugar|turbinado|demerara|muscovado)\b/,
      /\b(?:jam|jelly|marmalade|preserves)\b/,
    ],
  ],

  // Nuts & Toppings — before produce so "coconut" goes here
  [
    "Nuts & Toppings",
    [
      /\b(?:pecan|walnut|almond|cashew|pistachio|macadamia|hazelnut|peanut|pine nut|chestnut|brazil nut)\b/,
      /\b(?:pecans|walnuts|almonds|cashews|pistachios|macadamias|hazelnuts|peanuts|pine nuts|chestnuts)\b/,
      /\b(?:sunflower seed|pumpkin seed|sesame seed|flax|chia|hemp seed|poppy seed)\b/,
      /\b(?:coconut|shredded coconut|coconut flake)\b/,
      /\b(?:chocolate chip|sprinkle|raisin|raisins|dried cranberr|crouton)\b/,
    ],
  ],

  // Baking & Grains
  [
    "Baking & Grains",
    [
      /\b(?:flour|cornstarch|tapioca|arrowroot|baking powder|baking soda|yeast|gelatin|pectin)\b/,
      /\b(?:bread|tortilla|pita|naan|cracker|breadcrumb|panko|biscuit|croissant|bagel|muffin|roll)\b/,
      /\b(?:pasta|spaghetti|penne|fettuccine|linguine|macaroni|rigatoni|farfalle|orzo|lasagna|noodle|ramen|udon|vermicelli|couscous)\b/,
      /\b(?:rice|quinoa|barley|oat|oats|bulgur|polenta|cornmeal|grits|farro|millet|semolina|cereal|granola)\b/,
      /\b(?:corn tortilla|flour tortilla|wrap|phyllo|puff pastry|pie crust|dumpling wrapper)\b/,
      /\b(?:cocoa|chocolate|vanilla extract|vanilla|almond extract)\b/,
    ],
  ],

  // Seasonings & Spices
  [
    "Seasonings & Spices",
    [
      /\b(?:salt|pepper|black pepper|white pepper|red pepper|cayenne|paprika|smoked paprika|chili powder|chipotle)\b/,
      /\b(?:cumin|coriander|turmeric|curry|garam masala|cardamom|clove|cloves|nutmeg|allspice|saffron|sumac|za'atar|fenugreek)\b/,
      /\b(?:cinnamon|ginger|star anise|anise|fennel seed|caraway|dill seed|celery seed)\b/,
      /\b(?:oregano|basil|thyme|rosemary|sage|parsley|cilantro|dill|chive|chives|tarragon|marjoram|bay lea|mint|lavender)\b/,
      /\b(?:garlic powder|onion powder|garlic salt|seasoning|italian seasoning|herb|herbs de provence)\b/,
      /\b(?:mustard powder|dry mustard|ground mustard)\b/,
      /\b(?:msg|bouillon|stock cube)\b/,
    ],
  ],

  // Liquids & Condiments
  [
    "Liquids & Condiments",
    [
      /\b(?:water|broth|stock|chicken broth|beef broth|vegetable broth|chicken stock|beef stock|bone broth)\b/,
      /\b(?:wine|beer|sake|mirin|sherry|marsala|bourbon|rum|brandy|vodka|liqueur|champagne)\b/,
      /\b(?:vinegar|balsamic|red wine vinegar|white wine vinegar|apple cider vinegar|rice vinegar)\b/,
      /\b(?:soy sauce|tamari|fish sauce|oyster sauce|hoisin|teriyaki|worcestershire|tabasco|hot sauce|sriracha)\b/,
      /\b(?:ketchup|mustard|dijon|bbq sauce|barbecue sauce|salsa|pesto|chutney|relish|horseradish)\b/,
      /\b(?:lemon juice|lime juice|orange juice|apple juice|cranberry juice|tomato juice|pomegranate juice|juice)\b/,
      /\b(?:coconut milk|almond milk|oat milk|soy milk)\b/,
      /\b(?:tomato paste|tomato sauce|marinara|enchilada sauce|adobo|paste)\b/,
      /\b(?:extract|vanilla extract|almond extract|rose water|orange blossom)\b/,
    ],
  ],

  // Produce — broad catch for fruits/vegetables/herbs
  [
    "Produce",
    [
      /\b(?:apple|apples|banana|bananas|orange|oranges|lemon|lemons|lime|limes|grape|grapes|grapefruit)\b/,
      /\b(?:strawberr|blueberr|blackberr|raspberr|cranberr|cherry|cherries|peach|plum|apricot|nectarine|mango|papaya|pineapple|kiwi|fig|pomegranate|melon|watermelon|cantaloupe|honeydew)\b/,
      /\b(?:pear|persimmon|guava|passion fruit|lychee|starfruit|dragon fruit|kumquat|date|dates|prune|prunes|avocado)\b/,
      /\b(?:tomato|tomatoes|potato|potatoes|sweet potato|yam|onion|onions|garlic|shallot|leek|scallion|green onion|chive)\b/,
      /\b(?:carrot|celery|broccoli|cauliflower|cabbage|brussels sprout|kale|spinach|lettuce|arugula|chard|collard|bok choy|watercress)\b/,
      /\b(?:bell pepper|jalapeño|jalapeno|serrano|habanero|poblano|anaheim|chili|chile)\b/,
      /\b(?:mushroom|zucchini|squash|eggplant|artichoke|asparagus|green bean|snap pea|snow pea|okra)\b/,
      /\b(?:corn|pea|peas|bean|beans|lentil|lentils|chickpea|edamame)\b/,
      /\b(?:cucumber|radish|turnip|beet|parsnip|rutabaga|jicama|fennel|endive|radicchio)\b/,
      /\b(?:ginger|fresh ginger|galangal|lemongrass|turmeric root)\b/,
      /\b(?:basil|cilantro|parsley|mint|dill|chive|rosemary|thyme|sage|oregano|tarragon)\b/,
      /\b(?:rhubarb|plantain|taro|breadfruit|cassava|yuca)\b/,
    ],
  ],
];

/**
 * Classify a single ingredient name into a display group.
 * Pure string-matching — no backend metadata required.
 */
export function getDisplayGroup(ingredientName: string): DisplayGroup {
  const name = ingredientName.trim().toLowerCase();

  for (const [group, patterns] of KEYWORD_RULES) {
    for (const pattern of patterns) {
      if (pattern.test(name)) {
        return group;
      }
    }
  }

  return "Other";
}

/**
 * Group a list of ingredient names into display sections.
 * Returns entries in the canonical section order, alphabetically sorted
 * within each section.  Empty sections are omitted.
 */
export function groupIngredients(ingredients: string[]): Array<{ group: DisplayGroup; items: string[] }> {
  const buckets = new Map<DisplayGroup, string[]>();

  for (const name of ingredients) {
    const group = getDisplayGroup(name);
    if (!buckets.has(group)) {
      buckets.set(group, []);
    }
    buckets.get(group)!.push(name);
  }

  // Sort items inside each bucket alphabetically
  for (const items of buckets.values()) {
    items.sort((a, b) => a.localeCompare(b));
  }

  // Return in the canonical display order, skipping empty groups
  return DISPLAY_GROUP_ORDER.filter((g) => buckets.has(g)).map((g) => ({
    group: g,
    items: buckets.get(g)!,
  }));
}
