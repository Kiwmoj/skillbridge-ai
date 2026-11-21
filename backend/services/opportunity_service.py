"""Search live web results; never synthesize institution or deadline data."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import requests


class OpportunitySearch:
    def __init__(self, api_key: str, http=requests):
        self.api_key = api_key
        self.http = http

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, career: str = "", category: str = "other", location: str = "",
               education_level: str = "", limit: int = 10) -> list[dict]:
        if not self.enabled:
            raise RuntimeError("Live opportunity search is not configured on this SkillBridge service.")
        terms = [query, career, category.replace("_", " "), location, education_level]
        search_query = " ".join(part.strip() for part in terms if part.strip())
        response = self.http.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            params={"q": search_query, "count": limit}, timeout=20,
        )
        if response.status_code in {401, 403}:
            raise RuntimeError("The live search service rejected its server credential.")
        response.raise_for_status()
        payload = response.json()
        timestamp = datetime.now(timezone.utc).isoformat()
        results = []
        for item in payload.get("web", {}).get("results", []):
            url = item.get("url", "")
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                continue
            results.append({
                "title": str(item.get("title") or "Untitled search result")[:300],
                "source_url": url[:2048],
                "source_name": parsed.hostname or "Web result",
                "snippet": str(item.get("description") or "")[:2000],
                "category": category,
                "location": location or "Not listed by the search result",
                "deadline": "Not verified; check the source.",
                "eligibility": "Not verified; check the source.",
                "retrieved_at": timestamp,
                "verification": "Search result; details are not independently verified.",
            })
        return results[:limit]
