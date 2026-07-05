from pathlib import Path

from crowe_browse.extract import Element, interactive_elements, readable_text

FIX = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text()


def test_readable_text_keeps_article_drops_boilerplate():
    text = readable_text(_read("article.html"))
    assert "Blue oyster fruits at 15 to 21 C." in text
    assert "Keep humidity near 85 percent." in text
    assert "console.log" not in text  # script dropped
    assert "copyright" not in text  # footer dropped


def test_interactive_elements_enumerates_in_order():
    els = interactive_elements(_read("form.html"))
    assert [e.tag for e in els] == ["a", "input", "button"]
    assert els[0].ref == 0 and els[1].ref == 1 and els[2].ref == 2
    assert els[0].role == "link" and els[0].name == "First Link"
    assert els[1].role == "textbox" and "Search here" in els[1].name
    assert els[2].role == "button" and els[2].name == "Go"


def test_readable_text_drops_page_title():
    text = readable_text(_read("article.html"))
    assert "Oyster Guide" not in text  # the page <title> is metadata, not body text
    assert "Blue oyster fruits at 15 to 21 C." in text  # real content still present
