"""Web search and page extraction."""

from __future__ import annotations

from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import httpx

from evoresearcher.schemas import SourceNote


class WebResearcher:
    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                )
            },
            follow_redirects=True,
        )

    def search(self, query: str, limit: int = 3) -> list[SourceNote]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        response = self.client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SourceNote] = []
        for block in soup.select(".result")[:limit]:
            title_node = block.select_one(".result__title")
            link_node = block.select_one(".result__url")
            snippet_node = block.select_one(".result__snippet")
            if title_node is None or link_node is None:
                continue
            href = block.select_one(".result__title a")
            url_value = href.get("href", "").strip() if href else ""
            if not url_value.startswith("http"):
                continue
            results.append(
                SourceNote(
                    title=title_node.get_text(" ", strip=True),
                    url=url_value,
                    snippet="" if snippet_node is None else snippet_node.get_text(" ", strip=True),
                )
            )
        return results

    def enrich(self, source: SourceNote, char_limit: int = 1600) -> SourceNote:
        try:
            response = self.client.get(source.url)
            response.raise_for_status()
        except Exception:
            return source
        soup = BeautifulSoup(response.text, "html.parser")
        for bad in soup(["script", "style", "noscript"]):
            bad.extract()
        text = " ".join(soup.get_text(" ", strip=True).split())
        return source.model_copy(update={"excerpt": text[:char_limit]})
