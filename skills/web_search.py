"""
NimbusCLI - Web Search Skill
Searches the web using Tavily API via direct HTTP requests.
"""

import os
import requests
from skills.base import BaseSkill


class WebSearch(BaseSkill):
    name = "web_search"
    REQUEST_TIMEOUT_SECONDS = 30
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
        if not tavily_key:
            return "[ERROR] TAVILY_API_KEY is not set. Please configure your Tavily API key."
        return self._search_tavily(query, max_results, tavily_key)

    def _search_tavily(self, query: str, max_results: int, api_key: str) -> str:
        """Search using Tavily API via direct HTTP request."""
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                },
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for i, item in enumerate(data.get("results", []), 1):
                title = item.get("title", "No Title")
                url = item.get("url", "")
                content = item.get("content", "")[:300]
                results.append(f"[{i}] {title}\n    URL: {url}\n    {content}")

            if not results:
                return f"No results found for: {query}"

            header = f"[Tavily Search] Results for: {query}\n{'='*50}\n"
            return header + "\n\n".join(results)

        except requests.RequestException as e:
            return f"[Tavily Error] Request failed: {type(e).__name__}: {str(e)}"
        except Exception as e:
            return f"[Search Error] {type(e).__name__}: {str(e)}"
