from pathlib import Path

from crowe_browse.search import SEARCH_URL, parse_results

FIX = Path(__file__).parent / "fixtures"


def test_search_url_is_ddg_html_endpoint():
    url = SEARCH_URL.format(q="blue+oyster")
    assert url.startswith("https://html.duckduckgo.com/html/")
    assert "blue+oyster" in url


def test_parse_results_extracts_title_url_snippet():
    results = parse_results((FIX / "ddg_results.html").read_text())
    assert len(results) == 2
    assert results[0]["title"] == "Oyster Cultivation"
    assert results[0]["url"] == "https://example.com/oyster"
    assert "15-21C" in results[0]["snippet"]
    assert results[1]["url"] == "https://example.org/temps"
