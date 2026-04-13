좋아. 아래 내용 그대로 Figma에서 화면 설계할 수 있게 **페이지/컴포넌트/상태/인터랙션**까지 구체화해서 줄게. (양식 기반, 너가 말한 “메인 재료 Top3 + 양념 Similar2+Different2 + 맛 변화” UX 포함)

---

## Figma 구성안 (Information Architecture)

### Pages (Figma 파일 페이지)

1. **Foundations**

   * Colors, Typography, Spacing, Grid (8pt)
2. **Components**

   * Buttons, Chips, Input, Cards, Tabs, Bottom sheet/Modal, Toast, Tag
3. **Screens**

   * S1 Home/Input
   * S2 Results List
   * S3 Recipe Detail + Remix
   * S4 Substitution Picker (Modal)
   * S5 Add-Ingredient Pairing (Modal)
   * S6 Summary/Final Recipe
4. **States**

   * Empty, Loading, Error, No-match, Low-confidence

---

## Screen 1: Home / Input (S1)

**Goal:** 재료 입력 + 선호 옵션 설정 + 추천 시작

### Layout

* Header: **Fridge Remix**
* Section A: Ingredient Input
* Section B: Preferences
* CTA: “Get Recipe Ideas”

### Components

1. **Ingredient Input**

* Title: “What do you have?”
* Input style:

  * Large text area with placeholder: “e.g., chicken, pasta, tomato, garlic…”
* Helper text: “Separate items with commas”
* Buttons:

  * “Add from quick list” (opens quick chips)
  * “Clear”

2. **Quick Ingredient Chips** (optional)

* Common Western items:

  * chicken, beef, eggs, milk, butter, olive oil, garlic, onion, tomato, pasta, rice, cheese, lemon

3. **Preferences**

* Time:

  * Chip group: “Under 15 min”, “Under 30 min”, “No limit”
* Style:

  * Chip group: “Italian”, “Mexican”, “American”, “Asian-inspired”
* Taste:

  * Toggle chips: “Spicy”, “Lighter”
* Dietary (optional):

  * Toggle chips: “Dairy-free”, “Gluten-free”, “Vegetarian”
* Allergies (optional dropdown):

  * “Nut allergy”, “Shellfish allergy”, etc.

4. **CTA Button**

* Primary button: “Get Recipe Ideas”
* Disabled state if ingredient input empty

### States

* Empty state: illustration + “Add at least 3 ingredients”
* Loading: skeleton cards

### Interactions

* Tap CTA → go to **S2 Results List**
* Quick chips add items into text area automatically

---

## Screen 2: Results List (S2)

**Goal:** 추천 레시피 3–10개 보여주고 하나 선택

### Layout

* Header: Back + “Recipe Ideas”
* Filter row: “Cook-now only” toggle + “Sort: Best match”
* Results list: Recipe cards

### Recipe Card (Reusable Component)

* Title: “Creamy Garlic Pasta”
* Tags row: time chip “15 min”, style “Italian”, difficulty “Easy”
* **Feasibility badge**

  * Green: “Cook-now”
  * Orange: “Needs substitutions”
* Ingredient coverage bar (optional): “8/10 ingredients available”
* Missing preview (if any): “Missing: heavy cream, parmesan”
* CTA: “View & Remix”

### States

* No match: “No recipes found. Try removing one preference or adding more ingredients.”
* Low confidence: show label “Approximate match”

### Interactions

* Tap card → **S3 Recipe Detail + Remix**

---

## Screen 3: Recipe Detail + Remix (S3)

**Goal:** 레시피를 “메인 재료 / 양념”으로 나누고 부족분 해결

### Layout

* Header: Back + Recipe title
* Top summary:

  * Time, servings, tags
  * Feasibility badge
* Tabs: **Overview | Remix | Notes**

### Overview Tab

* Ingredients list with status:

  * ✅ Available
  * ❌ Missing
* Steps preview (collapsed)
* Button: “Open Remix”

### Remix Tab (핵심)

**Section 1: Missing Check Summary**

* “You can cook this with substitutions.”
* Missing Main Ingredients: list
* Missing Seasonings: list

