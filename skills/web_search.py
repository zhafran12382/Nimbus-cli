"""
NimbusCLI - Web Search Skill
Searches the web using DuckDuckGo (free) or Tavily (API key required).
"""

import os
from skills.base import BaseSkill


class WebSearch(BaseSkill):
    name = "web_search"
    description = (
        "Search the web for current information. Use this when you need up-to-date facts, "
        "recent news, documentation, or any information you don't already know. "
        "Returns search results with titles, snippets, and URLs."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return. Default: 5.",
                },
            },
            "required": ["query"],
        }

    def execute(self, query: str, max_results: int = 5) -> str:
        tavily_key = os.environ.get("TAVILY_API_KEY", "")

        if tavily_key:
            return self._search_tavily(query, max_results, tavily_key)
        else:
            return self._search_duckduckgo(query, max_results)

    def _search_tavily(self, query: str, max_results: int, api_key: str) -> str:
        """Search using Tavily API for higher quality results."""
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            response = client.search(query=query, max_results=max_results)

            results = []
            for i, item in enumerate(response.get("results", []), 1):
                title = item.get("title", "No Title")
                url = item.get("url", "")
                content = item.get("content", "")[:300]
                results.append(f"[{i}] {title}\n    URL: {url}\n    {content}")

            if not results:
                return f"No results found for: {query}"

            header = f"[Tavily Search] Results for: {query}\n{'='*50}\n"
            return header + "\n\n".join(results)

        except ImportError:
            return "[ERROR] tavily-python not installed. Falling back to DuckDuckGo.\n" + self._search_duckduckgo(query, max_results)
        except Exception as e:
            return f"[Tavily Error] {str(e)}. Falling back to DuckDuckGo.\n" + self._search_duckduckgo(query, max_results)

    def _search_duckduckgo(self, query: str, max_results: int) -> str:
        """Search using DuckDuckGo (free, no API key needed)."""
        try:
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results), 1):
                    title = r.get("title", "No Title")
                    url = r.get("href", "")
                    body = r.get("body", "")[:300]
                    results.append(f"[{i}] {title}\n    URL: {url}\n    {body}")

            if not results:
                return f"No results found for: {query}"

            header = f"[DuckDuckGo Search] Results for: {query}\n{'='*50}\n"
            return header + "\n\n".join(results)

        except ImportError:
            return "[ERROR] duckduckgo-search not installed. Run: pip install duckduckgo-search"
        except Exception as e:
            return f"[Search Error] {type(e).__name__}: {str(e)}"
