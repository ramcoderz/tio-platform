"""
Web scraper — Deterministic BFS engine using httpx and BeautifulSoup.
Domain detection uses multi-signal scoring: keyword frequency + URL signals + host hints.
"""

import asyncio
import re
import logging
import time
from urllib.parse import urlparse

import trafilatura

logger = logging.getLogger(__name__)
from backend.utils.console import console


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

# Minimum score to assign a domain (below this -> "general")
DOMAIN_THRESHOLD = 4


import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit

class Scraper:
    def __init__(self):
        self.ignored_patterns = [
            r"/privacy", r"/cookies", r"/terms", r"/legal",
            r"/track", r"/login", r"/signup", r"/logout",
            r"/license", r"/disclaimer", r"/copyright",
            r"/cart", r"/checkout", r"/account", r"/search",
        ]
        self.priority_keywords = [
            "about", "services", "faq", "docs", "products",
            "courses", "departments", "support", "attractions",
            "pricing", "features", "api", "admission",
        ]
        self.max_pages = 30
        self.max_depth = 1
        self.request_timeout = 15.0
        self.max_crawl_time = 90.0

    def _normalize_url(self, url: str) -> str:
        """Aggressive normalization to prevent duplicate crawls and loops."""
        try:
            parsed = urlsplit(url)
            # Lowercase domain, strip fragments and trailing slashes
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip('/')
            if not path: path = ''
            
            # Reconstruct without fragments or noisy query params
            return f"{parsed.scheme}://{netloc}{path}"
        except:
            return url

    async def extract_content(self, url: str) -> str:
        """Extract semantic content using httpx + Trafilatura/BS4."""
        _UNICODE_SANITIZE = {
            "\u2192": "->", "\u2190": "<-", "\u2013": "-", "\u2014": "--",
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2022": "*", "\u00a0": " ", "\u2026": "...", "\u00ae": "(R)",
            "\u2122": "(TM)", "\u00b0": " deg ", "\u00b7": "*",
        }

        def _sanitize(text: str) -> str:
            for char, rep in _UNICODE_SANITIZE.items():
                text = text.replace(char, rep)
            return text.encode("utf-8", errors="replace").decode("utf-8")

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "TiO-Crawler/1.0"})
                resp.raise_for_status()
                html = resp.text

            # Use Trafilatura for core extraction
            content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                output_format="txt",
            )
            
            if not content or len(content.split()) < 30:
                console.warning(f"Empty or low-content page skipped: {url}", stage="EXTRACTING")
                soup = BeautifulSoup(html, "html.parser")
                for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    s.decompose()
                content = soup.get_text(separator="\n", strip=True)
                
            return _sanitize(content or "")
        except asyncio.TimeoutError:
            console.error(f"Extraction timeout: {url}", stage="EXTRACTING")
            return ""
        except Exception as e:
            if "404" in str(e):
                console.warning(f"Page not found (404): {url}", stage="EXTRACTING")
            elif "403" in str(e):
                console.warning(f"Access blocked (403): {url}", stage="EXTRACTING")
            else:
                console.error(f"Extraction failure: {e} | {url}", stage="EXTRACTING")
            return ""

    async def discover_assets(
        self, base_url: str, limit: int = 30, depth: int = 1, allow_external: bool = False
    ) -> tuple[list[str], list[str]]:
        """
        DETERMINISTIC BFS Crawler — httpx-based, Playwright disabled for stability.
        Guaranteed to terminate via hard limits and timeouts.
        """
        start_time = time.monotonic()
        root_domain = urlparse(base_url).netloc.lower()
        
        discovered_pages: set[str] = {self._normalize_url(base_url)}
        discovered_docs: set[str] = set()
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(self._normalize_url(base_url), 0)]
        
        doc_extensions = {".pdf", ".docx", ".txt", ".md"}
        
        logger.info(f"[CRAWL] Starting stable BFS discovery for {base_url} (Limit={limit}, Depth={depth})")

        async with httpx.AsyncClient(timeout=self.request_timeout, follow_redirects=True) as client:
            while queue and len(discovered_pages) < limit:
                # 1. Hard limits check
                if time.monotonic() - start_time > self.max_crawl_time:
                    logger.warning(f"[CRAWL] Timeout reached ({self.max_crawl_time}s). Terminating.")
                    break

                current_url, current_depth = queue.pop(0)
                if current_url in visited or current_depth > depth:
                    continue
                
                visited.add(current_url)
                # console.info(f"Visiting {len(visited)}: {current_url}", stage="CRAWLING")

                try:
                    resp = await client.get(current_url, headers={"User-Agent": "TiO-Crawler/1.0"})
                    if resp.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = [a.get("href") for a in soup.find_all("a", href=True)]
                    
                    for link in links:
                        # Resolve relative URLs
                        absolute_url = urljoin(current_url, link)
                        norm_url = self._normalize_url(absolute_url)
                        parsed = urlparse(norm_url)
                        
                        # Boundary checks
                        if not allow_external and parsed.netloc.lower() != root_domain:
                            # console.info(f"External URL skipped: {norm_url}", stage="CRAWLING")
                            continue
                        
                        path_lower = parsed.path.lower()
                        
                        # Document check
                        if any(path_lower.endswith(ext) for ext in doc_extensions):
                            discovered_docs.add(norm_url)
                            continue

                        # Noise check
                        if any(re.search(pat, norm_url.lower()) for pat in self.ignored_patterns):
                            continue
                        
                        # Media check
                        if any(path_lower.endswith(ext) for ext in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".exe"}):
                            continue

                        if norm_url not in discovered_pages:
                            discovered_pages.add(norm_url)
                            if current_depth + 1 <= depth:
                                queue.append((norm_url, current_depth + 1))
                            
                            if len(discovered_pages) >= limit:
                                break
                        else:
                            # console.warning(f"Duplicate URL skipped: {norm_url}", stage="CRAWLING")
                            pass

                except asyncio.TimeoutError:
                    console.warning(f"Request timeout: {current_url}", stage="CRAWLING")
                    continue
                except Exception as e:
                    console.error(f"Crawl error: {e} | {current_url}", stage="CRAWLING")
                    continue

        # Final ranking and result selection
        page_scorer = self._score_url(base_url)
        sorted_pages = sorted(list(discovered_pages), key=page_scorer, reverse=True)[:limit]
        sorted_docs = sorted(list(discovered_docs), key=lambda x: page_scorer(x) + 10, reverse=True)[:limit]
        
        logger.info(f"[CRAWL] Discovery Complete. Pages={len(sorted_pages)}, Docs={len(sorted_docs)}")
        return sorted_pages, sorted_docs

    def _score_url(self, base_url: str, is_doc: bool = False):
        """Scoring function for URL prioritisation."""
        priority_map = {
            "dept": 20, "department": 25, "faculty": 20, "course": 15,
            "admission": 20, "docs": 20, "brochure": 25, "manual": 25,
            "policy": 20, "faq": 15, "handbook": 25, "guide": 25,
            "attraction": 20, "api": 20, "product": 15, "service": 15,
            "pricing": 20, "features": 15, "documentation": 20,
        }

        def scorer(url: str) -> int:
            s = 10 if is_doc else 0
            url_lower = url.lower()
            
            # High priority for home page
            if url == base_url or url == base_url + "/":
                return 1000
                
            # Bonus for keywords in path
            for kw, val in priority_map.items():
                if kw in url_lower:
                    s += val
            
            # Bonus for shallow depth
            s -= url_lower.count("/") * 5
            
            # Penalize noise keywords that weren't caught by filter
            if any(k in url_lower for k in ["login", "signup", "register", "cart"]):
                s -= 50
                
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

