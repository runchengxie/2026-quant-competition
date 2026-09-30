from html.parser import HTMLParser
from pathlib import Path


SITE_DIST = Path(__file__).resolve().parents[1] / "site" / "dist"
BASE_PATH = "/2026-quant-competition"


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.language = None
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang")
        if tag in {"a", "link"} and "href" in attributes:
            self.hrefs.append(attributes["href"])


def test_astro_build_contains_english_and_simplified_chinese_routes():
    english_path = SITE_DIST / "index.html"
    chinese_path = SITE_DIST / "zh-CN" / "index.html"
    assert english_path.is_file(), "Build the Astro site before running this test"
    assert chinese_path.is_file(), "Simplified Chinese route is missing from the build"

    english = english_path.read_text(encoding="utf-8")
    chinese = chinese_path.read_text(encoding="utf-8")
    english_page = PageLinks()
    chinese_page = PageLinks()
    english_page.feed(english)
    chinese_page.feed(chinese)

    assert english_page.language == "en"
    assert chinese_page.language == "zh-CN"
    assert "From strategy research to auditable execution." in english
    assert "从策略研究到可审计执行。" in chinese
    assert f"{BASE_PATH}/zh-CN/" in english_page.hrefs
    assert f"{BASE_PATH}/" in chinese_page.hrefs
    assert any(
        href.startswith(f"{BASE_PATH}/_astro/") and href.endswith(".css")
        for href in english_page.hrefs
    )
