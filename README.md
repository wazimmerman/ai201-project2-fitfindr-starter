# FitFindr

FitFindr is a small agent that searches mock secondhand listings, picks the best match, suggests an outfit using the user's wardrobe, and writes a short fit-card caption.

## Setup

```bash
uv pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
GROQ_API_KEY=your_key_here
```

Run tests:

```bash
uv run pytest tests/
```

Run the app:

```bash
uv run python app.py
```

## Tool Inventory

`search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Purpose: searches `data/listings.json` with local deterministic filtering and relevance scoring. `description` is the user's desired item/style, `size` is an optional size filter, and `max_price` is an optional inclusive price ceiling. It returns listing dicts with `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`, sorted best match first.

`suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Purpose: calls Groq `llama-3.3-70b-versatile` to suggest 1-2 outfits for the selected listing. `new_item` is the listing chosen by the agent, and `wardrobe` is a dict with an `items` list. It returns a non-empty styling string; if the wardrobe is empty, it gives general advice instead of crashing.

`create_fit_card(outfit: str, new_item: dict) -> str`

Purpose: calls Groq `llama-3.3-70b-versatile` to write a short social caption. `outfit` is the suggestion from `suggest_outfit`, and `new_item` is the selected listing. It returns a 2-4 sentence caption, or a descriptive error string if `outfit` is empty.

## Planning Loop

`run_agent()` creates a session dict with the original query, parsed filters, search results, selected item, wardrobe, outfit suggestion, fit card, and error field. A regex parser extracts phrases like `under $30` into `max_price=30.0` and `size M` into `size="M"`; the cleaned query becomes the search description.

The agent always searches first. If `search_listings()` returns `[]`, the agent writes an actionable message to `session["error"]` and returns immediately. If results exist, it stores `results[0]` as `session["selected_item"]`, passes that exact dict to `suggest_outfit()`, stores the returned outfit text, then passes the outfit and same selected item to `create_fit_card()`.

## State Management

The session dict is the single source of truth for one interaction. The key state fields are:

- `parsed`: the extracted `description`, `size`, and `max_price`
- `search_results`: all matching listing dicts
- `selected_item`: the top listing, passed to both downstream tools
- `outfit_suggestion`: the string returned by `suggest_outfit`
- `fit_card`: the string returned by `create_fit_card`
- `error`: a message only when the agent stops early

The Gradio app does not re-run any tools. It calls `run_agent()` once and formats the returned session into the three output panels.

## Interaction Walkthrough

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 - Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee baggy jeans chunky sneakers"`, `size=None`, `max_price=30.0`
- Why this tool: the agent must find a purchasable listing before styling anything
- Output: a ranked list of graphic tee listings under $30

**Step 2 - Tool called:**
- Tool: `suggest_outfit`
- Input: the top listing from Step 1 and `get_example_wardrobe()`
- Why this tool: the selected thrift item needs to be styled with the user's closet
- Output: a styling suggestion using named wardrobe pieces such as baggy jeans, chunky sneakers, combat boots, or a black crossbody bag

**Step 3 - Tool called:**
- Tool: `create_fit_card`
- Input: the outfit suggestion from Step 2 and the same selected listing from Step 1
- Why this tool: the user needs a shareable caption for the finished look
- Output: a short caption that mentions the item, price, platform, and vibe

**Final output to user:**
The app displays the top listing in panel one, the outfit idea in panel two, and the fit card in panel three.

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the description, size, and price filters | `run_agent()` sets `session["error"]` with a suggestion to widen the price range, remove size, or search a broader style. It does not call the other tools. |
| `suggest_outfit` | Wardrobe has no items | The tool asks the LLM for general styling categories and proportions instead of named wardrobe pieces, then returns that string. |
| `create_fit_card` | Outfit string is empty | The tool returns "Cannot create a fit card yet..." and explains that an outfit suggestion must be generated first. |

Concrete test example: `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`. The full agent returns an error message and leaves `selected_item`, `outfit_suggestion`, and `fit_card` as `None`.

## AI Usage

For the tool implementations, I used the completed Tool sections in `planning.md` as the AI prompt. The AI-produced structure was reviewed against the required signatures and then adjusted to use `load_listings()`, add deterministic scoring, and include fallback strings when Groq is unavailable.

For the planning loop, I used the Planning Loop, State Management, and Architecture sections from `planning.md` as the AI prompt. I checked that the generated flow branches after empty search results, stores values in the session dict, and passes the exact selected listing forward instead of reconstructing state.

## Spec Reflection

**One way planning.md helped during implementation:**
Writing the branch behavior before coding made the no-results path obvious. The agent's most important decision is not which LLM prompt to use, but whether it should continue at all after search.

**One divergence from your spec, and why:**
The LLM tools include fallback strings if the Groq call fails. The original happy-path spec assumed the API would be available, but adding fallbacks makes demos and tests more reliable while still attempting the required Groq call first.
