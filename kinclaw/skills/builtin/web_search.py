"""Web search skill via httpx (DuckDuckGo Instant Answer API)."""
from __future__ import annotations

import httpx
from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web and return results."

    async def execute(self, query: str = "", max_results: int = 5) -> dict:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
            results = []
            for r in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in r:
                    results.append({"text": r["Text"], "url": r.get("FirstURL", "")})
            return {"results": results, "abstract": data.get("Abstract", "")}
        except Exception as e:
            logger.error("Web search error: {}", e)
            return {"error": str(e), "results": []}
