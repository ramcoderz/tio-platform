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

    async def discover_pages(self, base_url: str, limit: int = 10) -> list[str]:
        """Discover important pages on the website."""
        domain = urlparse(base_url).netloc
        discovered = {base_url}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(base_url, wait_until="domcontentloaded", timeout=20000)
                
                # Find all links on the same domain
                links = await page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
                await browser.close()
                
                for link in links:
                    parsed = urlparse(link)
                    if parsed.netloc == domain:
                        # Clean link
                        clean_link = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if clean_link.endswith('/'): clean_link = clean_link[:-1]
                        
                        # Filter ignored patterns
                        if any(re.search(p, clean_link.lower()) for p in self.ignored_patterns):
                            continue
                        
                        discovered.add(clean_link)
                        if len(discovered) >= limit * 2: # Get a pool to prioritize from
                            break
        except Exception as e:
            print(f"Discovery error for {base_url}: {e}")

        # Prioritize important pages
        def score(url):
            s = 0
            for kw in self.priority_keywords:
                if kw in url.lower(): s += 10
            if url == base_url: s += 100
            return s

        sorted_pages = sorted(list(discovered), key=score, reverse=True)
        return sorted_pages[:limit]

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
