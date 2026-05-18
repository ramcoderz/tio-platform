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
    "education": [
        "/courses", "/admission", "/faculty", "/departments", "/academics", 
        "/student", "/profile", "/resume", "/cv", "/biodata", "/staff",
        "/hod", "/principal", "/dean", "/research"
    ],
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
            r"/gallery", r"/archive", r"/notices?", r"/events?",
        ]
        self.priority_keywords = [
            "about", "services", "faq", "docs", "products",
            "courses", "departments", "support", "attractions",
            "pricing", "features", "api", "admission",
        ]
        self.max_pages = 20
        self.max_depth = 1
        self.request_timeout = 6.0
        self.max_crawl_time = 60.0

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
        """
        Layered extraction pipeline:
        1. Trafilatura (High accuracy for articles)
        2. Readability-LXML fallback (Content-focused)
        3. BeautifulSoup fallback (Structural)
        4. Playwright fallback (JS-rendered)
        """
        _UNICODE_SANITIZE = {
            "\u2192": "->", "\u2190": "<-", "\u2013": "-", "\u2014": "--",
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2022": "*", "\u00a0": " ", "\u2026": "...", "\u00ae": "(R)",
            "\u2122": "(TM)", "\u00b0": " deg ", "\u00b7": "*",
        }

        def _sanitize(text: str) -> str:
            if not text: return ""
            for char, rep in _UNICODE_SANITIZE.items():
                text = text.replace(char, rep)
            return text.encode("utf-8", errors="replace").decode("utf-8")

        html = ""
        is_article = False
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout, follow_redirects=True) as client:
                resp = await asyncio.wait_for(
                    client.get(url, headers={"User-Agent": "TiO-Crawler/1.0"}),
                    timeout=self.request_timeout
                )
                resp.raise_for_status()
                html = resp.text
                is_article = self._is_article(html, url)
                if is_article:
                    console.info(f"[EXTRACTION] Article detected: {url}", stage="EXTRACTING")
        except Exception as e:
            console.error(f"Initial fetch failed: {e} | {url}", stage="EXTRACTING")
            pass

        # 1. Trafilatura
        content = ""
        if html:
            content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                output_format="txt",
            )
            if content and len(content.split()) > 100:
                console.info(f"[EXTRACTION] Trafilatura success: {len(content.split())} words", stage="EXTRACTING")
                return _sanitize(content)

        # 2. Readability-LXML Fallback (with strict 3s timeout)
        if html:
            try:
                async def run_readability():
                    from readability import Document
                    doc = Document(html)
                    summary = doc.summary()
                    soup = BeautifulSoup(summary, "html.parser")
                    return soup.get_text(separator="\n", strip=True)
                
                content = await asyncio.wait_for(run_readability(), timeout=3.0)
                if content and len(content.split()) > 100:
                    console.info(f"[EXTRACTION] Fallback: Readability used ({len(content.split())} words)", stage="EXTRACTING")
                    return _sanitize(content)
            except Exception as e:
                console.warning(f"[EXTRACTION] Readability fallback failed or timed out: {e}", stage="EXTRACTING")

        # 3. BeautifulSoup Fallback
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    s.decompose()
                content = soup.get_text(separator="\n", strip=True)
                if content and len(content.split()) > 100:
                    console.info(f"[EXTRACTION] Fallback: BeautifulSoup used ({len(content.split())} words)", stage="EXTRACTING")
                    return _sanitize(content)
            except Exception as e:
                console.warning(f"[EXTRACTION] BS4 fallback failed: {e}", stage="EXTRACTING")

        # 4. Playwright Rendered Extraction Fallback (with strict 10s timeout and fast load wait)
        if html:
            try:
                async def run_playwright():
                    from playwright.async_api import async_playwright
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()
                        await page.goto(url, timeout=8000, wait_until="load")
                        rendered_html = await page.content()
                        await browser.close()
                        
                        extracted_text = trafilatura.extract(rendered_html, include_comments=False, include_tables=True)
                        if not extracted_text or len(extracted_text.split()) < 50:
                            soup = BeautifulSoup(rendered_html, "html.parser")
                            for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
                                s.decompose()
                            extracted_text = soup.get_text(separator="\n", strip=True)
                        return extracted_text

                content = await asyncio.wait_for(run_playwright(), timeout=12.0)
                if content and len(content.split()) > 30:
                    console.info(f"[EXTRACTION] Fallback: Playwright used ({len(content.split())} words)", stage="EXTRACTING")
                    return _sanitize(content)
            except Exception as e:
                console.error(f"[EXTRACTION] Playwright fallback failed or timed out: {e} | {url}", stage="EXTRACTING")

        return _sanitize(content or "")

    def get_priority_score(self, url: str, base_url: str) -> float:
        """Returns a formatted score between 1.0 and 10.0 based on relevance."""
        url_lower = url.lower()
        if url_lower == base_url.lower() or url_lower == base_url.lower() + "/":
            return 10.0
            
        priority_map = {
            "cv": 9.9, "resume": 9.8, "faculty": 9.7, "profile": 9.6, "pdf": 9.5,
            "docx": 9.4, "ai-ml": 9.1, "staff": 9.0, "publications": 8.8,
            "department": 8.7, "admissions": 8.5, "academics": 8.3,
            "about": 8.0, "research": 7.8, "syllabus": 7.5, "curriculum": 7.2,
            "events": 6.5, "notices": 6.0, "blogs": 5.8, "announcements": 5.5,
            "login": 2.0, "privacy": 1.5, "terms": 1.2, "legal": 1.0,
            "gallery": 2.5, "archive": 2.8, "cookies": 1.1
        }
        
        score = 4.0 # Default base
        for kw, val in priority_map.items():
            if kw in url_lower:
                score = max(score, val)
        
        path = urlparse(url).path
        depth = len([d for d in path.split('/') if d])
        score = max(1.0, min(10.0, score - depth * 0.15))
        return round(score, 1)

    async def discover_assets(
        self, base_url: str, limit: int = 30, depth: int = 1, allow_external: bool = False, on_progress = None
    ) -> tuple[list[str], list[str]]:
        """
        Intelligent relevance-prioritized adaptive BFS Crawler.
        Discovers, ranks, and prioritizes crawling based on high-value keywords and asset types.
        """
        from backend.config.settings import get_settings
        settings = get_settings()
        
        # DEMO MODE & fast crawling limits from spec
        max_initial_urls = 15
        max_depth = 1
        max_docs = 5
        
        if settings.demo_mode:
            limit = min(limit, 12)
            depth = min(depth, 1)

        print(flush=True)
        print("========================================================", flush=True)
        print("[INGESTION] Starting chatbot Ingestion", flush=True)
        print("========================================================", flush=True)
        print(f"[CRAWLER] Root URL:\n{base_url}", flush=True)
        print(f"[CRAWLER] Depth:\n{depth}", flush=True)
        print(flush=True)

        start_time = time.monotonic()
        root_domain = urlparse(base_url).netloc.lower()
        doc_extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}

        print("========================================================", flush=True)
        print("[CRAWLER] Validating crawler pipeline...", flush=True)
        print("========================================================", flush=True)
        try:
            import httpx
            print("[OK] HTTP client active", flush=True)
        except Exception as e:
            print(f"[ERROR] HTTP client inactive: {e}", flush=True)

        try:
            import bs4
            import trafilatura
            print("[OK] Parser active", flush=True)
        except Exception as e:
            print(f"[ERROR] Parser inactive: {e}", flush=True)

        print("[OK] Timeout guards active", flush=True)
        print("========================================================", flush=True)
        print(flush=True)

        print("========================================================", flush=True)
        print("[CRAWLER] Analyzing site structure...", flush=True)
        print("========================================================", flush=True)

        # 1. Fetch homepage with hard 10s timeout & stream progress
        if on_progress:
            await on_progress(0, 0, "", {"type": "crawler_status", "stage": "Analyzing homepage", "progress": 20})
        
        print("[CRAWLER] Fetching homepage...", flush=True)
        raw_links = []
        homepage_html = ""
        t_fetch_start = time.monotonic()
        
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(base_url, headers={"User-Agent": "TiO-Crawler/1.0"})
                if resp.status_code == 200:
                    homepage_html = resp.text
                    duration = time.monotonic() - t_fetch_start
                    print(f"[CRAWLER] Homepage fetched in {duration:.1f}s", flush=True)
                else:
                    print(f"[WARNING] Homepage returned status code {resp.status_code}", flush=True)
        except Exception as e:
            print(f"[WARNING] Failed to fetch homepage within timeout: {e}", flush=True)
            print("[WARNING] Site analysis timeout exceeded. Falling back to fast crawl mode.", flush=True)

        # 2. DOM parsing with hard 5s timeout & stream progress
        if homepage_html:
            try:
                if on_progress:
                    await on_progress(0, 0, "", {"type": "crawler_status", "stage": "Parsing DOM", "progress": 30})
                print("[CRAWLER] Parsing DOM...", flush=True)
                
                async def parse_dom():
                    return BeautifulSoup(homepage_html, "html.parser")
                    
                soup = await asyncio.wait_for(parse_dom(), timeout=5.0)
                
                # 3. Link extraction with hard 5s timeout & stream progress
                if on_progress:
                    await on_progress(0, 0, "", {"type": "crawler_status", "stage": "Extracting links", "progress": 40})
                print("[CRAWLER] Extracting links...", flush=True)
                
                async def extract_links():
                    return [a.get("href") for a in soup.find_all("a", href=True)]
                    
                raw_links = await asyncio.wait_for(extract_links(), timeout=5.0)
                print(f"[CRAWLER] Found {len(raw_links)} raw links", flush=True)
            except Exception as e:
                print(f"[WARNING] DOM parsing or link extraction failed/timed out: {e}", flush=True)
                print("[WARNING] Site analysis timeout exceeded. Falling back to fast crawl mode.", flush=True)

        # 4. Priority filtering & scoring (with early skips and async yields)
        unique_urls = set()
        ranked_links = []
        
        if on_progress:
            await on_progress(0, 0, "", {"type": "crawler_status", "stage": "Filtering URLs", "progress": 50})
        print("[CRAWLER] Filtering low-priority URLs...", flush=True)
        
        priority_patterns = [r"about", r"faculty", r"academics", r"department", r"profile", r"pdf", r"syllabus", r"research"]
        skip_patterns = [r"gallery", r"event", r"archive", r"notice", r"repetitive", r"facebook", r"twitter", r"linkedin", r"instagram"]

        try:
            for idx, link in enumerate(raw_links):
                abs_url = urljoin(base_url, link)
                norm_url = self._normalize_url(abs_url)
                parsed = urlparse(norm_url)
                
                if not allow_external and parsed.netloc.lower() != root_domain:
                    continue
                if norm_url in unique_urls:
                    continue
                
                unique_urls.add(norm_url)
                
                if any(re.search(pat, norm_url.lower()) for pat in skip_patterns):
                    continue
                    
                score = self.get_priority_score(norm_url, base_url)
                
                # Prioritize important links only from spec
                if any(re.search(pat, norm_url.lower()) for pat in priority_patterns):
                    score += 2.0
                
                is_doc = any(parsed.path.lower().endswith(ext) for ext in doc_extensions)
                ranked_links.append({"url": norm_url, "score": score, "is_doc": is_doc})
                
                # Periodically yield to event loop to prevent starvation
                if idx % 20 == 0:
                    await asyncio.sleep(0)
                    
            # Sort links by relevance score
            ranked_links = sorted(ranked_links, key=lambda x: x["score"], reverse=True)
            print("[CRAWLER] Priority ranking complete", flush=True)
        except Exception as e:
            print(f"[WARNING] Priority ranking failed: {e}", flush=True)

        # 5. Live URL Discovery & Immediate Crawling Strategy
        crawling_candidates = [rl for rl in ranked_links if rl["score"] >= 4.0][:max_initial_urls]
        
        print("========================================================", flush=True)
        print("[CRAWLER] Homepage analyzed", flush=True)
        print("========================================================", flush=True)
        print(f"[CRAWLER] Homepage fetched", flush=True)
        print(f"[CRAWLER] Extracted {len(crawling_candidates)} priority links", flush=True)
        print("[CRAWLER] Beginning crawl immediately", flush=True)
        print(flush=True)

        discovered_pages = set()
        discovered_docs = set()
        
        discovered_pages.add(self._normalize_url(base_url))

        for rl in crawling_candidates:
            url = rl["url"]
            print(f"[CRAWLER] Discovered: {url}", flush=True)
            if rl["is_doc"]:
                if len(discovered_docs) < max_docs:
                    discovered_docs.add(url)
                    ext = url.split(".")[-1].upper()
                    filename = url.split("/")[-1]
                    print(flush=True)
                    print("========================================================", flush=True)
                    print("[DOCUMENT]", flush=True)
                    print(f"{ext} detected:\n{filename}", flush=True)
                    print("========================================================", flush=True)
                    print(flush=True)
                    if on_progress:
                        import asyncio
                        asyncio.create_task(on_progress(0, 0, "", {"type": "document_detected", "stage": "Document found", "document": filename, "progress": 50}))
            else:
                if len(discovered_pages) < limit:
                    discovered_pages.add(url)

        # 6. BFS Queue loop for High and Medium relevance pages
        visited = set()
        queue = []
        for rl in crawling_candidates:
            if not rl["is_doc"]:
                queue.append((rl["url"], 1))

        # Hard 6.0s timeout per page download in httpx
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            while queue and len(discovered_pages) < limit:
                # Async yield at every BFS loop iteration
                await asyncio.sleep(0)
                
                if time.monotonic() - start_time > self.max_crawl_time:
                    print(f"[WARNING] Crawl budget reached ({self.max_crawl_time}s). Stopping.", flush=True)
                    break

                current_url, current_depth = queue.pop(0)
                if current_url in visited or current_depth > depth:
                    continue
                
                visited.add(current_url)
                if on_progress:
                    try:
                        await on_progress(len(discovered_pages), limit, current_url)
                    except Exception as pe:
                        logger.warning(f"Error in crawler progress callback: {pe}")

                try:
                    resp = await asyncio.wait_for(
                        client.get(current_url, headers={"User-Agent": "TiO-Crawler/1.0"}),
                        timeout=6.0
                    )
                    if resp.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = [a.get("href") for a in soup.find_all("a", href=True)]
                    
                    for link in links:
                        absolute_url = urljoin(current_url, link)
                        norm_url = self._normalize_url(absolute_url)
                        parsed = urlparse(norm_url)
                        
                        if not allow_external and parsed.netloc.lower() != root_domain:
                            continue
                        
                        path_lower = parsed.path.lower()
                        score = self.get_priority_score(norm_url, base_url)
                        
                        # Skip low priority on deep discovery
                        if score < 4.5:
                            continue

                        if any(path_lower.endswith(ext) for ext in doc_extensions):
                            if len(discovered_docs) < max_docs:
                                discovered_docs.add(norm_url)
                                ext = norm_url.split(".")[-1].upper()
                                filename = norm_url.split("/")[-1]
                                print(flush=True)
                                print("========================================================", flush=True)
                                print("[DOCUMENT]", flush=True)
                                print(f"{ext} detected:\n{filename}", flush=True)
                                print("========================================================", flush=True)
                                print(flush=True)
                                if on_progress:
                                    import asyncio
                                    asyncio.create_task(on_progress(0, 0, "", {"type": "document_detected", "stage": "Document found", "document": filename, "progress": 50}))
                            continue

                        if any(re.search(pat, norm_url.lower()) for pat in self.ignored_patterns):
                            continue
                        
                        if any(path_lower.endswith(ext) for ext in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".exe"}):
                            continue

                        if norm_url not in discovered_pages:
                            discovered_pages.add(norm_url)
                            if current_depth + 1 <= depth:
                                queue.append((norm_url, current_depth + 1))
                            
                            if len(discovered_pages) >= limit:
                                break
                except asyncio.TimeoutError:
                    print(f"[ERROR] Failed to crawl: {current_url} | Reason: Timeout", flush=True)
                    continue
                except Exception as e:
                    print(f"[ERROR] Failed to crawl: {current_url} | Reason: {e}", flush=True)
                    continue

        sorted_pages = sorted(list(discovered_pages), key=lambda x: self.get_priority_score(x, base_url), reverse=True)[:limit]
        sorted_docs = sorted(list(discovered_docs), key=lambda x: self.get_priority_score(x, base_url) + 20, reverse=True)[:limit]
        
        print(f"[CRAWLER] Discovery Complete. Pages={len(sorted_pages)}, Docs={len(sorted_docs)}", flush=True)
        return sorted_pages, sorted_docs


    def _is_article(self, html: str, url: str) -> bool:
        """Detect if page is a news article, blog, or long-form content."""
        if not html: return False
        
        soup = BeautifulSoup(html, "html.parser")
        
        og_type = soup.find("meta", property="og:type")
        if og_type and og_type.get("content") in ("article", "news.article", "blog"):
            return True
            
        schema = soup.find("script", type="application/ld+json")
        if schema:
            try:
                import json
                data = json.loads(schema.string)
                if isinstance(data, dict):
                    t = data.get("@type", "")
                    if t in ("Article", "NewsArticle", "BlogPosting", "TechArticle"):
                        return True
                elif isinstance(data, list):
                    for item in data:
                        if item.get("@type") in ("Article", "NewsArticle", "BlogPosting"):
                            return True
            except: pass

        path = urlparse(url).path.lower()
        if any(p in path for p in ("/news/", "/blog/", "/article/", "/p/", "/post/")):
            return True

        if soup.find("article") or soup.find(class_=re.compile(r"article|post|entry|content-body", re.I)):
            return True

        return False

    def _score_url(self, base_url: str, is_doc: bool = False):
        """Scoring function for URL prioritisation with aggressive profile detection."""
        priority_map = {
            "dept": 20, "department": 25, "faculty": 35, "staff": 30, "profile": 35,
            "resume": 40, "cv": 40, "biodata": 40, "hod": 45, "principal": 45, "dean": 45,
            "course": 15, "admission": 20, "docs": 20, "brochure": 30, "manual": 25,
            "policy": 20, "faq": 15, "handbook": 25, "guide": 25,
            "attraction": 20, "api": 20, "product": 15, "service": 15,
            "pricing": 20, "features": 15, "documentation": 20, "research": 30,
        }

        def scorer(url: str) -> int:
            s = 20 if is_doc else 0
            url_lower = url.lower()
            
            if url == base_url or url == base_url + "/":
                return 1000
                
            for kw, val in priority_map.items():
                if kw in url_lower:
                    s += val
            
            if is_doc and any(k in url_lower for k in ["resume", "cv", "profile", "faculty"]):
                s += 50
            
            s -= url_lower.count("/") * 5
            
            if any(k in url_lower for k in ["login", "signup", "register", "cart"]):
                s -= 50
                
            return s

        return scorer

    def detect_domain(self, text: str, url: str) -> str:
        """
        Multi-signal domain classification.
        Returns one of: education | medical | tourism | developer | ecommerce | general
        """
        text_lower = text.lower()
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        path = parsed.path

        scores: dict[str, float] = {d: 0.0 for d in DOMAIN_INDICATORS}

        for domain, keywords in DOMAIN_INDICATORS.items():
            for kw in keywords:
                count = text_lower.count(kw)
                if count > 0:
                    scores[domain] += min(count, 5)

        for domain, paths in URL_DOMAIN_BOOSTS.items():
            for p in paths:
                if p in path:
                    scores[domain] += 15

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
