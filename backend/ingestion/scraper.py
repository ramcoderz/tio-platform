"""
Web scraper — Trafilatura-first with Playwright fallback.
Domain detection uses multi-signal scoring: keyword frequency + URL signals + metadata.
"""

import asyncio
import re
import logging
from urllib.parse import urlparse

import trafilatura

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain keyword indicators (from product spec)
# ---------------------------------------------------------------------------
DOMAIN_INDICATORS: dict[str, list[str]] = {
    "education": [
        "admissions", "admission", "faculty", "course", "courses",
        "department", "departments", "semester", "placement", "placements",
        "curriculum", "syllabus", "university", "college", "school",
        "student", "academic", "scholarship", "degree", "campus",
        "enrollment", "tuition", "lecture", "professor", "research",
    ],
    "medical": [
        "appointment", "appointments", "doctor", "doctors", "insurance",
        "department", "departments", "patient", "patients", "clinic",
        "hospital", "health", "treatment", "symptoms", "symptom",
        "surgery", "pharmacy", "prescription", "diagnosis", "emergency",
        "ward", "specialist", "consultation", "nursing", "therapy",
    ],
    "tourism": [
        "attractions", "attraction", "itinerary", "destination", "destinations",
        "rides", "ride", "events", "event", "hotel", "hotels", "resort",
        "travel", "tourism", "tour", "visiting", "experience", "sightseeing",
        "booking", "packages", "accommodation", "vacation", "leisure",
    ],
    "developer": [
        "api", "sdk", "integrations", "integration", "authentication",
        "webhooks", "webhook", "endpoint", "endpoints", "documentation",
        "docs", "developer", "library", "library", "rest", "graphql",
        "oauth", "token", "rate limit", "changelog", "reference",
    ],
    "ecommerce": [
        "products", "product", "pricing", "price", "catalog", "catalogue",
        "orders", "order", "shipping", "cart", "checkout", "buy",
        "purchase", "shop", "store", "discount", "refund", "returns",
        "inventory", "sku", "review", "wishlist",
    ],
}

# URL path keywords that boost specific domains
URL_DOMAIN_BOOSTS: dict[str, list[str]] = {
    "education": ["/courses", "/admission", "/faculty", "/departments", "/academics", "/student"],
    "medical":   ["/appointments", "/doctors", "/departments", "/patient", "/health"],
    "tourism":   ["/attractions", "/itinerary", "/destinations", "/events", "/tours"],
    "developer": ["/api", "/docs", "/sdk", "/developer", "/reference", "/webhooks"],
    "ecommerce": ["/products", "/catalog", "/shop", "/cart", "/pricing", "/orders"],
}

# Minimum score to assign a domain (below this → "general")
DOMAIN_THRESHOLD = 4


