import asyncio
import trafilatura
from playwright.async_api import async_playwright
import re
from urllib.parse import urlparse

class Scraper:
    def __init__(self):
        self.ignored_patterns = [
            r'/privacy', r'/cookies', r'/terms', r'/legal', r'/track', r'/login', r'/signup'
        ]
        self.priority_keywords = [
            'about', 'services', 'faq', 'docs', 'products', 'courses', 'departments', 'support'
        ]

    async def extract_content(self, url: str) -> str:
        """Extract semantic content from a URL using Trafilatura."""
        try:
            # Trafilatura is fast and handles most semantic extraction well
            downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
            if not downloaded:
                # Fallback to Playwright if trafilatura fails to fetch
                downloaded = await self._fetch_with_playwright(url)
            
            content = trafilatura.extract(downloaded, include_comments=False, include_tables=True, no_fallback=False)
            return content or ""
        except Exception as e:
            print(f"Scraping error for {url}: {e}")
            return ""

    async def _fetch_with_playwright(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            await browser.close()
            return content

    async def discover_assets(self, base_url: str, limit: int = 20, depth: int = 1) -> tuple[list[str], list[str]]:
        """Discover pages and document links on the website."""
        domain = urlparse(base_url).netloc
        discovered_pages = {base_url}
        discovered_docs = set()
        to_visit = [(base_url, 0)]
        visited = set()
        
        doc_extensions = {'.pdf', '.docx', '.txt', '.md'}

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                while to_visit and (len(discovered_pages) + len(discovered_docs)) < limit * 5:
                    current_url, current_depth = to_visit.pop(0)
                    if current_url in visited or current_depth > depth:
                        continue
                    
                    visited.add(current_url)
                    try:
                        await page.goto(current_url, wait_until="domcontentloaded", timeout=15000)
                        links = await page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
                        
                        for link in links:
                            parsed = urlparse(link)
                            if parsed.netloc == domain:
                                clean_link = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                                if clean_link.endswith('/'): clean_link = clean_link[:-1]
                                
                                # Check if it's a document
                                path_lower = parsed.path.lower()
                                if any(path_lower.endswith(ext) for ext in doc_extensions):
                                    discovered_docs.add(clean_link)
                                    continue

                                # Ignore binaries/archives
                                if any(path_lower.endswith(ext) for ext in {'.exe', '.zip', '.rar', '.msi', '.js', '.bat'}):
                                    continue
                                
                                # Filter ignored patterns
                                if any(re.search(p, clean_link.lower()) for p in self.ignored_patterns):
                                    continue
                                
                                if clean_link not in discovered_pages:
                                    discovered_pages.add(clean_link)
                                    if current_depth + 1 <= depth:
                                        to_visit.append((clean_link, current_depth + 1))
                            
                            if (len(discovered_pages) + len(discovered_docs)) >= limit * 6: break
                    except Exception as e:
                        print(f"Error visiting {current_url}: {e}")
                        continue

                await browser.close()
        except Exception as e:
            print(f"Discovery error for {base_url}: {e}")

        # Prioritize and sort
        def score(url, is_doc=False):
            s = 10 if is_doc else 0
            url_lower = url.lower()
            priority_map = {
                'dept': 20, 'department': 25, 'faculty': 20, 'course': 15, 
                'admission': 20, 'docs': 20, 'brochure': 25, 'manual': 25,
                'policy': 20, 'faq': 15, 'handbook': 25, 'guide': 25
            }
            for kw, val in priority_map.items():
                if kw in url_lower: s += val
            if url == base_url: s += 100
            s -= (url_lower.count('/') * 2)
            return s

        sorted_pages = sorted(list(discovered_pages), key=score, reverse=True)[:limit]
        sorted_docs = sorted(list(discovered_docs), key=lambda x: score(x, True), reverse=True)[:limit]
        
        return sorted_pages, sorted_docs

    def detect_domain(self, text: str, url: str) -> str:
        """Lightweight domain detection based on keywords."""
        text = text.lower()
        url = url.lower()
        
        indicators = {
            "medical": ["health", "medical", "patient", "clinic", "doctor", "treatment", "hospital", "pharmacy"],
            "tourism": ["tour", "travel", "visit", "destination", "itinerary", "hotel", "booking", "tourism", "vacation"],
            "education": ["course", "learn", "student", "university", "school", "curriculum", "education", "academy"],
            "developer": ["api", "documentation", "docs", "developer", "endpoint", "sdk", "code", "integration", "git"],
            "ecommerce": ["product", "shop", "cart", "price", "buy", "order", "shipping", "ecommerce", "store"]
        }
        
        scores = {d: 0 for d in indicators}
        for d, keywords in indicators.items():
            for kw in keywords:
                scores[d] += text.count(kw)
                if kw in url: scores[d] += 10
        
        best_domain = max(scores, key=scores.get)
        if scores[best_domain] < 3: # Threshold for "general"
            return "general"
        return best_domain

scraper = Scraper()
