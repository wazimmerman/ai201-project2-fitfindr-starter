"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "i",
    "im",
    "in",
    "is",
    "it",
    "looking",
    "me",
    "of",
    "the",
    "to",
    "under",
    "want",
    "with",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat_completion(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """Call Groq and return the assistant text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=280,
    )
    return response.choices[0].message.content.strip()


def _tokens(text: str) -> set[str]:
    """Normalize user/listing text into searchable keyword tokens."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOPWORDS and len(token) > 1
    }


def _listing_text(listing: dict) -> str:
    fields = [
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        listing.get("size", ""),
        listing.get("brand") or "",
        listing.get("platform", ""),
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
    ]
    return " ".join(fields)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    query_tokens = _tokens(description)
    if not query_tokens:
        return []

    scored_results: list[tuple[int, dict]] = []
    requested_size = size.lower().strip() if size else None

    for listing in listings:
        if max_price is not None and float(listing["price"]) > float(max_price):
            continue

        listing_size = str(listing.get("size", "")).lower()
        if requested_size and requested_size not in listing_size:
            continue

        listing_tokens = _tokens(_listing_text(listing))
        score = len(query_tokens & listing_tokens)

        title_tokens = _tokens(listing.get("title", ""))
        tag_tokens = _tokens(" ".join(listing.get("style_tags", [])))
        score += 2 * len(query_tokens & title_tokens)
        score += len(query_tokens & tag_tokens)

        if score > 0:
            scored_results.append((score, listing))

    scored_results.sort(key=lambda item: (-item[0], item[1]["price"]))
    return [listing for _, listing in scored_results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    wardrobe_items = wardrobe.get("items", []) if wardrobe else []
    item_summary = (
        f"{new_item.get('title')} (${new_item.get('price')}, "
        f"{new_item.get('platform')}) in {new_item.get('colors')} with tags "
        f"{new_item.get('style_tags')}"
    )

    system_prompt = (
        "You are FitFindr, a practical secondhand styling assistant. "
        "Give specific, wearable outfit advice in a warm, concise voice."
    )

    if not wardrobe_items:
        user_prompt = (
            "The user has not added wardrobe items yet. Give general styling "
            f"advice for this thrifted item: {item_summary}. Mention what kinds "
            "of bottoms, shoes, and layers would work. Keep it to 3-5 sentences."
        )
    else:
        wardrobe_lines = []
        for item in wardrobe_items:
            wardrobe_lines.append(
                "- {name} ({category}; colors: {colors}; tags: {tags}; notes: {notes})".format(
                    name=item.get("name"),
                    category=item.get("category"),
                    colors=", ".join(item.get("colors", [])),
                    tags=", ".join(item.get("style_tags", [])),
                    notes=item.get("notes") or "none",
                )
            )
        user_prompt = (
            f"New thrifted item: {item_summary}\n\n"
            "User wardrobe:\n"
            + "\n".join(wardrobe_lines)
            + "\n\nSuggest 1-2 outfits that use the new item and name specific "
            "wardrobe pieces. Include styling details like tuck, layering, or proportions."
        )

    try:
        return _chat_completion(system_prompt, user_prompt, temperature=0.7)
    except Exception as exc:
        if not wardrobe_items:
            return (
                f"General styling idea for {new_item.get('title')}: pair it with relaxed denim "
                "or a simple trouser, add shoes that match its strongest vibe, and use one "
                "easy layer or accessory to make it feel intentional. "
                f"(LLM styling unavailable: {exc})"
            )
        first_bottom = next((item for item in wardrobe_items if item.get("category") == "bottoms"), None)
        first_shoe = next((item for item in wardrobe_items if item.get("category") == "shoes"), None)
        pieces = [piece["name"] for piece in (first_bottom, first_shoe) if piece]
        piece_text = " and ".join(pieces) if pieces else "simple pieces from your wardrobe"
        return (
            f"Try {new_item.get('title')} with {piece_text}. Keep the proportions balanced, "
            "then add one accessory or light layer to make the outfit feel finished. "
            f"(LLM styling unavailable: {exc})"
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return (
            "Cannot create a fit card yet because the outfit suggestion is empty. "
            "Run suggest_outfit with a selected listing before generating the caption."
        )

    system_prompt = (
        "You write casual, authentic OOTD captions for secondhand fashion posts. "
        "Avoid sounding like an ad."
    )
    user_prompt = (
        "Create a 2-4 sentence caption for this thrifted find.\n\n"
        f"Item: {new_item.get('title')}\n"
        f"Price: ${new_item.get('price')}\n"
        f"Platform: {new_item.get('platform')}\n"
        f"Outfit idea: {outfit}\n\n"
        "Mention the item name, price, and platform naturally once each. "
        "Keep it social-media ready and specific to the outfit vibe."
    )

    try:
        return _chat_completion(system_prompt, user_prompt, temperature=1.0)
    except Exception as exc:
        return (
            f"Found {new_item.get('title')} on {new_item.get('platform')} for "
            f"${new_item.get('price')} and styled it around this vibe: {outfit} "
            f"(LLM caption unavailable: {exc})"
        )
