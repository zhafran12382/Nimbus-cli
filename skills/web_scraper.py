"""
NimbusCLI - Web Scraper Skill
Extracts text content from web pages.
"""

import requests
from skills.base import BaseSkill


class WebScraper(BaseSkill):
    name = "scrape_url"
    description = (
        "Scrape and extract the main text content from a web page URL. "
        "Use this when you need to read the full content of a webpage, article, "
        "documentation page, or any URL. Returns clean text, stripped of HTML."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the web page to scrape.",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters to return. Default: 5000.",
                },
            },
            "required": ["url"],
        }

    def execute(self, url: str, max_length: int = 5000) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            }

            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()

            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")

                # Remove script and style elements
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                # Try to find main content
                main = (
                    soup.find("main")
                    or soup.find("article")
                    or soup.find("div", {"class": "content"})
                    or soup.find("div", {"id": "content"})
                    or soup.body
                )

                if main:
                    text = main.get_text(separator="\n", strip=True)
                else:
                    text = soup.get_text(separator="\n", strip=True)

            except ImportError:
                # Fallback: basic text extraction without BeautifulSoup
                import re
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text).strip()

            # Clean up excessive blank lines
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)

            if len(text) > max_length:
                text = text[:max_length] + "\n\n[... truncated]"

            return f"[Scraped: {url}]\n{'='*50}\n{text}"

        except requests.exceptions.Timeout:
            return f"[ERROR] Request timed out for URL: {url}"
        except requests.exceptions.RequestException as e:
            return f"[ERROR] Failed to fetch URL: {str(e)}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {str(e)}"