class Scraper:
    def __init__(self):
        self.ignored_patterns = [
            r"/privacy", r"/cookies", r"/terms", r"/legal",
            r"/track", r"/login", r"/signup", r"/logout",
        ]
        self.priority_keywords = [
            "about", "services", "faq", "docs", "products",
            "courses", "departments", "support", "attractions",
        ]

    # -----------------------------------------------------------------------
    # Content extraction
    # -----------------------------------------------------------------------

    async def extract_content(self, url: str) -> str:
        """Extract semantic content from a URL using Trafilatura."""
        try:
            downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
            if not downloaded:
                downloaded = await self._fetch_with_playwright(url)
            content = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            return content or ""
        except Exception as e:
            logger.warning(f"[SCRAPER] extract_content error for {url}: {e}")
            return ""

    async def _fetch_with_playwright(self, url: str) -> str:
        """Playwright fallback for JS-rendered pages."""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            logger.warning(f"[SCRAPER] Playwright fallback failed for {url}: {e}")
            return ""

    # -----------------------------------------------------------------------
    # Asset discovery
    # -----------------------------------------------------------------------

    async def discover_assets(
        self, base_url: str, limit: int = 20, depth: int = 1
    ) -> tuple[list[str], list[str]]:
        """
        Crawl the website up to `depth` levels deep.
        Returns (page_urls, document_urls).
        Max pages/docs is capped at `limit`.
        """
        domain = urlparse(base_url).netloc
        discovered_pages: set[str] = {base_url}
        discovered_docs: set[str] = set()
        to_visit: list[tuple[str, int]] = [(base_url, 0)]
        visited: set[str] = set()
        doc_extensions = {".pdf", ".docx", ".txt", ".md"}

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                while to_visit and len(discovered_pages) + len(discovered_docs) < limit * 5:
                    current_url, current_depth = to_visit.pop(0)
                    if current_url in visited or current_depth > depth:
                        continue

                    visited.add(current_url)
                    try:
                        await page.goto(current_url, wait_until="domcontentloaded", timeout=15_000)
                        links = await page.eval_on_selector_all(
                            "a[href]", "elements => elements.map(e => e.href)"
                        )
                        for link in links:
                            parsed = urlparse(link)
                            if parsed.netloc != domain:
                                continue

                            clean_link = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                            if clean_link.endswith("/"):
                                clean_link = clean_link[:-1]

                            path_lower = parsed.path.lower()

                            # Document?
                            if any(path_lower.endswith(ext) for ext in doc_extensions):
                                discovered_docs.add(clean_link)
                                continue

                            # Skip binaries
                            if any(path_lower.endswith(ext) for ext in {
                                ".exe", ".zip", ".rar", ".msi", ".js", ".css",
                                ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                            }):
                                continue

                            # Skip noise patterns
                            if any(re.search(pat, clean_link.lower()) for pat in self.ignored_patterns):
                                continue

                            if clean_link not in discovered_pages:
                                discovered_pages.add(clean_link)
                                if current_depth + 1 <= depth:
                                    to_visit.append((clean_link, current_depth + 1))

                        if len(discovered_pages) + len(discovered_docs) >= limit * 5:
                            break
                    except Exception as e:
                        logger.debug(f"[SCRAPER] Error visiting {current_url}: {e}")

                await browser.close()
        except Exception as e:
            logger.warning(f"[SCRAPER] discover_assets error for {base_url}: {e}")

        sorted_pages = sorted(discovered_pages, key=self._score_url(base_url), reverse=True)[:limit]
        sorted_docs = sorted(discovered_docs, key=self._score_url(base_url, is_doc=True), reverse=True)[:limit]
        return sorted_pages, sorted_docs

    def _score_url(self, base_url: str, is_doc: bool = False):
        """Scoring function for URL prioritisation."""
        priority_map = {
            "dept": 20, "department": 25, "faculty": 20, "course": 15,
            "admission": 20, "docs": 20, "brochure": 25, "manual": 25,
            "policy": 20, "faq": 15, "handbook": 25, "guide": 25,
            "attraction": 20, "api": 20, "product": 15, "service": 15,
        }

        def scorer(url: str) -> int:
            s = 10 if is_doc else 0
            url_lower = url.lower()
            for kw, val in priority_map.items():
                if kw in url_lower:
                    s += val
            if url == base_url:
                s += 100
            s -= url_lower.count("/") * 2
            return s

        return scorer

    # -----------------------------------------------------------------------
    # Domain detection
    # -----------------------------------------------------------------------

    def detect_domain(self, text: str, url: str) -> str:
        """
        Multi-signal domain classification:
          1. Keyword frequency in scraped text (main signal)
          2. URL path keyword boosts
          3. Domain name hints from the URL host

        Returns one of: education | medical | tourism | developer | ecommerce | general
        """
        text_lower = text.lower()
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        path = parsed.path

        scores: dict[str, float] = {d: 0.0 for d in DOMAIN_INDICATORS}

        # Signal 1: keyword frequency in text (with diminishing returns)
        for domain, keywords in DOMAIN_INDICATORS.items():
            for kw in keywords:
                count = text_lower.count(kw)
                if count > 0:
                    scores[domain] += min(count, 5)  # cap at 5 per keyword

        # Signal 2: URL path boosts (strong signal)
        for domain, paths in URL_DOMAIN_BOOSTS.items():
            for p in paths:
                if p in path:
                    scores[domain] += 15

        # Signal 3: domain name hints in host
        host = parsed.netloc.lower()
        host_hints = {
            "education": [".edu", "university", "college", "school", "academy", "institute"],
            "medical":   [".health", "hospital", "clinic", "medical", "health"],
            "tourism":   ["travel", "tour", "tourism", "resort", "hotel", "visit"],
            "developer": ["dev.", "api.", "docs.", "developer.", "developers."],
            "ecommerce": ["shop.", "store.", "buy.", "cart.", "market."],
        }
        for domain, hints in host_hints.items():
            for hint in hints:
                if hint in host:
                    scores[domain] += 20

        logger.info(f"[DOMAIN DETECTION] Scores: {scores} for {url}")

        best = max(scores, key=scores.get)
        if scores[best] < DOMAIN_THRESHOLD:
            return "general"
        return best


scraper = Scraper()