**Section 2: Main Ingredient Replacement**

* For each missing main ingredient:

  * Row: “Missing: chicken”
  * Button: “Choose replacement”
  * When chosen: shows selected replacement + flavor note

**Main Replacement Card (after selection)**

* “Selected: shrimp”
* “Expected change: lighter taste, cooks faster”
* “Adjustment: reduce cooking time by 3–4 minutes”

**Section 3: Seasoning Options**

* For each missing seasoning:

  * Row: “Missing: heavy cream”
  * Two sub-sections:

    * “Similar taste (Top 2)”
    * “Different but works (Top 2)”
  * Each option as selectable card

**Seasoning Option Card**

* Title: “Milk + Butter”
* Badge: “Similar”
* Flavor change: “Still creamy, slightly lighter”
* How to mix (one line): “1 cup milk + 1 tbsp butter”
* When to add: “Add after garlic is sautéed”
* Select button: “Use this”

**Section 4: Generate Final Recipe**

* Primary CTA: “Generate Final Steps”
* Secondary: “Back to list”

### Notes Tab (optional)

* Substitution disclaimer
* Allergy warnings if toggled

### Interactions

* Tap “Choose replacement” → open **S4 Substitution Picker**
* Tap seasoning option → select it (single-select per missing seasoning)
* Tap “Generate Final Steps” → **S6 Summary/Final Recipe**

---

## Modal Screen 4: Main Ingredient Substitution Picker (S4)

**Goal:** 메인 재료 Top 3를 선택하게 만들기

### Modal layout

* Title: “Replace chicken”
* Subtitle: “Pick one option (Top 3)”
* List of 3 option cards

**Option Card**

* Option name: “Turkey”
* Texture change: “firmer, slightly drier”
* Flavor change: “milder”
* Best use tip: “Add extra sauce to keep it moist”
* Button: “Select”

**Bottom**

* “Skip replacement” link

---

## Modal Screen 5: Add-Ingredient Pairing (Optional feature) (S5)

**Goal:** 사용자가 “이 재료 넣고 싶어”를 실행

### Entry point

* Button on S3: “Add an ingredient I want to use”
* Modal content:

  * Input: “Ingredient to add” (e.g., mushrooms)
  * LLM output sections:

    * Compatibility: Good / Conditional / Not recommended
    * How to add: timing + method
    * Flavor change: 1 sentence
    * Caution: 1 line
* CTA: “Apply to recipe”

(이 기능은 MVP에서 빼도 됨. 넣으면 차별점이 강해져.)

---

## Screen 6: Summary / Final Recipe (S6)

**Goal:** 최종 결과를 “한 장”으로 보여주기

### Layout

* Header: “Your Remixed Recipe”
* Summary block:

  * Used ingredients
  * Missing ingredients (if any)
* Substitution summary:

  * Main replacement chosen
  * Seasoning option chosen
* Flavor change summary (1–2 lines)
* Final Steps (numbered list)
* Buttons:

  * “Copy recipe”
  * “Save”
  * “Try another recipe”

### States

* If still missing too many items:

  * Show “Shopping needed” badge + list

---

## 디자인 시스템 (Figma 토큰 추천)

* 8pt grid
* Buttons: Primary, Secondary, Ghost
* Chips: selectable, multi-select
* Badges: Cook-now green / Needs-sub orange
* Cards: recipe card, option card
* Typography:

  * H1 title, H2 section, body, caption

---

## 개발자가 바로 구현 가능한 “데이터 구조” (UI가 기대하는 값)

* RecipeCard:

  * title, time, tags, feasibility, coverage_ratio, missing_preview[]
* Detail:

  * ingredients: [{name, status}]
  * main_missing[]
  * seasoning_missing[]
  * main_sub_options: {missing_item: [opt1,opt2,opt3]}
  * seasoning_options: {missing_item: {similar:[2], different:[2]}}
  * final_steps[]
  * flavor_summary

---

원하면 내가 이걸 **Figma에 바로 옮기기 쉬운 체크리스트**(프레임 이름 규칙, 컴포넌트 네이밍, Auto Layout 설정)로도 만들어줄게.
