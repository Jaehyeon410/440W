export interface Recipe {
  id: string;
  title: string;
  time: string;
  style: string;
  difficulty: string;
  feasibility: "cook-now" | "needs-sub";
  coverageRatio: string;
  missingPreview: string[];
  ingredients: Ingredient[];
  mainMissing: string[];
  seasoningMissing: string[];
  steps: RecipeStep[];
  flavorSummary: string;
}

export interface Ingredient {
  name: string;
  amount: string;
  status: "available" | "missing";
}

export interface RecipeStep {
  title: string;
  description: string;
  detail?: string;
  tips?: string[];
  warnings?: string[];
}

// Mock data
export const mockRecipes: Recipe[] = [
  {
    id: "1",
    title: "Creamy Garlic Pasta",
    time: "15 min",
    style: "Italian",
    difficulty: "Easy",
    feasibility: "cook-now",
    coverageRatio: "8/10",
    missingPreview: [],
    ingredients: [
      { name: "Pasta", amount: "200g", status: "available" },
      { name: "Garlic", amount: "3 cloves", status: "available" },
      { name: "Olive oil", amount: "2 tbsp", status: "available" },
      { name: "Butter", amount: "2 tbsp", status: "available" },
      { name: "Heavy cream", amount: "1 cup", status: "missing" },
      { name: "Parmesan", amount: "1/2 cup", status: "missing" },
    ],
    mainMissing: [],
    seasoningMissing: ["Heavy cream", "Parmesan"],
    steps: [
      {
        title: "Boil pasta",
        description: "Boil pasta according to package directions",
        detail: "Bring a large pot of salted water to a rolling boil. Add pasta and cook for 8-10 minutes until al dente. Reserve 1 cup of pasta water before draining.",
        tips: [
          "Salt your water generously - it should taste like the sea",
          "Stir occasionally to prevent sticking",
          "Don't rinse pasta after draining - you want the starch"
        ],
        warnings: [
          "Don't overcook - pasta continues cooking when mixed with sauce",
          "Save pasta water before draining - it's liquid gold for sauce"
        ]
      },
      {
        title: "Sauté garlic",
        description: "Sauté minced garlic in olive oil and butter",
        detail: "Heat olive oil and butter in a large pan over medium heat. Add minced garlic and cook for 1-2 minutes until fragrant but not browned.",
        tips: [
          "Use medium heat - garlic burns easily",
          "Mince garlic finely for even distribution",
          "Fresh garlic is much better than jarred for this dish"
        ],
        warnings: [
          "Watch carefully - burned garlic tastes bitter and will ruin the dish",
          "Don't let butter brown before adding garlic"
        ]
      },
      {
        title: "Add cream",
        description: "Add heavy cream and simmer for 3 minutes",
        detail: "Pour in heavy cream and stir to combine with the garlic mixture. Let it simmer gently for 3 minutes, stirring occasionally, until it thickens slightly.",
        tips: [
          "Use room temperature cream if possible",
          "Stir frequently to prevent scorching",
          "Add a pinch of nutmeg for extra depth"
        ],
        warnings: [
          "Don't let it boil rapidly - cream can separate",
          "If sauce is too thick, thin with reserved pasta water"
        ]
      },
      {
        title: "Combine pasta",
        description: "Toss pasta in sauce and add parmesan",
        detail: "Add drained pasta to the sauce and toss well to coat every strand. Remove from heat and stir in grated parmesan cheese until melted and creamy.",
        tips: [
          "Toss pasta off heat when adding cheese",
          "Add pasta water gradually if sauce is too thick",
          "Use freshly grated parmesan for best results"
        ],
        warnings: [
          "Don't add cheese over high heat - it can become grainy",
          "Mix thoroughly to prevent clumping"
        ]
      },
      {
        title: "Season and serve",
        description: "Season with salt and pepper to taste",
        detail: "Taste and adjust seasoning with salt and freshly ground black pepper. Serve immediately in warm bowls, garnished with extra parmesan and fresh herbs if desired.",
        tips: [
          "Serve in warmed bowls for best experience",
          "Add red pepper flakes for a spicy kick",
          "Fresh parsley or basil makes a great garnish"
        ],
        warnings: [
          "Serve immediately - cream sauces don't reheat well",
          "Don't over-salt - parmesan is already salty"
        ]
      },
    ],
    flavorSummary: "Rich, creamy, and garlicky with a smooth texture",
  },
  {
    id: "2",
    title: "Chicken Stir-fry",
    time: "20 min",
    style: "Asian-inspired",
    difficulty: "Easy",
    feasibility: "needs-sub",
    coverageRatio: "6/8",
    missingPreview: ["Chicken", "Soy sauce"],
    ingredients: [
      { name: "Chicken breast", amount: "300g", status: "missing" },
      { name: "Garlic", amount: "2 cloves", status: "available" },
      { name: "Onion", amount: "1 medium", status: "available" },
      { name: "Soy sauce", amount: "3 tbsp", status: "missing" },
      { name: "Olive oil", amount: "2 tbsp", status: "available" },
    ],
    mainMissing: ["Chicken breast"],
    seasoningMissing: ["Soy sauce"],
    steps: [
      {
        title: "Prep chicken",
        description: "Cut chicken into bite-sized pieces",
        detail: "Slice chicken breast against the grain into thin, bite-sized pieces about 1 inch in size. Pat dry with paper towels for better browning.",
        tips: [
          "Freeze chicken for 15 minutes before cutting for easier slicing",
          "Cut against the grain for tender pieces",
          "Keep pieces uniform for even cooking"
        ],
        warnings: [
          "Ensure chicken is fully thawed before cutting",
          "Use a clean cutting board to prevent cross-contamination"
        ]
      },
      {
        title: "Heat wok",
        description: "Heat oil in a wok over high heat",
        detail: "Heat your wok or large skillet over high heat until it's smoking hot. Add oil and swirl to coat the surface.",
        tips: [
          "Use an oil with high smoke point like vegetable or peanut oil",
          "Wok should be very hot before adding ingredients",
          "Have all ingredients prepared before you start cooking"
        ],
        warnings: [
          "Don't walk away - stir-frying happens fast",
          "Ensure good ventilation - high heat cooking creates smoke"
        ]
      },
      {
        title: "Cook chicken",
        description: "Stir-fry chicken until cooked through",
        detail: "Add chicken pieces to the hot wok in a single layer. Let sear for 30 seconds before tossing. Continue stir-frying for 5-6 minutes until golden and cooked through.",
        tips: [
          "Don't overcrowd the wok - cook in batches if needed",
          "Let chicken sit briefly before tossing for better sear",
          "Use a metal spatula to scrape up any browned bits"
        ],
        warnings: [
          "Chicken must reach 165°F internal temperature",
          "Don't stir constantly - let it develop color"
        ]
      },
      {
        title: "Add aromatics",
        description: "Add garlic and onion, cook for 2 minutes",
        detail: "Push chicken to the sides of the wok. Add minced garlic and sliced onion to the center. Stir-fry for 2 minutes until fragrant and onion is slightly softened.",
        tips: [
          "Add garlic after chicken to prevent burning",
          "Slice onion into thick pieces to maintain texture",
          "Keep everything moving to prevent burning"
        ],
        warnings: [
          "Garlic can burn quickly on high heat",
          "Don't let vegetables turn mushy"
        ]
      },
      {
        title: "Add sauce and finish",
        description: "Add soy sauce and toss to combine",
        detail: "Pour soy sauce around the edges of the wok so it hits the hot surface. Toss everything together for 1 minute until well coated and glossy.",
        tips: [
          "Add sauce to the sides of the wok to caramelize slightly",
          "Toss vigorously to coat everything evenly",
          "Taste and adjust seasoning if needed"
        ],
        warnings: [
          "Don't add too much sauce - dish should be glossy, not soupy",
          "Serve immediately for best texture"
        ]
      },
    ],
    flavorSummary: "Savory and umami with aromatic garlic and onion",
  },
  {
    id: "3",
    title: "Tomato Basil Pasta",
    time: "25 min",
    style: "Italian",
    difficulty: "Easy",
    feasibility: "needs-sub",
    coverageRatio: "7/9",
    missingPreview: ["Tomato", "Basil"],
    ingredients: [
      { name: "Pasta", amount: "200g", status: "available" },
      { name: "Tomato", amount: "4 medium", status: "missing" },
      { name: "Garlic", amount: "3 cloves", status: "available" },
      { name: "Basil", amount: "1/4 cup", status: "missing" },
      { name: "Olive oil", amount: "3 tbsp", status: "available" },
    ],
    mainMissing: [],
    seasoningMissing: ["Tomato", "Basil"],
    steps: [
      {
        title: "Cook pasta",
        description: "Cook pasta until al dente",
        detail: "Bring a large pot of salted water to boil. Add pasta and cook for 8-10 minutes until al dente. Reserve 1 cup pasta water before draining.",
        tips: [
          "Salt water generously for well-seasoned pasta",
          "Stir occasionally to prevent sticking",
          "Test pasta 2 minutes before package time"
        ],
        warnings: [
          "Don't overcook - pasta should have a slight bite",
          "Always reserve pasta water before draining"
        ]
      },
      {
        title: "Sauté garlic",
        description: "Sauté garlic in olive oil",
        detail: "Heat olive oil in a large pan over medium heat. Add thinly sliced or minced garlic and cook for 1-2 minutes until golden and fragrant.",
        tips: [
          "Use quality extra virgin olive oil for best flavor",
          "Slice garlic thin for quick cooking",
          "Medium heat prevents burning"
        ],
        warnings: [
          "Don't burn the garlic - it becomes bitter",
          "Remove from heat if it's browning too quickly"
        ]
      },
      {
        title: "Cook tomatoes",
        description: "Add diced tomatoes and cook until soft",
        detail: "Add diced fresh tomatoes to the garlic oil. Season with salt and pepper. Cook for 10-12 minutes, stirring occasionally, until tomatoes break down into a chunky sauce.",
        tips: [
          "Use ripe, in-season tomatoes for best flavor",
          "Break up tomatoes with your spoon as they cook",
          "Add a pinch of sugar if tomatoes are acidic"
        ],
        warnings: [
          "Don't rush this step - tomatoes need time to develop flavor",
          "Stir occasionally to prevent sticking"
        ]
      },
      {
        title: "Combine pasta",
        description: "Toss pasta with tomato sauce",
        detail: "Add drained pasta to the tomato sauce. Toss well to coat. Add reserved pasta water a little at a time if sauce is too thick. Cook together for 1-2 minutes.",
        tips: [
          "Toss pasta and sauce together over low heat",
          "Add pasta water gradually to achieve desired consistency",
          "The starch helps sauce cling to pasta"
        ],
        warnings: [
          "Don't add all pasta water at once",
          "Sauce should coat pasta, not pool in the bowl"
        ]
      },
      {
        title: "Add basil and serve",
        description: "Top with fresh basil before serving",
        detail: "Remove from heat. Tear fresh basil leaves and toss with the pasta. Serve immediately with extra basil and grated parmesan if desired.",
        tips: [
          "Tear basil by hand instead of cutting to prevent browning",
          "Add basil at the very end to preserve fresh flavor",
          "Drizzle with extra olive oil before serving"
        ],
        warnings: [
          "Don't cook basil - heat destroys its fresh flavor",
          "Serve immediately for best taste"
        ]
      },
    ],
    flavorSummary: "Fresh, bright, and herbaceous with natural tomato sweetness",
  },
];

