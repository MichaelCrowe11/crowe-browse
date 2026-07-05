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


def test_parse_results_unwraps_ddg_redirect():
    html = (
        '<div class="result">'
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.net%2Fpage&amp;rut=abc">Redirected</a>'
        '<a class="result__snippet">via redirect</a>'
        '</div>'
    )
    results = parse_results(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.net/page"
    assert results[0]["title"] == "Redirected"
