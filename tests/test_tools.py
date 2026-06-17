import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import run_agent
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


class _FakeMessage:
    content = "Mocked FitFindr response with specific styling advice."


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


def _mock_groq(monkeypatch):
    def fake_chat_completion(system_prompt, user_prompt, temperature):
        return _FakeResponse().choices[0].message.content

    monkeypatch.setattr("tools._chat_completion", fake_chat_completion)


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0
    assert "graphic" in results[0]["title"].lower() or "graphic" in results[0]["description"].lower()


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)

    assert all(item["price"] <= 10 for item in results)


def test_suggest_outfit_handles_empty_wardrobe(monkeypatch):
    _mock_groq(monkeypatch)
    listing = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    suggestion = suggest_outfit(listing, get_empty_wardrobe())

    assert isinstance(suggestion, str)
    assert suggestion


def test_create_fit_card_handles_empty_outfit():
    listing = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    caption = create_fit_card("", listing)

    assert "Cannot create a fit card" in caption


def test_create_fit_card_returns_caption(monkeypatch):
    _mock_groq(monkeypatch)
    listing = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    caption = create_fit_card("Pair it with baggy jeans and combat boots.", listing)

    assert caption == "Mocked FitFindr response with specific styling advice."


def test_agent_stops_after_no_results(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Downstream tools should not run after empty search results.")

    monkeypatch.setattr("agent.suggest_outfit", fail_if_called)
    monkeypatch.setattr("agent.create_fit_card", fail_if_called)

    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())

    assert session["error"]
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