export const mainSubstitutions: Record<string, MainSubOption[]> = {
  "Chicken breast": [
    {
      name: "Turkey breast",
      textureChange: "Firmer, slightly drier",
      flavorChange: "Milder",
      bestUseTip: "Add extra sauce to keep it moist",
    },
    {
      name: "Shrimp",
      textureChange: "Tender and juicy",
      flavorChange: "Lighter, sweeter",
      bestUseTip: "Reduce cooking time by 3-4 minutes",
    },
    {
      name: "Tofu",
      textureChange: "Softer, absorbs flavors well",
      flavorChange: "Neutral, takes on sauce flavor",
      bestUseTip: "Press tofu first and use firm variety",
    },
  ],
};

export const seasoningSubstitutions: Record<string, SeasoningOption[]> = {
  "Heavy cream": [
    {
      name: "Milk + Butter",
      type: "similar",
      flavorChange: "Still creamy, slightly lighter",
      howToMix: "1 cup milk + 1 tbsp butter",
      whenToAdd: "Add after garlic is sautéed",
    },
    {
      name: "Coconut cream",
      type: "similar",
      flavorChange: "Creamy with subtle coconut notes",
      howToMix: "Use 1 cup coconut cream directly",
      whenToAdd: "Add after garlic is sautéed",
    },
    {
      name: "Greek yogurt",
      type: "different",
      flavorChange: "Tangy and lighter, less rich",
      howToMix: "1 cup yogurt, stir gently",
      whenToAdd: "Add off heat at the end",
    },
    {
      name: "Olive oil + Pasta water",
      type: "different",
      flavorChange: "Light and silky, not creamy",
      howToMix: "3 tbsp olive oil + 1/2 cup pasta water",
      whenToAdd: "Toss with hot pasta",
    },
  ],
  "Parmesan": [
    {
      name: "Pecorino Romano",
      type: "similar",
      flavorChange: "Sharper and saltier",
      howToMix: "Use same amount, reduce salt",
      whenToAdd: "Add at the same time",
    },
    {
      name: "Nutritional yeast",
      type: "similar",
      flavorChange: "Nutty, cheesy (dairy-free)",
      howToMix: "Use 1/4 cup for 1/2 cup parmesan",
      whenToAdd: "Sprinkle at the end",
    },
    {
      name: "Breadcrumbs + Garlic",
      type: "different",
      flavorChange: "Crunchy, garlicky (no cheese flavor)",
      howToMix: "1/2 cup breadcrumbs + 1 clove garlic",
      whenToAdd: "Toast and sprinkle on top",
    },
    {
      name: "Cashew cream",
      type: "different",
      flavorChange: "Creamy and mild, not sharp",
      howToMix: "Blend 1/2 cup soaked cashews with water",
      whenToAdd: "Stir into sauce",
    },
  ],
  "Soy sauce": [
    {
      name: "Tamari",
      type: "similar",
      flavorChange: "Similar umami, gluten-free",
      howToMix: "Use same amount",
      whenToAdd: "Use exactly as soy sauce",
    },
    {
      name: "Coconut aminos",
      type: "similar",
      flavorChange: "Slightly sweeter, less salty",
      howToMix: "Use 1.5x amount",
      whenToAdd: "Use exactly as soy sauce",
    },
    {
      name: "Worcestershire sauce",
      type: "different",
      flavorChange: "Tangy and complex",
      howToMix: "Use half the amount + pinch of salt",
      whenToAdd: "Use exactly as soy sauce",
    },
    {
      name: "Salt + Garlic powder",
      type: "different",
      flavorChange: "Salty and savory, less complex",
      howToMix: "1 tsp salt + 1/2 tsp garlic powder",
      whenToAdd: "Season during cooking",
    },
  ],
  "Tomato": [
    {
      name: "Canned tomatoes",
      type: "similar",
      flavorChange: "Deeper, cooked flavor",
      howToMix: "Use 1 can (400g) for 4 fresh tomatoes",
      whenToAdd: "Use in place of fresh",
    },
    {
      name: "Tomato paste + Water",
      type: "similar",
      flavorChange: "Concentrated, intense",
      howToMix: "2 tbsp paste + 1 cup water",
      whenToAdd: "Cook paste first, then add water",
    },
    {
      name: "Red bell pepper",
      type: "different",
      flavorChange: "Sweet, less acidic",
      howToMix: "Dice 2 large peppers",
      whenToAdd: "Cook longer to soften",
    },
    {
      name: "Roasted red peppers (jarred)",
      type: "different",
      flavorChange: "Smoky and sweet",
      howToMix: "Use 1 cup, blended or chopped",
      whenToAdd: "Add near the end",
    },
  ],
  "Basil": [
    {
      name: "Italian seasoning",
      type: "similar",
      flavorChange: "Herby with oregano notes",
      howToMix: "Use 1 tbsp dried for 1/4 cup fresh",
      whenToAdd: "Add during cooking",
    },
    {
      name: "Oregano",
      type: "similar",
      flavorChange: "Earthier, more pungent",
      howToMix: "Use half the amount",
      whenToAdd: "Add during cooking",
    },
    {
      name: "Spinach",
      type: "different",
      flavorChange: "Mild, green, no herb flavor",
      howToMix: "Use 1 cup fresh spinach",
      whenToAdd: "Wilt in at the end",
    },
    {
      name: "Parsley",
      type: "different",
      flavorChange: "Fresh and mild",
      howToMix: "Use same amount",
      whenToAdd: "Add at the end for freshness",
    },
  ],
};